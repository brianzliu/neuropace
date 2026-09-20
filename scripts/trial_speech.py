from __future__ import annotations

import contextlib
import os
import tempfile
import time
import wave
from pathlib import Path

import httpx

VOICE = "JBFqnCBsd6RMkjVDRZzb"
MODEL = "eleven_flash_v2_5"
SPEED = 1.0


class SpeechUnavailable(RuntimeError):
    pass


def speech_identity() -> str:
    return f"elevenlabs:{MODEL}:{VOICE}:pcm_16000:{SPEED}"


def synthesize_trial_speech(text: str, destination: Path, client: httpx.Client | None = None) -> dict:
    if destination.exists():
        with wave.open(str(destination), "rb") as audio:
            if audio.getnframes() and audio.getframerate() == 16000:
                return {"provider": "elevenlabs", "source": "cache"}
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SpeechUnavailable("ELEVENLABS_API_KEY is required to generate uncached speech")
    if not text.strip() or len(text) > 10000:
        raise SpeechUnavailable("Speech text must contain 1 to 10000 characters")
    started, first_byte = time.monotonic(), None
    chunks = []
    manager = contextlib.nullcontext(client) if client else httpx.Client(timeout=90)
    try:
        with manager as http:
            with http.stream(
                "POST",
                f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/stream",
                params={"output_format": "pcm_16000"},
                headers={"xi-api-key": key},
                json={
                    "text": text,
                    "model_id": MODEL,
                    "voice_settings": {
                        "stability": 0.45,
                        "similarity_boost": 0.75,
                        "style": 0,
                        "use_speaker_boost": False,
                        "speed": SPEED,
                    },
                },
            ) as response:
                if response.status_code != 200:
                    raise SpeechUnavailable(f"ElevenLabs speech returned HTTP {response.status_code}")
                for chunk in response.iter_bytes():
                    if chunk:
                        if first_byte is None:
                            first_byte = time.monotonic() - started
                        chunks.append(chunk)
    except httpx.HTTPError as error:
        raise SpeechUnavailable(f"ElevenLabs speech request failed ({type(error).__name__})") from None
    pcm = b"".join(chunks)
    if not pcm or len(pcm) % 2:
        raise SpeechUnavailable("ElevenLabs returned empty or incomplete PCM audio")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".wav", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(pcm)
        path.replace(destination)
    finally:
        path.unlink(missing_ok=True)
    return {
        "provider": "elevenlabs",
        "source": "api",
        "model": MODEL,
        "first_byte_s": round(first_byte, 3),
        "total_s": round(time.monotonic() - started, 3),
        "audio_seconds": round(len(pcm) / 32000, 3),
    }
