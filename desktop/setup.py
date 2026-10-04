"""Install a fresh local copy, dependencies, models and OS launch shortcuts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import socket
import subprocess
import sys
import time
import uuid
import venv
import webbrowser

from launch import (api_url, atomic_json, load_config, ollama_ready, request_json,
                    runtime_env, server_ready, start_supervisor, state_root, stop_supervisor)


def run(command: list[str], env: dict | None = None) -> None:
    subprocess.run(command, check=True, env=env)


def locate_ollama() -> str:
    candidates = [shutil.which("ollama")]
    if sys.platform == "win32":
        candidates += [str(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe")]
    else:
        candidates += ["/Applications/Ollama.app/Contents/Resources/ollama", "/opt/homebrew/bin/ollama", "/usr/local/bin/ollama"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    webbrowser.open("https://ollama.com/download")
    raise RuntimeError("Install Ollama from the page that opened, then run Setup again.")


def free_port() -> int:
    for port in range(8766, 8796):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No local port is available. Restart the laptop and run Setup again.")


def install_shortcuts(root: Path, config: dict) -> None:
    launcher = Path(config["app_dir"]) / "desktop" / "launch.py"
    python = Path(config["python"])
    if sys.platform == "win32":
        # Shell.SpecialFolders respects redirected Desktop and Startup folders.
        def ps_quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"
        args = f'"{launcher}" open --state-dir "{root}"'
        supervise_args = f'"{launcher}" supervise --state-dir "{root}"'
        repair_args = f'"{Path(config["app_dir"]) / "desktop" / "setup.py"}" --state-dir "{root}" --repair'
        script = f"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
function Shortcut($folder, $name, $target, $arguments) {{
    $shortcut = $shell.CreateShortcut((Join-Path $folder ($name + '.lnk')))
    $shortcut.TargetPath = $target
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = {ps_quote(config['app_dir'])}
    $shortcut.Save()
}}
$desktop = $shell.SpecialFolders.Item('Desktop')
Shortcut $desktop 'GrantFiller' {ps_quote(str(python.with_name('pythonw.exe')))} {ps_quote(args)}
Shortcut $desktop 'Repair GrantFiller' 'cmd.exe' {ps_quote('/k ""' + str(python) + '" ' + repair_args + '"')}
Shortcut ($shell.SpecialFolders.Item('Startup')) 'GrantFiller Background' {ps_quote(str(python.with_name('pythonw.exe')))} {ps_quote(supervise_args)}
"""
        run(["powershell.exe", "-NoProfile", "-Command", script])
    else:
        desktop = Path.home() / "Desktop"
        desktop.mkdir(exist_ok=True)
        app = desktop / "GrantFiller.app"
        import shlex
        command = " ".join(shlex.quote(p) for p in [str(python), str(launcher), "open", "--state-dir", str(root)])
        command += " >/dev/null 2>&1 &"
        # AppleScript's string escaping is distinct from shell quoting.
        literal = command.replace("\\", "\\\\").replace('"', '\\"')
        script_path = root / "open.applescript"
        script_path.write_text('do shell script "' + literal + '"\n', encoding="utf-8")
        if app.exists():
            shutil.rmtree(app)
        run(["osacompile", "-o", str(app), str(script_path)])
        repair = desktop / "Repair GrantFiller.command"
        repair.write_text("#!/bin/zsh\n" + " ".join(shlex.quote(p) for p in [str(python), str(Path(config['app_dir']) / 'desktop' / 'setup.py'), '--state-dir', str(root), '--repair']) + '\nread "?Press Return to close."\n', encoding="utf-8")
        repair.chmod(0o755)
        agents = Path.home() / "Library" / "LaunchAgents"
        agents.mkdir(parents=True, exist_ok=True)
        agent = agents / "org.grantfiller.local.plist"
        agent.write_bytes(plistlib.dumps({
            "Label": "org.grantfiller.local",
            "ProgramArguments": [str(python), str(launcher), "supervise", "--state-dir", str(root)],
            "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 15,
            "StandardOutPath": str(root / "logs" / "login.log"),
            "StandardErrorPath": str(root / "logs" / "login-errors.log"),
        }))
        # The current supervisor runs now. launchd loads this agent at the next login.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--no-shortcuts", action="store_true", help="For isolated verification only")
    parser.add_argument("--skip-model-pull", action="store_true", help="For test runners only")
    parser.add_argument("--skip-browser-install", action="store_true", help="For test runners only")
    parser.add_argument("--no-open", action="store_true", help="For test runners only")
    args = parser.parse_args()
    if sys.platform not in {"win32", "darwin"}:
        raise RuntimeError("This handoff kit supports Windows and macOS.")
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required.")
    if sys.platform == "darwin" and int(platform.mac_ver()[0].split('.')[0]) < 14:
        raise RuntimeError("The current Ollama release requires macOS 14 or newer.")
    root = (args.state_dir or state_root()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    print("GrantFiller setup. This may take a while while dependencies and AI models download.", flush=True)
    print("Saved work will stay in: " + str(root / "data"), flush=True)
    ollama = locate_ollama()
    source = Path(__file__).resolve().parent.parent
    destination = root / "app"
    old = None
    if (root / "installation.json").exists():
        old = load_config(root)
        stop_supervisor(root)
        if (root / "runtime.json").exists():
            raise RuntimeError("The previous copy is still stopping. Wait a moment and run Setup again.")
    if source != destination:
        destination.mkdir(exist_ok=True)
        # Copy only shipped application files. Never copy .env, databases, or a Mac venv.
        shutil.copytree(source / "backend" / "app", destination / "backend" / "app", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(source / "frontend" / "dist", destination / "frontend" / "dist", dirs_exist_ok=True)
        shutil.copytree(source / "desktop", destination / "desktop", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(source / "LICENSE", destination / "LICENSE")
    environment = destination / "backend" / ".venv"
    if not environment.exists():
        print("Creating the local runtime…", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    config = {
        "app_dir": str(destination), "python": str(python), "ollama": ollama,
        "install_id": old["install_id"] if old else str(uuid.uuid4()),
        "port": old["port"] if old else free_port(), "ollama_url": "http://127.0.0.1:11434",
        "chat_model": "qwen2.5:3b-instruct", "embed_model": "nomic-embed-text",
    }
    atomic_json(root / "installation.json", config)
    env = runtime_env(root, config)
    print("Installing the tested Python dependencies…", flush=True)
    run([str(python), "-m", "pip", "install", "--only-binary=:all:", "-r", str(destination / "desktop" / "requirements.lock")])
    if not args.skip_browser_install:
        print("Installing the browser used for importing grant websites…", flush=True)
        run([str(python), "-m", "playwright", "install", "chromium"], env)
    print("Starting background services…", flush=True)
    start_supervisor(root, config)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if server_ready(config) and ollama_ready(config):
            break
        time.sleep(1)
    else:
        raise RuntimeError("Startup failed. Check " + str(root / "logs"))
    if not args.skip_model_pull:
        for model in (config["chat_model"], config["embed_model"]):
            print("Downloading/checking local AI model: " + model, flush=True)
            run([ollama, "pull", model], env)
        print("Testing real local AI. The first model load can take several minutes…", flush=True)
        result = request_json(config["ollama_url"] + "/api/generate", {
            "model": config["chat_model"], "prompt": 'Return JSON with one key "ok" set to true.',
            "format": "json", "stream": False, "options": {"num_predict": 32},
        }, timeout=600)
        if not result.get("done") or not result.get("response"):
            raise RuntimeError("The local AI did not finish the test. Check Ollama and run Repair.")
        request_json(config["ollama_url"] + "/api/embed", {
            "model": config["embed_model"], "input": "GrantFiller installation check",
        }, timeout=300)
    check = request_json(api_url(config) + "/api/v1/config")
    if not args.skip_model_pull and not (check.get("llm_configured") and check.get("embedding_configured")):
        raise RuntimeError("The AI models are still missing. Run Setup again.")
    if not args.no_shortcuts:
        print("Adding the GrantFiller icon and login startup…", flush=True)
        install_shortcuts(root, config)
    print("SETUP COMPLETE. Open GrantFiller from the desktop icon.", flush=True)
    print("Before leaving: upload a real file, draft answers, export, reboot, and launch again.", flush=True)
    if not args.no_open:
        webbrowser.open(api_url(config))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("\nSETUP DID NOT FINISH: " + str(error), file=sys.stderr, flush=True)
        print("Your saved data has been kept. Fix the issue above and run Setup again.", file=sys.stderr)
        raise SystemExit(1)
