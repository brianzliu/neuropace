"""No placeholder text in the product: OpenAI is required, outages degrade to the verbatim transcript or a retry."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from reflow.api.app import create_app, ensure_demo_lecture
from reflow.clock import ManualClock
from reflow.config import FORMS, Settings
from reflow.core.gaps import regenerate_packages
from reflow.core.session import SessionRuntime
from reflow.llm.client import LLMClient, LLMUnavailable
from reflow.store.db import DB
from reflow.transcribe.transcript import Word

GOOD_RECAP = json.dumps({"plain": "p", "keyterm": "k: d", "analogy": "a", "sketch": "s"})


class FakeResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        out = self.outputs.pop(0) if self.outputs else RuntimeError("boom")
        if isinstance(out, Exception):
            raise out
        return type("R", (), {"output_text": out})()


class FakeClient:
    def __init__(self, outputs):
        self.responses = FakeResponses(outputs)


def test_client_raises_without_a_key_when_offline_is_not_allowed(tmp_path):
    s = Settings(data_dir=tmp_path)  # default: offline not allowed
    c = LLMClient(s, DB(s.db_path))
    with pytest.raises(LLMUnavailable, match="no OPENAI_API_KEY"):
        asyncio.run(c.recap("words", "corpus"))
    with pytest.raises(LLMUnavailable):
        asyncio.run(c.gap_package("span", "ctx", "corpus"))
    assert c.stats["unavailable"] == 2 and c.stats["fallbacks"] == 0


def test_gap_package_retries_then_raises_with_the_last_error(tmp_path, monkeypatch):
    s = Settings(data_dir=tmp_path, package_timeout_seconds=5)
    fake = FakeClient(
        [RuntimeError("rate limited"), RuntimeError("rate limited"), RuntimeError("rate limited")]
    )
    c = LLMClient(s, DB(s.db_path), client=fake)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    with pytest.raises(LLMUnavailable, match="rate limited"):
        asyncio.run(c.gap_package("span text here", "ctx", "corpus"))
    assert fake.responses.calls == 3


def test_session_creation_is_refused_without_a_key(tmp_path):
    s = Settings(data_dir=tmp_path, headset_port="sim", totem_port="keyboard")
    s.ensure_dirs()
    db = DB(s.db_path)
    ensure_demo_lecture(db)
    app = create_app(s, db, LLMClient(s, db))
    with TestClient(app) as c:
        assert c.get("/api/doctor").json()["openai"]["required"] is True
        lr = c.post("/api/learners", json={"name": "x"}).json()
        r = c.post(
            "/api/sessions", json={"learner_id": lr["id"], "lecture_id": "lec_demo0001", "mode": "live"}
        )
        assert r.status_code == 400 and "OPENAI_API_KEY" in r.json()["detail"]


@pytest.mark.asyncio
async def test_outage_gives_verbatim_transcript_and_failed_packages_then_regenerate_recovers(
    tmp_path, monkeypatch
):
    s = Settings(
        data_dir=tmp_path,
        baseline_seconds=10,
        recap_period_seconds=5,
        headset_port="sim",
        totem_port="keyboard",
    )
    s.ensure_dirs()
    db = DB(s.db_path)
    ensure_demo_lecture(db)
    fake = FakeClient([RuntimeError("down")] * 20)
    llm = LLMClient(s, db, client=fake)
    lec = db.get_lecture("lec_demo0001", full=True)
    lrn = db.create_learner("Ana")
    sess = db.create_session(learner_id=lrn["id"], lecture_id=lec["id"], mode="live", seed=1)
    rt = SessionRuntime(
        s, db, llm, sess, lrn, lec, "scripted", headset_port="sim", totem_port="keyboard", drive_manually=True
    )
    rt.clock = ManualClock(0.0)
    await rt.start()
    q = rt.subscribe()
    words = [Word(**w) for w in lec["words"]]
    wi = 0
    for sec in range(1, 41):
        rt.clock.set(float(sec))
        batch = []
        while wi < len(words) and words[wi].end <= sec:
            batch.append(words[wi])
            wi += 1
        if batch:
            rt._on_words(batch, True)
        rt.feed_sim_second()
        rt.step(float(sec))
        await asyncio.sleep(0)
        if sec == 30:
            rt.tap()
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    cu = [m for m in msgs if m["type"] == "catchup"]
    assert cu and cu[0]["source"] == "transcript" and "offline" not in cu[0]["line"]
    assert all(cu[0]["forms"][f] == cu[0]["line"] for f in FORMS)
    assert any(m["type"] == "notice" and "Recaps unavailable" in m["text"] for m in msgs)
    assert len(rt.ring) == 0

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    gaps = await rt.end()
    assert gaps and gaps[0]["package_source"] == "failed" and "down" in gaps[0]["package"]["error"]
    # the API comes back: regenerate fills the failed gap
    good_pkg = json.dumps(
        {
            "note": {"what_was_said": "w", "key_term": "k", "definition": "d", "connection": "c"},
            "question": {
                "question": "q?",
                "options": ["a", "b", "c", "d"],
                "correct_index": 1,
                "explanation": "e",
            },
            "forms": {
                "plain": "p",
                "keyterm": {"term": "k", "definition": "d", "example": "e"},
                "analogy": "a",
                "sketch": {
                    "line": "l",
                    "diagram": {
                        "title": "t",
                        "nodes": [{"id": "n1", "label": "x"}, {"id": "n2", "label": "y"}],
                        "edges": [{"from_id": "n1", "to_id": "n2", "label": "to"}],
                        "steps": [{"highlight": ["n1"], "caption": "c"}],
                    },
                },
            },
        }
    )
    fake.responses.outputs = [good_pkg]
    gaps2 = await regenerate_packages(db, llm, rt.id)
    assert gaps2[0]["package_source"] == "llm" and gaps2[0]["package"]["question"]["options"] == [
        "a",
        "b",
        "c",
        "d",
    ]
    assert db.get_gaps(rt.id)[0]["package_source"] == "llm"
