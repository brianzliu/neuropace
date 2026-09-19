"""Rolling recaps (TDD §6): every 20 s summarize the last 30 s in four forms; catch-ups look them up with no network."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass

from ..config import Settings
from ..llm.client import LLMClient
from ..transcribe.transcript import Transcript

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Recap:
    t_from: float
    t_to: float
    forms: dict[str, str]
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


class RecapRing:
    def __init__(self, maxlen: int = 30) -> None:
        self._items: deque[Recap] = deque(maxlen=maxlen)

    def add(self, r: Recap) -> None:
        self._items.append(r)

    def __len__(self) -> int:
        return len(self._items)

    def latest(self) -> Recap | None:
        return self._items[-1] if self._items else None

    def lookup(self, t: float, span_start: float) -> Recap | None:
        """Latest recap ending at or before t (+2 s slack) that still reaches back to the span; else the latest."""
        cands = [r for r in self._items if r.t_to <= t + 2.0 and r.t_to >= span_start - 5.0]
        if cands:
            return max(cands, key=lambda r: r.t_to)
        return self.latest()

    def all(self) -> list[dict]:
        return [r.to_dict() for r in self._items]


class RecapScheduler:
    def __init__(
        self,
        s: Settings,
        llm: LLMClient,
        transcript: Transcript,
        ring: RecapRing,
        on_recap: Callable[[Recap], None],
        keyterms: list[str] | None = None,
    ) -> None:
        self.s = s
        self.llm = llm
        self.tr = transcript
        self.ring = ring
        self.on_recap = on_recap
        self.keyterms = keyterms or []
        self.last_t: float | None = None
        self._task: asyncio.Task | None = None
        self.runs = 0
        self.skipped = 0

    def due(self, t: float) -> bool:
        return self.last_t is None or (t - self.last_t) >= self.s.recap_period_seconds

    def maybe_run(self, t: float) -> bool:
        """Call once per tick. Starts a recap task if due and none is in flight. Returns True if started."""
        if not self.due(t):
            return False
        if self._task is not None and not self._task.done():
            return False
        words = self.tr.between(t - self.s.recap_window_seconds, t)
        if len(words) < self.s.recap_min_words:
            self.skipped += 1
            self.last_t = t - self.s.recap_period_seconds / 2  # try again soon
            return False
        self.last_t = t
        t_from, t_to = words[0].start, words[-1].end
        text = " ".join(w.w for w in words)
        self._task = asyncio.create_task(self._run(t_from, t_to, text), name=f"recap@{t:.0f}")
        return True

    async def _run(self, t_from: float, t_to: float, text: str) -> None:
        try:
            forms, source = await self.llm.recap(text, self.tr.text_between(0, t_to), self.keyterms)
            r = Recap(round(t_from, 3), round(t_to, 3), forms.model_dump(), source)
            self.ring.add(r)
            self.runs += 1
            self.on_recap(r)
        except Exception as e:  # noqa: BLE001
            log.warning("recap failed: %s", e)

    async def flush(self) -> None:
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=self.s.recap_timeout_seconds + 1)
            except Exception:  # noqa: BLE001
                pass
