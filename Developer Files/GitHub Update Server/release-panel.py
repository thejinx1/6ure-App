from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import webbrowser
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import cgi


ROOT = Path(__file__).resolve().parent
DEVELOPER_DIR = ROOT.parent
WORKSPACE_DIR = DEVELOPER_DIR.parent
SOURCE_CODE_DIR = DEVELOPER_DIR / "Source Code"
APPLICATION_DIR = WORKSPACE_DIR / "Application"
DIST_DIR = SOURCE_CODE_DIR / "dist" / "6ure™ App"
PANEL_DIR = ROOT / ".release-panel"
SETTINGS_PATH = PANEL_DIR / "settings.json"
DEFAULT_OWNER = "thejinx1"
DEFAULT_REPO = "6ure-App"
API_VERSION = "2022-11-28"


class PanelError(Exception):
    def __init__(self, message: str, status: int = 400, details: object | None = None):
        super().__init__(message)
        self.status = status
        self.details = details


class GitHubError(PanelError):
    pass


def clean_version(version: str) -> str:
    version = version.strip()
    if not version:
        raise PanelError("Version is required.")
    return version[1:] if version.lower().startswith("v") else version


def tag_for_version(version: str) -> str:
    return f"v{clean_version(version)}"


def safe_asset_name(filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name:
        raise PanelError("Package filename is missing.")
    return re.sub(r"[^A-Za-z0-9._()+ -]+", "-", name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_url(owner: str, repo: str) -> str:
    return f"https://{owner}.github.io/{repo}/latest.json"


def json_bytes(data: object) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_json(path: Path, fallback: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_settings() -> dict:
    settings = load_json(SETTINGS_PATH, {})
    if not isinstance(settings, dict):
        settings = {}
    settings.setdefault("owner", DEFAULT_OWNER)
    settings.setdefault("repo", DEFAULT_REPO)
    settings.setdefault("installerArgs", "/S")
    return settings


def save_settings(settings: dict) -> None:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    safe = {
        "owner": settings.get("owner", DEFAULT_OWNER).strip() or DEFAULT_OWNER,
        "repo": settings.get("repo", DEFAULT_REPO).strip() or DEFAULT_REPO,
        "installerArgs": settings.get("installerArgs", "/S").strip(),
    }
    SETTINGS_PATH.write_text(json.dumps(safe, indent=2), encoding="utf-8")


def write_app_update_config(owner: str, repo: str) -> dict:
    config = {
        "manifestUrl": manifest_url(owner, repo),
        "githubReleasesUrl": f"https://github.com/{owner}/{repo}/releases",
        "channel": "stable",
        "allowInsecure": False,
    }
    updated: list[str] = []
    for path in (
        SOURCE_CODE_DIR / "update-config.json",
        APPLICATION_DIR / "update-config.json",
        DIST_DIR / "update-config.json",
    ):
        if path.parent.exists():
            path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            updated.append(str(path))
    return {"config": config, "updated": updated}


def github_headers(token: str, extra: dict | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token.strip()}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "6ure-app-release-panel",
    }
    if extra:
        headers.update(extra)
    return headers


def github_json(
    session: requests.Session,
    method: str,
    url: str,
    token: str,
    *,
    expected: tuple[int, ...] = (200,),
    **kwargs,
) -> object:
    response = session.request(method, url, headers=github_headers(token), timeout=60, **kwargs)
    if response.status_code not in expected:
        detail = response.text[:2000]
        raise GitHubError(f"GitHub API error {response.status_code}.", status=502, details=detail)
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


def get_repo(session: requests.Session, owner: str, repo: str, token: str) -> dict:
    data = github_json(session, "GET", f"https://api.github.com/repos/{owner}/{repo}", token)
    if not isinstance(data, dict):
        raise GitHubError("GitHub repo response was not valid.")
    return data


def get_or_create_release(
    session: requests.Session,
    owner: str,
    repo: str,
    token: str,
    version: str,
    notes: str,
    prerelease: bool,
) -> dict:
    tag = tag_for_version(version)
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    response = session.get(url, headers=github_headers(token), timeout=60)
    if response.status_code == 200:
        release = response.json()
        patch_url = f"https://api.github.com/repos/{owner}/{repo}/releases/{release['id']}"
        updated = github_json(
            session,
            "PATCH",
            patch_url,
            token,
            json={
                "name": clean_version(version),
                "body": notes,
                "draft": False,
                "prerelease": prerelease,
            },
        )
        if isinstance(updated, dict):
            return updated
        return release
    if response.status_code != 404:
        raise GitHubError(f"GitHub API error {response.status_code}.", status=502, details=response.text[:2000])

    create_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    created = github_json(
        session,
        "POST",
        create_url,
        token,
        expected=(201,),
        json={
            "tag_name": tag,
            "name": clean_version(version),
            "body": notes,
            "draft": False,
            "prerelease": prerelease,
        },
    )
    if not isinstance(created, dict):
        raise GitHubError("GitHub release response was not valid.")
    return created


def delete_existing_asset(
    session: requests.Session,
    owner: str,
    repo: str,
    token: str,
    release_id: int,
    asset_name: str,
) -> list[str]:
    deleted: list[str] = []
    assets = github_json(
        session,
        "GET",
        f"https://api.github.com/repos/{owner}/{repo}/releases/{release_id}/assets",
        token,
    )
    if not isinstance(assets, list):
        return deleted
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == asset_name:
            github_json(
                session,
                "DELETE",
                f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset['id']}",
                token,
                expected=(204,),
            )
            deleted.append(asset_name)
    return deleted


def upload_asset(
    session: requests.Session,
    release: dict,
    token: str,
    package_path: Path,
    asset_name: str,
) -> dict:
    upload_url = str(release.get("upload_url", "")).split("{", 1)[0]
    if not upload_url:
        raise GitHubError("Release upload URL was missing.")
    content_type = mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
    headers = github_headers(token, {"Content-Type": content_type})
    with package_path.open("rb") as handle:
        response = session.post(
            upload_url,
            headers=headers,
            params={"name": asset_name},
            data=handle,
            timeout=600,
        )
    if response.status_code != 201:
        raise GitHubError(f"GitHub upload error {response.status_code}.", status=502, details=response.text[:2000])
    return response.json()


def build_latest_manifest(
    version: str,
    notes: str,
    asset_url: str,
    sha256: str,
    size_bytes: int,
    package_type: str,
    installer_args: str,
) -> dict:
    package_type = package_type if package_type in {"installer", "zip"} else "installer"
    windows = {
        "url": asset_url,
        "sha256": sha256,
        "sizeBytes": size_bytes,
        "packageType": package_type,
    }
    if package_type == "installer":
        windows["installerArgs"] = installer_args.strip()
        windows["successExitCodes"] = [0, 3010]
    return {
        "version": clean_version(version),
        "notes": notes,
        "windows": windows,
    }


def commit_latest_json(
    session: requests.Session,
    owner: str,
    repo: str,
    token: str,
    manifest: dict,
) -> dict:
    repo_data = get_repo(session, owner, repo, token)
    branch = repo_data.get("default_branch") or "main"
    content_url = f"https://api.github.com/repos/{owner}/{repo}/contents/latest.json"
    sha = None
    existing = session.get(
        content_url,
        headers=github_headers(token),
        params={"ref": branch},
        timeout=60,
    )
    if existing.status_code == 200:
        existing_data = existing.json()
        if isinstance(existing_data, dict):
            sha = existing_data.get("sha")
    elif existing.status_code != 404:
        raise GitHubError(f"GitHub contents error {existing.status_code}.", status=502, details=existing.text[:2000])

    body = {
        "message": f"Update latest.json for v{manifest['version']}",
        "content": base64.b64encode(json_bytes(manifest)).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    result = github_json(session, "PUT", content_url, token, expected=(200, 201), json=body)
    if not isinstance(result, dict):
        raise GitHubError("GitHub content update response was not valid.")
    return {"branch": branch, "commit": result.get("commit", {})}


def publish_release(fields: dict, package_path: Path) -> dict:
    owner = fields.get("owner", DEFAULT_OWNER).strip()
    repo = fields.get("repo", DEFAULT_REPO).strip()
    token = fields.get("token", "").strip()
    version = clean_version(fields.get("version", ""))
    notes = fields.get("notes", "").strip()
    package_type = fields.get("packageType", "installer").strip() or "installer"
    installer_args = fields.get("installerArgs", "/S").strip()
    prerelease = fields.get("prerelease", "").lower() in {"1", "true", "yes", "on"}
    asset_name = safe_asset_name(fields.get("assetName") or package_path.name)

    if not owner or not repo:
        raise PanelError("Owner and repo are required.")
    if not token:
        raise PanelError("GitHub token is required.")
    if not package_path.exists():
        raise PanelError("Package file was not saved.")

    size_bytes = package_path.stat().st_size
    sha256 = sha256_file(package_path)

    with requests.Session() as session:
        get_repo(session, owner, repo, token)
        release = get_or_create_release(session, owner, repo, token, version, notes, prerelease)
        deleted_assets = delete_existing_asset(session, owner, repo, token, int(release["id"]), asset_name)
        asset = upload_asset(session, release, token, package_path, asset_name)
        asset_url = asset.get("browser_download_url")
        if not asset_url:
            raise GitHubError("Uploaded asset download URL was missing.")
        manifest = build_latest_manifest(
            version,
            notes,
            asset_url,
            sha256,
            size_bytes,
            package_type,
            installer_args,
        )
        content_result = commit_latest_json(session, owner, repo, token, manifest)

    save_settings({"owner": owner, "repo": repo, "installerArgs": installer_args})
    return {
        "ok": True,
        "version": version,
        "tag": tag_for_version(version),
        "releaseUrl": release.get("html_url"),
        "assetUrl": asset_url,
        "manifestUrl": manifest_url(owner, repo),
        "latest": manifest,
        "deletedAssets": deleted_assets,
        "commit": content_result,
    }


def run_build() -> dict:
    build_script = SOURCE_CODE_DIR / "build.ps1"
    if not build_script.exists():
        raise PanelError("build.ps1 was not found.")
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build_script)],
        cwd=SOURCE_CODE_DIR,
        text=True,
        capture_output=True,
        timeout=900,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "distExe": str(DIST_DIR / "6ure™ App.exe"),
    }


