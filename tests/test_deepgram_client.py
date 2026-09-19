"""Offline tests of the Deepgram streaming client: URL, message parsing, lecture-time offset. No network."""

from reflow.clock import ManualClock
from reflow.transcribe.deepgram_live import DeepgramLive


def _client(clock):
    got = []
    dg = DeepgramLive(
        "key",
        lambda ws, final: got.append((ws, final)),
        clock,
        sample_rate=16000,
        model="nova-3",
        keyterms=["ATP", "clock bias"],
    )
    return dg, got


def test_url_carries_model_encoding_rate_and_keyterms():
    dg, _ = _client(ManualClock(0.0))
    url = dg.url()
    assert url.startswith("wss://api.deepgram.com/v1/listen?")
    for part in (
        "model=nova-3",
        "encoding=linear16",
        "sample_rate=16000",
        "channels=1",
        "interim_results=true",
        "punctuate=true",
        "keyterm=ATP",
        "keyterm=clock+bias",
    ):
        assert part in url


def test_results_are_shifted_by_stream_t0_and_split_final_interim():
    clock = ManualClock(12.0)
    dg, got = _client(clock)
    dg.stream_t0 = 12.0
    msg = {
        "type": "Results",
        "is_final": True,
        "channel": {
            "alternatives": [
                {
                    "transcript": "hello world",
                    "words": [
                        {"word": "hello", "punctuated_word": "Hello", "start": 0.5, "end": 0.9},
                        {"word": "world", "punctuated_word": "world.", "start": 1.0, "end": 1.4},
                    ],
                }
            ]
        },
    }
    dg._handle(msg)
    assert got and got[0][1] is True
    ws = got[0][0]
    assert [w.w for w in ws] == ["Hello", "world."] and ws[0].start == 12.5 and ws[1].end == 13.4
    dg._handle({**msg, "is_final": False})
    assert got[1][1] is False and dg.words_received == 2


def test_non_result_messages_are_ignored_and_errors_recorded():
    dg, got = _client(ManualClock(0.0))
    dg._handle({"type": "Metadata", "request_id": "x"})
    dg._handle({"type": "UtteranceEnd"})
    dg._handle({"type": "Results", "channel": {"alternatives": []}})
    assert got == []
    dg._handle({"type": "Error", "description": "bad"})
    assert dg.error and "bad" in dg.error
