"""Sidecar routes. Mounted under /api next to the main router; they read the main store through
`request.app.state.db` exactly as routes.py does and keep their own state on `app.state.scholar`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from . import jargon
from .service import ScholarService

router = APIRouter()


def _service(request: Request) -> ScholarService:
    svc = getattr(request.app.state, "scholar", None)
    if svc is None:
        svc = ScholarService(request.app.state.settings, request.app.state.db)
        request.app.state.scholar = svc
    elif svc.db is not request.app.state.db:
        # demo mode toggles swap app.state.db; follow it, keep the cache and client
        svc.db = request.app.state.db
    return svc


@router.get("/scholar/status")
def scholar_status(request: Request):
    return {**_service(request).status(), "jargon_table": jargon.table_meta()}


@router.get("/sessions/{session_id}/scholar")
async def session_scholar(session_id: str, request: Request, refresh: bool = False):
    """References for every gap of a session, fetched on first call and cached. `refresh=1` refetches."""
    svc = _service(request)
    try:
        return await svc.session_references(session_id, refresh=refresh)
    except KeyError:
        raise HTTPException(404, "unknown session") from None


@router.get("/lectures/{lecture_id}/scholar/topics")
async def lecture_scholar_topics(lecture_id: str, request: Request, refresh: bool = False):
    svc = _service(request)
    if not request.app.state.db.get_lecture(lecture_id):
        raise HTTPException(404, "unknown lecture")
    return {"lecture_id": lecture_id, **(await svc.lecture_topics(lecture_id, refresh=refresh))}


@router.get("/lectures/{lecture_id}/scholar/jargon")
def lecture_jargon(
    lecture_id: str, request: Request, window: float = 20.0, step: float = 5.0, z: float = 1.5
):
    """Jargon-dense stretches of a lecture from its transcript alone, with the per-segment check."""
    lec = request.app.state.db.get_lecture(lecture_id, full=True)
    if not lec:
        raise HTTPException(404, "unknown lecture")
    out = jargon.analyze(
        lec.get("words") or [], window=window, step=step, z_flag=z, segments=lec.get("segments")
    )
    return {"lecture_id": lecture_id, **out}


@router.get("/sessions/{session_id}/scholar/jargon")
def session_jargon(
    session_id: str, request: Request, window: float = 20.0, step: float = 5.0, z: float = 1.5
):
    """Same, over what was actually transcribed in a session (falls back to the lecture's words)."""
    db = request.app.state.db
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    words = db.get_words(session_id)
    segments = None
    if sess.get("lecture_id"):
        lec = db.get_lecture(sess["lecture_id"], full=True) or {}
        segments = lec.get("segments")
        if not words:
            words = lec.get("words") or []
    out = jargon.analyze(words, window=window, step=step, z_flag=z, segments=segments)
    return {"session_id": session_id, **out}
