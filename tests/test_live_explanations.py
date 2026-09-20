import asyncio
import json
from types import SimpleNamespace

import pytest

from neuropace.clock import ManualClock
from neuropace.core.explanations import CatchupExplanations
from neuropace.llm.client import LLMUnavailable
from neuropace.transcribe.scripted import script_from_text
from neuropace.transcribe.transcript import Transcript


@pytest.fixture
def runtime(settings):
    transcript = Transcript()
    transcript.append(
        script_from_text(
            "A pendulum swings left and right. It moves fastest at the bottom and slows down at each end."
        )
    )
    events = []
    rt = SimpleNamespace(
        s=settings,
        status="running",
        review_only=False,
        clock=ManualClock(20),
        transcript=transcript,
        llm=object(),
        keyterms=[],
        seed=7,
        broadcast=events.append,
        flags={"flag_a": {"id": "flag_a", "t_start": 0, "t_trigger": 20, "t_end": 20, "catchup_shown": True}},
    )
    return rt, events


def package():
    return {
        "note": {
            "what_was_said": "A pendulum swings.",
            "key_term": "pendulum",
            "definition": "A swinging object.",
            "connection": "It exchanges energy.",
        },
        "question": {
            "question": "Where is it fastest?",
            "correct_index": 0,
            "options": ["Bottom", "Left", "Right", "Everywhere"],
            "explanation": "It moves fastest at the bottom.",
        },
        "artifacts": {
            "summary": "The pendulum moves back and forth.",
            "key_idea": {
                "term": "pendulum",
                "definition": "A swinging object.",
                "example": "It slows at the ends.",
            },
            "plan": {"visual": "animation", "doing": "steps", "why": "Show the repeated motion."},
            "animation": {
                "title": "Pendulum",
                "caption": "Back and forth.",
                "html": "<div><svg></svg><script>requestAnimationFrame(()=>{});</script></div>",
            },
            "steps": {
                "title": "Follow the swing",
                "steps": ["Start on the left.", "Move through the bottom."],
            },
        },
        "sources": {"core": "llm", "animation": "llm", "steps": "llm"},
    }


async def test_request_is_nonblocking_deduplicated_and_returns_real_artifacts(runtime, monkeypatch):
    rt, events = runtime
    release = asyncio.Event()
    calls = []

    async def build(*args, **kwargs):
        calls.append(args)
        await release.wait()
        return package(), "llm"

    monkeypatch.setattr("neuropace.core.explanations.build_package", build)
    explanations = CatchupExplanations(rt)
    assert explanations.request("flag_a")["status"] == "pending"
    first = explanations.jobs["flag_a"]
    assert explanations.request("flag_a")["status"] == "pending"
    assert explanations.jobs["flag_a"] is first
    release.set()
    await first
    result = explanations.snapshot()[0]
    assert result["status"] == "ready" and len(calls) == 1
    assert result["options"][0]["artifact"] == "animation"
    assert result["options"][0]["content"]["html"] == package()["artifacts"]["animation"]["html"]
    assert "correct_index" not in json.dumps(result)
    assert [event["status"] for event in events] == ["pending", "ready"]
    span = rt.transcript.text_between(0, 20)
    assert explanations.match(span, "") == (package(), "cache")
    assert explanations.match(span + " new content", "") is None


async def test_withheld_or_foreign_flags_cannot_generate_visuals(runtime):
    rt, _ = runtime
    explanations = CatchupExplanations(rt)
    rt.flags["flag_a"]["catchup_shown"] = False
    with pytest.raises(ValueError):
        explanations.request("flag_a")
    with pytest.raises(ValueError):
        explanations.request("foreign_flag")
    assert not explanations.jobs


async def test_generation_failure_is_visible_and_retryable(runtime, monkeypatch):
    rt, _ = runtime
    attempts = 0

    async def build(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LLMUnavailable("synthetic provider failure")
        return package(), "llm"

    monkeypatch.setattr("neuropace.core.explanations.build_package", build)
    explanations = CatchupExplanations(rt)
    explanations.request("flag_a")
    await explanations.jobs["flag_a"]
    assert explanations.snapshot()[0]["status"] == "failed"
    assert explanations.snapshot()[0]["error"]
    explanations.request("flag_a")
    await explanations.jobs["flag_a"]
    assert explanations.snapshot()[0]["status"] == "ready" and attempts == 2


async def test_api_tap_delivers_visual_snapshot_and_foreign_flags_are_rejected(
    app, settings, db, llm, monkeypatch
):
    import httpx

    from neuropace.core.session import SessionRuntime

    async def build(*args, **kwargs):
        return package(), "llm"

    monkeypatch.setattr("neuropace.core.explanations.build_package", build)
    learner = db.default_learner()
    session = db.create_session(learner_id=learner["id"], lecture_id=None, mode="live")
    rt = SessionRuntime(
        settings,
        db,
        llm,
        session,
        learner,
        None,
        "none",
        headset_port="sim",
        totem_port="keyboard",
        drive_manually=True,
    )
    rt.clock = ManualClock(8)
    await rt.start()
    app.state.runtimes[rt.id] = rt
    rt._on_words(
        script_from_text(
            "A pendulum swings left and right. It moves fastest at the bottom and slows down at each end."
        ),
        True,
    )
    q = rt.subscribe()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(f"/api/sessions/{rt.id}/tap")
            assert response.status_code == 200
            flag_id = response.json()["id"]
            await rt.explanations.finish()
            details = rt.snapshot()["catchup_explanations"]
            assert details[0]["flag_id"] == flag_id and details[0]["status"] == "ready"
            assert details[0]["options"][0]["artifact"] == "animation"
            retry = await client.post(f"/api/sessions/{rt.id}/catchups/{flag_id}/explanation")
            assert retry.status_code == 200 and retry.json()["status"] == "ready"
            assert (
                await client.post(f"/api/sessions/{rt.id}/catchups/foreign/explanation")
            ).status_code == 404
        messages = []
        while not q.empty():
            messages.append(q.get_nowait())
        assert any(m["type"] == "catchup" and m["rich"] for m in messages)
        assert any(m["type"] == "catchup_explanation" and m["status"] == "ready" for m in messages)
        rt.force_flag()
        offered = list(rt.flags)[-1]
        assert offered not in rt.explanations.jobs
        rt.open_catchup(offered)
        await rt.explanations.finish()
        assert rt.explanations.states[offered]["status"] == "ready"
    finally:
        await rt.end()
        app.state.runtimes.pop(rt.id, None)


async def test_generation_is_bounded_and_stops_with_the_session(runtime, monkeypatch):
    rt, _ = runtime

    async def build(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr("neuropace.core.explanations.build_package", build)
    explanations = CatchupExplanations(rt)
    for key in ("flag_b", "flag_c"):
        rt.flags[key] = {**rt.flags["flag_a"], "id": key}
    explanations.request("flag_a")
    explanations.request("flag_b")
    assert explanations.request("flag_c")["status"] == "failed"
    await explanations.stop()
    assert all(job.done() for job in explanations.jobs.values())
