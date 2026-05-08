from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Literal

import aiohttp
import discord
import uvicorn
from discord import app_commands
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse


load_dotenv()

APP_NAME = os.environ.get("APP_NAME", "6ure Files")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "data")).expanduser().resolve()
PACKAGE_DIR = DATA_DIR / "packages"
LATEST_PATH = DATA_DIR / "latest.json"
HISTORY_PATH = DATA_DIR / "release-history.json"
MAX_PACKAGE_BYTES = int(os.environ.get("MAX_PACKAGE_BYTES", str(600 * 1024 * 1024)))
DEFAULT_INSTALLER_ARGS = os.environ.get("DEFAULT_INSTALLER_ARGS", "/VERYSILENT /NORESTART").strip()
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "").strip()
DISCORD_ALLOWED_USER_IDS = {
    int(item.strip())
    for item in os.environ.get("DISCORD_ALLOWED_USER_IDS", "").split(",")
    if item.strip().isdigit()
}
DISCORD_ANNOUNCE_CHANNEL_ID = os.environ.get("DISCORD_ANNOUNCE_CHANNEL_ID", "").strip()

DATA_DIR.mkdir(parents=True, exist_ok=True)
PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=f"{APP_NAME} Updater")


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    cleaned = cleaned.strip(".-")
    return cleaned or "package"


def infer_package_type(filename: str, requested: str | None = None) -> str:
    if requested in {"installer", "zip"}:
        return requested
    lower = filename.lower()
    return "zip" if lower.endswith(".zip") else "installer"


def package_url(filename: str) -> str:
    quoted = urllib.parse.quote(filename)
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/packages/{quoted}"
    return f"packages/{quoted}"


