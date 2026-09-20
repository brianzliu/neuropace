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
    assert r.lookup(300.0, 250.0) is None
    assert r.lookup(5.0, 0.0) is None
    assert RecapRing().lookup(10.0, 2.0) is None
