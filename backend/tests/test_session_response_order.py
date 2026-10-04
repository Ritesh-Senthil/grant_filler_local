"""A saved response must not reach the client before the transaction commits."""
import asyncio

from fastapi import FastAPI
import httpx
import pytest

from app.database import get_session
from app.deps import SessionDep


@pytest.mark.asyncio
async def test_session_commit_finishes_before_response_is_sent():
    events = []
    app = FastAPI()

    async def delayed_session():
        yield object()
        events.append("commit_started")
        await asyncio.sleep(0.05)
        events.append("commit_finished")

    app.dependency_overrides[get_session] = delayed_session

    @app.post("/save")
    async def save(session: SessionDep):
        events.append("handler")
        return {"saved": True}

    async def observe_response(scope, receive, send):
        async def observed_send(message):
            if message["type"] == "http.response.start":
                events.append("response_sent")
            await send(message)
        await app(scope, receive, observed_send)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=observe_response), base_url="http://test"
    ) as client:
        response = await client.post("/save")
    assert response.status_code == 200
    assert events == ["handler", "commit_started", "commit_finished", "response_sent"]
