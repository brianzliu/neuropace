import time

import pytest

from neuropace.clock import ManualClock
from neuropace.core.session import SessionRuntime


@pytest.mark.parametrize("mode", ["live", "recorded"])
async def test_startup_calibration_keeps_connection_and_excludes_calibration_from_lecture(
    mode, settings, db, llm
):
    from neuropace.clock import MediaClock
    from neuropace.signal.features import DetectorEvent
    from neuropace.transcribe.transcript import Word

    rt, learner = await runtime(settings, db, llm)
    rt.mode = mode
    rt.review_only = False
    rt.startup_calibration = {"status": "waiting"}
    headset = rt.headset
    try:
        assert rt.snapshot()["startup_calibration"]["status"] == "waiting"
        rt.begin_personal_calibration()
        rt._on_words([Word("calibration", 10, 11)], True)
        rt._on_detector_events([DetectorEvent("enter", 12, 10, None)], 12)
        assert rt.words_total == 0 and not rt.flags
        add_window(rt)
        rt.step(40)
        assert rt.startup_calibration["status"] == "saved"
        assert db.get_learner(learner["id"])["baseline_source"] == "personal"
        await rt.complete_startup_calibration()
        assert not rt.calibration_pending
        assert rt.headset is headset
        assert rt.engine.baseline.ready and not rt._focus_hist and not rt._focus_buf
        assert rt.clock.now() < 1
        assert isinstance(rt.clock, MediaClock) == (mode == "recorded")
        rt._on_words([Word("lecture", 0, 1)], True)
        assert rt.words_total == 1
    finally:
        await rt.end()


async def test_startup_failure_can_retry_and_preserves_saved_baseline(settings, db, llm):
    rt, learner = await runtime(settings, db, llm)
    rt.mode = "live"
    rt.startup_calibration = {"status": "waiting"}
    before = db.get_learner(learner["id"])
    try:
        rt.begin_personal_calibration()
        add_window(rt, bad=True)
        rt.step(40)
        assert rt.startup_calibration["status"] == "failed"
        with pytest.raises(ValueError, match="calibration"):
            await rt.complete_startup_calibration()
        assert db.get_learner(learner["id"]) == before
        rt.begin_personal_calibration()
        assert rt.startup_calibration["status"] == "collecting"
        assert rt._personal_calibration["t_start"] == 40
    finally:
        await rt.end()
    assert db.get_learner(learner["id"]) == before


async def test_real_pipeline_uses_effort_when_beta_alertness_moves_the_other_way(settings, db, llm):
    from types import SimpleNamespace

    from neuropace.signal.features import FocusEngine

    rt, _ = await runtime(settings, db, llm)
    rt.engine = FocusEngine(settings, stored_baseline=(0.4, 0.1))
    extras = dict.fromkeys(
        (
            "alpha_ratio",
            "blink_rate",
            "z_effort_ema",
            "z_engagement_ema",
            "artifact_coverage",
            "cal_phase",
            "attention",
            "log_theta",
            "log_alpha",
            "log_beta",
        )
    )
    try:
        for second in range(30):
            rt._on_frame(
                SimpleNamespace(
                    **extras,
                    effort=0.4 if second < 10 else -0.2,
                    engagement=-0.6 if second < 10 else 0.5,
                    quality=0,
                    valid=True,
                    blink_count=0,
                    calibrated=False,
                )
            )
            rt.clock.set(second + 11)
            sample = rt.step()
            if second == 0:
                assert sample["x"] == pytest.approx(0.4)
        assert any(flag["source"] == "eeg" for flag in rt.flags.values())
        assert rt.engine.extra["engagement"] == 0.5
    finally:
        await rt.end()


async def test_personal_calibration_does_not_fit_the_waiting_period_ema(settings, db, llm):
    rt, _ = await runtime(settings, db, llm)
    try:
        rt.begin_personal_calibration()
        rt.engine.feed_frame(0.4, 0, True, extra={"cal_phase": None})
        sample = rt.step(11)
        assert sample["x"] == pytest.approx(0.4)
    finally:
        await rt.end()


