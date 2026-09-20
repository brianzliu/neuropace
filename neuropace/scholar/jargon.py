"""Content-based risk from the transcript alone: which stretches of a lecture were jargon-dense, measured
against OpenAlex (PLAN.md Part III Tier 1, "content-based risk flagging").

The table (data/term_specificity.json.gz, built by scripts/build_jargon_table.py from the `works` snapshot)
gives each stemmed term a specificity in [0, 1]: how concentrated its use is in one field of science across
every English abstract in the slice. A 20-second window's score is the mean specificity of its content words,
and a window is flagged when it stands out against the *same lecture's* other windows (a z-score), not
against an absolute bar: a physics lecture is denser than a history lecture everywhere, and that is not the
signal. What is the signal is the 40 seconds where the lecturer switched registers.

This module is pure: words in, windows and spans out. Nothing here touches the flag pipeline yet; the route
exposes it so the practice lecture's planted segment 3 can be checked before anyone wires it in as a third
flag source.
"""

from __future__ import annotations

import gzip
import json
import re
import statistics
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "term_specificity.json.gz"

# Token normalisation, identical to scripts/build_jargon_table.py (tests/test_scholar.py asserts they agree).
_TOKEN = re.compile(r"[a-z][a-z\-]{3,}")
_SUFFIXES = ("ization", "isation", "ations", "ation", "ities", "ity", "ies", "ing", "ers", "ed", "es", "s")

# A long word the table has never seen is, in a table built from hundreds of thousands of abstracts, almost
# always rare jargon or a proper noun; it is scored as "probably specialised" and reported separately.
UNKNOWN_SPEC = 0.6
UNKNOWN_MIN_LEN = 6
# A window with fewer scored terms than this (a trailing sliver, a pause) is neither baseline nor flaggable.
MIN_TERMS = 4
# Spoken-lecture words that are common in speech but rare in abstracts (so the table over-rates them).
_SPOKEN = frozenset(
    "okay right yeah well thing things actually basically literally really pretty maybe kind sort gonna wanna "
    "let's that's there's here's what's it's we're you're they're i'm don't doesn't didn't can't won't isn't "
    "aren't wasn't weren't going know think mean like just about because something anything everything "
    "everyone someone anyone people today yesterday tomorrow minute minutes second seconds hour hours".split()
)


def stem(w: str) -> str:
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def normalise_token(raw: str) -> str | None:
    w = raw.lower().strip("().,;:'\"[]{}?!<>/\\*+=_~^`|%$#@&")
    if not w or not _TOKEN.fullmatch(w):
        return None
    if w.startswith("-") or w.endswith("-"):
        w = w.strip("-")
        if len(w) < 4:
            return None
    return stem(w)


@lru_cache(maxsize=1)
def load() -> dict | None:
    if not DATA.exists():
        return None
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def available() -> bool:
    return load() is not None


def table_meta() -> dict:
    t = load()
    if not t:
        return {"available": False}
    return {
        "available": True,
        "built_at": t.get("built_at"),
        "works_used": t.get("works_used"),
        "works_seen": t.get("works_seen"),
        "part_files": len(t.get("part_files") or []),
        "terms": len(t.get("terms") or {}),
        "fields": len(t.get("fields") or []),
        # under ~200k usable works the vocabulary is thin and many real terms read as "unknown"
        "dev_sized": (t.get("works_used") or 0) < 200_000,
    }


def lookup(word: str) -> tuple[str | None, float | None, str | None]:
    """(stemmed key, specificity or None when unknown, home field name or None)."""
    t = load()
    key = normalise_token(word)
    if not t or not key:
        return key, None, None
    row = t["terms"].get(key)
    if not row:
        return key, None, None
    return key, float(row[0]), t["fields"][row[1]]["name"]


def _score_terms(words: list[str]) -> tuple[float | None, list[dict], int, int, Counter]:
    """Score one window: mean specificity over its distinct content terms (unknown long words at UNKNOWN_SPEC)."""
    t = load()
    if not t:
        return None, [], 0, 0, Counter()
    seen: dict[str, dict] = {}
    fields: Counter = Counter()
    n_known = n_unknown = 0
    for raw in words:
        if raw.lower() in _SPOKEN:
            continue
        key = normalise_token(raw)
        if not key or key in seen:
            continue
        row = t["terms"].get(key)
        if row:
            spec = float(row[0])
            home = t["fields"][row[1]]["name"]
            seen[key] = {
                "term": raw.lower().strip(".,;:!?"),
                "spec": round(spec, 3),
                "field": home,
                "known": True,
            }
            n_known += 1
            if spec >= 0.5:
                fields[home] += 1
        elif len(key) >= UNKNOWN_MIN_LEN:
            seen[key] = {
                "term": raw.lower().strip(".,;:!?"),
                "spec": UNKNOWN_SPEC,
                "field": None,
                "known": False,
            }
            n_unknown += 1
    if not seen:
        return None, [], 0, 0, fields
    score = sum(d["spec"] for d in seen.values()) / len(seen)
    top = sorted(seen.values(), key=lambda d: (-d["spec"], not d["known"]))[:5]
    return score, top, n_known, n_unknown, fields


