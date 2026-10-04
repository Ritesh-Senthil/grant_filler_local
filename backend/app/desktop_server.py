"""Production UI and API on one loopback server; no Vite or Node at runtime."""

import os
from pathlib import Path, PurePosixPath

from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.main import app


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        # Unknown API requests and missing assets must remain real 404s.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or PurePosixPath(path).suffix:
                raise
            if scope["method"] not in {"GET", "HEAD"}:
                raise
            return await super().get_response("index.html", scope)


@app.get("/api/v1/desktop/status")
async def desktop_status():
    return {
        "service": "grantfiller-desktop",
        "install_id": os.environ.get("GRANTFILLER_INSTALL_ID", "development"),
    }


ui_root = Path(os.environ.get(
    "GRANTFILLER_UI_DIR", str(Path(__file__).resolve().parents[2] / "frontend" / "dist")
))
if not (ui_root / "index.html").is_file():
    raise RuntimeError("GrantFiller's built interface is missing. Run setup again.")
app.mount("/", SPAStaticFiles(directory=ui_root, html=True), name="desktop-ui")
