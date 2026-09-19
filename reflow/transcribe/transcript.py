"""Transcript store on lecture time (TDD §5, §6): words, sentence boundaries, text between times."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_END = re.compile(r"[.!?]['\")\]]*$")


@dataclass(slots=True)
class Word:
    w: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return asdict(self)


class Transcript:
    def __init__(self) -> None:
        self.words: list[Word] = []
        self.interim: list[Word] = []

    # ---- writes ----
    def append(self, words: list[Word]) -> list[Word]:
        """Append final words; drops anything that would go backwards in time."""
        added = []
        last_end = self.words[-1].end if self.words else -1.0
        for w in words:
            if not w.w:
                continue
            if w.end < last_end - 0.05:
                continue
            self.words.append(w)
            last_end = max(last_end, w.end)
            added.append(w)
        self.interim = []
        return added

    def set_interim(self, words: list[Word]) -> None:
        self.interim = list(words)

    # ---- reads ----
    def __len__(self) -> int:
        return len(self.words)

    @property
    def end_time(self) -> float:
        return self.words[-1].end if self.words else 0.0

    def between(self, t0: float, t1: float) -> list[Word]:
        return [w for w in self.words if w.end > t0 and w.start < t1]

    def text_between(self, t0: float, t1: float) -> str:
        return " ".join(w.w for w in self.between(t0, t1))

    def last_words(self, n: int, before: float | None = None) -> list[Word]:
        ws = self.words if before is None else [w for w in self.words if w.end <= before + 1e-6]
        return ws[-n:]

    def sentence_starts(self) -> list[float]:
        """Start times of words that begin a sentence (first word, or after a terminal punctuation)."""
        starts: list[float] = []
        prev_terminal = True
        for w in self.words:
            if prev_terminal:
                starts.append(w.start)
            prev_terminal = bool(_END.search(w.w))
        return starts

    def sentence_end_after(self, t: float) -> float | None:
        """End time of the sentence in progress at t, if that sentence has already been closed."""
        for w in self.words:
            if w.end >= t and _END.search(w.w):
                return w.end
        return None

    def to_dicts(self) -> list[dict]:
        return [w.to_dict() for w in self.words]
