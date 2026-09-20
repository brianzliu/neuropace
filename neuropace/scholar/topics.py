"""The bundled OpenAlex topic table (data/openalex_topics.json, built by scripts/fetch_openalex_topics.py from
the AWS Open Data snapshot) and a keyword-overlap classifier over it.

The API's `/text/topics` is the primary classifier; this is the offline stand-in so a lecture still gets a
field label when there is no network or the daily budget is spent. It is labelled `source: "local"` wherever it
is used, so a demo never presents the fallback as the API's answer.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .openalex import Topic

DATA = Path(__file__).resolve().parent / "data" / "openalex_topics.json"

_STOP = frozenset(
    "the a an and or of to in on for with by at from as is are was were be been this that these those it its "
    "we you they he she our your their not no so if then than into over under about between through during "
    "before after above below up down out off again further once here there when where why how all any both "
    "each few more most other some such only own same too very can will just should now and studies study "
    "research analysis applications methods method techniques approach approaches systems system based using "
    "effects effect properties process processes".split()
)


@lru_cache(maxsize=1)
def load() -> dict:
    if not DATA.exists():
        return {"count": 0, "topics": [], "snapshot_date": None}
    return json.loads(DATA.read_text(encoding="utf-8"))


def available() -> bool:
    return load()["count"] > 0


def by_id(tid: str) -> Topic | None:
    for t in load()["topics"]:
        if t["id"] == tid:
            return Topic(
                id=t["id"],
                name=t["name"],
                subfield=t["subfield"],
                field=t["field"],
                domain=t["domain"],
                subfield_id=t.get("subfield_id", ""),
                field_id=t.get("field_id", ""),
            )
    return None


def _stem(w: str) -> str:
    # crude English stemming, enough to match "networks" to "network" and "learning" to "learn"
    for suf in (
        "ization",
        "isation",
        "ations",
        "ation",
        "ities",
        "ity",
        "ies",
        "ing",
        "ers",
        "ed",
        "es",
        "s",
    ):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _tokens(s: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in _STOP and len(w) > 1]


@lru_cache(maxsize=1)
def _index() -> list[tuple[dict, list[tuple[frozenset[str], float]]]]:
    """Per topic: its keyword phrases as stemmed token sets, each weighted by how rare the phrase is across
    topics (a keyword shared by many topics says little about which one this is)."""
    topics = load()["topics"]
    df: Counter[frozenset[str]] = Counter()
    per_topic: list[list[frozenset[str]]] = []
    for t in topics:
        phrases = []
        for kw in t["keywords"]:
            toks = frozenset(_tokens(kw))
            if toks:
                phrases.append(toks)
        name = frozenset(_tokens(t["name"]))
        if name:
            phrases.append(name)
        per_topic.append(phrases)
        for p in set(phrases):
            df[p] += 1
    n = max(1, len(topics))
    out = []
    for t, phrases in zip(topics, per_topic, strict=True):
        weighted = [(p, (1.0 + 0.5 * (len(p) - 1)) * math.log(1.0 + n / df[p])) for p in phrases]
        out.append((t, weighted))
    return out


def classify_local(text: str, n: int = 3) -> list[Topic]:
    """Score every topic by the keyword phrases whose words all appear in the text; multiword phrases and rare
    phrases count more. Deliberately simple: this only has to land in the right subfield."""
    toks = set(_tokens(text))
    if len(toks) < 2:
        return []
    scored: list[tuple[float, dict]] = []
    for t, phrases in _index():
        s = 0.0
        hits = 0
        multi = False
        for p, w in phrases:
            if p <= toks:
                s += w
                hits += 1
                multi = multi or len(p) > 1
        # one shared single word ("error", "satellite") is noise; one shared phrase ("french revolution") is not
        if hits >= 2 or multi:
            scored.append((s, t))
    scored.sort(key=lambda x: -x[0])
    top = scored[:n]
    if not top:
        return []
    mx = top[0][0]
    return [
        Topic(
            id=t["id"],
            name=t["name"],
            score=round(s / mx, 3),
            subfield=t["subfield"],
            field=t["field"],
            domain=t["domain"],
            subfield_id=t.get("subfield_id", ""),
            field_id=t.get("field_id", ""),
        )
        for s, t in top
    ]
