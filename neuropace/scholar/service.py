"""Turn a session's gaps into "go deeper" references: one OpenAlex works search per missed moment, constrained
to the lecture's topic, cached by gap id. Read-only over the main store; the gap package is never modified.

Sources are tagged so the UI can say where they came from:
  "openalex"     fetched from the API for this gap
  "cache"        served from this sidecar's cache
  "unavailable"  the API could not be reached (network, budget) — items are empty and the error is kept
  "disabled"     NEUROPACE_SCHOLAR=off
  "empty"        nothing open-access matched inside the lecture's topic or field (or the lecture has no label)
Lecture topics carry "openalex" or "local" (the bundled-table classifier) the same way.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import Counter

from ..config import Settings
from . import topics as topictable
from .cache import ScholarCache
from .openalex import OpenAlexClient, OpenAlexUnavailable, Topic, Work, parse_work, rank_works

log = logging.getLogger(__name__)

_STOP = frozenset(
    "the a an and or of to in on for with by at from as is are was were be been being this that these those it "
    "its we you they he she our your their not no so if then than into over under about between through during "
    "before after above below up down out off again further once here there when where why how all any both each "
    "few more most other some such only own same too very can will just should now also like really okay right "
    "going gonna kind sort thing things something actually basically because which what who would could".split()
)
PER_GAP = 3
CANDIDATES = 8


def _content_words(text: str, n: int = 3) -> list[str]:
    # five letters and up: short function words ("does", "track", "then") are what a spoken span is mostly made of
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{4,}", text.lower()) if w not in _STOP]
    return [w for w, _ in Counter(words).most_common(n)]


def gap_query(gap: dict, keyterms: list[str]) -> str:
    """The note's key term when a model wrote the notes (that is what the learner missed), plus lecture key terms
    that were actually said in the span; otherwise the span's most repeated content words. The extractive
    offline stand-in (package_source "offline", tests and no-key runs) picks its "key term" by position, not
    meaning, so its term is not used."""
    pkg = gap.get("package") or {}
    parts: list[str] = []
    if gap.get("package_source") not in ("offline", "failed", None):
        term = ((pkg.get("note") or {}).get("key_term") or "").strip()
        if not term:
            term = (((pkg.get("artifacts") or {}).get("key_idea") or {}).get("term") or "").strip()
        if term:
            parts.append(term)
    span = (gap.get("span_text") or "").lower()
    ctx = (gap.get("context_text") or "").lower()
    for where in (span, ctx):
        for k in keyterms:
            k = (k or "").strip()
            if k and k.lower() in where and k.lower() not in " ".join(parts).lower():
                parts.append(k)
            if len(parts) >= 3:
                break
        if len(parts) >= 2:
            break
    if not parts:
        parts = _content_words(gap.get("span_text") or "")
    return " ".join(parts)[:200]


class ScholarService:
    def __init__(
        self, settings: Settings, db, client: OpenAlexClient | None = None, cache: ScholarCache | None = None
    ):
        self.s = settings
        self.db = db
        self.enabled = os.environ.get("NEUROPACE_SCHOLAR", "on").strip().lower() not in (
            "off",
            "0",
            "false",
            "no",
        )
        self.client = client or OpenAlexClient(
            mailto=os.environ.get("OPENALEX_MAILTO") or None,
            api_key=os.environ.get("OPENALEX_API_KEY") or None,
        )
        self.cache = cache or ScholarCache(settings.data_dir / "scholar.db")
        self._sem = asyncio.Semaphore(3)

    async def aclose(self) -> None:
        await self.client.aclose()
        self.cache.close()

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "api_key": bool(self.client.api_key),
            "mailto": bool(self.client.mailto),
            "topic_table": {
                "available": topictable.available(),
                "count": topictable.load()["count"],
                "snapshot_date": topictable.load().get("snapshot_date"),
            },
            "budget": self.client.budget.as_dict(),
            "last_error": self.client.last_error,
        }

    # ---------------------------------------------------------------- lecture topics
    def _lecture_text(self, lecture_id: str | None, session_id: str | None) -> tuple[str, list[str]]:
        title, keyterms, words = "", [], []
        if lecture_id:
            lec = self.db.get_lecture(lecture_id, full=True) or {}
            title = lec.get("title") or ""
            keyterms = list(lec.get("keyterms") or [])
            words = lec.get("words") or []
        if not words and session_id:
            words = self.db.get_words(session_id)
        body = " ".join(w.get("w", "") for w in words[:400])
        text = " ".join(p for p in (title, ", ".join(keyterms[:12]), body) if p)
        return text, keyterms

    async def lecture_topics(
        self, lecture_id: str | None, session_id: str | None = None, refresh: bool = False
    ) -> dict:
        key = lecture_id or (f"session:{session_id}" if session_id else None)
        if not key:
            return {"source": "empty", "topics": []}
        if not refresh:
            cached = self.cache.get_lecture_topics(key)
            if cached and (cached["topics"] or cached["source"] != "unavailable"):
                return cached
        text, _ = self._lecture_text(lecture_id, session_id)
        if not text.strip():
            return {"source": "empty", "topics": []}
        topics: list[Topic] = []
        source = "unavailable"
        if self.enabled:
            try:
                topics = await self.client.classify(text)
                source = "openalex"
            except OpenAlexUnavailable as e:
                log.info("lecture topic classification unavailable: %s", e)
        else:
            source = "disabled"
        if not topics:
            local = topictable.classify_local(text)
            if local:
                topics, source = local, "local" if source in ("unavailable", "disabled") else source
        return self.cache.put_lecture_topics(key, source, [t.as_dict() for t in topics])

    # ---------------------------------------------------------------- gap references
    async def _search(self, query: str, topic_ids: list[str], field_ids: list[str]) -> tuple[list[Work], str]:
        """Inside the lecture's topic first; if nothing matches there, widen to its field. Never unconstrained:
        an off-field paper that happens to share a word is worse than saying nothing."""
        scope = topic_ids + field_ids
        cached = self.cache.get_query(query, scope)
        if cached is not None:
            return [parse_work(r) for r in cached], "cache"
        raw = await self._search_raw(query, topic_ids, [])
        if not raw and field_ids:
            raw = await self._search_raw(query, [], field_ids)
        if not raw and not topic_ids and not field_ids:
            raw = []  # no label at all for this lecture: no search either
        self.cache.put_query(query, scope, raw)
        return [parse_work(r) for r in raw], "openalex"

    async def _search_raw(self, query: str, topic_ids: list[str], field_ids: list[str]) -> list[dict]:
        if not topic_ids and not field_ids:
            return []
        works = await self.client.search_works(query, topic_ids, field_ids, n=CANDIDATES)
        # keep the raw-ish dict form the cache can replay through parse_work
        return [_work_to_raw(w) for w in works]

    async def session_references(self, session_id: str, refresh: bool = False) -> dict:
        sess = self.db.get_session(session_id)
        if not sess:
            raise KeyError(session_id)
        gaps = self.db.get_gaps(session_id)
        lecture_id = sess.get("lecture_id")
        topics = await self.lecture_topics(lecture_id, session_id)
        topic_ids = [t["id"] for t in topics["topics"][:1] if t.get("id")]
        field_ids = sorted({t["field_id"] for t in topics["topics"][:2] if t.get("field_id")})
        _, keyterms = self._lecture_text(lecture_id, session_id)
        if refresh:
            self.cache.clear_session(session_id)
        have = self.cache.get_gap_refs(session_id)
        shown = topics["topics"][:1]
        out: dict[str, dict] = {}
        todo: dict[str, list[str]] = {}  # query -> gap ids, so two moments on one term cost one search
        for g in gaps:
            gid = g["id"]
            prior = have.get(gid)
            if prior and (prior["items"] or prior["source"] in ("empty", "disabled")):
                out[gid] = prior
                continue
            query = gap_query(g, keyterms)
            if not query:
                out[gid] = self.cache.put_gap_refs(gid, session_id, "", "empty", shown, [])
            elif not self.enabled:
                out[gid] = self.cache.put_gap_refs(gid, session_id, query, "disabled", shown, [])
            else:
                todo.setdefault(query, []).append(gid)

        async def one(query: str, gids: list[str]) -> None:
            async with self._sem:
                try:
                    works, src = await self._search(query, topic_ids, field_ids)
                except OpenAlexUnavailable as e:
                    for gid in gids:
                        out[gid] = self.cache.put_gap_refs(
                            gid, session_id, query, "unavailable", shown, [], error=str(e)
                        )
                    return
            items = [w.as_dict() for w in rank_works(works, PER_GAP)]
            for i, gid in enumerate(gids):
                out[gid] = self.cache.put_gap_refs(
                    gid, session_id, query, (src if i == 0 else "cache") if items else "empty", shown, items
                )

        await asyncio.gather(*(one(q, gids) for q, gids in todo.items()))
        return {
            "session_id": session_id,
            "lecture_id": lecture_id,
            "topics": topics,
            "budget": self.client.budget.as_dict(),
            "gaps": [out[g["id"]] for g in gaps if g["id"] in out],
            "attribution": "Sources via OpenAlex (openalex.org), CC0.",
        }


def _work_to_raw(w: Work) -> dict:
    """Inverse of parse_work, enough for the query cache to round-trip."""
    inv: dict[str, list[int]] | None = None
    if w.abstract:
        inv = {}
        for i, tok in enumerate(w.abstract.split()):
            inv.setdefault(tok, []).append(i)
    return {
        "id": f"https://openalex.org/{w.id}",
        "title": w.title,
        "publication_year": w.year,
        "cited_by_count": w.cited_by,
        "doi": w.doi,
        "type": w.kind,
        "open_access": {"oa_url": w.oa_url},
        "primary_location": {"landing_page_url": w.landing_url, "source": {"display_name": w.venue}},
        "authorships": [{"author": {"display_name": a}} for a in w.authors],
        "abstract_inverted_index": inv,
        "topics": [{"id": f"https://openalex.org/{t}"} for t in w.topic_ids],
        "relevance_score": w.relevance,
    }
