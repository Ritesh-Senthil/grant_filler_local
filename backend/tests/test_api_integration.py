"""HTTP API tests (TestClient). Background jobs are not guaranteed to finish under TestClient — see test_job_runner_direct.py."""

from unittest.mock import AsyncMock

import fitz

from app.services.answers import AnswerBatchPayload, AnswerItem
from app.services.ollama import OllamaClient
from app.services.questions_extract import QuestionListPayload


def _minimal_pdf_bytes(text: str = "Question 1: What is your mission?") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = doc.tobytes()
    doc.close()
    return buf


def test_parse_without_upload_returns_400(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "G", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(f"/api/v1/grants/{gid}/parse", json={})
    assert r2.status_code == 400


def test_parse_use_url_without_url_returns_400(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "WebG", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(f"/api/v1/grants/{gid}/parse", json={"use_url": True})
    assert r2.status_code == 400


def test_preview_url_without_url_returns_400(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "P", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(f"/api/v1/grants/{gid}/preview-url", json={})
    assert r2.status_code == 400


def test_parse_use_url_enqueues_202(test_client, mock_ollama_questions, monkeypatch):
    from app.services import web_fetch as wf
    from app.services.ingest import TextSegment

    async def fake_fetch(settings, url):
        return ([TextSegment(label="web", text=("Grant question: Why? " * 30))], {"strategy": "test"})

    monkeypatch.setattr(wf, "fetch_web_segments", fake_fetch)

    r = test_client.post(
        "/api/v1/grants",
        json={"name": "URL grant", "grant_url": "https://example.org/g", "source_type": "pdf"},
    )
    gid = r.json()["id"]
    pr = test_client.post(f"/api/v1/grants/{gid}/parse", json={"use_url": True})
    assert pr.status_code == 202
    assert pr.json().get("job_id")


def test_generate_without_questions_returns_400(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "G", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(f"/api/v1/grants/{gid}/generate", json={})
    assert r2.status_code == 400


def test_get_unknown_grant_404(test_client):
    assert test_client.get("/api/v1/grants/00000000-0000-0000-0000-000000000001").status_code == 404


def test_get_unknown_job_404(test_client):
    assert test_client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000001").status_code == 404


def test_file_path_traversal_returns_404(test_client):
    assert test_client.get("/api/v1/files/../../../etc/passwd").status_code == 404


def test_org_put_get(test_client):
    test_client.put(
        "/api/v1/org",
        json={
            "legal_name": "Test Org Inc",
            "mission_short": "We help.",
            "mission_long": "",
            "address": "1 Main St",
            "extra_sections": [],
        },
    )
    r = test_client.get("/api/v1/org")
    assert r.status_code == 200
    assert r.json()["legal_name"] == "Test Org Inc"


def test_fact_crud(test_client):
    r = test_client.post("/api/v1/org/facts", json={"key": "EIN", "value": "12-3456789", "source": "irs"})
    assert r.status_code == 200
    fid = r.json()["id"]
    lst = test_client.get("/api/v1/org/facts").json()
    assert len(lst) == 1
    assert test_client.delete(f"/api/v1/org/facts/{fid}").status_code == 200
    assert test_client.get("/api/v1/org/facts").json() == []


def test_upload_too_large_rejected(test_client, monkeypatch):
    monkeypatch.setattr(test_client.app.state.settings, "max_upload_mb", 0)
    r = test_client.post("/api/v1/grants", json={"name": "G", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(
        f"/api/v1/grants/{gid}/files",
        files={"file": ("big.pdf", b"x" * 1024, "application/pdf")},
    )
    assert r2.status_code == 413


def test_parse_enqueue_returns_202(test_client, mock_ollama_questions):
    """POST /parse enqueues a job; completion is tested in test_job_runner_direct."""
    r = test_client.post("/api/v1/grants", json={"name": "Grant A", "source_type": "pdf"})
    gid = r.json()["id"]
    pdf = _minimal_pdf_bytes()
    assert test_client.post(
        f"/api/v1/grants/{gid}/files",
        files={"file": ("app.pdf", pdf, "application/pdf")},
    ).status_code == 200
    pr = test_client.post(f"/api/v1/grants/{gid}/parse", json={})
    assert pr.status_code == 202
    job_id = pr.json()["job_id"]
    jr = test_client.get(f"/api/v1/jobs/{job_id}")
    assert jr.status_code == 200
    assert jr.json()["job_kind"] == "parse"


def test_generate_enqueue_returns_202(test_client, monkeypatch):
    """Enqueue generate only when questions exist (inserted directly for this contract test)."""
    import asyncio

    from sqlalchemy import select

    from app.models import Question

    r = test_client.post("/api/v1/grants", json={"name": "G2", "source_type": "pdf"})
    gid = r.json()["id"]
    sf = test_client.app.state.session_factory

    async def add_question():
        async with sf() as session:
            session.add(
                Question(
                    grant_id=gid,
                    question_id="q_manual",
                    question_text="Test?",
                    q_type="textarea",
                    sort_order=0,
                )
            )
            await session.commit()

    asyncio.run(add_question())

    async def fake_chat_json(_system, _user, model):
        if getattr(model, "__name__", "") == "AnswerBatchPayload":
            return AnswerBatchPayload(
                answers=[AnswerItem(question_id="q_manual", answer_value="draft", needs_manual_input=False)]
            )
        return QuestionListPayload(questions=[])

    monkeypatch.setattr(OllamaClient, "chat_json", AsyncMock(side_effect=fake_chat_json))
    ge = test_client.post(f"/api/v1/grants/{gid}/generate", json={})
    assert ge.status_code == 202
    assert ge.json()["job_id"]


def test_patch_answer_creates_row(test_client):
    import asyncio

    from app.models import Question

    r = test_client.post("/api/v1/grants", json={"name": "P", "source_type": "pdf"})
    gid = r.json()["id"]
    sf = test_client.app.state.session_factory

    async def add_question():
        async with sf() as session:
            session.add(
                Question(
                    grant_id=gid,
                    question_id="any-id",
                    question_text="Test?",
                    q_type="textarea",
                    sort_order=0,
                )
            )
            await session.commit()

    asyncio.run(add_question())

    pa = test_client.patch(
        f"/api/v1/grants/{gid}/questions/any-id",
        json={"answer_value": "Manual answer", "reviewed": True},
    )
    assert pa.status_code == 200
    assert pa.json()["answer_value"] == "Manual answer"
    assert pa.json()["reviewed"] is True


def test_learn_org_without_questions_returns_400(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "G", "source_type": "pdf"})
    gid = r.json()["id"]
    r2 = test_client.post(f"/api/v1/grants/{gid}/learn-org", json={})
    assert r2.status_code == 400


def test_export_markdown_without_questions(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "G", "source_type": "pdf"})
    gid = r.json()["id"]
    ex = test_client.post(f"/api/v1/grants/{gid}/export", json={"format": "markdown"})
    assert ex.status_code == 200
    path = ex.json()["download_path"].lstrip("/")
    dl = test_client.get(f"/{path}")
    assert dl.status_code == 200
    assert b"# G" in dl.content


def test_delete_grant(test_client):
    r = test_client.post("/api/v1/grants", json={"name": "ToDelete", "source_type": "pdf"})
    gid = r.json()["id"]
    assert test_client.delete(f"/api/v1/grants/{gid}").status_code == 200
    assert test_client.get(f"/api/v1/grants/{gid}").status_code == 404


def test_schemas_question_read_from_model():
    from app.models import Question
    from app.schemas import QuestionRead

    q = Question(
        grant_id="g",
        question_id="q1",
        question_text="Hello?",
        q_type="textarea",
        sort_order=0,
    )
    qr = QuestionRead.from_model(q)
    assert qr.type == "textarea"


def test_ollama_chat_json_repair_on_bad_json(monkeypatch):
    """Second call returns valid JSON (repair path)."""
    from app.services.ollama import OllamaClient
    from pydantic import BaseModel

    class M(BaseModel):
        x: int

    calls = {"n": 0}

    async def fake_chat(self, system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json"
        return '{"x": 1}'

    monkeypatch.setattr(OllamaClient, "chat", fake_chat)
    import asyncio

    from app.config import Settings

    async def run():
        c = OllamaClient(Settings())
        out = await c.chat_json("s", "u", M)
        assert out.x == 1

    asyncio.run(run())
    assert calls["n"] == 2