def read_latest() -> dict:
    if not LATEST_PATH.exists():
        return {
            "version": "0.0.0",
            "notes": "",
            "windows": {},
        }
    try:
        data = json.loads(LATEST_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {}


def write_latest(payload: dict) -> None:
    tmp_path = LATEST_PATH.with_suffix(".tmp")
    tmp_path.write_bytes(json_bytes(payload))
    os.replace(tmp_path, LATEST_PATH)


def append_history(payload: dict) -> None:
    try:
        history = json.loads(HISTORY_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        history = []
    if not isinstance(history, list):
        history = []
    history.insert(0, payload)
    HISTORY_PATH.write_bytes(json_bytes({"releases": history[:50]}))


async def download_package(url: str, target: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    downloaded = 0
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"Package download returned HTTP {response.status}.")
            with target.open("wb") as handle:
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > MAX_PACKAGE_BYTES:
                        raise RuntimeError("Package is larger than MAX_PACKAGE_BYTES.")
                    digest.update(chunk)
                    handle.write(chunk)
    return digest.hexdigest(), downloaded


def build_manifest(
    version: str,
    notes: str,
    filename: str,
    sha256: str,
    size_bytes: int,
    package_type: str,
) -> dict:
    windows = {
        "url": package_url(filename),
        "sha256": sha256,
        "sizeBytes": size_bytes,
        "packageType": package_type,
    }
    if package_type == "installer":
        windows["installerArgs"] = DEFAULT_INSTALLER_ARGS
        windows["successExitCodes"] = [0, 3010]
    return {
        "version": version.strip().lstrip("v"),
        "notes": notes.strip(),
        "releasedAt": int(time.time() * 1000),
        "windows": windows,
    }


def user_is_allowed(user_id: int) -> bool:
    return not DISCORD_ALLOWED_USER_IDS or user_id in DISCORD_ALLOWED_USER_IDS


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"


@app.get("/latest.json")
async def latest_json() -> JSONResponse:
    return JSONResponse(read_latest(), headers={"Cache-Control": "no-store"})


@app.get("/packages/{filename}")
async def get_package(filename: str) -> FileResponse:
    clean_filename = Path(filename).name
    path = PACKAGE_DIR / clean_filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Package not found.")
    return FileResponse(path, filename=clean_filename)


class ReleaseModal(discord.ui.Modal, title="Publish Release"):
    version = discord.ui.TextInput(
        label="Version",
        placeholder="1.0.1",
        max_length=32,
        required=True,
    )
    notes = discord.ui.TextInput(
        label="Release notes",
        style=discord.TextStyle.paragraph,
        placeholder="Added cloud manager\nImproved updater",
        max_length=1800,
        required=True,
    )

    def __init__(self, package_source_url: str, source_filename: str, package_type: str) -> None:
        super().__init__()
        self.package_source_url = package_source_url
        self.source_filename = source_filename
        self.package_type = package_type

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not user_is_allowed(interaction.user.id):
            await interaction.response.send_message("You are not allowed to publish releases.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        clean_version = safe_name(str(self.version.value).strip().lstrip("v"))
        extension = Path(self.source_filename).suffix or (".zip" if self.package_type == "zip" else ".exe")
        target_filename = f"6ure-files-{clean_version}-{safe_name(Path(self.source_filename).stem)}{extension}"
        target_path = PACKAGE_DIR / target_filename
        tmp_path = PACKAGE_DIR / f"{target_filename}.tmp"

        try:
            sha256, size_bytes = await download_package(self.package_source_url, tmp_path)
            os.replace(tmp_path, target_path)
            manifest = build_manifest(
                version=clean_version,
                notes=str(self.notes.value),
                filename=target_filename,
                sha256=sha256,
                size_bytes=size_bytes,
                package_type=self.package_type,
            )
            write_latest(manifest)
            append_history(
                {
                    "publisherId": interaction.user.id,
                    "publisher": str(interaction.user),
                    "manifest": manifest,
                }
            )
        except Exception as error:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            await interaction.followup.send(f"Release failed: {error}", ephemeral=True)
            return

        await interaction.followup.send(
            f"Release v{clean_version} published.\nManifest: `/latest.json`\nPackage: `{target_filename}`",
            ephemeral=True,
        )
        await announce_release(manifest)


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


async def announce_release(manifest: dict) -> None:
    if not DISCORD_ANNOUNCE_CHANNEL_ID.isdigit():
        return
    channel = bot.get_channel(int(DISCORD_ANNOUNCE_CHANNEL_ID))
    if channel is None:
        return
    version = manifest.get("version", "")
    notes = manifest.get("notes", "")
    try:
        await channel.send(f"{APP_NAME} v{version} is ready.\n{notes}")
    except Exception:
        pass


@tree.command(name="release", description="Publish a new application release.")
@app_commands.describe(
    package="Setup exe, MSI, or portable zip to publish",
    package_url="Alternative HTTPS package URL",
    package_type="Use installer for setup exe/MSI, zip for portable app zips",
)
async def release(
    interaction: discord.Interaction,
    package: discord.Attachment | None = None,
    package_url: str | None = None,
    package_type: Literal["installer", "zip"] | None = None,
) -> None:
    if not user_is_allowed(interaction.user.id):
        await interaction.response.send_message("You are not allowed to publish releases.", ephemeral=True)
        return
    if package is None and not package_url:
        await interaction.response.send_message("Attach a setup exe/zip or provide package_url.", ephemeral=True)
        return

    source_url = package.url if package else str(package_url or "").strip()
    source_filename = package.filename if package else Path(urllib.parse.urlsplit(source_url).path).name
    if not source_url.lower().startswith("https://"):
        await interaction.response.send_message("Package URL must use HTTPS.", ephemeral=True)
        return
    if not source_filename:
        source_filename = "setup.exe"
    resolved_type = infer_package_type(source_filename, package_type)
    await interaction.response.send_modal(ReleaseModal(source_url, source_filename, resolved_type))


@tree.command(name="release_status", description="Show the latest published release.")
async def release_status(interaction: discord.Interaction) -> None:
    if not user_is_allowed(interaction.user.id):
        await interaction.response.send_message("You are not allowed to view release status.", ephemeral=True)
        return
    latest = read_latest()
    version = latest.get("version", "none")
    notes = latest.get("notes", "")
    package = latest.get("windows", {}).get("url", "")
    await interaction.response.send_message(
        f"Latest: v{version}\nPackage: {package}\nNotes:\n{notes}",
        ephemeral=True,
    )


@bot.event
async def on_ready() -> None:
    if DISCORD_GUILD_ID.isdigit():
        guild = discord.Object(id=int(DISCORD_GUILD_ID))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    print(f"{bot.user} is ready. Serving updates on {HOST}:{PORT}")


def run_api() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"))


async def run_bot() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is required.")
    await bot.start(DISCORD_TOKEN)


def main() -> None:
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
