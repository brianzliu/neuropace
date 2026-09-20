from __future__ import annotations

import math
import statistics

from ..config import Settings

DURATION_SECONDS = 30
MIN_VALID_SECONDS = 24


def fit_personal_baseline(samples: list[dict], start: float, settings: Settings) -> dict:
    if not math.isfinite(start):
        raise ValueError("Calibration start must be finite")
    seconds = {}
    for sample in samples:
        t = sample.get("t")
        if (
            not isinstance(t, (int, float))
            or not math.isfinite(t)
            or not start <= t < start + DURATION_SECONDS
        ):
            continue
        seconds[math.floor(t - start)] = sample
    clean = {}
    for second, sample in seconds.items():
        x = sample.get("x")
        if (
            sample.get("quality") == "good"
            and sample.get("state") in ("baseline", "ok", "drop")
            and sample.get("artifact") is False
            and sample.get("paused") is False
            and sample.get("sim") is False
            and (sample.get("mw") or {}).get("cal_phase") is None
            and isinstance(x, (int, float))
            and math.isfinite(x)
        ):
            clean[second] = float(x)
    if len(clean) < MIN_VALID_SECONDS:
        raise ValueError(f"Need at least {MIN_VALID_SECONDS} clean seconds out of 30; received {len(clean)}")
    positions = [-1, *sorted(clean), DURATION_SECONDS]
    max_missing = max(right - left - 1 for left, right in zip(positions, positions[1:], strict=False))
    if max_missing > 2:
        raise ValueError("Calibration contains a signal gap longer than two seconds")
    values = list(clean.values())
    mu = statistics.mean(values)
    sigma = max(statistics.stdev(values), settings.sigma_floor)
    return {
        "mu": mu,
        "sigma": sigma,
        "valid_seconds": len(values),
        "duration_seconds": DURATION_SECONDS,
        "coverage": len(values) / DURATION_SECONDS,
        "entry_log_engagement": mu + settings.drop_enter_z * sigma,
        "exit_log_engagement": mu + settings.drop_exit_z * sigma,
        "drop_enter_z": settings.drop_enter_z,
        "drop_exit_z": settings.drop_exit_z,
        "ema_tau_seconds": settings.ema_tau_seconds,
        "window_seconds": settings.window_seconds,
        "source": "real_headset_focused_window",
    }
