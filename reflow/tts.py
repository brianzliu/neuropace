"""The tutor voice (docs/PRODUCT.md §5): Deepgram Aura text to speech, one short beat per call, cached on disk.

Sentence-level beats need no word timestamps: the frontend highlights the beat being played and advances the
template in step with it. No key, or a failed call, means no voice: the screen stays readable, nothing is invented.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from .config import Settings

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
MAX_CHARS = 1500


class TTSUnavailable(RuntimeError):
    pass


def cache_path(s: Settings, text: str) -> Path:
    key = hashlib.sha256(f"{s.tts_model}|{text}".encode()).hexdigest()
    return s.data_dir / "cache" / "tts" / f"{key}.mp3"


async def synthesize(s: Settings, text: str, client: httpx.AsyncClient | None = None) -> bytes:
    """MP3 bytes for `text`. Raises TTSUnavailable without a key or when Deepgram fails."""
    text = " ".join(text.split())[:MAX_CHARS]
    if not text:
        raise TTSUnavailable("nothing to say")
    if not s.deepgram_api_key:
        raise TTSUnavailable("no DEEPGRAM_API_KEY")
    path = cache_path(s, text)
    if path.exists():
        return path.read_bytes()
    own = client is None
    client = client or httpx.AsyncClient(timeout=20.0)
    try:
        r = await client.post(
            DEEPGRAM_SPEAK_URL,
            params={"model": s.tts_model, "encoding": "mp3"},
            headers={"Authorization": f"Token {s.deepgram_api_key}", "Content-Type": "application/json"},
            json={"text": text},
        )
    except httpx.HTTPError as e:
        raise TTSUnavailable(f"Deepgram speak failed: {e}") from e
    finally:
        if own:
            await client.aclose()
    if r.status_code != 200 or not r.content:
        raise TTSUnavailable(f"Deepgram speak returned {r.status_code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return r.content
