"""Rolling recaps (TDD §6): every 20 s summarize the last 30 s in four forms; catch-ups look them up with no network."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass

from ..config import Settings
from ..llm.client import LLMClient, LLMUnavailable
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
    # A recap that ended this long before the missed span began still describes the point being made when the
    # student drifted (TDD §6: "no overlap -> the latest recap"); anything older would mislead, so the catch-up
    # falls back to the verbatim transcript instead. The scheduler sets it to one recap period plus slack.
    STALE_SECONDS_DEFAULT = 25.0

    def __init__(self, maxlen: int = 30, stale_seconds: float = STALE_SECONDS_DEFAULT) -> None:
        self._items: deque[Recap] = deque(maxlen=maxlen)
        self.stale_seconds = stale_seconds

    def add(self, r: Recap) -> None:
        self._items.append(r)

    def __len__(self) -> int:
        return len(self._items)

    def latest(self) -> Recap | None:
        return self._items[-1] if self._items else None

    def lookup(self, t: float, span_start: float) -> Recap | None:
        """The recap that covers the missed span [span_start, t] best: largest overlap, later one on ties
        (for a span shorter than one window this is simply the latest recap that reaches into it). When no recap
        reaches into the span yet (a tap between two recap cycles), the latest one is used as long as it ended
        within `stale_seconds` of the span start; older than that, or an empty ring, returns None and the
        catch-up shows the verbatim transcript."""
        cands = [r for r in self._items if r.t_to <= t + 2.0]
        if not cands:
            return None
        best, best_key = None, None
        for r in cands:
            overlap = max(0.0, min(r.t_to, t) - max(r.t_from, span_start))
            key = (round(overlap, 3), r.t_to)
            if best_key is None or key > best_key:
                best, best_key = r, key
        if best is not None and best_key is not None and best_key[0] > 0:
            return best
        latest = max(cands, key=lambda r: r.t_to)
        if span_start - latest.t_to <= self.stale_seconds:
            return latest
        return None

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
        ring.stale_seconds = s.recap_period_seconds + 5.0  # one cycle plus model latency
        self.on_recap = on_recap
        self.keyterms = keyterms or []
        self.last_t: float | None = None
        self._task: asyncio.Task | None = None
        self.runs = 0
        self.skipped = 0
        self.unavailable_reason: str | None = None
        self.on_unavailable: Callable[[str], None] | None = None

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
        except LLMUnavailable as e:
            first = self.unavailable_reason is None
            self.unavailable_reason = str(e)
            if first and self.on_unavailable is not None:
                self.on_unavailable(str(e))
            log.warning("recap unavailable: %s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("recap failed: %s", e)

    async def flush(self) -> None:
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=self.s.recap_timeout_seconds + 1)
            except Exception:  # noqa: BLE001
                pass
