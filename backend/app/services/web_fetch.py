"""
Fetch public HTTPS pages and extract main text for the parse pipeline.

Security: HTTPS-only, hostname blocklist, resolved IPs must be public (SSRF mitigation).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import re
import shutil
import socket
import ssl
from pathlib import Path
from urllib.parse import ParseResult, urljoin, urlparse

import certifi
import httpx
import trafilatura

from app.config import Settings
from app.services.ingest import TextSegment, extract_pdf_bytes

logger = logging.getLogger(__name__)

# ngrok free tier serves an interstitial HTML page to automated clients unless this header is set.
# See https://ngrok.com/docs/http/request-headers/
_NGROK_SKIP_WARNING = "ngrok-skip-browser-warning"

# Suspiciously short main text — try linked PDFs (many RFP pages are shells).
_PDF_FALLBACK_MAIN_TEXT_MAX = 800
_PDF_HREF_RE = re.compile(
    r"""href\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)


class WebFetchError(Exception):
    """User-visible fetch / extraction failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _blocked_hostname(host: str) -> bool:
    h = host.lower().rstrip(".")
    if not h:
        return True
    if h in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"):
        return True
    if h.endswith(".local") or h.endswith(".localhost"):
        return True
    if h.startswith("127."):
        return True
    return False


def _parse_http_local_ports(s: str) -> frozenset[int]:
    out: set[int] = set()
    for part in (s or "").split(","):
        part = part.strip()
        if part:
            out.add(int(part))
    return frozenset(out)


def _assert_safe_http_localhost(parsed: ParseResult, settings: Settings) -> ParseResult:
    """http://127.0.0.1:PORT or http://localhost:PORT only; loopback-only DNS for localhost."""
    if parsed.username or parsed.password:
        raise WebFetchError("AUTH_NOT_ALLOWED", "URLs with credentials are not allowed")
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in ("127.0.0.1", "localhost"):
        raise WebFetchError("HOST_BLOCKED", "Only 127.0.0.1 or localhost is allowed for HTTP local fetch")
    allowed = _parse_http_local_ports(settings.web_fetch_http_local_ports)
    port = parsed.port or 80
    if port not in allowed:
        raise WebFetchError(
            "PORT_BLOCKED",
            f"Port {port} is not allowed for local HTTP fetch (allowed: {', '.join(map(str, sorted(allowed)))})",
        )
    if host == "localhost":
        try:
            infos = socket.getaddrinfo("localhost", port, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise WebFetchError("DNS_FAILED", f"Could not resolve host: {e}") from e
        for info in infos:
            ip = info[4][0]
            addr = ipaddress.ip_address(ip.split("%")[0])
            if not addr.is_loopback:
                raise WebFetchError("HOST_BLOCKED", "localhost must resolve to loopback only")
    return parsed


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        return False
    if addr.is_private or addr.is_unspecified:
        return False
    # Unique local (fc00::/7), documentation, etc.
    if hasattr(addr, "is_global"):
        return bool(addr.is_global)
    return True


def assert_safe_url(url: str, settings: Settings | None = None) -> ParseResult:
    """Parse and validate URL for server-side fetch. Raises WebFetchError."""
    raw = (url or "").strip()
    if not raw:
        raise WebFetchError("URL_REQUIRED", "URL is empty")
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()

    if (
        settings is not None
        and settings.web_fetch_allow_http_localhost
        and scheme == "http"
    ):
        return _assert_safe_http_localhost(parsed, settings)

    if scheme != "https":
        raise WebFetchError(
            "HTTPS_ONLY",
            "Only https:// URLs are allowed. To allow http:// for localhost during "
            "development, set WEB_FETCH_ALLOW_HTTP_LOCALHOST=true in backend/.env "
            "(and WEB_FETCH_HTTP_LOCAL_PORTS if needed).",
        )
    if not parsed.hostname:
        raise WebFetchError("INVALID_URL", "Invalid URL")
    if _blocked_hostname(parsed.hostname):
        raise WebFetchError("HOST_BLOCKED", "This hostname is not allowed")
    if parsed.username or parsed.password:
        raise WebFetchError("AUTH_NOT_ALLOWED", "URLs with credentials are not allowed")
    port = parsed.port or 443
    if port != 443:
        raise WebFetchError("PORT_BLOCKED", "Only the default HTTPS port (443) is allowed")

    host = parsed.hostname
    assert host is not None
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise WebFetchError("DNS_FAILED", f"Could not resolve host: {e}") from e
    if not infos:
        raise WebFetchError("DNS_FAILED", "Could not resolve host")
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise WebFetchError("NON_PUBLIC_IP", "Resolved address is not a public host")
    return parsed


def _html_to_text(html: bytes, url: str) -> str:
    decoded = html.decode("utf-8", errors="replace")
    text = trafilatura.extract(
        decoded,
        url=url,
        include_comments=False,
        include_tables=True,
    )
    if text and text.strip():
        return text.strip()
    # Fallback: very bare pages
    text2 = trafilatura.extract(decoded, favor_recall=True, include_tables=True)
    return (text2 or "").strip()


def _collect_pdf_hrefs(html: bytes, base_url: str) -> list[str]:
    decoded = html.decode("utf-8", errors="replace")
    seen: set[str] = set()
    out: list[str] = []
    for m in _PDF_HREF_RE.finditer(decoded):
        href = m.group(1).strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme.lower() != "https":
            continue
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out[:3]


def _verify_for_httpx(settings: Settings) -> bool | ssl.SSLContext:
    """Explicit CA bundle + TLS context; avoids macOS/Python OpenSSL mismatches with plain verify=True."""
    if not settings.web_fetch_ssl_verify:
        return False
    ctx = ssl.create_default_context(cafile=certifi.where())
    return ctx


def _looks_like_ssl_handshake_failure(msg: str) -> bool:
    low = msg.lower()
    return any(
        x in low
        for x in (
            "ssl",
            "tls",
            "certificate",
            "record layer",
            "handshake",
            "wrong version",
        )
    )


async def _curl_download_bytes(url: str, max_bytes: int, headers: dict[str, str]) -> tuple[bytes, str, int]:
    """Fallback when Python's SSL stack fails (common with some tunnels + Python 3.12+ on macOS). Uses system curl."""
    if not shutil.which("curl"):
        raise WebFetchError(
            "FETCH_FAILED",
            "HTTPS fetch failed (SSL). Install curl or set WEB_FETCH_SSL_VERIFY=false for local debugging only.",
        )
    fd, tmp_path = tempfile_mkstemp_clean()
    os.close(fd)
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-sS",
            "-L",
            "--max-filesize",
            str(max_bytes),
            "-H",
            f"User-Agent: {headers['User-Agent']}",
            "-H",
            f"{_NGROK_SKIP_WARNING}: {headers.get(_NGROK_SKIP_WARNING, 'true')}",
            "-o",
            tmp_path,
            "-w",
            "%{http_code}\n%{url_effective}",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            detail = (err.decode() or out.decode() or "curl failed").strip()
            raise WebFetchError("FETCH_FAILED", detail)
        lines = out.decode().strip().split("\n", 1)
        status = int(lines[0].strip())
        final_url = lines[1].strip() if len(lines) > 1 else url
        body = Path(tmp_path).read_bytes()
        if len(body) > max_bytes:
            raise WebFetchError("RESPONSE_TOO_LARGE", f"Response exceeds {max_bytes} bytes")
        if status >= 400:
            raise WebFetchError("HTTP_ERROR", f"HTTP {status}")
        return body, final_url, status
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def tempfile_mkstemp_clean() -> tuple[int, str]:
    import tempfile

    return tempfile.mkstemp(prefix="gf_fetch_", suffix=".bin")


async def _download_bytes(
    settings: Settings,
    url: str,
    headers: dict[str, str],
) -> tuple[bytes, str, int, str]:
    """GET url: httpx first, then curl if SSL handshake fails. Returns (body, final_url, status, backend)."""
    max_bytes = settings.web_fetch_max_bytes
    timeout = httpx.Timeout(settings.web_fetch_timeout_s)
    limits = httpx.Limits(max_connections=5)
    verify = _verify_for_httpx(settings)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            headers=headers,
            http2=False,
            trust_env=settings.web_fetch_trust_env,
            verify=verify,
        ) as client:
            try:
                r = await client.get(url, follow_redirects=True)
            except httpx.TimeoutException as e:
                raise WebFetchError("TIMEOUT", "Request timed out") from e
            except httpx.RequestError as e:
                if _looks_like_ssl_handshake_failure(str(e)) and settings.web_fetch_ssl_verify:
                    logger.warning("httpx TLS failed (%s); retrying with curl", e)
                    b, u, s = await _curl_download_bytes(url, max_bytes, headers)
                    return b, u, s, "curl"
                raise WebFetchError("FETCH_FAILED", f"Could not fetch URL: {e}") from e
            final_url = str(r.url)
            status = r.status_code
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise WebFetchError("HTTP_ERROR", f"HTTP {e.response.status_code}") from e
            body = r.content
            if len(body) > max_bytes:
                raise WebFetchError("RESPONSE_TOO_LARGE", f"Response exceeds {max_bytes} bytes")
            return body, final_url, status, "httpx"
    except WebFetchError:
        raise
    except Exception as e:
        if _looks_like_ssl_handshake_failure(str(e)) and settings.web_fetch_ssl_verify and shutil.which("curl"):
            logger.warning("httpx error (%s); retrying with curl", e)
            b, u, s = await _curl_download_bytes(url, max_bytes, headers)
            return b, u, s, "curl"
        raise


