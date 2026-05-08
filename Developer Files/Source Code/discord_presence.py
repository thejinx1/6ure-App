from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any


OP_HANDSHAKE = 0
OP_FRAME = 1
MAX_TEXT_LENGTH = 128
MAX_ASSET_LENGTH = 313
VALID_ACTIVITY_TYPES = {0, 2, 3, 5}
DEFAULT_JOIN_URL = "https://discord.gg/nV4Ab3rkrY"

DEFAULT_CONFIG = {
    "enabled": True,
    "clientId": "",
    "activityType": 0,
    "details": "6ure workspace",
    "detailsUrl": DEFAULT_JOIN_URL,
    "state": "Ready",
    "stateUrl": DEFAULT_JOIN_URL,
    "largeImage": "6ure-logo",
    "largeText": "6ure App",
    "largeUrl": DEFAULT_JOIN_URL,
    "smallImage": "",
    "smallText": "",
    "smallUrl": "",
    "startTimestamp": True,
    "reconnectSeconds": 10,
    "buttons": [
        {
            "label": "Join 6ure",
            "url": DEFAULT_JOIN_URL,
        }
    ],
}


class DiscordIpcError(Exception):
    pass


def _clean_text(value: Any, limit: int = MAX_TEXT_LENGTH) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def _clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _clean_positive_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(1.0, number)


def _clean_activity_type(value: Any) -> int:
    try:
        activity_type = int(value)
    except (TypeError, ValueError):
        return 0
    return activity_type if activity_type in VALID_ACTIVITY_TYPES else 0


def _clean_asset(value: Any) -> str:
    return _clean_text(value, MAX_ASSET_LENGTH)


