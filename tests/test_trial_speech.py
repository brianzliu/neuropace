import wave

import httpx
import pytest

from scripts.trial_speech import SpeechUnavailable, synthesize_trial_speech


def test_elevenlabs_uses_flash_and_writes_playable_pcm_wave(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-credential")
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["xi-api-key"] == "test-credential"
        assert request.url.params["output_format"] == "pcm_16000"
        assert b"eleven_flash_v2_5" in request.content
        return httpx.Response(200, content=b"\x01\x00" * 16000)

    destination = tmp_path / "cue.wav"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = synthesize_trial_speech("Look at the dot.", destination, client)
    assert len(seen) == 1
    assert result["provider"] == "elevenlabs"
    with wave.open(str(destination), "rb") as audio:
        assert audio.getframerate() == 16000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getnframes() == 16000


def test_api_error_does_not_expose_credentials_or_provider_body(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-credential")
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(401, text="test-credential"))
    ) as client:
        with pytest.raises(SpeechUnavailable, match="401") as error:
            synthesize_trial_speech("Hello", tmp_path / "cue.wav", client)
    assert "test-credential" not in str(error.value)
    assert not (tmp_path / "cue.wav").exists()


def test_no_key_fails_without_a_request(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(SpeechUnavailable, match="ELEVENLABS_API_KEY"):
        synthesize_trial_speech("Hello", tmp_path / "cue.wav")


def test_complete_cached_audio_does_not_need_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    destination = tmp_path / "cue.wav"
    with wave.open(str(destination), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x01\x00" * 160)
    result = synthesize_trial_speech("Hello", destination)
    assert result["source"] == "cache"


def test_empty_audio_is_not_cached_as_a_success(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-credential")
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b""))
    ) as client:
        with pytest.raises(SpeechUnavailable, match="audio"):
            synthesize_trial_speech("Hello", tmp_path / "cue.wav", client)
    assert not (tmp_path / "cue.wav").exists()
