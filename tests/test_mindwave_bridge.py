"""The team's mindwave pipeline as NeuroPace's headset front end. No hardware: FakeSource and byte-level cross-checks."""

from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest

from mindwave import FakeSource, Pipeline
from mindwave.thinkgear import PacketParser, parse_payload
from neuropace.config import Settings
from neuropace.signal.features import FocusEngine
from neuropace.signal.headset import MindwaveHeadset, make_headset
from neuropace.signal.simulate import SimulatedEEG
from neuropace.signal.thinkgear import ThinkGearParser


def test_both_thinkgear_parsers_agree_on_the_same_bytes():
    sim = SimulatedEEG(seed=4)
    stream = b"".join(sim.next_bytes(256, with_status=(i % 2 == 0)) for i in range(4))
    ours = [e.value for e in ThinkGearParser().feed(stream) if e.kind == "raw"]
    theirs = PacketParser()
    raws = []
    for i in range(0, len(stream), 7):  # awkward chunking on purpose
        for payload in theirs.feed(stream[i : i + 7]):
            d = parse_payload(payload)
            raw = d.get(0x80)
            if isinstance(raw, bytes) and len(raw) == 2:
                raws.append(int.from_bytes(raw, "big", signed=True))
    assert ours == raws and len(ours) == 1024


def _frames(state: str, n: int, seed: int = 0):
    src = FakeSource(state=state, realtime=False, seed=seed)
    pipe = Pipeline(src, log_dir=None)
    out = []
    for f in pipe.frames():
        out.append(f)
        if len(out) >= n:
            break
    pipe.stop()
    return out


def test_fake_pipeline_frames_have_the_fields_neuropace_uses():
    frames = _frames("easy", 8)
    f = frames[-1]
    assert f.quality == 0 and f.valid and np.isfinite(f.engagement) and np.isfinite(f.effort)
    assert f.blink_count >= 0 and f.blink_rate >= 0
    off = _frames("off", 6)[-1]
    assert off.quality == 200 and not off.valid


def test_engine_external_mode_flags_a_drop_from_pipeline_frames():
    s = Settings(baseline_seconds=20)
    eng = FocusEngine(s)
    focused = _frames("hard", 60, seed=1)
    drowsy = _frames("drowsy", 40, seed=2)
    t = 0.0
    enters = []
    states = []
    for f in focused + drowsy:
        t += 1.0
        eng.feed_frame(f.effort, f.quality, f.valid, f.blink_count, extra={"effort": f.effort})
        smp, evs = eng.tick(t)
        states.append(smp.state)
        enters += [e.t for e in evs if e.kind == "enter"]
    assert eng.external and eng.baseline.ready
    assert "baseline" in states[:20] and states[30] == "ok"
    assert enters and enters[0] > 60, f"drop should be flagged after the switch at 60 s, got {enters}"
    assert eng.extra == {"effort": drowsy[-1].effort}
    # log10 index: e is 10**x
    assert smp.e is not None and abs(smp.e - 10 ** drowsy[-1].effort) < 1e-6


def test_engine_external_mode_gates_on_quality_and_staleness():
    s = Settings(baseline_seconds=5)
    eng = FocusEngine(s)
    eng.feed_frame(-0.5, 200, False)
    smp, _ = eng.tick(1.0)
    assert smp.quality == "bad" and smp.state == "bad"
    eng.feed_frame(-0.5, 0, True, blinks=2)
    smp, _ = eng.tick(2.0)
    assert smp.quality == "good" and smp.blink and eng.blinks.count == 2
    eng._ext_t = time.monotonic() - 10.0  # no frame for 10 s
    smp, _ = eng.tick(3.0)
    assert smp.quality == "bad"


@pytest.mark.asyncio
async def test_mindwave_headset_fake_delivers_frames_on_the_loop_and_maps_states():
    got = []
    hs = MindwaveHeadset(lambda f: got.append(f), fake=True)
    assert hs.kind == "fake" and hs.port == "fake"
    await hs.start()
    try:
        deadline = time.monotonic() + 8.0
        while len(got) < 2 and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        assert len(got) >= 2, "no frames from the fake pipeline within 8 s"
        assert hs.connected and hs.status()["frames"] >= 2
        hs.set_state("drifting")
        assert hs.source.state == "drowsy"
        hs.set_state("poor")
        assert hs.source.state == "off"
        hs.calibrate("easy")
        assert hs.status()["cal_phase"] == "easy"
        with pytest.raises(ValueError):
            hs.calibrate("nonsense")
    finally:
        await hs.stop()


@pytest.mark.parametrize("setting", ["/dev/cu.MindWaveMobile", "replay:/tmp/recording"])
def test_hardware_and_replay_do_not_report_or_accept_simulated_states(setting):
    headset = make_headset(setting, lambda *_: None, on_frame=lambda *_: None)
    assert headset.state is None
    with pytest.raises(ValueError, match="simulated"):
        headset.set_state("drifting")
    assert headset.state is None


def test_simulated_state_controls_remain_available():
    headset = make_headset("fake", lambda *_: None, on_frame=lambda *_: None)
    assert headset.state == "focused"
    headset.set_state("drifting")
    assert headset.state == "drifting"


def test_make_headset_routing():
    noop = lambda *_: None  # noqa: E731
    assert make_headset("sim", noop, on_frame=noop).kind == "simulated"
    assert make_headset("fake", noop, on_frame=noop).kind == "fake"
    r = make_headset("replay:/tmp/some-session", noop, on_frame=noop)
    assert r.kind == "replay" and r.replay_dir == "/tmp/some-session"
    assert make_headset("serial:/dev/cu.fake", noop, on_frame=noop).kind == "real"
    m = make_headset("/dev/cu.MindWaveMobile-SerialPort", noop, on_frame=noop)
    assert (
        isinstance(m, MindwaveHeadset) and m.kind == "real" and m.port == "/dev/cu.MindWaveMobile-SerialPort"
    )
