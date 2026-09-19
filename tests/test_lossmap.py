from reflow.config import Settings
from reflow.core.lossmap import compute_lossmap


def _session(sid: str, length: float, drop_at: tuple[float, float] | None, taps=(), eeg=(), paused=()):
    samples = []
    for t in range(int(length)):
        z = -2.5 if drop_at and drop_at[0] <= t < drop_at[1] else 0.0
        samples.append({"t": float(t), "z": z, "paused": t in paused, "artifact": False, "quality": "good"})
    return {"id": sid, "samples": samples, "taps": list(taps), "eeg_flags": list(eeg)}


def test_needs_two_learners():
    s = Settings()
    out = compute_lossmap([_session("a", 100, (40, 60))], 100, [], s)
    assert out["ready"] is False and out["n"] == 1


def test_pooled_peak_finds_planted_drop_and_ranks_segment():
    s = Settings()
    segs = [
        {"id": "seg1", "title": "a", "t_start": 0, "t_end": 60},
        {"id": "seg2", "title": "b", "t_start": 60, "t_end": 120, "planted_bad": True},
        {"id": "seg3", "title": "c", "t_start": 120, "t_end": 180},
    ]
    sessions = [
        _session("a", 180, (70, 110)),
        _session("b", 180, (75, 105), taps=(90.0,)),
        _session("c", 180, None),
    ]
    out = compute_lossmap(sessions, 180, segs, s)
    assert out["ready"] and out["n"] == 3
    assert 60 <= out["peak"]["t_start"] <= 80 and out["peak"]["t_end"] - out["peak"]["t_start"] == 40
    assert out["ranking"][0] == "seg2"
    b9 = next(b for b in out["bins"] if b["t"] == 90.0)
    assert b9["n"] == 3 and b9["loss"] > 1.0


def test_tap_counts_even_without_focus_and_paused_is_excluded():
    s = Settings()
    a = {"id": "a", "samples": [], "taps": [15.0], "eeg_flags": []}
    b = _session("b", 60, (10, 20), paused=range(10, 20))
    out = compute_lossmap([a, b], 60, [], s)
    b1 = next(x for x in out["bins"] if x["t"] == 10.0)
    assert b1["n"] == 1 and b1["loss"] == 1.0  # only the tap counts: b's samples in that bin are paused
