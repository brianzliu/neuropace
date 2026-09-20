"""Fetch the OpenAlex `topics` entity from the AWS Open Data snapshot and bundle a compact table.

Source: s3://openalex/data/jsonl/topics/ (https://registry.opendata.aws/openalex/), read over plain HTTPS so
no AWS credentials or boto3 are needed. The manifest lists every partition; a topic can appear in more than one
partition, the latest `updated_date` wins. Output is the few fields the scholar sidecar uses offline:
id, name, keywords and the subfield › field › domain path. ~4.5k rows, about 1 MB.

    uv run python scripts/fetch_openalex_topics.py            # writes neuropace/scholar/data/openalex_topics.json
    uv run python scripts/fetch_openalex_topics.py --check    # only prints the manifest summary
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
from pathlib import Path

import httpx

BUCKET = "https://openalex.s3.amazonaws.com"
MANIFEST = f"{BUCKET}/data/jsonl/topics/manifest.json"
OUT = Path(__file__).resolve().parents[1] / "neuropace" / "scholar" / "data" / "openalex_topics.json"


def _https(s3_url: str) -> str:
    return s3_url.replace("s3://openalex/", f"{BUCKET}/", 1)


def _compact(rec: dict) -> dict:
    return {
        "id": rec["id"].rsplit("/", 1)[-1],
        "name": rec.get("display_name") or "",
        "keywords": list(rec.get("keywords") or []),
        "subfield": (rec.get("subfield") or {}).get("display_name") or "",
        "subfield_id": _tail((rec.get("subfield") or {}).get("id"), 2),
        "field": (rec.get("field") or {}).get("display_name") or "",
        "field_id": _tail((rec.get("field") or {}).get("id"), 2),
        "domain": (rec.get("domain") or {}).get("display_name") or "",
    }


def _tail(url: str | None, parts: int) -> str:
    """'https://openalex.org/fields/22' -> 'fields/22', the form the works filter takes."""
    return "/".join((url or "").split("/")[-parts:]) if url else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="print the manifest summary and exit")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    with httpx.Client(timeout=60.0, follow_redirects=True) as http:
        manifest = http.get(MANIFEST).raise_for_status().json()
        files = manifest["files"]
        print(
            f"snapshot {manifest.get('date')}: {manifest.get('record_count')} topics in {len(files)} partitions, "
            f"{manifest.get('content_length', 0) / 1e6:.1f} MB compressed"
        )
        if args.check:
            return 0
        topics: dict[str, dict] = {}
        # manifest order is oldest updated_date first; later partitions overwrite
        for f in files:
            url = _https(f["url"])
            raw = http.get(url).raise_for_status().content
            n = 0
            with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    topics[rec["id"]] = _compact(rec)
                    n += 1
            print(f"  {url.rsplit('/', 2)[-2]}: {n} records")

    rows = sorted(topics.values(), key=lambda r: r["id"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "s3://openalex/data/jsonl/topics (AWS Open Data registry)",
        "snapshot_date": manifest.get("date"),
        "count": len(rows),
        "topics": rows,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(rows)} topics to {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
