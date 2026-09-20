from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from neuropace.core.next_step import StepChoice


def seed(db):
    learner = db.default_learner()
    session = db.create_session(learner_id=learner["id"], lecture_id="lec_demo0001", mode="live")
    db.update_session(session["id"], status="ended")
    lec = db.get_lecture("lec_demo0001", full=True)
    db.add_words(session["id"], lec["words"], 0)
    return learner, session


def test_guidance_bounds_ownership_time_and_available_actions(app, db, llm):
    learner, session = seed(db)
    route = f"/api/sessions/{session['id']}/next-step"
    llm._structured = AsyncMock(return_value=(StepChoice(action="review", reason="Practice."), "llm"))
    with TestClient(app) as c:
        assert c.post(route, json={"learner_id": "someone-else"}).status_code == 404
        assert c.post(route, json={"learner_id": learner["id"], "elapsed_seconds": -1}).status_code == 422
        result = c.post(route, json={"learner_id": learner["id"], "goal": "recall"}).json()
        assert result["action"] == "quiz" and result["source"] == "rules"
        assert "review" not in result["allowed_actions"]
        llm._structured.reset_mock()
        stopped = c.post(
            route, json={"learner_id": learner["id"], "elapsed_seconds": 60, "time_limit_seconds": 60}
        ).json()
        assert stopped["action"] == "complete" and stopped["done"]
        llm._structured.assert_not_called()
        assert db.get_session(session["id"])["status"] == "ended"


def test_guidance_accepts_valid_model_choice_and_allows_later_retries(app, db, llm):
    learner, session = seed(db)
    route = f"/api/sessions/{session['id']}/next-step"
    llm._structured = AsyncMock(
        return_value=(StepChoice(action="replay", reason="Revisit the context."), "llm")
    )
    with TestClient(app) as c:
        result = c.post(route, json={"learner_id": learner["id"]}).json()
        assert result["action"] == "replay" and result["source"] == "llm"
        llm._structured = AsyncMock(return_value=(StepChoice(action="quiz", reason="Try it again."), "llm"))
        retried = c.post(
            route,
            json={
                "learner_id": learner["id"],
                "current_step": "replay",
                "last_outcome": "read",
                "completed_steps": ["quiz", "replay", "quiz", "replay"],
            },
        ).json()
        assert retried["action"] == "quiz"
        assert "quiz" in retried["allowed_actions"]
        db.update_session(session["id"], status="running")
        assert c.post(route, json={"learner_id": learner["id"]}).status_code == 409


def test_guidance_only_finishes_when_goal_or_time_is_met(app, db, llm):
    learner, session = seed(db)
    route = f"/api/sessions/{session['id']}/next-step"
    llm._structured = AsyncMock(
        return_value=(StepChoice(action="complete", reason="Stop."), "llm")
    )
    with TestClient(app) as c:
        continuing = c.post(
            route,
            json={
                "learner_id": learner["id"],
                "goal": "recall",
                "current_step": "quiz",
                "last_outcome": "miss",
            },
        ).json()
        assert continuing["action"] != "complete"
        assert "complete" not in continuing["allowed_actions"]

        finished = c.post(
            route,
            json={
                "learner_id": learner["id"],
                "goal": "recall",
                "current_step": "quiz",
                "last_outcome": "hit",
            },
        ).json()
        assert finished["action"] == "complete"
        assert finished["done"]


def test_guidance_failed_packages_go_to_notes_and_never_change_gap_status(app, db, llm):
    learner, session = seed(db)
    db.replace_gaps(
        session["id"],
        [
            {
                "id": "gap_guide",
                "ord": 0,
                "t_start": 12,
                "t_end": 25,
                "span_text": "Synthetic lesson context",
                "status": "open",
                "package": {"error": "unavailable"},
                "package_source": "failed",
            }
        ],
    )
    llm._structured = AsyncMock(return_value=(None, "offline"))
    with TestClient(app) as c:
        result = c.post(
            f"/api/sessions/{session['id']}/next-step",
            json={"learner_id": learner["id"], "goal": "practice", "last_outcome": "miss"},
        ).json()
        assert result["action"] == "replay" and result["source"] == "rules"
        assert result["target_gap_id"] == "gap_guide"
        assert "review" not in result["allowed_actions"]
        assert db.get_gaps(session["id"])[0]["status"] == "open"