class ReleasePanelHandler(BaseHTTPRequestHandler):
    server_version = "6ureReleasePanel/1.0"

    def log_message(self, format: str, *args: object) -> None:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")

    def send_json(self, data: object, status: int = 200) -> None:
        body = json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, error: Exception, status: int = 500) -> None:
        if isinstance(error, PanelError):
            status = error.status
            payload = {"ok": False, "error": str(error), "details": error.details}
        else:
            payload = {"ok": False, "error": str(error)}
        self.send_json(payload, status)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PanelError(f"Invalid JSON body: {exc}")
        if not isinstance(data, dict):
            raise PanelError("JSON body must be an object.")
        return data

    def read_form(self) -> cgi.FieldStorage:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise PanelError("Expected multipart/form-data.")
        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

    @staticmethod
    def form_value(form: cgi.FieldStorage, name: str, default: str = "") -> str:
        if name not in form:
            return default
        item = form[name]
        if isinstance(item, list):
            item = item[0]
        return getattr(item, "value", default)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/release-panel.html"}:
                html_path = ROOT / "release-panel.html"
                body = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/config":
                settings = load_settings()
                self.send_json(
                    {
                        "ok": True,
                        "owner": settings["owner"],
                        "repo": settings["repo"],
                        "installerArgs": settings["installerArgs"],
                        "manifestUrl": manifest_url(settings["owner"], settings["repo"]),
                        "sourceCodeDir": str(SOURCE_CODE_DIR),
                        "applicationDir": str(APPLICATION_DIR),
                    }
                )
                return
            self.send_json({"ok": False, "error": "Not found."}, 404)
        except Exception as exc:
            self.send_error_json(exc)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/save-settings":
                data = self.read_json_body()
                save_settings(data)
                settings = load_settings()
                self.send_json({"ok": True, **settings, "manifestUrl": manifest_url(settings["owner"], settings["repo"])})
                return
            if path == "/api/set-app-config":
                data = self.read_json_body()
                owner = data.get("owner", DEFAULT_OWNER).strip()
                repo = data.get("repo", DEFAULT_REPO).strip()
                save_settings({"owner": owner, "repo": repo, "installerArgs": data.get("installerArgs", "")})
                self.send_json({"ok": True, **write_app_update_config(owner, repo)})
                return
            if path == "/api/check-pages":
                data = self.read_json_body()
                owner = data.get("owner", DEFAULT_OWNER).strip()
                repo = data.get("repo", DEFAULT_REPO).strip()
                url = manifest_url(owner, repo)
                response = requests.get(url, headers={"Cache-Control": "no-cache"}, timeout=20)
                payload = {
                    "ok": response.ok,
                    "status": response.status_code,
                    "url": url,
                    "body": response.text[:1200],
                }
                self.send_json(payload, 200 if response.ok else 502)
                return
            if path == "/api/build-app":
                self.send_json(run_build())
                return
            if path == "/api/publish":
                form = self.read_form()
                file_item = form["package"] if "package" in form else None
                if file_item is None or not getattr(file_item, "filename", ""):
                    raise PanelError("Choose a setup EXE or ZIP file first.")
                asset_name = safe_asset_name(file_item.filename)
                fields = {
                    "owner": self.form_value(form, "owner", DEFAULT_OWNER),
                    "repo": self.form_value(form, "repo", DEFAULT_REPO),
                    "token": self.form_value(form, "token", ""),
                    "version": self.form_value(form, "version", ""),
                    "notes": self.form_value(form, "notes", ""),
                    "packageType": self.form_value(form, "packageType", "installer"),
                    "installerArgs": self.form_value(form, "installerArgs", "/S"),
                    "prerelease": self.form_value(form, "prerelease", ""),
                    "assetName": asset_name,
                }
                temp_dir = Path(tempfile.mkdtemp(prefix="6ure-release-panel-"))
                package_path = temp_dir / asset_name
                try:
                    with package_path.open("wb") as output:
                        shutil.copyfileobj(file_item.file, output)
                    self.send_json(publish_release(fields, package_path))
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return
            self.send_json({"ok": False, "error": "Not found."}, 404)
        except Exception as exc:
            self.send_error_json(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="6ure App GitHub release panel")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), ReleasePanelHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Release panel: {url}")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping release panel.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
