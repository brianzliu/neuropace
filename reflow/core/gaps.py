"""Regenerate gap packages after a session ended (FR-N2..N4 recovery): pure function over stored rows."""

from __future__ import annotations

import asyncio
import time

from ..llm.client import LLMClient, LLMUnavailable
from ..store.db import DB


async def regenerate_packages(
    db: DB, llm: LLMClient, session_id: str, only_failed: bool = True
) -> list[dict]:
    gaps = db.get_gaps(session_id)
    words = db.get_words(session_id)
    corpus = " ".join(w["w"] for w in words)
    sess = db.get_session(session_id) or {}
    lecture = db.get_lecture(sess["lecture_id"]) if sess.get("lecture_id") else None
    keyterms = (lecture or {}).get("keyterms") or []
    seed = int(sess.get("seed") or 0)
    todo = [
        g for g in gaps if (not only_failed) or not g.get("package") or g.get("package_source") == "failed"
    ]
    sem = asyncio.Semaphore(4)

    async def fill(g: dict) -> None:
        async with sem:
            try:
                pkg, source = await llm.gap_package(
                    g["span_text"], g.get("context_text") or "", corpus, keyterms, seed=seed + g["ord"]
                )
            except LLMUnavailable as e:
                g["package"] = {"error": str(e)}
                g["package_source"] = "failed"
                return
            g["package"] = pkg.model_dump()
            g["package_source"] = source

    await asyncio.gather(*(fill(g) for g in todo))
    db.replace_gaps(session_id, gaps)
    return gaps


def recover_orphaned_sessions(db: DB, settings) -> list[str]:
    """Sessions left in status running by a previous server process (crash, restart) are closed here.
    Their flags become gaps without notes (package None), so the lecture page offers "write them" via regenerate."""
    from .spans import merge_into_gaps

    recovered: list[str] = []
    for sess in db.list_sessions():
        if sess["status"] != "running":
            continue
        flags = db.get_flags(sess["id"])
        words = db.get_words(sess["id"])
        end = max([w["end"] for w in words] + [f.get("t_end") or f["t_trigger"] for f in flags] + [0.0])
        rows = []
        if words and flags and sess.get("mode") != "review":
            from ..ids import new_id

            for g in merge_into_gaps(flags, settings, lecture_end=end):
                span = " ".join(w["w"] for w in words if w["end"] > g["t_start"] and w["start"] < g["t_end"])
                if not span.strip():
                    continue
                ctx = " ".join(
                    w["w"] for w in words if w["end"] > g["t_start"] - 60.0 and w["start"] < g["t_start"]
                )
                rows.append(
                    {
                        "id": new_id("gap"),
                        "ord": len(rows),
                        "t_start": g["t_start"],
                        "t_end": g["t_end"],
                        "span_text": span,
                        "context_text": ctx,
                        "flag_ids": g["flag_ids"],
                        "package": None,
                        "package_source": "failed",
                        "status": "open",
                    }
                )
        db.replace_gaps(sess["id"], rows)
        db.update_session(sess["id"], status="ended", ended_at=time.time())
        recovered.append(sess["id"])
    return recovered
