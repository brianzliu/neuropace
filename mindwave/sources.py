"""Event sources: the live headset, a recorded session, or synthetic EEG.

Every source yields thinkgear.Event objects from `events()`; Raw samples arrive at `fs` Hz and the
1 Hz Quality / Esense / Bands rows ride along in order.
"""
from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Iterator, Protocol

import numpy as np

from .thinkgear import FS, UV_PER_RAW, Bands, Control, Esense, Event, Quality, Raw, ThinkGearReader


class Source(Protocol):
    fs: int

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def events(self) -> Iterator[Event]: ...
    @property
    def connected(self) -> bool: ...
    def describe(self) -> dict: ...


class MindWaveSource:
    """The headset on a Bluetooth SPP serial port: the *outgoing* COM port on Windows (COM3 on the
    machine this was written on), /dev/cu.MindWaveMobile-SerialPo on macOS, /dev/rfcomm0 on Linux.
    port=None (or "auto") finds it with ports.find_headset_port(); the last resort is COM3."""

    fs = FS

    def __init__(self, port: str | None = None, baud: int = 57600) -> None:
        if port is None or port == "auto":
            from .ports import find_headset_port
            port = find_headset_port() or "COM3"
        self.port = port
        self._q: queue.Queue = queue.Queue(maxsize=16384)
        self._reader = ThinkGearReader(port, self._q, baud)
        self._stopped = False

    def start(self) -> None:
        if not self._reader.is_alive():
            self._reader.start()

    def stop(self) -> None:
        self._stopped = True
        self._reader.stop()

    def events(self) -> Iterator[Event]:
        while not self._stopped:
            try:
                yield self._q.get(timeout=0.5)
            except queue.Empty:
                continue

    @property
    def connected(self) -> bool:
        return self._reader.connected

    @property
    def error(self) -> str | None:
        return self._reader.error

    def describe(self) -> dict:
        return {"kind": "mindwave", "port": self.port}


