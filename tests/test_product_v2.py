"""Product v2 (docs/PRODUCT.md): families, artifact choice, restudy session with brain waves and focus, profile, migrations."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from reflow.clock import ManualClock
from reflow.config import FORMS
from reflow.core.session import SessionRuntime
from reflow.llm.schemas import ARTIFACT_KINDS, pick_artifact
from reflow.store.db import DB


def test_families_and_artifact_choice_by_content():
    assert FORMS == ("words", "analogy", "visual", "doing")
    arts = {
        "summary": "s",
        "key_idea": {"term": "k", "definition": "d", "example": "e"},
        "analogy": "a",
        "diagram": {"title": "t", "nodes": [], "edges": [], "steps": []},
        "chart": {"applicable": False},
        "steps": {"applicable": False},
        "example": {"title": "ex", "lines": ["l"], "result": "r"},
    }
    assert pick_artifact(arts, "visual")[0] == "diagram" and pick_artifact(arts, "doing")[0] == "example"
    arts["chart"] = {"applicable": True, "kind": "bar", "points": [{"label": "a", "value": 1}]}
    arts["steps"] = {"applicable": True, "steps": ["one", "two"]}
    assert pick_artifact(arts, "visual")[0] == "chart" and pick_artifact(arts, "doing")[0] == "steps"
    kind, content = pick_artifact(arts, "words")
    assert kind == "words" and content["summary"] == "s" and content["key_idea"]["term"] == "k"


def test_migration_merges_old_form_keys(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE learners(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL, baseline_mu REAL, baseline_sigma REAL, baseline_at REAL);
        CREATE TABLE tally(learner_id TEXT NOT NULL, form TEXT NOT NULL, rescues INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(learner_id, form));
        CREATE TABLE cards(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, gap_id TEXT NOT NULL, ord INTEGER NOT NULL, kind TEXT NOT NULL, form TEXT, shown_at REAL, outcome TEXT, choice INTEGER, option_order_json TEXT);
        INSERT INTO learners VALUES('lrn_me','you',0,NULL,NULL,NULL);
        INSERT INTO tally VALUES('lrn_me','plain',2,3),('lrn_me','keyterm',1,2),('lrn_me','analogy',0,1),('lrn_me','sketch',4,4);
        INSERT INTO cards VALUES('card_1','s','g',0,'reteach','sketch',0,'read',NULL,NULL);
        """
    )
    conn.commit()
    conn.close()
    db = DB(path)
    t = db.get_tally("lrn_me")
    assert (
        t["words"] == {"rescues": 3, "attempts": 5}
        and t["visual"] == {"rescues": 4, "attempts": 4}
        and t["analogy"] == {"rescues": 0, "attempts": 1}
    )
    assert db.get_card("card_1")["form"] == "visual" and "focus_ratio" in db.get_card("card_1")


@pytest.mark.asyncio
async def test_review_session_streams_waves_and_flags_without_transcript(settings, db, llm):
    lrn = db.default_learner()
    sess = db.create_session(learner_id=lrn["id"], lecture_id=None, mode="review", seed=3)
    rt = SessionRuntime(
        settings,
        db,
        llm,
        sess,
        lrn,
        None,
        "none",
        headset_port="sim",
        totem_port="keyboard",
        drive_manually=True,
    )
    rt.clock = ManualClock(0.0)
    await rt.start()
    q = rt.subscribe()
    for sec in range(1, 46):
        rt.clock.set(float(sec))
        if sec == 30:
            rt.set_sim_headset("drifting")
        rt.feed_sim_second()
        rt.step(float(sec))
        await asyncio.sleep(0)
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    raw = [m for m in msgs if m["type"] == "raw"]
    assert raw and raw[0]["fs"] == 64 and len(raw[0]["uv"]) == 8, "brain-wave chunks stream in review mode"
    focus = [m for m in msgs if m["type"] == "focus"]
    assert any(m.get("bands") and abs(sum(m["bands"].values()) - 1.0) < 0.01 for m in focus), (
        "relative band powers ride on focus samples"
    )
    assert not [m for m in msgs if m["type"] in ("recap", "catchup", "chip")], (
        "no recaps or catch-ups in restudy"
    )
    assert [m for m in msgs if m["type"] == "flag_open"], (
        "the drift is still flagged so restudy can switch the explanation"
    )
    assert await rt.end() == [] and db.get_session(rt.id)["status"] == "ended"


