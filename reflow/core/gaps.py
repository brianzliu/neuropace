"""Regenerate gap packages after a session ended (FR-N2..N4 recovery): pure function over stored rows."""

from __future__ import annotations

import asyncio

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
