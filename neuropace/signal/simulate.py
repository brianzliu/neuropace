"""Synthetic 512 Hz single-electrode EEG with a controllable state (TDD §3.3).

States: focused (beta-heavy), drifting (theta up, beta down), poor (off-head noise, poor_signal=200).
Band amplitudes wander slowly (AR(1) on log gain) so ln E has a realistic spread (sigma about 0.3),
and blinks are 400-unit bumps every 5-9 s. Emits real ThinkGear bytes so the parser runs in every simulated session.
"""

from __future__ import annotations

import numpy as np

from .thinkgear import encode_raw, encode_status

STATES = ("focused", "drifting", "poor")
# amplitudes (theta, alpha, beta) in raw units
_AMPS = {
    "focused": (12.0, 15.0, 18.0),
    "drifting": (22.0, 19.0, 9.0),
    "poor": (12.0, 15.0, 18.0),
}


class SimulatedEEG:
    def __init__(
        self,
        fs: int = 512,
        seed: int = 11,
        state: str = "focused",
        blink_every: tuple[float, float] = (5.0, 9.0),
        wander_sigma: float = 0.22,
        wander_tau: float = 6.0,
    ) -> None:
        self.fs = fs
        self.rng = np.random.default_rng(seed)
        self.state = state
        self._target = np.array(_AMPS[state])
        self._amps = self._target.copy()
        self._gain = np.zeros(3)  # log-gain AR(1)
        self._wander_sigma = wander_sigma
        self._wander_tau = wander_tau
        self._phase = np.zeros(3)
        self._freqs = np.array([6.0, 10.0, 20.0])
        self._blink_every = blink_every
        self._next_blink = self.rng.uniform(*blink_every)
        self._t = 0.0
        self.samples_emitted = 0

    def set_state(self, state: str) -> None:
        if state not in STATES:
            raise ValueError(f"unknown state {state}")
        self.state = state
        self._target = np.array(_AMPS[state])

    @property
    def poor_signal(self) -> int:
        return 200 if self.state == "poor" else 0

    def next_samples(self, n: int) -> np.ndarray:
        """n raw samples (int16-range floats)."""
        dt = 1.0 / self.fs
        span = n * dt
        t = self._t + dt * np.arange(1, n + 1)
        ramp = 1.0 - np.exp(-span / 2.0)
        self._amps = self._amps + (self._target - self._amps) * ramp
        rho = np.exp(-span / self._wander_tau)
        self._gain = rho * self._gain + self.rng.normal(0, self._wander_sigma * np.sqrt(1 - rho**2), 3)
        amps = self._amps * np.exp(self._gain)
        ph = self._phase[:, None] + 2 * np.pi * self._freqs[:, None] * (t - self._t)[None, :]
        sig = (amps[:, None] * np.sin(ph)).sum(axis=0)
        noise = self.rng.normal(0, 10.0, n)
        if self.state == "poor":
            noise = self.rng.normal(0, 600.0, n)
        x = sig + noise
        bump_w = 0.10
        while self._next_blink <= t[-1] + bump_w:
            center = self._next_blink
            x += 400.0 * np.exp(-0.5 * ((t - center) / (bump_w / 2.5)) ** 2)
            if center <= t[-1]:
                self._next_blink += self.rng.uniform(*self._blink_every)
            else:
                break
        self._phase = ph[:, -1] % (2 * np.pi)
        self._t = t[-1]
        self.samples_emitted += n
        return np.clip(x, -2048, 2047)

    def next_bytes(self, n: int, with_status: bool = False) -> bytes:
        out = bytearray()
        for v in self.next_samples(n):
            out += encode_raw(int(round(v)))
        if with_status:
            att = 70 if self.state == "focused" else 35
            out += encode_status(self.poor_signal, attention=att, meditation=50)
        return bytes(out)
