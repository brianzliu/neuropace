"""Three-anchor calibration and z-scoring.

    eyes_closed  ~10 s   alpha reference (relaxation baseline; also the easiest thing to show)
    easy         ~25 s   low anchor: read something easy
    hard         ~25 s   high anchor: dense paragraph, or serial 7s from 1000 out loud

For each index, mu = midpoint of the easy and hard means and sigma = max(pooled std, half the
easy->hard gap), so hard maps to about +1 and easy to about -1 for every wearer. The first
`settle_s` seconds of each phase are ignored because the 4 s window still straddles the previous
phase. If the hard task did NOT raise the effort index, `inverted` is set and reported rather than
silently flipping the sign.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

PHASES = ("eyes_closed", "easy", "hard")
COMMANDS = PHASES + ("done", "reset")
MIN_WINDOWS = 8         # valid windows per anchor for a full-strength calibration
MIN_WINDOWS_WEAK = 3    # below this the calibration is refused


class Ema:
    def __init__(self, tau_s: float = 5.0, dt: float = 1.0) -> None:
        self.a = 1.0 - math.exp(-dt / tau_s)
        self.value: float | None = None

    def update(self, x: float | None) -> float | None:
        if x is None:
            return self.value
        self.value = x if self.value is None else self.value + self.a * (x - self.value)
        return self.value

    def reset(self) -> None:
        self.value = None


@dataclass
class IndexStats:
    mu: float
    sigma: float
    easy_mean: float
    hard_mean: float
    inverted: bool


def _mean(v: list[float]) -> float:
    return sum(v) / len(v)


def _std(v: list[float]) -> float:
    m = _mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / max(1, len(v) - 1))


class Calibration:
    def __init__(self, settle_s: float = 4.0) -> None:
        self.settle_s = settle_s
        self._clear()

    def _clear(self) -> None:
        self.phase: str | None = None
        self._phase_t0 = 0.0
        # per phase: (effort, engagement, log_alpha)
        self.samples: dict[str, list[tuple[float, float, float]]] = {p: [] for p in PHASES}
        self.effort: IndexStats | None = None
        self.engagement: IndexStats | None = None
        self.alpha_open: float | None = None      # mean log alpha, easy phase
        self.alpha_closed: float | None = None    # mean log alpha, eyes-closed phase
        self.weak = False
        self.calibrated = False
        self.messages: list[str] = []

    def command(self, cmd: str, t: float) -> None:
        if cmd in PHASES:
            self.samples[cmd] = []
            self.phase = cmd
            self._phase_t0 = t
        elif cmd == "done":
            self.phase = None
            self.finalize()
        elif cmd == "reset":
            self._clear()
        else:
            raise ValueError(f"calibration command must be one of {COMMANDS}, got {cmd!r}")

    def add(self, effort: float, engagement: float, log_alpha: float, t: float) -> None:
        if self.phase and t - self._phase_t0 >= self.settle_s:
            self.samples[self.phase].append((effort, engagement, log_alpha))

    @staticmethod
    def _stats(easy: list[float], hard: list[float]) -> IndexStats:
        me, mh = _mean(easy), _mean(hard)
        pooled = math.sqrt((_std(easy) ** 2 + _std(hard) ** 2) / 2)
        gap = mh - me
        return IndexStats(mu=(me + mh) / 2, sigma=max(pooled, abs(gap) / 2, 1e-3),
                          easy_mean=me, hard_mean=mh, inverted=gap < 0)

    def finalize(self) -> bool:
        easy, hard = self.samples["easy"], self.samples["hard"]
        ne, nh = len(easy), len(hard)
        self.messages = []
        if ne < MIN_WINDOWS_WEAK or nh < MIN_WINDOWS_WEAK:
            self.calibrated = False
            self.messages.append(f"not enough valid windows (easy={ne}, hard={nh}, need >= {MIN_WINDOWS_WEAK})")
            return False
        self.weak = ne < MIN_WINDOWS or nh < MIN_WINDOWS
        if self.weak:
            self.messages.append(f"weak calibration (easy={ne}, hard={nh}, want >= {MIN_WINDOWS})")
        self.effort = self._stats([s[0] for s in easy], [s[0] for s in hard])
        self.engagement = self._stats([s[1] for s in easy], [s[1] for s in hard])
        if self.effort.inverted:
            self.messages.append("effort was LOWER during the hard task than the easy one: theta/alpha did not "
                                 "separate. Check the fit, or fall back to theta + attention.")
        self.alpha_open = _mean([s[2] for s in easy])
        ec = self.samples["eyes_closed"]
        self.alpha_closed = _mean([s[2] for s in ec]) if len(ec) >= 3 else None
        self.calibrated = True
        return True

    def z(self, effort: float, engagement: float) -> tuple[float | None, float | None]:
        if not self.calibrated or self.effort is None or self.engagement is None:
            return None, None
        return ((effort - self.effort.mu) / self.effort.sigma,
                (engagement - self.engagement.mu) / self.engagement.sigma)

    def alpha_ratio(self, log_alpha: float) -> float | None:
        """Current alpha power relative to the eyes-open (easy) mean; available as soon as a few
        easy windows exist, before "done"."""
        ref = self.alpha_open
        if ref is None:
            easy = self.samples["easy"]
            if len(easy) >= 3:
                ref = _mean([s[2] for s in easy])
        return None if ref is None else 10 ** (log_alpha - ref)

    @property
    def alpha_closed_open_ratio(self) -> float | None:
        if self.alpha_closed is None or self.alpha_open is None:
            return None
        return 10 ** (self.alpha_closed - self.alpha_open)

    def summary(self) -> dict:
        return {
            "calibrated": self.calibrated, "weak": self.weak, "phase": self.phase,
            "windows": {p: len(v) for p, v in self.samples.items()},
            "effort": asdict(self.effort) if self.effort else None,
            "engagement": asdict(self.engagement) if self.engagement else None,
            "alpha_closed_open_ratio": self.alpha_closed_open_ratio,
            "messages": list(self.messages),
        }
