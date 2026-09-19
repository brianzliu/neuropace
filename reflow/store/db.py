"""SQLite persistence (TDD §8.1). One connection, one lock, JSON in TEXT columns."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ..config import FORMS
from ..ids import new_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS curricula(
  learner_id TEXT PRIMARY KEY, content_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS learners(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL,
  baseline_mu REAL, baseline_sigma REAL, baseline_at REAL);
CREATE TABLE IF NOT EXISTS lectures(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, media_path TEXT,
  transcript_json TEXT, segments_json TEXT, quiz_json TEXT, keyterms_json TEXT, duration REAL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, lecture_id TEXT, mode TEXT NOT NULL, catchup_policy TEXT NOT NULL,
  headset_kind TEXT, totem_kind TEXT, transcript_kind TEXT, best_form TEXT, status TEXT NOT NULL,
  started_at REAL NOT NULL, ended_at REAL, baseline_json TEXT, seed INTEGER, auto_pause INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS focus_samples(
  session_id TEXT NOT NULL, t REAL NOT NULL, e REAL, x REAL, z REAL, w15 REAL, quality TEXT, state TEXT,
  artifact INTEGER, blink INTEGER, paused INTEGER);
CREATE INDEX IF NOT EXISTS ix_focus ON focus_samples(session_id, t);
CREATE TABLE IF NOT EXISTS words(session_id TEXT NOT NULL, idx INTEGER NOT NULL, w TEXT NOT NULL, start REAL, "end" REAL);
CREATE INDEX IF NOT EXISTS ix_words ON words(session_id, start);
CREATE TABLE IF NOT EXISTS flags(
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, source TEXT NOT NULL, t_trigger REAL NOT NULL, t_start REAL NOT NULL,
  t_end REAL, catchup_shown INTEGER, catchup_form TEXT, opened INTEGER DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recaps(session_id TEXT NOT NULL, t_from REAL, t_to REAL, forms_json TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS gaps(
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, ord INTEGER NOT NULL, t_start REAL, t_end REAL, span_text TEXT,
  context_text TEXT, flag_ids_json TEXT, package_json TEXT, package_source TEXT, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards(
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, gap_id TEXT NOT NULL, ord INTEGER NOT NULL, kind TEXT NOT NULL,
  form TEXT, shown_at REAL, outcome TEXT, choice INTEGER, option_order_json TEXT);
CREATE TABLE IF NOT EXISTS tally(
  learner_id TEXT NOT NULL, form TEXT NOT NULL, rescues INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(learner_id, form));
CREATE TABLE IF NOT EXISTS quiz_answers(
  session_id TEXT NOT NULL, item_id TEXT NOT NULL, phase TEXT NOT NULL, choice INTEGER, correct INTEGER,
  PRIMARY KEY(session_id, item_id, phase));
CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY, task TEXT, model TEXT, output_json TEXT, created_at REAL);
"""


def _j(v: Any) -> str | None:
    return None if v is None else json.dumps(v, ensure_ascii=False)


def _uj(v: str | None, default: Any = None) -> Any:
    return default if v is None else json.loads(v)


