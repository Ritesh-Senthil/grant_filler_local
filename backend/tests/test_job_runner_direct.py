"""
Direct asyncio tests for run_parse_job / run_generate_job (no TestClient background quirks).

Starlette's TestClient runs the ASGI app inside an event loop and does not reliably execute
async BackgroundTasks the same way as a real uvicorn process, so completion is tested here.
"""

import asyncio
from unittest.mock import AsyncMock

import fitz
import pytest

from app.job_runner import run_generate_job, run_parse_job
from app.models import Grant, Job
from app.services.answers import AnswerBatchPayload, AnswerItem
from app.services.ollama import OllamaClient
from app.services.questions_extract import ExtractedQuestion, QuestionListPayload
from app.storage import StorageService


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = doc.tobytes()
    doc.close()
    return buf


@pytest.fixture
def runner_ctx(test_client, mock_ollama_questions):
    """App state from a live TestClient (DB + storage + LLM + embedder)."""
    return test_client.app.state


async def _create_parse_job(sf, grant_id: str) -> str:
    from sqlalchemy.ext.asyncio import AsyncSession

    async with sf() as session:  # type: AsyncSession
        j = Job(grant_id=grant_id, job_kind="parse", status="pending")
        session.add(j)
        await session.commit()
        await session.refresh(j)
        return j.id


def test_run_parse_job_success(runner_ctx, mock_ollama_questions):
    settings = runner_ctx.settings
    storage = runner_ctx.storage
    llm = runner_ctx.llm
    sf = runner_ctx.session_factory

    async def setup():
        async with sf() as session:
            g = Grant(name="Direct", source_type="pdf", status="draft")
            session.add(g)
            await session.flush()
            gid = g.id
            key = StorageService.grant_source_key(gid, "x.pdf")
            storage.write_bytes(key, _pdf_with_text("Q: Mission?"))
            g.source_file_key = key
            await session.commit()
            jid = await _create_parse_job(sf, gid)
            return gid, jid

    gid, jid = asyncio.run(setup())
    asyncio.run(run_parse_job(sf, settings, storage, llm, jid, gid, None))

    async def check():
        async with sf() as session:
            from sqlalchemy import select
            from app.models import Question

            j = await session.get(Job, jid)
            assert j.status == "completed"
            r = await session.execute(select(Question).where(Question.grant_id == gid))
            assert len(r.scalars().all()) == 1

    asyncio.run(check())


def test_run_parse_job_success_web(runner_ctx, mock_ollama_questions, monkeypatch):
    from app.services import web_fetch as wf
    from app.services.ingest import TextSegment

    async def fake_fetch(settings, url):
        return (
            [TextSegment(label="web", text=("Question: goals? " * 50))],
            {"strategy": "test", "http_status": 200},
        )

    monkeypatch.setattr(wf, "fetch_web_segments", fake_fetch)

    settings = runner_ctx.settings
    storage = runner_ctx.storage
    llm = runner_ctx.llm
    sf = runner_ctx.session_factory

    async def setup():
        async with sf() as session:
            g = Grant(name="Web", source_type="pdf", status="draft", grant_url="https://example.org/a")
            session.add(g)
            await session.flush()
            gid = g.id
            await session.commit()
            jid = await _create_parse_job(sf, gid)
            return gid, jid

    gid, jid = asyncio.run(setup())
    asyncio.run(
        run_parse_job(
            sf,
            settings,
            storage,
            llm,
            jid,
            gid,
            None,
            parse_from_web=True,
        )
    )

    async def check():
        async with sf() as session:
            from sqlalchemy import select
            from app.models import Question

            j = await session.get(Job, jid)
            assert j.status == "completed"
            assert j.result_json and j.result_json.get("web_fetch")
            r = await session.execute(select(Question).where(Question.grant_id == gid))
            assert len(r.scalars().all()) == 1

    asyncio.run(check())