async def _fetch_rendered_html_playwright(url: str, settings: Settings) -> tuple[bytes, str]:
    """
    Load URL in headless Chromium (executes JS), return (html_bytes, final_url).
    Re-validates URL after redirects (SSRF). Raises WebFetchError.
    """
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise WebFetchError(
            "PLAYWRIGHT_UNAVAILABLE",
            "Playwright is not installed. Run: pip install playwright && playwright install chromium",
        ) from e

    assert_safe_url(url, settings)
    timeout_ms = max(5_000, settings.web_fetch_playwright_timeout_ms)
    post_load_s = max(0.0, settings.web_fetch_playwright_post_load_ms / 1000.0)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=settings.web_fetch_user_agent,
                    extra_http_headers={_NGROK_SKIP_WARNING: "true"},
                    ignore_https_errors=not settings.web_fetch_ssl_verify,
                )
                page = await context.new_page()
                page.set_default_navigation_timeout(timeout_ms)
                await page.goto(url, wait_until="load", timeout=timeout_ms)
                final_url = page.url
                if final_url and final_url != "about:blank":
                    assert_safe_url(final_url, settings)
                if post_load_s > 0:
                    await asyncio.sleep(post_load_s)
                html = await page.content()
                return html.encode("utf-8", errors="replace"), final_url or url
            finally:
                await browser.close()
    except WebFetchError:
        raise
    except PlaywrightError as e:
        msg = str(e).strip() or "browser fetch failed"
        logger.warning("playwright_fetch_failed url=%s err=%s", url, msg)
        raise WebFetchError(
            "PLAYWRIGHT_FAILED",
            f"Could not render this page in the browser: {msg}. "
            "If this is a first-time setup, run: playwright install chromium",
        ) from e
    except Exception as e:
        msg = str(e).strip() or "browser fetch failed"
        logger.warning("playwright_fetch_failed url=%s err=%s", url, msg)
        raise WebFetchError("PLAYWRIGHT_FAILED", f"Could not render this page: {msg}") from e