@pytest.mark.parametrize("use_stored", [None, True])
async def test_legacy_engagement_baseline_is_never_reused_as_effort(app, db, use_stored):
    import httpx

    learner = db.default_learner()
    assert db.compare_and_set_learner_baseline(
        learner["id"], -0.6, 0.12, learner["baseline_at"], metric="beta_ratio_v1"
    )
    before = db.get_learner(learner["id"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        body = {"learner_id": learner["id"], "mode": "review", "headset": "sim", "totem": "keyboard"}
        if use_stored is not None:
            body["use_stored_baseline"] = use_stored
        response = await client.post("/api/sessions", json=body)
        assert response.status_code == 200
        session = response.json()
        try:
            assert session["baseline"] is None
            assert not app.state.runtimes[session["id"]].engine.baseline.ready
        finally:
            await client.post(f"/api/sessions/{session['id']}/end")
    assert db.get_learner(learner["id"]) == before


@pytest.mark.parametrize("phase", ["waiting", "collecting", "failed"])
async def test_button_only_continuation_preserves_baseline_and_suppresses_only_eeg(phase, settings, db, llm):
    from neuropace.signal.features import DetectorEvent
    from neuropace.transcribe.transcript import Word

    rt, learner = await runtime(settings, db, llm)
    before = db.get_learner(learner["id"])
    rt.mode = "live"
    rt.review_only = False
    rt.startup_calibration = {"status": "waiting"}
    if phase == "collecting":
        rt.begin_personal_calibration()
    else:
        rt.startup_calibration = {"status": phase}
    try:
        result = await rt.complete_startup_calibration(without_eeg=True)
        assert result["status"] == "complete" and result["skipped"]
        assert not rt.calibration_pending and not rt.focus_enabled
        assert rt.headset_status()["focus_enabled"] is False
        assert rt._personal_calibration is None
        rt.engine.feed_frame(-10, 0, True)
        sample = rt.step(1)
        assert sample["focus_enabled"] is False and sample["x"] is None
        assert sample["state"] == "nosignal" and not sample["baseline_ready"]
        rt._on_detector_events([DetectorEvent("enter", 1, 0, None)], 1)
        assert not rt.flags
        rt._on_words([Word("The lecture keeps recording.", 0, 1)], True)
        assert rt.words_total == 1
        assert rt.tap("key")["source"] == "key"
    finally:
        await rt.end()
    assert db.get_learner(learner["id"]) == before
    assert db.get_session(rt.id)["baseline"]["focus_enabled"] is False


async def test_button_only_api_survives_a_fresh_consumer(app, settings, db, llm):
    import httpx

    rt, learner = await runtime(settings, db, llm)
    rt.mode = "live"
    rt.startup_calibration = {"status": "waiting"}
    app.state.runtimes[rt.id] = rt
    before = db.get_learner(learner["id"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        r = await client.post(f"/api/sessions/{rt.id}/personal-calibration/skip")
        assert r.status_code == 200 and r.json()["skipped"]
        assert (await client.get(f"/api/sessions/{rt.id}")).json()["focus_enabled"] is False
        await client.post(f"/api/sessions/{rt.id}/end")
        assert (await client.get(f"/api/sessions/{rt.id}")).json()["focus_enabled"] is False
        assert db.get_learner(learner["id"]) == before


async def runtime(settings, db, llm):
    learner = db.create_learner("Calibration test")
    db.set_learner_baseline(learner["id"], 1.0, 0.2)
    session = db.create_session(
        learner_id=learner["id"], lecture_id=None, mode="review", catchup_policy="always"
    )
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
    rt.clock = ManualClock(10)
    await rt.start()
    rt.headset.kind = "real"
    rt.engine.feed_frame(-0.3, 0, True, extra={"cal_phase": None})
    rt._raw_last_mono = time.monotonic()
    rt.step(10)
    return rt, learner


def add_window(rt, bad=False):
    for second in range(30):
        rt._focus_hist.append(
            {
                "t": 10.5 + second,
                "x": -0.3 + second / 1000,
                "quality": "bad" if bad else "good",
                "state": "bad" if bad else "baseline",
                "sim": False,
                "artifact": False,
                "paused": False,
                "mw": {"cal_phase": None},
            }
        )
    rt.clock.set(40)
    rt._raw_last_mono = time.monotonic()


async def test_preview_does_not_save_but_apply_is_persisted_and_idempotent(settings, db, llm):
    rt, learner = await runtime(settings, db, llm)
    try:
        start = rt.begin_personal_calibration()
        assert start["duration_seconds"] == 30 and start["t_start"] == 10
        with pytest.raises(ValueError, match="30 seconds"):
            rt.finish_personal_calibration()
        add_window(rt)
        preview = rt.finish_personal_calibration()
        assert preview["saved"] is False
        assert db.get_learner(learner["id"])["baseline_mu"] == 1.0
        saved = rt.finish_personal_calibration(apply=True)
        assert saved["saved"] is True
        persisted = db.get_learner(learner["id"])
        assert persisted["baseline_mu"] == saved["mu"]
        assert persisted["baseline_sigma"] == saved["sigma"]
        assert rt.snapshot()["learner"]["baseline_mu"] == saved["mu"]
        assert rt.snapshot()["session"]["baseline"]["mu"] == saved["mu"]
        assert rt.finish_personal_calibration(apply=True) == saved
        assert db.get_learner(learner["id"])["baseline_at"] == persisted["baseline_at"]
    finally:
        await rt.end()


async def test_failed_calibration_and_session_end_preserve_the_old_baseline(settings, db, llm):
    rt, learner = await runtime(settings, db, llm)
    before = db.get_learner(learner["id"])
    rt.begin_personal_calibration()
    add_window(rt, bad=True)
    with pytest.raises(ValueError, match="24"):
        rt.finish_personal_calibration(apply=True)
    rt.engine.baseline.mu, rt.engine.baseline.sigma = -9.0, 0.8
    await rt.end()
    assert db.get_learner(learner["id"]) == before


async def test_a_newer_calibration_is_not_overwritten(settings, db, llm):
    rt, learner = await runtime(settings, db, llm)
    try:
        rt.begin_personal_calibration()
        add_window(rt)
        db.set_learner_baseline(learner["id"], 2.0, 0.3)
        with pytest.raises(ValueError, match="changed"):
            rt.finish_personal_calibration(apply=True)
        assert db.get_learner(learner["id"])["baseline_mu"] == 2.0
    finally:
        await rt.end()


@pytest.mark.parametrize("kind", ["simulated", "fake", "replay", "virtual"])
async def test_only_real_headsets_can_calibrate_a_person(kind, settings, db, llm):
    rt, _ = await runtime(settings, db, llm)
    rt.headset.kind = kind
    try:
        with pytest.raises(ValueError, match="real headset"):
            rt.begin_personal_calibration()
    finally:
        await rt.end()


async def test_no_start_or_a_duplicate_start_cannot_silently_change_the_window(settings, db, llm):
    rt, _ = await runtime(settings, db, llm)
    try:
        with pytest.raises(ValueError, match="not started"):
            rt.finish_personal_calibration()
        rt.begin_personal_calibration()
        with pytest.raises(ValueError, match="already"):
            rt.begin_personal_calibration()
    finally:
        await rt.end()


async def test_personal_calibration_api_and_a_fresh_consumer(app, settings, db, llm):
    import httpx

    rt, learner = await runtime(settings, db, llm)
    app.state.runtimes[rt.id] = rt
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        root = f"/api/sessions/{rt.id}/personal-calibration"
        try:
            assert (
                await client.post(root + "/start", headers={"Origin": "https://untrusted.invalid"})
            ).status_code == 403
            started = await client.post(root + "/start")
            assert started.status_code == 200, started.text
            assert (await client.post(root + "/finish", json={"apply": True})).status_code == 409
            add_window(rt)
            preview = await client.post(root + "/finish", json={})
            assert preview.status_code == 200 and preview.json()["saved"] is False
            assert db.get_learner(learner["id"])["baseline_mu"] == 1.0
            saved = await client.post(root + "/finish", json={"apply": True})
            assert saved.status_code == 200 and saved.json()["saved"] is True
        finally:
            await rt.end()
            app.state.runtimes.pop(rt.id, None)
        fresh = await client.post(
            "/api/sessions",
            json={
                "learner_id": learner["id"],
                "mode": "review",
                "headset": "sim",
                "totem": "keyboard",
                "use_stored_baseline": True,
            },
        )
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()["baseline"]["stored"] is True
        assert fresh.json()["baseline"]["mu"] == saved.json()["mu"]
        assert fresh.json()["baseline"]["sigma"] == saved.json()["sigma"]
        await client.post(f"/api/sessions/{fresh.json()['id']}/end")


async def test_explicit_personal_baseline_is_used_by_default_but_can_be_disabled(app, settings, db, llm):
    import httpx

    rt, learner = await runtime(settings, db, llm)
    rt.begin_personal_calibration()
    add_window(rt)
    saved = rt.finish_personal_calibration(apply=True)
    await rt.end()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for preference in (None, False):
            body = {"learner_id": learner["id"], "mode": "review", "headset": "sim", "totem": "keyboard"}
            if preference is not None:
                body["use_stored_baseline"] = preference
            response = await client.post("/api/sessions", json=body)
            assert response.status_code == 200, response.text
            fresh = response.json()
            try:
                if preference is None:
                    assert fresh["baseline"] is not None
                    assert fresh["baseline"]["stored"] is True
                    assert fresh["baseline"]["mu"] == saved["mu"]
                else:
                    assert fresh["baseline"] is None
            finally:
                await client.post(f"/api/sessions/{fresh['id']}/end")
