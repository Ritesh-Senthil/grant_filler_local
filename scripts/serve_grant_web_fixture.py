#!/usr/bin/env python3
"""Serve the static grant website fixture for GrantFiller URL / parse testing.

Serves testdata/grant_web_fixture on http://127.0.0.1:8765/ by default (port must match
WEB_FETCH_HTTP_LOCAL_PORTS when WEB_FETCH_ALLOW_HTTP_LOCALHOST=true in backend/.env).

Usage (from repo root):
    python3 scripts/serve_grant_web_fixture.py

    python3 scripts/serve_grant_web_fixture.py --port 8080

Then in GrantFiller set Grant URL to http://127.0.0.1:8765/ (or chosen port) and use Preview / Parse.
"""

from __future__ import annotations

import argparse
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE_DIR = _REPO_ROOT / "testdata" / "grant_web_fixture"


class FixtureHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(_FIXTURE_DIR), **kwargs)

    def log_message(self, format: str, *log_args: object) -> None:
        # Quieter default; comment out to see each request
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Listen port (must be in WEB_FETCH_HTTP_LOCAL_PORTS, default 8765)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default 127.0.0.1)",
    )
    args = parser.parse_args()

    if not _FIXTURE_DIR.is_dir():
        print(f"Fixture directory not found: {_FIXTURE_DIR}", file=sys.stderr)
        sys.exit(1)

    httpd = ThreadingHTTPServer((args.host, args.port), FixtureHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Serving grant fixture from {_FIXTURE_DIR}")
    print(f"  → Open in browser: {url}")
    print()
    print("GrantFiller: set WEB_FETCH_ALLOW_HTTP_LOCALHOST=true in backend/.env, restart API,")
    print(f"then use this URL as the grant link: {url}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
