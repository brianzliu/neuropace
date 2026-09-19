"""Keyboard control shared by run_pipeline.py (console) and monitor.py (plot window)."""
from __future__ import annotations

KEY_HELP = ("keys: 1 eyes_closed  2 easy  3 hard  0 done  r reset  a auto-calibrate (10/25/25 s)\n"
            "      fake source only: c closed  e easy  h hard  d drowsy  o off-head  b blink")
CAL_KEYS = {"1": "eyes_closed", "2": "easy", "3": "hard", "0": "done", "r": "reset"}
FAKE_KEYS = {"c": "eyes_closed", "e": "easy", "h": "hard", "d": "drowsy", "o": "off"}


def apply_key(key: str, pipe, source) -> str | None:
    """Apply a key; returns a one-line description, or None if the key is unbound."""
    from .sources import FakeSource

    if key in CAL_KEYS:
        pipe.calibrate(CAL_KEYS[key])
        return f"calibrate {CAL_KEYS[key]}"
    if key == "a":
        pipe.auto_calibrate()
        return "auto-calibrate started"
    if isinstance(source, FakeSource):
        if key in FAKE_KEYS:
            source.set_state(FAKE_KEYS[key])
            return f"fake state -> {FAKE_KEYS[key]}"
        if key == "b":
            source.blink()
            return "fake blink"
    return None
