"""Thin async client for the OpenAlex REST API (https://api.openalex.org).

Two calls are used: `/text/topics` to label free text with an OpenAlex topic, and `/works` search filtered to
open-access articles and reviews, optionally constrained to topic ids. OpenAlex meters usage per request
(keyless ~$0.10/day, a free account key $1/day); the daily budget headers are surfaced on every response so
the sidecar can report where it stands. Every failure raises `OpenAlexUnavailable`; callers disclose, never
invent.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)

BASE = "https://api.openalex.org"
WORK_FIELDS = (
    "id,title,publication_year,cited_by_count,doi,type,open_access,primary_location,authorships,"
    "abstract_inverted_index,topics,relevance_score"
)
MAX_CLASSIFY_CHARS = 1500


class OpenAlexUnavailable(RuntimeError):
    pass


@dataclass
class Budget:
    """Daily budget as reported by the last response's X-RateLimit headers."""

    limit: int | None = None
    remaining: int | None = None
    used: int | None = None
    reset_seconds: int | None = None
    cost_usd: float | None = None
    remaining_usd: float | None = None

    @classmethod
    def from_headers(cls, h: httpx.Headers) -> Budget:
        def _i(k: str) -> int | None:
            v = h.get(k)
            try:
                return int(v) if v is not None else None
            except ValueError:
                return None

        def _f(k: str) -> float | None:
            v = h.get(k)
            try:
                return float(v) if v is not None else None
            except ValueError:
                return None

        return cls(
            limit=_i("X-RateLimit-Limit"),
            remaining=_i("X-RateLimit-Remaining"),
            used=_i("X-RateLimit-Credits-Used"),
            reset_seconds=_i("X-RateLimit-Reset"),
            cost_usd=_f("X-RateLimit-Cost-USD"),
            remaining_usd=_f("X-RateLimit-Remaining-USD"),
        )

    def as_dict(self) -> dict:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_seconds": self.reset_seconds,
            "remaining_usd": self.remaining_usd,
        }


@dataclass
class Topic:
    id: str  # "T10320"
    name: str
    score: float | None = None
    subfield: str = ""
    field: str = ""
    domain: str = ""
    subfield_id: str = ""  # "subfields/2202"
    field_id: str = ""  # "fields/22"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "subfield": self.subfield,
            "field": self.field,
            "domain": self.domain,
            "subfield_id": self.subfield_id,
            "field_id": self.field_id,
            "path": " > ".join(p for p in (self.domain, self.field, self.subfield, self.name) if p),
        }


@dataclass
class Work:
    id: str
    title: str
    year: int | None
    cited_by: int
    doi: str | None
    kind: str
    venue: str | None
    authors: list[str]
    oa_url: str | None
    landing_url: str | None
    abstract: str
    topic_ids: list[str] = field(default_factory=list)
    relevance: float = 0.0

    @property
    def why(self) -> str:
        return first_sentence(self.abstract)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "cited_by": self.cited_by,
            "doi": self.doi,
            "kind": self.kind,
            "venue": self.venue,
            "authors": self.authors[:3],
            "more_authors": max(0, len(self.authors) - 3),
            "url": self.oa_url or self.landing_url or self.doi or self.id,
            "why": self.why,
        }


