from __future__ import annotations

import atexit
import base64
import concurrent.futures
import ctypes
import http.cookiejar
import http.cookies
import html
import json
import hashlib
import email.utils
import mimetypes
import os
import posixpath
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import uuid
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken

from discord_presence import DiscordPresenceManager, load_presence_config


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


ROOT = resource_root()
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
DEFAULT_APP_VERSION = "1.4.3"
APP_VERSION_FILE_NAME = os.environ.get("REYLI_APP_VERSION_FILE", "app-version.json")


def clean_app_version(value: str) -> str:
    text = str(value or "").strip().lstrip("v")
    return text if re.fullmatch(r"\d+(?:\.\d+){0,3}", text) else ""


def load_app_version() -> str:
    env_version = clean_app_version(os.environ.get("REYLI_APP_VERSION", ""))
    if env_version:
        return env_version

    seen: set[Path] = set()
    for root in (ROOT, APP_ROOT):
        path = (root / APP_VERSION_FILE_NAME).resolve()
        if path in seen:
            continue
        seen.add(path)
        try:
            if not path.exists():
                continue
            raw = path.read_text(encoding="utf-8-sig").strip()
            if not raw:
                continue
            if raw.startswith("{"):
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    version = clean_app_version(payload.get("version") or payload.get("appVersion") or "")
                    if version:
                        return version
            version = clean_app_version(raw)
            if version:
                return version
        except Exception:
            continue

    return DEFAULT_APP_VERSION


