"""GrantFiller launcher and process supervisor (standard library only)."""
from __future__ import annotations

import argparse
import html
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler
import webbrowser
import zipfile

LOG = logging.getLogger("grantfiller.desktop")


def state_root() -> Path:
    override = os.environ.get("GRANTFILLER_DESKTOP_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "GrantFiller"
    return Path.home() / "Library" / "Application Support" / "GrantFiller"


def load_config(root: Path) -> dict:
    config = json.loads((root / "installation.json").read_text(encoding="utf-8"))
    for key in ("app_dir", "python", "install_id", "port", "ollama"):
        if key not in config:
            raise RuntimeError("Setup is incomplete. Run Setup again.")
    return config


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def request_json(url: str, body: dict | None = None, timeout: float = 3) -> dict:
    # Loopback traffic must not be routed through a corporate HTTP proxy.
    request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def api_url(config: dict) -> str:
    return f"http://127.0.0.1:{int(config['port'])}"


def server_ready(config: dict) -> bool:
    try:
        response = request_json(api_url(config) + "/api/v1/desktop/status")
        return (response.get("service") == "grantfiller-desktop"
                and response.get("install_id") == config["install_id"])
    except Exception:
        return False


def ollama_ready(config: dict) -> bool:
    try:
        return isinstance(request_json(config["ollama_url"] + "/api/tags").get("models"), list)
    except Exception:
        return False


def runtime_env(root: Path, config: dict) -> dict:
    env = os.environ.copy()
    data = root / "data"
    env.update({
        "DATA_DIR": str(data), "DATABASE_URL": f"sqlite+aiosqlite:///{data / 'grantfiller.db'}",
        "LLM_PROVIDER": "ollama", "LOCAL_ONLY": "true", "GOOGLE_API_KEY": "",
        "OLLAMA_BASE_URL": config["ollama_url"], "OLLAMA_MODEL": config["chat_model"],
        "OLLAMA_EMBED_MODEL": config["embed_model"], "ALLOW_REMOTE_ACCESS": "false",
        "PARSE_CHUNK_CONCURRENCY": "1", "GENERATE_QUESTION_CONCURRENCY": "1",
        "OLLAMA_NO_CLOUD": "1", "OLLAMA_HOST": "127.0.0.1:11434",
        "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1",
        "GRANTFILLER_INSTALL_ID": config["install_id"],
        "GRANTFILLER_UI_DIR": str(Path(config["app_dir"]) / "frontend" / "dist"),
        "PLAYWRIGHT_BROWSERS_PATH": str(root / "browsers"), "PYTHONUNBUFFERED": "1",
    })
    return env


def spawn(command: list[str], root: Path, config: dict, log_name: str) -> subprocess.Popen:
    log_path = root / "logs" / log_name
    if log_path.exists() and log_path.stat().st_size > 10_000_000:
        os.replace(log_path, log_path.with_suffix(".previous.log"))
    with log_path.open("a", encoding="utf-8") as stream:
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {"start_new_session": True}
        return subprocess.Popen(command, cwd=config["app_dir"], env=runtime_env(root, config),
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, **kwargs)


class InstanceLock:
    """OS releases this lock after a crash; stale PID files cannot block startup."""
    def __init__(self, path: Path):
        self.file = path.open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)

    def acquire(self) -> bool:
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def close(self) -> None:
        self.file.close()


