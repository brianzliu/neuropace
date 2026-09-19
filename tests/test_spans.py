from reflow.config import Settings
from reflow.core.spans import eeg_span, merge_into_gaps, snap_end, tap_span
from reflow.transcribe.scripted import script_from_text
from reflow.transcribe.transcript import Transcript

TEXT = "Radio travels at the speed of light. Multiply the delay by the speed of light and you get the distance. One distance puts you on a sphere. Three spheres give two points."


def _tr() -> Transcript:
    tr = Transcript()
    tr.append(script_from_text(TEXT, 150))
    return tr


def test_tap_span_has_lead_in_and_snaps_to_sentence_start():
    s = Settings()
    tr = _tr()
    starts = tr.sentence_starts()
    t0, t1 = tap_span(tr, 12.0, s)
    assert t0 in starts and t0 <= 12.0 - 8.0 + 0.25
    assert t1 >= 12.0


def test_snap_start_respects_max_back():
    s = Settings(tap_snap_back_max=3.0)
    tr = _tr()
    t0, _ = tap_span(tr, 12.0, s)
    assert t0 == 4.0  # no sentence start within 3 s of the trigger before t-8, so plain lead-in


def test_snap_end_extends_only_within_cap():
    tr = _tr()
    e = tr.sentence_end_after(1.0)
    assert e is not None
    assert snap_end(tr, 1.0, max_extend=100.0) == e
    assert snap_end(tr, 1.0, max_extend=0.1) == 1.0


def test_eeg_span_open_and_closed():
    s = Settings()
    tr = _tr()
    t0, t1 = eeg_span(tr, 20.0, None, s)
    assert t1 is None and t0 <= 12.25
    t0, t1 = eeg_span(tr, 20.0, 80.0, s)
    assert t1 <= 20.0 + s.eeg_flag_max_seconds + s.tap_end_extend_max


def test_merge_into_gaps_min_max_and_adjacency():
    s = Settings()
    flags = [
        {"id": "a", "t_start": 3.0, "t_end": 5.0},
        {"id": "b", "t_start": 12.0, "t_end": 16.0},
        {"id": "c", "t_start": 60.0, "t_end": 200.0},
        {"id": "d", "t_start": 300.0, "t_end": None},
    ]
    gaps = merge_into_gaps(flags, s, lecture_end=310.0)
    assert [g["flag_ids"] for g in gaps] == [["a", "b"], ["c"], ["d"]]
    assert gaps[0]["t_end"] - gaps[0]["t_start"] >= s.gap_min_seconds
    assert gaps[1]["t_end"] - gaps[1]["t_start"] == s.gap_max_seconds
    assert gaps[2]["t_end"] <= 310.0 and gaps[2]["t_end"] - gaps[2]["t_start"] >= 1.0


def test_merge_drops_spans_past_lecture_end():
    s = Settings()
    assert merge_into_gaps([{"id": "x", "t_start": 500.0, "t_end": 520.0}], s, lecture_end=100.0) == []