def reconstruct_abstract(inv: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; put the words back in order."""
    if not inv:
        return ""
    pos: list[tuple[int, str]] = []
    for w, ps in inv.items():
        for p in ps:
            pos.append((p, w))
    pos.sort()
    return " ".join(w for _, w in pos)


def first_sentence(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    m = re.search(r"^(.{20,}?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    if len(s) > limit:
        s = s[: limit - 1].rsplit(" ", 1)[0] + "..."
    return s


def _short_id(url: str | None) -> str:
    return (url or "").rsplit("/", 1)[-1]


def parse_topic(d: dict) -> Topic:
    return Topic(
        id=_short_id(d.get("id")),
        name=d.get("display_name") or "",
        score=d.get("score"),
        subfield=(d.get("subfield") or {}).get("display_name") or "",
        field=(d.get("field") or {}).get("display_name") or "",
        domain=(d.get("domain") or {}).get("display_name") or "",
        subfield_id=_tail((d.get("subfield") or {}).get("id"), 2),
        field_id=_tail((d.get("field") or {}).get("id"), 2),
    )


def _tail(url: str | None, parts: int) -> str:
    """'https://openalex.org/fields/22' -> 'fields/22', the form the works filter takes."""
    return "/".join((url or "").split("/")[-parts:]) if url else ""


def parse_work(r: dict) -> Work:
    loc = r.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = r.get("open_access") or {}
    return Work(
        id=_short_id(r.get("id")),
        title=(r.get("title") or "").strip() or "(untitled)",
        year=r.get("publication_year"),
        cited_by=int(r.get("cited_by_count") or 0),
        doi=r.get("doi"),
        kind=r.get("type") or "article",
        venue=src.get("display_name") or loc.get("raw_source_name"),
        authors=[
            (a.get("author") or {}).get("display_name") or a.get("raw_author_name") or ""
            for a in (r.get("authorships") or [])
        ],
        oa_url=oa.get("oa_url") or loc.get("pdf_url"),
        landing_url=loc.get("landing_page_url"),
        abstract=reconstruct_abstract(r.get("abstract_inverted_index")),
        topic_ids=[_short_id(t.get("id")) for t in (r.get("topics") or [])],
        relevance=float(r.get("relevance_score") or 0.0),
    )


def rank_works(works: list[Work], n: int = 3) -> list[Work]:
    """Search relevance first (the query is the term the learner missed), citations second, a review or a work
    with an abstract to quote gets a nudge. Candidates far below the best match are dropped, and one row per
    title so a preprint and its journal version don't both show."""
    if not works:
        return []
    max_rel = max(w.relevance for w in works) or 1.0
    max_cit = math.log1p(max(w.cited_by for w in works)) or 1.0

    def score(w: Work) -> float:
        rel = w.relevance / max_rel
        cit = math.log1p(w.cited_by) / max_cit
        s = 0.6 * rel + 0.4 * cit
        if w.kind == "review":
            s += 0.15
        if w.abstract:
            s += 0.1
        return s

    seen: set[str] = set()
    out: list[Work] = []
    for w in sorted(works, key=score, reverse=True):
        if max_rel > 0 and w.relevance / max_rel < 0.1:
            continue
        key = re.sub(r"\W+", " ", w.title.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
        if len(out) >= n:
            break
    return out


class OpenAlexClient:
    def __init__(
        self,
        mailto: str | None = None,
        api_key: str | None = None,
        http: httpx.AsyncClient | None = None,
        timeout: float = 12.0,
    ) -> None:
        self.mailto = mailto
        self.api_key = api_key
        self._http = http
        self._own_http = http is None
        self.timeout = timeout
        self.budget = Budget()
        self.last_error: str | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=self.timeout, headers={"User-Agent": "neuropace-scholar/0.1"}
            )
        return self._http

    async def aclose(self) -> None:
        if self._own_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    def _params(self, **kw: str) -> dict[str, str]:
        p = {k: v for k, v in kw.items() if v}
        if self.mailto:
            p["mailto"] = self.mailto
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    async def _get(self, path: str, **params: str) -> dict:
        try:
            r = await self.http.get(f"{BASE}{path}", params=self._params(**params))
        except httpx.HTTPError as e:
            self.last_error = f"openalex: {e.__class__.__name__}"
            raise OpenAlexUnavailable(self.last_error) from e
        self.budget = Budget.from_headers(r.headers)
        if r.status_code == 429:
            self.last_error = "openalex: daily budget exhausted (429)"
            raise OpenAlexUnavailable(self.last_error)
        if r.status_code >= 400:
            self.last_error = f"openalex: HTTP {r.status_code}"
            raise OpenAlexUnavailable(self.last_error)
        try:
            return r.json()
        except ValueError as e:
            self.last_error = "openalex: bad JSON"
            raise OpenAlexUnavailable(self.last_error) from e

    async def classify(self, text: str) -> list[Topic]:
        """Label free text with OpenAlex topics (primary first). The endpoint reads `title`; a long
        paragraph works fine there, so lecture text goes in as-is, truncated."""
        text = re.sub(r"\s+", " ", text or "").strip()[:MAX_CLASSIFY_CHARS]
        if not text:
            return []
        d = await self._get("/text/topics", title=text)
        topics = [parse_topic(t) for t in (d.get("topics") or [])]
        prim = d.get("primary_topic")
        if prim and (not topics or topics[0].id != _short_id(prim.get("id"))):
            topics.insert(0, parse_topic(prim))
        return topics

    async def search_works(
        self,
        query: str,
        topic_ids: list[str] | None = None,
        field_ids: list[str] | None = None,
        n: int = 6,
    ) -> list[Work]:
        """Open-access articles and reviews matching `query`, by search relevance, constrained to `topic_ids`
        (or, wider, `field_ids` like "fields/22") when given. Returns the raw candidates; `rank_works` picks the
        ones to show."""
        query = re.sub(r"\s+", " ", query or "").strip()
        if not query:
            return []
        flt = "is_oa:true,type:article|review"
        if topic_ids:
            flt += ",topics.id:" + "|".join(t for t in topic_ids if t)
        elif field_ids:
            flt += ",topics.field.id:" + "|".join(f for f in field_ids if f)
        d = await self._get(
            "/works",
            search=query,
            filter=flt,
            per_page=str(max(1, min(n, 25))),
            select=WORK_FIELDS,
        )
        return [parse_work(r) for r in (d.get("results") or [])]