def _clean_url(value: Any) -> str:
    url = _clean_text(value, 512)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def _normalize_button(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    label = _clean_text(value.get("label"), 32)
    url = _clean_text(value.get("url"), 512)
    parsed = urllib.parse.urlsplit(url)
    if not label or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return {"label": label, "url": url}


def _read_json_file(path: Path) -> dict | None:
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_presence_config(paths: list[Path]) -> dict:
    config = dict(DEFAULT_CONFIG)
    for path in paths:
        payload = _read_json_file(path)
        if isinstance(payload, dict):
            config.update(payload)

    env_map = {
        "REYLI_DISCORD_CLIENT_ID": "clientId",
        "REYLI_DISCORD_ACTIVITY_TYPE": "activityType",
        "REYLI_DISCORD_DETAILS": "details",
        "REYLI_DISCORD_DETAILS_URL": "detailsUrl",
        "REYLI_DISCORD_STATE": "state",
        "REYLI_DISCORD_STATE_URL": "stateUrl",
        "REYLI_DISCORD_LARGE_IMAGE": "largeImage",
        "REYLI_DISCORD_LARGE_TEXT": "largeText",
        "REYLI_DISCORD_LARGE_URL": "largeUrl",
        "REYLI_DISCORD_SMALL_IMAGE": "smallImage",
        "REYLI_DISCORD_SMALL_TEXT": "smallText",
        "REYLI_DISCORD_SMALL_URL": "smallUrl",
        "REYLI_DISCORD_RECONNECT_SECONDS": "reconnectSeconds",
    }
    for env_name, key in env_map.items():
        value = os.environ.get(env_name)
        if value is not None:
            config[key] = value

    enabled_env = os.environ.get("REYLI_DISCORD_PRESENCE_ENABLED")
    if enabled_env is not None:
        config["enabled"] = _clean_bool(enabled_env, True)

    buttons = config.get("buttons")
    if isinstance(buttons, list):
        config["buttons"] = [button for button in (_normalize_button(item) for item in buttons) if button][:2]
    else:
        config["buttons"] = []

    config["enabled"] = _clean_bool(config.get("enabled"), True)
    config["clientId"] = _clean_text(config.get("clientId"), 64)
    config["activityType"] = _clean_activity_type(config.get("activityType"))
    config["details"] = _clean_text(config.get("details") or DEFAULT_CONFIG["details"])
    config["detailsUrl"] = _clean_url(config.get("detailsUrl") or config.get("details_url"))
    config["state"] = _clean_text(config.get("state") or DEFAULT_CONFIG["state"])
    config["stateUrl"] = _clean_url(config.get("stateUrl") or config.get("state_url"))
    config["largeImage"] = _clean_asset(config.get("largeImage") or config.get("largeImageKey"))
    config["largeText"] = _clean_text(config.get("largeText") or config.get("largeImageText"))
    config["largeUrl"] = _clean_url(config.get("largeUrl") or config.get("large_url"))
    config["smallImage"] = _clean_asset(config.get("smallImage") or config.get("smallImageKey"))
    config["smallText"] = _clean_text(config.get("smallText") or config.get("smallImageText"))
    config["smallUrl"] = _clean_url(config.get("smallUrl") or config.get("small_url"))
    config["startTimestamp"] = _clean_bool(config.get("startTimestamp"), True)
    config["reconnectSeconds"] = _clean_positive_float(config.get("reconnectSeconds"), 10.0)
    return config


class _FileTransport:
    def __init__(self, handle, name: str) -> None:
        self.handle = handle
        self.name = name

    def send(self, opcode: int, payload: dict) -> None:
        raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.handle.write(struct.pack("<II", opcode, len(raw_payload)) + raw_payload)
        self.handle.flush()

    def close(self) -> None:
        try:
            self.handle.close()
        except OSError:
            pass


class _SocketTransport:
    def __init__(self, sock: socket.socket, name: str) -> None:
        self.sock = sock
        self.name = name

    def send(self, opcode: int, payload: dict) -> None:
        raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.sock.sendall(struct.pack("<II", opcode, len(raw_payload)) + raw_payload)

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _open_windows_transport() -> _FileTransport:
    last_error: OSError | None = None
    for index in range(10):
        pipe_name = fr"\\?\pipe\discord-ipc-{index}"
        try:
            return _FileTransport(open(pipe_name, "r+b", buffering=0), pipe_name)
        except OSError as error:
            last_error = error
    raise DiscordIpcError(f"Discord IPC pipe was not found: {last_error}")


def _ipc_prefixes() -> list[Path]:
    prefixes: list[Path] = []
    seen: set[str] = set()
    for env_name in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"):
        value = os.environ.get(env_name)
        if not value:
            continue
        path = Path(value)
        key = os.path.normcase(str(path))
        if key not in seen:
            prefixes.append(path)
            seen.add(key)
    if "/tmp" not in seen:
        prefixes.append(Path("/tmp"))
    return prefixes


def _open_unix_transport() -> _SocketTransport:
    last_error: OSError | None = None
    for prefix in _ipc_prefixes():
        for index in range(10):
            ipc_path = prefix / f"discord-ipc-{index}"
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(1.5)
                sock.connect(str(ipc_path))
                return _SocketTransport(sock, str(ipc_path))
            except OSError as error:
                last_error = error
                try:
                    sock.close()
                except Exception:
                    pass
    raise DiscordIpcError(f"Discord IPC socket was not found: {last_error}")


def open_discord_transport():
    if sys.platform.startswith("win"):
        return _open_windows_transport()
    return _open_unix_transport()


class DiscordPresenceManager:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.enabled = bool(config.get("enabled"))
        self.client_id = str(config.get("clientId") or "").strip()
        self.reconnect_seconds = _clean_positive_float(config.get("reconnectSeconds"), 10.0)
        self.started_at = int(time.time())
        self.connected = False
        self.connection_name = ""
        self.last_error = "" if self.client_id else "Discord client id is not configured."
        self.last_updated_at = 0
        self._desired_activity: dict | None = self._build_activity()
        self._desired_details = str(self._desired_activity.get("details", "")) if self._desired_activity else ""
        self._desired_state = str(self._desired_activity.get("state", "")) if self._desired_activity else ""
        self._version = 0
        self._sent_version = -1
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.enabled or not self.client_id:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, name="DiscordPresence", daemon=True)
            self._thread.start()

    def set_activity(
        self,
        *,
        details: str | None = None,
        state: str | None = None,
        small_image: str | None = None,
        small_text: str | None = None,
    ) -> dict:
        activity = self._build_activity(
            details=details,
            state=state,
            small_image=small_image,
            small_text=small_text,
        )
        with self._lock:
            self._desired_activity = activity
            self._desired_details = str(activity.get("details", "")) if activity else ""
            self._desired_state = str(activity.get("state", "")) if activity else ""
            self._version += 1
            self.last_updated_at = int(time.time() * 1000)
        self.start()
        self._wakeup.set()
        return self.status()

    def clear(self) -> dict:
        with self._lock:
            self._desired_activity = None
            self._desired_details = ""
            self._desired_state = ""
            self._version += 1
            self.last_updated_at = int(time.time() * 1000)
        self._wakeup.set()
        return self.status()

    def shutdown(self) -> None:
        with self._lock:
            self._desired_activity = None
            self._version += 1
        self._stop.set()
        self._wakeup.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "configured": bool(self.client_id),
                "connected": self.connected,
                "connection": self.connection_name,
                "details": self._desired_details,
                "state": self._desired_state,
                "largeImage": str(self.config.get("largeImage") or ""),
                "largeText": str(self.config.get("largeText") or ""),
                "lastError": self.last_error,
                "lastUpdatedAt": self.last_updated_at,
            }

    def _build_activity(
        self,
        *,
        details: str | None = None,
        state: str | None = None,
        small_image: str | None = None,
        small_text: str | None = None,
    ) -> dict:
        activity: dict[str, Any] = {"type": _clean_activity_type(self.config.get("activityType"))}
        clean_details = _clean_text(details if details is not None else self.config.get("details"))
        clean_state = _clean_text(state if state is not None else self.config.get("state"))
        if clean_details:
            activity["details"] = clean_details
            details_url = _clean_url(self.config.get("detailsUrl") or self.config.get("details_url"))
            if details_url:
                activity["details_url"] = details_url
        if clean_state:
            activity["state"] = clean_state
            state_url = _clean_url(self.config.get("stateUrl") or self.config.get("state_url"))
            if state_url:
                activity["state_url"] = state_url
        if _clean_bool(self.config.get("startTimestamp"), True):
            activity["timestamps"] = {"start": self.started_at}

        assets: dict[str, str] = {}
        large_image = _clean_asset(self.config.get("largeImage"))
        large_text = _clean_text(self.config.get("largeText"))
        large_url = _clean_url(self.config.get("largeUrl") or self.config.get("large_url"))
        final_small_image = _clean_asset(small_image if small_image is not None else self.config.get("smallImage"))
        final_small_text = _clean_text(small_text if small_text is not None else self.config.get("smallText"))
        small_url = _clean_url(self.config.get("smallUrl") or self.config.get("small_url"))
        if large_image:
            assets["large_image"] = large_image
        if large_text:
            assets["large_text"] = large_text
        if large_url:
            assets["large_url"] = large_url
        if final_small_image:
            assets["small_image"] = final_small_image
        if final_small_text:
            assets["small_text"] = final_small_text
        if small_url:
            assets["small_url"] = small_url
        if assets:
            activity["assets"] = assets

        buttons = self.config.get("buttons")
        if isinstance(buttons, list) and buttons:
            activity["buttons"] = buttons[:2]
        return activity

    def _run(self) -> None:
        transport = None
        try:
            while not self._stop.is_set():
                if transport is None:
                    try:
                        transport = open_discord_transport()
                        self._handshake(transport)
                        with self._lock:
                            self.connected = True
                            self.connection_name = str(getattr(transport, "name", ""))
                            self.last_error = ""
                            self._sent_version = -1
                    except Exception as error:
                        if transport is not None:
                            transport.close()
                            transport = None
                        with self._lock:
                            self.connected = False
                            self.connection_name = ""
                            self.last_error = str(error)
                        self._wakeup.wait(self.reconnect_seconds)
                        self._wakeup.clear()
                        continue

                try:
                    self._send_pending(transport)
                except Exception as error:
                    transport.close()
                    transport = None
                    with self._lock:
                        self.connected = False
                        self.connection_name = ""
                        self.last_error = str(error)
                    continue

                self._wakeup.wait(30.0)
                self._wakeup.clear()
        finally:
            if transport is not None:
                try:
                    self._send_activity(transport, None)
                except Exception:
                    pass
                transport.close()
            with self._lock:
                self.connected = False
                self.connection_name = ""

    def _handshake(self, transport) -> None:
        transport.send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})

    def _send_pending(self, transport) -> None:
        with self._lock:
            activity = self._desired_activity
            version = self._version
            if version == self._sent_version:
                return
        self._send_activity(transport, activity)
        with self._lock:
            self._sent_version = version
            self.last_updated_at = int(time.time() * 1000)

    def _send_activity(self, transport, activity: dict | None) -> None:
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {
                "pid": os.getpid(),
                "activity": activity,
            },
            "nonce": uuid.uuid4().hex,
        }
        transport.send(OP_FRAME, payload)
