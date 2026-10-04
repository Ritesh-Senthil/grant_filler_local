"""Real HTTP/process integration checks. --installed also exercises real Ollama."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import fitz
import httpx

from launch import (api_url, atomic_json, load_config, server_ready, start_supervisor,
                    stop_supervisor)
from setup import free_port, install_shortcuts
import model_upgrade


class FakeAI(BaseHTTPRequestHandler):
    fact_id = ""
    fail_upgrade = False
    def log_message(self, *_):
        pass

    def respond(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.respond({"models": [{"name": "qwen2.5:3b-instruct"}, {"name": "qwen2.5:7b-instruct"}, {"name": "nomic-embed-text:latest"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        if self.path == "/api/embeddings":
            self.respond({"embedding": [0.1, 0.2, 0.3]})
        else:
            title = (body.get("format") or {}).get("title", "")
            if title == "UpgradeCheck":
                value = {"ok": not self.fail_upgrade}
            elif title == "QuestionListPayload":
                value = {"questions": [{"question_id": "mission", "question_text": "What is your organization's mission?", "type": "textarea", "required": True}]}
            else:
                value = {"answers": [{"question_id": "mission", "answer_value": "We provide community essentials to families.", "needs_manual_input": False, "evidence_fact_ids": [self.fact_id]}]}
            self.respond({"message": {"content": json.dumps(value)}})


def wait_for(predicate, timeout=60):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(.5)
    raise AssertionError("Timed out waiting for recovery")


def exercise(root: Path, config: dict, *, real_ai: bool):
    wait_for(lambda: server_ready(config))
    with httpx.Client(base_url=api_url(config), timeout=30, trust_env=False) as client:
        def post(path, **kw):
            response = client.post(path, **kw)
            if response.is_error:
                print(f"FAILED {path}: {response.status_code} {response.text}", flush=True)
            response.raise_for_status()
            return response.json()
        for route in ("/", "/settings", "/org", "/grants/example"):
            response = client.get(route)
            assert response.status_code == 200 and '<div id="root">' in response.text, route
        for route in ("/api/v1/unknown", "/assets/missing.js"):
            assert client.get(route).status_code == 404
        assert client.patch("/api/v1/llm", json={"llm_provider": "gemini"}).status_code == 422
        status = client.get("/api/v1/config").json()
        assert status["local_only"] and status["llm_provider"] == "ollama"
        assert status["llm_configured"] and status["embedding_configured"]
        facts = post("/api/v1/org/facts", json={"key": "Mission", "value": "We provide community essentials to families.", "source": "installation test"})
        FakeAI.fact_id = facts["id"]
        grant = post("/api/v1/grants", json={"name": "Installation test", "source_type": "pdf"})
        gid = grant["id"]
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Application question: What is your organization's mission?\nPlease describe your mission in one paragraph.")
        pdf = doc.tobytes()
        doc.close()
        post(f"/api/v1/grants/{gid}/files", files={"file": ("sample.pdf", pdf, "application/pdf")})
        assert client.get(f"/api/v1/grants/{gid}").json()["source_file_key"], "Upload was acknowledged before it was saved"
        def job_done(job_id):
            row = client.get(f"/api/v1/jobs/{job_id}").json()
            if row["status"] == "failed":
                raise AssertionError(row.get("error"))
            return row["status"] == "completed"
        job = post(f"/api/v1/grants/{gid}/parse", json={})
        wait_for(lambda: job_done(job["job_id"]), 180 if real_ai else 60)
        job = post(f"/api/v1/grants/{gid}/generate", json={})
        wait_for(lambda: job_done(job["job_id"]), 180 if real_ai else 60)
        detail = client.get(f"/api/v1/grants/{gid}").json()
        assert detail["questions"] and detail["answers"], detail
        for kind in ("qa_pdf", "docx", "markdown"):
            exported = post(f"/api/v1/grants/{gid}/export", json={"format": kind})
            path = exported.get("download_url") or exported.get("download_path")
            if not path:
                path = "/api/v1/files/" + exported["file_key"]
            response = client.get(path)
            response.raise_for_status()
            assert len(response.content) > 20, kind
        before = json.loads((root / "runtime.json").read_text())["backend_pid"]
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(before), "/F"], check=True, capture_output=True)
        else:
            os.kill(before, signal.SIGKILL)
        def recovered():
            return server_ready(config) and json.loads((root / "runtime.json").read_text())["backend_pid"] != before
        wait_for(recovered)
        assert client.get(f"/api/v1/grants/{gid}").json()["answers"]
        start_supervisor(root, config)
        time.sleep(2)
        assert server_ready(config)
    stop_supervisor(root)
    wait_for(lambda: not server_ready(config))
    start_supervisor(root, config)
    wait_for(lambda: server_ready(config))
    assert list((root / "backups").glob("*.zip")), "Startup backup was not created"
    if not real_ai:
        from unittest.mock import patch
        with patch.object(model_upgrade, "download_model"):
            FakeAI.fail_upgrade = True
            try:
                model_upgrade.upgrade(root, "qwen2.5:7b-instruct")
            except RuntimeError:
                assert load_config(root)["chat_model"] == config["chat_model"]
                assert server_ready(config)
            else:
                raise AssertionError("An invalid AI test must not change the app")
            finally:
                FakeAI.fail_upgrade = False
            model_upgrade.upgrade(root, "qwen2.5:7b-instruct")
            assert load_config(root)["chat_model"] == "qwen2.5:7b-instruct"
            model_upgrade.upgrade(root, "qwen2.5:3b-instruct")
            assert load_config(root)["chat_model"] == config["chat_model"]
            assert httpx.get(api_url(config) + f"/api/v1/grants/{gid}", trust_env=False).json()["answers"]
        print("PASS: AI update, return to 3B, saved work preserved, rejected update keeps current app", flush=True)
    print("PASS: routes, local-only AI, PDF upload, question extraction, drafting, PDF/Word/Markdown exports, crash recovery, duplicate launch, restart persistence, backup", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed", type=Path)
    parser.add_argument("--shortcuts", action="store_true")
    args = parser.parse_args()
    if args.installed:
        root = args.installed.resolve()
        exercise(root, load_config(root), real_ai=True)
        return
    with tempfile.TemporaryDirectory(prefix="grantfiller-smoke-") as directory:
        root = Path(directory)
        (root / "logs").mkdir()
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAI)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        config = {"app_dir": str(Path(__file__).resolve().parent.parent), "python": sys.executable,
                  "install_id": str(uuid.uuid4()), "port": free_port(), "ollama": sys.executable,
                  "ollama_url": f"http://127.0.0.1:{server.server_port}",
                  "chat_model": "qwen2.5:3b-instruct", "embed_model": "nomic-embed-text"}
        atomic_json(root / "installation.json", config)
        try:
            start_supervisor(root, config)
            exercise(root, config, real_ai=False)
            if args.shortcuts:
                install_shortcuts(root, config)
                print("PASS: native desktop shortcuts and login startup assets")
        finally:
            stop_supervisor(root)
            server.shutdown()


if __name__ == "__main__":
    main()