def analyze(
    words: list[dict],
    window: float = 20.0,
    step: float = 5.0,
    z_flag: float = 1.5,
    min_score: float = 0.2,
    segments: list[dict] | None = None,
) -> dict:
    """Windows, flagged spans and the lecture's field mix for timestamped words [{w, start, end}].

    `segments` (the lecture's own, with t_start/t_end and optional planted_bad) get a per-segment mean and
    rank so the practice lecture's planted segment can be checked directly."""
    meta = table_meta()
    if not meta["available"] or not words:
        return {"table": meta, "windows": [], "spans": [], "fields": [], "segments": []}
    t_end = max(w["end"] for w in words)
    wins: list[dict] = []
    all_fields: Counter = Counter()
    t0 = 0.0
    while t0 < t_end:
        t1 = t0 + window
        ws = [w["w"] for w in words if w["end"] > t0 and w["start"] < t1]
        score, top, n_known, n_unknown, fields = _score_terms(ws)
        all_fields.update(fields)
        wins.append(
            {
                "t0": round(t0, 2),
                "t1": round(min(t1, t_end), 2),
                "score": None if score is None else round(score, 3),
                "z": None,
                "n_words": len(ws),
                "n_known": n_known,
                "n_unknown": n_unknown,
                "top": top,
            }
        )
        t0 += step
    scores = [
        w["score"] for w in wins if w["score"] is not None and w["n_known"] + w["n_unknown"] >= MIN_TERMS
    ]
    if len(scores) >= 4:
        mu = statistics.fmean(scores)
        sd = statistics.pstdev(scores) or 1e-9
        for w in wins:
            if w["score"] is not None:
                w["z"] = round((w["score"] - mu) / sd, 2)
    # flagged windows -> merged spans
    spans: list[dict] = []
    for w in wins:
        flagged = (
            w["z"] is not None
            and w["z"] >= z_flag
            and (w["score"] or 0) >= min_score
            and w["n_known"] + w["n_unknown"] >= MIN_TERMS
        )
        if not flagged:
            continue
        if spans and w["t0"] <= spans[-1]["t_end"]:
            s = spans[-1]
            s["t_end"] = w["t1"]
            s["peak_z"] = max(s["peak_z"], w["z"])
            for d in w["top"]:
                if d["term"] not in {x["term"] for x in s["terms"]}:
                    s["terms"].append(d)
        else:
            spans.append({"t_start": w["t0"], "t_end": w["t1"], "peak_z": w["z"], "terms": list(w["top"])})
    for s in spans:
        s["terms"] = sorted(s["terms"], key=lambda d: -d["spec"])[:6]
    total_f = sum(all_fields.values()) or 1
    fields_out = [{"field": f, "share": round(n / total_f, 3)} for f, n in all_fields.most_common(6)]
    segs_out: list[dict] = []
    if segments:
        for s in segments:
            in_seg = [
                w["score"]
                for w in wins
                if w["score"] is not None and w["t0"] >= s["t_start"] - 1e-6 and w["t1"] <= s["t_end"] + 1e-6
            ]
            segs_out.append(
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "t_start": s["t_start"],
                    "t_end": s["t_end"],
                    "planted_bad": bool(s.get("planted_bad")),
                    "mean_score": round(statistics.fmean(in_seg), 3) if in_seg else None,
                }
            )
        ranked = sorted((x for x in segs_out if x["mean_score"] is not None), key=lambda x: -x["mean_score"])
        for i, x in enumerate(ranked):
            x["rank"] = i + 1
    return {
        "table": meta,
        "window": window,
        "step": step,
        "z_flag": z_flag,
        "windows": wins,
        "spans": spans,
        "fields": fields_out,
        "segments": segs_out,
        "attribution": "Term specificity computed from OpenAlex works abstracts (openalex.org, CC0).",
    }
