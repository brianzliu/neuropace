import math

import numpy as np
import pytest

from neuropace.config import Settings
from neuropace.signal.personal_calibration import fit_personal_baseline


def clean_samples():
    return [
        {
            "t": 10.5 + second,
            "x": -0.3 + 0.03 * math.sin(second),
            "quality": "good",
            "state": "baseline",
            "artifact": False,
            "paused": False,
            "sim": False,
            "mw": {"cal_phase": None},
        }
        for second in range(30)
    ]


def test_personal_baseline_uses_the_full_focused_window_and_keeps_the_detector_thresholds():
    samples = clean_samples()
    settings = Settings()
    result = fit_personal_baseline(samples, 10, settings)
    assert result["valid_seconds"] == 30
    assert result["mu"] == pytest.approx(np.mean([sample["x"] for sample in samples]))
    assert result["sigma"] == settings.sigma_floor
    assert result["entry_log_effort"] == pytest.approx(result["mu"] - 1.25 * result["sigma"])
    assert result["exit_log_effort"] == pytest.approx(result["mu"] - 0.6 * result["sigma"])
    assert result["duration_seconds"] == 30


@pytest.mark.parametrize(
    "field,value",
    [
        ("quality", "bad"),
        ("artifact", True),
        ("paused", True),
        ("sim", True),
        ("x", None),
        ("x", math.nan),
        ("x", math.inf),
    ],
)
def test_invalid_inputs_cannot_count_as_clean_calibration(field, value):
    samples = clean_samples()
    for sample in samples[:7]:
        sample[field] = value
    with pytest.raises(ValueError, match="24"):
        fit_personal_baseline(samples, 10, Settings())


def test_duplicate_frames_cannot_manufacture_thirty_seconds():
    with pytest.raises(ValueError, match="24"):
        fit_personal_baseline(clean_samples()[:1] * 100, 10, Settings())


def test_a_sustained_gap_is_rejected_even_when_total_coverage_is_high():
    samples = clean_samples()
    del samples[12:16]
    with pytest.raises(ValueError, match="gap"):
        fit_personal_baseline(samples, 10, Settings())


def test_short_scattered_artifacts_are_excluded_without_rejecting_good_data():
    samples = clean_samples()
    for i in (1, 6, 11, 16, 21, 26):
        samples[i]["artifact"] = True
    result = fit_personal_baseline(samples, 10, Settings())
    assert result["valid_seconds"] == 24
    assert result["coverage"] == 0.8


def test_scattered_missing_data_still_requires_eighty_percent_coverage():
    samples = clean_samples()
    for i in (1, 5, 9, 13, 17, 21, 25):
        samples[i]["artifact"] = True
    with pytest.raises(ValueError, match="24"):
        fit_personal_baseline(samples, 10, Settings())


def test_signal_diagnostic_phases_are_not_a_focused_baseline():
    samples = clean_samples()
    for sample in samples:
        sample["mw"]["cal_phase"] = "eyes_closed"
    with pytest.raises(ValueError, match="24"):
        fit_personal_baseline(samples, 10, Settings())


def test_samples_outside_the_marked_window_do_not_change_the_fit():
    samples = clean_samples()
    before = {**samples[0], "t": 9.9, "x": 100}
    after = {**samples[-1], "t": 40, "x": 100}
    assert fit_personal_baseline([before, *samples, after], 10, Settings()) == fit_personal_baseline(
        samples, 10, Settings()
    )


def test_noisy_but_valid_data_keeps_its_measured_spread():
    samples = clean_samples()
    for i, sample in enumerate(samples):
        sample["x"] = -0.5 + 0.4 * math.sin(i)
    result = fit_personal_baseline(samples, 10, Settings())
    assert result["sigma"] == pytest.approx(np.std([sample["x"] for sample in samples], ddof=1))
