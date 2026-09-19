"""Lecture-time clocks (TDD §1). Every event in a session is stamped on lecture_time."""

from __future__ import annotations

import time


class LiveClock:
    """Seconds since the session started, monotonic."""

    def __init__(self, start: float | None = None) -> None:
        self._start = time.monotonic() if start is None else start

    def now(self) -> float:
        return time.monotonic() - self._start

    @property
    def paused(self) -> bool:
        return False


class MediaClock:
    """Driven by the client's media player. Between reports it extrapolates while playing."""

    def __init__(self) -> None:
        self._t = 0.0
        self._playing = False
        self._reported_at = time.monotonic()

    def set(self, t: float, playing: bool) -> None:
        self._t = max(0.0, float(t))
        self._playing = bool(playing)
        self._reported_at = time.monotonic()

    def now(self) -> float:
        if not self._playing:
            return self._t
        return self._t + (time.monotonic() - self._reported_at)

    @property
    def paused(self) -> bool:
        return not self._playing


class ManualClock:
    """For tests: time advances only when told to."""

    def __init__(self, t: float = 0.0) -> None:
        self._t = t
        self.paused = False

    def now(self) -> float:
        return self._t

    def advance(self, dt: float) -> None:
        self._t += dt

    def set(self, t: float) -> None:
        self._t = t
