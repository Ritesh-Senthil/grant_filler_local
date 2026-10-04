"""Test and switch models in an existing GrantFiller desktop installation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import webbrowser
from launch import (InstanceLock, api_url, atomic_json, load_config, request_json,
                    runtime_env, server_ready, start_supervisor, state_root,
                    stop_supervisor)

MODELS = ("qwen2.5:7b-instruct", "qwen2.5:3b-instruct")


def wait_ready(config: dict) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if server_ready(config):
            return
        time.sleep(1)
    raise RuntimeError("GrantFiller did not start. Run Repair GrantFiller.")


def check_idle(root: Path) -> None:
    database = root / "data" / "grantfiller.db"
    if database.exists():
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            active = connection.execute(
                "SELECT id FROM jobs WHERE status IN ('pending', 'running') LIMIT 1"
            ).fetchone()
        if active:
            raise RuntimeError("A grant job is still running. Let it finish, then try again.")


def download_model(root: Path, config: dict, model: str) -> None:
    subprocess.run([config["ollama"], "pull", model], check=True,
                   env=runtime_env(root, config))


def install_options(root: Path, config: dict) -> None:
    source = Path(__file__).resolve().parent
    destination = Path(config["app_dir"]) / "desktop"
    # Updating Repair makes the selected model survive future repairs.
    for name in ("model_upgrade.py", "upgrade-ai-windows.ps1",
                 "Choose AI Model Windows.cmd", "setup.py"):
        original = source / name
        target = destination / name
        if original.resolve() != target.resolve():
            shutil.copy2(original, target)
    if sys.platform == "win32":
        path = str(destination / "Choose AI Model Windows.cmd").replace("'", "''")
        script = (
            "$ErrorActionPreference = 'Stop'; $shell = New-Object -ComObject WScript.Shell; "
            "$shortcut = $shell.CreateShortcut((Join-Path ($shell.SpecialFolders.Item('Desktop')) "
            "'GrantFiller AI Options.lnk')); "
            f"$shortcut.TargetPath = '{path}'; $shortcut.Save()"
        )
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], check=True)


def upgrade(root: Path, model: str) -> None:
    if model not in MODELS:
        raise ValueError("Unsupported model")
    old = load_config(root)
    lock = InstanceLock(root / "model-change.lock")
    if not lock.acquire():
        lock.close()
        raise RuntimeError("Another AI update is already running.")
    try:
        check_idle(root)
        if not server_ready(old):
            start_supervisor(root, old)
            wait_ready(old)
        print("Downloading/checking " + model + ". Keep this window open.", flush=True)
        download_model(root, old, model)
        print("Testing real local AI before changing your app…", flush=True)
        started = time.monotonic()
        result = request_json(old["ollama_url"] + "/api/chat", {
            "model": model, "stream": False,
            "messages": [{"role": "user", "content": 'Return exactly {"ok":true}.'}],
            "format": {"title": "UpgradeCheck", "type": "object",
                       "properties": {"ok": {"type": "boolean"}},
                       "required": ["ok"], "additionalProperties": False},
            "options": {"temperature": 0, "num_predict": 64},
        }, timeout=600)
        if json.loads(result.get("message", {}).get("content", "")) != {"ok": True}:
            raise RuntimeError("The AI test failed. Your current model is unchanged.")
        print(f"AI test passed in {time.monotonic() - started:.1f} seconds (includes loading).", flush=True)
        check_idle(root)
        new = {**old, "chat_model": model}
        stop_supervisor(root)
        if (root / "runtime.json").exists():
            raise RuntimeError("GrantFiller is still stopping. Wait a moment and try again.")
        try:
            atomic_json(root / "installation.json", new)
            start_supervisor(root, new)
            wait_ready(new)
            status = request_json(api_url(new) + "/api/v1/config")
            if status.get("chat_model") != model or not status.get("llm_configured"):
                raise RuntimeError("The app did not activate the selected model.")
            install_options(root, new)
        except Exception:
            stop_supervisor(root)
            atomic_json(root / "installation.json", old)
            start_supervisor(root, old)
            raise
        print("AI UPDATE COMPLETE: " + model, flush=True)
        print("Saved work has been kept. GrantFiller AI Options on the desktop lets you choose 3B or 7B.", flush=True)
        print("Test a real grant now; choose Faster (3B) if 7B takes too long.", flush=True)
    finally:
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--model", choices=MODELS, default=MODELS[0])
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    root = (args.state_dir or state_root()).resolve()
    upgrade(root, args.model)
    if not args.no_open:
        webbrowser.open(api_url(load_config(root)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("AI UPDATE DID NOT FINISH: " + str(error), file=sys.stderr, flush=True)
        print("Saved work is safe. Open GrantFiller or use Repair if needed.", file=sys.stderr)
        raise SystemExit(1)
