# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path


APP_NAME = "6ure™ App"
APP_VERSION = (os.environ.get("REYLI_APP_VERSION") or os.environ.get("APP_VERSION") or "1.5.2").strip().lstrip("v")
ROOT = Path.cwd()
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

DATAS = [
    ("index.html", "."),
    ("assets", "assets"),
    ("discord-presence.json", "."),
    ("app-version.json", "."),
    ("ffx-effect-names.json", "."),
]

HIDDEN_IMPORTS = []
if IS_WINDOWS:
    HIDDEN_IMPORTS.append("webview.platforms.edgechromium")
elif IS_MACOS:
    HIDDEN_IMPORTS.append("webview.platforms.cocoa")
elif IS_LINUX:
    HIDDEN_IMPORTS.extend(["webview.platforms.gtk", "webview.platforms.qt"])

VERSION_FILE = "version_info.txt" if IS_WINDOWS and (ROOT / "version_info.txt").exists() else None
WINDOWS_ICON = "assets/6ure-logo.ico" if IS_WINDOWS and (ROOT / "assets" / "6ure-logo.ico").exists() else None
MAC_ICON = "assets/6ure-logo.icns" if IS_MACOS and (ROOT / "assets" / "6ure-logo.icns").exists() else None
BUNDLE_ID = os.environ.get("REYLI_MAC_BUNDLE_ID") or "com.reyli.sixure-app"


a = Analysis(
    ["files_app.py"],
    pathex=[],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    append_pkg=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=IS_MACOS,
    target_arch=os.environ.get("REYLI_TARGET_ARCH") or None,
    codesign_identity=os.environ.get("REYLI_MAC_CODESIGN_IDENTITY") or None,
    entitlements_file=os.environ.get("REYLI_MAC_ENTITLEMENTS") or None,
    version=VERSION_FILE,
    icon=WINDOWS_ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=MAC_ICON,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION or "1.5.2",
            "CFBundleVersion": APP_VERSION or "1.5.2",
            "LSMinimumSystemVersion": "10.15",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
        },
    )