APP_VERSION = load_app_version()
DATA_ROOT = Path(os.environ.get("REYLI_DATA_DIR", str(ROOT))).expanduser().resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)
PORT = int(os.environ.get("PORT", "4173"))
MAX_BODY_BYTES = 2 * 1024 * 1024
CONFIG_FILE_NAME = os.environ.get("REYLI_CONFIG_FILE", "6ure-files-state.json")
CONFIG_BACKUP_FILE_NAME = os.environ.get("REYLI_CONFIG_BACKUP_FILE", "6ure-files-state.backup.json")
CONFIG_TMP_FILE_NAME = os.environ.get("REYLI_CONFIG_TMP_FILE", "6ure-files-state.tmp")
CONFIG_PATH = DATA_ROOT / CONFIG_FILE_NAME
CONFIG_BACKUP_PATH = DATA_ROOT / CONFIG_BACKUP_FILE_NAME
CONFIG_TMP_PATH = DATA_ROOT / CONFIG_TMP_FILE_NAME
PROTECTED_STATIC_NAMES = {CONFIG_PATH.name, CONFIG_BACKUP_PATH.name, CONFIG_TMP_PATH.name}
APP_SETTINGS_FILE_NAME = os.environ.get("REYLI_APP_SETTINGS_FILE", "app-settings.json")
APP_SETTINGS_PATH = DATA_ROOT / APP_SETTINGS_FILE_NAME
APP_SETTINGS_TMP_PATH = DATA_ROOT / f"{APP_SETTINGS_FILE_NAME}.tmp"
VAULT_FILE_NAME = os.environ.get("REYLI_VAULT_FILE", "6ure-secure-vault.json")
VAULT_KEY_FILE_NAME = os.environ.get("REYLI_VAULT_KEY_FILE", "6ure-secure-vault.key")
VAULT_PATH = DATA_ROOT / VAULT_FILE_NAME
VAULT_KEY_PATH = DATA_ROOT / VAULT_KEY_FILE_NAME
DEBUG_BUNDLE_DIR = DATA_ROOT / "debug-bundles"
REPAIR_LOG_PATH = DATA_ROOT / "last-repair.json"
PROTECTED_STATIC_NAMES.update(
    {
        APP_SETTINGS_PATH.name,
        APP_SETTINGS_TMP_PATH.name,
        VAULT_PATH.name,
        VAULT_KEY_PATH.name,
        REPAIR_LOG_PATH.name,
    }
)
LEAKER_PROXY_COOKIE_PATH = DATA_ROOT / "leaker-proxy-cookies.lwp"
PROTECTED_STATIC_NAMES.add(LEAKER_PROXY_COOKIE_PATH.name)
HLX_API_KEY_FILE_NAME = os.environ.get("REYLI_HLX_API_KEY_FILE", "hlx-api-key.txt")
HLX_API_KEY_PATH = DATA_ROOT / HLX_API_KEY_FILE_NAME
PROTECTED_STATIC_NAMES.add(HLX_API_KEY_FILE_NAME)
UPDATE_CONFIG_FILE_NAME = os.environ.get("REYLI_UPDATE_CONFIG_FILE", "update-config.json")
PROTECTED_STATIC_NAMES.add(UPDATE_CONFIG_FILE_NAME)
DISCORD_PRESENCE_CONFIG_FILE_NAME = os.environ.get(
    "REYLI_DISCORD_PRESENCE_CONFIG_FILE",
    "discord-presence.json",
)
PROTECTED_STATIC_NAMES.add(DISCORD_PRESENCE_CONFIG_FILE_NAME)
UPDATE_DOWNLOAD_DIR = DATA_ROOT / "updates"
UPDATE_BACKUP_DIR = DATA_ROOT / "update-backups"
UPDATE_MAX_PACKAGE_BYTES = int(os.environ.get("REYLI_UPDATE_MAX_PACKAGE_BYTES", str(500 * 1024 * 1024)))
UPDATE_STATE_LOCK = threading.Lock()
UPDATE_STATE = {
    "checking": False,
    "installing": False,
    "lastCheckAt": 0,
    "lastError": "",
    "latest": None,
    "installPhase": "",
    "installMessage": "",
    "downloadedBytes": 0,
    "totalBytes": None,
    "installProgress": 0,
    "installStartedAt": 0,
    "installUpdatedAt": 0,
}
DISCORD_PRESENCE_LOCK = threading.Lock()
DISCORD_PRESENCE: DiscordPresenceManager | None = None
FILES_BASE_URL = "https://files.6ureleaks.com"
FILES_SITE_URL = f"{FILES_BASE_URL}/web/client/files"
DASHBOARD_URL = "https://6ureleaks.com/dashboard"
RESOURCES_URL = "https://6ureleaks.com/resources"
RESOURCES_API_URL = "https://6ureleaks.com/api/resources"
PROTECTED_LIST_PAGE_URL = "https://6ureleaks.com/requests/protected"
PROTECTED_LIST_API_URL = "https://6ureleaks.com/api/protection/users"
LEAKER_SITE_BASE_URL = "https://6ureleaks.com"
LEAKER_PROXY_PREFIX = "/leaker-proxy"
LEAKER_OAUTH_BRIDGE_PATH = "/leaker-oauth/bridge"
APP_DISCORD_OAUTH_URL = os.environ.get(
    "REYLI_APP_DISCORD_OAUTH_URL",
    "https://discord.com/oauth2/authorize?client_id=948565930034749501&redirect_uri=https%3A%2F%2F6ureleaks.com%2Frequests%2Fapi%2Fauth%2Fdiscord%2Fcallback&response_type=code&scope=identify+guilds&state=eyJjYWxsYmFja1VybCI6Imh0dHBzOi8vNnVyZWxlYWtzLmNvbS8iLCJ0IjoxNzc4MjQzNzYzNTE0LCJuIjoiZWMxZGExMGIxNWFlOWQ1YmI0M2VjYzIxYTI5MzFlNTIifQ.c5eb5f8863df611a9d0216549dc3b0163f7a868471e4c7cc0b887ea4f69ad2bd",
).strip()
LEAKER_PROXY_TIMEOUT_SECONDS = 45
LEAKER_PROXY_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
DISCORD_OAUTH_HOSTS = {"discord.com", "ptb.discord.com", "canary.discord.com", "discordapp.com"}
ALLOWED_EXTERNAL_HOSTS = {
    "6ureleaks.com",
    "files.6ureleaks.com",
    "discord.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}
NETWORK_CHECK_HOSTS = (
    ("files.6ureleaks.com", 443),
    ("6ureleaks.com", 443),
    ("discord.com", 443),
)
HLX_API_BASE_URL = os.environ.get("REYLI_HLX_API_BASE_URL", "https://api.hlx.li").strip().rstrip("/")
HLX_API_TIMEOUT_SECONDS = float(os.environ.get("REYLI_HLX_API_TIMEOUT_SECONDS", "5.5"))
HLX_API_CONNECT_TIMEOUT_SECONDS = float(os.environ.get("REYLI_HLX_API_CONNECT_TIMEOUT_SECONDS", "1.6"))
HLX_API_RETRIES = int(os.environ.get("REYLI_HLX_API_RETRIES", "1"))
HLX_TIKTOK_CACHE_SECONDS = float(os.environ.get("REYLI_HLX_TIKTOK_CACHE_SECONDS", "120"))
HLX_TIKTOK_SEARCH_DEFAULT_RESULTS = int(os.environ.get("REYLI_HLX_TIKTOK_SEARCH_DEFAULT_RESULTS", "5"))
HLX_TIKTOK_SEARCH_MAX_CANDIDATES = int(os.environ.get("REYLI_HLX_TIKTOK_SEARCH_MAX_CANDIDATES", "6"))
HLX_TIKTOK_SEARCH_MAX_WORKERS = int(os.environ.get("REYLI_HLX_TIKTOK_SEARCH_MAX_WORKERS", "6"))
HLX_TIKTOK_SEARCH_BUDGET_SECONDS = float(os.environ.get("REYLI_HLX_TIKTOK_SEARCH_BUDGET_SECONDS", "3.2"))
HLX_TIKTOK_DETAIL_BUDGET_SECONDS = float(os.environ.get("REYLI_HLX_TIKTOK_DETAIL_BUDGET_SECONDS", "3.8"))
HLX_YOUTUBE_SEARCH_DEFAULT_RESULTS = int(os.environ.get("REYLI_HLX_YOUTUBE_SEARCH_DEFAULT_RESULTS", "5"))
HLX_YOUTUBE_SEARCH_MAX_CANDIDATES = int(os.environ.get("REYLI_HLX_YOUTUBE_SEARCH_MAX_CANDIDATES", "16"))
HLX_YOUTUBE_SEARCH_MAX_WORKERS = int(os.environ.get("REYLI_HLX_YOUTUBE_SEARCH_MAX_WORKERS", "6"))
HLX_YOUTUBE_SEARCH_BUDGET_SECONDS = float(os.environ.get("REYLI_HLX_YOUTUBE_SEARCH_BUDGET_SECONDS", "2.4"))
HLX_YOUTUBE_DISCOVERY_CACHE_SECONDS = float(os.environ.get("REYLI_HLX_YOUTUBE_DISCOVERY_CACHE_SECONDS", "300"))
HLX_YOUTUBE_DISCOVERY_TIMEOUT_SECONDS = float(os.environ.get("REYLI_HLX_YOUTUBE_DISCOVERY_TIMEOUT_SECONDS", "3.4"))
HLX_TIKTOK_LOCK = threading.RLock()
HLX_TIKTOK_CACHE: dict[str, dict] = {}
HLX_YOUTUBE_DISCOVERY_LOCK = threading.RLock()
HLX_YOUTUBE_DISCOVERY_CACHE: dict[str, dict] = {}
HLX_API_KEY_LOCK = threading.RLock()
HLX_API_KEY_CACHE = {"path": "", "mtime": 0.0, "key": ""}
HLX_HTTP_LOCAL = threading.local()
YOUTUBE_WEB_LOCAL = threading.local()
MY_RESOURCES_UPLOADER_ID = os.environ.get("REYLI_RESOURCES_UPLOADER_ID", "1421177012814614548").strip()
MY_RESOURCES_UPLOADER_ALIASES = tuple(
    alias.strip().casefold().lstrip("@")
    for alias in os.environ.get("REYLI_RESOURCES_UPLOADER_ALIASES", "reyliar,reyli").split(",")
    if alias.strip()
)
MY_RESOURCES_PAGE_LIMIT = 100
MY_RESOURCES_MAX_PAGES = int(os.environ.get("REYLI_RESOURCES_MAX_PAGES", "40"))
MY_RESOURCES_CACHE_SECONDS = float(os.environ.get("REYLI_RESOURCES_CACHE_SECONDS", "90"))
MY_RESOURCES_LOCK = threading.RLock()
MY_RESOURCES_CACHE: dict[str, dict] = {}
RESOURCE_DETAIL_CACHE_SECONDS = float(os.environ.get("REYLI_RESOURCE_DETAIL_CACHE_SECONDS", "45"))
RESOURCE_DETAIL_LOCK = threading.RLock()
RESOURCE_DETAIL_CACHE: dict[int, dict] = {}
APP_AUTH_PROFILE_CACHE_SECONDS = float(os.environ.get("REYLI_APP_AUTH_PROFILE_CACHE_SECONDS", "0"))
APP_AUTH_NEGATIVE_CACHE_SECONDS = float(os.environ.get("REYLI_APP_AUTH_NEGATIVE_CACHE_SECONDS", "4"))
APP_AUTH_LOCK = threading.RLock()
APP_AUTH_STATE = {
    "authenticated": False,
    "user": None,
    "checkedAt": 0.0,
    "updatedAt": 0.0,
    "lastError": "",
}
FILES_MIN_ACTION_INTERVAL = float(os.environ.get("REYLI_FILES_MIN_ACTION_INTERVAL", "0.25"))
FILES_TASK_POLL_INTERVAL = float(os.environ.get("REYLI_FILES_TASK_POLL_INTERVAL", "0.35"))
FILES_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024 * 80
FILES_EXTRACT_MAX_ZIP_BYTES = int(os.environ.get("REYLI_FILES_EXTRACT_MAX_ZIP_BYTES", str(FILES_MAX_UPLOAD_BYTES)))
FILES_EXTRACT_MAX_TOTAL_BYTES = int(
    os.environ.get("REYLI_FILES_EXTRACT_MAX_TOTAL_BYTES", str(FILES_MAX_UPLOAD_BYTES))
)
FILES_EXTRACT_MAX_FILES = int(os.environ.get("REYLI_FILES_EXTRACT_MAX_FILES", "250000"))
FILES_UPLOAD_HISTORY_LIMIT = 24
FILES_JOBS: dict[str, "FilesUploadJob"] = {}
FILES_JOBS_LOCK = threading.Lock()
AUTH_LOCK = threading.Lock()
AUTH_STATE = {
    "authenticated": False,
    "username": "",
    "password": "",
}
REMOTE_CLIENT_LOCK = threading.Lock()
REMOTE_CLIENT_TTL_SECONDS = float(os.environ.get("REYLI_REMOTE_CLIENT_TTL_SECONDS", "600"))
REMOTE_CLIENT_CACHE = {
    "username": "",
    "password": "",
    "client": None,
    "expiresAt": 0.0,
}
LEAKER_PROXY_SESSION = requests.Session()
LEAKER_PROXY_LOCK = threading.RLock()
LEAKER_PROXY_SESSION.cookies = http.cookiejar.LWPCookieJar(str(LEAKER_PROXY_COOKIE_PATH))
try:
    if LEAKER_PROXY_COOKIE_PATH.is_file():
        LEAKER_PROXY_SESSION.cookies.load(ignore_discard=True, ignore_expires=True)
except Exception:
    pass

LEAKER_COOKIE_CONSENT_MAX_AGE_SECONDS = 60 * 60 * 24 * 365 * 5
LEAKER_COOKIE_CONSENT_COOKIES = {
    "cookieConsent": "accepted",
    "cookiesAccepted": "true",
    "cookie_consent": "accepted",
    "cookie_consent_accepted": "true",
    "CookieConsent": "true",
    "cc_cookie": urllib.parse.quote(
        json.dumps(
            {
                "categories": ["necessary", "analytics", "marketing"],
                "level": ["necessary", "analytics", "marketing"],
                "revision": 0,
                "data": None,
            },
            separators=(",", ":"),
        ),
        safe="",
    ),
}


def ensure_leaker_cookie_consent(*, save: bool = True) -> int:
    now = int(time.time())
    expires = now + LEAKER_COOKIE_CONSENT_MAX_AGE_SECONDS
    synced = 0
    with LEAKER_PROXY_LOCK:
        for name, value in LEAKER_COOKIE_CONSENT_COOKIES.items():
            existing = None
            for cookie in LEAKER_PROXY_SESSION.cookies:
                if cookie.name == name and str(cookie.domain or "").lstrip(".") == "6ureleaks.com":
                    existing = cookie
                    break
            if existing and existing.value == value and int(existing.expires or 0) > now + 60 * 60 * 24 * 30:
                continue
            LEAKER_PROXY_SESSION.cookies.set_cookie(
                requests.cookies.create_cookie(
                    name=name,
                    value=value,
                    domain=".6ureleaks.com",
                    path="/",
                    secure=True,
                    expires=expires,
                )
            )
            synced += 1
        if synced and save:
            try:
                LEAKER_PROXY_SESSION.cookies.save(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
    return synced


def leaker_cookie_consent_response_headers() -> list[str]:
    return [
        f"{name}={value}; Path=/; Max-Age={LEAKER_COOKIE_CONSENT_MAX_AGE_SECONDS}; SameSite=Lax"
        for name, value in LEAKER_COOKIE_CONSENT_COOKIES.items()
    ]


ensure_leaker_cookie_consent(save=True)
FILES_STATE_STRING_KEYS = {
    "username",
    "password",
    "lastEditor",
    "lastFolderPath",
    "lastFolderName",
}
FILES_STATE_LIST_KEYS = {
    "lastFolderPaths",
    "lastFolderNames",
}
FORM_TOKEN_RE = re.compile(r'name="_form_token"\s+value="([^"]+)"')
CSRF_TOKEN_RE = re.compile(r"'X-CSRF-TOKEN': '([^']+)'")

legacy_root_raw = str(os.environ.get("REYLI_LEGACY_DATA_DIR", "") or "").strip()
LEGACY_DATA_ROOT = Path(legacy_root_raw).expanduser().resolve() if legacy_root_raw else None
if LEGACY_DATA_ROOT == DATA_ROOT:
    LEGACY_DATA_ROOT = None
LEGACY_CONFIG_PATH = LEGACY_DATA_ROOT / CONFIG_FILE_NAME if LEGACY_DATA_ROOT else None
LEGACY_CONFIG_BACKUP_PATH = LEGACY_DATA_ROOT / CONFIG_BACKUP_FILE_NAME if LEGACY_DATA_ROOT else None


def json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def read_state_file(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


DEFAULT_APP_SETTINGS = {
    "encryptedVault": True,
    "silentRepairMode": True,
}
APP_SETTINGS_LOCK = threading.RLock()
VAULT_LOCK = threading.RLock()


def bool_setting(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def load_app_settings() -> dict:
    payload = read_state_file(APP_SETTINGS_PATH)
    settings = dict(DEFAULT_APP_SETTINGS)
    if isinstance(payload, dict):
        for key, default in DEFAULT_APP_SETTINGS.items():
            if key in payload:
                settings[key] = bool_setting(payload.get(key), default)
        for key in ("lastRepairAt", "lastRepairActions", "lastRepairSource"):
            if key in payload:
                settings[key] = payload[key]
    return settings


def save_app_settings(settings: dict) -> dict:
    clean = dict(DEFAULT_APP_SETTINGS)
    if isinstance(settings, dict):
        for key, default in DEFAULT_APP_SETTINGS.items():
            if key in settings:
                clean[key] = bool_setting(settings.get(key), default)
        for key in ("lastRepairAt", "lastRepairActions", "lastRepairSource"):
            if key in settings:
                clean[key] = settings[key]
    with APP_SETTINGS_LOCK:
        APP_SETTINGS_TMP_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(APP_SETTINGS_TMP_PATH, APP_SETTINGS_PATH)
    return clean


def get_app_setting(key: str) -> bool:
    settings = load_app_settings()
    default = bool(DEFAULT_APP_SETTINGS.get(key, False))
    return bool_setting(settings.get(key), default)


def secure_file_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def windows_dpapi_transform(data: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI is only available on Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_bool
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_bool
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    input_buffer = ctypes.create_string_buffer(data)
    input_blob = DATA_BLOB(len(data), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_char)))
    output_blob = DATA_BLOB()
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "6ure App Vault",
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))


def load_or_create_vault_key(*, create: bool = True) -> bytes | None:
    with VAULT_LOCK:
        payload = read_state_file(VAULT_KEY_PATH)
        if isinstance(payload, dict):
            method = str(payload.get("method") or "").strip().lower()
            encoded_key = str(payload.get("key") or "").strip()
            if encoded_key:
                raw_key = base64.b64decode(encoded_key.encode("ascii")) if method == "dpapi-fernet" else encoded_key.encode("ascii")
                if method == "dpapi-fernet":
                    return windows_dpapi_transform(raw_key, protect=False)
                if method == "local-fernet":
                    return raw_key
        if not create:
            return None

        key = Fernet.generate_key()
        if os.name == "nt":
            try:
                protected_key = windows_dpapi_transform(key, protect=True)
                payload = {
                    "version": 1,
                    "method": "dpapi-fernet",
                    "key": base64.b64encode(protected_key).decode("ascii"),
                    "createdAt": int(time.time() * 1000),
                }
            except Exception:
                payload = {
                    "version": 1,
                    "method": "local-fernet",
                    "key": key.decode("ascii"),
                    "createdAt": int(time.time() * 1000),
                }
        else:
            payload = {
                "version": 1,
                "method": "local-fernet",
                "key": key.decode("ascii"),
                "createdAt": int(time.time() * 1000),
            }
        VAULT_KEY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        secure_file_permissions(VAULT_KEY_PATH)
        return key


def vault_fernet(*, create: bool = True) -> Fernet | None:
    key = load_or_create_vault_key(create=create)
    return Fernet(key) if key else None


def read_vault_payload() -> dict:
    with VAULT_LOCK:
        payload = read_state_file(VAULT_PATH)
        if not isinstance(payload, dict):
            return {}
        token = str(payload.get("token") or "").strip()
        if not token:
            return {}
        fernet = vault_fernet(create=False)
        if fernet is None:
            return {}
        try:
            raw = fernet.decrypt(token.encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
        except (InvalidToken, ValueError, OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}


def write_vault_payload(payload: dict) -> None:
    with VAULT_LOCK:
        fernet = vault_fernet(create=True)
        if fernet is None:
            raise FilesAutomationError("Encrypted vault key could not be created.")
        clean_payload = dict(payload) if isinstance(payload, dict) else {}
        clean_payload["version"] = 1
        clean_payload["updatedAt"] = int(time.time() * 1000)
        token = fernet.encrypt(json.dumps(clean_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        VAULT_PATH.write_text(
            json.dumps({"version": 1, "cipher": "fernet", "token": token.decode("ascii")}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        secure_file_permissions(VAULT_PATH)


def save_vault_credentials(username: str, password: str) -> None:
    clean_username = str(username or "").strip()
    clean_password = str(password or "")
    if not clean_username or not clean_password:
        raise FilesAutomationError("Vault credentials are incomplete.")
    payload = read_vault_payload()
    payload["credentials"] = {
        "username": clean_username,
        "password": clean_password,
        "updatedAt": int(time.time() * 1000),
    }
    write_vault_payload(payload)


def load_vault_credentials() -> tuple[str, str]:
    payload = read_vault_payload()
    credentials = payload.get("credentials") if isinstance(payload, dict) else None
    if not isinstance(credentials, dict):
        return "", ""
    username = str(credentials.get("username") or "").strip()
    password = str(credentials.get("password") or "")
    return (username, password) if username and password else ("", "")


def clear_vault_credentials() -> None:
    payload = read_vault_payload()
    if isinstance(payload, dict) and payload:
        payload.pop("credentials", None)
        write_vault_payload(payload)


def vault_status() -> dict:
    method = ""
    key_payload = read_state_file(VAULT_KEY_PATH)
    if isinstance(key_payload, dict):
        method = str(key_payload.get("method") or "")
    username, password = load_vault_credentials()
    return {
        "enabled": get_app_setting("encryptedVault"),
        "available": VAULT_PATH.exists(),
        "hasCredentials": bool(username and password),
        "username": username,
        "method": method or ("dpapi-fernet" if os.name == "nt" else "local-fernet"),
        "path": str(VAULT_PATH),
    }


def normalize_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    clean_items: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        clean_items.append(text)
    return clean_items


def sanitize_upload_history(entries) -> list[dict]:
    if not isinstance(entries, list):
        return []

    clean_entries: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        editor_name = str(entry.get("editorName", "") or "").strip()
        folder_path = str(entry.get("folderPath", "") or "").strip()
        folder_name = str(entry.get("folderName", "") or "").strip()
        if not editor_name or not folder_path or not folder_name:
            continue

        clean_entry = {
            "editorName": editor_name,
            "folderPath": folder_path,
            "folderName": folder_name,
        }
        saved_at = entry.get("savedAt")
        if isinstance(saved_at, int):
            clean_entry["savedAt"] = saved_at
        clean_entries.append(clean_entry)
        if len(clean_entries) >= FILES_UPLOAD_HISTORY_LIMIT:
            break

    return clean_entries


def sanitize_files_state(raw_files) -> dict:
    clean_files: dict = {}
    if not isinstance(raw_files, dict):
        return clean_files

    for key in FILES_STATE_STRING_KEYS:
        value = raw_files.get(key)
        if isinstance(value, str) and value.strip():
            clean_files[key] = value.strip()

    for key in FILES_STATE_LIST_KEYS:
        items = normalize_string_list(raw_files.get(key))
        if items:
            clean_files[key] = items

    if "lastFolderPaths" not in clean_files and clean_files.get("lastFolderPath"):
        clean_files["lastFolderPaths"] = [clean_files["lastFolderPath"]]
    if "lastFolderNames" not in clean_files and clean_files.get("lastFolderName"):
        clean_files["lastFolderNames"] = [clean_files["lastFolderName"]]

    history = sanitize_upload_history(raw_files.get("recentUploads"))
    if history:
        clean_files["recentUploads"] = history

    return clean_files


def sanitize_persisted_state(payload: dict | None) -> dict:
    raw = payload if isinstance(payload, dict) else {}
    clean = {"files": sanitize_files_state(raw.get("files"))}
    saved_at = raw.get("_savedAt")
    if isinstance(saved_at, int):
        clean["_savedAt"] = saved_at
    return clean


def save_persisted_state(payload: dict) -> dict:
    clean = sanitize_persisted_state(payload)
    clean["_savedAt"] = int(time.time() * 1000)
    text = json.dumps(clean, ensure_ascii=False, indent=2)
    CONFIG_TMP_PATH.write_text(text, encoding="utf-8")
    os.replace(CONFIG_TMP_PATH, CONFIG_PATH)
    CONFIG_BACKUP_PATH.write_text(text, encoding="utf-8")
    return clean


def migrate_legacy_state_if_needed() -> dict | None:
    if CONFIG_PATH.exists() or CONFIG_BACKUP_PATH.exists():
        return None

    for legacy_path in (LEGACY_CONFIG_PATH, LEGACY_CONFIG_BACKUP_PATH):
        legacy_state = read_state_file(legacy_path)
        if legacy_state is None:
            continue
        return save_persisted_state(legacy_state)

    return None


def load_persisted_state() -> dict:
    current = read_state_file(CONFIG_PATH)
    if current is not None:
        return sanitize_persisted_state(current)

    backup = read_state_file(CONFIG_BACKUP_PATH)
    if backup is not None:
        return sanitize_persisted_state(backup)

    migrated = migrate_legacy_state_if_needed()
    if migrated is not None:
        return migrated

    return {"files": {}}


def get_files_state() -> dict:
    files_state = load_persisted_state().get("files", {})
    return dict(files_state) if isinstance(files_state, dict) else {}


def save_files_state(**values) -> dict:
    state = load_persisted_state()
    files_state = state.setdefault("files", {})
    pending_username = str(values.get("username") or files_state.get("username") or "").strip()
    pending_password = str(values.get("password") or "")
    if pending_password and get_app_setting("encryptedVault"):
        save_vault_credentials(pending_username, pending_password)
        values = dict(values)
        values.pop("password", None)
        files_state.pop("password", None)
    for key, value in values.items():
        if key in FILES_STATE_STRING_KEYS:
            text = str(value or "").strip()
            if text:
                files_state[key] = text
            else:
                files_state.pop(key, None)
            continue

        if key in FILES_STATE_LIST_KEYS:
            items = normalize_string_list(value)
            if items:
                files_state[key] = items
            else:
                files_state.pop(key, None)
    return save_persisted_state(state)


def merge_recent_upload_entries(files_state: dict, entries: list[dict]) -> None:
    current_history = sanitize_upload_history(files_state.get("recentUploads"))
    entry_keys = {
        (entry["editorName"], entry["folderPath"], entry["folderName"])
        for entry in entries
    }
    deduped = [
        item
        for item in current_history
        if (item.get("editorName"), item.get("folderPath"), item.get("folderName")) not in entry_keys
    ]
    files_state["recentUploads"] = [*entries, *deduped][:FILES_UPLOAD_HISTORY_LIMIT]


def record_upload_history(editor_name: str, folder_path: str, folder_name: str) -> dict:
    return record_upload_batch_history(editor_name, [Path(folder_path).expanduser().resolve()])


def record_upload_batch_history(editor_name: str, folder_paths: list[Path]) -> dict:
    state = load_persisted_state()
    files_state = state.setdefault("files", {})
    normalized_editor = str(editor_name or "").strip()
    if not normalized_editor:
        return save_persisted_state(state)

    entries: list[dict] = []
    saved_at = int(time.time() * 1000)
    for folder_path in folder_paths:
        path = Path(folder_path).expanduser().resolve()
        folder_name = path.name.strip()
        folder_text = str(path).strip()
        if not folder_name or not folder_text:
            continue
        entries.append(
            {
                "editorName": normalized_editor,
                "folderPath": folder_text,
                "folderName": folder_name,
                "savedAt": saved_at,
            }
        )

    if not entries:
        return save_persisted_state(state)

    files_state["lastEditor"] = normalized_editor
    files_state["lastFolderPath"] = entries[0]["folderPath"]
    files_state["lastFolderName"] = entries[0]["folderName"]
    files_state["lastFolderPaths"] = [entry["folderPath"] for entry in entries]
    files_state["lastFolderNames"] = [entry["folderName"] for entry in entries]
    merge_recent_upload_entries(files_state, entries)
    return save_persisted_state(state)


def clear_persisted_account_data() -> dict:
    clear_vault_credentials()
    return save_persisted_state({"files": {}})


def clear_last_files_selection() -> dict:
    state = load_persisted_state()
    files_state = state.setdefault("files", {})
    for key in (
        "lastEditor",
        "lastFolderPath",
        "lastFolderName",
        "lastFolderPaths",
        "lastFolderNames",
    ):
        files_state.pop(key, None)
    return save_persisted_state(state)


def sync_session_from_state(state: dict | None = None) -> dict:
    current_state = state if isinstance(state, dict) else load_persisted_state()
    files_state = current_state.get("files", {}) if isinstance(current_state, dict) else {}
    username = str(files_state.get("username", "") or "").strip() if isinstance(files_state, dict) else ""
    password = str(files_state.get("password", "") or "") if isinstance(files_state, dict) else ""
    if get_app_setting("encryptedVault"):
        vault_username, vault_password = load_vault_credentials()
        if vault_username and vault_password:
            username = vault_username
            password = vault_password
    authenticated = bool(username and password)
    with AUTH_LOCK:
        previous = (
            bool(AUTH_STATE["authenticated"]),
            str(AUTH_STATE["username"]),
            str(AUTH_STATE["password"]),
        )
        AUTH_STATE["authenticated"] = authenticated
        AUTH_STATE["username"] = username if authenticated else ""
        AUTH_STATE["password"] = password if authenticated else ""
    if previous != (authenticated, username if authenticated else "", password if authenticated else ""):
        clear_remote_client_cache()
    return {"authenticated": authenticated, "username": username if authenticated else ""}


def set_session_credentials(username: str, password: str) -> None:
    clean_username = str(username or "").strip()
    clean_password = str(password or "")
    with AUTH_LOCK:
        previous = (
            bool(AUTH_STATE["authenticated"]),
            str(AUTH_STATE["username"]),
            str(AUTH_STATE["password"]),
        )
        AUTH_STATE["authenticated"] = True
        AUTH_STATE["username"] = clean_username
        AUTH_STATE["password"] = clean_password
    if previous != (True, clean_username, clean_password):
        clear_remote_client_cache()


def clear_session_credentials() -> None:
    with AUTH_LOCK:
        previous = bool(AUTH_STATE["authenticated"]) or bool(AUTH_STATE["username"]) or bool(AUTH_STATE["password"])
        AUTH_STATE["authenticated"] = False
        AUTH_STATE["username"] = ""
        AUTH_STATE["password"] = ""
    if previous:
        clear_remote_client_cache()


def get_session_snapshot() -> dict:
    with AUTH_LOCK:
        return {
            "authenticated": bool(AUTH_STATE["authenticated"]),
            "username": str(AUTH_STATE["username"]),
        }


def get_session_credentials() -> tuple[str, str]:
    with AUTH_LOCK:
        if not AUTH_STATE["authenticated"]:
            return "", ""
        return str(AUTH_STATE["username"]), str(AUTH_STATE["password"])


def clear_remote_client_cache() -> None:
    with REMOTE_CLIENT_LOCK:
        client = REMOTE_CLIENT_CACHE.get("client")
        session = getattr(client, "session", None)
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        REMOTE_CLIENT_CACHE["username"] = ""
        REMOTE_CLIENT_CACHE["password"] = ""
        REMOTE_CLIENT_CACHE["client"] = None
        REMOTE_CLIENT_CACHE["expiresAt"] = 0.0


def quote_remote_path(path: str) -> str:
    return urllib.parse.quote(path, safe="")


def normalize_remote_name(value: str, label: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    if any(part in cleaned for part in ("/", "\\", "\x00")) or cleaned in {".", ".."}:
        raise ValueError(f"{label} contains invalid characters.")
    return cleaned


def normalize_remote_path(value: str, label: str = "Cloud path", allow_root: bool = True) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if "\x00" in text:
        raise ValueError(f"{label} contains invalid characters.")
    if not text:
        if allow_root:
            return "/"
        raise ValueError(f"{label} is required.")
    if not text.startswith("/"):
        text = "/" + text
    cleaned = posixpath.normpath(text)
    if cleaned in {"", "."}:
        cleaned = "/"
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    if cleaned != "/":
        cleaned = cleaned.rstrip("/")
    if cleaned == "/" and not allow_root:
        raise ValueError(f"{label} cannot be the cloud root.")
    return cleaned


def remote_basename(remote_path: str) -> str:
    return posixpath.basename(normalize_remote_path(remote_path, allow_root=False))


def remote_parent_path(remote_path: str) -> str:
    parent = posixpath.dirname(normalize_remote_path(remote_path, allow_root=False))
    return parent if parent else "/"


def remote_join(parent: str, *parts: str) -> str:
    clean_parent = normalize_remote_path(parent)
    joined = clean_parent
    for part in parts:
        text = str(part or "").strip().replace("\\", "/").strip("/")
        if not text:
            continue
        joined = posixpath.join(joined, text)
    return normalize_remote_path(joined)


def is_remote_dir_type(value) -> bool:
    return str(value or "").strip().lower() in {"1", "dir", "folder", "directory"}


def remote_breadcrumbs(remote_path: str) -> list[dict]:
    clean_path = normalize_remote_path(remote_path)
    crumbs = [{"name": "Cloud", "path": "/"}]
    if clean_path == "/":
        return crumbs

    current = ""
    for part in [item for item in clean_path.split("/") if item]:
        current = remote_join(current or "/", part)
        crumbs.append({"name": part, "path": current})
    return crumbs


def normalize_cloud_entry(base_path: str, entry: dict) -> dict:
    name = str(entry.get("name", "") or "").strip()
    entry_type = str(entry.get("type", "") or "").strip()
    is_dir = is_remote_dir_type(entry_type)
    size_value = entry.get("size")
    try:
        size_bytes = int(size_value)
    except (TypeError, ValueError):
        size_bytes = None
    modified_value = entry.get("last_modified")
    try:
        last_modified = int(modified_value)
    except (TypeError, ValueError):
        last_modified = 0

    return {
        "name": name,
        "path": remote_join(base_path, name),
        "type": "folder" if is_dir else "file",
        "sizeBytes": None if is_dir else size_bytes,
        "lastModified": last_modified,
        "isZip": (not is_dir) and name.lower().endswith(".zip"),
    }


def sort_cloud_entries(entries: list[dict]) -> list[dict]:
    return sorted(
        entries,
        key=lambda item: (0 if item.get("type") == "folder" else 1, str(item.get("name", "")).lower()),
    )


def get_network_status(timeout: float = 1.4) -> dict:
    errors: list[str] = []
    started_at = time.time()
    for host, port in NETWORK_CHECK_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return {
                    "online": True,
                    "host": host,
                    "latencyMs": max(0, round((time.time() - started_at) * 1000)),
                }
        except OSError as error:
            errors.append(f"{host}:{port} {error}")
    return {
        "online": False,
        "host": "",
        "latencyMs": max(0, round((time.time() - started_at) * 1000)),
        "errors": errors[-3:],
    }


def clean_discord_display_name(value) -> str:
    text = html.unescape(str(value or "")).replace("\x00", "").strip()
    text = re.sub(r"\s+", " ", text)
    if text.startswith("@"):
        text = text[1:].strip()
    if not text or len(text) > 80:
        return ""
    return text


def clean_discord_id(value) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{6,24}", text):
        return text
    return ""


def normalize_discord_avatar_url(value, discord_id: str = "") -> str:
    text = html.unescape(str(value or "").strip()).replace("\\/", "/")
    text = re.sub(r"\\u0026", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"\\u003d", "=", text, flags=re.IGNORECASE)
    text = re.sub(r"\\u003f", "?", text, flags=re.IGNORECASE)
    if not text:
        return ""
    if text.startswith("//"):
        text = f"https:{text}"
    if text.startswith(("cdn.discordapp.com/", "media.discordapp.net/")):
        text = f"https://{text}"
    if text.startswith("/_next/image"):
        try:
            parsed = urllib.parse.urlsplit(text)
            nested_url = (urllib.parse.parse_qs(parsed.query or "").get("url") or [""])[0]
            nested = normalize_discord_avatar_url(nested_url, discord_id)
            if nested:
                return nested
        except Exception:
            pass
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if text.startswith("/"):
        return make_6ure_absolute_url(text)
    if discord_id and re.fullmatch(r"[A-Za-z0-9_]{8,}", text):
        extension = "gif" if text.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{discord_id}/{text}.{extension}"
    return ""


def normalize_app_auth_user(record, *, source: str = "") -> dict | None:
    if not isinstance(record, dict):
        return None

    id_keys = (
        "discordId",
        "discord_id",
        "discordMemberId",
        "discord_member_id",
        "userId",
        "user_id",
        "sub",
        "id",
    )
    username_keys = (
        "username",
        "tag",
    )
    display_name_keys = (
        "global_name",
        "globalName",
        "displayName",
        "display_name",
        "discord_member_name",
        "name",
    )
    avatar_keys = (
        "avatarUrl",
        "avatar_url",
        "image",
        "picture",
        "discord_member_avatar",
        "avatar",
    )

    discord_id = ""
    for key in id_keys:
        value = record.get(key)
        discord_id = clean_discord_id(value)
        if discord_id:
            break

    username = ""
    for key in username_keys:
        value = record.get(key)
        username = clean_discord_display_name(value)
        if username and username.lower() not in {"discord", "sign in", "login", "user"}:
            break
        username = ""

    display_name = ""
    for key in display_name_keys:
        value = record.get(key)
        display_name = clean_discord_display_name(value)
        if display_name and display_name.lower() not in {"discord", "sign in", "login", "user"}:
            break
        display_name = ""

    avatar_url = ""
    for key in avatar_keys:
        avatar_url = normalize_discord_avatar_url(record.get(key), discord_id)
        if avatar_url:
            break

    if not discord_id and not username and not display_name:
        return None

    display_name = display_name or username or discord_id
    return {
        "id": discord_id,
        "username": username,
        "displayName": display_name,
        "avatarUrl": avatar_url,
        "source": source,
    }


def score_app_auth_user(user: dict | None) -> int:
    if not user:
        return 0
    score = 0
    if user.get("id"):
        score += 5
    if user.get("displayName"):
        score += 5
    if user.get("username"):
        score += 3
    if user.get("avatarUrl"):
        score += 1
    return score


def extract_app_auth_user_from_json(data, *, source: str = "") -> dict | None:
    best: dict | None = None
    best_score = 0
    seen: set[int] = set()

    def walk(node, depth: int = 0) -> None:
        nonlocal best, best_score
        if depth > 8:
            return
        marker = id(node)
        if marker in seen:
            return
        seen.add(marker)

        if isinstance(node, dict):
            candidate = normalize_app_auth_user(node, source=source)
            candidate_score = score_app_auth_user(candidate)
            if candidate_score > best_score:
                best = candidate
                best_score = candidate_score
            for key in ("user", "account", "profile", "session", "member", "discord", "data"):
                value = node.get(key)
                if isinstance(value, (dict, list)):
                    walk(value, depth + 1)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    walk(value, depth + 1)

    walk(data)
    return best


def extract_app_auth_user_from_text(text: str, *, source: str = "") -> dict | None:
    if not text:
        return None

    next_data_match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(?P<data>.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if next_data_match:
        try:
            data = json.loads(html.unescape(next_data_match.group("data")))
            user = extract_app_auth_user_from_json(data, source=source)
            if user:
                return user
        except Exception:
            pass

    id_match = re.search(
        r'"(?:discordId|discord_id|discordMemberId|discord_member_id|userId|user_id|sub|id)"\s*:\s*"?(?P<id>\d{6,24})"?',
        text,
        flags=re.IGNORECASE,
    )
    display_name_match = re.search(
        r'"(?:global_name|globalName|displayName|display_name|discord_member_name|name)"\s*:\s*"(?P<name>[^"\\]{1,80})"',
        text,
        flags=re.IGNORECASE,
    )
    username_match = re.search(
        r'"(?:username|tag)"\s*:\s*"(?P<name>[^"\\]{1,80})"',
        text,
        flags=re.IGNORECASE,
    )
    avatar_match = re.search(
        r'"(?:avatarUrl|avatar_url|image|picture|discord_member_avatar|avatar)"\s*:\s*"(?P<avatar>https?:\\?/\\?/[^"\\]+|/[^"\\]+|[A-Za-z0-9_]{8,})"',
        text,
        flags=re.IGNORECASE,
    )
    if not avatar_match:
        avatar_match = re.search(
            r'(?P<avatar>https?://cdn\.discordapp\.com/avatars/\d{6,24}/[^"\'<>\s]+)',
            text,
            flags=re.IGNORECASE,
        )
    if not id_match and not display_name_match and not username_match and not avatar_match:
        return None

    avatar_value = html.unescape(avatar_match.group("avatar")).replace("\\/", "/") if avatar_match else ""
    avatar_id_match = re.search(r"/avatars/(?P<id>\d{6,24})/", avatar_value)
    record = {
        "id": id_match.group("id") if id_match else (avatar_id_match.group("id") if avatar_id_match else ""),
        "username": username_match.group("name") if username_match else "",
        "displayName": display_name_match.group("name") if display_name_match else "",
        "avatar": avatar_value,
    }
    return normalize_app_auth_user(record, source=source)


def set_app_auth_user(user: dict | None) -> dict:
    now = time.time()
    with APP_AUTH_LOCK:
        APP_AUTH_STATE["authenticated"] = bool(user)
        APP_AUTH_STATE["user"] = dict(user) if user else None
        APP_AUTH_STATE["checkedAt"] = now
        APP_AUTH_STATE["updatedAt"] = now
        APP_AUTH_STATE["lastError"] = ""
        return get_app_auth_snapshot()


def mark_app_auth_checked(*, error: str = "") -> dict:
    with APP_AUTH_LOCK:
        APP_AUTH_STATE["checkedAt"] = time.time()
        APP_AUTH_STATE["lastError"] = str(error or "")
        return get_app_auth_snapshot()


def clear_app_auth_state(*, clear_cookies: bool = False) -> dict:
    with APP_AUTH_LOCK:
        APP_AUTH_STATE["authenticated"] = False
        APP_AUTH_STATE["user"] = None
        APP_AUTH_STATE["checkedAt"] = time.time()
        APP_AUTH_STATE["updatedAt"] = time.time()
        APP_AUTH_STATE["lastError"] = ""
    if clear_cookies:
        with LEAKER_PROXY_LOCK:
            LEAKER_PROXY_SESSION.cookies.clear()
            ensure_leaker_cookie_consent(save=False)
            try:
                LEAKER_PROXY_SESSION.cookies.save(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
    return get_app_auth_snapshot()


def get_app_auth_snapshot() -> dict:
    with APP_AUTH_LOCK:
        user = APP_AUTH_STATE.get("user")
        return {
            "authenticated": bool(APP_AUTH_STATE.get("authenticated") and user),
            "user": dict(user) if isinstance(user, dict) else None,
            "checkedAt": int(float(APP_AUTH_STATE.get("checkedAt") or 0) * 1000),
            "updatedAt": int(float(APP_AUTH_STATE.get("updatedAt") or 0) * 1000),
            "lastError": str(APP_AUTH_STATE.get("lastError") or ""),
        }


def app_auth_cache_is_fresh(snapshot: dict) -> bool:
    checked_at = float(snapshot.get("checkedAt") or 0) / 1000
    if checked_at <= 0:
        return False
    age = time.time() - checked_at
    if snapshot.get("authenticated"):
        return age < APP_AUTH_PROFILE_CACHE_SECONDS
    return age < APP_AUTH_NEGATIVE_CACHE_SECONDS


def fetch_app_auth_user_from_leaker_session() -> dict | None:
    ensure_leaker_cookie_consent(save=False)
    endpoints = (
        ("/api/auth/session", "json"),
        ("/requests/account", "html"),
        ("/dashboard", "html"),
        ("/dashboard/upload", "html"),
    )
    headers = {
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Referer": LEAKER_SITE_BASE_URL,
        "User-Agent": LEAKER_PROXY_USER_AGENT,
    }

    last_error = ""
    for path, expected in endpoints:
        url = f"{LEAKER_SITE_BASE_URL}{path}"
        try:
            with LEAKER_PROXY_LOCK:
                response = LEAKER_PROXY_SESSION.get(
                    url,
                    headers=headers,
                    allow_redirects=True,
                    timeout=16,
                )
                try:
                    LEAKER_PROXY_SESSION.cookies.save(ignore_discard=True, ignore_expires=True)
                except Exception:
                    pass
            if response.status_code == 401:
                continue
            if response.status_code >= 400:
                last_error = f"{path} returned HTTP {response.status_code}"
                continue
            user = None
            content_type = response.headers.get("Content-Type", "")
            if expected == "json" or "application/json" in content_type:
                try:
                    data = response.json()
                    if data:
                        user = extract_app_auth_user_from_json(data, source=path)
                except ValueError:
                    user = extract_app_auth_user_from_text(response.text, source=path)
            else:
                user = extract_app_auth_user_from_text(response.text, source=path)
            if user:
                return user
        except Exception as error:
            last_error = str(error)

    if last_error:
        mark_app_auth_checked(error=last_error)
    return None


def get_app_auth_status(*, refresh: bool = False) -> dict:
    snapshot = get_app_auth_snapshot()
    if not refresh and app_auth_cache_is_fresh(snapshot):
        snapshot["success"] = True
        return snapshot

    user = fetch_app_auth_user_from_leaker_session()
    if user:
        snapshot = set_app_auth_user(user)
    else:
        snapshot = clear_app_auth_state(clear_cookies=False)
    snapshot["success"] = True
    return snapshot


def resource_uploader_aliases_from_user(user: dict | None) -> tuple[str, ...]:
    if not isinstance(user, dict):
        return MY_RESOURCES_UPLOADER_ALIASES
    aliases = []
    for value in (user.get("username"), user.get("displayName")):
        alias = normalize_resource_uploader_name(value or "")
        if alias and alias not in aliases:
            aliases.append(alias)
    return tuple(aliases) or MY_RESOURCES_UPLOADER_ALIASES


def current_resources_uploader() -> dict:
    snapshot = get_app_auth_snapshot()
    user = snapshot.get("user") if snapshot.get("authenticated") else None
    if isinstance(user, dict) and (user.get("id") or user.get("username") or user.get("displayName")):
        aliases = resource_uploader_aliases_from_user(user)
        display_name = user.get("displayName") or user.get("username") or "username"
        clean_display_name = clean_discord_display_name(display_name) or "username"
        return {
            "id": clean_discord_id(user.get("id")) or MY_RESOURCES_UPLOADER_ID,
            "aliases": aliases,
            "displayName": clean_display_name,
        }
    return {
        "id": MY_RESOURCES_UPLOADER_ID,
        "aliases": MY_RESOURCES_UPLOADER_ALIASES,
        "displayName": "reyli",
    }


def make_6ure_absolute_url(value: str) -> str:
    clean_value = str(value or "").strip()
    if not clean_value:
        return ""
    try:
        parsed = urllib.parse.urlsplit(clean_value)
    except ValueError:
        return clean_value
    if parsed.scheme in {"http", "https"}:
        return clean_value
    if clean_value.startswith("//"):
        return f"https:{clean_value}"
    if clean_value.startswith("/"):
        return f"{LEAKER_SITE_BASE_URL}{clean_value}"
    return clean_value


def safe_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_resource_uploader_name(value: str) -> str:
    return str(value or "").strip().casefold().lstrip("@")


def resource_matches_uploader(item: dict, uploader_id: str, uploader_aliases: tuple[str, ...]) -> bool:
    member_id = str(item.get("discord_member_id") or "").strip()
    if uploader_id and member_id == uploader_id:
        return True

    member_name = normalize_resource_uploader_name(item.get("discord_member_name") or "")
    return bool(member_name and member_name in uploader_aliases)


def resource_matches_my_uploader(item: dict) -> bool:
    uploader = current_resources_uploader()
    return resource_matches_uploader(
        item,
        str(uploader.get("id") or ""),
        tuple(uploader.get("aliases") or ()),
    )


def sanitize_resource_description(value: str, limit: int = 220) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def sanitize_resource_detail_text(value: str, limit: int = 5000) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def sanitize_resource_tags(value) -> list[str]:
    if isinstance(value, list):
        source = value
    elif isinstance(value, str):
        source = re.split(r"[,#]", value)
    else:
        source = []

    tags: list[str] = []
    seen: set[str] = set()
    for item in source:
        tag = str(item or "").strip().lstrip("#")
        key = tag.casefold()
        if not tag or key in seen:
            continue
        seen.add(key)
        tags.append(tag)
    return tags[:16]


def sanitize_my_resource_item(item: dict) -> dict:
    resource_id = safe_int(item.get("id"))
    leaked_at = str(item.get("leaked_at") or "").strip()
    return {
        "id": resource_id,
        "name": str(item.get("name") or "Untitled resource").strip(),
        "editorName": str(item.get("editor_name") or "Unknown").strip(),
        "filePath": str(item.get("file_path") or "").strip(),
        "thumbnailUrl": make_6ure_absolute_url(item.get("thumbnail_url") or ""),
        "placeUrl": make_6ure_absolute_url(item.get("place_url") or ""),
        "url": f"{RESOURCES_URL}/{resource_id}" if resource_id else RESOURCES_URL,
        "category": str(item.get("category") or "Uncategorized").strip(),
        "downloadCount": safe_int(item.get("download_count")),
        "viewCount": safe_int(item.get("view_count")),
        "commentsCount": safe_int(item.get("comments_count")),
        "isPremium": bool(safe_int(item.get("is_premium"))),
        "isProtected": bool(safe_int(item.get("is_protected"))),
        "status": str(item.get("status") or "").strip(),
        "price": str(item.get("price") or "").strip(),
        "priceNumeric": safe_float(item.get("price_numeric")),
        "fileSizeBytes": safe_int(item.get("file_size_bytes")),
        "description": "" if safe_int(item.get("hide_description")) else sanitize_resource_description(item.get("description") or ""),
        "editorSocialUrl": make_6ure_absolute_url(item.get("editor_social_url") or ""),
        "editorAvatarUrl": make_6ure_absolute_url(item.get("editor_avatar_url") or ""),
        "uploaderName": str(item.get("discord_member_name") or "").strip(),
        "uploaderId": str(item.get("discord_member_id") or "").strip(),
        "uploaderAvatarUrl": make_6ure_absolute_url(item.get("discord_member_avatar") or ""),
        "leakedAt": leaked_at,
    }


def sanitize_resource_detail_item(item: dict) -> dict:
    clean_item = sanitize_my_resource_item(item)
    resource_id = safe_int(clean_item.get("id"))
    hide_description = safe_int(item.get("hide_description"))
    clean_item.update(
        {
            "apiUrl": f"{RESOURCES_API_URL}/{resource_id}" if resource_id else RESOURCES_API_URL,
            "editorId": safe_int(item.get("editor_id")),
            "tags": sanitize_resource_tags(item.get("tags")),
            "description": "" if hide_description else sanitize_resource_detail_text(item.get("description") or ""),
            "hideDescription": bool(hide_description),
            "isFeatured": bool(safe_int(item.get("is_featured"))),
            "hidden": bool(safe_int(item.get("hidden"))),
            "countsForPayout": bool(safe_int(item.get("counts_for_payout"))),
            "editorTotalDownloads": safe_int(item.get("editor_total_downloads")),
            "editorResourceCount": safe_int(item.get("editor_resource_count")),
            "createdAt": str(item.get("created_at") or "").strip(),
            "updatedAt": str(item.get("updated_at") or "").strip(),
        }
    )
    return clean_item


def sanitize_related_resource_item(item: dict) -> dict:
    clean_item = sanitize_my_resource_item(item)
    resource_id = safe_int(clean_item.get("id"))
    clean_item["apiUrl"] = f"{RESOURCES_API_URL}/{resource_id}" if resource_id else RESOURCES_API_URL
    clean_item["tags"] = sanitize_resource_tags(item.get("tags"))
    return clean_item


def fetch_resources_page(page: int, *, skip_metadata: bool = True) -> dict:
    params = {
        "page": max(1, int(page or 1)),
        "limit": MY_RESOURCES_PAGE_LIMIT,
        "sort": "recent",
        "order": "desc",
    }
    if skip_metadata:
        params["skipMetadata"] = "1"

    response = requests.get(
        RESOURCES_API_URL,
        params=params,
        headers={
            "Accept": "application/json",
            "Referer": RESOURCES_URL,
            "User-Agent": LEAKER_PROXY_USER_AGENT,
        },
        timeout=18,
    )
    response.raise_for_status()
    return response.json()


def fetch_resource_detail(resource_id: int) -> dict:
    clean_resource_id = safe_int(resource_id)
    if clean_resource_id <= 0:
        raise ValueError("Invalid resource id.")

    response = requests.get(
        f"{RESOURCES_API_URL}/{clean_resource_id}",
        headers={
            "Accept": "application/json",
            "Referer": f"{RESOURCES_URL}/{clean_resource_id}",
            "User-Agent": LEAKER_PROXY_USER_AGENT,
        },
        timeout=18,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Resource API returned an invalid response.")
    return payload


def get_resource_detail_payload(resource_id: int, *, refresh: bool = False) -> dict:
    clean_resource_id = safe_int(resource_id)
    if clean_resource_id <= 0:
        raise ValueError("Invalid resource id.")

    now = time.time()
    with RESOURCE_DETAIL_LOCK:
        cached_entry = RESOURCE_DETAIL_CACHE.get(clean_resource_id) or {}
        cached_payload = cached_entry.get("payload")
        if not refresh and cached_payload and float(cached_entry.get("expiresAt") or 0) > now:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload

    started_at = time.time()
    raw_payload = fetch_resource_detail(clean_resource_id)
    raw_item = raw_payload.get("item")
    if not isinstance(raw_item, dict):
        raise ValueError("Resource was not found.")

    raw_related = raw_payload.get("related")
    related = [
        sanitize_related_resource_item(item)
        for item in raw_related
        if isinstance(item, dict)
    ] if isinstance(raw_related, list) else []

    payload = {
        "success": True,
        "sourceUrl": f"{RESOURCES_API_URL}/{clean_resource_id}",
        "profileUrl": f"{RESOURCES_URL}/{clean_resource_id}",
        "item": sanitize_resource_detail_item(raw_item),
        "related": related,
        "cached": False,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }

    with RESOURCE_DETAIL_LOCK:
        RESOURCE_DETAIL_CACHE[clean_resource_id] = {
            "payload": payload,
            "expiresAt": time.time() + RESOURCE_DETAIL_CACHE_SECONDS,
        }
    return dict(payload)


def get_hlx_api_key() -> str:
    key = str(os.environ.get("REYLI_HLX_API_KEY") or os.environ.get("HLX_API_KEY") or "").strip()
    if key:
        return key
    candidates = [HLX_API_KEY_PATH]
    if sys.platform.startswith("win"):
        appdata_root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata_root:
            candidates.append(Path(appdata_root) / "6ure Leak Upld. User Data" / HLX_API_KEY_FILE_NAME)
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        cache_path = str(candidate)
        with HLX_API_KEY_LOCK:
            if (
                HLX_API_KEY_CACHE.get("path") == cache_path
                and float(HLX_API_KEY_CACHE.get("mtime") or 0) == float(stat.st_mtime)
                and HLX_API_KEY_CACHE.get("key")
            ):
                return str(HLX_API_KEY_CACHE["key"])
        try:
            key = candidate.read_text(encoding="utf-8-sig").strip()
        except OSError:
            continue
        if key:
            with HLX_API_KEY_LOCK:
                HLX_API_KEY_CACHE.update({"path": cache_path, "mtime": float(stat.st_mtime), "key": key})
            return key
    return ""


def hlx_http_session() -> requests.Session:
    session = getattr(HLX_HTTP_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        HLX_HTTP_LOCAL.session = session
    return session


def youtube_web_session() -> requests.Session:
    session = getattr(YOUTUBE_WEB_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        YOUTUBE_WEB_LOCAL.session = session
    return session


def normalize_tiktok_username(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" in text or text.startswith("www.") or text.startswith("tiktok.com"):
        try:
            parsed = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
            match = re.search(r"/@([^/?#]+)", parsed.path or "")
            if match:
                text = match.group(1)
        except ValueError:
            pass
    text = text.strip().lstrip("@")
    text = re.split(r"[\s/?#&]+", text, 1)[0]
    text = re.sub(r"[^A-Za-z0-9._]", "", text)
    return text[:64]


def tiktok_username_candidates(value: str) -> list[str]:
    raw = str(value or "").strip()
    candidates: list[str] = []

    def add(candidate: str) -> None:
        clean = normalize_tiktok_username(candidate)
        key = clean.casefold()
        if clean and key not in {item.casefold() for item in candidates}:
            candidates.append(clean)

    add(raw)
    for token in re.split(r"[\s,;]+", raw):
        add(token)
    compact = re.sub(r"\s+", "", raw)
    if compact != raw:
        add(compact)
    return candidates[:8]


def tiktok_search_profile_candidates(value: str) -> list[str]:
    raw = str(value or "").strip()
    base_candidates = tiktok_username_candidates(raw)
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        clean = normalize_tiktok_username(candidate)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            candidates.append(clean)

    for candidate in base_candidates:
        add(candidate)

    query = normalize_tiktok_username(raw)
    query_key = query.casefold()
    if query_key:
        for alias in MY_RESOURCES_UPLOADER_ALIASES:
            alias_clean = normalize_tiktok_username(alias)
            alias_key = alias_clean.casefold()
            if alias_key and (query_key in alias_key or alias_key in query_key):
                add(alias_clean)

        if len(query) >= 4:
            add(query[:-1])
        if len(query) >= 3:
            for suffix in ("ar", "i", "ii", "x", "_", ".", "official", "real", "0", "1", "2", "3", "4"):
                add(f"{query}{suffix}")

    max_candidates = max(1, min(12, HLX_TIKTOK_SEARCH_MAX_CANDIDATES))
    return candidates[:max_candidates]


def score_hlx_tiktok_search_result(profile: dict, query: str, candidate_order: dict[str, int]) -> tuple:
    query_key = normalize_tiktok_username(query).casefold()
    username_key = normalize_tiktok_username(profile.get("username")).casefold()
    nickname_key = normalize_tiktok_username(profile.get("nickname")).casefold()
    candidate_rank = candidate_order.get(username_key, 999)
    follower_count = safe_int(profile.get("followerCount"))

    if username_key == query_key:
        relation_rank = 0
    elif username_key.startswith(query_key):
        relation_rank = 1
    elif query_key and (query_key in username_key or query_key in nickname_key):
        relation_rank = 2
    else:
        common_prefix = 0
        for left, right in zip(username_key, query_key):
            if left != right:
                break
            common_prefix += 1
        relation_rank = 3 if common_prefix >= max(3, len(query_key) - 1) else 4

    return (
        relation_rank,
        candidate_rank,
        -follower_count,
        username_key,
    )


def hlx_cache_get(key: str, *, allow_stale: bool = False) -> dict | None:
    now = time.time()
    with HLX_TIKTOK_LOCK:
        cached_entry = HLX_TIKTOK_CACHE.get(key) or {}
        cached_payload = cached_entry.get("payload")
        if cached_payload and (allow_stale or float(cached_entry.get("expiresAt") or 0) > now):
            return dict(cached_payload)
    return None


def hlx_cache_set(key: str, payload: dict) -> None:
    with HLX_TIKTOK_LOCK:
        HLX_TIKTOK_CACHE[key] = {
            "payload": payload,
            "expiresAt": time.time() + HLX_TIKTOK_CACHE_SECONDS,
        }


def hlx_tiktok_get(path: str, params: dict) -> dict:
    api_key = get_hlx_api_key()
    if not api_key:
        raise ValueError("HLX API key is missing.")
    last_error = "HLX API request failed."
    attempts = max(1, min(3, HLX_API_RETRIES + 1))
    read_timeout = max(1.0, HLX_API_TIMEOUT_SECONDS)
    connect_timeout = max(0.5, min(HLX_API_CONNECT_TIMEOUT_SECONDS, read_timeout))
    for attempt in range(attempts):
        try:
            response = hlx_http_session().get(
                f"{HLX_API_BASE_URL}{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                    "X-API-Key": api_key,
                    "User-Agent": LEAKER_PROXY_USER_AGENT,
                },
                timeout=(connect_timeout, read_timeout),
            )
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type.lower():
                last_error = f"HLX API returned HTTP {response.status_code}."
                if response.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    break
            else:
                payload = response.json()
                if response.status_code >= 400:
                    last_error = str(payload.get("detail") or payload.get("error") or f"HLX API HTTP {response.status_code}")
                    if response.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                        break
                elif isinstance(payload, dict) and str(payload.get("status") or "").lower() in {"error", "failed"}:
                    last_error = str(payload.get("message") or payload.get("error") or "HLX API request failed.")
                elif isinstance(payload, dict):
                    return payload
                else:
                    last_error = "HLX API returned an invalid response."
                    break
        except (requests.Timeout, requests.ConnectionError) as error:
            last_error = f"HLX API connection was slow: {error}"
        except ValueError as error:
            last_error = str(error)
            break

        if attempt < attempts - 1:
            time.sleep(0.12 + (attempt * 0.18))

    raise ValueError(last_error)


def format_tiktok_profile_url(username: str) -> str:
    clean_username = normalize_tiktok_username(username)
    return f"https://www.tiktok.com/@{clean_username}" if clean_username else "https://www.tiktok.com"


def normalize_hlx_timestamp(value) -> str:
    timestamp = safe_int(value)
    if timestamp <= 0:
        return ""
    if timestamp > 100000000000:
        timestamp = int(timestamp / 1000)
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp))
    except (OverflowError, OSError, ValueError):
        return ""


def sanitize_hlx_tiktok_video(item: dict, detail: dict | None = None) -> dict:
    source = item if isinstance(item, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    video_detail = detail.get("video") if isinstance(detail.get("video"), dict) else {}
    stats = detail.get("stats") if isinstance(detail.get("stats"), dict) else {}
    author = detail.get("author") if isinstance(detail.get("author"), dict) else {}
    video_url = str(source.get("url") or detail.get("url") or "").strip()
    video_id = str(source.get("id") or detail.get("id") or video_detail.get("id") or "").strip()
    if not video_url and video_id:
        username = normalize_tiktok_username(author.get("username") or author.get("uniqueId") or "")
        if username:
            video_url = f"{format_tiktok_profile_url(username)}/video/{video_id}"
    title = str(source.get("title") or detail.get("title") or detail.get("description") or detail.get("desc") or "").strip()
    return {
        "id": video_id,
        "url": video_url,
        "title": sanitize_resource_description(title, limit=180),
        "description": sanitize_resource_description(detail.get("description") or detail.get("desc") or title, limit=260),
        "duration": safe_int(source.get("duration") or video_detail.get("duration")),
        "durationText": str(video_detail.get("durationFormatted") or "").strip(),
        "coverUrl": make_6ure_absolute_url(
            video_detail.get("cover")
            or video_detail.get("originCover")
            or detail.get("cover")
            or source.get("cover")
            or source.get("thumbnail")
            or ""
        ),
        "dynamicCoverUrl": make_6ure_absolute_url(video_detail.get("dynamicCover") or detail.get("dynamicCover") or ""),
        "playUrl": make_6ure_absolute_url(video_detail.get("playAddr") or video_detail.get("downloadAddr") or ""),
        "viewCount": safe_int(source.get("view_count") or source.get("viewCount") or stats.get("playCount") or stats.get("play_count")),
        "likeCount": safe_int(source.get("like_count") or source.get("likeCount") or stats.get("diggCount") or stats.get("digg_count")),
        "commentCount": safe_int(source.get("comment_count") or source.get("commentCount") or stats.get("commentCount") or stats.get("comment_count")),
        "shareCount": safe_int(source.get("share_count") or source.get("shareCount") or stats.get("shareCount") or stats.get("share_count")),
        "createdAt": normalize_hlx_timestamp(source.get("timestamp") or detail.get("createTime") or detail.get("creation")),
    }


def sanitize_hlx_tiktok_profile(payload: dict, *, include_videos: bool = True) -> dict:
    username = normalize_tiktok_username(payload.get("username") or payload.get("uniqueId") or "")
    videos = payload.get("videos") if isinstance(payload.get("videos"), list) else []
    return {
        "id": str(payload.get("id") or payload.get("secUid") or "").strip(),
        "username": username,
        "nickname": str(payload.get("nickname") or payload.get("nickName") or username or "TikTok user").strip(),
        "url": format_tiktok_profile_url(username),
        "avatarUrl": make_6ure_absolute_url(
            payload.get("avatar")
            or payload.get("avatarMedium")
            or payload.get("avatarLarger")
            or payload.get("avatarThumb")
            or ""
        ),
        "signature": sanitize_resource_description(payload.get("signature") or "", limit=260),
        "bioLink": make_6ure_absolute_url(payload.get("bioLink") or ""),
        "verified": bool(payload.get("verified")),
        "private": bool(payload.get("privateAccount") or payload.get("secret")),
        "followerCount": safe_int(payload.get("followerCount")),
        "followingCount": safe_int(payload.get("followingCount")),
        "heartCount": safe_int(payload.get("heartCount") or payload.get("heart")),
        "videoCount": safe_int(payload.get("videoCount")),
        "diggCount": safe_int(payload.get("diggCount")),
        "videos": [sanitize_hlx_tiktok_video(item) for item in videos if isinstance(item, dict)] if include_videos else [],
    }


def fetch_hlx_tiktok_profile(username: str, *, limit: int = 0, refresh: bool = False) -> dict:
    clean_username = normalize_tiktok_username(username)
    if not clean_username:
        raise ValueError("Enter a TikTok username.")
    clean_limit = max(0, min(100, safe_int(limit, 0)))
    cache_key = f"profile:{clean_username.casefold()}:{clean_limit}"
    if not refresh:
        cached_payload = hlx_cache_get(cache_key)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload
    started_at = time.time()
    try:
        raw = hlx_tiktok_get("/tiktok/profile", {"username": clean_username, "limit": clean_limit})
    except Exception as error:
        cached_payload = hlx_cache_get(cache_key, allow_stale=True)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            payload["stale"] = True
            payload["warning"] = str(error)
            return payload
        raise
    profile = sanitize_hlx_tiktok_profile(raw, include_videos=True)
    if not profile.get("username"):
        profile["username"] = clean_username
        profile["url"] = format_tiktok_profile_url(clean_username)
    payload = {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/tiktok/profile",
        "profile": profile,
        "rawSource": str(raw.get("source") or "").strip(),
        "cached": False,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }
    hlx_cache_set(cache_key, payload)
    return dict(payload)


def fetch_hlx_tiktok_video(url: str, *, refresh: bool = False) -> dict:
    clean_url = str(url or "").strip()
    if not clean_url:
        raise ValueError("Video URL is missing.")
    cache_key = f"video:{clean_url}"
    if not refresh:
        cached_payload = hlx_cache_get(cache_key)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload
    try:
        raw = hlx_tiktok_get("/tiktok/video", {"url": clean_url})
    except Exception as error:
        cached_payload = hlx_cache_get(cache_key, allow_stale=True)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            payload["stale"] = True
            payload["warning"] = str(error)
            return payload
        raise
    payload = {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/tiktok/video",
        "video": sanitize_hlx_tiktok_video({"url": clean_url}, raw),
        "cached": False,
        "updatedAt": int(time.time() * 1000),
    }
    hlx_cache_set(cache_key, payload)
    return dict(payload)


def get_hlx_tiktok_search_payload(
    query: str,
    *,
    limit: int = 0,
    result_limit: int = HLX_TIKTOK_SEARCH_DEFAULT_RESULTS,
    refresh: bool = False,
) -> dict:
    candidates = tiktok_search_profile_candidates(query)
    if not candidates:
        raise ValueError("Enter a TikTok username.")

    started_at = time.time()
    results: list[dict] = []
    errors: list[dict] = []
    seen_results: set[str] = set()
    result_limit = max(1, min(12, safe_int(result_limit, HLX_TIKTOK_SEARCH_DEFAULT_RESULTS)))
    workers = max(1, min(HLX_TIKTOK_SEARCH_MAX_WORKERS, len(candidates)))
    budget_seconds = max(1.5, min(15.0, HLX_TIKTOK_SEARCH_BUDGET_SECONDS))
    loop_started = time.monotonic()
    deadline = loop_started + budget_seconds
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    futures: dict[concurrent.futures.Future, str] = {
        executor.submit(fetch_hlx_tiktok_profile, candidate, limit=limit, refresh=refresh): candidate
        for candidate in candidates
    }
    pending = set(futures)
    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = concurrent.futures.wait(
                pending,
                timeout=min(0.35, remaining),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done:
                if len(results) >= result_limit and time.monotonic() >= loop_started + min(1.2, budget_seconds):
                    break
                continue
            for future in done:
                candidate = futures[future]
                try:
                    profile_payload = future.result()
                    profile = profile_payload.get("profile")
                    username_key = normalize_tiktok_username(profile.get("username") if isinstance(profile, dict) else "").casefold()
                    if isinstance(profile, dict) and username_key and username_key not in seen_results:
                        seen_results.add(username_key)
                        results.append(profile)
                except Exception as error:
                    errors.append({"username": candidate, "message": str(error)})
            if len(results) >= result_limit:
                break
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    partial = bool(pending)
    candidate_order = {candidate.casefold(): index for index, candidate in enumerate(candidates)}
    results.sort(key=lambda item: score_hlx_tiktok_search_result(item, query, candidate_order))
    results = results[:result_limit]
    return {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/tiktok/profile",
        "query": query,
        "candidates": candidates,
        "results": results,
        "errors": errors[:4],
        "partial": partial,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }


def get_hlx_tiktok_profile_payload(
    username: str,
    *,
    limit: int = 12,
    preview_limit: int = 0,
    refresh: bool = False,
) -> dict:
    payload = fetch_hlx_tiktok_profile(username, limit=limit, refresh=refresh)
    profile = dict(payload.get("profile") or {})
    videos = [dict(item) for item in profile.get("videos") or [] if isinstance(item, dict)]
    preview_limit = max(0, min(12, safe_int(preview_limit, 6)))
    detail_errors: list[dict] = []
    if preview_limit and videos:
        detail_targets = [(index, item) for index, item in enumerate(videos[:preview_limit]) if item.get("url")]
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(3, len(detail_targets) or 1))
        futures = {
            executor.submit(fetch_hlx_tiktok_video, item.get("url"), refresh=refresh): (index, item)
            for index, item in detail_targets
        }
        pending = set(futures)
        try:
            done, pending = concurrent.futures.wait(
                pending,
                timeout=max(1.0, min(12.0, HLX_TIKTOK_DETAIL_BUDGET_SECONDS)),
                return_when=concurrent.futures.ALL_COMPLETED,
            )
            for future in done:
                index, item = futures[future]
                try:
                    video_payload = future.result()
                    video = video_payload.get("video")
                    if isinstance(video, dict):
                        videos[index].update({key: value for key, value in video.items() if value not in ("", 0, None)})
                except Exception as error:
                    detail_errors.append({"url": item.get("url"), "message": str(error)})
            for future in pending:
                index, item = futures[future]
                detail_errors.append({"url": item.get("url"), "message": "Video details timed out."})
                future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    profile["videos"] = videos
    return {
        **payload,
        "profile": profile,
        "detailErrors": detail_errors[:4],
    }


def normalize_youtube_identifier(value: str, *, max_length: int = 128) -> str:
    text = str(value or "").strip().lstrip("@")
    text = re.split(r"[\s/?#&]+", text, 1)[0]
    text = re.sub(r"[^A-Za-z0-9._-]", "", text)
    return text[:max_length]


def youtube_handle_from_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
    except ValueError:
        return ""
    path = parsed.path or ""
    handle_match = re.search(r"/@([^/?#]+)", path)
    if handle_match:
        return normalize_youtube_identifier(handle_match.group(1))
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0].lower() in {"c", "user"}:
        return normalize_youtube_identifier(parts[1])
    return ""


def normalize_youtube_channel_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" in text or text.startswith("www.") or text.startswith("m.youtube.com") or text.startswith("youtube.com") or text.startswith("youtu.be"):
        try:
            parsed = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
        except ValueError:
            return ""
        host = parsed.netloc.lower().split("@")[-1].split(":")[0]
        path = parsed.path or ""
        if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            parts = [part for part in path.split("/") if part]
            if parts and parts[0].startswith("@"):
                handle = normalize_youtube_identifier(parts[0][1:])
                return f"https://www.youtube.com/@{handle}" if handle else ""
            if len(parts) >= 2 and parts[0].lower() in {"channel", "c", "user"}:
                identifier = re.sub(r"[^A-Za-z0-9._-]", "", parts[1])[:128]
                return f"https://www.youtube.com/{parts[0]}/{identifier}" if identifier else ""
        return text
    clean = normalize_youtube_identifier(text)
    if not clean:
        return ""
    if clean.upper().startswith("UC") and len(clean) >= 12:
        return f"https://www.youtube.com/channel/{clean}"
    return f"https://www.youtube.com/@{clean}"


def youtube_channel_candidates(value: str) -> list[str]:
    raw = str(value or "").strip()
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        clean = normalize_youtube_channel_url(candidate)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            candidates.append(clean)

    add(raw)
    for token in re.split(r"[\s,;]+", raw):
        add(token)

    looks_like_url = "://" in raw or raw.startswith("www.") or raw.startswith("youtube.com") or raw.startswith("youtu.be")
    handle = youtube_handle_from_url(raw) or ("" if looks_like_url else normalize_youtube_identifier(raw))
    if handle:
        add(f"https://www.youtube.com/@{handle}")
        add(f"https://www.youtube.com/c/{handle}")
        add(f"https://www.youtube.com/user/{handle}")
        if handle.upper().startswith("UC") and len(handle) >= 12:
            add(f"https://www.youtube.com/channel/{handle}")
        for suffix in ("official", "tv", "channel", "videos"):
            add(f"https://www.youtube.com/@{handle}{suffix}")

    max_candidates = max(1, min(24, HLX_YOUTUBE_SEARCH_MAX_CANDIDATES))
    return candidates[:max_candidates]


def parse_social_count(value) -> int:
    text = html.unescape(str(value or "")).replace("\xa0", " ").strip().casefold()
    if not text:
        return 0
    compact_match = re.search(r"(\d+(?:[.,]\d+)?)\s*([kmb])\b", text, flags=re.IGNORECASE)
    if compact_match:
        number_text = compact_match.group(1).replace(",", ".")
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(compact_match.group(2).casefold(), 1)
        return int(safe_float(number_text) * multiplier)
    number_match = re.search(r"\d[\d,.\s]*", text)
    if not number_match:
        return 0
    digits = re.sub(r"[^\d]", "", number_match.group(0))
    return safe_int(digits)


def youtube_renderer_text(value) -> str:
    if value in (None, False):
        return ""
    if isinstance(value, str):
        return html.unescape(value).strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return "".join(youtube_renderer_text(item) for item in value).strip()
    if not isinstance(value, dict):
        return ""
    for key in ("simpleText", "text", "label"):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return html.unescape(text).strip()
    runs = value.get("runs")
    if isinstance(runs, list):
        text = "".join(youtube_renderer_text(run) for run in runs).strip()
        if text:
            return text
    accessibility = value.get("accessibility")
    if isinstance(accessibility, dict):
        text = youtube_renderer_text(accessibility.get("accessibilityData"))
        if text:
            return text
    return ""


def extract_balanced_json_object(text: str, marker: str) -> dict:
    source = str(text or "")
    marker_index = source.find(marker)
    if marker_index < 0:
        return {}
    start = source.find("{", marker_index)
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(source[start:index + 1])
                    return payload if isinstance(payload, dict) else {}
                except ValueError:
                    return {}
    return {}


def iter_youtube_channel_renderers(value):
    if isinstance(value, dict):
        renderer = value.get("channelRenderer")
        if isinstance(renderer, dict):
            yield renderer
        for nested in value.values():
            yield from iter_youtube_channel_renderers(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_youtube_channel_renderers(nested)


def youtube_url_from_renderer(renderer: dict) -> str:
    if not isinstance(renderer, dict):
        return ""
    browse = first_hlx_dict(
        renderer.get("browseEndpoint"),
        first_hlx_dict(renderer.get("navigationEndpoint")).get("browseEndpoint"),
    )
    path = str(browse.get("canonicalBaseUrl") or "").strip()
    if not path:
        path = str(
            first_hlx_dict(first_hlx_dict(renderer.get("navigationEndpoint")).get("commandMetadata")).get("webCommandMetadata", {}).get("url")
            or ""
        ).strip()
    if path:
        if path.startswith("/"):
            return normalize_youtube_channel_url(f"https://www.youtube.com{path}")
        return normalize_youtube_channel_url(path)
    channel_id = str(renderer.get("channelId") or browse.get("browseId") or "").strip()
    if channel_id and channel_id.upper().startswith("UC"):
        return normalize_youtube_channel_url(channel_id)
    return ""


def youtube_discovery_terms(value: str) -> list[str]:
    raw = str(value or "").strip()
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        clean = re.sub(r"\s+", " ", str(term or "").strip().lstrip("@"))
        if not clean or len(clean) < 3:
            return
        key = clean.casefold()
        if key not in seen:
            seen.add(key)
            terms.append(clean)

    handle = youtube_handle_from_url(raw)
    looks_like_url = "://" in raw or raw.startswith("www.") or raw.startswith("youtube.com") or raw.startswith("youtu.be")
    identifier = handle or ("" if looks_like_url else normalize_youtube_identifier(raw))
    add(identifier or raw)
    if identifier:
        add(re.sub(r"[_\-.]+", " ", identifier))
        without_digits = re.sub(r"\d+$", "", identifier)
        if without_digits != identifier:
            add(without_digits)
        without_suffix = re.sub(r"(official|channel|videos|music|tv)$", "", identifier, flags=re.IGNORECASE)
        if without_suffix != identifier:
            add(without_suffix)
    return terms[:4]


def sanitize_youtube_discovery_channel(renderer: dict, *, query: str = "") -> dict:
    browse = first_hlx_dict(
        renderer.get("browseEndpoint") if isinstance(renderer, dict) else None,
        first_hlx_dict(renderer.get("navigationEndpoint") if isinstance(renderer, dict) else {}).get("browseEndpoint"),
    )
    channel_id = str((renderer or {}).get("channelId") or browse.get("browseId") or "").strip()
    url = youtube_url_from_renderer(renderer)
    handle = youtube_renderer_text((renderer or {}).get("subscriberCountText"))
    if not handle.startswith("@"):
        handle_from_url = youtube_handle_from_url(url)
        handle = f"@{handle_from_url}" if handle_from_url else ""
    username = normalize_youtube_identifier(handle) or normalize_youtube_identifier(youtube_handle_from_url(url)) or channel_id
    title = (
        youtube_renderer_text((renderer or {}).get("title"))
        or youtube_renderer_text((renderer or {}).get("shortBylineText"))
        or username
        or "YouTube channel"
    )
    subscriber_text = youtube_renderer_text((renderer or {}).get("subscriberCountText"))
    video_count_text = youtube_renderer_text((renderer or {}).get("videoCountText"))
    thumbnail = best_hlx_thumbnail_url(first_hlx_dict((renderer or {}).get("thumbnail")).get("thumbnails") or "")
    description = youtube_renderer_text((renderer or {}).get("descriptionSnippet"))
    return {
        "id": channel_id,
        "username": username,
        "handle": handle or (f"@{username}" if username and not username.upper().startswith("UC") else ""),
        "nickname": sanitize_resource_description(title, limit=90),
        "url": url or normalize_youtube_channel_url(channel_id or username),
        "avatarUrl": thumbnail,
        "signature": sanitize_resource_description(description, limit=260),
        "verified": False,
        "private": False,
        "followerCount": parse_social_count(subscriber_text),
        "followingCount": 0,
        "heartCount": 0,
        "videoCount": parse_social_count(video_count_text),
        "diggCount": 0,
        "platform": "youtube",
        "videos": [],
        "discovery": True,
        "matchQuery": query,
    }


def youtube_profile_keys(profile: dict) -> set[str]:
    keys: set[str] = set()
    if not isinstance(profile, dict):
        return keys
    for key in ("id", "url", "username", "handle"):
        value = str(profile.get(key) or "").strip()
        if value:
            keys.add(value.casefold())
    url = str(profile.get("url") or "").strip()
    handle = youtube_handle_from_url(url)
    if handle:
        keys.add(handle.casefold())
        keys.add(f"@{handle}".casefold())
    return keys


def add_unique_youtube_profile(results: list[dict], seen: set[str], profile: dict) -> bool:
    keys = youtube_profile_keys(profile)
    if not keys:
        return False
    if keys & seen:
        return False
    seen.update(keys)
    results.append(profile)
    return True


def youtube_profile_has_value(value) -> bool:
    if value in ("", None, False):
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, list):
        return bool(value)
    return True


def merge_youtube_profiles(base: dict, update: dict) -> dict:
    merged = dict(base or {})
    for key, value in (update or {}).items():
        if youtube_profile_has_value(value):
            merged[key] = value
    if update and not update.get("discovery"):
        merged.pop("discovery", None)
    return merged


def upsert_youtube_profile(results: list[dict], seen: set[str], profile: dict) -> bool:
    keys = youtube_profile_keys(profile)
    if not keys:
        return False
    for index, existing in enumerate(results):
        if youtube_profile_keys(existing) & keys:
            results[index] = merge_youtube_profiles(existing, profile)
            seen.update(youtube_profile_keys(results[index]))
            return False
    seen.update(keys)
    results.append(profile)
    return True


def discover_youtube_channels(query: str, *, limit: int = 12, refresh: bool = False) -> tuple[list[dict], list[dict]]:
    clean_query = str(query or "").strip()
    result_limit = max(1, min(24, safe_int(limit, 12)))
    cache_key = f"youtube-discovery:{clean_query.casefold()}:{result_limit}"
    now = time.time()
    with HLX_YOUTUBE_DISCOVERY_LOCK:
        cached_entry = HLX_YOUTUBE_DISCOVERY_CACHE.get(cache_key) or {}
        if not refresh and float(cached_entry.get("expiresAt") or 0) > now:
            return list(cached_entry.get("profiles") or []), list(cached_entry.get("errors") or [])

    profiles: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": LEAKER_PROXY_USER_AGENT,
    }
    terms = youtube_discovery_terms(clean_query)

    def fetch_discovery_term(term: str) -> tuple[str, list[dict], dict | None]:
        try:
            response = youtube_web_session().get(
                "https://www.youtube.com/results",
                params={"search_query": term, "sp": "EgIQAg==", "hl": "en", "gl": "US"},
                headers=headers,
                timeout=max(1.0, min(10.0, HLX_YOUTUBE_DISCOVERY_TIMEOUT_SECONDS)),
            )
            response.raise_for_status()
            data = extract_balanced_json_object(response.text, "ytInitialData")
            if not data:
                raise ValueError("YouTube search payload could not be parsed.")
            term_profiles = []
            term_seen: set[str] = set()
            for renderer in iter_youtube_channel_renderers(data):
                profile = sanitize_youtube_discovery_channel(renderer, query=term)
                if add_unique_youtube_profile(term_profiles, term_seen, profile) and len(term_profiles) >= result_limit:
                    break
            return term, term_profiles, None
        except Exception as error:
            return term, [], {"query": term, "message": str(error)}

    workers = max(1, min(4, len(terms)))
    term_results: dict[str, list[dict]] = {}
    if terms:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        futures = {executor.submit(fetch_discovery_term, term): term for term in terms}
        pending = set(futures)
        try:
            deadline = time.monotonic() + max(1.2, min(8.0, HLX_YOUTUBE_DISCOVERY_TIMEOUT_SECONDS + 0.8))
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                done, pending = concurrent.futures.wait(
                    pending,
                    timeout=min(0.35, remaining),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                if not done:
                    continue
                for future in done:
                    term = futures[future]
                    try:
                        result_term, result_profiles, result_error = future.result()
                        term_results[result_term or term] = result_profiles
                        if result_error:
                            errors.append(result_error)
                    except Exception as error:
                        errors.append({"query": term, "message": str(error)})
                preview_profiles: list[dict] = []
                preview_seen: set[str] = set()
                for term in terms:
                    for profile in term_results.get(term, []):
                        add_unique_youtube_profile(preview_profiles, preview_seen, profile)
                        if len(preview_profiles) >= result_limit:
                            break
                    if len(preview_profiles) >= result_limit:
                        break
                if len(preview_profiles) >= result_limit and terms[0] in term_results:
                    break
            for future in pending:
                errors.append({"query": futures[future], "message": "YouTube channel discovery timed out."})
                future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    for term in terms:
        if len(profiles) >= result_limit:
            break
        for profile in term_results.get(term, []):
            add_unique_youtube_profile(profiles, seen, profile)
            if len(profiles) >= result_limit:
                break

    with HLX_YOUTUBE_DISCOVERY_LOCK:
        HLX_YOUTUBE_DISCOVERY_CACHE[cache_key] = {
            "profiles": profiles,
            "errors": errors,
            "expiresAt": time.time() + HLX_YOUTUBE_DISCOVERY_CACHE_SECONDS,
        }
    return list(profiles), list(errors)


def best_hlx_thumbnail_url(value) -> str:
    if isinstance(value, str):
        return make_6ure_absolute_url(value)
    if isinstance(value, dict):
        return make_6ure_absolute_url(value.get("url") or value.get("src") or "")
    if isinstance(value, list):
        best = None
        best_score = -1
        for item in value:
            if isinstance(item, str):
                score = 0
                url = item
            elif isinstance(item, dict):
                score = safe_int(item.get("width")) * safe_int(item.get("height"))
                url = str(item.get("url") or item.get("src") or "").strip()
            else:
                continue
            if url and score >= best_score:
                best = url
                best_score = score
        return make_6ure_absolute_url(best or "")
    return ""


def youtube_video_url_from_id(video_id: str) -> str:
    clean_id = re.sub(r"[^A-Za-z0-9_-]", "", str(video_id or ""))[:32]
    return f"https://www.youtube.com/watch?v={clean_id}" if clean_id else ""


def is_youtube_video_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(value or ""))
    except ValueError:
        return False
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    path = parsed.path.lower()
    if host == "youtu.be" and path.strip("/"):
        return True
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return path == "/watch" and bool(urllib.parse.parse_qs(parsed.query).get("v"))
    return False


def youtube_channel_url_from_video_payload(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    url = str(
        payload.get("channel_url")
        or payload.get("channelUrl")
        or payload.get("uploader_url")
        or payload.get("uploaderUrl")
        or payload.get("creator_url")
        or ""
    ).strip()
    if url:
        return url
    channel_id = str(payload.get("channel_id") or payload.get("channelId") or payload.get("uploader_id") or "").strip()
    if channel_id and channel_id.upper().startswith("UC"):
        clean_channel_id = re.sub(r"[^A-Za-z0-9_-]", "", channel_id)[:128]
        return f"https://www.youtube.com/channel/{clean_channel_id}"
    handle = str(payload.get("channel_handle") or payload.get("handle") or payload.get("uploader_id") or "").strip()
    if handle and not handle.upper().lstrip("@").startswith("UC"):
        return normalize_youtube_channel_url(handle)
    return ""


def first_hlx_dict(*values) -> dict:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def unwrap_hlx_payload(payload: dict, *keys: str) -> dict:
    current = payload if isinstance(payload, dict) else {}
    for key in keys:
        value = current.get(key)
        if isinstance(value, dict):
            return value
    data = current.get("data")
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, dict):
                return value
        return data
    return current


def hlx_text_value(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, dict):
            nested = hlx_text_value(value, "name", "title", "text", "url")
            if nested:
                return nested
    return ""


def hlx_int_value(payload: dict, *keys: str) -> int:
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        number = safe_int(value)
        if number:
            return number
        if isinstance(value, dict):
            nested = hlx_int_value(value, "count", "value", "total")
            if nested:
                return nested
    return 0


def sanitize_hlx_youtube_video(item: dict, detail: dict | None = None) -> dict:
    source = unwrap_hlx_payload(item if isinstance(item, dict) else {}, "video", "entry")
    detail = unwrap_hlx_payload(detail if isinstance(detail, dict) else {}, "video", "entry")
    video_id = hlx_text_value(source, "id", "videoId", "video_id") or hlx_text_value(detail, "id", "videoId", "video_id")
    url = (
        hlx_text_value(source, "url", "webpage_url", "webpageUrl", "original_url")
        or hlx_text_value(detail, "url", "webpage_url", "webpageUrl", "original_url")
    )
    if not url:
        url = youtube_video_url_from_id(video_id)
    title = hlx_text_value(source, "title", "name") or hlx_text_value(detail, "title", "name") or "YouTube video"
    thumbnail = best_hlx_thumbnail_url(
        source.get("thumbnail")
        or source.get("thumbnailUrl")
        or source.get("thumbnails")
        or detail.get("thumbnail")
        or detail.get("thumbnails")
        or ""
    )
    return {
        "id": video_id,
        "url": url,
        "title": sanitize_resource_description(title, limit=180),
        "description": sanitize_resource_description(hlx_text_value(source, "description") or hlx_text_value(detail, "description") or title, limit=260),
        "duration": hlx_int_value(source, "duration") or hlx_int_value(detail, "duration"),
        "durationText": hlx_text_value(source, "duration_string", "durationText") or hlx_text_value(detail, "duration_string", "durationText"),
        "coverUrl": thumbnail,
        "dynamicCoverUrl": "",
        "playUrl": "",
        "viewCount": hlx_int_value(source, "view_count", "viewCount", "views") or hlx_int_value(detail, "view_count", "viewCount", "views"),
        "likeCount": hlx_int_value(source, "like_count", "likeCount", "likes") or hlx_int_value(detail, "like_count", "likeCount", "likes"),
        "commentCount": hlx_int_value(source, "comment_count", "commentCount", "comments") or hlx_int_value(detail, "comment_count", "commentCount", "comments"),
        "shareCount": 0,
        "createdAt": normalize_hlx_timestamp(source.get("timestamp") or detail.get("timestamp")),
    }


def sanitize_hlx_youtube_channel(payload: dict, *, include_videos: bool = True, fallback_url: str = "") -> dict:
    root = unwrap_hlx_payload(payload if isinstance(payload, dict) else {}, "profile", "result")
    channel = unwrap_hlx_payload(payload if isinstance(payload, dict) else {}, "channel")
    if channel is payload:
        channel = first_hlx_dict(root.get("channel"))
    if not channel:
        channel = root
    if not any(key in channel for key in ("id", "channel_id", "channelId", "name", "title", "handle", "url")):
        for value in channel.values():
            if isinstance(value, dict) and any(key in value for key in ("channel_id", "channelId", "handle", "subscriber_count", "video_count")):
                channel = value
                break
    stats = first_hlx_dict(channel.get("stats"), channel.get("statistics"), root.get("stats"), root.get("statistics"))
    videos = channel.get("videos")
    if not isinstance(videos, list):
        videos = root.get("videos") if isinstance(root.get("videos"), list) else []
    if not isinstance(videos, list):
        videos = channel.get("entries") if isinstance(channel.get("entries"), list) else []
    if not isinstance(videos, list) and isinstance(root.get("entries"), list):
        videos = root.get("entries")
    channel_id = hlx_text_value(channel, "id", "channel_id", "channelId", "ucid") or hlx_text_value(root, "id", "channel_id", "channelId", "ucid")
    raw_handle = hlx_text_value(channel, "handle", "channel_handle", "uploader_id") or hlx_text_value(root, "handle", "channel_handle", "uploader_id")
    clean_handle = normalize_youtube_identifier(raw_handle)
    handle = raw_handle if raw_handle.startswith("@") else (f"@{clean_handle}" if clean_handle and not clean_handle.upper().startswith("UC") else "")
    username = normalize_youtube_identifier(handle) or normalize_youtube_identifier(youtube_handle_from_url(fallback_url)) or channel_id
    title = hlx_text_value(channel, "name", "uploader", "title") or hlx_text_value(root, "name", "uploader", "title") or username or "YouTube channel"
    url = hlx_text_value(channel, "url", "channel_url", "channelUrl", "webpage_url") or hlx_text_value(root, "url", "channel_url", "channelUrl", "webpage_url") or fallback_url
    if not url:
        url = normalize_youtube_channel_url(handle or username)
    return {
        "id": channel_id,
        "username": username,
        "handle": handle or (f"@{username}" if username and not username.upper().startswith("UC") else ""),
        "nickname": title,
        "url": url,
        "avatarUrl": best_hlx_thumbnail_url(
            channel.get("thumbnail")
            or channel.get("avatar")
            or channel.get("avatarUrl")
            or channel.get("thumbnails")
            or root.get("thumbnail")
            or root.get("thumbnails")
            or ""
        ),
        "signature": sanitize_resource_description(hlx_text_value(channel, "description", "channel_description") or hlx_text_value(root, "description", "channel_description"), limit=260),
        "bioLink": "",
        "verified": bool(channel.get("verified") or channel.get("is_verified") or root.get("verified") or root.get("is_verified")),
        "private": False,
        "followerCount": (
            hlx_int_value(channel, "subscriber_count", "subscriberCount", "subscribers")
            or hlx_int_value(root, "subscriber_count", "subscriberCount", "subscribers")
            or hlx_int_value(stats, "subscriber_count", "subscriberCount", "subscribers")
        ),
        "followingCount": 0,
        "heartCount": (
            hlx_int_value(channel, "view_count", "viewCount", "views")
            or hlx_int_value(root, "view_count", "viewCount", "views")
            or hlx_int_value(stats, "view_count", "viewCount", "views")
        ),
        "videoCount": (
            hlx_int_value(channel, "video_count", "videoCount")
            or hlx_int_value(root, "video_count", "videoCount")
            or hlx_int_value(stats, "video_count", "videoCount")
            or len(videos)
        ),
        "diggCount": 0,
        "platform": "youtube",
        "videos": [sanitize_hlx_youtube_video(item) for item in videos if isinstance(item, dict)] if include_videos else [],
    }


def fetch_hlx_youtube_channel(value: str, *, limit: int = 0, refresh: bool = False) -> dict:
    channel_url = normalize_youtube_channel_url(value)
    if not channel_url:
        raise ValueError("Enter a YouTube channel handle or URL.")
    if is_youtube_video_url(channel_url):
        video_raw = hlx_tiktok_get("/youtube/video", {"url": channel_url})
        resolved_channel_url = normalize_youtube_channel_url(youtube_channel_url_from_video_payload(video_raw))
        if not resolved_channel_url:
            raise ValueError("YouTube video loaded, but its channel URL could not be resolved.")
        channel_url = resolved_channel_url
    clean_limit = max(0, min(100, safe_int(limit, 0)))
    cache_key = f"youtube-channel:{channel_url.casefold()}:{clean_limit}"
    if not refresh:
        cached_payload = hlx_cache_get(cache_key)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload
    started_at = time.time()
    try:
        raw = hlx_tiktok_get(
            "/youtube/channel",
            {
                "url": channel_url,
                "max_videos": clean_limit,
                "sort": "newest",
                "fast": "true",
            },
        )
    except Exception as error:
        cached_payload = hlx_cache_get(cache_key, allow_stale=True)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            payload["stale"] = True
            payload["warning"] = str(error)
            return payload
        raise
    profile = sanitize_hlx_youtube_channel(raw, include_videos=True, fallback_url=channel_url)
    payload = {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/youtube/channel",
        "profile": profile,
        "rawSource": str(raw.get("source") or "").strip(),
        "cached": False,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }
    hlx_cache_set(cache_key, payload)
    return dict(payload)


def fetch_hlx_youtube_video(url: str, *, refresh: bool = False) -> dict:
    clean_url = str(url or "").strip()
    if not clean_url:
        raise ValueError("YouTube video URL is missing.")
    cache_key = f"youtube-video:{clean_url}"
    if not refresh:
        cached_payload = hlx_cache_get(cache_key)
        if cached_payload:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload
    raw = hlx_tiktok_get("/youtube/video", {"url": clean_url})
    payload = {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/youtube/video",
        "video": sanitize_hlx_youtube_video({"url": clean_url}, raw),
        "cached": False,
        "updatedAt": int(time.time() * 1000),
    }
    hlx_cache_set(cache_key, payload)
    return dict(payload)


def score_hlx_youtube_search_result(profile: dict, query: str, candidate_order: dict[str, int]) -> tuple:
    query_key = normalize_youtube_identifier(youtube_handle_from_url(query) or query).casefold()
    username_key = normalize_youtube_identifier(profile.get("username")).casefold()
    handle_key = normalize_youtube_identifier(profile.get("handle")).casefold()
    nickname_key = normalize_youtube_identifier(profile.get("nickname")).casefold()
    url_key = str(profile.get("url") or "").casefold()
    candidate_rank = min(
        candidate_order.get(url_key, 999),
        candidate_order.get(username_key, 999),
        candidate_order.get(handle_key, 999),
    )
    subscriber_count = safe_int(profile.get("followerCount"))
    discovery_rank = 1 if profile.get("discovery") else 0
    if query_key and query_key in {username_key, handle_key}:
        relation_rank = 0
    elif query_key and (username_key.startswith(query_key) or handle_key.startswith(query_key)):
        relation_rank = 1
    elif query_key and (query_key in username_key or query_key in handle_key or query_key in nickname_key):
        relation_rank = 2
    else:
        relation_rank = 3
    return (relation_rank, discovery_rank, candidate_rank, -subscriber_count, username_key or nickname_key)


def get_hlx_youtube_search_payload(
    query: str,
    *,
    limit: int = 0,
    result_limit: int = HLX_YOUTUBE_SEARCH_DEFAULT_RESULTS,
    refresh: bool = False,
) -> dict:
    started_at = time.time()
    result_limit = max(1, min(12, safe_int(result_limit, HLX_YOUTUBE_SEARCH_DEFAULT_RESULTS)))
    discovery_limit = max(result_limit * 3, min(24, HLX_YOUTUBE_SEARCH_MAX_CANDIDATES))
    discovered_profiles, discovery_errors = discover_youtube_channels(query, limit=discovery_limit, refresh=refresh)

    candidates = youtube_channel_candidates(query)
    seen_candidates = {candidate.casefold() for candidate in candidates}
    for profile in discovered_profiles:
        for value in (profile.get("url"), profile.get("handle"), profile.get("id")):
            clean = normalize_youtube_channel_url(value)
            key = clean.casefold()
            if clean and key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(clean)
                break
        if len(candidates) >= max(1, min(24, HLX_YOUTUBE_SEARCH_MAX_CANDIDATES)):
            break
    if not candidates:
        raise ValueError("Enter a YouTube channel handle or URL.")

    results: list[dict] = []
    errors: list[dict] = list(discovery_errors)
    seen_results: set[str] = set()
    for profile in discovered_profiles[:result_limit]:
        upsert_youtube_profile(results, seen_results, profile)

    workers = max(1, min(HLX_YOUTUBE_SEARCH_MAX_WORKERS, len(candidates)))
    budget_seconds = max(1.5, min(18.0, HLX_YOUTUBE_SEARCH_BUDGET_SECONDS))
    loop_started = time.monotonic()
    deadline = loop_started + budget_seconds
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    futures: dict[concurrent.futures.Future, str] = {
        executor.submit(fetch_hlx_youtube_channel, candidate, limit=limit, refresh=refresh): candidate
        for candidate in candidates
    }
    pending = set(futures)
    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = concurrent.futures.wait(
                pending,
                timeout=min(0.35, remaining),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            min_fast_wait = min(0.55, budget_seconds)
            if not done:
                if len(results) >= result_limit and time.monotonic() >= loop_started + min_fast_wait:
                    break
                continue
            for future in done:
                candidate = futures[future]
                try:
                    profile_payload = future.result()
                    profile = profile_payload.get("profile")
                    if not isinstance(profile, dict):
                        continue
                    upsert_youtube_profile(results, seen_results, profile)
                except Exception as error:
                    errors.append({"url": candidate, "message": str(error)})
            if len(results) >= result_limit and time.monotonic() >= loop_started + min_fast_wait:
                break
    finally:
        for future in pending:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)

    for profile in discovered_profiles:
        if len(results) >= result_limit:
            break
        upsert_youtube_profile(results, seen_results, profile)

    partial = bool(pending) or any(profile.get("discovery") for profile in results)
    candidate_order = {candidate.casefold(): index for index, candidate in enumerate(candidates)}
    for index, candidate in enumerate(candidates):
        handle = youtube_handle_from_url(candidate)
        if handle:
            candidate_order.setdefault(normalize_youtube_identifier(handle).casefold(), index)
            candidate_order.setdefault(f"@{normalize_youtube_identifier(handle)}".casefold(), index)
    for index, profile in enumerate(discovered_profiles):
        for key in youtube_profile_keys(profile):
            candidate_order.setdefault(key, index)
    results.sort(key=lambda item: score_hlx_youtube_search_result(item, query, candidate_order))
    return {
        "success": True,
        "sourceUrl": f"{HLX_API_BASE_URL}/youtube/channel",
        "query": query,
        "candidates": candidates,
        "results": results[:result_limit],
        "discovered": len(discovered_profiles),
        "errors": errors[:4],
        "partial": partial,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }


def get_hlx_youtube_channel_payload(
    value: str,
    *,
    limit: int = 12,
    refresh: bool = False,
) -> dict:
    return fetch_hlx_youtube_channel(value, limit=limit, refresh=refresh)


def build_my_resources_stats(items: list[dict]) -> dict:
    categories: dict[str, int] = {}
    editors: dict[str, int] = {}
    downloads = 0
    views = 0
    premium = 0
    protected = 0

    for item in items:
        category = item.get("category") or "Uncategorized"
        editor = item.get("editorName") or "Unknown"
        categories[category] = categories.get(category, 0) + 1
        editors[editor] = editors.get(editor, 0) + 1
        downloads += safe_int(item.get("downloadCount"))
        views += safe_int(item.get("viewCount"))
        premium += 1 if item.get("isPremium") else 0
        protected += 1 if item.get("isProtected") else 0

    def top_counts(values: dict[str, int]) -> list[dict]:
        return [
            {"name": name, "count": count}
            for name, count in sorted(values.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[:8]
        ]

    return {
        "total": len(items),
        "downloads": downloads,
        "views": views,
        "premium": premium,
        "protected": protected,
        "latestAt": items[0].get("leakedAt") if items else "",
        "categories": top_counts(categories),
        "editors": top_counts(editors),
    }


def get_my_resources_payload(*, refresh: bool = False) -> dict:
    now = time.time()
    uploader = current_resources_uploader()
    uploader_id = str(uploader.get("id") or "").strip()
    uploader_aliases = tuple(uploader.get("aliases") or ())
    uploader_cache_key = f"{uploader_id}|{','.join(uploader_aliases)}"
    with MY_RESOURCES_LOCK:
        cached_entry = MY_RESOURCES_CACHE.get(uploader_cache_key) or {}
        cached_payload = cached_entry.get("payload")
        if not refresh and cached_payload and float(cached_entry.get("expiresAt") or 0) > now:
            payload = dict(cached_payload)
            payload["cached"] = True
            return payload

    started_at = time.time()
    first_page = fetch_resources_page(1, skip_metadata=False)
    pagination = first_page.get("pagination") if isinstance(first_page.get("pagination"), dict) else {}
    total_pages = max(1, safe_int(pagination.get("totalPages"), 1))
    total_pages = min(total_pages, MY_RESOURCES_MAX_PAGES)

    raw_items: list[dict] = []
    if isinstance(first_page.get("items"), list):
        raw_items.extend(item for item in first_page["items"] if isinstance(item, dict))

    if total_pages > 1:
        workers = min(8, total_pages - 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(fetch_resources_page, page, skip_metadata=True): page
                for page in range(2, total_pages + 1)
            }
            for future in concurrent.futures.as_completed(futures):
                page_payload = future.result()
                page_items = page_payload.get("items")
                if isinstance(page_items, list):
                    raw_items.extend(item for item in page_items if isinstance(item, dict))

    seen_ids: set[int] = set()
    items: list[dict] = []
    for item in raw_items:
        if not resource_matches_uploader(item, uploader_id, uploader_aliases):
            continue
        clean_item = sanitize_my_resource_item(item)
        resource_id = clean_item.get("id")
        if resource_id in seen_ids:
            continue
        seen_ids.add(resource_id)
        items.append(clean_item)

    items.sort(key=lambda item: str(item.get("leakedAt") or ""), reverse=True)
    payload = {
        "success": True,
        "sourceUrl": RESOURCES_API_URL,
        "profileUrl": RESOURCES_URL,
        "uploader": {
            "id": uploader_id,
            "aliases": list(uploader_aliases),
            "displayName": str(uploader.get("displayName") or "username"),
        },
        "items": items,
        "stats": build_my_resources_stats(items),
        "scanned": {
            "pages": total_pages,
            "items": len(raw_items),
            "apiTotal": safe_int(pagination.get("total")),
            "apiTotalPages": safe_int(pagination.get("totalPages")),
        },
        "cached": False,
        "durationMs": max(0, round((time.time() - started_at) * 1000)),
        "updatedAt": int(time.time() * 1000),
    }

    with MY_RESOURCES_LOCK:
        MY_RESOURCES_CACHE[uploader_cache_key] = {
            "payload": payload,
            "expiresAt": time.time() + MY_RESOURCES_CACHE_SECONDS,
        }
    return dict(payload)


def is_leaker_proxy_path(path: str) -> bool:
    clean_path = str(path or "")
    if clean_path == LEAKER_PROXY_PREFIX or clean_path.startswith(f"{LEAKER_PROXY_PREFIX}/"):
        return True
    if clean_path.startswith("/_next/") or clean_path.startswith("/cdn-cgi/"):
        return True
    if clean_path.startswith("/api/"):
        return True
    for prefix in (
        "/dashboard",
        "/requests",
        "/resources",
        "/auth",
        "/login",
        "/signin",
        "/password",
        "/membership",
        "/verify",
        "/favicon",
    ):
        if clean_path == prefix or clean_path.startswith(f"{prefix}/"):
            return True
    return False


def is_leaker_site_root_request(parsed: urllib.parse.SplitResult, headers=None) -> bool:
    if parsed.path != "/":
        return False
    params = urllib.parse.parse_qs(parsed.query or "", keep_blank_values=True)
    if "callbackUrl" in params or "_rsc" in params:
        return True

    referer = ""
    try:
        referer = str(headers.get("Referer", "") if headers is not None else "")
    except Exception:
        referer = ""
    if not referer:
        return False

    try:
        ref = urllib.parse.urlsplit(referer)
    except ValueError:
        return False

    ref_host = ref.netloc.lower().split("@")[-1].split(":")[0]
    if ref_host not in {"127.0.0.1", "localhost"}:
        return False

    ref_path = ref.path or "/"
    return is_leaker_proxy_path(ref_path) or ref_path == LEAKER_OAUTH_BRIDGE_PATH


def leaker_upstream_path(path: str) -> str:
    clean_path = str(path or "/")
    if clean_path == LEAKER_PROXY_PREFIX:
        return "/"
    if clean_path.startswith(f"{LEAKER_PROXY_PREFIX}/"):
        return clean_path[len(LEAKER_PROXY_PREFIX) :] or "/"
    return clean_path or "/"


def leaker_proxy_location(location: str) -> str:
    raw = str(location or "").strip()
    if not raw:
        return raw
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        parsed = None
    if parsed and parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower().split("@")[-1].split(":")[0]
        if parsed.scheme in {"http", "https"} and host == "6ureleaks.com":
            path = parsed.path or "/"
            query = f"?{parsed.query}" if parsed.query else ""
            fragment = f"#{parsed.fragment}" if parsed.fragment else ""
            return f"{path}{query}{fragment}"
        return raw
    if raw.startswith("/"):
        return raw
    return raw


def is_discord_oauth_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
    except ValueError:
        return False
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    path = parsed.path.lower()
    return (
        parsed.scheme == "https"
        and host in DISCORD_OAUTH_HOSTS
        and (path == "/oauth2/authorize" or path == "/api/oauth2/authorize")
    )


def normalize_discord_oauth_url(url: str) -> str:
    clean_url = html.unescape(str(url or "").strip())
    clean_url = clean_url.replace("\\/", "/")
    clean_url = re.sub(r"\\u0026", "&", clean_url, flags=re.IGNORECASE)
    clean_url = re.sub(r"\\u003d", "=", clean_url, flags=re.IGNORECASE)
    clean_url = re.sub(r"\\u003f", "?", clean_url, flags=re.IGNORECASE)
    clean_url = re.sub(r"\\u002f", "/", clean_url, flags=re.IGNORECASE)
    return clean_url.rstrip("\\")


def leaker_discord_oauth_bridge_url(url: str) -> str:
    clean_url = normalize_discord_oauth_url(url)
    return f"{LEAKER_OAUTH_BRIDGE_PATH}?url={urllib.parse.quote(clean_url, safe='')}"


def rewrite_discord_oauth_urls(text: str) -> str:
    if not text or "discord" not in text.lower():
        return text

    pattern = re.compile(
        r"""https:(?://|\\/\\/)(?:(?:canary|ptb)\.)?(?:discord\.com|discordapp\.com)(?:/|\\/)(?:api(?:/|\\/))?oauth2(?:/|\\/)authorize[^\s"'<>)]*""",
        flags=re.IGNORECASE,
    )

    def replace(match: re.Match) -> str:
        raw_url = match.group(0)
        clean_url = normalize_discord_oauth_url(raw_url)
        if not is_discord_oauth_url(clean_url):
            return raw_url
        return leaker_discord_oauth_bridge_url(clean_url)

    return pattern.sub(replace, text)


def leaker_discord_oauth_bridge_script() -> str:
    return r"""<script>
(() => {
  const DISCORD_OAUTH_RE = /^https:\/\/(?:(?:canary|ptb)\.)?(?:discord\.com|discordapp\.com)\/(?:api\/)?oauth2\/authorize\b/i;
  const LOCAL_BRIDGE_RE = /^(?:https?:\/\/[^/]+)?\/leaker-oauth\/bridge\b/i;

  function resolveDiscordOAuthUrl(url) {
    const cleanUrl = String(url || '');
    if (DISCORD_OAUTH_RE.test(cleanUrl)) return cleanUrl;
    if (!LOCAL_BRIDGE_RE.test(cleanUrl)) return '';
    try {
      const parsed = new URL(cleanUrl, window.location.origin);
      const oauthUrl = parsed.searchParams.get('url') || '';
      return DISCORD_OAUTH_RE.test(oauthUrl) ? oauthUrl : '';
    } catch {
      return '';
    }
  }

  function notifyDiscordOAuth(url) {
    const cleanUrl = resolveDiscordOAuthUrl(url);
    if (!cleanUrl) return false;
    try {
      window.parent.postMessage({ type: '6ure-discord-oauth', url: cleanUrl }, window.location.origin);
    } catch {}
    return true;
  }

  document.addEventListener('click', event => {
    const link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!link || !notifyDiscordOAuth(link.href)) return;
    event.preventDefault();
    event.stopPropagation();
  }, true);

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!form || !notifyDiscordOAuth(form.action)) return;
    event.preventDefault();
    event.stopPropagation();
  }, true);

  const originalOpen = window.open;
  window.open = function(url, target, features) {
    if (notifyDiscordOAuth(url)) return null;
    return originalOpen ? originalOpen.apply(window, arguments) : null;
  };
})();
</script>"""


def inject_leaker_discord_oauth_bridge(text: str) -> str:
    if not text:
        return text
    script = leaker_discord_oauth_bridge_script()
    if "6ure-discord-oauth" in text:
        return text
    if re.search(r"</body\s*>", text, flags=re.IGNORECASE):
        return re.sub(r"</body\s*>", script + r"</body>", text, count=1, flags=re.IGNORECASE)
    return text + script


def leaker_discord_oauth_bridge_html(url: str) -> str:
    safe_url = json.dumps(str(url or ""))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Discord OAuth</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      background: #080910;
      color: #f7f5ff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      display: grid;
      place-items: center;
      padding: 24px;
      text-align: center;
    }}
    main {{
      display: grid;
      gap: 10px;
      max-width: 420px;
    }}
    strong {{ font-size: 17px; font-weight: 950; }}
    span {{ color: #a4a0c5; font-size: 13px; font-weight: 800; line-height: 1.45; }}
  </style>
</head>
<body>
  <main>
    <strong>Discord OAuth is opening.</strong>
    <span>Complete Discord login in the separate window. Leaker Mode will continue here automatically.</span>
  </main>
  <script>
    const oauthUrl = {safe_url};
    function notifyParent() {{
      try {{
        window.parent.postMessage({{ type: '6ure-discord-oauth', url: oauthUrl }}, window.location.origin);
      }} catch {{}}
    }}
    notifyParent();
    setTimeout(notifyParent, 300);
    setTimeout(notifyParent, 900);
  </script>
</body>
</html>"""


def cookie_expiry_timestamp(value) -> int | None:
    if value in (None, "", False):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    try:
        parsed = email.utils.parsedate_to_datetime(str(value))
        return int(parsed.timestamp())
    except Exception:
        return None


def iter_webview_cookie_records(cookies):
    if not cookies:
        return
    if isinstance(cookies, http.cookies.SimpleCookie):
        for morsel in cookies.values():
            yield {
                "name": morsel.key,
                "value": morsel.value,
                "domain": morsel["domain"],
                "path": morsel["path"],
                "expires": morsel["expires"],
                "secure": morsel["secure"],
            }
        return
    if isinstance(cookies, dict):
        if "name" in cookies and "value" in cookies:
            yield cookies
            return
        for name, value in cookies.items():
            if isinstance(value, dict):
                record = dict(value)
                record.setdefault("name", name)
                yield record
            else:
                yield {"name": name, "value": value}
        return
    if isinstance(cookies, (list, tuple, set)):
        for item in cookies:
            yield from iter_webview_cookie_records(item)


def sync_leaker_proxy_cookies_from_webview(cookies) -> int:
    synced = 0
    with LEAKER_PROXY_LOCK:
        for record in iter_webview_cookie_records(cookies):
            name = str(record.get("name", "") or "").strip()
            value = str(record.get("value", "") or "")
            if not name:
                continue
            domain = str(record.get("domain", "") or "").strip().lower()
            if domain.startswith("."):
                clean_domain = domain[1:]
            else:
                clean_domain = domain
            if clean_domain and clean_domain != "6ureleaks.com" and not clean_domain.endswith(".6ureleaks.com"):
                continue
            domain = domain or ".6ureleaks.com"
            path = str(record.get("path", "") or "/").strip() or "/"
            secure = bool(record.get("secure", True))
            kwargs = {"domain": domain, "path": path, "secure": secure}
            expires = cookie_expiry_timestamp(record.get("expires"))
            if expires:
                kwargs["expires"] = expires
            cookie = requests.cookies.create_cookie(name=name, value=value, **kwargs)
            LEAKER_PROXY_SESSION.cookies.set_cookie(cookie)
            synced += 1
        consent_synced = ensure_leaker_cookie_consent(save=False)
        if synced or consent_synced:
            try:
                LEAKER_PROXY_SESSION.cookies.save(ignore_discard=True, ignore_expires=True)
            except Exception:
                pass
    return synced


def rewrite_leaker_proxy_text(text: str) -> str:
    if not text:
        return text

    rewritten = rewrite_discord_oauth_urls(text)
    rewritten = re.sub(
        r"""(?i)https?://6ureleaks\.com(?P<path>/[^\s"'`<>)]*)?""",
        lambda match: match.group("path") or "/",
        rewritten,
    )

    return rewritten


def should_rewrite_leaker_content(content_type: str) -> bool:
    clean_type = str(content_type or "").lower()
    return (
        clean_type.startswith("text/")
        or "javascript" in clean_type
        or "application/json" in clean_type
    )


def should_rewrite_leaker_page(content_type: str, upstream_path: str) -> bool:
    return False


class FilesAutomationError(Exception):
    pass


class FilesDuplicateLeakError(FilesAutomationError):
    def __init__(self, remote_path: str) -> None:
        clean_remote_path = str(remote_path or "").strip().lstrip("/")
        self.remote_path = clean_remote_path
        super().__init__(f"This leak is available in cloud already: {clean_remote_path}")


class FilesProtectedNameError(FilesAutomationError):
    def __init__(self, matches: list[dict]) -> None:
        self.matches = matches
        names = ", ".join(
            f"{item.get('candidateName')} -> {item.get('protectedName')}"
            for item in matches[:5]
            if item.get("candidateName") and item.get("protectedName")
        )
        suffix = f": {names}" if names else "."
        super().__init__(f"Protected name detected{suffix}")


class FilesUploadCancelledError(FilesAutomationError):
    def __init__(self) -> None:
        super().__init__("Upload was cancelled by the user.")


def normalize_protected_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = text.lstrip("@")
    return "".join(char for char in text if char.isalnum())


def protected_name_tokens(value: str) -> set[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return {normalize_protected_key(token) for token in re.split(r"[^\w@]+", text) if normalize_protected_key(token)}


def add_protected_alias(aliases: list[str], value: str) -> None:
    text = str(value or "").strip()
    if not text:
        return
    candidates = [text]
    if text.startswith("@"):
        candidates.append(text[1:])
    for candidate in candidates:
        key = normalize_protected_key(candidate)
        if key and key not in {normalize_protected_key(alias) for alias in aliases}:
            aliases.append(candidate.strip())


def extract_social_aliases(social_link: str) -> list[str]:
    aliases: list[str] = []
    link = str(social_link or "").strip()
    if not link:
        return aliases
    try:
        parsed = urllib.parse.urlsplit(link)
    except ValueError:
        return aliases
    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part.strip()]
    for part in path_parts:
        clean = part.strip()
        if clean.startswith("@"):
            add_protected_alias(aliases, clean)
        elif parsed.netloc.lower().endswith("youtube.com") and clean.startswith("@"):
            add_protected_alias(aliases, clean)
    return aliases


def protected_text_value(item: dict, field: str) -> str:
    return str(item.get(field, "") or "").strip()


def clean_protected_image_url(value: str) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    nested_index = url.find("https://", len("https://"))
    if nested_index > 0:
        url = url[nested_index:]
    url = re.sub(
        r"(\.(?:png|jpe?g|webp|gif))\?size=\d+\.(?:png|jpe?g|webp|gif)\?size=(\d+)",
        r"\1?size=\2",
        url,
        flags=re.IGNORECASE,
    )
    return url


def protected_public_record(item: dict) -> dict:
    clean: dict = {}
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    if "avatar" in clean:
        clean["avatar"] = clean_protected_image_url(str(clean.get("avatar") or ""))
    if "creatorAvatar" in clean:
        clean["creatorAvatar"] = clean_protected_image_url(str(clean.get("creatorAvatar") or ""))
    return clean


def fetch_protected_users() -> list[dict]:
    try:
        response = requests.get(
            PROTECTED_LIST_API_URL,
            timeout=30,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": PROTECTED_LIST_PAGE_URL,
                "User-Agent": "6ure App protected-check",
            },
        )
    except requests.RequestException as error:
        raise FilesAutomationError("Protected list could not be loaded from 6ureleaks.com.") from error
    if response.status_code != 200:
        raise FilesAutomationError(f"Protected list returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as error:
        raise FilesAutomationError("Protected list is not valid JSON.") from error
    if isinstance(payload, dict) and isinstance(payload.get("value"), list):
        payload = payload["value"]
    if not isinstance(payload, list):
        raise FilesAutomationError("Protected list response is invalid.")
    return [item for item in payload if isinstance(item, dict)]


def normalize_protected_user(item: dict) -> dict:
    aliases: list[str] = []
    for field in ("username", "displayName", "creatorName"):
        add_protected_alias(aliases, str(item.get(field, "") or ""))
    for alias in extract_social_aliases(str(item.get("socialLink", "") or "")):
        add_protected_alias(aliases, alias)
    name = (
        str(item.get("creatorName", "") or "").strip()
        or str(item.get("displayName", "") or "").strip()
        or str(item.get("username", "") or "").strip()
        or (aliases[0] if aliases else "Unknown")
    )
    raw = protected_public_record(item)
    return {
        "name": name,
        "userId": protected_text_value(item, "userId"),
        "username": protected_text_value(item, "username"),
        "avatar": clean_protected_image_url(protected_text_value(item, "avatar")),
        "avatarDecoration": protected_text_value(item, "avatar_decoration"),
        "displayName": protected_text_value(item, "displayName"),
        "subscriptionEndsAt": protected_text_value(item, "subscriptionEndsAt"),
        "subscriptionEndsAtManual": protected_text_value(item, "subscriptionEndsAtManual"),
        "subscriptionDateSource": protected_text_value(item, "subscriptionDateSource"),
        "migratedLpSubscriber": bool(item.get("migratedLpSubscriber", False)),
        "socialLink": protected_text_value(item, "socialLink"),
        "creatorName": protected_text_value(item, "creatorName"),
        "creatorAvatar": clean_protected_image_url(protected_text_value(item, "creatorAvatar")),
        "creatorPlatform": protected_text_value(item, "creatorPlatform"),
        "followerCount": item.get("followerCount"),
        "videoCount": item.get("videoCount"),
        "likesCount": item.get("likesCount"),
        "verified": item.get("verified"),
        "creatorBio": protected_text_value(item, "creatorBio"),
        "creatorBioLink": protected_text_value(item, "creatorBioLink"),
        "aliases": aliases,
        "raw": raw,
    }


def get_protected_list_payload() -> dict:
    users = [normalize_protected_user(item) for item in fetch_protected_users()]
    users = [item for item in users if item["aliases"]]
    return {
        "sourceUrl": PROTECTED_LIST_PAGE_URL,
        "apiUrl": PROTECTED_LIST_API_URL,
        "checkedAt": int(time.time() * 1000),
        "count": len(users),
        "users": users,
    }


def protected_alias_matches(candidate_name: str, alias: str) -> bool:
    candidate_key = normalize_protected_key(candidate_name)
    alias_key = normalize_protected_key(alias)
    if not candidate_key or not alias_key:
        return False
    if candidate_key == alias_key:
        return True
    tokens = protected_name_tokens(candidate_name)
    if len(alias_key) >= 3 and alias_key in tokens:
        return True
    return len(alias_key) >= 4 and alias_key in candidate_key


def check_protected_names(candidate_names: list[str]) -> dict:
    protected_payload = get_protected_list_payload()
    clean_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for name in candidate_names:
        clean_name = str(name or "").strip()
        key = clean_name.casefold()
        if clean_name and key not in seen_candidates:
            seen_candidates.add(key)
            clean_candidates.append(clean_name)

    matches: list[dict] = []
    seen_matches: set[tuple[str, str, str]] = set()
    for candidate in clean_candidates:
        for user in protected_payload["users"]:
            for alias in user.get("aliases", []):
                if not protected_alias_matches(candidate, alias):
                    continue
                key = (candidate.casefold(), str(user.get("name", "")).casefold(), str(alias).casefold())
                if key in seen_matches:
                    continue
                seen_matches.add(key)
                matches.append(
                    {
                        "candidateName": candidate,
                        "protectedName": user.get("name", ""),
                        "matchedAlias": alias,
                        "userId": user.get("userId", ""),
                        "username": user.get("username", ""),
                        "displayName": user.get("displayName", ""),
                        "avatar": user.get("avatar", ""),
                        "creatorName": user.get("creatorName", ""),
                        "creatorAvatar": user.get("creatorAvatar", ""),
                        "creatorPlatform": user.get("creatorPlatform", ""),
                        "socialLink": user.get("socialLink", ""),
                        "subscriptionEndsAt": user.get("subscriptionEndsAt", ""),
                        "user": user,
                    }
                )
                break

    return {
        "sourceUrl": protected_payload["sourceUrl"],
        "checkedAt": protected_payload["checkedAt"],
        "protectedCount": protected_payload["count"],
        "checkedNames": clean_candidates,
        "matches": matches,
        "blocked": bool(matches),
    }


def protected_match_label(match: dict) -> str:
    label = (
        str(match.get("creatorName", "") or "").strip()
        or str(match.get("displayName", "") or "").strip()
        or str(match.get("username", "") or "").strip()
        or str(match.get("protectedName", "") or "").strip()
        or str(match.get("matchedAlias", "") or "").strip()
        or "This creator"
    )
    if label != "This creator" and not label.startswith("@"):
        creator_platform = str(match.get("creatorPlatform", "") or "").strip().lower()
        if creator_platform in {"tiktok", "instagram", "youtube", "twitter", "x"}:
            label = "@" + label
    return label


def protected_publish_warning(matches: list[dict]) -> str:
    labels: list[str] = []
    seen: set[str] = set()
    for match in matches:
        label = protected_match_label(match)
        key = label.casefold()
        if label and key not in seen:
            seen.add(key)
            labels.append(label)
    if not labels:
        return "A protected creator was detected. You can't post this leak to 6ureleaks.com/resources."
    if len(labels) == 1:
        return f"{labels[0]} is protected. You can't post this leak to 6ureleaks.com/resources."
    return f"{', '.join(labels[:4])} are protected. You can't post this leak to 6ureleaks.com/resources."


def unique_config_paths(candidates: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            key = os.path.normcase(str(path.expanduser().resolve()))
        except OSError:
            key = os.path.normcase(str(path.expanduser()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def discord_presence_config_paths() -> list[Path]:
    candidates = [
        ROOT / DISCORD_PRESENCE_CONFIG_FILE_NAME,
        APP_ROOT / DISCORD_PRESENCE_CONFIG_FILE_NAME,
        DATA_ROOT / DISCORD_PRESENCE_CONFIG_FILE_NAME,
    ]
    configured_path = str(os.environ.get("REYLI_DISCORD_PRESENCE_CONFIG_PATH", "") or "").strip()
    if configured_path:
        candidates.append(Path(configured_path))
    return unique_config_paths(candidates)


def start_discord_presence() -> DiscordPresenceManager:
    global DISCORD_PRESENCE
    with DISCORD_PRESENCE_LOCK:
        if DISCORD_PRESENCE is None:
            config = load_presence_config(discord_presence_config_paths())
            DISCORD_PRESENCE = DiscordPresenceManager(config)
            DISCORD_PRESENCE.start()
        return DISCORD_PRESENCE


def stop_discord_presence() -> None:
    global DISCORD_PRESENCE
    with DISCORD_PRESENCE_LOCK:
        manager = DISCORD_PRESENCE
        DISCORD_PRESENCE = None
    if manager is not None:
        manager.shutdown()


def set_discord_presence_activity(
    *,
    details: str | None = None,
    state: str | None = None,
    small_image: str | None = None,
    small_text: str | None = None,
) -> dict:
    manager = start_discord_presence()
    return manager.set_activity(details=details, state=state, small_image=small_image, small_text=small_text)


def get_discord_presence_status() -> dict:
    return start_discord_presence().status()


def refresh_discord_presence_from_session() -> None:
    session = get_session_snapshot()
    if session["authenticated"]:
        set_discord_presence_activity(details="6ure workspace", state="Ready")
    else:
        set_discord_presence_activity(details="6ure App", state="Signed out")


def update_config_paths() -> list[Path]:
    candidates = [ROOT / UPDATE_CONFIG_FILE_NAME, APP_ROOT / UPDATE_CONFIG_FILE_NAME, DATA_ROOT / UPDATE_CONFIG_FILE_NAME]
    return unique_config_paths(candidates)


atexit.register(stop_discord_presence)



def load_update_config() -> dict:
    config: dict = {}
    for path in update_config_paths():
        payload = read_state_file(path)
        if isinstance(payload, dict):
            config.update(payload)

    env_manifest_url = str(os.environ.get("REYLI_UPDATE_MANIFEST_URL", "") or "").strip()
    if env_manifest_url:
        config["manifestUrl"] = env_manifest_url
    env_releases_url = str(os.environ.get("REYLI_GITHUB_RELEASES_URL", "") or "").strip()
    if env_releases_url:
        config["githubReleasesUrl"] = env_releases_url
    env_channel = str(os.environ.get("REYLI_UPDATE_CHANNEL", "") or "").strip()
    if env_channel:
        config["channel"] = env_channel
    return config


def github_repo_from_url(url: str) -> tuple[str, str] | None:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if host in {"github.com", "www.github.com"} and len(parts) >= 2:
        return parts[0], parts[1]
    if host == "api.github.com" and len(parts) >= 4 and parts[0] == "repos":
        return parts[1], parts[2]
    return None


def github_latest_manifest_url(url: str) -> str:
    repo = github_repo_from_url(url)
    if not repo:
        return ""
    owner, repo_name = repo
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if host not in {"github.com", "www.github.com"}:
        return ""
    if len(parts) >= 3 and parts[2] == "releases":
        return f"https://github.com/{owner}/{repo_name}/releases/latest/download/latest.json"
    return ""


def get_update_manifest_url(config: dict | None = None) -> str:
    current = config if isinstance(config, dict) else load_update_config()
    configured_url = str(current.get("manifestUrl") or current.get("manifest_url") or "").strip()
    github_manifest_url = github_latest_manifest_url(configured_url)
    if github_manifest_url and not configured_url.lower().endswith(".json"):
        return github_manifest_url
    if configured_url:
        return configured_url
    releases_url = str(
        current.get("githubReleasesUrl")
        or current.get("github_releases_url")
        or current.get("releasesUrl")
        or current.get("releases_url")
        or ""
    ).strip()
    return github_latest_manifest_url(releases_url) or releases_url


def github_release_api_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if host == "api.github.com" and len(parts) >= 4 and parts[0] == "repos" and parts[3] == "releases":
        return urllib.parse.urlunsplit(parsed._replace(query="", fragment=""))
    repo = github_repo_from_url(url)
    if not repo:
        return ""
    owner, repo_name = repo
    if host in {"github.com", "www.github.com"} and len(parts) >= 5 and parts[2] == "releases" and parts[3] == "tag":
        tag = urllib.parse.quote(parts[4], safe="")
        return f"https://api.github.com/repos/{owner}/{repo_name}/releases/tags/{tag}"
    if host in {"github.com", "www.github.com"} and len(parts) >= 3 and parts[2] == "releases":
        return f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
    return ""


def allow_insecure_update_url(config: dict | None = None) -> bool:
    current = config if isinstance(config, dict) else load_update_config()
    return bool(current.get("allowInsecure") or current.get("allow_insecure")) or os.environ.get(
        "REYLI_ALLOW_INSECURE_UPDATES"
    ) == "1"


def ensure_update_url_allowed(url: str, config: dict | None = None) -> None:
    parsed = urllib.parse.urlsplit(str(url or "").strip())
    if parsed.scheme == "https":
        return
    if allow_insecure_update_url(config) and parsed.scheme in {"http", "file"}:
        return
    raise FilesAutomationError("Update URLs must use HTTPS.")


def file_url_to_path(url: str) -> Path:
    parsed = urllib.parse.urlsplit(url)
    raw_path = urllib.parse.unquote(parsed.path or "")
    if os.name == "nt" and re.match(r"^/[A-Za-z]:", raw_path):
        raw_path = raw_path[1:]
    return Path(raw_path)


def update_request_headers(accept: str = "application/json") -> dict[str, str]:
    headers = {
        "Cache-Control": "no-cache",
        "User-Agent": f"6ure-app-updater/{APP_VERSION}",
    }
    if accept:
        headers["Accept"] = accept
    return headers


def clean_github_asset_sha256(asset: dict) -> str:
    digest = str(asset.get("digest") or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    return digest if re.fullmatch(r"[a-f0-9]{64}", digest) else ""


def github_asset_download_url(asset: dict) -> str:
    return str(asset.get("browser_download_url") or "").strip()


def package_type_from_asset_name(name: str) -> str:
    lower_name = str(name or "").lower()
    if lower_name.endswith((".exe", ".msi")):
        return "installer"
    if lower_name.endswith(".dmg"):
        return "dmg"
    if lower_name.endswith((".tar.gz", ".tgz")):
        return "tar.gz"
    if lower_name.endswith(".zip"):
        return "zip"
    if lower_name.endswith(".appimage"):
        return "appimage"
    if lower_name.endswith(".deb"):
        return "deb"
    if lower_name.endswith(".rpm"):
        return "rpm"
    return "package"


def read_github_checksums(release: dict) -> dict[str, str]:
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    checksum_asset = next(
        (asset for asset in assets if isinstance(asset, dict) and str(asset.get("name") or "").lower() == "checksums.txt"),
        None,
    )
    checksum_url = github_asset_download_url(checksum_asset or {})
    if not checksum_url:
        return {}
    try:
        response = requests.get(checksum_url, timeout=30, headers=update_request_headers("text/plain"))
        if response.status_code != 200:
            return {}
    except requests.RequestException:
        return {}

    checksums: dict[str, str] = {}
    for line in response.text.splitlines():
        match = re.match(r"^\s*([a-fA-F0-9]{64})\s+\*?(.+?)\s*$", line)
        if not match:
            continue
        name = posixpath.basename(match.group(2).replace("\\", "/")).lower()
        if name:
            checksums[name] = match.group(1).lower()
    return checksums


def find_release_asset(assets: list, *predicates) -> dict | None:
    for predicate in predicates:
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "").lower()
            if name and predicate(name):
                return asset
    return None


def github_release_asset_payload(asset: dict | None, checksums: dict[str, str]) -> dict | None:
    if not isinstance(asset, dict):
        return None
    name = str(asset.get("name") or "").strip()
    url = github_asset_download_url(asset)
    if not name or not url:
        return None
    size = asset.get("size")
    payload: dict = {
        "url": url,
        "sha256": clean_github_asset_sha256(asset) or checksums.get(name.lower(), ""),
        "packageType": package_type_from_asset_name(name),
    }
    if isinstance(size, int) and size >= 0:
        payload["sizeBytes"] = size
    if payload["packageType"] == "installer":
        payload["installerArgs"] = "/S"
        payload["successExitCodes"] = [0, 3010]
    return payload


def github_release_to_update_manifest(release: dict, config: dict) -> dict:
    if not isinstance(release, dict):
        raise FilesAutomationError("GitHub release payload is invalid.")
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    latest_asset = find_release_asset(assets, lambda name: name == "latest.json")
    latest_url = github_asset_download_url(latest_asset or {})
    if latest_url:
        try:
            return read_http_update_json(latest_url, config, allow_github_fallback=False)
        except Exception:
            pass

    tag_name = str(release.get("tag_name") or "").strip()
    version = tag_name.lstrip("v") or parse_version_from_release_name(str(release.get("name") or ""))
    if not version:
        raise FilesAutomationError("GitHub release is missing a version.")

    checksums = read_github_checksums(release)
    windows_asset = find_release_asset(
        assets,
        lambda name: "windows" in name and "setup" in name and name.endswith(".exe"),
        lambda name: "win" in name and "setup" in name and name.endswith(".exe"),
        lambda name: "windows" in name and name.endswith(".exe"),
        lambda name: "windows" in name and name.endswith(".zip"),
        lambda name: "win" in name and name.endswith(".zip"),
    )
    macos_asset = find_release_asset(
        assets,
        lambda name: ("macos" in name or "darwin" in name or "osx" in name) and name.endswith(".dmg"),
        lambda name: ("macos" in name or "darwin" in name or "osx" in name) and name.endswith(".zip"),
    )
    linux_asset = find_release_asset(
        assets,
        lambda name: "linux" in name and name.endswith((".tar.gz", ".tgz")),
        lambda name: "linux" in name and name.endswith(".appimage"),
        lambda name: "linux" in name and name.endswith((".deb", ".rpm", ".zip")),
    )

    manifest: dict = {
        "version": version,
        "notes": str(release.get("body") or release.get("name") or "").strip(),
    }
    for key, asset in (("windows", windows_asset), ("macos", macos_asset), ("linux", linux_asset)):
        payload = github_release_asset_payload(asset, checksums)
        if payload:
            manifest[key] = payload
    return manifest


def parse_version_from_release_name(name: str) -> str:
    match = re.search(r"\bv?(\d+(?:\.\d+){1,3})\b", str(name or ""), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def read_github_release_json(api_url: str, config: dict) -> dict:
    ensure_update_url_allowed(api_url, config)
    response = requests.get(api_url, timeout=30, headers=update_request_headers("application/vnd.github+json"))
    if response.status_code != 200:
        raise FilesAutomationError(f"GitHub release returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as error:
        raise FilesAutomationError("GitHub release did not return valid JSON.") from error
    return github_release_to_update_manifest(payload, config)


def read_http_update_json(url: str, config: dict, *, allow_github_fallback: bool = True) -> dict:
    api_url = github_release_api_url(url)
    parsed = urllib.parse.urlsplit(url)
    release_page_request = bool(
        api_url
        and parsed.netloc.lower() in {"github.com", "www.github.com"}
        and parsed.path.rstrip("/").endswith("/releases")
    )
    if release_page_request:
        return read_github_release_json(api_url, config)

    response = requests.get(url, timeout=30, headers=update_request_headers())
    if response.status_code != 200:
        if allow_github_fallback and api_url:
            return read_github_release_json(api_url, config)
        raise FilesAutomationError(f"Update manifest returned HTTP {response.status_code}.")
    try:
        payload = response.json()
    except ValueError as error:
        if allow_github_fallback and api_url:
            return read_github_release_json(api_url, config)
        raise FilesAutomationError("Update manifest is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise FilesAutomationError("Update manifest is invalid.")
    if "tag_name" in payload and isinstance(payload.get("assets"), list):
        return github_release_to_update_manifest(payload, config)
    return payload


def read_update_json(url: str, config: dict) -> dict:
    ensure_update_url_allowed(url, config)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "file":
        payload = read_state_file(file_url_to_path(url))
        if not isinstance(payload, dict):
            raise FilesAutomationError("Update manifest is invalid.")
        return payload
    return read_http_update_json(url, config)


def parse_version(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().lower().lstrip("v")
    parts = re.split(r"[^0-9]+", text)
    numbers = [int(part) for part in parts if part != ""]
    return tuple(numbers or [0])


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    candidate_parts = list(parse_version(candidate))
    current_parts = list(parse_version(current))
    length = max(len(candidate_parts), len(current_parts))
    candidate_parts.extend([0] * (length - len(candidate_parts)))
    current_parts.extend([0] * (length - len(current_parts)))
    return tuple(candidate_parts) > tuple(current_parts)


def current_update_platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def update_platform_label(platform_key: str) -> str:
    labels = {
        "windows": "Windows",
        "macos": "macOS",
        "linux": "Linux",
    }
    return labels.get(str(platform_key or "").lower(), str(platform_key or "").strip() or "Platform")


def payload_package_type(payload: dict) -> str:
    package_url = str(payload.get("url") or "").strip()
    package_type = str(payload.get("packageType") or payload.get("type") or "").strip().lower()
    if package_type:
        return package_type
    return package_type_from_asset_name(urllib.parse.urlsplit(package_url).path)


def is_windows_setup_payload(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    package_type = payload_package_type(payload)
    package_url = str(payload.get("url") or "").strip().lower()
    return package_type in {"installer", "setup", "exe", "msi"} or package_url.endswith((".exe", ".msi"))


def merge_update_payload_defaults(parent: dict, child: dict) -> dict:
    merged = {
        key: value
        for key, value in parent.items()
        if key not in {"setup", "installer", "exe", "msi", "zip", "portable", "archive"}
    }
    merged.update(child)
    return merged


def select_platform_update_payload(manifest: dict, platform_key: str) -> dict:
    platform_payload = manifest.get(platform_key)
    if not isinstance(platform_payload, dict) and platform_key == "macos":
        platform_payload = manifest.get("darwin")

    if platform_key == "windows":
        top_level_setup_keys = ("windowsSetup", "windowsInstaller", "winSetup", "winInstaller")
        for key in top_level_setup_keys:
            payload = manifest.get(key)
            if isinstance(payload, dict) and is_windows_setup_payload(payload):
                return payload

        if isinstance(platform_payload, dict):
            for key in ("setup", "installer", "exe", "msi"):
                payload = platform_payload.get(key)
                if isinstance(payload, dict) and is_windows_setup_payload(payload):
                    return merge_update_payload_defaults(platform_payload, payload)
            if is_windows_setup_payload(platform_payload):
                return platform_payload
            for key in ("zip", "portable", "archive"):
                payload = platform_payload.get(key)
                if isinstance(payload, dict):
                    return merge_update_payload_defaults(platform_payload, payload)

    if isinstance(platform_payload, dict):
        return platform_payload

    has_platform_payloads = any(
        isinstance(manifest.get(key), dict) for key in ("windows", "windowsSetup", "windowsInstaller", "macos", "darwin", "linux")
    )
    if has_platform_payloads:
        return {}
    package_payload = manifest.get("package")
    return package_payload if isinstance(package_payload, dict) else manifest


def normalize_update_manifest(manifest: dict, manifest_url: str) -> dict:
    platform_key = current_update_platform_key()
    platform_payload = select_platform_update_payload(manifest, platform_key)

    version = str(platform_payload.get("version") or manifest.get("version") or "").strip().lstrip("v")
    package_url = str(platform_payload.get("url") or manifest.get("url") or "").strip()
    sha256 = str(platform_payload.get("sha256") or manifest.get("sha256") or "").strip().lower()
    notes = str(platform_payload.get("notes") or manifest.get("notes") or "").strip()
    mandatory = bool(platform_payload.get("mandatory") or manifest.get("mandatory"))
    size_bytes = platform_payload.get("sizeBytes", manifest.get("sizeBytes"))
    package_type = str(
        platform_payload.get("packageType") or platform_payload.get("type") or manifest.get("packageType") or ""
    ).strip().lower()
    package_url = urllib.parse.urljoin(manifest_url, package_url) if package_url else ""
    package_path = urllib.parse.urlsplit(package_url).path.lower() if package_url else ""
    known_package_types = {"zip", "installer", "dmg", "tar.gz", "tgz", "appimage", "deb", "rpm"}
    if package_type not in known_package_types:
        if package_path.endswith((".exe", ".msi")):
            package_type = "installer"
        elif package_path.endswith(".dmg"):
            package_type = "dmg"
        elif package_path.endswith((".tar.gz", ".tgz")):
            package_type = "tar.gz"
        elif package_path.endswith(".appimage"):
            package_type = "appimage"
        elif package_path.endswith(".deb"):
            package_type = "deb"
        elif package_path.endswith(".rpm"):
            package_type = "rpm"
        else:
            package_type = "zip"

    installer_args = platform_payload.get("installerArgs", manifest.get("installerArgs", ""))
    if isinstance(installer_args, list):
        clean_installer_args = [str(item) for item in installer_args if str(item).strip()]
    else:
        clean_installer_args = str(installer_args or "").strip()

    success_exit_codes = platform_payload.get("successExitCodes", manifest.get("successExitCodes"))
    if isinstance(success_exit_codes, list):
        clean_success_exit_codes = []
        for code in success_exit_codes:
            try:
                clean_success_exit_codes.append(int(code))
            except (TypeError, ValueError):
                continue
        if not clean_success_exit_codes:
            clean_success_exit_codes = [0, 3010]
    else:
        clean_success_exit_codes = [0, 3010]

    if not version:
        raise FilesAutomationError("Update manifest is missing a version.")
    update_available = is_newer_version(version)
    if update_available:
        if not package_url:
            raise FilesAutomationError(f"Update manifest is missing a {update_platform_label(platform_key)} package URL.")
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise FilesAutomationError("Update manifest is missing a valid SHA-256 checksum.")

    package_name = posixpath.basename(urllib.parse.urlsplit(package_url).path) if package_url else ""
    install_mode = "automatic" if platform_key == "windows" and package_type == "installer" else "manual"

    return {
        "version": version,
        "url": package_url,
        "sha256": sha256,
        "notes": notes,
        "mandatory": mandatory,
        "packageType": package_type,
        "installerArgs": clean_installer_args,
        "successExitCodes": clean_success_exit_codes,
        "sizeBytes": size_bytes if isinstance(size_bytes, int) and size_bytes >= 0 else None,
        "platform": platform_key,
        "platformLabel": update_platform_label(platform_key),
        "packageName": urllib.parse.unquote(package_name),
        "installMode": install_mode,
        "updateAvailable": update_available,
    }


def check_for_update() -> dict:
    config = load_update_config()
    manifest_url = get_update_manifest_url(config)
    if not manifest_url:
        result = {
            "configured": False,
            "currentVersion": APP_VERSION,
            "updateAvailable": False,
            "msg": "Update manifest URL is not configured.",
        }
        with UPDATE_STATE_LOCK:
            UPDATE_STATE["lastCheckAt"] = int(time.time() * 1000)
            UPDATE_STATE["latest"] = None
            UPDATE_STATE["lastError"] = ""
        return result

    with UPDATE_STATE_LOCK:
        if UPDATE_STATE["checking"]:
            raise FilesAutomationError("Update check is already running.")
        UPDATE_STATE["checking"] = True
        UPDATE_STATE["lastError"] = ""

    try:
        manifest = read_update_json(manifest_url, config)
        latest = normalize_update_manifest(manifest, manifest_url)
        result = {
            "configured": True,
            "currentVersion": APP_VERSION,
            "latest": latest,
            "updateAvailable": bool(latest["updateAvailable"]),
            "msg": "Update available." if latest["updateAvailable"] else "You are on the latest version.",
        }
        with UPDATE_STATE_LOCK:
            UPDATE_STATE["lastCheckAt"] = int(time.time() * 1000)
            UPDATE_STATE["latest"] = latest
        return result
    except Exception as error:
        with UPDATE_STATE_LOCK:
            UPDATE_STATE["lastError"] = str(error)
        raise
    finally:
        with UPDATE_STATE_LOCK:
            UPDATE_STATE["checking"] = False


def get_update_status() -> dict:
    config = load_update_config()
    with UPDATE_STATE_LOCK:
        latest = UPDATE_STATE["latest"]
        return {
            "configured": bool(get_update_manifest_url(config)),
            "currentVersion": APP_VERSION,
            "checking": bool(UPDATE_STATE["checking"]),
            "installing": bool(UPDATE_STATE["installing"]),
            "lastCheckAt": UPDATE_STATE["lastCheckAt"],
            "lastError": UPDATE_STATE["lastError"],
            "latest": latest,
            "updateAvailable": bool(isinstance(latest, dict) and latest.get("updateAvailable")),
            "installPhase": UPDATE_STATE["installPhase"],
            "installMessage": UPDATE_STATE["installMessage"],
            "downloadedBytes": UPDATE_STATE["downloadedBytes"],
            "totalBytes": UPDATE_STATE["totalBytes"],
            "installProgress": UPDATE_STATE["installProgress"],
            "installStartedAt": UPDATE_STATE["installStartedAt"],
            "installUpdatedAt": UPDATE_STATE["installUpdatedAt"],
        }


def set_update_install_status(
    phase: str,
    message: str,
    *,
    downloaded_bytes: int | None = None,
    total_bytes: int | None = None,
    progress: int | None = None,
) -> None:
    with UPDATE_STATE_LOCK:
        UPDATE_STATE["installPhase"] = str(phase or "")
        UPDATE_STATE["installMessage"] = str(message or "")
        if downloaded_bytes is not None:
            UPDATE_STATE["downloadedBytes"] = max(0, int(downloaded_bytes))
        if total_bytes is not None:
            UPDATE_STATE["totalBytes"] = max(0, int(total_bytes)) if int(total_bytes) >= 0 else None
        if progress is not None:
            UPDATE_STATE["installProgress"] = max(0, min(100, int(progress)))
        UPDATE_STATE["installUpdatedAt"] = int(time.time() * 1000)


def reset_update_install_status() -> None:
    with UPDATE_STATE_LOCK:
        UPDATE_STATE["installPhase"] = ""
        UPDATE_STATE["installMessage"] = ""
        UPDATE_STATE["downloadedBytes"] = 0
        UPDATE_STATE["totalBytes"] = None
        UPDATE_STATE["installProgress"] = 0
        UPDATE_STATE["installStartedAt"] = int(time.time() * 1000)
        UPDATE_STATE["installUpdatedAt"] = UPDATE_STATE["installStartedAt"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update_package(update_info: dict) -> Path:
    package_url = str(update_info.get("url", "") or "").strip()
    expected_sha256 = str(update_info.get("sha256", "") or "").strip().lower()
    ensure_update_url_allowed(package_url, load_update_config())

    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    version = re.sub(r"[^A-Za-z0-9._-]+", "-", str(update_info.get("version", "update") or "update"))
    package_type = str(update_info.get("packageType") or "").strip().lower()
    url_path = urllib.parse.urlsplit(package_url).path.lower()
    if package_type == "installer":
        extension = ".msi" if url_path.endswith(".msi") else ".exe"
    else:
        extension = ".zip"
    package_path = UPDATE_DOWNLOAD_DIR / f"6ure-app-{version}{extension}"
    temp_path = UPDATE_DOWNLOAD_DIR / f"{package_path.name}.tmp"
    downloaded = 0
    declared_size = update_info.get("sizeBytes")
    total_bytes = int(declared_size) if isinstance(declared_size, int) and declared_size >= 0 else None
    set_update_install_status(
        "download",
        f"Preparing download for v{update_info.get('version', '')}.",
        downloaded_bytes=0,
        total_bytes=total_bytes if total_bytes is not None else -1,
        progress=8,
    )

    parsed = urllib.parse.urlsplit(package_url)
    if parsed.scheme == "file":
        source_path = file_url_to_path(package_url)
        shutil.copyfile(source_path, temp_path)
        downloaded = temp_path.stat().st_size
        set_update_install_status(
            "download",
            "Copied local update package.",
            downloaded_bytes=downloaded,
            total_bytes=downloaded,
            progress=70,
        )
    else:
        with requests.get(package_url, timeout=60, stream=True) as response:
            if response.status_code != 200:
                raise FilesAutomationError(f"Update package returned HTTP {response.status_code}.")
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                total_bytes = int(content_length)
                set_update_install_status(
                    "download",
                    "Downloading update package.",
                    downloaded_bytes=0,
                    total_bytes=total_bytes,
                    progress=10,
                )
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > UPDATE_MAX_PACKAGE_BYTES:
                        raise FilesAutomationError("Update package is larger than the configured safety limit.")
                    handle.write(chunk)
                    if total_bytes and total_bytes > 0:
                        download_progress = 10 + round((downloaded / total_bytes) * 60)
                    else:
                        download_progress = 20
                    set_update_install_status(
                        "download",
                        "Downloading update package.",
                        downloaded_bytes=downloaded,
                        total_bytes=total_bytes if total_bytes is not None else -1,
                        progress=min(70, download_progress),
                    )

    set_update_install_status(
        "verify",
        "Verifying update checksum.",
        downloaded_bytes=downloaded,
        total_bytes=total_bytes if total_bytes is not None else downloaded,
        progress=76,
    )
    actual_sha256 = sha256_file(temp_path)
    if actual_sha256.lower() != expected_sha256:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise FilesAutomationError("Update package checksum did not match the manifest.")

    os.replace(temp_path, package_path)
    set_update_install_status("ready", "Update package verified.", downloaded_bytes=downloaded, total_bytes=downloaded, progress=88)
    return package_path


def ps_single_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def ps_array(values: list[str | int]) -> str:
    if not values:
        return "@()"
    return "@(" + ", ".join(ps_single_quote(str(value)) for value in values) + ")"


def write_windows_zip_update_script(package_path: Path) -> Path:
    if not sys.platform.startswith("win"):
        raise FilesAutomationError("Automatic update install is currently supported on Windows only.")
    if not getattr(sys, "frozen", False):
        raise FilesAutomationError("Automatic update install is only available in the packaged app.")

    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    script_path = UPDATE_DOWNLOAD_DIR / "apply-6ure-app-update.ps1"
    exe_name = Path(sys.executable).name
    app_dir = APP_ROOT.resolve()
    exe_path = Path(sys.executable).resolve()
    backup_root = UPDATE_BACKUP_DIR.resolve()

    script = f"""
$ErrorActionPreference = "Stop"
$appDir = {ps_single_quote(str(app_dir))}
$zipPath = {ps_single_quote(str(package_path.resolve()))}
$backupRoot = {ps_single_quote(str(backup_root))}
$exeName = {ps_single_quote(exe_name)}
$exePath = {ps_single_quote(str(exe_path))}
$pidToWait = {os.getpid()}
$logPath = Join-Path $backupRoot "last-update.log"

function Write-UpdateLog {{
  param([string]$Message)
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $logPath -Value "$stamp $Message"
}}

function Invoke-Retry {{
  param([scriptblock]$Action, [string]$Label)
  $lastError = $null
  for ($i = 1; $i -le 25; $i++) {{
    try {{
      & $Action
      return
    }} catch {{
      $lastError = $_
      Start-Sleep -Milliseconds 700
    }}
  }}
  throw "$Label failed: $lastError"
}}

try {{
  New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
  Write-UpdateLog "Waiting for process $pidToWait"
  try {{
    Wait-Process -Id $pidToWait -Timeout 90
  }} catch {{
    Start-Sleep -Seconds 3
  }}
  Start-Sleep -Milliseconds 900

  $stamp = Get-Date -Format "yyyyMMddHHmmss"
  $extractDir = Join-Path (Split-Path -Parent $zipPath) "payload-$stamp"
  $backupDir = Join-Path $backupRoot "backup-$stamp"
  New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
  New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

  Write-UpdateLog "Extracting $zipPath"
  Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force
  $payloadDir = $extractDir
  if (-not (Test-Path -LiteralPath (Join-Path $payloadDir $exeName))) {{
    $dirs = @(Get-ChildItem -LiteralPath $extractDir -Directory -Force)
    if ($dirs.Count -eq 1 -and (Test-Path -LiteralPath (Join-Path $dirs[0].FullName $exeName))) {{
      $payloadDir = $dirs[0].FullName
    }}
  }}
  if (-not (Test-Path -LiteralPath (Join-Path $payloadDir $exeName))) {{
    throw "Update package does not contain $exeName."
  }}

  Write-UpdateLog "Backing up $appDir"
  Get-ChildItem -LiteralPath $appDir -Force | Where-Object {{ $_.Name -ne "update-config.json" }} | ForEach-Object {{
    Copy-Item -LiteralPath $_.FullName -Destination $backupDir -Recurse -Force
  }}

  Write-UpdateLog "Removing old app files"
  Invoke-Retry -Label "Remove old app files" -Action {{
    Get-ChildItem -LiteralPath $appDir -Force | Where-Object {{ $_.Name -ne "update-config.json" }} | Remove-Item -Recurse -Force
  }}

  Write-UpdateLog "Copying new app files"
  Invoke-Retry -Label "Copy new app files" -Action {{
    Get-ChildItem -LiteralPath $payloadDir -Force | Where-Object {{ $_.Name -ne "update-config.json" }} | Copy-Item -Destination $appDir -Recurse -Force
  }}

  $targetConfig = Join-Path $appDir "update-config.json"
  $payloadConfig = Join-Path $payloadDir "update-config.json"
  if (-not (Test-Path -LiteralPath $targetConfig) -and (Test-Path -LiteralPath $payloadConfig)) {{
    Copy-Item -LiteralPath $payloadConfig -Destination $targetConfig -Force
  }}

  Write-UpdateLog "Starting updated app"
  Start-Process -FilePath (Join-Path $appDir $exeName) -WorkingDirectory $appDir
  Start-Sleep -Seconds 2
  Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
  Write-UpdateLog "Update completed"
}} catch {{
  Write-UpdateLog ("Update failed: " + $_)
  try {{
    if ((Test-Path -LiteralPath $backupDir) -and (Test-Path -LiteralPath $appDir)) {{
      Get-ChildItem -LiteralPath $backupDir -Force | Copy-Item -Destination $appDir -Recurse -Force -ErrorAction SilentlyContinue
    }}
  }} catch {{}}
  if (Test-Path -LiteralPath $exePath) {{
    Start-Process -FilePath $exePath -WorkingDirectory $appDir
  }}
  exit 1
}}
""".strip()
    script_path.write_text(script, encoding="utf-8")
    return script_path


def write_windows_installer_update_script(package_path: Path, update_info: dict) -> Path:
    if not sys.platform.startswith("win"):
        raise FilesAutomationError("Automatic update install is currently supported on Windows only.")
    if not getattr(sys, "frozen", False):
        raise FilesAutomationError("Automatic update install is only available in the packaged app.")

    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    script_path = UPDATE_DOWNLOAD_DIR / "run-6ure-app-installer-update.ps1"
    app_dir = APP_ROOT.resolve()
    exe_path = Path(sys.executable).resolve()
    backup_root = UPDATE_BACKUP_DIR.resolve()
    installer_args = update_info.get("installerArgs", "")
    if isinstance(installer_args, list):
        installer_arg_items = [str(item) for item in installer_args if str(item).strip()]
    elif str(installer_args or "").strip():
        installer_arg_items = [str(installer_args).strip()]
    else:
        installer_arg_items = []
    success_codes = update_info.get("successExitCodes")
    if not isinstance(success_codes, list):
        success_codes = [0, 3010]
    clean_success_codes: list[int] = []
    for code in success_codes:
        try:
            clean_success_codes.append(int(code))
        except (TypeError, ValueError):
            continue
    if not clean_success_codes:
        clean_success_codes = [0, 3010]

    script = f"""
$ErrorActionPreference = "Stop"
$appDir = {ps_single_quote(str(app_dir))}
$installerPath = {ps_single_quote(str(package_path.resolve()))}
$exePath = {ps_single_quote(str(exe_path))}
$backupRoot = {ps_single_quote(str(backup_root))}
$installerArgs = {ps_array(installer_arg_items)}
$successExitCodes = @({", ".join(str(code) for code in clean_success_codes)})
$pidToWait = {os.getpid()}
$logPath = Join-Path $backupRoot "last-update.log"

function Write-UpdateLog {{
  param([string]$Message)
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $logPath -Value "$stamp $Message"
}}

try {{
  New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
  Write-UpdateLog "Waiting for process $pidToWait"
  try {{
    Wait-Process -Id $pidToWait -Timeout 90
  }} catch {{
    Start-Sleep -Seconds 3
  }}
  Start-Sleep -Milliseconds 900

  Write-UpdateLog "Running installer $installerPath"
  if ($installerArgs.Count -gt 0) {{
    $proc = Start-Process -FilePath $installerPath -ArgumentList $installerArgs -Wait -PassThru
  }} else {{
    $proc = Start-Process -FilePath $installerPath -Wait -PassThru
  }}
  if ($null -ne $proc -and $successExitCodes -notcontains $proc.ExitCode) {{
    throw "Installer exited with code $($proc.ExitCode)."
  }}

  if (Test-Path -LiteralPath $exePath) {{
    Write-UpdateLog "Starting updated app"
    Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath)
  }}
  Write-UpdateLog "Installer update completed"
}} catch {{
  Write-UpdateLog ("Installer update failed: " + $_)
  if (Test-Path -LiteralPath $exePath) {{
    Start-Process -FilePath $exePath -WorkingDirectory (Split-Path -Parent $exePath)
  }}
  exit 1
}}
""".strip()
    script_path.write_text(script, encoding="utf-8")
    return script_path


def launch_windows_update_installer(package_path: Path, update_info: dict) -> None:
    package_type = str(update_info.get("packageType") or "").strip().lower()
    script_path = (
        write_windows_installer_update_script(package_path, update_info)
        if package_type == "installer"
        else write_windows_zip_update_script(package_path)
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        cwd=str(APP_ROOT),
        close_fds=True,
        creationflags=creationflags,
    )


def open_update_download(update_info: dict) -> None:
    package_url = str(update_info.get("url", "") or "").strip()
    if not package_url:
        raise FilesAutomationError("Update package URL is missing.")
    ensure_update_url_allowed(package_url, load_update_config())
    if not webbrowser.open(package_url):
        raise FilesAutomationError("Update download could not be opened.")


def prepare_update_install() -> dict:
    with UPDATE_STATE_LOCK:
        if UPDATE_STATE["installing"]:
            raise FilesAutomationError("Update install is already running.")
        UPDATE_STATE["installing"] = True
        latest = UPDATE_STATE["latest"]
    reset_update_install_status()

    try:
        if not isinstance(latest, dict) or not latest.get("updateAvailable"):
            set_update_install_status("check", "Checking latest update manifest.", progress=3)
            latest_result = check_for_update()
            latest = latest_result.get("latest")
        if not isinstance(latest, dict) or not latest.get("updateAvailable"):
            raise FilesAutomationError("No update is available.")

        auto_install_supported = sys.platform.startswith("win") and getattr(sys, "frozen", False)
        if str(latest.get("installMode") or "").lower() == "manual" or not auto_install_supported:
            platform_label = str(latest.get("platformLabel") or update_platform_label(latest.get("platform", ""))).strip()
            set_update_install_status("manual", f"Opening {platform_label} update download.", progress=100)
            open_update_download(latest)
            return {
                "currentVersion": APP_VERSION,
                "latest": latest,
                "downloadUrl": str(latest.get("url", "") or ""),
                "manualDownload": True,
                "restarting": False,
            }

        set_update_install_status("download", f"Starting update v{latest.get('version', '')}.", progress=6)
        package_path = download_update_package(latest)
        set_update_install_status("launch", "Launching installer and closing app.", progress=94)
        launch_windows_update_installer(package_path, latest)
        set_update_install_status("handoff", "Installer launched. The app will close now.", progress=100)
        return {
            "currentVersion": APP_VERSION,
            "latest": latest,
            "packagePath": str(package_path),
            "manualDownload": False,
            "restarting": True,
        }
    except Exception as error:
        with UPDATE_STATE_LOCK:
            UPDATE_STATE["lastError"] = str(error)
        set_update_install_status("error", str(error), progress=0)
        raise
    finally:
        with UPDATE_STATE_LOCK:
            if UPDATE_STATE["installPhase"] not in {"handoff", "launch"}:
                UPDATE_STATE["installing"] = False


def migrate_credentials_to_vault() -> list[str]:
    actions: list[str] = []
    if not get_app_setting("encryptedVault"):
        return actions
    state = load_persisted_state()
    files_state = state.setdefault("files", {})
    username = str(files_state.get("username") or "").strip()
    password = str(files_state.get("password") or "")
    if username and password:
        save_vault_credentials(username, password)
        files_state.pop("password", None)
        save_persisted_state(state)
        actions.append("Moved saved cloud credentials into the encrypted vault.")
    return actions


def ensure_update_config_repair() -> list[str]:
    actions: list[str] = []
    config = load_update_config()
    if get_update_manifest_url(config):
        return actions
    default_config = {
        "manifestUrl": "https://thejinx1.github.io/6ure-App/latest.json",
        "githubReleasesUrl": "https://github.com/thejinx1/6ure-App/releases",
        "channel": "stable",
        "allowInsecure": False,
    }
    target_path = DATA_ROOT / UPDATE_CONFIG_FILE_NAME
    target_path.write_text(json.dumps(default_config, ensure_ascii=False, indent=2), encoding="utf-8")
    actions.append("Restored the GitHub Pages update channel.")
    return actions


def repair_persisted_state_files() -> list[str]:
    actions: list[str] = []
    if CONFIG_TMP_PATH.exists():
        try:
            CONFIG_TMP_PATH.unlink()
            actions.append("Removed a stale state temp file.")
        except OSError:
            pass

    current = read_state_file(CONFIG_PATH)
    backup = read_state_file(CONFIG_BACKUP_PATH)
    if current is None and CONFIG_PATH.exists() and backup is not None:
        CONFIG_PATH.write_text(json.dumps(sanitize_persisted_state(backup), ensure_ascii=False, indent=2), encoding="utf-8")
        actions.append("Restored app state from backup.")
    elif current is None and not CONFIG_PATH.exists():
        save_persisted_state({"files": {}})
        actions.append("Created a fresh app state file.")
    elif current is not None and not CONFIG_BACKUP_PATH.exists():
        CONFIG_BACKUP_PATH.write_text(json.dumps(sanitize_persisted_state(current), ensure_ascii=False, indent=2), encoding="utf-8")
        actions.append("Recreated the state backup file.")
    return actions


def cleanup_stale_update_files() -> list[str]:
    actions: list[str] = []
    if not UPDATE_DOWNLOAD_DIR.exists():
        return actions
    cutoff = time.time() - 24 * 60 * 60
    removed = 0
    for path in UPDATE_DOWNLOAD_DIR.glob("*.tmp"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        actions.append(f"Removed {removed} stale update temp file(s).")
    return actions


def write_repair_log(source: str, actions: list[str]) -> dict:
    payload = {
        "source": str(source or "manual"),
        "ranAt": int(time.time() * 1000),
        "actions": actions,
    }
    REPAIR_LOG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    settings = load_app_settings()
    settings["lastRepairAt"] = payload["ranAt"]
    settings["lastRepairActions"] = actions
    settings["lastRepairSource"] = payload["source"]
    save_app_settings(settings)
    return payload


def run_silent_repair(source: str = "manual") -> dict:
    actions: list[str] = []
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    if not APP_SETTINGS_PATH.exists():
        save_app_settings(load_app_settings())
        actions.append("Created maintenance settings.")
    actions.extend(repair_persisted_state_files())
    actions.extend(ensure_update_config_repair())
    actions.extend(migrate_credentials_to_vault())
    actions.extend(cleanup_stale_update_files())
    ensure_leaker_cookie_consent(save=True)
    log_payload = write_repair_log(source, actions)
    return {
        "success": True,
        "source": log_payload["source"],
        "ranAt": log_payload["ranAt"],
        "actions": actions,
        "changed": bool(actions),
    }


def disable_encrypted_vault() -> None:
    username, password = load_vault_credentials()
    if username and password:
        state = load_persisted_state()
        files_state = state.setdefault("files", {})
        files_state["username"] = username
        files_state["password"] = password
        save_persisted_state(state)
    clear_vault_credentials()


def update_security_settings(payload: dict) -> dict:
    settings = load_app_settings()
    previous_vault = bool_setting(settings.get("encryptedVault"), True)
    for key in ("encryptedVault", "silentRepairMode"):
        if key in payload:
            settings[key] = bool_setting(payload.get(key), DEFAULT_APP_SETTINGS[key])
    settings = save_app_settings(settings)
    current_vault = bool_setting(settings.get("encryptedVault"), True)
    actions: list[str] = []
    if current_vault and not previous_vault:
        actions.extend(migrate_credentials_to_vault())
    elif previous_vault and not current_vault:
        disable_encrypted_vault()
        actions.append("Moved saved credentials back to app state.")
    return security_status(extra_actions=actions)


def security_status(extra_actions: list[str] | None = None) -> dict:
    settings = load_app_settings()
    repair_log = read_state_file(REPAIR_LOG_PATH) or {}
    return {
        "success": True,
        "settings": {
            "encryptedVault": bool_setting(settings.get("encryptedVault"), True),
            "silentRepairMode": bool_setting(settings.get("silentRepairMode"), True),
        },
        "vault": vault_status(),
        "repair": {
            "lastRepairAt": settings.get("lastRepairAt") or repair_log.get("ranAt") or 0,
            "lastRepairActions": settings.get("lastRepairActions") or repair_log.get("actions") or [],
            "lastRepairSource": settings.get("lastRepairSource") or repair_log.get("source") or "",
        },
        "actions": extra_actions or [],
    }


def redact_debug_value(key: str, value):
    lower_key = str(key or "").lower()
    if any(word in lower_key for word in ("password", "token", "secret", "cookie", "key")):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(item_key): redact_debug_value(str(item_key), item_value) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_debug_value(key, item) for item in value[:100]]
    return value


def sanitized_debug_state() -> dict:
    state = load_persisted_state()
    return redact_debug_value("state", state)


def file_summary(path: Path) -> dict:
    try:
        stat = path.stat()
        return {
            "exists": True,
            "path": str(path),
            "sizeBytes": stat.st_size,
            "modifiedAt": int(stat.st_mtime * 1000),
        }
    except OSError:
        return {"exists": False, "path": str(path)}


def write_debug_bundle_entry(bundle: zipfile.ZipFile, name: str, payload) -> None:
    if isinstance(payload, (dict, list)):
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = str(payload)
    bundle.writestr(name, text)


def reveal_file(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer.exe", f"/select,{str(path)}"], close_fds=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)
    except Exception:
        pass


def create_debug_bundle(*, reveal: bool = True) -> dict:
    DEBUG_BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bundle_path = DEBUG_BUNDLE_DIR / f"6ure-debug-{stamp}.zip"
    metadata = {
        "appVersion": APP_VERSION,
        "createdAt": int(time.time() * 1000),
        "platform": sys.platform,
        "python": sys.version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "root": str(ROOT),
        "appRoot": str(APP_ROOT),
        "dataRoot": str(DATA_ROOT),
    }
    paths = {
        "config": file_summary(CONFIG_PATH),
        "configBackup": file_summary(CONFIG_BACKUP_PATH),
        "updateConfig": [file_summary(path) for path in update_config_paths()],
        "presenceConfig": [file_summary(path) for path in discord_presence_config_paths()],
        "vault": file_summary(VAULT_PATH),
        "vaultKey": {"exists": VAULT_KEY_PATH.exists(), "path": str(VAULT_KEY_PATH)},
        "repairLog": file_summary(REPAIR_LOG_PATH),
    }
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        write_debug_bundle_entry(bundle, "metadata.json", metadata)
        write_debug_bundle_entry(bundle, "security-status.json", security_status())
        write_debug_bundle_entry(bundle, "state-sanitized.json", sanitized_debug_state())
        write_debug_bundle_entry(bundle, "paths.json", paths)
        write_debug_bundle_entry(bundle, "update-status.json", redact_debug_value("update", get_update_status()))
        write_debug_bundle_entry(bundle, "update-config.json", redact_debug_value("updateConfig", load_update_config()))
        repair_payload = read_state_file(REPAIR_LOG_PATH)
        if repair_payload:
            write_debug_bundle_entry(bundle, "last-repair.json", repair_payload)
        update_log = UPDATE_BACKUP_DIR / "last-update.log"
        if update_log.exists():
            try:
                bundle.write(update_log, "last-update.log")
            except OSError:
                pass
    if reveal:
        reveal_file(bundle_path)
    return {
        "success": True,
        "path": str(bundle_path),
        "fileName": bundle_path.name,
        "sizeBytes": bundle_path.stat().st_size,
        "createdAt": int(time.time() * 1000),
    }


WINDOWS_INVALID_ZIP_NAME_CHARS = set('<>:"|?*')


def zip_member_relative_path(info: zipfile.ZipInfo) -> Path | None:
    raw_name = str(info.filename or "").replace("\\", "/")
    if not raw_name:
        return None
    if raw_name.startswith("/") or re.match(r"^[A-Za-z]:", raw_name):
        raise FilesAutomationError(f"ZIP member has an unsafe path: {raw_name}")

    parts: list[str] = []
    for part in raw_name.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or "\x00" in part:
            raise FilesAutomationError(f"ZIP member has an unsafe path: {raw_name}")
        if os.name == "nt" and any(char in WINDOWS_INVALID_ZIP_NAME_CHARS for char in part):
            raise FilesAutomationError(f"ZIP member cannot be extracted on Windows: {raw_name}")
        parts.append(part)

    if not parts:
        return None
    return Path(*parts)


def path_is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def extract_zip_archive(zip_path: Path, extract_root: Path) -> tuple[list[Path], list[str], int]:
    file_paths: list[Path] = []
    dir_paths: set[str] = set()
    seen_files: set[str] = set()
    total_bytes = 0
    extract_root = extract_root.resolve()

    try:
        archive = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as error:
        raise FilesAutomationError("The selected file is not a valid ZIP archive.") from error

    with archive:
        members = archive.infolist()
        if not members:
            raise FilesAutomationError("The ZIP archive is empty.")

        for info in members:
            relative_path = zip_member_relative_path(info)
            if relative_path is None:
                continue

            relative_text = relative_path.as_posix()
            target_path = (extract_root / relative_path).resolve()
            if not path_is_within(extract_root, target_path):
                raise FilesAutomationError(f"ZIP member has an unsafe path: {info.filename}")

            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                dir_paths.add(relative_text.rstrip("/"))
                continue

            if info.flag_bits & 0x1:
                raise FilesAutomationError("Encrypted ZIP files are not supported.")

            file_key = os.path.normcase(str(relative_path))
            if file_key in seen_files:
                raise FilesAutomationError(f"ZIP archive contains duplicate file paths: {relative_text}")
            seen_files.add(file_key)

            total_bytes += max(0, int(info.file_size or 0))
            if total_bytes > FILES_EXTRACT_MAX_TOTAL_BYTES:
                raise FilesAutomationError("The ZIP archive is larger than the configured extract safety limit.")
            if len(file_paths) + 1 > FILES_EXTRACT_MAX_FILES:
                raise FilesAutomationError("The ZIP archive contains too many files to extract safely.")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            file_paths.append(target_path)

    return file_paths, sorted(dir_paths, key=lambda item: (item.count("/"), item.lower())), total_bytes


def default_extract_target_path(remote_path: str) -> str:
    source_path = normalize_remote_path(remote_path, allow_root=False)
    parent = remote_parent_path(source_path)
    name = remote_basename(source_path)
    stem = name[:-4] if name.lower().endswith(".zip") else f"{name}-extracted"
    stem = stem.strip() or "extracted"
    return remote_join(parent, normalize_remote_name(stem, "Extract folder name"))


class FilesRemoteClient:
    def __init__(self, username: str, password: str) -> None:
        self.username = str(username or "").strip()
        self.password = str(password or "")
        if not self.username or not self.password:
            raise FilesAutomationError("Sign in is required before managing cloud files.")
        self.session = requests.Session()
        self.csrf_token = ""
        self.last_action_at = 0.0

    def rate_guard(self, minimum: float = FILES_MIN_ACTION_INTERVAL) -> None:
        now = time.monotonic()
        wait_time = max(0.0, minimum - (now - self.last_action_at))
        if wait_time:
            time.sleep(wait_time)
        self.last_action_at = time.monotonic()

    @staticmethod
    def response_detail(response: requests.Response) -> str:
        text = response.text[:500].replace("\n", " ")
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            detail = str(payload.get("error") or payload.get("message") or "").strip()
            if detail:
                return detail[:500].replace("\n", " ")
        return text

    def request(
        self,
        method: str,
        url: str,
        label: str,
        expected: tuple[int, ...] = (200,),
        timeout: int = 60,
        **kwargs,
    ) -> requests.Response:
        body = kwargs.get("data")
        last_response: requests.Response | None = None
        for attempt in range(1, 5):
            self.rate_guard()
            if hasattr(body, "seek"):
                body.seek(0)
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            last_response = response
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after and retry_after.isdigit() else min(20, attempt * 3)
                time.sleep(wait_time)
                continue
            if response.status_code in expected:
                return response
            detail = self.response_detail(response)
            raise FilesAutomationError(f"{label} returned HTTP {response.status_code}: {detail}")

        status = last_response.status_code if last_response is not None else "no-response"
        raise FilesAutomationError(f"{label} failed after rate-limit retries; last status {status}.")

    def login(self) -> None:
        login_url = f"{FILES_BASE_URL}/web/client/login"
        response = self.request("GET", login_url, "load sign-in form")
        match = FORM_TOKEN_RE.search(response.text)
        if not match:
            raise FilesAutomationError("Could not find sign-in form token.")

        response = self.request(
            "POST",
            login_url,
            "sign in",
            expected=(301, 302, 303),
            data={"username": self.username, "password": self.password, "_form_token": match.group(1)},
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        if "/web/client/files" not in location:
            raise PermissionError("Wrong username or password.")

        files_page = self.request("GET", FILES_SITE_URL, "load files page")
        csrf_match = CSRF_TOKEN_RE.search(files_page.text)
        if not csrf_match:
            raise FilesAutomationError("Could not find files CSRF token.")
        self.csrf_token = csrf_match.group(1)

    def csrf_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"X-CSRF-TOKEN": self.csrf_token}
        headers.update(extra_headers or {})
        return headers

    def list_dir(self, remote_path: str) -> list[dict]:
        clean_path = normalize_remote_path(remote_path)
        response = self.request(
            "GET",
            f"{FILES_BASE_URL}/web/client/dirs?path={quote_remote_path(clean_path)}",
            f"list cloud path {clean_path}",
        )
        data = response.json()
        if not isinstance(data, list):
            raise FilesAutomationError("Cloud directory listing returned an invalid response.")
        return sort_cloud_entries([normalize_cloud_entry(clean_path, entry) for entry in data if isinstance(entry, dict)])

    def check_exists(self, parent_path: str, names: list[str]) -> list[dict]:
        response = self.request(
            "POST",
            f"{FILES_BASE_URL}/web/client/exist?op=upload&path={quote_remote_path(normalize_remote_path(parent_path))}",
            "check cloud destination",
            headers=self.csrf_headers({"Content-Type": "application/json"}),
            data=json.dumps({"files": names}),
        )
        data = response.json()
        return data if isinstance(data, list) else []

    def wait_task(self, task_id: str, label: str, timeout_seconds: int = 300) -> dict:
        clean_task_id = str(task_id or "").strip()
        if not clean_task_id:
            return {}

        deadline = time.monotonic() + timeout_seconds
        task_url = f"{FILES_BASE_URL}/web/client/tasks/{quote_remote_path(clean_task_id)}"
        while time.monotonic() < deadline:
            response = self.request(
                "GET",
                task_url,
                f"check {label} task",
                headers=self.csrf_headers(),
                timeout=30,
            )
            try:
                payload = response.json()
            except ValueError as error:
                raise FilesAutomationError(f"{label} task returned an invalid response.") from error
            task_status = int(payload.get("status", 0) or 0)
            if task_status == 200:
                return payload
            if task_status >= 400:
                raise FilesAutomationError(f"{label} task returned HTTP {task_status}.")
            time.sleep(max(0.1, FILES_TASK_POLL_INTERVAL))

        raise FilesAutomationError(f"{label} task did not finish in time.")

    def wait_task_response(self, response: requests.Response, label: str) -> dict:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        task_id = str(payload.get("message", "") or "").strip() if isinstance(payload, dict) else ""
        return self.wait_task(task_id, label)

    def move(self, source_path: str, target_path: str) -> None:
        source = normalize_remote_path(source_path, allow_root=False)
        target = normalize_remote_path(target_path, allow_root=False)
        if source == target:
            raise ValueError("Source and destination are the same.")
        response = self.request(
            "POST",
            (
                f"{FILES_BASE_URL}/web/client/file-actions/move"
                f"?path={quote_remote_path(source)}&target={quote_remote_path(target)}"
            ),
            "move cloud item",
            expected=(202,),
            headers=self.csrf_headers(),
            timeout=30,
        )
        self.wait_task_response(response, "move")

    def delete(self, remote_path: str, item_type: str) -> None:
        clean_path = normalize_remote_path(remote_path, allow_root=False)
        if is_remote_dir_type(item_type):
            response = self.request(
                "DELETE",
                f"{FILES_BASE_URL}/web/client/dirs?path={quote_remote_path(clean_path)}",
                "delete cloud folder",
                expected=(202, 404),
                headers=self.csrf_headers(),
                timeout=30,
            )
            if response.status_code == 404:
                return
            self.wait_task_response(response, "delete")
            return

        self.request(
            "DELETE",
            f"{FILES_BASE_URL}/web/client/files?path={quote_remote_path(clean_path)}",
            "delete cloud file",
            expected=(200, 404),
            headers=self.csrf_headers(),
            timeout=30,
        )

    def create_dir(self, remote_path: str, parents: bool = True, ignore_existing: bool = False) -> None:
        clean_path = normalize_remote_path(remote_path, allow_root=False)
        query = f"path={quote_remote_path(clean_path)}"
        if parents:
            query += "&mkdir_parents=true"
        response = self.request(
            "POST",
            f"{FILES_BASE_URL}/web/client/dirs?{query}",
            "create cloud folder",
            expected=(201, 409),
            headers=self.csrf_headers(),
            timeout=30,
        )
        if response.status_code == 409 and not ignore_existing:
            raise FilesAutomationError(f"Cloud folder already exists: {clean_path}")

    def download_file(self, remote_path: str, destination: Path, max_bytes: int = FILES_EXTRACT_MAX_ZIP_BYTES) -> int:
        clean_path = normalize_remote_path(remote_path, allow_root=False)
        total_bytes = 0
        url = f"{FILES_BASE_URL}/web/client/file?path={quote_remote_path(clean_path)}"
        last_status: int | str = "no-response"
        for attempt in range(1, 5):
            self.rate_guard()
            response = self.session.get(url, headers=self.csrf_headers(), timeout=300, stream=True)
            last_status = response.status_code
            if response.status_code == 429:
                response.close()
                retry_after = response.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after and retry_after.isdigit() else min(20, attempt * 3)
                time.sleep(wait_time)
                continue
            if response.status_code != 200:
                detail = self.response_detail(response)
                response.close()
                raise FilesAutomationError(f"download ZIP returned HTTP {response.status_code}: {detail}")

            with response, destination.open("wb") as target:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise FilesAutomationError("The ZIP file is larger than the configured extract safety limit.")
                    target.write(chunk)
            return total_bytes

        raise FilesAutomationError(f"download ZIP failed after rate-limit retries; last status {last_status}.")

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        clean_remote_path = normalize_remote_path(remote_path, allow_root=False)
        headers = self.csrf_headers(
            {
                "X-SFTPGO-MTIME": str(round(local_path.stat().st_mtime * 1000)),
                "Content-Type": "application/octet-stream",
            }
        )
        with local_path.open("rb") as handle:
            self.request(
                "POST",
                f"{FILES_BASE_URL}/web/client/file?path={quote_remote_path(clean_remote_path)}&mkdir_parents=true",
                f"upload extracted file {clean_remote_path}",
                expected=(201,),
                headers=headers,
                data=handle,
                timeout=300,
            )

    def extract_remote_zip(self, remote_path: str, target_path: str = "") -> dict:
        source = normalize_remote_path(remote_path, allow_root=False)
        if not remote_basename(source).lower().endswith(".zip"):
            raise ValueError("Only ZIP files can be extracted.")

        target = normalize_remote_path(target_path, "Extract target", allow_root=False) if target_path else default_extract_target_path(source)
        target_parent = remote_parent_path(target)
        target_name = normalize_remote_name(remote_basename(target), "Extract target folder name")
        target = remote_join(target_parent, target_name)

        if self.check_exists(target_parent, [target_name]):
            raise FilesAutomationError(f"The extract target already exists: {target}")

        with tempfile.TemporaryDirectory(prefix="6ure-files-extract-") as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "archive.zip"
            extract_root = temp_root / "contents"
            extract_root.mkdir(parents=True, exist_ok=True)

            downloaded_bytes = self.download_file(source, archive_path)
            file_paths, dir_paths, total_bytes = extract_zip_archive(archive_path, extract_root)

            self.create_dir(target, parents=True)
            for relative_dir in dir_paths:
                self.create_dir(remote_join(target, relative_dir), parents=True, ignore_existing=True)

            for local_file in file_paths:
                relative_path = local_file.relative_to(extract_root).as_posix()
                self.upload_file(local_file, remote_join(target, relative_path))

        return {
            "path": target,
            "files": len(file_paths),
            "folders": len(dir_paths),
            "sizeBytes": total_bytes,
            "downloadedBytes": downloaded_bytes,
        }


def get_authenticated_remote_client() -> FilesRemoteClient:
    username, password = get_session_credentials()
    if not username or not password:
        sync_session_from_state()
        username, password = get_session_credentials()
    if not username or not password:
        raise FilesAutomationError("Sign in is required before managing cloud files.")

    now = time.monotonic()
    with REMOTE_CLIENT_LOCK:
        cached_client = REMOTE_CLIENT_CACHE.get("client")
        if (
            cached_client is not None
            and REMOTE_CLIENT_CACHE.get("username") == username
            and REMOTE_CLIENT_CACHE.get("password") == password
            and float(REMOTE_CLIENT_CACHE.get("expiresAt") or 0.0) > now
        ):
            REMOTE_CLIENT_CACHE["expiresAt"] = now + REMOTE_CLIENT_TTL_SECONDS
            return cached_client

    client = FilesRemoteClient(username, password)
    client.login()
    with REMOTE_CLIENT_LOCK:
        stale_client = REMOTE_CLIENT_CACHE.get("client")
        stale_session = getattr(stale_client, "session", None)
        if stale_session is not None:
            try:
                stale_session.close()
            except Exception:
                pass
        REMOTE_CLIENT_CACHE["username"] = username
        REMOTE_CLIENT_CACHE["password"] = password
        REMOTE_CLIENT_CACHE["client"] = client
        REMOTE_CLIENT_CACHE["expiresAt"] = time.monotonic() + REMOTE_CLIENT_TTL_SECONDS
    return client


class CancellableFileReader:
    def __init__(self, handle, cancel_event: threading.Event) -> None:
        self._handle = handle
        self._cancel_event = cancel_event
        self.name = getattr(handle, "name", "")
        self.mode = getattr(handle, "mode", "rb")

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise FilesUploadCancelledError()

    def read(self, size: int = -1):
        self._check_cancelled()
        chunk = self._handle.read(size)
        self._check_cancelled()
        return chunk

    def seek(self, offset: int, whence: int = os.SEEK_SET):
        return self._handle.seek(offset, whence)

    def tell(self) -> int:
        return self._handle.tell()

    def fileno(self) -> int:
        return self._handle.fileno()


def normalize_local_folder_paths(folder_paths) -> list[Path]:
    if isinstance(folder_paths, (str, Path)):
        candidates = [folder_paths]
    elif isinstance(folder_paths, list):
        candidates = folder_paths
    else:
        candidates = []

    resolved_paths: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        path = Path(text).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Selected leak folder does not exist: {path}")
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        resolved_paths.append(path)

    if not resolved_paths:
        raise ValueError("At least one leak folder is required.")

    return resolved_paths


def get_local_folder_summary(folder_path: Path) -> dict:
    total_bytes = 0
    file_count = 0
    for item in folder_path.rglob("*"):
        try:
            if not item.is_file():
                continue
            file_count += 1
            total_bytes += item.stat().st_size
        except OSError:
            continue

    return {
        "path": str(folder_path),
        "name": folder_path.name,
        "sizeBytes": total_bytes,
        "fileCount": file_count,
    }


def get_local_folder_summaries(folder_paths) -> list[dict]:
    return [get_local_folder_summary(path) for path in normalize_local_folder_paths(folder_paths)]


def save_last_folder_selection(paths: list[Path]) -> dict:
    if not paths:
        return clear_last_files_selection()
    return save_files_state(
        lastFolderPath=str(paths[0]),
        lastFolderName=paths[0].name,
        lastFolderPaths=[str(path) for path in paths],
        lastFolderNames=[path.name for path in paths],
    )


def validate_files_credentials(username: str, password: str) -> None:
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        raise ValueError("Username and password are required.")

    session = requests.Session()
    response = session.get(f"{FILES_BASE_URL}/web/client/login", timeout=30)
    if response.status_code != 200:
        raise FilesAutomationError(f"Sign-in page returned HTTP {response.status_code}.")

    match = FORM_TOKEN_RE.search(response.text)
    if not match:
        raise FilesAutomationError("Could not find sign-in form token.")

    response = session.post(
        f"{FILES_BASE_URL}/web/client/login",
        timeout=30,
        data={"username": username, "password": password, "_form_token": match.group(1)},
        allow_redirects=False,
    )
    location = response.headers.get("Location", "")
    if response.status_code not in {301, 302, 303} or "/web/client/files" not in location:
        raise PermissionError("Wrong username or password.")

    files_page = session.get(FILES_SITE_URL, timeout=30)
    if files_page.status_code != 200:
        raise FilesAutomationError(f"Files page returned HTTP {files_page.status_code}.")
    if not CSRF_TOKEN_RE.search(files_page.text):
        raise FilesAutomationError("Could not verify the files session.")


class FilesUploadJob:
    def __init__(self, editor_name: str, folder_paths) -> None:
        self.id = uuid.uuid4().hex
        self.editor_name = normalize_remote_name(editor_name, "Editor name")
        self.folder_paths = normalize_local_folder_paths(folder_paths)
        self.folder_names: list[str] = []
        seen_folder_names: set[str] = set()
        for path in self.folder_paths:
            folder_name = normalize_remote_name(path.name, "Leak folder name")
            folder_key = folder_name.lower()
            if folder_key in seen_folder_names:
                raise ValueError("Selected leak folders must have unique folder names.")
            seen_folder_names.add(folder_key)
            self.folder_names.append(folder_name)

        self.folder_path = self.folder_paths[0]
        self.folder_name = self.folder_names[0]
        self.folder_count = len(self.folder_paths)
        self.created_at = int(time.time() * 1000)
        self.status = "queued"
        self.phase = "Queued"
        self.progress = 0
        self.total_files = 0
        self.uploaded_files = 0
        self.logs: list[str] = []
        self.technical_report = ""
        self.result_kind = ""
        self.result_paths: list[str] = []
        self.duplicate_path = ""
        self.protected_matches: list[dict] = []
        self.protected_warning = ""
        self.last_action_at = 0.0
        self.last_presence_at = 0.0
        self.last_presence_phase = ""
        self.last_presence_progress = -1
        self.last_presence_status = ""
        self.cancel_event = threading.Event()
        self.cancel_requested = False
        self.rollback_targets: list[str] = []
        self.rollback_errors: list[str] = []
        self.lock = threading.Lock()

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "id": self.id,
                "status": self.status,
                "phase": self.phase,
                "progress": self.progress,
                "totalFiles": self.total_files,
                "uploadedFiles": self.uploaded_files,
                "editorName": self.editor_name,
                "folderName": self.folder_name,
                "folderNames": list(self.folder_names),
                "folderCount": self.folder_count,
                "logs": self.logs[-80:],
                "technicalReport": self.technical_report,
                "resultKind": self.result_kind,
                "resultPaths": list(self.result_paths),
                "duplicatePath": self.duplicate_path,
                "protectedMatches": list(self.protected_matches),
                "protectedWarning": self.protected_warning,
                "cancelRequested": self.cancel_requested,
                "rollbackErrors": list(self.rollback_errors),
            }

    def set_status(self, status: str, phase: str | None = None) -> None:
        with self.lock:
            if self.cancel_requested and status in {"queued", "running"}:
                self.status = "cancelling"
                if phase:
                    self.phase = phase if phase == "Rolling back" else "Cancelling"
                presence_changed = True
            else:
                self.status = status
                if phase:
                    self.phase = phase
                presence_changed = True
        if presence_changed:
            self.update_presence(force=True)

    def set_progress(self) -> None:
        with self.lock:
            self.progress = 0 if not self.total_files else round((self.uploaded_files / self.total_files) * 100)
        self.update_presence()

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        with self.lock:
            self.logs.append(f"{timestamp} - {message}")
            self.logs = self.logs[-160:]

    def update_presence(self, force: bool = False) -> None:
        with self.lock:
            status = self.status
            phase = self.phase
            progress = self.progress
            uploaded_files = self.uploaded_files
            total_files = self.total_files
            now = time.monotonic()
            if not force:
                progress_step = progress >= self.last_presence_progress + 5
                phase_changed = phase != self.last_presence_phase or status != self.last_presence_status
                time_elapsed = now - self.last_presence_at >= 5.0
                if not phase_changed and not progress_step and not time_elapsed:
                    return
            self.last_presence_at = now
            self.last_presence_phase = phase
            self.last_presence_progress = progress
            self.last_presence_status = status

        if status in {"queued", "running"}:
            if phase == "Uploading":
                details = "Uploading leak"
                state = f"{self.editor_name} - {progress}%"
                if total_files:
                    state = f"{state} ({uploaded_files}/{total_files})"
                set_discord_presence_activity(details=details, state=state)
                return
            set_discord_presence_activity(details="Preparing upload", state=phase or "Queued")
            return

        if status == "cancelling":
            set_discord_presence_activity(details="Cancelling upload", state=phase or "Rolling back")
            return
        if status == "success":
            set_discord_presence_activity(details="Upload complete", state="Ready")
            return
        if status == "cancelled":
            set_discord_presence_activity(details="Upload cancelled", state="Ready")
            return
        if status == "failed":
            set_discord_presence_activity(details="Upload failed", state="Needs attention")

    def set_protected_warning(self, matches: list[dict], warning: str = "") -> None:
        clean_matches = [match for match in matches if isinstance(match, dict)]
        message = warning or protected_publish_warning(clean_matches)
        with self.lock:
            self.protected_matches = clean_matches
            self.protected_warning = message

    def request_cancel(self) -> None:
        with self.lock:
            if self.status in {"success", "failed", "cancelled"}:
                return
            self.cancel_requested = True
            self.status = "cancelling"
            self.phase = "Cancelling"
        self.cancel_event.set()
        self.log("Cancel requested. Rolling back this upload job.")
        self.update_presence(force=True)

    def ensure_not_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise FilesUploadCancelledError()

    def add_rollback_target(self, editor_name: str, folder_name: str) -> None:
        remote_path = "/" + "/".join(part.strip("/") for part in (editor_name, folder_name) if part)
        with self.lock:
            if remote_path not in self.rollback_targets:
                self.rollback_targets.append(remote_path)

    def fail(self, error: Exception) -> None:
        remote_folders = "\n".join(f"- /{self.editor_name}/{name}" for name in self.folder_names)
        local_folders = "\n".join(f"- {path}" for path in self.folder_paths)
        duplicate_path = error.remote_path if isinstance(error, FilesDuplicateLeakError) else ""
        protected_matches = error.matches if isinstance(error, FilesProtectedNameError) else []
        protected_report = (
            "\n".join(
                f"- {item.get('candidateName')} matched {item.get('protectedName')} via {item.get('matchedAlias')}"
                for item in protected_matches
            )
            if protected_matches
            else ""
        )
        with self.lock:
            self.status = "failed"
            self.phase = "Failed"
            self.result_kind = "duplicate" if duplicate_path else "protected" if protected_matches else "failed"
            self.duplicate_path = duplicate_path
            self.result_paths = (
                [duplicate_path]
                if duplicate_path
                else [
                    f"{item.get('candidateName')} -> {item.get('protectedName')}"
                    for item in protected_matches
                    if item.get("candidateName") and item.get("protectedName")
                ]
            )
            self.technical_report = (
                f"error_type: {type(error).__name__}\n"
                f"message: {error}\n"
                f"editor: {self.editor_name}\n"
                f"local_folders:\n{local_folders}\n"
                f"remote_folders:\n{remote_folders}\n"
                + (f"protected_matches:\n{protected_report}\n" if protected_report else "")
                + f"uploaded_files: {self.uploaded_files}/{self.total_files}\n"
            )
        self.update_presence(force=True)

    def mark_cancelled(self, rollback_errors: list[str]) -> None:
        remote_folders = "\n".join(f"- /{self.editor_name}/{name}" for name in self.folder_names)
        local_folders = "\n".join(f"- {path}" for path in self.folder_paths)
        with self.lock:
            self.rollback_errors = list(rollback_errors)
            if rollback_errors:
                self.status = "failed"
                self.phase = "Rollback failed"
                self.result_kind = "cancel_failed"
                self.technical_report = (
                    "Upload cancellation was requested, but rollback did not complete cleanly.\n"
                    f"editor: {self.editor_name}\n"
                    f"local_folders:\n{local_folders}\n"
                    f"remote_folders:\n{remote_folders}\n"
                    "rollback_errors:\n"
                    + "\n".join(f"- {error}" for error in rollback_errors)
                    + "\n"
                )
            else:
                self.status = "cancelled"
                self.phase = "Cancelled"
                self.result_kind = "cancelled"
                self.technical_report = ""
            self.result_paths = []
            self.duplicate_path = ""
        self.update_presence(force=True)

    def rate_guard(
        self,
        label: str,
        minimum: float = FILES_MIN_ACTION_INTERVAL,
        ignore_cancel: bool = False,
    ) -> None:
        now = time.monotonic()
        wait_time = max(0.0, minimum - (now - self.last_action_at))
        deadline = now + wait_time
        while time.monotonic() < deadline:
            if not ignore_cancel:
                self.ensure_not_cancelled()
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        self.last_action_at = time.monotonic()

    def request(
        self,
        session: requests.Session,
        method: str,
        url: str,
        label: str,
        expected: tuple[int, ...] = (200,),
        ignore_cancel: bool = False,
        **kwargs,
    ) -> requests.Response:
        last_response: requests.Response | None = None
        timeout = kwargs.pop("timeout", 60)
        body = kwargs.get("data")
        for attempt in range(1, 5):
            if not ignore_cancel:
                self.ensure_not_cancelled()
            self.rate_guard(label, ignore_cancel=ignore_cancel)
            if hasattr(body, "seek"):
                body.seek(0)
            try:
                response = session.request(method, url, timeout=timeout, **kwargs)
            except Exception as error:
                if not ignore_cancel and self.cancel_event.is_set():
                    raise FilesUploadCancelledError() from error
                raise
            last_response = response
            if not ignore_cancel:
                self.ensure_not_cancelled()
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after and retry_after.isdigit() else min(20, attempt * 3)
                self.log(f"Rate limited during {label}; backing off for {wait_time:.0f}s.")
                deadline = time.monotonic() + wait_time
                while time.monotonic() < deadline:
                    if not ignore_cancel:
                        self.ensure_not_cancelled()
                    time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
                continue
            if response.status_code in expected:
                return response
            detail = response.text[:500].replace("\n", " ")
            raise FilesAutomationError(f"{label} returned HTTP {response.status_code}: {detail}")

        status = last_response.status_code if last_response is not None else "no-response"
        raise FilesAutomationError(f"{label} failed after rate-limit retries; last status {status}.")

    def run(self) -> None:
        session: requests.Session | None = None
        csrf_token = ""
        try:
            self.ensure_not_cancelled()
            self.set_status("running", "Preparing")
            username, password = get_session_credentials()
            if not username or not password:
                sync_session_from_state()
                username, password = get_session_credentials()
            if not username or not password:
                raise FilesAutomationError("Sign in is required before starting an upload.")
            self.ensure_not_cancelled()

            folder_payloads: list[tuple[Path, str, list[Path]]] = []
            empty_folders: list[str] = []
            total_bytes = 0
            total_files = 0
            for folder_path, folder_name in zip(self.folder_paths, self.folder_names):
                self.ensure_not_cancelled()
                files = [path for path in folder_path.rglob("*") if path.is_file()]
                if not files:
                    empty_folders.append(folder_name)
                    continue
                folder_payloads.append((folder_path, folder_name, files))
                total_bytes += sum(path.stat().st_size for path in files)
                total_files += len(files)

            if empty_folders:
                raise FilesAutomationError(
                    "Selected leak folders do not contain uploadable files: " + ", ".join(empty_folders)
                )
            if not folder_payloads:
                raise FilesAutomationError("Selected leak folders do not contain uploadable files.")
            if total_bytes > FILES_MAX_UPLOAD_BYTES:
                raise FilesAutomationError("Selected leak folders are larger than the configured upload safety limit.")

            self.total_files = total_files
            self.set_progress()
            self.log(f"Queued {self.total_files} files from {self.folder_count} leak folders.")
            self.set_status("running", "Checking protected list")
            try:
                protected_result = check_protected_names([self.editor_name, *self.folder_names])
                self.log(f"Checked {protected_result['protectedCount']} protected names from 6ureleaks.com.")
                if protected_result["matches"]:
                    self.set_protected_warning(protected_result["matches"])
                    self.log(self.protected_warning)
            except FilesAutomationError as error:
                self.set_protected_warning(
                    [],
                    "The protected list could not be checked live. The upload will continue, but publishing should be reviewed before posting to 6ureleaks.com/resources.",
                )
                self.log(f"Protected list check warning: {error}")

            session = requests.Session()
            csrf_token = self.login(session, username, password)
            self.ensure_not_cancelled()
            editor_remote_name = self.ensure_editor_folder(session, csrf_token)
            result_paths: list[str] = []
            for folder_path, folder_name, files in folder_payloads:
                self.ensure_not_cancelled()
                self.ensure_upload_target_is_clear(session, csrf_token, editor_remote_name, folder_name)
                self.add_rollback_target(editor_remote_name, folder_name)
                self.upload_folder(session, csrf_token, editor_remote_name, folder_path, folder_name, files)
                self.ensure_not_cancelled()
                self.verify_uploaded_folder(session, editor_remote_name, folder_name)
                result_paths.append(f"{editor_remote_name}/{folder_name}")

            self.ensure_not_cancelled()
            record_upload_batch_history(editor_name=editor_remote_name, folder_paths=self.folder_paths)
            clear_last_files_selection()
            self.set_status("success", "Complete")
            with self.lock:
                self.progress = 100
                self.result_kind = "protected_warning" if self.protected_warning else "success"
                self.result_paths = result_paths
            self.duplicate_path = ""
            self.update_presence(force=True)
            if self.protected_warning:
                self.log("Upload complete. Publishing warning remains active.")
            else:
                self.log("Upload complete. Run /cloud moveall in Discord.")
        except FilesUploadCancelledError:
            self.log("Cancellation started. Removing files uploaded by this job.")
            rollback_errors: list[str] = []
            if session is not None and csrf_token:
                rollback_errors = self.rollback_upload(session, csrf_token)
            else:
                self.log("Nothing was uploaded before cancellation.")
            self.mark_cancelled(rollback_errors)
            if rollback_errors:
                self.log("Cancellation finished, but rollback reported errors.")
            else:
                self.log("Upload cancelled and rolled back.")
        except Exception as error:
            self.log(f"Failed: {error}")
            self.fail(error)

    def login(self, session: requests.Session, username: str, password: str) -> str:
        self.set_status("running", "Signing in")
        login_url = f"{FILES_BASE_URL}/web/client/login"
        response = self.request(session, "GET", login_url, "load sign-in form")
        match = FORM_TOKEN_RE.search(response.text)
        if not match:
            raise FilesAutomationError("Could not find sign-in form token.")

        response = self.request(
            session,
            "POST",
            login_url,
            "sign in",
            expected=(302,),
            data={"username": username, "password": password, "_form_token": match.group(1)},
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        if "/web/client/files" not in location:
            raise FilesAutomationError("Sign-in did not redirect to the files page.")

        files_page = self.request(session, "GET", FILES_SITE_URL, "load files page")
        csrf_match = CSRF_TOKEN_RE.search(files_page.text)
        if not csrf_match:
            raise FilesAutomationError("Could not find files CSRF token.")
        self.log("Authenticated with files.6ureleaks.com.")
        return csrf_match.group(1)

    def list_dirs(
        self,
        session: requests.Session,
        path: str,
        label: str,
        ignore_cancel: bool = False,
    ) -> list[dict]:
        response = self.request(
            session,
            "GET",
            f"{FILES_BASE_URL}/web/client/dirs?path={quote_remote_path(path)}",
            label,
            ignore_cancel=ignore_cancel,
        )
        data = response.json()
        return data if isinstance(data, list) else []

    def ensure_editor_folder(self, session: requests.Session, csrf_token: str) -> str:
        self.set_status("running", "Scanning editors")
        root_entries = self.list_dirs(session, "/", "scan all editor folders")
        self.log(f"Scanned {len(root_entries)} root folders across the full editor list.")
        folders = [entry for entry in root_entries if str(entry.get("type")) == "1"]
        existing = next((entry.get("name") for entry in folders if str(entry.get("name", "")).lower() == self.editor_name.lower()), None)
        if existing:
            self.log(f"Editor folder found: {existing}.")
            return str(existing)

        self.set_status("running", "Creating editor folder")
        self.request(
            session,
            "POST",
            f"{FILES_BASE_URL}/web/client/dirs?path={quote_remote_path('/' + self.editor_name)}",
            "create editor folder",
            expected=(201,),
            headers={"X-CSRF-TOKEN": csrf_token},
        )
        self.log(f"Editor folder created: {self.editor_name}.")
        return self.editor_name

    def ensure_upload_target_is_clear(
        self,
        session: requests.Session,
        csrf_token: str,
        editor_name: str,
        folder_name: str,
    ) -> None:
        self.set_status("running", "Checking destination")
        response = self.request(
            session,
            "POST",
            f"{FILES_BASE_URL}/web/client/exist?op=upload&path={quote_remote_path('/' + editor_name)}",
            "check upload target",
            headers={"X-CSRF-TOKEN": csrf_token, "Content-Type": "application/json"},
            data=json.dumps({"files": [folder_name]}),
        )
        existing = response.json()
        if existing:
            raise FilesDuplicateLeakError(f"{editor_name}/{folder_name}")
        self.log(f"Destination is clear for {folder_name}.")

    def upload_folder(
        self,
        session: requests.Session,
        csrf_token: str,
        editor_name: str,
        folder_path: Path,
        folder_name: str,
        files: list[Path],
    ) -> None:
        self.set_status("running", "Uploading")
        checked_dirs: set[str] = set()
        remote_root = "/" + editor_name
        for file_path in files:
            self.ensure_not_cancelled()
            relative = file_path.relative_to(folder_path).as_posix()
            upload_name = f"{folder_name}/{relative}"
            parent = upload_name.rsplit("/", 1)[0]
            mkdir_parents = "false"
            if parent not in checked_dirs:
                mkdir_parents = "true"
                checked_dirs.add(parent)

            upload_url = (
                f"{FILES_BASE_URL}/web/client/file?path={quote_remote_path(remote_root)}"
                f"{quote_remote_path('/' + upload_name)}&mkdir_parents={mkdir_parents}"
            )
            headers = {
                "X-CSRF-TOKEN": csrf_token,
                "X-SFTPGO-MTIME": str(round(file_path.stat().st_mtime * 1000)),
                "Content-Type": "application/octet-stream",
            }
            self.log(f"Uploading {upload_name}.")
            with file_path.open("rb") as handle:
                self.request(
                    session,
                    "POST",
                    upload_url,
                    f"upload {upload_name}",
                    expected=(201,),
                    headers=headers,
                    data=CancellableFileReader(handle, self.cancel_event),
                    timeout=300,
                )
            self.ensure_not_cancelled()
            with self.lock:
                self.uploaded_files += 1
            self.set_progress()

    def verify_uploaded_folder(self, session: requests.Session, editor_name: str, folder_name: str) -> None:
        self.set_status("running", "Verifying")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            self.ensure_not_cancelled()
            entries = self.list_dirs(session, "/" + editor_name, "verify uploaded folder")
            if any(str(entry.get("type")) == "1" and entry.get("name") == folder_name for entry in entries):
                self.log(f"Verified folder on screen/list: /{editor_name}/{folder_name}.")
                return
            sleep_deadline = time.monotonic() + 1.5
            while time.monotonic() < sleep_deadline:
                self.ensure_not_cancelled()
                time.sleep(min(0.2, max(0.0, sleep_deadline - time.monotonic())))
        raise FilesAutomationError("Upload finished but the remote folder was not visible during verification.")

    def rollback_upload(self, session: requests.Session, csrf_token: str) -> list[str]:
        with self.lock:
            targets = list(reversed(self.rollback_targets))
        if not targets:
            self.log("Nothing was uploaded before cancellation.")
            return []

        self.set_status("running", "Rolling back")
        rollback_errors: list[str] = []
        for remote_path in targets:
            try:
                self.delete_remote_folder(session, csrf_token, remote_path)
                self.log(f"Rolled back {remote_path}.")
            except Exception as error:
                message = f"{remote_path}: {error}"
                rollback_errors.append(message)
                self.log(f"Rollback error: {message}")
        return rollback_errors

    def delete_remote_folder(self, session: requests.Session, csrf_token: str, remote_path: str) -> None:
        clean_remote_path = normalize_remote_path(remote_path, allow_root=False)
        response = self.request(
            session,
            "DELETE",
            f"{FILES_BASE_URL}/web/client/dirs?path={quote_remote_path(clean_remote_path)}",
            f"delete remote folder {clean_remote_path}",
            expected=(202, 404),
            headers={"X-CSRF-TOKEN": csrf_token},
            timeout=30,
            ignore_cancel=True,
        )
        if response.status_code == 404:
            self.log(f"Remote folder was already absent: {clean_remote_path}.")
            return

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        task_id = str(payload.get("message", "") or "").strip()
        if not task_id:
            self.wait_remote_folder_absent(session, clean_remote_path, timeout_seconds=60)
            return

        deadline = time.monotonic() + 300
        task_url = f"{FILES_BASE_URL}/web/client/tasks/{quote_remote_path(task_id)}"
        try:
            while time.monotonic() < deadline:
                task_response = self.request(
                    session,
                    "GET",
                    task_url,
                    f"check delete task {task_id}",
                    expected=(200,),
                    headers={"X-CSRF-TOKEN": csrf_token},
                    timeout=30,
                    ignore_cancel=True,
                )
                try:
                    task_payload = task_response.json()
                except ValueError as error:
                    raise FilesAutomationError("Delete task returned an invalid response.") from error
                task_status = int(task_payload.get("status", 0) or 0)
                if task_status == 200:
                    return
                if task_status >= 400:
                    raise FilesAutomationError(f"Delete task returned HTTP {task_status}.")
                time.sleep(1)
        except FilesAutomationError as error:
            message = str(error).lower()
            if "returned http 401" not in message and "returned http 403" not in message and "invalid token" not in message:
                raise
            self.log("Delete task status could not be read. Verifying folder removal from the cloud list.")
            self.wait_remote_folder_absent(session, clean_remote_path, timeout_seconds=300)
            return

        self.log("Delete task did not finish in time. Verifying folder removal from the cloud list.")
        self.wait_remote_folder_absent(session, clean_remote_path, timeout_seconds=120)

    def remote_folder_exists(self, session: requests.Session, remote_path: str) -> bool:
        clean_path = normalize_remote_path(remote_path, allow_root=False)
        parent = remote_parent_path(clean_path)
        name = remote_basename(clean_path)
        entries = self.list_dirs(session, parent, f"check rollback target {clean_path}", ignore_cancel=True)
        return any(str(entry.get("type")) == "1" and str(entry.get("name", "")) == name for entry in entries)

    def wait_remote_folder_absent(
        self,
        session: requests.Session,
        remote_path: str,
        timeout_seconds: int = 180,
    ) -> None:
        clean_path = normalize_remote_path(remote_path, allow_root=False)
        deadline = time.monotonic() + timeout_seconds
        last_error = ""
        while time.monotonic() < deadline:
            try:
                if not self.remote_folder_exists(session, clean_path):
                    self.log(f"Verified remote folder is absent: {clean_path}.")
                    return
            except Exception as error:
                last_error = str(error)
            time.sleep(1.2)
        suffix = f" Last check: {last_error}" if last_error else ""
        raise FilesAutomationError(f"Delete was accepted, but {clean_path} was still visible after waiting.{suffix}")


def start_files_job(editor_name: str, folder_paths) -> FilesUploadJob:
    job = FilesUploadJob(editor_name, folder_paths)
    with FILES_JOBS_LOCK:
        FILES_JOBS[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return job


class FilesAppHandler(BaseHTTPRequestHandler):
    server_version = "6ureFilesLocal/1.0"

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/json; charset=utf-8",
        extra_headers: dict[str, str | list[str] | tuple[str, ...]] | None = None,
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra_headers or {}).items():
                if isinstance(value, (list, tuple)):
                    for item in value:
                        self.send_header(key, str(item))
                else:
                    self.send_header(key, str(value))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json_bytes(payload))

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body is too large.")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"ok": True})
            return
        if parsed.path == "/api/files/last":
            self._files_last()
            return
        if parsed.path == "/api/files/status":
            self._files_status(parsed.query)
            return
        if parsed.path == "/api/cloud/list":
            self._cloud_list(parsed.query)
            return
        if parsed.path == "/api/protected/list":
            self._protected_list()
            return
        if parsed.path == "/api/update/status":
            self._update_status()
            return
        if parsed.path == "/api/discord-presence/status":
            self._discord_presence_status()
            return
        if parsed.path == "/api/network/status":
            self._network_status()
            return
        if parsed.path == "/api/security/status":
            self._security_status()
            return
        if parsed.path == "/api/app-auth/status":
            self._app_auth_status(parsed.query)
            return
        if parsed.path == "/api/resources/mine":
            self._my_resources(parsed.query)
            return
        resource_detail_match = re.fullmatch(r"/api/resources/(\d+)", parsed.path)
        if resource_detail_match:
            self._resource_detail(resource_detail_match.group(1), parsed.query)
            return
        if parsed.path == "/api/hlx/tiktok/search":
            self._hlx_tiktok_search(parsed.query)
            return
        if parsed.path == "/api/hlx/tiktok/profile":
            self._hlx_tiktok_profile(parsed.query)
            return
        if parsed.path == "/api/hlx/tiktok/video":
            self._hlx_tiktok_video(parsed.query)
            return
        if parsed.path == "/api/hlx/youtube/search":
            self._hlx_youtube_search(parsed.query)
            return
        if parsed.path == "/api/hlx/youtube/channel":
            self._hlx_youtube_channel(parsed.query)
            return
        if parsed.path == "/api/hlx/youtube/video":
            self._hlx_youtube_video(parsed.query)
            return
        if parsed.path == "/api/leaker-mode/status":
            self._leaker_mode_status()
            return
        if parsed.path == "/api/leaker-mode/session":
            self._leaker_mode_session()
            return
        if parsed.path == "/api/leaker-oauth/status":
            self._leaker_oauth_status()
            return
        if parsed.path == LEAKER_OAUTH_BRIDGE_PATH:
            self._leaker_oauth_bridge(parsed.query)
            return
        if is_leaker_site_root_request(parsed, self.headers) or is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._serve_static(parsed.path)

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if is_leaker_site_root_request(parsed, self.headers) or is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._send(404, b"", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/window-action":
            self._window_action()
            return
        if parsed.path == "/api/open-url":
            self._open_url()
            return
        if parsed.path == "/api/leaker-mode/start":
            self._leaker_mode_start()
            return
        if parsed.path == "/api/leaker-mode/launch":
            self._leaker_mode_launch()
            return
        if parsed.path == "/api/leaker-mode/exit":
            self._leaker_mode_exit()
            return
        if parsed.path == "/api/leaker-oauth/open":
            self._leaker_oauth_open()
            return
        if parsed.path == "/api/app-auth/discord/start":
            self._app_auth_discord_start()
            return
        if parsed.path == "/api/app-auth/logout":
            self._app_auth_logout()
            return
        if parsed.path == "/api/files/login":
            self._files_login()
            return
        if parsed.path == "/api/files/logout":
            self._files_logout()
            return
        if parsed.path == "/api/files/select-folder":
            self._files_select_folder()
            return
        if parsed.path == "/api/files/folder-summary":
            self._files_folder_summary()
            return
        if parsed.path == "/api/files/start-upload":
            self._files_start_upload()
            return
        if parsed.path == "/api/files/cancel-upload":
            self._files_cancel_upload()
            return
        if parsed.path == "/api/cloud/action":
            self._cloud_action()
            return
        if parsed.path == "/api/protected/check":
            self._protected_check()
            return
        if parsed.path == "/api/update/check":
            self._update_check()
            return
        if parsed.path == "/api/update/install":
            self._update_install()
            return
        if parsed.path == "/api/security/settings":
            self._security_settings()
            return
        if parsed.path == "/api/security/repair":
            self._security_repair()
            return
        if parsed.path == "/api/debug/bundle":
            self._debug_bundle()
            return
        if parsed.path == "/api/discord-presence/activity":
            self._discord_presence_activity()
            return
        if parsed.path == "/api/discord-presence/clear":
            self._discord_presence_clear()
            return
        if is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._send_json(404, {"success": False, "msg": "Not found."})

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._send_json(404, {"success": False, "msg": "Not found."})

    def do_PATCH(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._send_json(404, {"success": False, "msg": "Not found."})

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if is_leaker_proxy_path(parsed.path):
            self._leaker_proxy(parsed)
            return
        self._send_json(404, {"success": False, "msg": "Not found."})

    def _serve_static(self, request_path: str) -> None:
        target = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        file_path = (ROOT / target).resolve()

        if ROOT not in file_path.parents and file_path != ROOT:
            self._send(403, b"Forbidden", "text/plain; charset=utf-8")
            return
        if file_path.name in PROTECTED_STATIC_NAMES:
            self._send(403, b"Forbidden", "text/plain; charset=utf-8")
            return
        if not file_path.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type += "; charset=utf-8"
        self._send(200, file_path.read_bytes(), content_type)

    def _leaker_proxy(self, parsed: urllib.parse.SplitResult) -> None:
        try:
            ensure_leaker_cookie_consent(save=False)
            upstream_path = leaker_upstream_path(parsed.path)
            upstream_url = f"{LEAKER_SITE_BASE_URL}{upstream_path}"
            if parsed.query:
                upstream_url = f"{upstream_url}?{parsed.query}"

            body = None
            if self.command not in {"GET", "HEAD"}:
                length = int(self.headers.get("Content-Length", "0"))
                if length > MAX_BODY_BYTES * 8:
                    raise ValueError("Request body is too large.")
                body = self.rfile.read(length) if length else b""

            blocked_request_headers = {
                "host",
                "connection",
                "content-length",
                "accept-encoding",
                "cookie",
            }
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in blocked_request_headers
            }
            headers["Host"] = "6ureleaks.com"
            headers["User-Agent"] = LEAKER_PROXY_USER_AGENT
            headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            if self.command not in {"GET", "HEAD"}:
                headers["Origin"] = LEAKER_SITE_BASE_URL
            headers["Referer"] = LEAKER_SITE_BASE_URL + "/dashboard"

            with LEAKER_PROXY_LOCK:
                response = LEAKER_PROXY_SESSION.request(
                    self.command,
                    upstream_url,
                    headers=headers,
                    data=body,
                    allow_redirects=False,
                    timeout=LEAKER_PROXY_TIMEOUT_SECONDS,
                )
                try:
                    LEAKER_PROXY_SESSION.cookies.save(ignore_discard=True, ignore_expires=True)
                except Exception:
                    pass

            content_type = response.headers.get("Content-Type", "application/octet-stream")
            response_body = b"" if self.command == "HEAD" else response.content
            if response_body and should_rewrite_leaker_content(content_type) and should_rewrite_leaker_page(content_type, upstream_path):
                text = response.text
                text = rewrite_leaker_proxy_text(text)
                text = inject_leaker_discord_oauth_bridge(text)
                response_body = text.encode(response.encoding or "utf-8", errors="replace")

            blocked_response_headers = {
                "content-security-policy",
                "content-security-policy-report-only",
                "x-frame-options",
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "connection",
                "set-cookie",
                "strict-transport-security",
                "cross-origin-opener-policy",
                "cross-origin-embedder-policy",
                "cross-origin-resource-policy",
            }
            extra_headers: dict[str, str | list[str]] = {}
            for key, value in response.headers.items():
                lower = key.lower()
                if lower in blocked_response_headers or lower == "content-type":
                    continue
                if lower == "location":
                    if is_discord_oauth_url(value) and self.command != "HEAD":
                        body = leaker_discord_oauth_bridge_html(value).encode("utf-8")
                        self._send(
                            200,
                            body,
                            "text/html; charset=utf-8",
                            {"X-6ure-Leaker-Proxy": "1", "X-6ure-Leaker-OAuth-Bridge": "1"},
                        )
                        return
                    extra_headers[key] = leaker_proxy_location(value)
                else:
                    extra_headers[key] = value
            extra_headers["X-6ure-Leaker-Proxy"] = "1"
            extra_headers["Set-Cookie"] = leaker_cookie_consent_response_headers()
            self._send(response.status_code, response_body, content_type, extra_headers)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
        except Exception as error:
            self._send_json(502, {"success": False, "msg": f"Leaker proxy failed: {error}"})

    def _window_action(self) -> None:
        try:
            payload = self._read_json()
            action = str(payload.get("action", "")).strip().lower()
            if action not in {"minimize", "maximize", "close"}:
                raise ValueError("Unsupported window action.")

            bridge = getattr(self.server, "window_bridge", None)
            if bridge is None:
                raise ValueError("Window bridge is unavailable.")

            threading.Thread(target=bridge.window_action, args=(action,), daemon=True).start()
            if action == "close":
                threading.Thread(target=self._force_exit_after_close, daemon=True).start()
            self._send_json(200, {"success": True})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    @staticmethod
    def _force_exit_after_close() -> None:
        time.sleep(1.2)
        stop_discord_presence()
        os._exit(0)

    def _open_url(self) -> None:
        try:
            payload = self._read_json()
            url = str(payload.get("url", "")).strip()
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != "https" or parsed.netloc.lower() not in ALLOWED_EXTERNAL_HOSTS:
                raise ValueError("URL is not allowed.")
            webbrowser.open(url)
            self._send_json(200, {"success": True})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_bridge(self):
        bridge = getattr(self.server, "window_bridge", None)
        if bridge is None:
            raise ValueError("Window bridge is unavailable.")
        return bridge

    def _leaker_mode_status(self) -> None:
        try:
            self._send_json(200, self._leaker_bridge().leaker_status())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_mode_session(self) -> None:
        try:
            user = fetch_app_auth_user_from_leaker_session()
            if user:
                set_app_auth_user(user)
            else:
                clear_app_auth_state(clear_cookies=False)
            self._send_json(
                200,
                {
                    "success": True,
                    "authenticated": bool(user),
                    "user": user,
                    "checkedAt": int(time.time() * 1000),
                },
            )
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_mode_start(self) -> None:
        try:
            self._send_json(200, self._leaker_bridge().start_leaker_mode())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_mode_launch(self) -> None:
        try:
            self._send_json(200, self._leaker_bridge().launch_leaker_mode())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_mode_exit(self) -> None:
        try:
            self._send_json(200, self._leaker_bridge().exit_leaker_mode())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_oauth_status(self) -> None:
        try:
            self._send_json(200, self._leaker_bridge().leaker_oauth_status())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _leaker_oauth_bridge(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            url = normalize_discord_oauth_url((params.get("url") or [""])[0])
            if not is_discord_oauth_url(url):
                raise ValueError("Invalid Discord OAuth URL.")
            body = leaker_discord_oauth_bridge_html(url).encode("utf-8")
            self._send(
                200,
                body,
                "text/html; charset=utf-8",
                {"X-6ure-Leaker-OAuth-Bridge": "1"},
            )
        except Exception as error:
            clean_error = html.escape(str(error))
            self._send(
                400,
                f"Discord OAuth bridge failed: {clean_error}".encode("utf-8"),
                "text/plain; charset=utf-8",
            )

    def _leaker_oauth_open(self) -> None:
        try:
            payload = self._read_json()
            url = str(payload.get("url", "") or "").strip()
            self._send_json(200, self._leaker_bridge().open_leaker_oauth(url))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _app_auth_status(self, query: str = "") -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            payload = get_app_auth_status(refresh=refresh)
            try:
                oauth_status = self._leaker_bridge().leaker_oauth_status()
            except Exception:
                oauth_status = {
                    "phase": "idle",
                    "active": False,
                    "completed": False,
                    "cancelled": False,
                    "windowOpen": False,
                }
            payload["oauth"] = oauth_status
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _app_auth_discord_start(self) -> None:
        try:
            payload = self._read_json()
            url = str(payload.get("url", "") or "").strip() or APP_DISCORD_OAUTH_URL
            if not is_discord_oauth_url(url):
                raise ValueError("Invalid Discord OAuth URL.")
            oauth_status = self._leaker_bridge().open_leaker_oauth(url)
            auth_status = get_app_auth_status(refresh=False)
            auth_status["oauth"] = oauth_status
            self._send_json(200, auth_status)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _app_auth_logout(self) -> None:
        try:
            try:
                self._leaker_bridge().exit_leaker_mode()
            except Exception:
                pass
            payload = clear_app_auth_state(clear_cookies=True)
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _discord_presence_status(self) -> None:
        try:
            payload = get_discord_presence_status()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _network_status(self) -> None:
        try:
            payload = get_network_status()
            payload["success"] = True
            payload["checkedAt"] = int(time.time() * 1000)
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _security_status(self) -> None:
        try:
            self._send_json(200, security_status())
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _security_settings(self) -> None:
        try:
            payload = self._read_json()
            self._send_json(200, update_security_settings(payload))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _security_repair(self) -> None:
        try:
            self._send_json(200, run_silent_repair("manual"))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _debug_bundle(self) -> None:
        try:
            payload = self._read_json()
            reveal = payload.get("reveal", True) is not False
            self._send_json(200, create_debug_bundle(reveal=reveal))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _my_resources(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "")
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(200, get_my_resources_payload(refresh=refresh))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"Resources could not be loaded: {error}"})

    def _resource_detail(self, resource_id: str, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "")
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(200, get_resource_detail_payload(safe_int(resource_id), refresh=refresh))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"Resource could not be loaded: {error}"})

    def _hlx_tiktok_search(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            search_query = str((params.get("username") or params.get("q") or [""])[0]).strip()
            limit = safe_int((params.get("limit") or ["0"])[0], 0)
            result_limit = safe_int((params.get("resultLimit") or ["8"])[0], 8)
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(
                200,
                get_hlx_tiktok_search_payload(
                    search_query,
                    limit=limit,
                    result_limit=result_limit,
                    refresh=refresh,
                ),
            )
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"TikTok search failed: {error}"})

    def _hlx_tiktok_profile(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            username = str((params.get("username") or [""])[0]).strip()
            limit = safe_int((params.get("limit") or ["12"])[0], 12)
            preview_limit = safe_int((params.get("previewLimit") or ["0"])[0], 0)
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(
                200,
                get_hlx_tiktok_profile_payload(
                    username,
                    limit=limit,
                    preview_limit=preview_limit,
                    refresh=refresh,
                ),
            )
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"TikTok profile failed: {error}"})

    def _hlx_tiktok_video(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            url = str((params.get("url") or [""])[0]).strip()
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(200, fetch_hlx_tiktok_video(url, refresh=refresh))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"TikTok video failed: {error}"})

    def _hlx_youtube_search(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            search_query = str((params.get("url") or params.get("username") or params.get("q") or [""])[0]).strip()
            limit = safe_int((params.get("limit") or ["0"])[0], 0)
            result_limit = safe_int((params.get("resultLimit") or ["5"])[0], 5)
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(
                200,
                get_hlx_youtube_search_payload(
                    search_query,
                    limit=limit,
                    result_limit=result_limit,
                    refresh=refresh,
                ),
            )
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"YouTube search failed: {error}"})

    def _hlx_youtube_channel(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            url = str((params.get("url") or params.get("username") or [""])[0]).strip()
            limit = safe_int((params.get("limit") or ["12"])[0], 12)
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(200, get_hlx_youtube_channel_payload(url, limit=limit, refresh=refresh))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"YouTube channel failed: {error}"})

    def _hlx_youtube_video(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query or "", keep_blank_values=True)
            url = str((params.get("url") or [""])[0]).strip()
            refresh = str(params.get("refresh", [""])[0]).strip().lower() in {"1", "true", "yes"}
            self._send_json(200, fetch_hlx_youtube_video(url, refresh=refresh))
        except Exception as error:
            self._send_json(400, {"success": False, "msg": f"YouTube video failed: {error}"})

    def _discord_presence_activity(self) -> None:
        try:
            payload = self._read_json()
            result = set_discord_presence_activity(
                details=str(payload.get("details", "") or "") if "details" in payload else None,
                state=str(payload.get("state", "") or "") if "state" in payload else None,
                small_image=str(payload.get("smallImage", "") or "") if "smallImage" in payload else None,
                small_text=str(payload.get("smallText", "") or "") if "smallText" in payload else None,
            )
            result["success"] = True
            self._send_json(200, result)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _discord_presence_clear(self) -> None:
        try:
            manager = start_discord_presence()
            payload = manager.clear()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_last(self) -> None:
        state = get_files_state()
        session = get_session_snapshot()
        authenticated = bool(session["authenticated"])
        last_folder_paths = normalize_string_list(state.get("lastFolderPaths"))
        last_folder_names = normalize_string_list(state.get("lastFolderNames"))
        if not last_folder_paths and state.get("lastFolderPath"):
            last_folder_paths = [str(state.get("lastFolderPath", "")).strip()]
        if not last_folder_names and state.get("lastFolderName"):
            last_folder_names = [str(state.get("lastFolderName", "")).strip()]
        app_snapshot = get_app_auth_snapshot()
        app_user = app_snapshot.get("user") if app_snapshot.get("authenticated") else None
        app_display_name = ""
        if isinstance(app_user, dict):
            app_display_name = clean_discord_display_name(app_user.get("displayName") or app_user.get("username") or "")
        self._send_json(
            200,
            {
                "success": True,
                "lastEditor": state.get("lastEditor", ""),
                "lastFolderPath": state.get("lastFolderPath", ""),
                "lastFolderName": state.get("lastFolderName", ""),
                "lastFolderPaths": last_folder_paths,
                "lastFolderNames": last_folder_names,
                "authenticated": authenticated,
                "hasCredentials": authenticated,
                "cloudUsername": session["username"],
                "filesUsername": app_display_name or session["username"],
                "storagePath": str(DATA_ROOT),
            },
        )

    def _files_login(self) -> None:
        try:
            payload = self._read_json()
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            validate_files_credentials(username, password)
            persisted = save_files_state(username=username, password=password)
            set_session_credentials(username, password)
            sync_session_from_state(persisted)
            set_discord_presence_activity(details="6ure workspace", state="Ready")
            self._send_json(200, {"success": True, "username": username})
        except PermissionError as error:
            clear_session_credentials()
            self._send_json(401, {"success": False, "msg": str(error)})
        except Exception as error:
            clear_session_credentials()
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_logout(self) -> None:
        try:
            clear_session_credentials()
            clear_persisted_account_data()
            set_discord_presence_activity(details="6ure App", state="Signed out")
            self._send_json(200, {"success": True})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_status(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            job_id = str(params.get("id", [""])[0])
            with FILES_JOBS_LOCK:
                job = FILES_JOBS.get(job_id)
            if not job:
                raise ValueError("Upload job was not found.")
            payload = job.snapshot()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_select_folder(self) -> None:
        try:
            payload = self._read_json()
            existing_folder_paths = payload.get("existingFolderPaths")
            if not isinstance(existing_folder_paths, list):
                existing_folder_paths = []

            bridge = getattr(self.server, "window_bridge", None)
            if bridge is None:
                raise ValueError("Window bridge is unavailable.")

            folder_paths = bridge.select_folders()
            if not folder_paths:
                self._send_json(200, {"success": False, "cancelled": True})
                return

            paths = normalize_local_folder_paths([*existing_folder_paths, *folder_paths])
            folder_payload = [get_local_folder_summary(path) for path in paths]
            save_last_folder_selection(paths)
            self._send_json(
                200,
                {
                    "success": True,
                    "path": folder_payload[0]["path"],
                    "name": folder_payload[0]["name"],
                    "folders": folder_payload,
                },
            )
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_folder_summary(self) -> None:
        try:
            payload = self._read_json()
            folder_paths = payload.get("folderPaths")
            if not isinstance(folder_paths, list):
                folder_paths = [str(payload.get("folderPath", "")).strip()]
            folder_payload = get_local_folder_summaries(folder_paths)
            save_last_folder_selection([Path(item["path"]).expanduser().resolve() for item in folder_payload])
            self._send_json(200, {"success": True, "folders": folder_payload})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _protected_list(self) -> None:
        try:
            payload = get_protected_list_payload()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _protected_check(self) -> None:
        try:
            payload = self._read_json()
            names = payload.get("names")
            if not isinstance(names, list):
                names = [payload.get("name", "")]
            result = check_protected_names([str(name or "") for name in names])
            result["success"] = True
            self._send_json(200, result)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_start_upload(self) -> None:
        try:
            payload = self._read_json()
            editor_name = str(payload.get("editorName", "")).strip()
            raw_folder_paths = payload.get("folderPaths")
            if isinstance(raw_folder_paths, list):
                folder_paths = raw_folder_paths
            else:
                folder_paths = [str(payload.get("folderPath", "")).strip()]
            job = start_files_job(editor_name, folder_paths)
            save_files_state(
                lastEditor=job.editor_name,
                lastFolderPath=str(job.folder_path),
                lastFolderName=job.folder_name,
                lastFolderPaths=[str(path) for path in job.folder_paths],
                lastFolderNames=list(job.folder_names),
            )
            self._send_json(200, {"success": True, "jobId": job.id})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _files_cancel_upload(self) -> None:
        try:
            payload = self._read_json()
            job_id = str(payload.get("jobId", "")).strip()
            with FILES_JOBS_LOCK:
                job = FILES_JOBS.get(job_id)
            if not job:
                raise ValueError("Upload job was not found.")
            job.request_cancel()
            snapshot = job.snapshot()
            snapshot["success"] = True
            self._send_json(200, snapshot)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _cloud_list(self, query: str) -> None:
        try:
            params = urllib.parse.parse_qs(query)
            cloud_path = normalize_remote_path(params.get("path", ["/"])[0])
            client = get_authenticated_remote_client()
            entries = client.list_dir(cloud_path)
            self._send_json(
                200,
                {
                    "success": True,
                    "path": cloud_path,
                    "parentPath": remote_parent_path(cloud_path) if cloud_path != "/" else "",
                    "breadcrumbs": remote_breadcrumbs(cloud_path),
                    "entries": entries,
                },
            )
        except PermissionError as error:
            clear_session_credentials()
            self._send_json(401, {"success": False, "msg": str(error)})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _cloud_action(self) -> None:
        try:
            payload = self._read_json()
            action = str(payload.get("action", "") or "").strip().lower()
            source_path = normalize_remote_path(str(payload.get("path", "") or ""), allow_root=False)
            item_type = str(payload.get("type", "") or "").strip().lower()
            source_name = remote_basename(source_path)
            source_parent = remote_parent_path(source_path)
            client = get_authenticated_remote_client()

            if action == "rename":
                new_name = normalize_remote_name(str(payload.get("name", "") or ""), "New name")
                target_path = remote_join(source_parent, new_name)
                client.move(source_path, target_path)
                self._send_json(
                    200,
                    {
                        "success": True,
                        "msg": f"Renamed to {new_name}.",
                        "path": target_path,
                        "listPath": remote_parent_path(target_path),
                    },
                )
                return

            if action == "move":
                destination_folder = normalize_remote_path(
                    str(payload.get("destinationPath", "") or ""),
                    "Destination folder",
                )
                target_path = remote_join(destination_folder, source_name)
                client.move(source_path, target_path)
                self._send_json(
                    200,
                    {
                        "success": True,
                        "msg": f"Moved to {destination_folder}.",
                        "path": target_path,
                        "listPath": remote_parent_path(target_path),
                    },
                )
                return

            if action == "delete":
                client.delete(source_path, item_type)
                self._send_json(
                    200,
                    {
                        "success": True,
                        "msg": f"Deleted {source_name}.",
                        "listPath": source_parent,
                    },
                )
                return

            if action == "extract":
                target_path = str(payload.get("targetPath", "") or "").strip()
                result = client.extract_remote_zip(source_path, target_path)
                self._send_json(
                    200,
                    {
                        "success": True,
                        "msg": f"Extracted {source_name}.",
                        "result": result,
                        "path": result["path"],
                        "listPath": remote_parent_path(result["path"]),
                    },
                )
                return

            raise ValueError("Unsupported cloud action.")
        except PermissionError as error:
            clear_session_credentials()
            self._send_json(401, {"success": False, "msg": str(error)})
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _update_status(self) -> None:
        try:
            payload = get_update_status()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _update_check(self) -> None:
        try:
            payload = check_for_update()
            payload["success"] = True
            self._send_json(200, payload)
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _update_install(self) -> None:
        try:
            payload = prepare_update_install()
            payload["success"] = True
            self._send_json(200, payload)
            if payload.get("restarting"):
                threading.Thread(target=self._close_for_update, daemon=True).start()
        except Exception as error:
            self._send_json(400, {"success": False, "msg": str(error)})

    def _close_for_update(self) -> None:
        time.sleep(0.8)
        bridge = getattr(self.server, "window_bridge", None)
        if bridge is not None:
            try:
                bridge.window_action("close")
            except Exception:
                pass
        time.sleep(1.4)
        stop_discord_presence()
        os._exit(0)

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def create_server(port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), FilesAppHandler)


def main() -> None:
    boot_state = clear_last_files_selection()
    sync_session_from_state(boot_state)
    server = create_server(PORT)
    print(f"6ure™ App local server running at http://localhost:{PORT}")
    server.serve_forever()


if get_app_setting("silentRepairMode"):
    run_silent_repair("startup")
BOOT_STATE = clear_last_files_selection()
sync_session_from_state(BOOT_STATE)
refresh_discord_presence_from_session()


if __name__ == "__main__":
    main()