async def fetch_web_segments(settings: Settings, url: str) -> tuple[list[TextSegment], dict]:
    """
    Download URL(s), return TextSegments and metadata for job.result_json.
    Raises WebFetchError.
    """
    parsed = assert_safe_url(url, settings)

    headers = {
        "User-Agent": settings.web_fetch_user_agent,
        _NGROK_SKIP_WARNING: "true",
    }

    meta: dict = {"strategy": "https_trafilatura", "final_url": url, "http_status": None, "text_chars": 0}

    if not settings.web_fetch_ssl_verify:
        logger.warning("web_fetch_ssl_verify is disabled — use only for local debugging")

    body, final_url, status, backend = await _download_bytes(settings, url, headers)
    meta["final_url"] = final_url
    meta["http_status"] = status
    meta["fetch_backend"] = backend

    if body.startswith(b"%PDF"):
        segments = extract_pdf_bytes(body)
        meta["strategy"] = "direct_pdf"
        if not segments:
            raise WebFetchError("NO_TEXT", "No text extracted from PDF at URL")
        text_len = sum(len(s.text) for s in segments)
        meta["text_chars"] = text_len
        if text_len < settings.web_min_extracted_chars:
            raise WebFetchError(
                "TEXT_TOO_SHORT",
                "Extracted text is too short; try uploading the PDF or a fuller page.",
            )
        return segments, meta

    text = _html_to_text(body, final_url)
    meta["text_chars"] = len(text)

    if len(text) < _PDF_FALLBACK_MAIN_TEXT_MAX:
        for pdf_url in _collect_pdf_hrefs(body, final_url):
            try:
                assert_safe_url(pdf_url, settings)
                pdf_body, pdf_final, pdf_status, pdf_backend = await _download_bytes(
                    settings, pdf_url, headers
                )
                meta["pdf_fetch_backend"] = pdf_backend
                if not pdf_body.startswith(b"%PDF"):
                    continue
                pdf_segs = extract_pdf_bytes(pdf_body)
                if pdf_segs:
                    text_len = sum(len(s.text) for s in pdf_segs)
                    if text_len >= settings.web_min_extracted_chars:
                        meta["strategy"] = "https_trafilatura_plus_pdf"
                        meta["pdf_url"] = pdf_final
                        meta["pdf_http_status"] = pdf_status
                        meta["text_chars"] = text_len
                        return pdf_segs, meta
            except WebFetchError as e:
                logger.info("pdf_link_skip url=%s err=%s", pdf_url, e)
                continue
            except Exception as e:
                logger.info("pdf_link_fetch_skip url=%s err=%s", pdf_url, e)
                continue

    if len(text) < settings.web_min_extracted_chars:
        if settings.web_fetch_playwright:
            # Render the same document the static client resolved to (post-redirect).
            pw_body, pw_final = await _fetch_rendered_html_playwright(final_url, settings)
            pw_text = _html_to_text(pw_body, pw_final)
            meta["playwright_fallback"] = True
            meta["strategy"] = "playwright_trafilatura"
            meta["final_url"] = pw_final
            meta["fetch_backend"] = "playwright"
            meta["text_chars"] = len(pw_text)
            meta["static_text_chars"] = len(text)
            if len(pw_text) >= settings.web_min_extracted_chars:
                label = f"web:{parsed.hostname or 'unknown'}"
                return [TextSegment(label=label, text=pw_text)], meta
        raise WebFetchError(
            "TEXT_TOO_SHORT",
            "Little or no readable text from this page (JS-only or login wall?). "
            "Try uploading a PDF/DOCX or paste content if available.",
        )

    label = f"web:{parsed.hostname or 'unknown'}"
    return [TextSegment(label=label, text=text)], meta


