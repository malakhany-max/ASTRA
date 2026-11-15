"""Start the complete local ASTRA demo and open its two browser apps."""

from __future__ import annotations

import asyncio
import ctypes
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import psutil


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


ROOT = bundle_root()
FRONTEND = ROOT / "frontend" if (ROOT / "frontend").is_dir() else ROOT
BACKEND = ROOT / "backend" if (ROOT / "backend").is_dir() else ROOT
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ASTRA Companion"
LOG = DATA / "launcher.log"
# Concurrent imports of astra_security can deadlock at startup.
_BACKEND_IMPORT_LOCK = threading.Lock()
_NULL_STREAM = open(os.devnull, "w", encoding="utf-8")
if sys.stdout is None:
    sys.stdout = _NULL_STREAM
if sys.stderr is None:
    sys.stderr = _NULL_STREAM


class LoopbackHTTPServer(ThreadingHTTPServer):
    """Skip HTTPServer's reverse-DNS server_name lookup, which stalls offline."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class SpaHandler(SimpleHTTPRequestHandler):
    """Serve a built app and return its entry page for client-side routes."""

    app_mode = "astronaut"

    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def _proxy(self) -> bool:
        """Forward API calls through the app origin so WebView CORS cannot block them."""
        from urllib.error import HTTPError

        path = self.path
        if path == "/__astra/local-session":
            return False
        if path.startswith("/api/companion/"):
            upstream = "http://127.0.0.1:8200" + path.replace("/api", "", 1)
        elif path.startswith("/link/"):
            upstream = "http://127.0.0.1:8300" + path
        elif path.startswith(("/auth/", "/api/commands")) or (
            self.app_mode == "ground" and path.startswith(("/api/crew", "/api/astronauts/", "/api/alerts", "/api/link/state", "/api/backup/state", "/api/security/state"))
        ):
            upstream = "http://127.0.0.1:8100" + path
        elif path.startswith(("/api/", "/demo/")):
            upstream = "http://127.0.0.1:8000" + path
        else:
            return False

        body = None
        if self.command in {"POST", "PUT", "PATCH", "DELETE"}:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items()
                   if key.lower() not in {"host", "connection", "content-length", "transfer-encoding", "accept-encoding"}}
        request = Request(upstream, data=body, headers=headers, method=self.command)
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as exc:
            response = exc
        except Exception as exc:
            _log(f"API proxy failed: {self.command} {path} -> {upstream}: {type(exc).__name__}: {exc}")
            payload = json.dumps({"error": f"Local ASTRA service unavailable for {path}: {type(exc).__name__}: {exc}"}).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return True
        with response:
            payload = response.read()
            if response.status >= 400:
                _log(f"API proxy: {self.command} {path} -> {upstream} [{response.status}]")
            self.send_response(response.status)
            for key, value in response.headers.items():
                if key.lower() not in {"connection", "transfer-encoding", "content-length", "content-encoding", "access-control-allow-origin"}:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        return True

    def end_headers(self):
        if self.path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        elif self.path in {"/", "/index.html"}:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if self._proxy():
            return
        if self.path == "/__astra/local-session":
            with _BACKEND_IMPORT_LOCK:
                from astra_security.rbac import create_session
            role = "flight_surgeon" if self.app_mode == "ground" else "astronaut"
            principal = {"username": f"local-{self.app_mode}", "role": role,
                         "astronaut_id": "A-07" if role == "astronaut" else None}
            body = json.dumps({"access_token": create_session(principal), "token_type": "bearer"}).encode()
            _log(f"Local session issued: mode={self.app_mode}, role={role}.")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        candidate = Path(self.translate_path(self.path))
        if not candidate.is_file() and not self.path.startswith(("/api/", "/assets/")):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if not self._proxy():
            self.send_error(404)

    def do_PUT(self):
        if not self._proxy():
            self.send_error(404)

    def do_DELETE(self):
        if not self._proxy():
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", f"http://127.0.0.1:{5174 if self.app_mode == 'ground' else 5173}")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def log_message(self, _format: str, *_args) -> None:
        pass


def _port_available(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def _start_web_apps() -> list[ThreadingHTTPServer]:
    apps = (("web-astronaut", 5173), ("web-ground", 5174))
    servers = []
    for app, port in apps:
        directory = FRONTEND / app / "dist"
        if not directory.is_dir():
            raise FileNotFoundError(f"Built web app is missing: {directory}")
        if not _port_available(port):
            raise RuntimeError(f"Port {port} is already in use. Close the other ASTRA instance and retry.")
        app_handler = type(f"{app.replace('-', '_')}Handler", (SpaHandler,),
                           {"app_mode": "ground" if app == "web-ground" else "astronaut"})
        handler = partial(app_handler, directory=str(directory))
        server = LoopbackHTTPServer(("127.0.0.1", port), handler)
        threading.Thread(target=server.serve_forever, name=f"astra-{app}", daemon=True).start()
        servers.append(server)
    return servers


def _require_service_ports_free() -> None:
    busy = [port for port in (8000, 8100, 8200, 8300) if not _port_available(port)]
    if busy:
        raise RuntimeError(
            "ASTRA could not start its local services because these ports are already in use: "
            + ", ".join(map(str, busy))
            + ". Close the other program using them and relaunch."
        )


def _edge_path() -> Path | None:
    override = os.environ.get("ASTRA_EDGE_PATH")
    candidates = [Path(override)] if override else []
    for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if root:
            candidates.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _app_mode() -> tuple[str, int, str]:
    executable = Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).stem.lower()
    if "ground" in executable or os.environ.get("ASTRA_APP_MODE", "").lower() == "ground":
        return "ground", 5174, "Ground Station"
    return "astronaut", 5173, "Astronaut App"


def _create_service_mutex() -> tuple[int, bool]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, True, "Local\\ASTRACompanionServices-v1")
    if not handle:
        raise OSError("Could not create the ASTRA service coordinator.")
    already_exists = ctypes.get_last_error() == 183
    return int(handle), not already_exists


def _wait_for_services(timeout: float = 90.0, backend_thread: threading.Thread | None = None,
                        backend_error: list[str] | None = None, owner_alive: bool = True) -> None:
    endpoints = ((8000, "/health"), (8100, "/health"), (8200, "/health"),
                 (8300, "/link/state"), (5173, "/"), (5174, "/"))
    started = time.monotonic()
    deadline = started + timeout
    while time.monotonic() < deadline:
        ready = True
        if backend_error:
            raise RuntimeError(backend_error[0])
        if backend_thread is not None and not backend_thread.is_alive():
            detail = backend_error[0] if backend_error else "The ASTRA backend stopped during startup."
            raise RuntimeError(detail)
        if owner_alive and time.monotonic() - started > 6 and not _other_instances_running():
            raise RuntimeError("The other ASTRA instance closed before its shared services became ready. "
                               "Launch either app again; it will start the services itself.")
        for port, path in endpoints:
            if _port_available(port):
                ready = False
                break
            try:
                with urlopen(f"http://127.0.0.1:{port}{path}", timeout=2.0) as response:
                    if response.status != 200:
                        ready = False
                        break
            except Exception:
                ready = False
                break
        if ready:
            return
        time.sleep(0.35)
    raise RuntimeError("ASTRA's shared services did not become ready in time.")


def _open_app_window(edge: Path, mode: str, port: int) -> subprocess.Popen:
    profile = DATA / "edge-profiles" / f"{mode}-{os.getpid()}"
    profile.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [str(edge), f"--app=http://127.0.0.1:{port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "--disable-background-mode",
         "--disable-background-networking", "--disable-component-update", "--disable-sync",
         "--disable-extensions", "--disable-default-apps"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True,
    )


def _other_instances_running() -> bool:
    for marker in DATA.glob("active-*.pid"):
        try:
            pid = int(marker.stem.removeprefix("active-"))
            if pid == os.getpid():
                continue
            process = psutil.Process(pid)
            if process.name().lower().startswith(("astronaut", "groundstation")):
                return True
        except psutil.NoSuchProcess:
            marker.unlink(missing_ok=True)
        except (ValueError, psutil.AccessDenied, psutil.ZombieProcess, OSError, SystemError) as exc:
            _log(f"Could not verify launcher lease {marker.name}: {type(exc).__name__}: {exc}")
            return True
        else:
            marker.unlink(missing_ok=True)
    return False


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "ASTRA Companion", 0x10 | 0x1000)
    except Exception:
        pass


def _log(message: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def main() -> None:
    servers: list[ThreadingHTTPServer] = []
    app_process: subprocess.Popen | None = None
    mutex = 0
    owns_services = False
    lease: Path | None = None
    backend_thread: threading.Thread | None = None
    backend_error: list[str] = []
    started = time.monotonic()

    def phase(name: str) -> None:
        _log(f"[startup +{int((time.monotonic() - started) * 1000)} ms] {name}")
    try:
        phase("main entered")
        DATA.mkdir(parents=True, exist_ok=True)
        mode, port, app_name = _app_mode()
        lease = DATA / f"active-{os.getpid()}.pid"
        lease.write_text(mode, encoding="ascii")
        if not BACKEND.joinpath("config", "ports.yaml").is_file():
            raise RuntimeError("ASTRA app resources are missing from this build.")
        edge = _edge_path()
        if edge is None:
            raise RuntimeError("Microsoft Edge is required to show ASTRA's standalone app windows.")

        mutex, owns_services = _create_service_mutex()

        os.environ["ASTRA_ROOT"] = str(BACKEND)
        os.environ["ASTRA_PROJECT"] = str(ROOT)
        os.environ.setdefault("ASTRA_KEYS_DIR", str(DATA / "keys"))
        os.environ.setdefault("ASTRA_DB", str(DATA / "security.db"))
        os.environ.setdefault("ASTRA_HUB_DB", str(DATA / "hub.db"))
        os.environ.setdefault("ASTRA_HUB_BACKUP", str(DATA / "hub.backup.enc"))
        os.environ.setdefault("ASTRA_GROUND_DB", str(DATA / "ground.db"))
        os.environ.setdefault("ASTRA_GROUND_BACKUP", str(DATA / "ground.backup.enc"))
        os.environ.setdefault("ASTRA_LINK_DB", str(DATA / "link.db"))

        phase("paths and edge resolved")
        if owns_services:
            _require_service_ports_free()
            servers = _start_web_apps()
        phase("web servers ready")
        app_process = _open_app_window(edge, mode, port)
        phase("window opened")
        if owns_services:
            sys.path.insert(0, str(BACKEND / "simulators"))
            with _BACKEND_IMPORT_LOCK:
                from run_demo import _serve
            phase("backend imports done")

            def run_backends() -> None:
                try:
                    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
                    asyncio.run(_serve(), loop_factory=loop_factory)
                except BaseException as exc:
                    message = f"ASTRA backend startup failed: {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                    backend_error.append(message)
                    _log(message)
            backend_thread = threading.Thread(target=run_backends, name="astra-backends", daemon=True)
            backend_thread.start()
        _wait_for_services(backend_thread=backend_thread, backend_error=backend_error,
                           owner_alive=not owns_services)
        phase("services ready")
        _log(f"{app_name} opened in standalone mode; services owner={owns_services}.")

        if owns_services:
            idle_since: float | None = None
            while True:
                own_window_open = app_process.poll() is None
                another_app_open = _other_instances_running()
                if own_window_open or another_app_open:
                    idle_since = None
                elif idle_since is None:
                    idle_since = time.monotonic()
                elif time.monotonic() - idle_since >= 2.0:
                    break
                time.sleep(0.5)
        else:
            while app_process.poll() is None:
                time.sleep(0.5)
    except Exception as exc:
        if app_process is not None and app_process.poll() is None:
            app_process.terminate()
        _log(f"Startup error: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        _show_error(f"ASTRA could not start.\n\n{exc}\n\nDetails: {LOG}")
    finally:
        if app_process is not None and app_process.poll() is None:
            try:
                app_process.terminate()
            except OSError as exc:
                _log(f"Could not close the app window process: {exc}")
        for server in servers:
            try:
                server.shutdown()
            except Exception as exc:
                _log(f"Could not stop the local web server: {type(exc).__name__}: {exc}")
        if lease is not None:
            try:
                lease.unlink(missing_ok=True)
            except OSError as exc:
                _log(f"Could not clear launcher lease {lease.name}: {exc}")
        if mutex:
            try:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                if owns_services:
                    kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
                    if not kernel32.ReleaseMutex(mutex):
                        _log(f"ReleaseMutex failed with Windows error {ctypes.get_last_error()}.")
                kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
                if not kernel32.CloseHandle(mutex):
                    _log(f"CloseHandle failed with Windows error {ctypes.get_last_error()}.")
            except Exception as exc:
                _log(f"Could not release the local service coordinator: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
