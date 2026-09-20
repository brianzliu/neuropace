"""The brain-wave path (docs/PRODUCT.md §6 "your brain waves"): raw chunks from every headset kind, stream health,
a headset that comes on mid-lecture, and the virtual headset over a real serial (pty) link."""

from __future__ import annotations

import asyncio
import sys
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from mindwave import FakeSource, Pipeline
from neuropace.clock import ManualClock
from neuropace.core.session import UV_PER_RAW, SessionRuntime
from neuropace.signal.headset import MindwaveHeadset


def _runtime(settings, db, llm, headset, drive_manually=False, tick=0.2, headset_auto=False):
    lrn = db.default_learner()
    sess = db.create_session(learner_id=lrn["id"], lecture_id=None, mode="review", seed=5)
    return SessionRuntime(
        settings,
        db,
        llm,
        sess,
        lrn,
        None,
        "none",
        headset_port=headset,
        totem_port="keyboard",
        tick_interval=tick,
        drive_manually=drive_manually,
        headset_auto=headset_auto,
    )


def _drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


async def _wait(pred, timeout: float, step: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        await asyncio.sleep(step)
    return pred()


@pytest.mark.asyncio
async def test_simulator_raw_chunks_are_microvolts_at_64_hz(settings, db, llm):
    rt = _runtime(settings, db, llm, "sim", drive_manually=True)
    rt.clock = ManualClock(0.0)
    await rt.start()
    q = rt.subscribe()
    for sec in range(1, 4):
        rt.clock.set(float(sec))
        rt.feed_sim_second()
        rt.step(float(sec))
    raws = [m for m in _drain(q) if m["type"] == "raw"]
    assert len(raws) == 24, "8 chunks of 8 samples per second at 64 Hz"
    assert all(m["fs"] == 64 and len(m["uv"]) == 8 for m in raws)
    peak = max(abs(v) for m in raws for v in m["uv"])
    assert 5 < peak < 600, f"microvolt scale, got peak {peak}"
    st = rt.headset_status()
    assert st["simulated"] is True and st["stream"]["chunks"] == 24 and st["stream"]["live"] is True
    await rt.end()


@pytest.mark.asyncio
async def test_pipeline_fake_headset_streams_raw_through_the_runtime(settings, db, llm):
    rt = _runtime(settings, db, llm, "fake")
    await rt.start()
    q = rt.subscribe()
    try:
        assert await _wait(lambda: rt._raw_chunks >= 8, 6.0), "no raw chunks from the pipeline within 6 s"
        msgs = _drain(q)
        raws = [m for m in msgs if m["type"] == "raw"]
        assert raws and all(m["fs"] == 64 and len(m["uv"]) == 8 for m in raws)
        st = rt.headset_status()
        assert st["kind"] == "fake" and st["connected"] and st["stream"]["live"]
        hello = rt.snapshot()
        assert hello["sim"]["headset"] is True and hello["headset"]["stream"]["live"] is True
        # the first headset message of the session carries the stream health too
        hs = [m for m in msgs if m["type"] == "headset"]
        assert hs and "stream" in hs[0]
    finally:
        await rt.end()


@pytest.mark.asyncio
async def test_replay_raw_chunks_are_bit_exact_with_the_recording(tmp_path):
    src = FakeSource(state="easy", realtime=False, seed=3)
    pipe = Pipeline(src, log_dir=str(tmp_path / "eeg"))
    got = []
    for f in pipe.frames():
        got.append(f)
        if len(got) >= 2:
            break
    session_dir = pipe.session_dir
    pipe.stop()
    raw = np.fromfile(session_dir / "raw.int16", dtype="<i2")
    assert raw.size >= 512 * 4
    chunks: list[dict] = []
    hs = MindwaveHeadset(lambda f: None, replay_dir=str(session_dir), replay_speed=0, on_raw=chunks.append)
    assert hs.kind == "replay"
    await hs.start()
    try:
        assert await _wait(lambda: len(chunks) >= 4, 6.0)
    finally:
        await hs.stop()
    expected = [round(float(np.mean(raw[i * 8 : (i + 1) * 8])) * UV_PER_RAW, 1) for i in range(8)]
    assert chunks[0]["fs"] == 64 and chunks[0]["uv"] == expected


@pytest.mark.asyncio
async def test_stream_stall_and_recovery_are_broadcast(settings, db, llm):
    rt = _runtime(settings, db, llm, "fake")
    await rt.start()
    q = rt.subscribe()
    try:
        assert await _wait(lambda: rt.headset_status()["stream"]["live"], 6.0)
        _drain(q)
        rt.headset.source.stop()  # the device goes quiet (Bluetooth out of range)
        assert await _wait(lambda: not rt.headset_status()["stream"]["live"], 5.0)
        await asyncio.sleep(0.5)
        hs = [m for m in _drain(q) if m["type"] == "headset"]
        assert hs and hs[-1]["stream"]["live"] is False and hs[-1]["connected"] is False
        assert rt.headset_status()["stream"]["age_s"] >= rt.RAW_STALE_S
    finally:
        await rt.end()


@pytest.mark.asyncio
async def test_headset_that_comes_on_mid_lecture_replaces_the_simulator(settings, db, llm, monkeypatch):
    import neuropace.signal.headset as hs_mod

    monkeypatch.setattr(
        hs_mod, "autodetect_headset_port", lambda probe=True: "/dev/cu.MindWaveMobile-SerialPort"
    )
    rt = _runtime(settings, db, llm, "sim", headset_auto=True)

    def fake_real(port: str):
        h = MindwaveHeadset(rt._on_frame, fake=True, on_raw=rt._on_raw_chunk)
        h.kind, h.port = "real", port  # the pipeline on a serial port, minus the serial port
        return h

    monkeypatch.setattr(rt, "_make_real_headset", fake_real)
    await rt.start()
    q = rt.subscribe()
    try:
        assert rt.headset.kind == "simulated" and rt._headset_auto
        assert await _wait(lambda: rt.headset.kind == "real", 8.0), (
            "the probe should attach within a few seconds"
        )
        assert await _wait(lambda: rt.engine.external and rt.headset_status()["stream"]["live"], 8.0)
        msgs = _drain(q)
        kinds = [m["kind"] for m in msgs if m["type"] == "headset"]
        assert "simulated" in kinds and kinds[-1] == "real"
        assert any("Headset connected" in m["text"] for m in msgs if m["type"] == "notice")
        assert db.get_session(rt.id)["headset_kind"] == "real"
        assert rt.snapshot()["sim"]["headset"] is False
        focus = [m for m in msgs if m["type"] == "focus"]
        assert focus and focus[-1]["sim"] is False
    finally:
        await rt.end()


@pytest.mark.asyncio
async def test_restudy_session_measures_focus_on_the_wall_clock(settings, db, llm):
    """Restudy is headset only. Its clock must run (a paused media clock marked every second paused, so no
    card ever had a focus ratio and no drift ever switched an explanation) and the lecture's stored baseline
    must make a drowsy wearer a drop within seconds."""
    from mindwave import FakeSource, Pipeline

    def frames(state: str, n: int, seed: int):
        pipe = Pipeline(FakeSource(state=state, realtime=False, seed=seed), log_dir=None)
        out = []
        for f in pipe.frames():
            out.append(f)
            if len(out) >= n:
                break
        pipe.stop()
        return out

    lrn = db.default_learner()
    db.set_learner_baseline(lrn["id"], -0.55, 0.06)
    lrn = db.default_learner()
    sess = db.create_session(
        learner_id=lrn["id"],
        lecture_id=None,
        mode="review",
        seed=7,
        baseline={"mu": lrn["baseline_mu"], "sigma": lrn["baseline_sigma"], "stored": True},
    )
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
    await rt.start()
    q = rt.subscribe()
    assert rt.engine.baseline.ready and rt.engine.baseline.stored
    easy, drowsy = frames("easy", 12, 1), frames("drowsy", 40, 2)
    t = 0.0
    for f in easy + drowsy:
        t += 1.0
        rt._on_frame(f)
        d = rt.step(t)
        await asyncio.sleep(0)
    assert d["t"] == t and d["paused"] is False and d["x"] is not None and d["quality"] == "good"
    assert rt.engine.external
    msgs = _drain(q)
    flags = [m for m in msgs if m["type"] == "flag_open" and m["flag"]["source"] == "eeg"]
    assert flags, "a drowsy wearer against the lecture's baseline must be flagged during restudy"
    assert 12 < flags[0]["flag"]["t_trigger"] < 40
    await rt.end()


def test_devices_endpoint_is_cheap_and_cached(app):
    with TestClient(app) as c:
        d = c.get("/api/devices").json()
        assert d["headset"]["kind"] == "simulated" and d["totem"]["kind"] == "keyboard"
        assert d["checked_at"] == c.get("/api/devices").json()["checked_at"], "cached for a few seconds"


@pytest.mark.skipif(sys.platform == "win32", reason="needs a pty")
def test_virtual_headset_is_a_real_headset_to_the_pipeline(tmp_path):
    """ThinkGear bytes over a pty: the serial reader, parser, pipeline and stream health all see a real device."""
    from mindwave import MindWaveSource
    from neuropace.signal.headset import make_headset, resolve_headset
    from neuropace.signal.virtual_headset import VirtualHeadset

    ctl = tmp_path / "ctl"
    vh = VirtualHeadset(state="easy", control_path=str(ctl), seed=2)
    path = vh.start()
    try:
        assert resolve_headset(path) == path
        h = make_headset(path, lambda *_: None, on_frame=lambda f: None)
        assert isinstance(h, MindwaveHeadset) and h.kind == "real" and h.port == path
        src = MindWaveSource(path)
        pipe = Pipeline(src, log_dir=None)
        frames, raws = [], []
        pipe.on_frame(frames.append)
        pipe.on_raw(raws.append)
        pipe.start()
        try:
            t0 = time.monotonic()
            while time.monotonic() - t0 < 8 and len(frames) < 2:
                time.sleep(0.05)
            assert len(frames) >= 2 and src.connected and src.error is None
            f = frames[-1]
            assert f.quality == 0 and f.valid and np.isfinite(f.engagement) and f.attention is not None
            assert raws and raws[-1]["fs"] == 64 and len(raws[-1]["uv"]) == 8
            assert max(abs(v) for v in raws[-1]["uv"]) < 400
            ctl.write_text("state off\n")
            t0 = time.monotonic()
            while time.monotonic() - t0 < 4 and (not frames or frames[-1].quality != 200):
                time.sleep(0.05)
            assert frames[-1].quality == 200, "electrode off must reach the pipeline as poor_signal 200"
            ctl.write_text("pause 4\n")
            # the control file is read within 0.25 s, so the wire is silent from about t+0.25 to t+4.25;
            # connected means bytes in the last 3 s: false at t+3.6, true again by t+5.5
            time.sleep(3.6)
            assert not src.connected, "no bytes for more than 3 s = disconnected"
            time.sleep(1.9)
            assert src.connected, "bytes again = reconnected without reopening the port"
        finally:
            pipe.stop()
    finally:
        vh.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="needs a pty")
