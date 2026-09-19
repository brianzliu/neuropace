"""Scripted transcript source (TDD §5.3): replays a word-timed script in lecture time, no network needed."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from .transcript import Word

WordsCallback = Callable[[list[Word], bool], None]


def script_from_text(text: str, wpm: float = 150.0, start: float = 0.0) -> list[Word]:
    """Turn plain prose into evenly timed words (about `wpm`), pausing a little at sentence ends."""
    toks = [t for t in re.split(r"\s+", text.strip()) if t]
    per = 60.0 / wpm
    t = start
    out: list[Word] = []
    for tok in toks:
        dur = per * (0.8 + min(len(tok), 12) / 12 * 0.6)
        out.append(Word(tok, round(t, 3), round(t + dur, 3)))
        t += dur + (0.35 if re.search(r"[.!?]$", tok) else 0.0)
    return out


def load_script(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    if "words" not in data and "text" in data:
        data["words"] = [w.to_dict() for w in script_from_text(data["text"], data.get("wpm", 150.0))]
    return data


class ScriptedTranscript:
    kind = "scripted"

    def __init__(self, words: list[Word], on_words: WordsCallback, clock, chunk_seconds: float = 0.5) -> None:
        self.words = sorted(words, key=lambda w: w.start)
        self.on_words = on_words
        self.clock = clock
        self.chunk = chunk_seconds
        self._task: asyncio.Task | None = None
        self._i = 0

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="scripted-transcript")

    async def _run(self) -> None:
        try:
            while self._i < len(self.words):
                now = self.clock.now()
                batch: list[Word] = []
                while self._i < len(self.words) and self.words[self._i].end <= now:
                    batch.append(self.words[self._i])
                    self._i += 1
                if batch:
                    self.on_words(batch, True)
                await asyncio.sleep(self.chunk)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
