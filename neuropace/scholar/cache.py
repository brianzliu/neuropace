"""The scholar sidecar's own SQLite file (data/scholar.db). Kept apart from store/db.py on purpose: nothing in
the main schema changes, and deleting this file only forgets fetched sources.

Rows are keyed by gap id (sources shown under one missed moment) and lecture id (the lecture's topic label).
A query-level cache sits underneath both so regenerating notes for the same term costs no budget."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scholar_gap_refs(
    gap_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    source TEXT NOT NULL,
    topics_json TEXT,
    items_json TEXT NOT NULL,
    error TEXT,
    fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS scholar_gap_refs_session ON scholar_gap_refs(session_id);
CREATE TABLE IF NOT EXISTS scholar_lecture_topics(
    lecture_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    topics_json TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS scholar_query_cache(
    qhash TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    topic_ids TEXT NOT NULL,
    works_json TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
"""


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def _uj(s: str | None, default=None):
    if s is None:
        return default
    try:
        return json.loads(s)
    except ValueError:
        return default


class ScholarCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._c.row_factory = sqlite3.Row
        with self._lock:
            self._c.executescript(SCHEMA)
            self._c.commit()

    def close(self) -> None:
        with self._lock:
            self._c.close()

    # ---- gap references ----
    def get_gap_refs(self, session_id: str) -> dict[str, dict]:
        with self._lock:
            rows = self._c.execute(
                "SELECT * FROM scholar_gap_refs WHERE session_id=?", (session_id,)
            ).fetchall()
        out = {}
        for r in rows:
            out[r["gap_id"]] = {
                "gap_id": r["gap_id"],
                "query": r["query"],
                "source": r["source"],
                "topics": _uj(r["topics_json"], []),
                "items": _uj(r["items_json"], []),
                "error": r["error"],
                "fetched_at": r["fetched_at"],
            }
        return out

    def put_gap_refs(
        self,
        gap_id: str,
        session_id: str,
        query: str,
        source: str,
        topics: list[dict],
        items: list[dict],
        error: str | None = None,
    ) -> dict:
        now = time.time()
        with self._lock:
            self._c.execute(
                "INSERT OR REPLACE INTO scholar_gap_refs(gap_id,session_id,query,source,topics_json,items_json,error,fetched_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (gap_id, session_id, query, source, _j(topics), _j(items), error, now),
            )
            self._c.commit()
        return {
            "gap_id": gap_id,
            "query": query,
            "source": source,
            "topics": topics,
            "items": items,
            "error": error,
            "fetched_at": now,
        }

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._c.execute("DELETE FROM scholar_gap_refs WHERE session_id=?", (session_id,))
            self._c.commit()

    # ---- lecture topics ----
    def get_lecture_topics(self, lecture_id: str) -> dict | None:
        with self._lock:
            r = self._c.execute(
                "SELECT * FROM scholar_lecture_topics WHERE lecture_id=?", (lecture_id,)
            ).fetchone()
        if not r:
            return None
        return {"source": r["source"], "topics": _uj(r["topics_json"], []), "fetched_at": r["fetched_at"]}

    def put_lecture_topics(self, lecture_id: str, source: str, topics: list[dict]) -> dict:
        now = time.time()
        with self._lock:
            self._c.execute(
                "INSERT OR REPLACE INTO scholar_lecture_topics(lecture_id,source,topics_json,fetched_at) VALUES(?,?,?,?)",
                (lecture_id, source, _j(topics), now),
            )
            self._c.commit()
        return {"source": source, "topics": topics, "fetched_at": now}

    def clear_lecture_topics(self, lecture_id: str) -> None:
        with self._lock:
            self._c.execute("DELETE FROM scholar_lecture_topics WHERE lecture_id=?", (lecture_id,))
            self._c.commit()

    # ---- query cache ----
    @staticmethod
    def qhash(query: str, topic_ids: list[str]) -> str:
        key = query.strip().lower() + "|" + ",".join(sorted(topic_ids))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    def get_query(self, query: str, topic_ids: list[str]) -> list[dict] | None:
        with self._lock:
            r = self._c.execute(
                "SELECT works_json FROM scholar_query_cache WHERE qhash=?", (self.qhash(query, topic_ids),)
            ).fetchone()
        return _uj(r["works_json"], None) if r else None

    def put_query(self, query: str, topic_ids: list[str], works: list[dict]) -> None:
        with self._lock:
            self._c.execute(
                "INSERT OR REPLACE INTO scholar_query_cache(qhash,query,topic_ids,works_json,fetched_at) VALUES(?,?,?,?,?)",
                (self.qhash(query, topic_ids), query, ",".join(sorted(topic_ids)), _j(works), time.time()),
            )
            self._c.commit()
