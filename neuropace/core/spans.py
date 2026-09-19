"""Trigger time -> span, and flags -> gaps (TDD §6, FR-N1)."""

from __future__ import annotations

from ..config import Settings
from ..transcribe.transcript import Transcript


def snap_start(tr: Transcript, t_start: float, t_trigger: float, max_back: float) -> float:
    """Nearest earlier sentence start within max_back of the trigger, else t_start."""
    lo = t_trigger - max_back
    cands = [s for s in tr.sentence_starts() if lo <= s <= t_start + 0.25]
    return max(cands) if cands else max(0.0, t_start)


def snap_end(tr: Transcript, t_end: float, max_extend: float) -> float:
    e = tr.sentence_end_after(t_end)
    if e is not None and e <= t_end + max_extend:
        return e
    return t_end


def tap_span(tr: Transcript, t_tap: float, s: Settings) -> tuple[float, float]:
    t_start = snap_start(tr, t_tap - s.lead_in_seconds, t_tap, s.tap_snap_back_max)
    t_end = snap_end(tr, t_tap, s.tap_end_extend_max)
    return max(0.0, t_start), max(t_end, t_start + 1.0)


def eeg_span(tr: Transcript, t_enter: float, t_exit: float | None, s: Settings) -> tuple[float, float | None]:
    t_start = snap_start(tr, t_enter - s.lead_in_seconds, t_enter, s.tap_snap_back_max)
    if t_exit is None:
        return max(0.0, t_start), None
    t_end = min(t_exit, t_enter + s.eeg_flag_max_seconds)
    t_end = snap_end(tr, t_end, s.tap_end_extend_max)
    return max(0.0, t_start), max(t_end, t_start + 1.0)


def merge_into_gaps(flags: list[dict], s: Settings, lecture_end: float | None = None) -> list[dict]:
    """Merge overlapping/adjacent flagged spans into gaps with min/max lengths. Flags need t_start, t_end, id."""
    spans = []
    for f in flags:
        if f.get("t_start") is None:
            continue
        t0 = float(f["t_start"])
        t1 = float(f["t_end"]) if f.get("t_end") is not None else t0 + s.lead_in_seconds
        spans.append([max(0.0, t0), max(t1, t0 + 1.0), [f["id"]]])
    spans.sort(key=lambda x: x[0])
    merged: list[list] = []
    for sp in spans:
        if merged and sp[0] <= merged[-1][1] + s.gap_merge_gap_seconds:
            merged[-1][1] = max(merged[-1][1], sp[1])
            merged[-1][2].extend(sp[2])
        else:
            merged.append(sp)
    out = []
    for t0, t1, ids in merged:
        if t1 - t0 < s.gap_min_seconds:
            t0 = max(0.0, t1 - s.gap_min_seconds)
        if t1 - t0 > s.gap_max_seconds:
            t1 = t0 + s.gap_max_seconds
        if lecture_end is not None:
            t1 = min(t1, lecture_end)
            if t1 - t0 < 1.0:
                continue
        out.append({"t_start": round(t0, 3), "t_end": round(t1, 3), "flag_ids": ids})
    return out