def test_run_parse_job_fails_no_questions(runner_ctx, monkeypatch):
    settings = runner_ctx.settings
    storage = runner_ctx.storage
    llm = runner_ctx.llm
    sf = runner_ctx.session_factory

    monkeypatch.setattr(
        OllamaClient,
        "chat_json",
        AsyncMock(return_value=QuestionListPayload(questions=[])),
    )

    async def setup():
        async with sf() as session:
            g = Grant(name="Direct", source_type="pdf", status="draft")
            session.add(g)
            await session.flush()
            gid = g.id
            key = StorageService.grant_source_key(gid, "x.pdf")
            storage.write_bytes(key, _pdf_with_text("Some text"))
            g.source_file_key = key
            await session.commit()
            jid = await _create_parse_job(sf, gid)
            return gid, jid

    gid, jid = asyncio.run(setup())
    asyncio.run(run_parse_job(sf, settings, storage, llm, jid, gid, None))

    async def check():
        async with sf() as session:
            j = await session.get(Job, jid)
            assert j.status == "failed"
            assert "No valid questions" in (j.error or "")

    asyncio.run(check())


def test_run_parse_job_fails_no_extractable_text(runner_ctx, mock_ollama_questions):
    """Blank PDF page yields no segments before LLM."""
    settings = runner_ctx.settings
    storage = runner_ctx.storage
    llm = runner_ctx.llm
    sf = runner_ctx.session_factory

    def empty_pdf():
        doc = fitz.open()
        doc.new_page()
        buf = doc.tobytes()
        doc.close()
        return buf

    async def setup():
        async with sf() as session:
            g = Grant(name="Empty", source_type="pdf", status="draft")
            session.add(g)
            await session.flush()
            gid = g.id
            key = StorageService.grant_source_key(gid, "e.pdf")
            storage.write_bytes(key, empty_pdf())
            g.source_file_key = key
            await session.commit()
            jid = await _create_parse_job(sf, gid)
            return gid, jid

    gid, jid = asyncio.run(setup())
    asyncio.run(run_parse_job(sf, settings, storage, llm, jid, gid, None))

    async def check():
        async with sf() as session:
            j = await session.get(Job, jid)
            assert j.status == "failed"
            assert "No text extracted" in (j.error or "")

    asyncio.run(check())


async def _fake_embed_text(_self, _text: str) -> list[float]:
    return [0.1] * 128


async def _fake_embed_texts(_self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 128 for _ in texts]


def test_run_generate_job_success(runner_ctx, monkeypatch):
    settings = runner_ctx.settings
    llm = runner_ctx.llm
    embedder = runner_ctx.embedder
    sf = runner_ctx.session_factory

    monkeypatch.setattr(OllamaClient, "embed_text", _fake_embed_text)
    monkeypatch.setattr(OllamaClient, "embed_texts", _fake_embed_texts)

    monkeypatch.setattr(
        OllamaClient,
        "chat_json",
        AsyncMock(
            side_effect=[
                QuestionListPayload(
                    questions=[
                        ExtractedQuestion(
                            question_id="q1",
                            question_text="Mission?",
                            type="textarea",
                        )
                    ]
                ),
                AnswerBatchPayload(
                    answers=[
                        AnswerItem(
                            question_id="q1",
                            answer_value="We serve.",
                            needs_manual_input=False,
                            evidence_fact_ids=[],
                        )
                    ]
                ),
            ]
        ),
    )

    storage = runner_ctx.storage

    async def setup():
        async with sf() as session:
            g = Grant(name="Gen", source_type="pdf", status="draft")
            session.add(g)
            await session.flush()
            gid = g.id
            key = StorageService.grant_source_key(gid, "x.pdf")
            storage.write_bytes(key, _pdf_with_text("Mission?"))
            g.source_file_key = key
            await session.commit()
        jid_parse = await _create_parse_job(sf, gid)
        return gid, jid_parse

    gid, jid_parse = asyncio.run(setup())
    asyncio.run(run_parse_job(sf, settings, storage, llm, jid_parse, gid, None))

    async def mk_gen_job():
        async with sf() as session:
            j = Job(grant_id=gid, job_kind="generate", status="pending")
            session.add(j)
            await session.commit()
            await session.refresh(j)
            return j.id

    jid_gen = asyncio.run(mk_gen_job())
    asyncio.run(run_generate_job(sf, settings, llm, embedder, jid_gen, gid, None))

    async def check():
        async with sf() as session:
            j = await session.get(Job, jid_gen)
            assert j.status == "completed"
            from sqlalchemy import select
            from app.models import Answer

            r = await session.execute(select(Answer).where(Answer.grant_id == gid))
            ans = r.scalars().all()
            assert len(ans) == 1

    asyncio.run(check())
