"""FastAPI app factory (TDD §9): REST + WebSocket + static frontend, one process."""

from __future__ import annotations

import contextlib
import json
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from .. import __version__
from ..config import Settings, load_settings
from ..demo import DemoData
from ..llm.client import LLMClient
from ..store.db import DB
from . import routes, ws
from .local_bridge import LocalBridgeGuard

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"
DEMO_SCRIPT = ROOT / "data" / "lectures" / "demo" / "script.json"

NO_BUILD_HTML = """<!doctype html><meta charset=utf-8><title>NeuroPace</title>
<body style="font-family:system-ui;padding:2rem;background:#0f1115;color:#e6e6e6">
<h1>NeuroPace API is running</h1><p>The frontend is not built yet. Run:</p>
<pre>cd frontend && pnpm install && pnpm build</pre><p>then reload. API docs: <a href="/docs" style="color:#8ab4f8">/docs</a></p></body>"""


def ensure_demo_lecture(db: DB) -> None:
    if not DEMO_SCRIPT.exists():
        return
    data = json.loads(DEMO_SCRIPT.read_text())
    lid = data.get("id", "lec_demo0001")
    if db.get_lecture(lid):
        return
    db.create_lecture(
        title=data["title"],
        kind="scripted",
        words=data["words"],
        segments=data.get("segments"),
        quiz=data.get("quiz"),
        keyterms=data.get("keyterms"),
        duration=data.get("duration"),
        lecture_id=lid,
    )
    log.info("demo lecture ingested as %s", lid)


def create_app(
    settings: Settings | None = None, db: DB | None = None, llm: LLMClient | None = None
) -> FastAPI:
    s = settings or load_settings()
    s.ensure_dirs()
    db = db or DB(s.db_path)
    ensure_demo_lecture(db)
    demo = DemoData(s)
    active_db = demo.database() if demo.enabled else db
    llm = llm or LLMClient(s, active_db)
    from ..core.gaps import recover_orphaned_sessions

    orphans = recover_orphaned_sessions(db, s)
    if orphans:
        log.info("closed %d session(s) left running by a previous process", len(orphans))

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        import asyncio

        app.state.loop = asyncio.get_running_loop()
        yield
        for rt in list(app.state.runtimes.values()):
            with contextlib.suppress(Exception):
                await rt.abort()
        demo.close()

    app = FastAPI(title="NeuroPace", version=__version__, lifespan=lifespan)
    app.state.pairing_token = secrets.token_urlsafe(24)
    app.add_middleware(LocalBridgeGuard, origins=s.ui_origins, token=app.state.pairing_token)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(s.ui_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-NeuroPace-Token", "X-Reflow-Token", "Range"],
        expose_headers=["Content-Range", "Accept-Ranges"],
    )
    app.state.settings = s
    app.state.real_db = db
    app.state.demo = demo
    app.state.db = active_db
    app.state.llm = llm
    app.state.runtimes = {}
    app.state.reviews = {}
    app.state.office_hours = {}
    app.state.loop = None

    def _each_running(fn):
        for rt in list(app.state.runtimes.values()):
            if rt.status == "running":
                fn(rt)

    def tap_all() -> None:
        """Keyboard totem from the terminal: a "lost me" on every running session."""
        _each_running(lambda rt: rt.tap(source="key"))

    def force_all() -> None:
        _each_running(lambda rt: rt.force_flag())

    app.state.tap_all = tap_all
    app.state.force_all = force_all
    app.include_router(routes.router, prefix="/api")
    app.include_router(ws.router)

    @app.get("/api/bridge/check")
    def bridge_check():
        return {"ok": True}

    @app.get("/media/{lecture_id}")
    def media(lecture_id: str):
        lec = app.state.db.get_lecture(lecture_id)
        if not lec or not lec.get("media_path") or not Path(lec["media_path"]).exists():
            return JSONResponse({"error": "no media"}, status_code=404)
        return FileResponse(lec["media_path"])

    if (FRONTEND_DIST / "index.html").exists():
        if (FRONTEND_DIST / "assets").exists():
            app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str, request: Request):
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def no_build():
            return HTMLResponse(NO_BUILD_HTML)

    return app
