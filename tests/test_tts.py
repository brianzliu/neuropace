"""The tutor voice: Deepgram Aura through one endpoint, cached per beat, honest when unavailable."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from neuropace.config import Settings
from neuropace.tts import TTSUnavailable, cache_path, synthesize


class FakeSpeak:
    def __init__(self, status=200, body=b"ID3fakemp3"):
        self.calls = []
        self.status = status
        self.body = body

    async def post(self, url, **kw):
        self.calls.append((url, kw))
        return httpx.Response(self.status, content=self.body, request=httpx.Request("POST", url))


def test_synthesize_caches_and_sends_the_beat(tmp_path):
    s = Settings(data_dir=tmp_path, deepgram_api_key="k")
    fake = FakeSpeak()
    audio = asyncio.run(synthesize(s, "  Every satellite   broadcasts the time. ", client=fake))
    assert audio == b"ID3fakemp3" and len(fake.calls) == 1
    url, kw = fake.calls[0]
    assert kw["params"]["model"] == s.tts_model and kw["json"] == {
        "text": "Every satellite broadcasts the time."
    }
    assert kw["headers"]["Authorization"] == "Token k"
    assert cache_path(s, "Every satellite broadcasts the time.").exists()
    again = asyncio.run(synthesize(s, "Every satellite broadcasts the time.", client=fake))
    assert again == audio and len(fake.calls) == 1, "second beat served from the cache"


def test_synthesize_is_unavailable_without_a_key_or_on_failure(tmp_path):
    with pytest.raises(TTSUnavailable, match="DEEPGRAM"):
        asyncio.run(synthesize(Settings(data_dir=tmp_path, deepgram_api_key=None), "hi"))
    s = Settings(data_dir=tmp_path, deepgram_api_key="k")
    with pytest.raises(TTSUnavailable, match="402"):
        asyncio.run(synthesize(s, "hi", client=FakeSpeak(status=402)))
    with pytest.raises(TTSUnavailable, match="nothing"):
        asyncio.run(synthesize(s, "   ", client=FakeSpeak()))


def test_flux_uses_separate_key_endpoint_and_expressivity(tmp_path):
    s = Settings(data_dir=tmp_path, deepgram_api_key="stt", deepgram_tts_api_key="tts")
    fake = FakeSpeak()
    asyncio.run(synthesize(s, "Focus on one idea at a time.", client=fake))
    url, kw = fake.calls[0]
    assert url == "https://api.deepgram.com/v2/speak"
    assert kw["headers"]["Authorization"] == "Token tts"
    assert kw["params"] == {"model": "flux-cole-en", "encoding": "mp3", "expressivity": "2"}
    animated = cache_path(s, "hello")
    s.tts_expressivity = 0
    assert cache_path(s, "hello") != animated
    s.tts_model = "aura-2-thalia-en"
    asyncio.run(synthesize(s, "Aura compatibility.", client=fake))
    assert fake.calls[-1][0] == "https://api.deepgram.com/v1/speak"
    assert "expressivity" not in fake.calls[-1][1]["params"]


def test_tts_endpoint_returns_503_without_a_key(app):
    with TestClient(app) as c:
        r = c.post("/api/tts", json={"text": "hello"})
        assert r.status_code == 503 and "DEEPGRAM" in r.json()["detail"]
        assert c.get("/api/doctor").json()["tts"]["ok"] is False