def test_review_records_focus_and_profile_reset(app):
    with TestClient(app) as c:
        r = c.post(
            "/api/sessions",
            json={
                "lecture_id": "lec_demo0001",
                "mode": "live",
                "baseline_seconds": 5,
                "headset": "sim",
                "totem": "keyboard",
            },
        )
        sid = r.json()["id"]
        import time

        time.sleep(2.5)
        c.post(f"/api/sessions/{sid}/tap")
        c.post(f"/api/sessions/{sid}/end")
        st = c.post(f"/api/sessions/{sid}/review/start").json()
        card = st["card"]
        assert card["kind"] == "reteach", "teach first, then check (docs/PRODUCT.md §5)"
        assert (
            card["reteach"]["artifact"] in ARTIFACT_KINDS
            and card["reteach"]["why"]
            and "said" in card["reteach"]
        )
        adv = c.post(
            f"/api/sessions/{sid}/review/advance", json={"card_id": card["id"], "focus_ratio": 0.6}
        ).json()
        assert adv["next"]["kind"] == "question"
        fam = card["form"]
        assert adv["tally"]["forms"][fam]["focus"]["mean_focus"] == 0.6
        assert adv["tally"]["forms"][fam]["score"] is not None and "preferred" in adv["tally"]
        ans = c.post(
            f"/api/sessions/{sid}/review/answer",
            json={"card_id": adv["next"]["id"], "choice": 0, "focus_ratio": 0.9},
        ).json()
        assert ans["outcome"] in ("hit", "miss") and ans["credited_form"] == fam
        prof = c.get("/api/me/profile").json()
        assert (
            prof["learner"]["id"] == "lrn_me"
            and prof["stats"]["lectures"] >= 1
            and set(prof["tally"]["forms"]) == set(FORMS)
        )
        assert all("label" in v for v in prof["tally"]["forms"].values())
        rs = c.post("/api/me/reset").json()
        assert rs["ok"] and c.get("/api/me/profile").json()["tally"]["total_attempts"] == 0
        # review session over the API: headset only, no lecture
        r2 = c.post("/api/sessions", json={"mode": "review", "headset": "sim", "totem": "keyboard"})
        assert r2.status_code == 200 and r2.json()["transcript_kind"] == "none"
        c.post(f"/api/sessions/{r2.json()['id']}/end")


def test_orphaned_running_sessions_are_closed_at_startup(settings, db, llm):
    from reflow.core.gaps import recover_orphaned_sessions

    me = db.default_learner()
    sess = db.create_session(learner_id=me["id"], lecture_id="lec_demo0001", mode="live", seed=1)
    lec = db.get_lecture("lec_demo0001", full=True)
    db.add_words(sess["id"], lec["words"][:120], 0)
    db.upsert_flag(
        {
            "id": "flag_o1",
            "session_id": sess["id"],
            "source": "key",
            "t_trigger": 20.0,
            "t_start": 12.0,
            "t_end": 20.0,
            "catchup_shown": True,
            "catchup_form": "words",
        }
    )
    assert db.get_session(sess["id"])["status"] == "running"
    recovered = recover_orphaned_sessions(db, settings)
    assert recovered == [sess["id"]]
    s2 = db.get_session(sess["id"])
    gaps = db.get_gaps(sess["id"])
    assert (
        s2["status"] == "ended"
        and len(gaps) == 1
        and gaps[0]["package"] is None
        and gaps[0]["package_source"] == "failed"
    )
    assert gaps[0]["span_text"] and 12.0 <= gaps[0]["t_start"] <= 20.0
    assert recover_orphaned_sessions(db, settings) == []
