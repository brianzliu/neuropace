import math

import numpy as np

from neuropace.config import Settings
from neuropace.signal.blinks import BlinkDetector
from neuropace.signal.features import Baseline, DropDetector, FocusEngine, band_powers, blank_blinks
from neuropace.signal.simulate import SimulatedEEG
from neuropace.signal.thinkgear import ThinkGearParser


def tone(freq: float, fs: int = 512, seconds: float = 2.0, amp: float = 20.0) -> np.ndarray:
    t = np.arange(int(fs * seconds)) / fs
    return amp * np.sin(2 * np.pi * freq * t)


def test_band_powers_isolate_tones():
    bp = band_powers(tone(6.0), 512)
    assert bp["theta"] > 20 * (bp["alpha"] + bp["beta"])
    bp = band_powers(tone(20.0), 512)
    assert bp["beta"] > 20 * (bp["alpha"] + bp["theta"])


def test_raw_focus_uses_theta_alpha_and_not_forehead_beta():
    values = []
    for beta in (2.0, 35.0):
        engine = FocusEngine(Settings())
        engine.feed_poor_signal(0)
        engine.feed_raw(tone(6, amp=20) + tone(10, amp=10) + tone(20, amp=beta))
        sample, _ = engine.tick(1)
        values.append(sample.x)
    assert values[0] == values[1]
    assert math.isclose(values[0], math.log10(4), abs_tol=0.001)


def test_blank_blinks_removes_bump():
    x = tone(10.0)
    x[400:460] += 500.0
    cleaned = blank_blinks(x, [430], 512)
    assert cleaned.max() < 60 and cleaned.min() > -60


def test_blink_detector_counts_bumps_once():
    fs = 512
    det = BlinkDetector(fs)
    rng = np.random.default_rng(0)
    x = rng.normal(0, 10, fs * 6) + 15 * np.sin(2 * np.pi * 10 * np.arange(fs * 6) / fs)
    for c in (1.0, 2.5, 4.2):
        i = int(c * fs)
        x[i - 25 : i + 25] += 400 * np.exp(-0.5 * (np.arange(-25, 25) / 8) ** 2)
    n = 0
    for i in range(0, x.size, 64):
        n += det.feed(x[i : i + 64])
    assert n == 3 and det.count == 3


def test_baseline_readiness_rules():
    b = Baseline(seconds=10, min_valid_fraction=0.6, min_valid_samples=3, sigma_floor=0.05)
    for _ in range(5):
        b.add(0.1, listening=True)
    assert not b.ready
    b.add(0.2, listening=True)
    assert b.ready and b.sigma >= 0.05
    b2 = Baseline(seconds=10, min_valid_fraction=0.6, min_valid_samples=3, sigma_floor=0.05)
    for i in range(10):
        b2.add(
            0.1 if i < 3 else None, listening=True
        )  # mostly artifacts, but the period ends with >= 3 valid
    assert b2.ready


def test_drop_detector_hysteresis_cap_refractory_and_lead_in():
    s = Settings(lead_in_seconds=8, eeg_flag_max_seconds=45, eeg_refractory_seconds=20)
    d = DropDetector(s)
    assert d.update(10.0, -1.5, allowed=False) == []  # suppressed
    ev = d.update(11.0, -1.5, allowed=True)
    assert ev and ev[0].kind == "enter" and ev[0].t_start == 3.0
    assert d.update(12.0, -0.8, True) == []  # between exit and enter thresholds: stays in drop
    ev = d.update(13.0, -0.2, True)
    assert ev and ev[0].kind == "exit" and ev[0].t_end == 13.0
    assert d.update(20.0, -3.0, True) == []  # refractory
    ev = d.update(34.0, -3.0, True)
    assert ev and ev[0].kind == "enter"
    exits = []
    for t in range(35, 81):
        out = d.update(float(t), -3.0, True)
        exits += [(e.t, e.kind) for e in out]
    assert exits == [(79.0, "exit")], "45 s cap closes the flag even while z stays low"
    assert not d.in_drop


def _run_engine(
    s: Settings, seconds: int, drift_at: int | None = None, recover_at: int | None = None, seed: int = 1
):
    sim = SimulatedEEG(seed=seed)
    parser = ThinkGearParser()
    eng = FocusEngine(s)
    samples, events = [], []
    for sec in range(1, seconds + 1):
        if drift_at and sec == drift_at:
            sim.set_state("drifting")
        if recover_at and sec == recover_at:
            sim.set_state("focused")
        for ev in parser.feed(sim.next_bytes(512, with_status=True)):
            if ev.kind == "raw":
                eng.feed_raw([ev.value])
            elif ev.kind == "poor_signal":
                eng.feed_poor_signal(ev.value)
        smp, evs = eng.tick(float(sec))
        samples.append(smp)
        events += evs
    return eng, samples, events