def backup(root: Path) -> Path | None:
    """Run only before the backend starts, so files cannot change during a snapshot."""
    data = root / "data"
    source = data / "grantfiller.db"
    if not source.is_file():
        return None
    directory = root / "backups"
    directory.mkdir(exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    destination = directory / f"grantfiller-{today}.zip"
    if destination.exists():
        return destination
    database_copy = directory / "snapshot.db"
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(database_copy) as dst:
                src.backup(dst)
        temporary = destination.with_suffix(".partial")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(database_copy, "data/grantfiller.db")
            for path in data.rglob("*"):
                if path.is_file() and path.name not in {"grantfiller.db", "grantfiller.db-wal", "grantfiller.db-shm"}:
                    archive.write(path, str(Path("data") / path.relative_to(data)))
        os.replace(temporary, destination)
        # Retain the seven most recent snapshots created by this launcher.
        for old in sorted(directory.glob("grantfiller-????-??-??.zip"))[:-7]:
            old.unlink()
        return destination
    finally:
        database_copy.unlink(missing_ok=True)


def supervise(root: Path, config: dict) -> None:
    lock = InstanceLock(root / "supervisor.lock")
    if not lock.acquire():
        lock.close()
        return
    stop = root / "stop.signal"
    stop.unlink(missing_ok=True)
    running = True
    children: dict[str, subprocess.Popen] = {}
    next_start = {"backend": 0.0, "ollama": 0.0}
    failures = {"backend": 0, "ollama": 0}
    def end(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, end)
    signal.signal(signal.SIGINT, end)
    try:
        # Never back up an unrelated server's database or start a second backend.
        if server_ready(config):
            raise RuntimeError("A GrantFiller backend is already running outside its supervisor.")
        try:
            backup(root)
        except Exception:
            LOG.exception("Startup backup failed; continuing without this snapshot")
        while running and not stop.exists():
            now = time.monotonic()
            for name in ("ollama", "backend"):
                child = children.get(name)
                if child is not None and child.poll() is not None:
                    LOG.error("%s exited (%s); restarting", name, child.returncode)
                    del children[name]
                    failures[name] += 1
                    next_start[name] = now + min(30, 2 ** min(failures[name], 5))
                if name in children or now < next_start[name]:
                    continue
                if name == "ollama" and ollama_ready(config):
                    continue  # Reuse the user's installed Ollama; never kill it.
                command = ([config["ollama"], "serve"] if name == "ollama" else
                           [config["python"], str(Path(config["app_dir"]) / "desktop" / "launch.py"), "serve"])
                try:
                    children[name] = spawn(command, root, config, name + ".log")
                    LOG.info("Started %s (%s)", name, children[name].pid)
                except Exception:
                    LOG.exception("Unable to start %s", name)
                    next_start[name] = now + 15
            atomic_json(root / "runtime.json", {
                "supervisor_pid": os.getpid(), "backend_pid": children.get("backend").pid if children.get("backend") else None,
                "updated_at": time.time(), "url": api_url(config),
            })
            time.sleep(2)
    finally:
        # Terminate only processes started by this supervisor.
        for child in children.values():
            if child.poll() is None:
                child.terminate()
        for child in children.values():
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        (root / "runtime.json").unlink(missing_ok=True)
        lock.close()


def start_supervisor(root: Path, config: dict) -> None:
    python = Path(config["python"])
    if sys.platform == "win32":
        python = python.with_name("pythonw.exe")
    spawn([str(python), str(Path(config["app_dir"]) / "desktop" / "launch.py"),
           "supervise", "--state-dir", str(root)], root, config, "supervisor-console.log")


def show_start_page(root: Path, message: str, destination: str | None = None, refresh: bool = True) -> Path:
    path = root / "starting.html"
    meta = f'<meta http-equiv="refresh" content="0;url={html.escape(destination, quote=True)}">' if destination else ('<meta http-equiv="refresh" content="3">' if refresh else "")
    path.write_text(f'<!doctype html><html><head><meta charset="utf-8">{meta}<title>GrantFiller</title></head>'
                    '<body style="font:18px system-ui;max-width:650px;margin:12vh auto;padding:24px">'
                    f'<h1>GrantFiller</h1><p>{html.escape(message)}</p>'
                    '<p style="color:#666">You can close this tab. Saved work stays on this laptop.</p></body></html>', encoding="utf-8")
    return path


def open_app(root: Path, config: dict) -> None:
    if server_ready(config):
        webbrowser.open(api_url(config))
        return
    start_supervisor(root, config)
    page = show_start_page(root, "Starting your local grant assistant. This may take a moment.")
    webbrowser.open(page.as_uri())
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if server_ready(config):
            show_start_page(root, "GrantFiller is ready. Opening your workspace…", api_url(config))
            return
        time.sleep(1)
    show_start_page(root, "GrantFiller could not start. Run the Repair GrantFiller shortcut. "
                    f"If you need help, share the logs in {root / 'logs'}.", refresh=False)
    raise RuntimeError("Backend startup timed out. See logs.")


def stop_supervisor(root: Path) -> None:
    (root / "stop.signal").touch()
    deadline = time.monotonic() + 30
    while (root / "runtime.json").exists() and time.monotonic() < deadline:
        time.sleep(.5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("open", "supervise", "serve", "check", "stop", "backup"))
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    root = (args.state_dir or state_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    os.environ["GRANTFILLER_DESKTOP_HOME"] = str(root)
    LOG.setLevel(logging.INFO)
    handler = RotatingFileHandler(root / "logs" / "launcher.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    try:
        config = load_config(root)
        if args.action == "serve":
            os.environ.update(runtime_env(root, config))
            sys.path.insert(0, str(Path(config["app_dir"]) / "backend"))
            import uvicorn
            uvicorn.run("app.desktop_server:app", host="127.0.0.1", port=int(config["port"]),
                        reload=False, workers=1, access_log=False, loop="asyncio")
        elif args.action == "supervise":
            supervise(root, config)
        elif args.action == "open":
            open_app(root, config)
        elif args.action == "stop":
            stop_supervisor(root)
        elif args.action == "backup":
            stop_supervisor(root)
            try:
                print(backup(root))
            finally:
                start_supervisor(root, config)
        else:
            result = request_json(api_url(config) + "/api/v1/config")
            print(json.dumps(result, indent=2))
            return 0 if server_ready(config) and result.get("llm_configured") and result.get("embedding_configured") else 1
        return 0
    except Exception:
        LOG.exception("Launcher failed")
        if args.action == "open":
            page = show_start_page(root, "GrantFiller needs attention. Run Setup or Repair GrantFiller. "
                                   f"Troubleshooting logs: {root / 'logs'}.", refresh=False)
            webbrowser.open(page.as_uri())
        else:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
