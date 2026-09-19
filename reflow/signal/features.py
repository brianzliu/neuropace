"""Focus index pipeline (TDD §3.2): band powers -> E = beta/(alpha+theta) -> ln -> EMA -> baseline z -> 15 s window
-> drop detector with hysteresis, cap, refractory, lead-in.

Blinks are blanked (linear interpolation over +-150 ms) before the FFT; segments whose residual peak-to-peak is still
an outlier are rejected. The poor-signal byte gates everything.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass

import numpy as np

from ..config import Settings
from .blinks import BlinkDetector

BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}


@dataclass(slots=True)
class FocusSample:
    t: float
    e: float | None
    x: float | None
    z: float | None
    w15: float | None
    quality: str  # good | bad
    state: str  # baseline | ok | drop | bad | nosignal
    baseline_ready: bool
    baseline_progress: float
    artifact: bool
    blink: bool
    paused: bool
    poor_signal: int
    attention: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DetectorEvent:
    kind: str  # enter | exit
    t: float
    t_start: float
    t_end: float | None


def band_powers(segment: np.ndarray, fs: int) -> dict[str, float]:
    x = np.asarray(segment, dtype=np.float64)
    x = x - x.mean()
    w = np.hanning(x.size)
    spec = np.abs(np.fft.rfft(x * w)) ** 2
    freqs = np.fft.rfftfreq(x.size, 1.0 / fs)
    out = {}
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        out[name] = float(spec[m].sum())
    return out


def blank_blinks(segment: np.ndarray, blink_idx: list[int], fs: int, half_ms: int = 150) -> np.ndarray:
    """Linear interpolation over +-half_ms around each blink index (indices relative to the segment)."""
    if not blink_idx:
        return segment
    x = np.asarray(segment, dtype=np.float64).copy()
    half = int(fs * half_ms / 1000)
    n = x.size
    for i in blink_idx:
        a = max(0, i - half)
        b = min(n - 1, i + half)
        if b <= a:
            continue
        x[a : b + 1] = np.linspace(x[a], x[b], b - a + 1)
    return x


class Baseline:
    def __init__(
        self, seconds: float, min_valid_fraction: float, min_valid_samples: int, sigma_floor: float
    ) -> None:
        self.seconds = seconds
        self.min_valid_fraction = min_valid_fraction
        self.min_valid_samples = min_valid_samples
        self.sigma_floor = sigma_floor
        self._xs: list[float] = []
        self.listened = 0.0
        self.mu: float | None = None
        self.sigma: float | None = None
        self.stored = False

    @classmethod
    def from_stored(cls, mu: float, sigma: float, sigma_floor: float = 0.05) -> Baseline:
        b = cls(0.0, 0.0, 0, sigma_floor)
        b.mu, b.sigma, b.stored = float(mu), max(float(sigma), sigma_floor), True
        return b

    @property
    def ready(self) -> bool:
        return self.mu is not None

    @property
    def min_valid_effective(self) -> int:
        """Short rehearsal baselines (e.g. 8 s) must still be able to finish: scale the 30-sample floor down."""
        return max(3, min(self.min_valid_samples, int(self.min_valid_fraction * self.seconds)))

    @property
    def needed_valid(self) -> float:
        return max(float(self.min_valid_effective), self.min_valid_fraction * self.seconds)

    @property
    def progress(self) -> float:
        if self.ready:
            return 1.0
        if self.seconds <= 0:
            return 1.0
        return min(1.0, len(self._xs) / self.needed_valid)

    def add(self, x: float | None, listening: bool) -> None:
        if self.ready:
            return
        if listening:
            self.listened += 1.0
            if x is not None and math.isfinite(x):
                self._xs.append(x)
        if (len(self._xs) >= self.needed_valid) or (
            self.listened >= self.seconds and len(self._xs) >= self.min_valid_effective
        ):
            arr = np.asarray(self._xs)
            self.mu = float(arr.mean())
            self.sigma = max(float(arr.std(ddof=1)) if arr.size > 1 else self.sigma_floor, self.sigma_floor)


class DropDetector:
    def __init__(self, s: Settings) -> None:
        self.s = s
        self.in_drop = False
        self.t_enter: float | None = None
        self.last_exit: float | None = None

    def update(self, t: float, w15: float | None, allowed: bool) -> list[DetectorEvent]:
        events: list[DetectorEvent] = []
        s = self.s
        if self.in_drop:
            assert self.t_enter is not None
            timed_out = t - self.t_enter >= s.eeg_flag_max_seconds
            recovered = w15 is not None and w15 > s.drop_exit_z
            if timed_out or recovered or not allowed:
                self.in_drop = False
                self.last_exit = t
                events.append(DetectorEvent("exit", t, self.t_enter - s.lead_in_seconds, t))
                self.t_enter = None
            return events
        if not allowed or w15 is None:
            return events
        if self.last_exit is not None and t - self.last_exit < s.eeg_refractory_seconds:
            return events
        if w15 < s.drop_enter_z:
            self.in_drop = True
            self.t_enter = t
            events.append(DetectorEvent("enter", t, t - s.lead_in_seconds, None))
        return events


class FocusEngine:
    """Feed raw samples and status bytes; call tick(t) once per lecture second."""

    def __init__(self, s: Settings, stored_baseline: tuple[float, float] | None = None) -> None:
        self.s = s
        self.fs = s.fs
        self._win = int(s.fft_window_seconds * s.fs)
        self._raw = np.zeros(0, dtype=np.float64)
        self._raw_pos = 0  # global sample index of self._raw[0]
        self.blinks = BlinkDetector(s.fs, abs_p2p=s.blink_abs_p2p, median_mult=s.blink_median_mult)
        self._p2p_hist: deque[float] = deque(maxlen=30)
        self.poor_signal = 200
        self.attention: int | None = None
        self.eeg_power: dict[str, int] | None = None
        self._x_ema: float | None = None
        self._alpha = 1.0 - math.exp(-1.0 / s.ema_tau_seconds)
        self.baseline = (
            Baseline.from_stored(*stored_baseline, sigma_floor=s.sigma_floor)
            if stored_baseline
            else Baseline(
                s.baseline_seconds, s.baseline_min_valid_fraction, s.baseline_min_valid_samples, s.sigma_floor
            )
        )
        self.detector = DropDetector(s)
        self._zwin: deque[float | None] = deque(maxlen=s.window_seconds)
        self._blinks_since_tick = 0
        self._received_any = False
        self.samples_total = 0
        self.artifacts = 0
        self.last: FocusSample | None = None

    # ---- inputs ----
    def feed_raw(self, samples) -> None:
        x = np.asarray(samples, dtype=np.float64)
        if x.size == 0:
            return
        self._received_any = True
        self.samples_total += x.size
        self._blinks_since_tick += self.blinks.feed(x)
        self._raw = np.concatenate([self._raw, x])
        keep = self._win * 2
        if self._raw.size > keep:
            drop = self._raw.size - keep
            self._raw = self._raw[drop:]
            self._raw_pos += drop

    def feed_poor_signal(self, v: int) -> None:
        self.poor_signal = int(v)
        self._received_any = True

    def feed_attention(self, v: int) -> None:
        self.attention = int(v)

    def feed_eeg_power(self, v: dict[str, int]) -> None:
        self.eeg_power = v

    # ---- per-second update ----
    def _segment_features(self) -> tuple[float | None, bool]:
        """Returns (x = ln E or None, artifact)."""
        if self._raw.size < self._win:
            return None, False
        seg = self._raw[-self._win :]
        seg_start = self._raw_pos + self._raw.size - self._win
        rel = [
            p - seg_start
            for p in self.blinks.recent_blink_positions
            if seg_start <= p < seg_start + self._win
        ]
        clean = blank_blinks(seg, rel, self.fs)
        p2p = float(clean.max() - clean.min())
        med = float(np.median(self._p2p_hist)) if len(self._p2p_hist) >= 5 else 0.0
        thresh = (
            max(self.s.artifact_abs_p2p, self.s.artifact_median_mult * med)
            if med > 0
            else self.s.artifact_abs_p2p
        )
        if p2p > thresh:
            self.artifacts += 1
            return None, True
        self._p2p_hist.append(p2p)
        bp = band_powers(clean, self.fs)
        denom = bp["alpha"] + bp["theta"]
        if denom <= 0 or bp["beta"] <= 0:
            return None, True
        e = bp["beta"] / denom
        return math.log(e), False

    def tick(self, t: float, paused: bool = False) -> tuple[FocusSample, list[DetectorEvent]]:
        s = self.s
        quality_ok = self._received_any and self.poor_signal <= s.poor_signal_gate
        x, artifact = self._segment_features() if quality_ok else (None, False)
        blink = self._blinks_since_tick > 0
        self._blinks_since_tick = 0
        valid = quality_ok and x is not None and not paused
        if valid:
            assert x is not None
            self._x_ema = x if self._x_ema is None else self._x_ema + self._alpha * (x - self._x_ema)
        x_ema = self._x_ema if valid else None
        listening = quality_ok and not paused
        self.baseline.add(x_ema, listening)
        z: float | None = None
        if self.baseline.ready and x_ema is not None:
            assert self.baseline.mu is not None and self.baseline.sigma is not None
            z = (x_ema - self.baseline.mu) / self.baseline.sigma
        self._zwin.append(z)
        vals = [v for v in self._zwin if v is not None]
        w15 = float(np.mean(vals)) if len(vals) >= s.window_min_valid else None
        allowed = self.baseline.ready and quality_ok and not paused
        events = self.detector.update(t, w15, allowed)
        if not self._received_any:
            state = "nosignal"
        elif not quality_ok:
            state = "bad"
        elif not self.baseline.ready:
            state = "baseline"
        elif self.detector.in_drop:
            state = "drop"
        else:
            state = "ok"
        sample = FocusSample(
            t=round(t, 3),
            e=(math.exp(x) if x is not None else None),
            x=(round(x_ema, 4) if x_ema is not None else None),
            z=(round(z, 3) if z is not None else None),
            w15=(round(w15, 3) if w15 is not None else None),
            quality="good" if quality_ok else "bad",
            state=state,
            baseline_ready=self.baseline.ready,
            baseline_progress=round(self.baseline.progress, 3),
            artifact=artifact,
            blink=blink,
            paused=paused,
            poor_signal=self.poor_signal,
            attention=self.attention,
        )
        self.last = sample
        return sample, events
