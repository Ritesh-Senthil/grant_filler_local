"""Shared fixtures: isolated DB under tmp, Starlette TestClient, table wipe between tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator

import pytest
from sqlalchemy import delete, select
from starlette.testclient import TestClient

from app.database import get_session_factory, reset_engine
from app.deps import ensure_default_org
from app.models import Answer, Fact, Grant, Job, Organization, Question


async def _wipe_all_data() -> None:
    """Remove grants/jobs/answers/questions/facts; keep or recreate default org."""
    sf = get_session_factory()
    async with sf() as session:
        await session.execute(delete(Job))
        await session.execute(delete(Answer))
        await session.execute(delete(Question))
        await session.execute(delete(Grant))
        await session.execute(delete(Fact))
        await session.flush()
        r = await session.execute(select(Organization).where(Organization.id == "default-org"))
        if r.scalar_one_or_none() is None:
            session.add(Organization(id="default-org"))
        await session.commit()


@pytest.fixture(scope="session")
def test_client(tmp_path_factory: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    root = tmp_path_factory.mktemp("grantfiller_test")
    data = root / "data"
    data.mkdir(parents=True)
    os.environ["DATA_DIR"] = str(data)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{root / 'test.db'}"
    reset_engine()
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        assert client.get("/api/v1/health").status_code == 200
        yield client


@pytest.fixture(autouse=True)
def _wipe_between_tests(test_client: TestClient) -> Generator[None, None, None]:
    """Reset grants/questions/etc. before each test so order never leaks state."""
    asyncio.run(_wipe_all_data())
    yield


@pytest.fixture
def mock_ollama_questions(monkeypatch: pytest.MonkeyPatch):
    """Patch OllamaClient.chat_json to return one textarea question (no network)."""
    from unittest.mock import AsyncMock

    from app.services.ollama import OllamaClient
    from app.services.questions_extract import ExtractedQuestion, QuestionListPayload

    payload = QuestionListPayload(
        questions=[
            ExtractedQuestion(
                question_id="q_test_1",
                question_text="What is your organization's mission?",
                type="textarea",
            )
        ]
    )
    m = AsyncMock(return_value=payload)
    monkeypatch.setattr(OllamaClient, "chat_json", m)
    return m

