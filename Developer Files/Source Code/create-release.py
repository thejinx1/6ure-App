from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from build import APP_NAME, clean_version, default_app_version, source_root


def current_platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"Unsupported release platform: {sys.platform}")


def architecture_label() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "x64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    return machine or "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_directory_contents(source_dir: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def zip_directory(source_dir: Path, target_zip: Path, arcname: str) -> None:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(arcname) / path.relative_to(source_dir))


def tar_gz_directory(source_dir: Path, target_tar: Path, arcname: str) -> None:
    with tarfile.open(target_tar, "w:gz") as archive:
        archive.add(source_dir, arcname=arcname)


def create_macos_dmg(app_bundle: Path, target_dmg: Path) -> bool:
    if sys.platform != "darwin" or not shutil.which("hdiutil"):
        return False
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(app_bundle),
            "-ov",
            "-format",
            "UDZO",
            str(target_dmg),
        ],
        check=True,
    )
    return True


def build_current_platform(root: Path, version: str) -> None:
    subprocess.run([sys.executable, str(root / "build.py"), "--version", version], cwd=str(root), check=True)


def package_current_platform(root: Path, version: str, output_dir: Path) -> tuple[Path, str, dict]:
    platform_key = current_platform_key()
    arch = architecture_label()
    output_dir.mkdir(parents=True, exist_ok=True)

    if platform_key == "windows":
        dist_dir = root / "dist" / APP_NAME
        if not dist_dir.is_dir():
            raise RuntimeError(f"Windows dist folder was not found: {dist_dir}")
        package_path = output_dir / f"6ure-app-{version}-win-{arch}.zip"
        package_path.unlink(missing_ok=True)
        zip_directory_contents(dist_dir, package_path)
        return package_path, "zip", {}

    if platform_key == "macos":
        app_bundle = root / "dist" / f"{APP_NAME}.app"
        if not app_bundle.is_dir():
            raise RuntimeError(f"macOS app bundle was not found: {app_bundle}")
        dmg_path = output_dir / f"6ure-app-{version}-macos-{arch}.dmg"
        dmg_path.unlink(missing_ok=True)
        if create_macos_dmg(app_bundle, dmg_path):
            return dmg_path, "dmg", {}

        zip_path = output_dir / f"6ure-app-{version}-macos-{arch}.zip"
        zip_path.unlink(missing_ok=True)
        zip_directory(app_bundle, zip_path, app_bundle.name)
        return zip_path, "zip", {"installMode": "manual"}

    dist_dir = root / "dist" / APP_NAME
    if not dist_dir.is_dir():
        raise RuntimeError(f"Linux dist folder was not found: {dist_dir}")
    package_path = output_dir / f"6ure-app-{version}-linux-{arch}.tar.gz"
    package_path.unlink(missing_ok=True)
    tar_gz_directory(dist_dir, package_path, APP_NAME)
    return package_path, "tar.gz", {}


def load_existing_manifest(path: Path) -> dict:
    try:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and package a 6ure desktop release for the current platform.")
    parser.add_argument("--version", default="", help="Release version. Defaults to DEFAULT_APP_VERSION.")
    parser.add_argument("--base-url", default="", help="Base URL used in latest.json package URLs.")
    parser.add_argument("--output-dir", default="releases", help="Release output directory.")
    parser.add_argument("--notes", default="", help="Release notes stored in latest.json.")
    parser.add_argument("--skip-build", action="store_true", help="Package the existing dist output without rebuilding.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = source_root()
    version = clean_version(args.version) or default_app_version(root)
    if not args.skip_build:
        build_current_platform(root, version)

    output_dir = (root / args.output_dir).resolve()
    package_path, package_type, extra_payload = package_current_platform(root, version, output_dir)
    package_url = f"{args.base_url.rstrip('/')}/{package_path.name}" if args.base_url else f"https://example.com/updates/{package_path.name}"

    payload = {
        "url": package_url,
        "sha256": sha256_file(package_path),
        "sizeBytes": package_path.stat().st_size,
        "packageType": package_type,
    }
    payload.update(extra_payload)
    manifest_path = output_dir / "latest.json"
    manifest = load_existing_manifest(manifest_path)
    manifest["version"] = version
    manifest["notes"] = args.notes
    manifest[current_platform_key()] = payload
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Release package: {package_path}")
    print(f"Manifest: {manifest_path}")
    print(f"SHA256: {payload['sha256']}")


if __name__ == "__main__":
    main()
