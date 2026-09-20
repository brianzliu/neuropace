"""Build the term-specificity ("jargon") table from a slice of the OpenAlex `works` snapshot.

Input: part files in the layout Voloridge's `fetch.py` (and any `aws s3 sync`) produces,
    <root>/works/updated_date=YYYY-MM-DD/part_NNNN.gz        (gzipped JSON Lines, one work per line)
Output: neuropace/scholar/data/term_specificity.json.gz, read by neuropace/scholar/jargon.py.

What is computed. For every English work with an abstract and a primary topic, the abstract's unique tokens
(the keys of `abstract_inverted_index` — no reconstruction needed) are normalised and stemmed, and each term's
document frequency is counted per OpenAlex *field* (26 of them: Medicine, Computer Science, ...). A term's
specificity is how concentrated those counts are across fields, measured against the corpus's own field mix:

    p(f | t) = df(t, f) / df(t)            q(f) = N_f / N
    specificity(t) = KL(p || q) / log(1 / q(home))         home = argmax_f p(f | t), clipped to [0, 1]

The denominator is the KL a term would reach if it lived *only* in its home field, so an exclusive term
scores 1 whether its field is Medicine (a third of the corpus) or Dentistry (under one percent).

A term used evenly across science ("results", "method", "increase") scores ~0; a term that lives in one
field ("pseudorange", "thylakoid", "backpropagation") scores near 1. This is TF-IDF with fields as the
documents, which is what makes it a jargon measure rather than a general-English rarity measure. The table
also keeps each term's home field and log10 document frequency, so the runtime can tell rare jargon from
common jargon and say which field a lecture window drew from.

Scale. Pure Python, one worker per part file (multiprocessing), a cheap substring pre-filter so works without
abstracts are skipped before JSON parsing. About 180k works per part file; a 30-file slice (~5.5M works,
~5 GB) is the intended run on Voloridge's EC2 instances; three files (~400k works) make a usable dev table.

    uv run python scripts/build_jargon_table.py                      # reads data/openalex, writes the table
    uv run python scripts/build_jargon_table.py --root /path/to/data/openalex --workers 8
    uv run python scripts/build_jargon_table.py --max-files 3 --min-df 10   # small dev table
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "data" / "openalex"
DEFAULT_OUT = ROOT / "neuropace" / "scholar" / "data" / "term_specificity.json.gz"

# The same normalisation the runtime uses (neuropace/scholar/jargon.py imports these two).
_TOKEN = re.compile(r"[a-z][a-z\-]{3,}")
_SUFFIXES = ("ization", "isation", "ations", "ation", "ities", "ity", "ies", "ing", "ers", "ed", "es", "s")


def stem(w: str) -> str:
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def normalise_token(raw: str) -> str | None:
    """One abstract token -> one table key, or None when it is not a word we score (numbers, symbols, short)."""
    w = raw.lower().strip("().,;:'\"[]{}?!<>/\\*+=_~^`|%$#@&")
    if not w or not _TOKEN.fullmatch(w):
        return None
    if w.startswith("-") or w.endswith("-"):
        w = w.strip("-")
        if len(w) < 4:
            return None
    return stem(w)


def _field_id(rec: dict) -> str | None:
    pt = rec.get("primary_topic") or {}
    fid = (pt.get("field") or {}).get("id")
    return fid.rsplit("/", 1)[-1] if fid else None  # "https://openalex.org/fields/17" -> "17"


def count_part(path: str) -> tuple[str, dict[str, Counter], Counter, int, int]:
    """One worker: per-field term document frequencies for one part file."""
    per_field: dict[str, Counter] = {}
    docs_per_field: Counter = Counter()
    seen = kept = 0
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            seen += 1
            # cheap pre-filter before the JSON parse: no abstract, or not English, skip
            if '"abstract_inverted_index":null' in line or '"abstract_inverted_index": null' in line:
                continue
            if '"language":"en"' not in line and '"language": "en"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            inv = rec.get("abstract_inverted_index")
            fid = _field_id(rec)
            if not inv or not fid:
                continue
            terms = {t for t in (normalise_token(k) for k in inv) if t}
            if len(terms) < 8:
                continue
            kept += 1
            docs_per_field[fid] += 1
            c = per_field.get(fid)
            if c is None:
                c = per_field[fid] = Counter()
            c.update(terms)
    return path, per_field, docs_per_field, seen, kept


def reduce_table(
    per_field: dict[str, Counter], docs_per_field: Counter, min_df: int, max_terms: int
) -> tuple[dict[str, list], list[str]]:
    fields = sorted(docs_per_field)
    n_total = sum(docs_per_field.values())
    q = {f: docs_per_field[f] / n_total for f in fields}
    df_total: Counter = Counter()
    for c in per_field.values():
        df_total.update(c)
    rows: dict[str, list] = {}
    for term, df in df_total.items():
        if df < min_df:
            continue
        kl = 0.0
        best_f, best_p = fields[0], -1.0
        for f in fields:
            d = per_field[f].get(term, 0)
            if not d:
                continue
            p = d / df
            kl += p * math.log(p / q[f])
            if p > best_p:
                best_f, best_p = f, p
        norm = math.log(1.0 / q[best_f]) if q[best_f] < 1.0 else 0.0
        spec = max(0.0, min(1.0, kl / norm)) if norm > 0 else 0.0
        rows[term] = [round(spec, 3), fields.index(best_f), round(math.log10(df), 2)]
    if len(rows) > max_terms:
        # keep the most frequent terms: a rare term that fell off the table is treated as "unknown" at runtime
        keep = sorted(rows, key=lambda t: -df_total[t])[:max_terms]
        rows = {t: rows[t] for t in keep}
    return rows, fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_IN, help="fetch.py output dir (contains works/)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-files", type=int, default=None, help="cap on part files (newest first)")
    ap.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    ap.add_argument("--min-df", type=int, default=20, help="drop terms seen in fewer works than this")
    ap.add_argument("--max-terms", type=int, default=200_000)
    args = ap.parse_args()

    parts = sorted((args.root / "works").glob("updated_date=*/part_*.gz"), reverse=True)
    if args.max_files:
        parts = parts[: args.max_files]
    if not parts:
        print(f"no part files under {args.root / 'works'} (run Voloridge's fetch.py --entity works first)")
        return 1
    total_mb = sum(p.stat().st_size for p in parts) / 1e6
    print(f"{len(parts)} part file(s), {total_mb:.0f} MB compressed, {args.workers} worker(s)")

    t0 = time.time()
    per_field: dict[str, Counter] = {}
    docs_per_field: Counter = Counter()
    seen = kept = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(count_part, str(p)): p for p in parts}
        for fut in as_completed(futs):
            path, pf, dpf, s, k = fut.result()
            seen += s
            kept += k
            docs_per_field.update(dpf)
            for f, c in pf.items():
                if f in per_field:
                    per_field[f].update(c)
                else:
                    per_field[f] = c
            print(
                f"  {Path(path).parent.name}/{Path(path).name}: {s:,} works, {k:,} usable  [{time.time() - t0:.0f}s]"
            )

    rows, fields = reduce_table(per_field, docs_per_field, args.min_df, args.max_terms)
    field_names = _field_names(fields)
    payload = {
        "source": "s3://openalex/data/jsonl/works (AWS Open Data registry), abstracts of English works",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "part_files": [f"{p.parent.name}/{p.name}" for p in parts],
        "works_seen": seen,
        "works_used": kept,
        "min_df": args.min_df,
        "fields": [{"id": f, "name": field_names.get(f, f), "docs": docs_per_field[f]} for f in fields],
        "columns": ["specificity", "field_index", "log10_df"],
        "terms": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print(
        f"used {kept:,} of {seen:,} works across {len(fields)} fields; {len(rows):,} terms -> {args.out} "
        f"({args.out.stat().st_size / 1e6:.2f} MB) in {time.time() - t0:.0f}s"
    )
    top = sorted(rows.items(), key=lambda kv: (-kv[1][0], -kv[1][2]))[:12]
    low = sorted((kv for kv in rows.items() if kv[1][2] > 3.5), key=lambda kv: kv[1][0])[:12]
    print("most field-specific (common):", ", ".join(f"{t}({r[0]})" for t, r in top))
    print("least field-specific (common):", ", ".join(f"{t}({r[0]})" for t, r in low))
    return 0


def _field_names(ids: list[str]) -> dict[str, str]:
    """Field names from the bundled topic table (built from the same snapshot), so the output is readable."""
    path = ROOT / "neuropace" / "scholar" / "data" / "openalex_topics.json"
    out: dict[str, str] = {}
    if path.exists():
        for t in json.loads(path.read_text(encoding="utf-8"))["topics"]:
            fid = (t.get("field_id") or "").rsplit("/", 1)[-1]
            if fid and t.get("field"):
                out[fid] = t["field"]
    return {i: out.get(i, i) for i in ids}


if __name__ == "__main__":
    sys.exit(main())