def test_one_headset_one_lecture_over_the_api(app, monkeypatch):
    """A second lecture on the same serial port is refused while the first records; a restudy session that is
    being replaced lets go of the port within seconds instead."""
    from neuropace.signal.virtual_headset import VirtualHeadset

    vh = VirtualHeadset(state="easy", seed=4)
    path = vh.start()
    try:
        with TestClient(app) as c:
            first = c.post(
                "/api/sessions",
                json={"lecture_id": "lec_demo0001", "mode": "live", "headset": path, "totem": "keyboard"},
            )
            assert first.status_code == 200 and first.json()["headset"]["kind"] == "real"
            second = c.post(
                "/api/sessions",
                json={"lecture_id": "lec_demo0001", "mode": "live", "headset": path, "totem": "keyboard"},
            )
            assert second.status_code == 409 and "still recording" in second.json()["detail"]
            c.post(f"/api/sessions/{first.json()['id']}/end")
            review = c.post("/api/sessions", json={"mode": "review", "headset": path, "totem": "keyboard"})
            assert review.status_code == 200
            # the next screen's restudy session arrives while the previous one is still ending
            import threading

            threading.Timer(0.3, lambda: c.post(f"/api/sessions/{review.json()['id']}/end")).start()
            t0 = time.monotonic()
            review2 = c.post("/api/sessions", json={"mode": "review", "headset": path, "totem": "keyboard"})
            assert review2.status_code == 200 and time.monotonic() - t0 < 4.5
            c.post(f"/api/sessions/{review2.json()['id']}/end")
    finally:
        vh.stop()
