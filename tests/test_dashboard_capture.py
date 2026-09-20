import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from neuropace.clock import ManualClock
from neuropace.core.board import BoardCapture
from neuropace.core.dashboard import DashboardSummary, ReviewSuggestion, dashboard_data, organize_dashboard
from neuropace.totem.uno_q import UnoQRelay


def make_session(db, learner_id):
    return db.create_session(
        learner_id=learner_id, lecture_id="lec_demo0001", mode="live", catchup_policy="always"
    )


def gap(gid, status="open"):
    return {
        "id": gid,
        "ord": 0,
        "t_start": 3,
        "t_end": 10,
        "span_text": "GPS timing",
        "status": status,
        "package": {"note": {"key_term": "Clock offsets", "definition": "Compare satellite clocks."}},
    }


def test_dashboard_is_learner_scoped_and_completion_is_explicit(app, db):
    a, b = db.create_learner("Synthetic A"), db.create_learner("Synthetic B")
    sa, sb = make_session(db, a["id"]), make_session(db, b["id"])
    db.replace_gaps(sa["id"], [gap("gap_a"), gap("gap_closed", "closed")])
    db.replace_gaps(sb["id"], [gap("gap_b")])
    with TestClient(app) as client:
        body = {"title": "Synthetic syllabus", "topics": [{"title": "Timing", "completed": True}]}
        assert client.put(f"/api/learners/{a['id']}/curriculum", json=body).status_code == 200
        result = client.get(f"/api/learners/{a['id']}/dashboard?organize=true").json()
        assert [c["id"] for c in result["concepts"]] == ["gap_a"]
        assert result["closed"] == 1 and result["organization_source"] == "rules"
        assert result["curriculum"] == body
        assert client.get(f"/api/learners/{b['id']}/dashboard").json()["curriculum"]["topics"] == []
        assert client.get("/api/learners/nope/dashboard").status_code == 404
        parsed = client.post(
            f"/api/learners/{a['id']}/syllabus/parse",
            files={"file": ("syllabus.txt", b"Timing\nOrbits\nTiming", "text/plain")},
        ).json()
        assert parsed["source"] == "lines"
        assert [t["title"] for t in parsed["curriculum"]["topics"]] == ["Timing", "Orbits"]
        assert all(not t["completed"] for t in parsed["curriculum"]["topics"])
        # Parsing previews never overwrite the saved syllabus.
        assert client.get(f"/api/learners/{a['id']}/dashboard").json()["curriculum"] == body
        assert (
            client.post(
                f"/api/learners/{a['id']}/syllabus/parse", files={"file": ("bad.pdf", b"not pdf")}
            ).status_code
            == 400
        )
        assert (
            client.post(
                f"/api/learners/{a['id']}/syllabus/parse", files={"file": ("big.txt", b"x" * 2_000_001)}
            ).status_code
            == 413
        )


@pytest.mark.asyncio
async def test_organizer_rejects_foreign_and_duplicate_ids_and_preserves_remaining(db):
    learner = db.create_learner("Synthetic")
    session = make_session(db, learner["id"])
    db.replace_gaps(session["id"], [gap("a"), gap("b", "exhausted")])
    for ids in (["foreign"], ["a", "a"]):
        llm = SimpleNamespace(
            _structured=AsyncMock(
                return_value=(
                    DashboardSummary(
                        summary="Untrusted",
                        priorities=[ReviewSuggestion(gap_id=i, reason="Review") for i in ids],
                    ),
                    "llm",
                )
            )
        )
        data = await organize_dashboard(llm, dashboard_data(db, learner["id"]))
        assert data["organization_source"] == "rules"
    llm = SimpleNamespace(
        _structured=AsyncMock(
            return_value=(
                DashboardSummary(
                    summary="Review timing.", priorities=[ReviewSuggestion(gap_id="a", reason="Start here")]
                ),
                "llm",
            )
        )
    )
    data = await organize_dashboard(llm, dashboard_data(db, learner["id"]))
    assert [c["id"] for c in data["concepts"]] == ["a", "b"]
    assert data["concepts"][0]["session_id"] == session["id"]


@pytest.mark.asyncio
async def test_board_bounds_stale_frames_withholding_and_async_generation():
    messages = []
    rt = SimpleNamespace(
        clock=ManualClock(),
        status="running",
        broadcast=messages.append,
        transcript=SimpleNamespace(text_between=lambda a, b: "teacher transcript"),
        llm=SimpleNamespace(board_explanation=AsyncMock(return_value=("Explanation", "llm"))),
    )
    board = BoardCapture(rt)
    jpeg = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xfftest").decode()
    with pytest.raises(ValueError):
        board.add("not an image")
    for t in range(0, 110, 2):
        rt.clock._t = t
        board.add(jpeg)
    assert len(board.frames) == 45
    with pytest.raises(ValueError):
        board.add(jpeg)
    board.on_tap({"id": "withheld", "catchup_shown": False, "t_trigger": 108})
    assert board.task is None
    board.on_tap({"id": "request", "catchup_shown": True, "t_trigger": 105})
    await board.task
    frames = rt.llm.board_explanation.call_args.args[1]
    assert len(frames) <= 4 and all(45 <= f["t"] <= 105 for f in frames)
    assert messages[-1]["status"] == "ready" and all("image" not in f for f in messages[-1]["frames"])
    board.prune(300)
    assert not board.frames
    await board.stop()


def test_relay_fragmentation_deduplication_quality_and_disconnect():
    taps, frames = [], []
    hub = UnoQRelay("synthetic-device", taps.append, frames.append)

    def send(message):
        wire = (json.dumps(message) + "\n").encode()
        for i in range(0, len(wire), 7):
            hub.receive(None, wire[i : i + 7])

    send({"seq": 1, "type": "tap"})
    send({"seq": 1, "type": "tap"})
    assert len(taps) == 1
    hub.connected = True
    send(
        {
            "seq": 2,
            "type": "frame",
            "frame": {"connected": True, "engagement": 1.2, "quality": 0, "valid": True, "blink_count": 1},
        }
    )
    assert hub.headset.connected and len(frames) == 1
    send(
        {
            "seq": 3,
            "type": "frame",
            "frame": {
                "connected": True,
                "engagement": float("nan"),
                "quality": 0,
                "valid": True,
                "blink_count": 1,
            },
        }
    )
    assert len(frames) == 1
    hub.headset.last_frame -= 4
    assert not hub.headset.connected
    hub.receive(None, b"x" * 9000)
    assert not hub._buffer
    hub.connected = False
    assert not hub.headset.connected


def test_profile_and_reset_follow_selected_learner(app, db):
    first = db.default_learner()
    selected = db.create_learner("Synthetic selected learner")
    db.set_learner_baseline(first["id"], 1.0, 2.0)
    db.set_learner_baseline(selected["id"], 3.0, 4.0)
    make_session(db, selected["id"])
    with TestClient(app) as client:
        profile = client.get("/api/me/profile", params={"learner_id": selected["id"]}).json()
        assert profile["learner"]["id"] == selected["id"]
        assert profile["stats"]["streak_days"] == 1
        assert client.get("/api/me/profile").json()["learner"]["id"] == first["id"]
        assert client.get("/api/me/profile?learner_id=missing").status_code == 404
        assert client.post("/api/me/reset?learner_id=missing").status_code == 404
        assert client.post("/api/me/reset", params={"learner_id": selected["id"]}).status_code == 200
        assert db.get_learner(selected["id"])["baseline_mu"] is None
        assert db.get_learner(selected["id"])["baseline_source"] is None
        assert db.get_learner(first["id"])["baseline_mu"] == 1.0
