from __future__ import annotations

import html
import gc
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APPDATA_FOLDER_NAME = "6ure Leak Upld. User Data"


def persistent_app_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APPDATA_FOLDER_NAME

    if not sys.platform.startswith("win"):
        root = os.environ.get("XDG_DATA_HOME")
        if root:
            return Path(root) / APPDATA_FOLDER_NAME
        return Path.home() / ".local" / "share" / APPDATA_FOLDER_NAME

    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if root:
        return Path(root) / APPDATA_FOLDER_NAME
    return app_dir() / "data" / APPDATA_FOLDER_NAME


def files_data_dir() -> Path:
    configured = os.environ.get("REYLI_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return persistent_app_data_dir()


def webview_profile_dir() -> Path:
    configured = os.environ.get("REYLI_FILES_WEBVIEW_PROFILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return persistent_app_data_dir() / "webview-profile"


WEBVIEW_LOW_MEMORY_BROWSER_ARGS = (
    "--disable-background-networking",
    "--disable-component-extensions-with-background-pages",
    "--disable-extensions",
    "--disable-notifications",
    "--disable-speech-api",
    "--disable-sync",
    "--disk-cache-size=67108864",
    "--media-cache-size=16777216",
    "--renderer-process-limit=3",
)


def append_env_browser_args(name: str, args: tuple[str, ...]) -> None:
    existing = str(os.environ.get(name) or "").strip()
    parts = [part for part in existing.split() if part]
    seen = set(parts)
    for arg in args:
        if arg not in seen:
            parts.append(arg)
            seen.add(arg)
    if parts:
        os.environ[name] = " ".join(parts)


def configure_webview_runtime_environment() -> None:
    if sys.platform.startswith("win"):
        os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", str(webview_profile_dir()))
        append_env_browser_args("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", WEBVIEW_LOW_MEMORY_BROWSER_ARGS)
    elif sys.platform.startswith("linux"):
        append_env_browser_args("QTWEBENGINE_CHROMIUM_FLAGS", WEBVIEW_LOW_MEMORY_BROWSER_ARGS)


os.environ.setdefault("REYLI_CONFIG_FILE", "6ure-files-state.json")
os.environ.setdefault("REYLI_CONFIG_BACKUP_FILE", "6ure-files-state.backup.json")
os.environ.setdefault("REYLI_DATA_DIR", str(files_data_dir()))
os.environ.setdefault("REYLI_LEGACY_DATA_DIR", str(app_dir()))
configure_webview_runtime_environment()

import webview  # noqa: E402

from server import (  # noqa: E402
    create_server,
    get_app_auth_status,
    is_discord_oauth_url,
    stop_discord_presence,
    sync_leaker_proxy_cookies_from_webview,
)


APP_NAME = "6ure™ App"
APP_WIDTH = 860
APP_HEIGHT = 720
WEBVIEW_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)
MAC_WEBVIEW_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Apple Silicon Mac OS X 14_0) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
LEAKER_CLOUD_URL = "https://6ureleaks.com/dashboard/resources"
LEAKER_UPLOAD_URL = "https://6ureleaks.com/dashboard/upload"
LEAKER_HOST = "6ureleaks.com"
LEAKER_AUTH_TIMEOUT_SECONDS = 20 * 60
LEAKER_OAUTH_TIMEOUT_SECONDS = 10 * 60


def webview_gui() -> str | None:
    if sys.platform.startswith("win"):
        return "edgechromium"
    if sys.platform == "darwin":
        return "cocoa"
    return None


def webview_user_agent() -> str:
    return MAC_WEBVIEW_USER_AGENT if sys.platform == "darwin" else WEBVIEW_USER_AGENT