class ReplaySource:
    """Replays a session directory written by pipeline.SessionLogger.

    speed: 1.0 = real time, 4.0 = four times faster, 0 = as fast as possible (tests).
    apply_calibration: re-issue the calibration commands recorded in the session.
    """

    def __init__(self, session_dir: str | Path, speed: float = 1.0,
                 apply_calibration: bool = True, loop: bool = False) -> None:
        self.dir = Path(session_dir)
        meta = json.loads((self.dir / "session.json").read_text(encoding="utf-8"))
        self.fs = int(meta.get("fs", FS))
        self.t0 = float(meta.get("t0") or 0.0)
        self.meta = meta
        self.raw = np.fromfile(self.dir / "raw.int16", dtype="<i2")
        lines = (self.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.events_log = [json.loads(line) for line in lines if line.strip()]
        self.events_log.sort(key=lambda e: e.get("n", 0))
        self.speed, self.apply_calibration, self.loop = speed, apply_calibration, loop
        self._stopped = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self._stopped = True

    @property
    def connected(self) -> bool:
        return not self._stopped

    def describe(self) -> dict:
        return {"kind": "replay", "dir": str(self.dir), "speed": self.speed}

    def _to_event(self, e: dict) -> Event | None:
        t = float(e.get("t", self.t0))
        kind = e.get("type")
        if kind == "quality":
            return Quality(t, int(e["poor_signal"]))
        if kind == "esense":
            return Esense(t, int(e["attention"]), int(e["meditation"]))
        if kind == "bands":
            return Bands(t, tuple(int(v) for v in e["values"]))
        if kind == "calibrate" and self.apply_calibration:
            return Control(t, str(e["phase"]))
        return None

    def events(self) -> Iterator[Event]:
        block = 32
        while not self._stopped:
            ei, ne = 0, len(self.events_log)
            wall0, n_total = time.perf_counter(), len(self.raw)
            for start in range(0, n_total, block):
                if self._stopped:
                    return
                end = min(start + block, n_total)
                while ei < ne and self.events_log[ei].get("n", 0) <= start:
                    ev = self._to_event(self.events_log[ei])
                    ei += 1
                    if ev is not None:
                        yield ev
                for n in range(start, end):
                    yield Raw(self.t0 + n / self.fs, int(self.raw[n]))
                if self.speed > 0:
                    delay = wall0 + (end / self.fs) / self.speed - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
            while ei < ne:
                ev = self._to_event(self.events_log[ei])
                ei += 1
                if ev is not None:
                    yield ev
            if not self.loop:
                break
        self._stopped = True


class FakeSource:
    """Synthetic single-channel EEG so consumers can be built and tested without the headset.

    States shape the signal: alpha surges with eyes closed, theta rises on a hard task, blinks come
    faster when drowsy, "off" is an electrode off the skin (noise + poor_signal 200).
    """

    fs = FS
    STATES = ("eyes_closed", "easy", "hard", "drowsy", "off")
    # sinusoid amplitudes in uV, blink rate per minute, and the 1 Hz rows the headset would report
    PROFILE = {
        "eyes_closed": dict(alpha=20.0, theta=4.0, beta=2.0, blinks=0.0, quality=0, attention=30, meditation=70),
        "easy":        dict(alpha=6.0, theta=4.0, beta=3.0, blinks=15.0, quality=0, attention=45, meditation=50),
        "hard":        dict(alpha=3.0, theta=12.0, beta=5.0, blinks=8.0, quality=0, attention=75, meditation=30),
        "drowsy":      dict(alpha=8.0, theta=8.0, beta=2.0, blinks=30.0, quality=26, attention=20, meditation=60),
        "off":         dict(alpha=0.0, theta=0.0, beta=0.0, blinks=0.0, quality=200, attention=0, meditation=0),
    }

    def __init__(self, state: str = "easy", realtime: bool = True, seed: int = 0) -> None:
        self.set_state(state)
        self.realtime = realtime
        self._rng = np.random.default_rng(seed)
        self._stopped = False
        self._n = 0
        self._lp = 0.0
        self._blink_len = int(0.25 * FS)
        self._blink_left = 0
        self._manual_blinks = 0

    def set_state(self, state: str) -> None:
        if state not in self.STATES:
            raise ValueError(f"state must be one of {self.STATES}, got {state!r}")
        self.state = state

    def blink(self) -> None:
        self._manual_blinks += 1

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self._stopped = True

    @property
    def connected(self) -> bool:
        return not self._stopped

    def describe(self) -> dict:
        return {"kind": "fake", "state": self.state}

    def _block(self, m: int) -> np.ndarray:
        p = self.PROFILE[self.state]
        rng = self._rng
        if self.state == "off":
            return rng.normal(0.0, 300.0, m)
        t = (self._n + np.arange(m)) / FS
        x = rng.normal(0.0, 3.0, m)
        # 1/f-ish background: one-pole lowpass of white noise, state carried across blocks
        w = rng.normal(0.0, 2.0, m)
        y = np.empty(m)
        lp = self._lp
        for i in range(m):
            lp = 0.9 * lp + w[i]
            y[i] = lp
        self._lp = lp
        x += y
        drift = 1.0 + 0.3 * np.sin(2 * np.pi * 0.2 * t)
        x += p["alpha"] * drift * np.sin(2 * np.pi * 10.0 * t + 0.3)
        x += p["theta"] * np.sin(2 * np.pi * 6.0 * t + 1.1)
        x += p["beta"] * np.sin(2 * np.pi * 20.0 * t + 2.0)
        if self._blink_left == 0:
            spontaneous = rng.random() < p["blinks"] / 60.0 * (m / FS)
            if self._manual_blinks > 0 or spontaneous:
                if self._manual_blinks > 0:
                    self._manual_blinks -= 1
                self._blink_left = self._blink_len
        if self._blink_left > 0:
            k = min(self._blink_left, m)
            i0 = self._blink_len - self._blink_left
            x[:k] += 250.0 * np.sin(np.pi * (i0 + np.arange(k)) / self._blink_len)
            self._blink_left -= k
        return x

    def events(self) -> Iterator[Event]:
        block = 32
        wall0 = time.perf_counter()
        t0 = time.time()            # sample-derived clock, so realtime=False still advances time
        next_1hz = FS
        rng = self._rng
        while not self._stopped:
            x = self._block(block)
            t_now = t0 + (self._n + block) / FS
            counts = np.clip(np.rint(x / UV_PER_RAW), -32768, 32767).astype(int)
            for v in counts:
                yield Raw(t_now, int(v))
            self._n += block
            if self._n >= next_1hz:
                next_1hz += FS
                p = self.PROFILE[self.state]
                yield Quality(t_now, int(p["quality"]))
                att = int(np.clip(p["attention"] + rng.normal(0, 8), 0, 100))
                med = int(np.clip(p["meditation"] + rng.normal(0, 8), 0, 100))
                yield Esense(t_now, att, med)
                scale = rng.uniform(0.8, 1.2)
                yield Bands(t_now, tuple(int(v * scale) for v in (
                    3e5, 2e4 * p["theta"] + 1e3, 1e4 * p["alpha"] + 1e3, 8e3 * p["alpha"] + 1e3,
                    5e3 * p["beta"] + 1e3, 4e3 * p["beta"] + 1e3, 1e3, 8e2)))
            if self.realtime:
                delay = wall0 + self._n / FS - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