def test_engine_baseline_then_drop_flag_with_lead_in():
    s = Settings(baseline_seconds=30)
    eng, samples, events = _run_engine(s, 120, drift_at=60, recover_at=100)
    assert samples[10].state == "baseline" and not samples[10].baseline_ready
    assert samples[35].baseline_ready and samples[35].state == "ok"
    enters = [e for e in events if e.kind == "enter"]
    assert enters, "drift should be flagged"
    assert 60 < enters[0].t <= 80
    assert math.isclose(enters[0].t_start, enters[0].t - 8.0)
    assert eng.blinks.count >= 8
    assert any(smp.blink for smp in samples)


def test_engine_time_in_drop_separates_focused_from_drifting():
    """Detector quality on the simulator: little time in drop while focused, most of the time in drop while drifting."""
    s = Settings(baseline_seconds=180)
    focused = 0
    drifting = 0
    for seed in (5, 6):
        _, samples, _ = _run_engine(s, 480, seed=seed)
        focused += sum(1 for smp in samples[180:] if smp.state == "drop") / 300
        _, samples, _ = _run_engine(s, 420, drift_at=200, seed=seed + 10)
        drifting += sum(1 for smp in samples[230:] if smp.state == "drop") / 190
    assert focused / 2 < 0.3, f"focused wearer spends {focused / 2:.0%} of the time flagged"
    assert drifting / 2 > 0.45, f"drifting wearer spends only {drifting / 2:.0%} of the time flagged"


def test_engine_bad_quality_suppresses_everything():
    s = Settings(baseline_seconds=10)
    sim = SimulatedEEG(seed=2, state="poor")
    parser = ThinkGearParser()
    eng = FocusEngine(s)
    for sec in range(1, 30):
        for ev in parser.feed(sim.next_bytes(512, with_status=True)):
            if ev.kind == "raw":
                eng.feed_raw([ev.value])
            elif ev.kind == "poor_signal":
                eng.feed_poor_signal(ev.value)
        smp, evs = eng.tick(float(sec))
        assert smp.quality == "bad" and smp.state == "bad" and not evs


def test_stored_baseline_is_ready_immediately():
    s = Settings()
    eng = FocusEngine(s, stored_baseline=(0.1, 0.3))
    assert eng.baseline.ready and eng.baseline.stored
    smp, _ = eng.tick(1.0)
    assert smp.state == "nosignal"


def test_serial_silence_does_not_reuse_old_samples(monkeypatch):
    now = [10.0]
    monkeypatch.setattr("neuropace.signal.features.time.monotonic", lambda: now[0])
    eng = FocusEngine(Settings(), stored_baseline=(0.0, 0.1))
    eng.feed_poor_signal(0)
    eng.feed_raw(tone(10) + tone(20))
    sample, _ = eng.tick(1)
    assert sample.x is not None
    now[0] += 4
    sample, events = eng.tick(2)
    assert sample.quality == "bad" and sample.x is None and not events


def test_artifact_cannot_open_a_drop_from_old_window_values():
    eng = FocusEngine(Settings(), stored_baseline=(0.0, 0.1))
    eng._zwin.extend([-3.0] * 15)
    eng.feed_frame(-0.5, 0, False)
    sample, events = eng.tick(20)
    assert sample.artifact and sample.state == "bad" and sample.x is None
    assert not events and not eng.detector.in_drop


def test_diagnostic_phases_do_not_poison_the_focused_baseline():
    engine = FocusEngine(Settings(baseline_seconds=10))
    for second in range(10):
        engine.feed_frame(-5.0, 0, True, extra={"cal_phase": "eyes_closed"})
        engine.tick(second)
    assert not engine.baseline.ready
    for second in range(10, 20):
        engine.feed_frame(-0.3, 0, True, extra={"cal_phase": None})
        engine.tick(second)
    assert engine.baseline.ready
    assert math.isclose(engine.baseline.mu, -0.3)


def test_diagnostic_phases_are_not_automatic_attention_lapses():
    engine = FocusEngine(Settings(), stored_baseline=(0.0, 0.1))
    engine._zwin.extend([-3.0] * 15)
    engine.feed_frame(-0.5, 0, True, extra={"cal_phase": "hard"})
    sample, events = engine.tick(20)
    assert not events
    assert sample.x is None and sample.z is None
    assert sample.state == "baseline"
