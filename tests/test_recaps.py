from neuropace.core.recaps import Recap, RecapRing


def _ring():
    r = RecapRing()
    # recaps every 20 s over 30 s windows, ending at 40, 60, 80, 100
    for end in (40.0, 60.0, 80.0, 100.0):
        r.add(Recap(end - 30.0, end, {"plain": f"recap ending {end:.0f}"}, "llm"))
    return r


def test_short_span_gets_the_latest_recap_that_reaches_it():
    r = _ring()
    assert r.lookup(101.0, 93.0).t_to == 100.0
    assert r.lookup(85.0, 77.0).t_to == 80.0, "a recap that ends after the tap (+2 s slack) is not used"


def test_long_span_prefers_the_recap_with_most_coverage_later_on_ties():
    r = _ring()
    # lapse from 45 to 101: recaps ending 60 (cover 15 s), 80 (30 s) and 100 (30 s) -> the later of the ties
    assert r.lookup(101.0, 45.0).t_to == 100.0
    # lapse from 35 to 62: ending 60 covers 27 s, ending 40 covers 5 s -> 60
    assert r.lookup(62.0, 35.0).t_to == 60.0


def test_no_overlap_or_future_recaps_require_current_transcript():
    r = _ring()
    assert r.lookup(300.0, 250.0) is None, (
        "a recap from minutes ago would mislead: verbatim transcript instead"
    )
    assert r.lookup(5.0, 0.0) is None
    assert RecapRing().lookup(10.0, 2.0) is None


def test_a_tap_between_two_recap_cycles_still_gets_the_latest_recap():
    """TDD §6: no overlap -> the latest recap. The last recap ended at 100; a tap at 115 whose span starts at
    107 reaches nothing, but the point being made at 100 is what the student lost the thread of."""
    r = _ring()
    assert r.lookup(115.0, 107.0).t_to == 100.0
    assert r.lookup(130.0, 122.0).t_to == 100.0, "22 s stale: still within one recap cycle plus slack"
    assert r.lookup(140.0, 132.0) is None, "32 s stale: the verbatim transcript is more honest"
    r.stale_seconds = 40.0
    assert r.lookup(140.0, 132.0).t_to == 100.0, "the scheduler sets the staleness to its own period"
