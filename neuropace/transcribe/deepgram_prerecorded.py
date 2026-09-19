"""Deepgram prerecorded transcription (TDD §5.2): media file in, word list out (cached by the caller)."""

from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from .transcript import Word

DEEPGRAM_REST = "https://api.deepgram.com/v1/listen"


async def transcribe_file(
    path: str | Path, api_key: str, model: str = "nova-3", keyterms: list[str] | None = None
) -> list[Word]:
    p = Path(path)
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    params: list[tuple[str, str]] = [
        ("model", model),
        ("smart_format", "true"),
        ("punctuate", "true"),
        ("language", "en"),
    ]
    for k in keyterms or []:
        params.append(("keyterm", k))
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        r = await client.post(
            DEEPGRAM_REST,
            params=params,
            content=p.read_bytes(),
            headers={"Authorization": f"Token {api_key}", "Content-Type": ctype},
        )
        r.raise_for_status()
        data = r.json()
    alt = data["results"]["channels"][0]["alternatives"][0]
    return [
        Word(w.get("punctuated_word") or w["word"], round(float(w["start"]), 3), round(float(w["end"]), 3))
        for w in alt.get("words", [])
    ]