def leaker_control_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Leaker Mode</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      background: #080910;
      color: #f7f5ff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }
    body {
      display: grid;
      place-items: center;
      padding: 10px;
    }
    main {
      width: 100%;
      height: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border: 1px solid rgba(82, 247, 255, 0.22);
      border-radius: 8px;
      background:
        radial-gradient(circle at 10% 0%, rgba(82, 247, 255, 0.16), transparent 38%),
        linear-gradient(180deg, rgba(16, 19, 32, 0.96), rgba(7, 10, 18, 0.96));
      box-shadow: 0 16px 42px rgba(0, 0, 0, 0.46), 0 0 34px rgba(82, 247, 255, 0.08);
    }
    .copy {
      min-width: 0;
      display: grid;
      gap: 2px;
    }
    strong {
      font-size: 12px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    span {
      color: #9693b5;
      font-size: 10px;
      font-weight: 800;
      line-height: 1.25;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    button {
      min-height: 32px;
      padding: 7px 12px;
      border: 1px solid rgba(255, 93, 115, 0.28);
      border-radius: 7px;
      background: rgba(39, 11, 18, 0.9);
      color: #ff9cab;
      font: inherit;
      font-size: 11px;
      font-weight: 900;
      cursor: pointer;
    }
    button:hover {
      border-color: rgba(255, 143, 160, 0.38);
      background: rgba(66, 14, 27, 0.96);
    }
  </style>
</head>
<body>
  <main>
    <div class="copy">
      <strong>Leaker Mode</strong>
      <span>Leaker Dashboard is open.</span>
    </div>
    <button type="button" onclick="window.pywebview.api.exit_leaker_mode()">Exit</button>
  </main>
</body>
</html>"""


def safe_destroy_window(window) -> None:
    if not window:
        return
    try:
        if not window.events.closed.is_set():
            window.destroy()
    except Exception:
        pass


MEMORY_TRIM_MIN_INTERVAL_SECONDS = 6.0
_MEMORY_TRIM_LOCK = threading.Lock()
_MEMORY_TRIM_LAST_AT = 0.0


def windows_descendant_process_ids(root_pid: int | None = None) -> list[int]:
    if not sys.platform.startswith("win"):
        return []

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

    class ProcessEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if int(snapshot) == -1:
        return []

    children: dict[int, list[int]] = {}
    try:
        entry = ProcessEntry32()
        entry.dwSize = ctypes.sizeof(ProcessEntry32)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return []
        while True:
            pid = int(entry.th32ProcessID)
            parent_pid = int(entry.th32ParentProcessID)
            children.setdefault(parent_pid, []).append(pid)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)

    descendants: list[int] = []
    queue = [int(root_pid or os.getpid())]
    seen = set(queue)
    while queue:
        parent_pid = queue.pop(0)
        for child_pid in children.get(parent_pid, []):
            if child_pid in seen:
                continue
            seen.add(child_pid)
            descendants.append(child_pid)
            queue.append(child_pid)
    return descendants


def windows_trim_working_set(pid: int) -> bool:
    if not sys.platform.startswith("win"):
        return False

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(0x0400 | 0x0100, False, int(pid))
    if not handle:
        return False
    try:
        return bool(psapi.EmptyWorkingSet(handle))
    finally:
        kernel32.CloseHandle(handle)


def trim_app_memory(*, force: bool = False, reason: str = "") -> dict:
    global _MEMORY_TRIM_LAST_AT

    now = time.monotonic()
    with _MEMORY_TRIM_LOCK:
        if not force and now - _MEMORY_TRIM_LAST_AT < MEMORY_TRIM_MIN_INTERVAL_SECONDS:
            return {"success": True, "skipped": True, "reason": reason}
        _MEMORY_TRIM_LAST_AT = now

    collected = gc.collect()
    trimmed_children = 0
    trimmed_current = False

    if sys.platform.startswith("win"):
        trimmed_current = windows_trim_working_set(os.getpid())
        for pid in windows_descendant_process_ids():
            if windows_trim_working_set(pid):
                trimmed_children += 1
    elif sys.platform.startswith("linux"):
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            if hasattr(libc, "malloc_trim"):
                libc.malloc_trim(0)
                trimmed_current = True
        except Exception:
            trimmed_current = False

    return {
        "success": True,
        "skipped": False,
        "reason": reason,
        "collected": collected,
        "trimmedCurrent": trimmed_current,
        "trimmedChildren": trimmed_children,
    }


def schedule_memory_trim(delay: float = 0.75, *, reason: str = "", force: bool = False) -> None:
    def run_trim() -> None:
        try:
            trim_app_memory(force=force, reason=reason)
        except Exception:
            pass

    timer = threading.Timer(max(0.0, float(delay or 0)), run_trim)
    timer.daemon = True
    timer.start()


def is_leaker_dashboard_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return False
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    return host == LEAKER_HOST and parsed.path.lower().startswith("/dashboard")


def is_leaker_oauth_return_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return False
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    path = parsed.path.lower() or "/"
    return host == LEAKER_HOST and (
        path == "/"
        or path.startswith("/dashboard")
        or path.startswith("/requests/api/auth/discord/callback")
        or path.startswith("/api/auth/callback")
        or path.startswith("/requests/account")
    )


def is_leaker_window_authenticated(window, current_url: str) -> bool:
    if not is_leaker_dashboard_url(current_url):
        return False
    try:
        result = window.evaluate_js(
            """
            (() => {
              const text = (document.body ? document.body.innerText : '').toLowerCase();
              const hasPassword = Boolean(document.querySelector('input[type="password"]'));
              const hasLoginLink = Boolean(document.querySelector('a[href*="/login"], a[href*="/signin"], a[href*="/auth"]'));
              const hasLoginText = text.includes('sign in') || text.includes('log in') || text.includes('login');
              const hasDashboardShell = text.includes('cloud') || text.includes('upload') || text.includes('dashboard');
              return { loginSignals: hasPassword || hasLoginLink || (hasLoginText && !hasDashboardShell) };
            })()
            """
        )
        if isinstance(result, dict) and result.get("loginSignals"):
            return False
    except Exception:
        pass
    return True


class LeakerControlApi:
    def __init__(self, owner: "FilesWindowApi") -> None:
        self.owner = owner

    def exit_leaker_mode(self) -> dict:
        return self.owner.exit_leaker_mode()


class FilesWindowApi:
    def __init__(self) -> None:
        self.window = None
        self.maximized = False
        self._leaker_lock = threading.RLock()
        self._leaker_login_window = None
        self._leaker_cloud_window = None
        self._leaker_upload_window = None
        self._leaker_control_window = None
        self._leaker_oauth_window = None
        self._leaker_thread: threading.Thread | None = None
        self._leaker_oauth_thread: threading.Thread | None = None
        self._leaker_session_id = 0
        self._leaker_oauth_id = 0
        self._leaker_exiting = False
        self._leaker_status = {
            "phase": "idle",
            "message": "Leaker Mode is idle.",
            "active": False,
            "needsLogin": False,
            "updatedAt": int(time.time() * 1000),
        }
        self._leaker_oauth_status = {
            "phase": "idle",
            "message": "Discord OAuth is idle.",
            "active": False,
            "completed": False,
            "cancelled": False,
            "syncedCookies": 0,
            "updatedAt": int(time.time() * 1000),
        }

    def bind(self, window) -> None:
        self.window = window

    def window_action(self, action: str) -> None:
        if not self.window:
            return

        if action == "minimize":
            self.window.minimize()
            schedule_memory_trim(0.8, reason="window-minimized")
            return

        if action == "maximize":
            if self.maximized:
                self.window.restore()
            else:
                self.window.maximize()
            self.maximized = not self.maximized
            return

        if action == "close":
            try:
                self.exit_leaker_mode(restore_main=False)
            except Exception:
                pass
            safe_destroy_window(self.window)
            schedule_memory_trim(0.1, reason="window-closing", force=True)

    def select_folders(self) -> list[str]:
        if not self.window:
            return []
        try:
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=True)
            return [str(item) for item in result] if result else []
        except Exception:
            return []

    def select_folder(self) -> str:
        folders = self.select_folders()
        return folders[0] if folders else ""

    def _main_webview2_control(self):
        native = getattr(self.window, "native", None)
        for candidate in (
            getattr(native, "webview", None),
            getattr(getattr(native, "browser", None), "webview", None),
        ):
            if candidate is not None and getattr(candidate, "CoreWebView2", None) is not None:
                return candidate
        raise RuntimeError("Main WebView2 control is unavailable.")

    def _call_devtools_protocol(self, method_name: str, payload: dict, timeout: float = 12.0) -> dict:
        webview_control = self._main_webview2_control()
        result: dict = {"value": None, "error": None}
        done = threading.Semaphore(0)

        def run_on_ui_thread():
            try:
                from System import Action, Func, Object, String
                from System.Threading.Tasks import Task, TaskScheduler

                task = webview_control.CoreWebView2.CallDevToolsProtocolMethodAsync(
                    method_name,
                    json.dumps(payload or {}),
                )

                def on_complete(completed_task):
                    try:
                        result["value"] = completed_task.Result
                    except Exception as error:
                        result["error"] = error
                    finally:
                        done.release()

                task.ContinueWith(Action[Task[String]](on_complete), TaskScheduler.FromCurrentSynchronizationContext())
            except Exception as error:
                result["error"] = error
                done.release()
            return None

        try:
            from System import Func, Object

            webview_control.Invoke(Func[Object](run_on_ui_thread))
        except Exception as error:
            raise RuntimeError(f"WebView2 command could not be scheduled: {error}") from error

        if not done.acquire(timeout=timeout):
            raise TimeoutError(f"WebView2 DevTools command timed out: {method_name}")
        if result["error"] is not None:
            raise RuntimeError(f"WebView2 DevTools command failed: {result['error']}") from result["error"]

        try:
            return json.loads(result["value"] or "{}")
        except Exception:
            return {}

    def _select_webview_upload_paths(self, payload: dict) -> tuple[list[str], str, int]:
        if not self.window:
            return [], "", 0

        directory = bool(payload.get("directory"))
        multiple = bool(payload.get("multiple")) or directory
        if directory:
            selected = self.window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
            if not selected:
                return [], "", 0
            root = Path(str(selected[0])).expanduser().resolve()
            file_count = 0
            for current_root, _, file_names in os.walk(root):
                for file_name in file_names:
                    file_path = Path(current_root) / file_name
                    try:
                        if file_path.is_file():
                            file_count += 1
                    except OSError:
                        continue
            return [str(root)], root.name, file_count

        selected = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=multiple)
        files = [str(Path(item).expanduser().resolve()) for item in selected] if selected else []
        return files, Path(files[0]).parent.name if files else "", len(files)

    def apply_webview_upload_selection(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            payload = {}
        input_id = str(payload.get("inputId") or "").strip()
        if not input_id.startswith("sixure-upload-"):
            raise ValueError("Upload input was not identified.")

        files, folder_name, file_count = self._select_webview_upload_paths(payload)
        if not files:
            return {"success": False, "cancelled": True}

        expression = f"""
        (() => {{
          const inputId = {json.dumps(input_id)};
          const selector = '[data-sixure-upload-input-id="' + String(inputId).replace(/["\\\\]/g, '\\\\$&') + '"]';
          for (const frameId of ['leakerUploadFrame', 'leakerLoginFrame', 'leakerCloudFrame']) {{
            const frame = document.getElementById(frameId);
            const doc = frame && frame.contentDocument;
            const input = doc && doc.querySelector(selector);
            if (input) {{
              input.__sixureNativeSelectionStartedAt = Date.now();
              return input;
            }}
          }}
          return null;
        }})()
        """
        evaluation = self._call_devtools_protocol(
            "Runtime.evaluate",
            {
                "expression": expression,
                "objectGroup": "sixureUpload",
                "includeCommandLineAPI": False,
                "returnByValue": False,
                "awaitPromise": False,
            },
        )
        remote_object = evaluation.get("result") if isinstance(evaluation, dict) else {}
        object_id = str((remote_object or {}).get("objectId") or "")
        if not object_id:
            raise RuntimeError("Upload input could not be found in Leaker Dashboard.")

        try:
            self._call_devtools_protocol("DOM.setFileInputFiles", {"objectId": object_id, "files": files}, timeout=30.0)
            self._call_devtools_protocol(
                "Runtime.evaluate",
                {
                    "expression": f"""
                    (() => {{
                      const inputId = {json.dumps(input_id)};
                      const selector = '[data-sixure-upload-input-id="' + String(inputId).replace(/["\\\\]/g, '\\\\$&') + '"]';
                      for (const frameId of ['leakerUploadFrame', 'leakerLoginFrame', 'leakerCloudFrame']) {{
                        const frame = document.getElementById(frameId);
                        const doc = frame && frame.contentDocument;
                        const input = doc && doc.querySelector(selector);
                        if (!input) continue;
                        if (Date.now() - Number(input.__sixureLastNativeChangeAt || 0) > 700) {{
                          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                          input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                        return true;
                      }}
                      return false;
                    }})()
                    """,
                    "returnByValue": True,
                    "awaitPromise": False,
                },
            )
        finally:
            try:
                self._call_devtools_protocol("Runtime.releaseObjectGroup", {"objectGroup": "sixureUpload"})
            except Exception:
                pass

        return {
            "success": True,
            "applied": True,
            "count": file_count or len(files),
            "folderName": folder_name,
        }

    def _set_leaker_status(self, phase: str, message: str, *, active: bool = False, needs_login: bool = False) -> dict:
        with self._leaker_lock:
            self._leaker_status = {
                "phase": phase,
                "message": message,
                "active": active,
                "needsLogin": needs_login,
                "updatedAt": int(time.time() * 1000),
            }
            return dict(self._leaker_status)

    def leaker_status(self) -> dict:
        with self._leaker_lock:
            status = dict(self._leaker_status)
            cloud_open = bool(self._leaker_cloud_window and not self._leaker_cloud_window.events.closed.is_set())
            upload_open = bool(self._leaker_upload_window and not self._leaker_upload_window.events.closed.is_set())
            control_open = bool(self._leaker_control_window and not self._leaker_control_window.events.closed.is_set())
            login_open = bool(self._leaker_login_window and not self._leaker_login_window.events.closed.is_set())
        if status.get("phase") == "active" and not (cloud_open or upload_open):
            return self._set_leaker_status("idle", "Leaker Mode windows were closed.")
        status.update(
            {
                "success": True,
                "cloudOpen": cloud_open,
                "uploadOpen": upload_open,
                "controlOpen": control_open,
                "loginOpen": login_open,
                "cloudUrl": LEAKER_CLOUD_URL,
                "uploadUrl": LEAKER_UPLOAD_URL,
            }
        )
        return status

    def _set_leaker_oauth_status(
        self,
        phase: str,
        message: str,
        *,
        active: bool = False,
        completed: bool = False,
        cancelled: bool = False,
        synced_cookies: int = 0,
    ) -> dict:
        with self._leaker_lock:
            self._leaker_oauth_status = {
                "phase": phase,
                "message": message,
                "active": active,
                "completed": completed,
                "cancelled": cancelled,
                "syncedCookies": int(synced_cookies or 0),
                "updatedAt": int(time.time() * 1000),
            }
            return dict(self._leaker_oauth_status)

    def leaker_oauth_status(self) -> dict:
        with self._leaker_lock:
            status = dict(self._leaker_oauth_status)
            window_open = bool(self._leaker_oauth_window and not self._leaker_oauth_window.events.closed.is_set())
            thread_alive = bool(self._leaker_oauth_thread and self._leaker_oauth_thread.is_alive())
            if status.get("active") and not window_open and not status.get("completed") and not thread_alive:
                status = self._set_leaker_oauth_status(
                    "cancelled",
                    "Discord OAuth window was closed.",
                    cancelled=True,
                )
                window_open = False
        status.update({"success": True, "windowOpen": window_open})
        return status

    def open_leaker_oauth(self, url: str) -> dict:
        clean_url = str(url or "").strip()
        if not is_discord_oauth_url(clean_url):
            raise ValueError("Only Discord OAuth URLs can be opened separately.")

        with self._leaker_lock:
            existing = self._leaker_oauth_window
            if existing and not existing.events.closed.is_set():
                try:
                    existing.restore()
                except Exception:
                    pass
                return self.leaker_oauth_status()

            self._leaker_oauth_id += 1
            oauth_id = self._leaker_oauth_id
            self._leaker_oauth_status = {
                "phase": "opening",
                "message": "Opening Discord OAuth in a separate window.",
                "active": True,
                "completed": False,
                "cancelled": False,
                "syncedCookies": 0,
                "updatedAt": int(time.time() * 1000),
            }
            self._leaker_oauth_thread = threading.Thread(
                target=self._run_leaker_oauth,
                args=(oauth_id, clean_url),
                daemon=True,
            )
            self._leaker_oauth_thread.start()

        return self.leaker_oauth_status()

    def _is_current_leaker_oauth(self, oauth_id: int) -> bool:
        with self._leaker_lock:
            return self._leaker_oauth_id == oauth_id

    def _run_leaker_oauth(self, oauth_id: int, url: str) -> None:
        oauth_window = None
        returned_at = None
        try:
            oauth_window = webview.create_window(
                "Discord OAuth",
                url,
                width=900,
                height=760,
                min_size=(620, 520),
                resizable=True,
                frameless=False,
                easy_drag=False,
                background_color="#080910",
                text_select=True,
            )
            with self._leaker_lock:
                if not self._is_current_leaker_oauth(oauth_id):
                    safe_destroy_window(oauth_window)
                    return
                self._leaker_oauth_window = oauth_window

            self._set_leaker_oauth_status(
                "waiting",
                "Complete Discord OAuth in the separate window.",
                active=True,
            )

            deadline = time.monotonic() + LEAKER_OAUTH_TIMEOUT_SECONDS
            while time.monotonic() < deadline and self._is_current_leaker_oauth(oauth_id):
                if oauth_window.events.closed.is_set():
                    self._set_leaker_oauth_status(
                        "cancelled",
                        "Discord OAuth window was closed.",
                        cancelled=True,
                    )
                    return

                try:
                    current_url = oauth_window.get_current_url() or ""
                except Exception:
                    current_url = ""

                if is_leaker_oauth_return_url(current_url):
                    if returned_at is None:
                        returned_at = time.monotonic()
                    if time.monotonic() - returned_at >= 1.0:
                        sync_deadline = time.monotonic() + 20.0
                        synced_cookies = 0
                        self._set_leaker_oauth_status(
                            "syncing",
                            "Discord OAuth finished. Syncing 6ureleaks.com session.",
                            active=True,
                            synced_cookies=synced_cookies,
                        )
                        while time.monotonic() < sync_deadline and self._is_current_leaker_oauth(oauth_id):
                            if oauth_window.events.closed.is_set():
                                break
                            try:
                                synced_cookies = max(
                                    synced_cookies,
                                    sync_leaker_proxy_cookies_from_webview(oauth_window.get_cookies()),
                                )
                            except Exception:
                                pass
                            try:
                                auth_status = get_app_auth_status(refresh=True)
                            except Exception:
                                auth_status = {}
                            if auth_status.get("authenticated"):
                                self._set_leaker_oauth_status(
                                    "completed",
                                    "Discord OAuth completed. Returning to Leaker Mode.",
                                    completed=True,
                                    synced_cookies=synced_cookies,
                                )
                                time.sleep(0.35)
                                safe_destroy_window(oauth_window)
                                return
                            self._set_leaker_oauth_status(
                                "syncing",
                                "Discord OAuth finished. Syncing 6ureleaks.com session.",
                                active=True,
                                synced_cookies=synced_cookies,
                            )
                            time.sleep(0.75)
                        self._set_leaker_oauth_status(
                            "completed",
                            "Discord OAuth finished. Waiting for 6ureleaks.com session verification.",
                            completed=True,
                            synced_cookies=synced_cookies,
                        )
                        time.sleep(0.35)
                        safe_destroy_window(oauth_window)
                        return
                else:
                    returned_at = None

                time.sleep(0.35)

            if self._is_current_leaker_oauth(oauth_id):
                self._set_leaker_oauth_status(
                    "timeout",
                    "Discord OAuth timed out.",
                    cancelled=True,
                )
                safe_destroy_window(oauth_window)
        except Exception as error:
            if self._is_current_leaker_oauth(oauth_id):
                self._set_leaker_oauth_status(
                    "error",
                    f"Discord OAuth could not be opened: {error}",
                    cancelled=True,
                )
        finally:
            with self._leaker_lock:
                if self._leaker_oauth_window is oauth_window:
                    self._leaker_oauth_window = None

    def start_leaker_mode(self) -> dict:
        self._set_leaker_status(
            "ready",
            "Leaker Mode is handled inside the main 6ure™ App window.",
            needs_login=False,
        )
        return self.leaker_status()
        with self._leaker_lock:
            phase = self._leaker_status.get("phase")
            if phase in {"authenticating", "ready", "launching"}:
                return self.leaker_status()
            if phase == "active":
                self._focus_leaker_windows()
                return self.leaker_status()
            self._leaker_session_id += 1
            session_id = self._leaker_session_id
            self._leaker_exiting = False
            self._leaker_status = {
                "phase": "authenticating",
            "message": "Checking your 6ureleaks.com Leaker Dashboard session.",
                "active": False,
                "needsLogin": True,
                "updatedAt": int(time.time() * 1000),
            }
            self._leaker_thread = threading.Thread(target=self._run_leaker_auth_flow, args=(session_id,), daemon=True)
            self._leaker_thread.start()
        return self.leaker_status()

    def launch_leaker_mode(self) -> dict:
        self._set_leaker_status(
            "active",
            "Leaker Mode is active inside the main 6ure™ App window.",
            active=True,
            needs_login=False,
        )
        return self.leaker_status()
        with self._leaker_lock:
            phase = self._leaker_status.get("phase")
            if phase == "active":
                self._focus_leaker_windows()
                return self.leaker_status()
            if phase != "ready":
                return self.leaker_status()
            self._leaker_status = {
                "phase": "launching",
                "message": "Opening the Leaker Dashboard.",
                "active": False,
                "needsLogin": False,
                "updatedAt": int(time.time() * 1000),
            }

        threading.Thread(target=self._open_leaker_windows, daemon=True).start()
        return self.leaker_status()

    def trim_webview_memory(self, reason: str = "manual") -> dict:
        return trim_app_memory(force=True, reason=reason)

    def exit_leaker_mode(self, *, restore_main: bool = True) -> dict:
        with self._leaker_lock:
            self._leaker_exiting = True
            self._leaker_oauth_id += 1
            windows = [
                self._leaker_login_window,
                self._leaker_cloud_window,
                self._leaker_upload_window,
                self._leaker_control_window,
                self._leaker_oauth_window,
            ]
            self._leaker_login_window = None
            self._leaker_cloud_window = None
            self._leaker_upload_window = None
            self._leaker_control_window = None
            self._leaker_oauth_window = None
            self._leaker_status = {
                "phase": "idle",
                "message": "Leaker Mode is idle.",
                "active": False,
                "needsLogin": False,
                "updatedAt": int(time.time() * 1000),
            }
            self._leaker_oauth_status = {
                "phase": "idle",
                "message": "Discord OAuth is idle.",
                "active": False,
                "completed": False,
                "cancelled": False,
                "syncedCookies": 0,
                "updatedAt": int(time.time() * 1000),
            }

        for window in windows:
            safe_destroy_window(window)
        if restore_main:
            try:
                if self.window and not self.window.events.closed.is_set():
                    self.window.restore()
            except Exception:
                pass
        schedule_memory_trim(0.6, reason="leaker-mode-exit", force=True)
        return self.leaker_status()

    def _is_current_leaker_session(self, session_id: int) -> bool:
        with self._leaker_lock:
            return not self._leaker_exiting and self._leaker_session_id == session_id

    def _run_leaker_auth_flow(self, session_id: int) -> None:
        login_window = None
        try:
            login_window = webview.create_window(
                "6ure Leaker Login",
                LEAKER_UPLOAD_URL,
                width=1120,
                height=760,
                min_size=(760, 540),
                resizable=True,
                background_color="#080910",
                text_select=True,
                focus=True,
            )
            if not login_window:
                raise RuntimeError("Login window could not be opened.")
            with self._leaker_lock:
                if not self._is_current_leaker_session(session_id):
                    safe_destroy_window(login_window)
                    return
                self._leaker_login_window = login_window

            self._set_leaker_status(
                "authenticating",
                "Sign in to 6ureleaks.com inside 6ure™ App. Leaker Mode will continue after login.",
                needs_login=True,
            )

            deadline = time.monotonic() + LEAKER_AUTH_TIMEOUT_SECONDS
            while time.monotonic() < deadline and self._is_current_leaker_session(session_id):
                if login_window.events.closed.is_set():
                    self._set_leaker_status("idle", "Leaker Mode login was cancelled.")
                    return
                current_url = ""
                try:
                    current_url = login_window.get_current_url() or ""
                except Exception:
                    current_url = ""
                if is_leaker_window_authenticated(login_window, current_url):
                    safe_destroy_window(login_window)
                    with self._leaker_lock:
                        if self._leaker_login_window is login_window:
                            self._leaker_login_window = None
                    self._set_leaker_status(
                        "ready",
                        "6ureleaks.com session is ready. Starting Leaker Mode.",
                        needs_login=False,
                    )
                    return
                time.sleep(0.8)

            if self._is_current_leaker_session(session_id):
                self._set_leaker_status("idle", "Leaker Mode login timed out.")
        except Exception as error:
            if self._is_current_leaker_session(session_id):
                self._set_leaker_status("error", f"Leaker Mode could not start: {error}")
        finally:
            with self._leaker_lock:
                if self._leaker_login_window is login_window and login_window and login_window.events.closed.is_set():
                    self._leaker_login_window = None

    def _leaker_layout(self) -> dict:
        screen = webview.screens[0] if webview.screens else None
        if not screen:
            return {"x": 60, "y": 80, "pane_width": 860, "pane_height": 760, "control_x": 740, "control_y": 12}
        frame = getattr(screen, "frame", None)
        x = int(getattr(frame, "X", getattr(screen, "x", 0)))
        y = int(getattr(frame, "Y", getattr(screen, "y", 0)))
        width = int(getattr(frame, "Width", getattr(screen, "width", 1920)))
        height = int(getattr(frame, "Height", getattr(screen, "height", 1080)))
        margin = 14
        gap = 10
        control_height = 70
        pane_width = max(640, int((width - (margin * 2) - gap) / 2))
        pane_height = max(620, height - control_height - margin)
        pane_y = y + control_height
        return {
            "x": x + margin,
            "y": pane_y,
            "pane_width": pane_width,
            "pane_height": pane_height,
            "right_x": x + margin + pane_width + gap,
            "control_x": x + max(margin, int((width - 360) / 2)),
            "control_y": y + 8,
        }

    def _open_leaker_windows(self) -> None:
        try:
            self._close_leaker_dashboard_windows()
            layout = self._leaker_layout()
            cloud_window = webview.create_window(
                "6ure Leaker Mode - Cloud",
                LEAKER_CLOUD_URL,
                width=layout["pane_width"],
                height=layout["pane_height"],
                x=layout["x"],
                y=layout["y"],
                min_size=(620, 520),
                resizable=True,
                background_color="#080910",
                text_select=True,
                focus=True,
            )
            upload_window = webview.create_window(
                "6ure Leaker Mode - Upload",
                LEAKER_UPLOAD_URL,
                width=layout["pane_width"],
                height=layout["pane_height"],
                x=layout["right_x"],
                y=layout["y"],
                min_size=(620, 520),
                resizable=True,
                background_color="#080910",
                text_select=True,
                focus=True,
            )
            control_window = webview.create_window(
                "Leaker Mode",
                html=leaker_control_html(),
                js_api=LeakerControlApi(self),
                width=360,
                height=70,
                x=layout["control_x"],
                y=layout["control_y"],
                min_size=(320, 64),
                resizable=False,
                frameless=False,
                easy_drag=True,
                on_top=True,
                background_color="#080910",
                text_select=False,
                focus=False,
            )

            with self._leaker_lock:
                self._leaker_cloud_window = cloud_window
                self._leaker_upload_window = upload_window
                self._leaker_control_window = control_window
                self._leaker_status = {
                    "phase": "active",
                    "message": "Leaker Mode is active.",
                    "active": True,
                    "needsLogin": False,
                    "updatedAt": int(time.time() * 1000),
                }

            try:
                if self.window and not self.window.events.closed.is_set():
                    self.window.minimize()
            except Exception:
                pass
        except Exception as error:
            self._set_leaker_status("error", f"Leaker Mode windows could not be opened: {error}")

    def _focus_leaker_windows(self) -> None:
        for window in (self._leaker_cloud_window, self._leaker_upload_window, self._leaker_control_window):
            try:
                if window and not window.events.closed.is_set():
                    window.restore()
            except Exception:
                pass

    def _close_leaker_dashboard_windows(self) -> None:
        with self._leaker_lock:
            windows = [self._leaker_cloud_window, self._leaker_upload_window, self._leaker_control_window]
            self._leaker_cloud_window = None
            self._leaker_upload_window = None
            self._leaker_control_window = None
        for window in windows:
            safe_destroy_window(window)
        schedule_memory_trim(0.6, reason="leaker-dashboard-closed", force=True)


def start_http_server():
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def wait_for_server(port: int, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.4) as response:
                if response.status == 200:
                    return
        except Exception as error:
            last_error = error
            time.sleep(0.05)

    raise RuntimeError(f"Local server did not start: {last_error}")


def fallback_connection_html(reason: str = "") -> str:
    clean_reason = html.escape(str(reason or "Local service is unavailable."))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>6ure™ App</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      background:
        radial-gradient(circle at 50% 18%, rgba(82, 247, 255, 0.13), transparent 34%),
        radial-gradient(circle at 78% 24%, rgba(139, 92, 246, 0.1), transparent 30%),
        #080910;
      color: #f7f5ff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }}
    body {{
      display: grid;
      place-items: center;
      padding: 18px;
    }}
    .card {{
      width: min(460px, 100%);
      display: grid;
      justify-items: center;
      gap: 14px;
      padding: 22px;
      border: 1px solid rgba(82, 247, 255, 0.22);
      border-radius: 10px;
      background:
        radial-gradient(circle at 50% 0%, rgba(82, 247, 255, 0.12), transparent 38%),
        linear-gradient(180deg, rgba(16, 19, 32, 0.98), rgba(7, 10, 18, 0.98));
      box-shadow: 0 28px 86px rgba(0, 0, 0, 0.5), 0 0 44px rgba(82, 247, 255, 0.08);
      text-align: center;
      animation: cardIn 420ms cubic-bezier(0.2, 0.86, 0.2, 1) both;
    }}
    .mark {{
      width: 58px;
      height: 58px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(82, 247, 255, 0.24);
      border-radius: 12px;
      background: rgba(82, 247, 255, 0.08);
      color: #b8faff;
      box-shadow: 0 0 30px rgba(82, 247, 255, 0.14);
    }}
    .mark svg {{ width: 30px; height: 30px; }}
    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      font-weight: 950;
    }}
    p {{
      margin: 0;
      color: #9693b5;
      font-size: 12px;
      font-weight: 800;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }}
    button {{
      min-height: 38px;
      padding: 8px 16px;
      border: 1px solid rgba(82, 247, 255, 0.28);
      border-radius: 8px;
      background: linear-gradient(135deg, rgba(24, 26, 44, 0.94), rgba(82, 247, 255, 0.2));
      color: #f7f5ff;
      font: inherit;
      font-size: 12px;
      font-weight: 900;
      cursor: pointer;
    }}
    @keyframes cardIn {{
      from {{ opacity: 0; transform: translateY(14px) scale(0.96); }}
      to {{ opacity: 1; transform: none; }}
    }}
  </style>
</head>
<body>
  <main class="card">
    <div class="mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M5 9.8A10.7 10.7 0 0 1 12 7.2c2.6 0 5 .9 7 2.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
        <path d="M8.2 13.2A6.2 6.2 0 0 1 12 12c1.4 0 2.7.4 3.8 1.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
        <path d="M10.8 16.5a2.1 2.1 0 0 1 2.4 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
        <path d="M5 19 19 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
      </svg>
    </div>
    <h1>Connection unavailable</h1>
    <p>6ure™ App could not open its local app screen. Check your connection or restart the app.</p>
    <p>{clean_reason}</p>
    <button type="button" onclick="location.reload()">Retry</button>
  </main>
</body>
</html>"""


def main() -> None:
    server = None
    startup_error: Exception | None = None
    try:
        server = start_http_server()
        wait_for_server(server.server_port)
    except Exception as error:
        startup_error = error

    api = FilesWindowApi()
    url = f"http://127.0.0.1:{server.server_port}/" if server and startup_error is None else None

    window = webview.create_window(
        APP_NAME,
        url,
        html=fallback_connection_html(str(startup_error)) if startup_error is not None else None,
        width=APP_WIDTH,
        height=APP_HEIGHT,
        min_size=(620, 520),
        frameless=False,
        easy_drag=False,
        resizable=True,
        background_color="#080910",
        text_select=False,
    )
    api.bind(window)
    if server is not None:
        setattr(server, "window_bridge", api)

    profile_dir = webview_profile_dir()
    profile_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(profile_dir)

    try:
        start_options = {
            "debug": False,
            "private_mode": False,
            "storage_path": str(profile_dir),
            "user_agent": webview_user_agent(),
        }
        gui = webview_gui()
        if gui:
            start_options["gui"] = gui
        schedule_memory_trim(2.5, reason="startup")
        schedule_memory_trim(12.0, reason="startup-settled")
        webview.start(**start_options)
    finally:
        try:
            api.exit_leaker_mode(restore_main=False)
        except Exception:
            pass
        trim_app_memory(force=True, reason="shutdown")
        if server is not None:
            server.shutdown()
        stop_discord_presence()


if __name__ == "__main__":
    main()