_BOILERPLATE_HINTS = (
    "cookie policy",
    "privacy policy",
    "terms of service",
    "all rights reserved",
    "enable javascript",
    "javascript is required",
    "sign in to continue",
    "log in to continue",
)


def preview_quality_warnings(combined_text: str, char_count: int) -> list[str]:
    """
    Heuristic flags for UX (not authoritative). Shown next to URL preview before full parse.
    """
    warnings: list[str] = []
    low = (combined_text or "").lower().strip()
    if not low:
        warnings.append(
            "Preview is empty. This page may need login, or only load in a browser step-by-step. Try uploading a PDF of the form."
        )
        return warnings
    if char_count < 2000 and len(low) < 500:
        warnings.append(
            "Little text was extracted. Multi-step wizards and login-only pages often won't show the full application here—prefer a PDF or Word export from the funder."
        )
    for hint in _BOILERPLATE_HINTS:
        if hint in low:
            warnings.append(
                "Text looks like site chrome or legal pages rather than the grant form. Confirm you're on the application page, or use a PDF."
            )
            break
    linkish = low.count("http://") + low.count("https://")
    if linkish > 12 and char_count < 8000:
        warnings.append(
            "Lots of links versus prose—the readable form may not have loaded. Try Preview again after the page finishes loading, or upload a PDF."
        )
    return warnings[:4]


async def preview_web_fetch(settings: Settings, url: str) -> dict:
    """Lightweight preview for UI (same safety rules as parse)."""
    segments, meta = await fetch_web_segments(settings, url)
    combined = "\n\n".join(s.text for s in segments)
    preview = combined[:4000]
    char_count = len(combined)
    return {
        "preview": preview,
        "char_count": char_count,
        "warnings": preview_quality_warnings(combined, char_count),
        "meta": meta,
    }
