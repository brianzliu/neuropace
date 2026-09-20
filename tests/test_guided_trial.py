import math

import pytest

from scripts.guided_eeg_trial import score_trial


def frames(session="test", start=0, seconds=60, quality="good", alpha=1.0):
    return [
        {
            "type": "focus",
            "session_id": session,
            "t": t,
            "quality": quality,
            "state": "ok" if quality == "good" else "bad",
            "artifact": False,
            "paused": False,
            "sim": False,
            "baseline_ready": True,
            "mw": {"engagement": -0.5, "log_alpha": alpha},
            "z": -0.2,
            "w15": -0.2,
        }
        for t in range(start, start + seconds)
    ]


def block(task="drift"):
    return {"phase": "block1", "task": task, "session_id": "test", "t_start": 0, "t_end": 60}


def flag(source="eeg", simulated=False, t=30):
    return {
        "type": "flag_open",
        "session_id": "test",
        "flag": {"id": "f1", "source": source, "simulated": simulated, "t_trigger": t},
    }


def test_real_eeg_trigger_is_scored_against_independent_report():
    result = score_trial(frames() + [flag()], [block()], [{"phase": "block1", "reported": "elsewhere"}])
    assert result["confusion"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 0}
    assert result["blocks"][0]["first_trigger_latency_s"] == 30
    assert result["blocks"][0]["valid_fraction"] == 1


@pytest.mark.parametrize("source,simulated", [("forced", True), ("key", False), ("eeg", True)])
def test_manual_or_simulated_triggers_cannot_pass_the_detector(source, simulated):
    result = score_trial(
        frames() + [flag(source, simulated)], [block()], [{"phase": "block1", "reported": "elsewhere"}]
    )
    assert result["confusion"]["fn"] == 1
    assert result["confusion"]["tp"] == 0


def test_a_cue_is_not_assumed_to_be_the_participants_actual_attention():
    result = score_trial(frames() + [flag()], [block()], [{"phase": "block1", "reported": "lecture"}])
    assert result["confusion"]["fp"] == 1
    assert result["confusion"]["tp"] == 0


@pytest.mark.parametrize("reported", [None, "mixed"])
def test_unreported_or_mixed_blocks_are_not_scored_as_success(reported):
    probes = [] if reported is None else [{"phase": "block1", "reported": reported}]
    result = score_trial(frames(), [block()], probes)
    assert result["scored_blocks"] == 0
    assert result["blocks"][0]["eligible"] is False


def test_missing_or_bad_signal_is_not_a_true_negative():
    result = score_trial(
        frames(quality="bad"), [block("focus")], [{"phase": "block1", "reported": "lecture"}]
    )
    assert result["scored_blocks"] == 0
    assert result["blocks"][0]["valid_fraction"] == 0


def test_duplicate_media_times_do_not_inflate_signal_coverage():
    events = frames(start=20, seconds=1) * 100
    result = score_trial(events, [block()], [{"phase": "block1", "reported": "elsewhere"}])
    assert result["blocks"][0]["valid_seconds"] == 1
    assert result["scored_blocks"] == 0


def test_eyes_closed_alpha_response_uses_valid_windows_and_is_not_attention_accuracy():
    events = frames(start=0, seconds=25, alpha=1) + frames(start=30, seconds=30, alpha=math.log10(40))
    markers = [
        {"phase": "eyes_open_1", "task": "signal", "session_id": "test", "t_start": 0, "t_end": 25},
        {"phase": "eyes_closed", "task": "signal", "session_id": "test", "t_start": 30, "t_end": 60},
    ]
    result = score_trial(events, markers, [])
    assert result["alpha_closed_open_ratio"] == pytest.approx(4)
    assert result["scored_blocks"] == 0


def test_transitions_and_other_sessions_cannot_create_a_detection():
    other = flag(t=35)
    other["session_id"] = "other"
    result = score_trial(
        frames() + [flag(t=5), other], [block()], [{"phase": "block1", "reported": "elsewhere"}]
    )
    assert result["confusion"]["fn"] == 1


def test_simulated_focus_is_excluded_even_when_quality_is_good():
    events = frames()
    for event in events:
        event["sim"] = True
    result = score_trial(events, [block()], [{"phase": "block1", "reported": "lecture"}])
    assert result["scored_blocks"] == 0


def test_paused_or_uncalibrated_frames_cannot_pass_the_trial():
    for field, value in (("paused", True), ("baseline_ready", False)):
        events = frames()
        for event in events:
            event[field] = value
        result = score_trial(events, [block()], [{"phase": "block1", "reported": "lecture"}])
        assert result["scored_blocks"] == 0


def test_controller_hides_answers_and_blocks_foreign_origins(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from scripts import guided_eeg_trial as guided

    monkeypatch.setattr(guided, "ROOT", tmp_path)
    manifest = {
        "title": "fixture",
        "duration": 60,
        "lecture_id": "fixture",
        "sections": [{"id": "screening", "task": "focus", "text": "source", "correct_index": 1}],
    }
    trial = guided.Trial("http://127.0.0.1:1", manifest)
    with TestClient(guided.make_app(trial)) as client:
        public = client.get("/manifest").json()
        assert "correct_index" not in public["sections"][0]
        assert "text" not in public["sections"][0]
        assert client.post("/heartbeat", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
        assert client.get("/audio/unrelated.txt").status_code == 404
        assert client.post("/signal").status_code == 409
        assert client.post("/lesson").status_code == 409
        assert client.post("/submit", json={"answers": {}}).status_code == 409
        assert trial.sessions == []
