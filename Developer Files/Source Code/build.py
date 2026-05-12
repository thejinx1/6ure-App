from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "6ure™ App"


def source_root() -> Path:
    return Path(__file__).resolve().parent


def clean_version(value: str) -> str:
    text = str(value or "").strip().lstrip("v")
    return text if re.fullmatch(r"\d+(?:\.\d+){0,3}", text) else ""


def default_app_version(root: Path) -> str:
    for value in (os.environ.get("REYLI_APP_VERSION"), os.environ.get("APP_VERSION")):
        version = clean_version(value or "")
        if version:
            return version

    server_path = root / "server.py"
    match = re.search(r'DEFAULT_APP_VERSION\s*=\s*"([^"]+)"', server_path.read_text(encoding="utf-8"))
    version = clean_version(match.group(1) if match else "")
    if not version:
        raise RuntimeError("App version was not set and DEFAULT_APP_VERSION could not be read.")
    return version


def write_app_version(root: Path, version: str) -> None:
    (root / "app-version.json").write_text(
        json.dumps({"version": version}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def windows_version_tuple(version: str) -> tuple[str, str]:
    parts = [int(part) for part in re.findall(r"\d+", version)[:4]]
    while len(parts) < 4:
        parts.append(0)
    parts = [min(part, 65535) for part in parts]
    return ", ".join(str(part) for part in parts), ".".join(str(part) for part in parts)


def write_windows_version_info(root: Path, version: str) -> None:
    file_version_tuple, file_version_text = windows_version_tuple(version)
    payload = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({file_version_tuple}),
    prodvers=({file_version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'reyli'),
          StringStruct('FileDescription', '6ure App desktop client'),
          StringStruct('FileVersion', '{file_version_text}'),
          StringStruct('InternalName', '6ure App'),
          StringStruct('OriginalFilename', '6ure App.exe'),
          StringStruct('ProductName', '6ure App'),
          StringStruct('ProductVersion', '{file_version_text}'),
          StringStruct('LegalCopyright', 'Copyright reyli')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    (root / "version_info.txt").write_text(payload, encoding="utf-8")


def ensure_macos_icns(root: Path) -> None:
    if sys.platform != "darwin":
        return
    icon_path = root / "assets" / "6ure-logo.icns"
    png_path = root / "assets" / "6ure-logo.png"
    if icon_path.exists() or not png_path.exists():
        return
    if not shutil.which("sips") or not shutil.which("iconutil"):
        print("macOS icon tools were not found; building without a .icns icon.", file=sys.stderr)
        return

    iconset = root / "build" / "6ure-logo.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    icon_targets = (
        (16, 1),
        (16, 2),
        (32, 1),
        (32, 2),
        (128, 1),
        (128, 2),
        (256, 1),
        (256, 2),
        (512, 1),
        (512, 2),
    )
    for size, scale in icon_targets:
        pixels = size * scale
        scale_suffix = "@2x" if scale == 2 else ""
        output = iconset / f"icon_{size}x{size}{scale_suffix}.png"
        subprocess.run(["sips", "-z", str(pixels), str(pixels), str(png_path), "--out", str(output)], check=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icon_path)], check=True)


def run_pyinstaller(root: Path, version: str, clean: bool) -> None:
    env = os.environ.copy()
    env["REYLI_APP_VERSION"] = version
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if clean:
        command.append("--clean")
    command.append(str(root / "6ure Files.spec"))
    subprocess.run(command, cwd=str(root), env=env, check=True)


def copy_runtime_config(root: Path) -> list[Path]:
    dist_root = root / "dist"
    runtime_roots: list[Path] = []
    onedir = dist_root / APP_NAME
    mac_app = dist_root / f"{APP_NAME}.app"

    if onedir.exists():
        runtime_roots.append(onedir)
    if mac_app.exists():
        runtime_roots.extend([mac_app / "Contents" / "MacOS", mac_app / "Contents" / "Resources"])

    for target_root in runtime_roots:
        target_root.mkdir(parents=True, exist_ok=True)
        for name in ("update-config.json", "discord-presence.json", "app-version.json"):
            source = root / name
            if source.exists():
                shutil.copy2(source, target_root / name)
    return runtime_roots


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the 6ure desktop app for the current platform.")
    parser.add_argument("--version", default="", help="App version to stamp into app-version.json and package metadata.")
    parser.add_argument("--no-clean", action="store_true", help="Skip PyInstaller's clean build mode.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = source_root()
    version = clean_version(args.version) or default_app_version(root)
    write_app_version(root, version)
    write_windows_version_info(root, version)
    ensure_macos_icns(root)
    run_pyinstaller(root, version, clean=not args.no_clean)
    runtime_roots = copy_runtime_config(root)

    print(f"App version: {version}")
    if runtime_roots:
        print("Runtime config copied to:")
        for path in runtime_roots:
            print(f"  {path}")
    print(f"Built output: {root / 'dist'}")


if __name__ == "__main__":
    main()
