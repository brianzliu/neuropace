from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from neuropace.core.review_recommendation import ReviewRecommendationIn, recommend_review


def seed(db):
    learner = db.default_learner()
    sess = db.create_session(learner_id=learner["id"], lecture_id="lec_demo0001", mode="live")
    db.update_session(sess["id"], status="ended")
    db.replace_gaps(
        sess["id"],
        [
            {
                "id": "gap_rec",
                "ord": 0,
                "t_start": 2,
                "t_end": 5,
                "span_text": "Synthetic",
                "status": "open",
                "package": {"note": {}},
                "package_source": "offline",
            }
        ],
    )
    return learner, sess


@pytest.mark.asyncio
async def test_eeg_advice_is_bounded_simulated_and_does_not_mutate(db):
    learner, sess = seed(db)
    llm = SimpleNamespace(_structured=AsyncMock(return_value=(None, "offline")))
    rt = SimpleNamespace(
        status="running",
        headset=SimpleNamespace(kind="simulated", connected=True),
        clock=SimpleNamespace(now=lambda: 20),
        _focus_recent=[{"t": t, "quality": "good", "state": "drop"} for t in range(12, 20)],
    )
    body = ReviewRecommendationIn(learner_id=learner["id"])
    result = await recommend_review(db, llm, sess, body, rt)
    assert result["mode"] == "whiteboard" and result["eeg"]["simulated"]
    assert result["eeg"]["available"] and result["advisory"]
    assert db.get_gaps(sess["id"])[0]["status"] == "open"
    rt.clock.now = lambda: 100
    stale = await recommend_review(db, llm, sess, body, rt)
    assert not stale["eeg"]["available"] and stale["mode"] == "practice"
    rt.clock.now = lambda: 20
    rt.headset.connected = False
    assert not (await recommend_review(db, llm, sess, body, rt))["eeg"]["available"]


def test_linked_conversation_and_sensor_sessions_are_learner_scoped(app, db):
    learner, sess = seed(db)
    other = db.create_learner("Other synthetic learner")
    foreign = db.create_session(learner_id=other["id"], lecture_id="lec_demo0001", mode="office_hours")
    route = f"/api/sessions/{sess['id']}/review/recommendation"
    with TestClient(app) as c:
        for field in ("conversation_session_id", "focus_session_id"):
            assert c.post(route, json={"learner_id": learner["id"], field: foreign["id"]}).status_code == 404
        assert c.post(route, json={"learner_id": other["id"]}).status_code == 404
        assert (
            c.post(
                route, json={"learner_id": learner["id"], "conversation_session_id": sess["id"]}
            ).status_code
            == 400
        )
        r = c.post(route, json={"learner_id": learner["id"]})
        assert r.status_code == 200 and r.json()["mode"] == "practice"