class DB:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def _q(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self._q(sql, params)
        return rows[0] if rows else None

    def _x(self, sql: str, params: tuple = ()) -> None:
        with self.lock:
            self.conn.execute(sql, params)

    def _xm(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        with self.lock:
            self.conn.executemany(sql, rows)

    def get_curriculum(self, learner_id: str) -> dict:
        row = self._one("SELECT content_json FROM curricula WHERE learner_id=?", (learner_id,))
        return _uj(row["content_json"]) if row else {"title": "My curriculum", "topics": []}

    def set_curriculum(self, learner_id: str, content: dict) -> None:
        self._x(
            "INSERT INTO curricula(learner_id,content_json) VALUES(?,?) "
            "ON CONFLICT(learner_id) DO UPDATE SET content_json=excluded.content_json",
            (learner_id, _j(content)),
        )

    # ---- learners ----
    def create_learner(self, name: str) -> dict:
        lid = new_id("lrn")
        self._x(
            "INSERT INTO learners(id, name, created_at) VALUES(?,?,?)",
            (lid, name.strip() or "learner", time.time()),
        )
        return self.get_learner(lid)  # type: ignore[return-value]

    def get_learner(self, lid: str) -> dict | None:
        r = self._one("SELECT * FROM learners WHERE id=?", (lid,))
        return dict(r) if r else None

    def list_learners(self) -> list[dict]:
        return [dict(r) for r in self._q("SELECT * FROM learners ORDER BY created_at")]

    def set_learner_baseline(self, lid: str, mu: float, sigma: float) -> None:
        self._x(
            "UPDATE learners SET baseline_mu=?, baseline_sigma=?, baseline_at=? WHERE id=?",
            (mu, sigma, time.time(), lid),
        )

    # ---- lectures ----
    def create_lecture(
        self,
        title: str,
        kind: str,
        words: list[dict] | None,
        segments: list[dict] | None,
        quiz: list[dict] | None,
        keyterms: list[str] | None,
        media_path: str | None = None,
        duration: float | None = None,
        lecture_id: str | None = None,
    ) -> dict:
        lid = lecture_id or new_id("lec")
        if duration is None and words:
            duration = max(w["end"] for w in words)
        self._x(
            "INSERT OR REPLACE INTO lectures(id,title,kind,media_path,transcript_json,segments_json,quiz_json,keyterms_json,duration,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                lid,
                title,
                kind,
                media_path,
                _j(words),
                _j(segments),
                _j(quiz),
                _j(keyterms),
                duration,
                time.time(),
            ),
        )
        return self.get_lecture(lid, full=True)  # type: ignore[return-value]

    def get_lecture(self, lid: str, full: bool = False) -> dict | None:
        r = self._one("SELECT * FROM lectures WHERE id=?", (lid,))
        if not r:
            return None
        d = dict(r)
        out = {
            "id": d["id"],
            "title": d["title"],
            "kind": d["kind"],
            "media_path": d["media_path"],
            "duration": d["duration"],
            "segments": _uj(d["segments_json"], []),
            "quiz": _uj(d["quiz_json"], []),
            "keyterms": _uj(d["keyterms_json"], []),
            "created_at": d["created_at"],
            "word_count": len(_uj(d["transcript_json"], [])),
        }
        if full:
            out["words"] = _uj(d["transcript_json"], [])
        return out

    def list_lectures(self) -> list[dict]:
        return [self.get_lecture(r["id"]) for r in self._q("SELECT id FROM lectures ORDER BY created_at")]  # type: ignore[misc]

    # ---- sessions ----
    def create_session(self, **kw: Any) -> dict:
        sid = kw.get("id") or new_id("sess")
        self._x(
            "INSERT INTO sessions(id,learner_id,lecture_id,mode,catchup_policy,headset_kind,totem_kind,transcript_kind,best_form,"
            "status,started_at,baseline_json,seed,auto_pause) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sid,
                kw["learner_id"],
                kw.get("lecture_id"),
                kw["mode"],
                kw.get("catchup_policy", "always"),
                kw.get("headset_kind"),
                kw.get("totem_kind"),
                kw.get("transcript_kind"),
                kw.get("best_form"),
                "running",
                time.time(),
                _j(kw.get("baseline")),
                kw.get("seed"),
                1 if kw.get("auto_pause", True) else 0,
            ),
        )
        return self.get_session(sid)  # type: ignore[return-value]

    def get_session(self, sid: str) -> dict | None:
        r = self._one("SELECT * FROM sessions WHERE id=?", (sid,))
        if not r:
            return None
        d = dict(r)
        d["baseline"] = _uj(d.pop("baseline_json"))
        d["auto_pause"] = bool(d.get("auto_pause", 1))
        return d

    def list_sessions(self, lecture_id: str | None = None, learner_id: str | None = None) -> list[dict]:
        sql, params = "SELECT id FROM sessions", []
        conds = []
        if lecture_id:
            conds.append("lecture_id=?")
            params.append(lecture_id)
        if learner_id:
            conds.append("learner_id=?")
            params.append(learner_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY started_at DESC"
        return [self.get_session(r["id"]) for r in self._q(sql, tuple(params))]  # type: ignore[misc]

    def update_session(self, sid: str, **fields: Any) -> None:
        if "baseline" in fields:
            fields["baseline_json"] = _j(fields.pop("baseline"))
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self._x(f"UPDATE sessions SET {sets} WHERE id=?", (*fields.values(), sid))

    # ---- focus samples and words ----
    def add_focus_samples(self, sid: str, samples: list[dict]) -> None:
        self._xm(
            "INSERT INTO focus_samples(session_id,t,e,x,z,w15,quality,state,artifact,blink,paused) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    sid,
                    s["t"],
                    s.get("e"),
                    s.get("x"),
                    s.get("z"),
                    s.get("w15"),
                    s.get("quality"),
                    s.get("state"),
                    int(bool(s.get("artifact"))),
                    int(bool(s.get("blink"))),
                    int(bool(s.get("paused"))),
                )
                for s in samples
            ],
        )

    def get_focus_samples(self, sid: str) -> list[dict]:
        return [dict(r) for r in self._q("SELECT * FROM focus_samples WHERE session_id=? ORDER BY t", (sid,))]

    def add_words(self, sid: str, words: list[dict], start_idx: int) -> None:
        self._xm(
            'INSERT INTO words(session_id, idx, w, start, "end") VALUES(?,?,?,?,?)',
            [(sid, start_idx + i, w["w"], w["start"], w["end"]) for i, w in enumerate(words)],
        )

    def get_words(self, sid: str) -> list[dict]:
        return [
            {"w": r["w"], "start": r["start"], "end": r["end"]}
            for r in self._q('SELECT w, start, "end" FROM words WHERE session_id=? ORDER BY idx', (sid,))
        ]

    # ---- flags and recaps ----
    def upsert_flag(self, f: dict) -> None:
        self._x(
            "INSERT OR REPLACE INTO flags(id,session_id,source,t_trigger,t_start,t_end,catchup_shown,catchup_form,opened,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                f["id"],
                f["session_id"],
                f["source"],
                f["t_trigger"],
                f["t_start"],
                f.get("t_end"),
                None if f.get("catchup_shown") is None else int(bool(f["catchup_shown"])),
                f.get("catchup_form"),
                int(bool(f.get("opened"))),
                f.get("created_at", time.time()),
            ),
        )

    def get_flags(self, sid: str) -> list[dict]:
        out = []
        for r in self._q("SELECT * FROM flags WHERE session_id=? ORDER BY t_trigger", (sid,)):
            d = dict(r)
            d["catchup_shown"] = None if d["catchup_shown"] is None else bool(d["catchup_shown"])
            d["opened"] = bool(d["opened"])
            out.append(d)
        return out

    def add_recap(self, sid: str, t_from: float, t_to: float, forms: dict, source: str) -> None:
        self._x(
            "INSERT INTO recaps(session_id,t_from,t_to,forms_json,source) VALUES(?,?,?,?,?)",
            (sid, t_from, t_to, _j(forms), source),
        )

    def get_recaps(self, sid: str) -> list[dict]:
        return [
            {
                "t_from": r["t_from"],
                "t_to": r["t_to"],
                "forms": _uj(r["forms_json"], {}),
                "source": r["source"],
            }
            for r in self._q("SELECT * FROM recaps WHERE session_id=? ORDER BY t_to", (sid,))
        ]

    # ---- gaps and cards ----
    def replace_gaps(self, sid: str, gaps: list[dict]) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM gaps WHERE session_id=?", (sid,))
            self.conn.execute("DELETE FROM cards WHERE session_id=?", (sid,))
            for g in gaps:
                self.conn.execute(
                    "INSERT INTO gaps(id,session_id,ord,t_start,t_end,span_text,context_text,flag_ids_json,package_json,package_source,status)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        g["id"],
                        sid,
                        g["ord"],
                        g["t_start"],
                        g["t_end"],
                        g["span_text"],
                        g.get("context_text", ""),
                        _j(g.get("flag_ids", [])),
                        _j(g.get("package")),
                        g.get("package_source"),
                        g.get("status", "open"),
                    ),
                )

    def get_gaps(self, sid: str) -> list[dict]:
        out = []
        for r in self._q("SELECT * FROM gaps WHERE session_id=? ORDER BY ord", (sid,)):
            d = dict(r)
            d["flag_ids"] = _uj(d.pop("flag_ids_json"), [])
            d["package"] = _uj(d.pop("package_json"))
            out.append(d)
        return out

    def set_gap_status(self, gid: str, status: str) -> None:
        self._x("UPDATE gaps SET status=? WHERE id=?", (status, gid))

    def add_card(self, c: dict) -> None:
        self._x(
            "INSERT INTO cards(id,session_id,gap_id,ord,kind,form,shown_at,outcome,choice,option_order_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                c["id"],
                c["session_id"],
                c["gap_id"],
                c["ord"],
                c["kind"],
                c.get("form"),
                c.get("shown_at", time.time()),
                c.get("outcome"),
                c.get("choice"),
                _j(c.get("option_order")),
            ),
        )

    def update_card(self, cid: str, **fields: Any) -> None:
        if "option_order" in fields:
            fields["option_order_json"] = _j(fields.pop("option_order"))
        sets = ", ".join(f"{k}=?" for k in fields)
        self._x(f"UPDATE cards SET {sets} WHERE id=?", (*fields.values(), cid))

    def get_cards(self, sid: str) -> list[dict]:
        out = []
        for r in self._q("SELECT * FROM cards WHERE session_id=? ORDER BY ord", (sid,)):
            d = dict(r)
            d["option_order"] = _uj(d.pop("option_order_json"))
            out.append(d)
        return out

    def get_card(self, cid: str) -> dict | None:
        r = self._one("SELECT * FROM cards WHERE id=?", (cid,))
        if not r:
            return None
        d = dict(r)
        d["option_order"] = _uj(d.pop("option_order_json"))
        return d

    # ---- tally ----
    def get_tally(self, learner_id: str) -> dict[str, dict]:
        rows = {
            r["form"]: {"rescues": r["rescues"], "attempts": r["attempts"]}
            for r in self._q("SELECT * FROM tally WHERE learner_id=?", (learner_id,))
        }
        return {f: rows.get(f, {"rescues": 0, "attempts": 0}) for f in FORMS}

    def population_tally(self) -> dict[str, dict]:
        rows = {
            r["form"]: {"rescues": r["r"], "attempts": r["a"]}
            for r in self._q("SELECT form, SUM(rescues) r, SUM(attempts) a FROM tally GROUP BY form")
        }
        return {f: rows.get(f, {"rescues": 0, "attempts": 0}) for f in FORMS}

    def tally_add(self, learner_id: str, form: str, rescue: bool) -> None:
        self._x(
            "INSERT INTO tally(learner_id, form, rescues, attempts) VALUES(?,?,?,1)"
            " ON CONFLICT(learner_id, form) DO UPDATE SET rescues=rescues+excluded.rescues, attempts=attempts+1",
            (learner_id, form, 1 if rescue else 0),
        )

    # ---- quiz ----
    def set_quiz_answers(self, sid: str, phase: str, answers: list[dict]) -> None:
        self._xm(
            "INSERT OR REPLACE INTO quiz_answers(session_id,item_id,phase,choice,correct) VALUES(?,?,?,?,?)",
            [(sid, a["item_id"], phase, a.get("choice"), int(bool(a.get("correct")))) for a in answers],
        )

    def get_quiz_answers(self, sid: str, phase: str | None = None) -> list[dict]:
        if phase:
            rows = self._q("SELECT * FROM quiz_answers WHERE session_id=? AND phase=?", (sid, phase))
        else:
            rows = self._q("SELECT * FROM quiz_answers WHERE session_id=?", (sid,))
        return [dict(r) for r in rows]

    # ---- llm cache ----
    def cache_get(self, key: str) -> dict | None:
        r = self._one("SELECT output_json FROM llm_cache WHERE key=?", (key,))
        return _uj(r["output_json"]) if r else None

    def cache_put(self, key: str, task: str, model: str, output: dict) -> None:
        self._x(
            "INSERT OR REPLACE INTO llm_cache(key,task,model,output_json,created_at) VALUES(?,?,?,?,?)",
            (key, task, model, _j(output), time.time()),
        )
