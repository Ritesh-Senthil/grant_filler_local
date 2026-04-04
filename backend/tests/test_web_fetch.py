"""URL policy and HTML extraction (no live network)."""

import pytest

from app.config import Settings
from app.services.web_fetch import (
    WebFetchError,
    _collect_pdf_hrefs,
    _html_to_text,
    assert_safe_url,
)


def test_assert_safe_url_requires_https():
    with pytest.raises(WebFetchError, match="https"):
        assert_safe_url("http://example.com/page")


def test_assert_safe_url_blocks_localhost():
    with pytest.raises(WebFetchError):
        assert_safe_url("https://localhost/foo")


def test_assert_safe_url_blocks_credentials():
    with pytest.raises(WebFetchError, match="credentials"):
        assert_safe_url("https://user:pass@example.com/x")


def test_assert_safe_url_blocks_non_443():
    with pytest.raises(WebFetchError, match="port"):
        assert_safe_url("https://example.com:8443/x")


def test_assert_safe_url_allows_http_localhost_when_enabled():
    s = Settings(web_fetch_allow_http_localhost=True)
    p = assert_safe_url("http://127.0.0.1:8765/index.html", settings=s)
    assert p.hostname == "127.0.0.1"
    assert p.port == 8765


def test_assert_safe_url_blocks_http_localhost_wrong_port_when_enabled():
    s = Settings(web_fetch_allow_http_localhost=True)
    with pytest.raises(WebFetchError, match="Port"):
        assert_safe_url("http://127.0.0.1:9999/x", settings=s)


def test_collect_pdf_hrefs():
    html = b'<html><a href="/files/rfp.pdf">x</a><a href="https://other.example.org/a.PDF?x=1">y</a></html>'
    hrefs = _collect_pdf_hrefs(html, "https://grant.example.org/apply")
    assert "https://grant.example.org/files/rfp.pdf" in hrefs
    assert "https://other.example.org/a.PDF?x=1" in hrefs


def test_html_to_text_basic():
    html = b"""<!DOCTYPE html><html><body><article><h1>Grant</h1><p>What is your mission?</p></article></body></html>"""
    t = _html_to_text(html, "https://example.org/g")
    assert "mission" in t.lower()


@pytest.mark.asyncio
async def test_fetch_web_segments_mocked_httpx(monkeypatch):
    """Happy path: HTML body with enough text (mocked transport, no DNS)."""
    import httpx
    from urllib.parse import urlparse

    from app.services import web_fetch as wf

    html_page = b"""<!DOCTYPE html><html><body><main>""" + (b"Question one: What is your vision? " * 50) + b"""</main></body></html>"""

    async def fake_get(url, follow_redirects=True):
        req = httpx.Request("GET", url)
        return httpx.Response(200, content=html_page, request=req)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, follow_redirects=True):
            return await fake_get(url, follow_redirects)

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    def fake_assert(u: str, settings=None):
        p = urlparse(u)
        if p.scheme != "https":
            raise WebFetchError("HTTPS_ONLY", "n")
        return p

    monkeypatch.setattr(wf, "assert_safe_url", fake_assert)

    settings = Settings()
    segs, meta = await wf.fetch_web_segments(settings, "https://example.org/app")
    assert segs
    assert meta.get("http_status") == 200
    assert meta.get("text_chars", 0) >= settings.web_min_extracted_chars


@pytest.mark.asyncio
async def test_fetch_web_segments_playwright_fallback(monkeypatch):
    """Thin static HTML triggers Playwright path; mocked (no real browser)."""
    from urllib.parse import urlparse

    from app.services import web_fetch as wf

    html_short = b"<!DOCTYPE html><html><body><p>hi</p></body></html>"
    html_rendered = (
        b"<!DOCTYPE html><html><body><main>"
        + (b"What is your mission? " * 80)
        + b"</main></body></html>"
    )

    async def fake_download(*a, **kw):
        return html_short, "https://example.org/app", 200, "httpx"

    async def fake_pw(u: str, settings):
        assert "example.org" in u
        return html_rendered, "https://example.org/app"

    def fake_assert(u: str, settings=None):
        p = urlparse(u)
        if p.scheme != "https":
            raise WebFetchError("HTTPS_ONLY", "n")
        return p

    monkeypatch.setattr(wf, "_download_bytes", fake_download)
    monkeypatch.setattr(wf, "_fetch_rendered_html_playwright", fake_pw)
    monkeypatch.setattr(wf, "assert_safe_url", fake_assert)

    settings = Settings()
    segs, meta = await wf.fetch_web_segments(settings, "https://example.org/app")
    assert segs and len(segs) == 1
    assert meta.get("fetch_backend") == "playwright"
    assert meta.get("strategy") == "playwright_trafilatura"
    assert meta.get("playwright_fallback") is True
    assert meta.get("text_chars", 0) >= settings.web_min_extracted_chars
