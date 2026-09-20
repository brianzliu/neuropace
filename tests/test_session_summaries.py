"""Per-session one-liner summaries: rules fallbacks, the LLM pass, and shape safety."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from neuropace.core.dashboard import (
    SessionOneLiner,
    SessionOneLinerList,
    dashboard_data,
    organize_dashboard,
)


def make_session(db, learner_id):
    return db.create_session(
        learner_id=learner_id, lecture_id="lec_demo0001", mode="live", catchup_policy="always"
    )


def gap(gid, status="open", term="Clock offsets"):
    return {
        "id": gid,
        "ord": 0,
        "t_start": 3,
        "t_end": 10,
        "span_text": "GPS timing",
        "status": status,
        "package": {"note": {"key_term": term, "definition": "Compare satellite clocks."}},
    }


def summaries(data):
    return {s["id"]: (s["summary"], s["summary_source"]) for s in data["sessions"]}


def test_fallbacks_cover_empty_partially_and_fully_cleared(db):
    learner = db.create_learner("Synthetic summaries")
    empty = make_session(db, learner["id"])
    partial = make_session(db, learner["id"])
    db.replace_gaps(partial["id"], [gap("a"), gap("b", "closed")])
    cleared = make_session(db, learner["id"])
    db.replace_gaps(cleared["id"], [gap("c", "closed")])
    data = dashboard_data(db, learner["id"])
    got = summaries(data)
    assert got[empty["id"]] == ("No saved moments yet.", "rules")
    assert got[partial["id"]] == ("2 saved moments · 1 cleared", "rules")
    assert got[cleared["id"]] == ("All 1 moment cleared in review.", "rules")


@pytest.mark.asyncio
async def test_offline_organize_keeps_fallbacks_and_drops_inputs(db, llm):
    learner = db.create_learner("Synthetic summaries")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a")])
    data = await organize_dashboard(llm, dashboard_data(db, learner["id"]))
    assert "_session_inputs" not in data
    assert summaries(data)[session["id"]] == ("1 saved moment", "rules")


@pytest.mark.asyncio
async def test_llm_oneliners_apply_and_ignore_foreign_or_blank(db):
    learner = db.create_learner("Synthetic summaries")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a")])
    other = make_session(db, learner["id"])
    db.replace_gaps(other["id"], [gap("b")])
    mock = SimpleNamespace(
        _structured=AsyncMock(
            side_effect=[
                (None, "offline"),
                (
                    SessionOneLinerList(
                        summaries=[
                            SessionOneLiner(session_id=session["id"], summary="  Timing drifts explained.  "),
                            SessionOneLiner(session_id="sess_foreign", summary="Invented session."),
                            SessionOneLiner(session_id=other["id"], summary="   "),
                        ]
                    ),
                    "llm",
                ),
            ]
        )
    )
    data = await organize_dashboard(mock, dashboard_data(db, learner["id"]))
    got = summaries(data)
    assert got[session["id"]] == ("Timing drifts explained.", "llm")
    assert "sess_foreign" not in got
    assert got[other["id"]] == ("1 saved moment", "rules")


@pytest.mark.asyncio
async def test_llm_session_id_prefix_stripped(db):
    """Models echo the supplied session_id into the prose; it must never reach the UI."""
    learner = db.create_learner("Synthetic id strip")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a")])
    mock = SimpleNamespace(
        _structured=AsyncMock(
            side_effect=[
                (None, "offline"),
                (
                    SessionOneLinerList(
                        summaries=[
                            SessionOneLiner(session_id=session["id"], summary="sess_deadbeef: Timing drifts explained."),
                        ]
                    ),
                    "llm",
                ),
            ]
        )
    )
    data = await organize_dashboard(mock, dashboard_data(db, learner["id"]))
    assert summaries(data)[session["id"]] == ("Timing drifts explained.", "llm")


@pytest.mark.asyncio
async def test_unexpected_llm_shape_leaves_fallbacks_alone(db):
    """Shared mocks may answer every _structured call with another task's
    model; the summarizer must ignore it instead of crashing."""
    from neuropace.core.dashboard import DashboardSummary

    learner = db.create_learner("Synthetic summaries")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a")])
    mock = SimpleNamespace(
        _structured=AsyncMock(return_value=(DashboardSummary(summary="x", priorities=[]), "llm"))
    )
    data = await organize_dashboard(mock, dashboard_data(db, learner["id"]))
    assert summaries(data)[session["id"]] == ("1 saved moment", "rules")


def test_plain_dashboard_hides_inputs_but_shows_fallbacks(app, db):
    learner = db.create_learner("Synthetic summaries")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a")])
    with TestClient(app) as client:
        body = client.get(f"/api/learners/{learner['id']}/dashboard").json()
        assert "_session_inputs" not in body
        assert body["sessions"][0]["summary"] == "1 saved moment"
