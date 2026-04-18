"""Settings epic: org banner, preferences, developer credits, enhancement stub."""

import asyncio
import base64
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import select

from app.database import get_session_factory
from app.models import Organization

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_legacy_org_profile_migrates_to_facts(test_client):
    async def seed_legacy() -> None:
        sf = get_session_factory()
        async with sf() as session:
            r = await session.execute(select(Organization).where(Organization.id == "default-org"))
            org = r.scalar_one()
            org.legal_name = "Migrated Legal LLC"
            await session.commit()

    asyncio.run(seed_legacy())
    test_client.get("/api/v1/org")
    facts = test_client.get("/api/v1/org/facts").json()
    assert any(
        f.get("key") == "Legal name" and "Migrated Legal" in (f.get("value") or "") for f in facts
    )

    async def check_cleared() -> None:
        sf = get_session_factory()
        async with sf() as session:
            r = await session.execute(select(Organization).where(Organization.id == "default-org"))
            org = r.scalar_one()
            assert not (org.legal_name or "").strip()

    asyncio.run(check_cleared())


def test_org_put_sets_header_display_name(test_client):
    r = test_client.put(
        "/api/v1/org",
        json={"header_display_name": "  Acme Foundation  "},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["header_display_name"] == "Acme Foundation"
    get_r = test_client.get("/api/v1/org")
    assert get_r.json()["header_display_name"] == "Acme Foundation"


def test_org_banner_upload_fetch_and_delete(test_client):
    up = test_client.post(
        "/api/v1/org/banner",
        files={"file": ("one.png", PNG_1X1, "image/png")},
    )
    assert up.status_code == 200
    key = up.json()["banner_file_key"]
    assert key
    assert key.endswith(".png")
    fr = test_client.get(f"/api/v1/files/{key}")
    assert fr.status_code == 200
    assert fr.content[:8] == b"\x89PNG\r\n\x1a\n"

    rm = test_client.delete("/api/v1/org/banner")
    assert rm.status_code == 200
    assert rm.json().get("banner_file_key") in (None, "")


def test_org_banner_rejects_non_image(test_client):
    r = test_client.post(
        "/api/v1/org/banner",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 415


def test_org_put_clear_banner(test_client):
    up = test_client.post(
        "/api/v1/org/banner",
        files={"file": ("one.png", PNG_1X1, "image/png")},
    )
    assert up.status_code == 200
    assert up.json()["banner_file_key"]

    cleared = test_client.put("/api/v1/org", json={"clear_banner": True})
    assert cleared.status_code == 200
    assert cleared.json().get("banner_file_key") in (None, "")


def test_preferences_default_and_patch(test_client):
    r = test_client.get("/api/v1/preferences")
    assert r.status_code == 200
    assert r.json()["locale"] == "iso"

    p = test_client.patch("/api/v1/preferences", json={"locale": "en-US"})
    assert p.status_code == 200
    assert p.json()["locale"] == "en-US"

    again = test_client.get("/api/v1/preferences")
    assert again.json()["locale"] == "en-US"


def test_preferences_invalid_locale_422(test_client):
    r = test_client.patch("/api/v1/preferences", json={"locale": "not a locale !!!"})
    assert r.status_code == 422


def test_developer_credits_reads_settings(test_client):
    app = test_client.app
    s = app.state.settings
    app.state.settings = s.model_copy(
        update={
            "grantfiller_dev_display_name": "Test Dev",
            "grantfiller_dev_github_url": "https://github.com/example",
            "grantfiller_dev_linkedin_url": "https://linkedin.com/in/example",
            "grantfiller_dev_sponsor_text": "Sponsor us",
            "grantfiller_dev_sponsor_url": "https://sponsor.example",
        }
    )
    try:
        r = test_client.get("/api/v1/app/developer-credits")
        assert r.status_code == 200
        j = r.json()
        assert j["display_name"] == "Test Dev"
        assert j["github_url"] == "https://github.com/example"
        assert j["linkedin_url"] == "https://linkedin.com/in/example"
        assert j["sponsor_text"] == "Sponsor us"
        assert j["sponsor_url"] == "https://sponsor.example"
    finally:
        app.state.settings = s


def test_enhancement_appends_jsonl(test_client):
    r = test_client.post("/api/v1/enhancements", json={"message": "Please add dark mode polish."})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    dd = Path(os.environ["DATA_DIR"])
    log = dd / "enhancement_requests.jsonl"
    assert log.is_file()
    last = log.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(last)
    assert row["message"] == "Please add dark mode polish."


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"message": ""},
    ],
)
def test_enhancement_validates_body(test_client, bad):
    r = test_client.post("/api/v1/enhancements", json=bad)
    assert r.status_code == 422
