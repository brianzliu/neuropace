"""Pooled lecture loss map (TDD §8.4). Pure function over per-session signals."""

from __future__ import annotations

import math

from ..config import Settings


def session_bins(
    samples: list[dict], taps: list[float], eeg_flags: list[tuple[float, float]], n_bins: int, bin_s: float
) -> list[float | None]:
    zsum = [0.0] * n_bins
    zcnt = [0] * n_bins
    for smp in samples:
        z = smp.get("z")
        if z is None or smp.get("paused") or smp.get("artifact") or smp.get("quality") == "bad":
            continue
        b = int(smp["t"] // bin_s)
        if 0 <= b < n_bins:
            zsum[b] += float(z)
            zcnt[b] += 1
    tap_b = [0] * n_bins
    for t in taps:
        b = int(t // bin_s)
        if 0 <= b < n_bins:
            tap_b[b] = 1
    eeg_b = [0] * n_bins
    for t0, t1 in eeg_flags:
        b0, b1 = int(max(0.0, t0) // bin_s), int(max(0.0, t1) // bin_s)
        for b in range(max(0, b0), min(n_bins - 1, b1) + 1):
            eeg_b[b] = 1
    out: list[float | None] = []
    for b in range(n_bins):
        if zcnt[b] > 0:
            z = zsum[b] / zcnt[b]
            out.append(-z + 1.0 * tap_b[b] + 0.5 * eeg_b[b])
        elif tap_b[b]:
            out.append(1.0 * tap_b[b] + 0.5 * eeg_b[b])
        else:
            out.append(None)
    return out


def compute_lossmap(
    sessions: list[dict], lecture_length: float, segments: list[dict] | None, s: Settings
) -> dict:
    """sessions: [{id, samples: [focus dicts], taps: [t], eeg_flags: [(t0, t1)]}]"""
    bin_s = s.lossmap_bin_seconds
    n_bins = max(1, int(math.ceil(max(lecture_length, 1.0) / bin_s)))
    n = len(sessions)
    if n < 2:
        return {
            "ready": False,
            "n": n,
            "reason": "needs 2 or more learners",
            "bin_seconds": bin_s,
            "n_bins": n_bins,
        }
    per = [session_bins(x["samples"], x["taps"], x["eeg_flags"], n_bins, bin_s) for x in sessions]
    pooled: list[float | None] = []
    counts: list[int] = []
    for b in range(n_bins):
        vals = [p[b] for p in per if p[b] is not None]
        counts.append(len(vals))
        pooled.append(sum(vals) / len(vals) if vals else None)
    w = s.lossmap_window_bins
    best_i, best_v = 0, -math.inf
    for i in range(0, max(1, n_bins - w + 1)):
        vals = [v for v in pooled[i : i + w] if v is not None]
        if not vals:
            continue
        v = sum(vals) / len(vals) * (len(vals) / w)
        if v > best_v:
            best_i, best_v = i, v
    peak = {
        "t_start": best_i * bin_s,
        "t_end": min(lecture_length, (best_i + w) * bin_s),
        "score": (round(best_v, 3) if best_v > -math.inf else None),
    }
    seg_out = []
    for i, seg in enumerate(segments or []):
        b0, b1 = int(seg["t_start"] // bin_s), int(max(seg["t_start"], seg["t_end"] - 1e-6) // bin_s)
        vals = [pooled[b] for b in range(max(0, b0), min(n_bins - 1, b1) + 1) if pooled[b] is not None]
        seg_out.append(
            {
                "index": i,
                "id": seg.get("id", f"seg{i + 1}"),
                "title": seg.get("title", f"Segment {i + 1}"),
                "t_start": seg["t_start"],
                "t_end": seg["t_end"],
                "score": (round(sum(vals) / len(vals), 3) if vals else None),
            }
        )
    ranked = sorted([x for x in seg_out if x["score"] is not None], key=lambda x: -x["score"])
    for r_i, x in enumerate(ranked):
        x["rank"] = r_i + 1
    return {
        "ready": True,
        "n": n,
        "bin_seconds": bin_s,
        "n_bins": n_bins,
        "bins": [
            {"t": b * bin_s, "loss": (round(v, 3) if v is not None else None), "n": counts[b]}
            for b, v in enumerate(pooled)
        ],
        "peak": peak,
        "segments": seg_out,
        "ranking": [x["id"] for x in ranked],
    }
