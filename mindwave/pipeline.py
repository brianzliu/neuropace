"""Pipeline: headset stream -> one FeatureFrame of attention metrics per second.

Standalone. Nothing here depends on, or knows about, any application. Consumers subscribe
in-process, over the WebSocket feed, or read the session files afterwards.

In-process use:

    from mindwave import Pipeline, MindWaveSource
    pipe = Pipeline(MindWaveSource())  # port found automatically; or MindWaveSource("COM3")
    pipe.serve()                       # optional: WebSocket feed on ws://127.0.0.1:8765
    pipe.calibrate("eyes_closed")      # then "easy", "hard", "done" — or pipe.auto_calibrate()
    for frame in pipe.frames():        # blocks; one FeatureFrame per second
        if frame.valid:
            frame.effort, frame.engagement, frame.blink_rate, frame.alpha_ratio, ...
            frame.z_effort_ema, frame.z_engagement_ema      # None until calibrated

Or register `pipe.on_frame(callback)` (called on the pipeline thread; keep it quick).

The pipeline owns filtering, artifact gating, band powers, blink detection, calibration
z-scores and the 5 s EMA. It makes no decisions: what a metric means for a given use is the
consumer's business.

Every session is logged to sessions/<stamp>/ (raw.int16, events.jsonl, features.jsonl) unless
log_dir=None; ReplaySource plays a session back with its calibration commands.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

from . import features as F
from .calibration import COMMANDS, Calibration, Ema
from .sources import Source
from .thinkgear import FS, UV_PER_RAW, Bands, Control, Esense, Quality, Raw

QUALITY_MAX = 50        # poor_signal above this -> frame invalid
# Artifact-masked fraction above this -> frame invalid. Each blink masks ~0.6 s of the 4 s window
# (measured duration + padding), so at a normal 15 blinks/min two blinks in one window is common;
# 0.5 still leaves 2 s of clean EEG, ample for theta and above, without gating on ordinary blinking.
COVERAGE_MAX = 0.50
QUALITY_STALE_S = 3.0   # no 1 Hz row for this long -> treat as off-head


@dataclass
class FeatureFrame:
    t: float                        # unix seconds at the end of the window
    n: int                          # absolute sample index at the end of the window
    quality: int                    # poor_signal: 0 best ... 200 off-head
    valid: bool                     # quality ok, artifacts <= 30 %, source connected, buffer full
    connected: bool
    log_theta: float                # log10 band power (own Welch PSD, 4-8 Hz)
    log_alpha: float                # 8-13 Hz
    log_beta: float                 # 13-30 Hz
    log_gamma: float                # 30-45 Hz
    effort: float                   # log theta - log alpha: mental workload, rises when concentrating
    engagement: float               # log beta - log(alpha + theta): alertness (Pope index)
    effort_ema: float | None        # EMA tau = 5 s, held across invalid frames
    engagement_ema: float | None
    z_effort: float | None          # calibrated: easy phase ~ -1, hard phase ~ +1 for this wearer.
    z_engagement: float | None      #   None until calibrated or when the frame is invalid
    z_effort_ema: float | None      # the smoothed calibrated values: the ones to act on
    z_engagement_ema: float | None
    alpha_ratio: float | None       # alpha now / alpha during the easy phase: relaxation, eyes closed
    blink_count: int                # blinks that began in this 1 s hop
    blink_rate: float               # per minute, trailing 30 s: up with fatigue, down when absorbed
    blink_dur_ms: float | None      # mean duration, trailing 30 s: up with drowsiness
    artifact_coverage: float        # masked fraction of the 4 s window
    attention: int | None           # NeuroSky eSense passthrough, for comparison only
    meditation: int | None
    asic_bands: list[int] | None    # NeuroSky ASIC band powers, arbitrary units
    calibrated: bool
    cal_phase: str | None           # phase currently collecting, if any
    calibration_weak: bool

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 4)
        d["type"] = "features"
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class RingBuffer:
    """Fixed-capacity buffer addressed by absolute sample index."""

    def __init__(self, capacity: int) -> None:
        self.cap = capacity
        self.buf = np.zeros(capacity, dtype=np.float64)
        self.n = 0

    def push(self, value: float) -> None:
        self.buf[self.n % self.cap] = value
        self.n += 1

    def slice(self, start: int, end: int) -> np.ndarray:
        return self.buf[np.arange(start, end) % self.cap]


class SessionLogger:
    def __init__(self, root: str | Path, source_desc: dict, fs: int) -> None:
        self.dir = Path(root) / time.strftime("%Y%m%d-%H%M%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fs = fs
        self.t0: float | None = None
        self._source = source_desc
        self._raw_f = open(self.dir / "raw.int16", "wb")
        self._ev_f = open(self.dir / "events.jsonl", "w", encoding="utf-8")
        self._fr_f = open(self.dir / "features.jsonl", "w", encoding="utf-8")
        self._raw_buf: list[int] = []
        self._write_meta()

    def _write_meta(self) -> None:
        meta = {"fs": self.fs, "t0": self.t0, "source": self._source, "created": time.time()}
        (self.dir / "session.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    def set_t0(self, t: float) -> None:
        self.t0 = t
        self._write_meta()

    def raw(self, value: int) -> None:
        self._raw_buf.append(value)

    def event(self, kind: str, t: float, n: int, **fields) -> None:
        self._ev_f.write(json.dumps({"type": kind, "t": t, "n": n, **fields}) + "\n")

    def frame(self, frame: FeatureFrame) -> None:
        self._fr_f.write(frame.to_json() + "\n")

    def flush(self) -> None:
        if self._raw_buf:
            np.asarray(self._raw_buf, dtype="<i2").tofile(self._raw_f)
            self._raw_buf.clear()
        for f in (self._raw_f, self._ev_f, self._fr_f):
            f.flush()

    def close(self) -> None:
        self.flush()
        for f in (self._raw_f, self._ev_f, self._fr_f):
            f.close()
        self._write_meta()


class Pipeline:
    def __init__(self, source: Source, window_s: float = 4.0, hop_s: float = 1.0,
                 log_dir: str | Path | None = "sessions", ema_tau_s: float = 5.0,
                 artifact_kw: dict | None = None) -> None:
        self.source = source
        self.fs = source.fs
        self.win = int(window_s * self.fs)
        self.hop = int(hop_s * self.fs)
        self.buf = RingBuffer(2 * self.win)
        self.calibration = Calibration(settle_s=window_s)
        self.artifact_kw = artifact_kw or {}
        self._ema = {k: Ema(ema_tau_s, hop_s) for k in ("effort", "engagement", "z_effort", "z_engagement")}
        self._frame_subs: list[Callable[[FeatureFrame], None]] = []
        self._blink_subs: list[Callable[[dict], None]] = []
        self._raw_subs: list[Callable[[dict], None]] = []
        self._status_subs: list[Callable[[dict], None]] = []
        self._queues: list[queue.Queue] = []
        self.history: deque[FeatureFrame] = deque(maxlen=600)
        self.latest: FeatureFrame | None = None
        self._quality: int | None = None
        self._quality_t = 0.0
        self._esense: Esense | None = None
        self._bands: Bands | None = None
        self._blink_times: deque[tuple[float, float]] = deque()
        self._t_last = time.time()
        self._log = SessionLogger(log_dir, source.describe(), self.fs) if log_dir else None
        self._next_hop = self.win
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._dec_acc: list[float] = []
        self._raw_chunk: list[float] = []
        self._last_status: tuple | None = None
        self._server = None

    # ---- lifecycle -------------------------------------------------------------------------

    @property
    def session_dir(self) -> Path | None:
        return self._log.dir if self._log else None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.source.start()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="mindwave-pipeline")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self.source.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._server is not None:
            self._server.stop()
        if self._log is not None:
            self._log.close()

    def serve(self, host: str = "127.0.0.1", port: int = 8765):
        """Start the WebSocket feed (features, raw trace, blinks, status; accepts calibrate)."""
        from .server import WebSocketServer
        self._server = WebSocketServer(self, host, port)
        self._server.start()
        return self._server

    # ---- consumer API ----------------------------------------------------------------------

    def frames(self) -> Iterator[FeatureFrame]:
        """Blocking iterator over frames; starts the pipeline if needed."""
        if not self._running:
            self.start()
        q: queue.Queue = queue.Queue()
        self._queues.append(q)
        try:
            while self._running or not q.empty():
                try:
                    yield q.get(timeout=0.5)
                except queue.Empty:
                    continue
        finally:
            self._queues.remove(q)

    def on_frame(self, cb: Callable[[FeatureFrame], None]) -> None:
        self._frame_subs.append(cb)

    def on_blink(self, cb: Callable[[dict], None]) -> None:
        self._blink_subs.append(cb)

    def on_raw(self, cb: Callable[[dict], None]) -> None:
        """64 Hz decimated trace in 125 ms chunks: {"type":"raw","t","fs","uv":[...]}."""
        self._raw_subs.append(cb)

    def on_status(self, cb: Callable[[dict], None]) -> None:
        self._status_subs.append(cb)

    def calibrate(self, command: str) -> None:
        """One of: eyes_closed | easy | hard | done | reset."""
        if command not in COMMANDS:
            raise ValueError(f"calibrate() takes one of {COMMANDS}, got {command!r}")
        self._apply_calibration(command, self._t_last, log=True)

    def auto_calibrate(self, eyes_closed_s: float = 10, easy_s: float = 25, hard_s: float = 25,
                       say: Callable[[str], None] = print) -> threading.Thread:
        """Run the three phases on a timer with console prompts; returns the thread."""
        script = (("eyes_closed", eyes_closed_s, "close your eyes and relax"),
                  ("easy", easy_s, "read something easy"),
                  ("hard", hard_s, "count down from 1000 by 7s, out loud"))

        def run() -> None:
            for phase, secs, prompt in script:
                if secs <= 0:
                    continue
                say(f"[calibration] {phase}: {prompt} ({secs:.0f} s)")
                self.calibrate(phase)
                time.sleep(secs)
            self.calibrate("done")
            cal = self.calibration
            say("[calibration] " + ("ok" if cal.calibrated else "FAILED")
                + (" (weak)" if cal.weak else "") + "".join(f"; {m}" for m in cal.messages))
            r = cal.alpha_closed_open_ratio
            if r is not None:
                say(f"[calibration] alpha closed/open = {r:.2f}x")

        th = threading.Thread(target=run, daemon=True, name="mindwave-autocal")
        th.start()
        return th

    def status(self) -> dict:
        cal = self.calibration
        return {
            "type": "status",
            "connected": self.source.connected,
            "quality": self._current_quality(self._t_last),
            "calibrated": cal.calibrated,
            "cal_phase": cal.phase,
            "calibration_weak": cal.weak,
            "alpha_closed_open_ratio": cal.alpha_closed_open_ratio,
            "messages": list(cal.messages),
            "source": self.source.describe(),
            "samples": self.buf.n,
            "error": getattr(self.source, "error", None),
            "session_dir": str(self.session_dir) if self.session_dir else None,
        }

    def raw_window(self, seconds: float = 4.0):
        """Display-band (0.5-45 Hz) uV trace of the last `seconds`, with its artifact mask and
        blinks, for plotting: blinks stay visible instead of being cut by the 3 Hz analysis edge."""
        m = int(seconds * self.fs)
        n = self.buf.n
        if n < m:
            return np.zeros(m), np.zeros(m, dtype=bool), []
        x_uv = F.to_uv(self.buf.slice(n - m, n))
        blinks, mask = F.detect_artifacts(F.blink_band(x_uv), self.fs, **self.artifact_kw)
        return F.display_band(x_uv), mask, blinks

    # ---- internals -------------------------------------------------------------------------

    def _loop(self) -> None:
        for ev in self.source.events():
            if not self._running:
                break
            if isinstance(ev, Raw):
                self._on_raw(ev)
            elif isinstance(ev, Quality):
                self._quality, self._quality_t, self._t_last = ev.poor_signal, ev.t, ev.t
                if self._log:
                    self._log.event("quality", ev.t, self.buf.n, poor_signal=ev.poor_signal)
                self._emit_status()
            elif isinstance(ev, Esense):
                self._esense = ev
                if self._log:
                    self._log.event("esense", ev.t, self.buf.n, attention=ev.attention, meditation=ev.meditation)
            elif isinstance(ev, Bands):
                self._bands = ev
                if self._log:
                    self._log.event("bands", ev.t, self.buf.n, values=list(ev.values))
            elif isinstance(ev, Control):
                self._apply_calibration(ev.phase, ev.t, log=False)
        self._running = False

    def _on_raw(self, ev: Raw) -> None:
        buf = self.buf
        buf.push(ev.value)
        n = buf.n
        self._t_last = ev.t
        if self._log is not None:
            if self._log.t0 is None:
                self._log.set_t0(ev.t)
            self._log.raw(ev.value)
        if self._raw_subs:
            acc = self._dec_acc
            acc.append(ev.value * UV_PER_RAW)
            if len(acc) >= 8:
                self._raw_chunk.append(sum(acc) / len(acc))
                acc.clear()
                if len(self._raw_chunk) >= 8:
                    msg = {"type": "raw", "t": round(ev.t, 3), "fs": self.fs // 8,
                           "uv": [round(v, 1) for v in self._raw_chunk]}
                    self._raw_chunk = []
                    self._fanout(self._raw_subs, msg)
        if n >= self._next_hop:
            if n - self._next_hop > buf.cap - self.win:     # fell behind: drop stale hops
                self._next_hop = n
            while n >= self._next_hop:
                self._compute(self._next_hop, ev.t)
                self._next_hop += self.hop

    def _current_quality(self, t: float) -> int:
        if self._quality is None or t - self._quality_t > QUALITY_STALE_S:
            return 200
        return self._quality

    def _compute(self, end_n: int, t: float) -> None:
        wf = F.compute_window(self.buf.slice(end_n - self.win, end_n), self.fs, **self.artifact_kw)
        quality = self._current_quality(t)
        connected = self.source.connected
        # contact gates blinks; valid additionally requires the window to be mostly artifact-free.
        # A blink storm makes a window invalid for the PSD but the blinks themselves are still real.
        contact = quality <= QUALITY_MAX and connected
        valid = contact and wf.artifact_coverage <= COVERAGE_MAX

        # Count each blink once: only those that began inside this hop, and only while the
        # electrode is actually on skin - an off-head channel is pure noise and will otherwise
        # manufacture a steady stream of phantom blinks, corrupting the fatigue axis.
        hop_start = self.win - self.hop
        new_blinks = [b for b in wf.blinks if b.start >= hop_start] if contact else []
        for b in new_blinks:
            tb = t - (self.win - b.start) / self.fs
            self._blink_times.append((tb, b.duration_ms))
            msg = {"type": "blink", "t": round(tb, 3), "amplitude_uv": round(b.amplitude_uv, 1),
                   "duration_ms": round(b.duration_ms, 1)}
            if self._log:
                self._log.event("blink", tb, end_n, amplitude_uv=msg["amplitude_uv"], duration_ms=msg["duration_ms"])
            self._fanout(self._blink_subs, msg)
        while self._blink_times and self._blink_times[0][0] < t - 30.0:
            self._blink_times.popleft()
        blink_rate = len(self._blink_times) * 2.0
        blink_dur = (sum(d for _, d in self._blink_times) / len(self._blink_times)) if self._blink_times else None

        cal = self.calibration
        with self._lock:
            if valid:
                cal.add(wf.effort, wf.engagement, wf.log_alpha, t)
            z_e, z_g = cal.z(wf.effort, wf.engagement) if valid else (None, None)
            alpha_ratio = cal.alpha_ratio(wf.log_alpha) if valid else None
            calibrated, phase, weak = cal.calibrated, cal.phase, cal.weak
        e_ema = self._ema["effort"].update(wf.effort if valid else None)
        g_ema = self._ema["engagement"].update(wf.engagement if valid else None)
        ze_ema = self._ema["z_effort"].update(z_e)
        zg_ema = self._ema["z_engagement"].update(z_g)

        frame = FeatureFrame(
            t=t, n=end_n, quality=quality, valid=valid, connected=connected,
            log_theta=wf.log_theta, log_alpha=wf.log_alpha, log_beta=wf.log_beta, log_gamma=wf.log_gamma,
            effort=wf.effort, engagement=wf.engagement, effort_ema=e_ema, engagement_ema=g_ema,
            z_effort=z_e, z_engagement=z_g, z_effort_ema=ze_ema, z_engagement_ema=zg_ema,
            alpha_ratio=alpha_ratio, blink_count=len(new_blinks), blink_rate=blink_rate,
            blink_dur_ms=blink_dur, artifact_coverage=wf.artifact_coverage,
            attention=self._esense.attention if self._esense else None,
            meditation=self._esense.meditation if self._esense else None,
            asic_bands=list(self._bands.values) if self._bands else None,
            calibrated=calibrated, cal_phase=phase, calibration_weak=weak,
        )
        self.latest = frame
        self.history.append(frame)
        if self._log:
            self._log.frame(frame)
            self._log.flush()
        self._fanout(self._frame_subs, frame)
        for q in self._queues:
            q.put(frame)
        self._emit_status()

    def _apply_calibration(self, command: str, t: float, log: bool) -> None:
        with self._lock:
            self.calibration.command(command, t)
        if command in ("done", "reset"):
            self._ema["z_effort"].reset()
            self._ema["z_engagement"].reset()
        if log and self._log:
            self._log.event("calibrate", t, self.buf.n, phase=command)
        self._emit_status(force=True)

    def _emit_status(self, force: bool = False) -> None:
        if not self._status_subs:
            return
        s = self.status()
        key = (s["connected"], s["quality"] > QUALITY_MAX, s["calibrated"], s["cal_phase"])
        if force or key != self._last_status:
            self._last_status = key
            self._fanout(self._status_subs, s)

    @staticmethod
    def _fanout(subs, payload) -> None:
        for cb in list(subs):
            try:
                cb(payload)
            except Exception as e:  # a bad subscriber must not kill the pipeline thread
                print(f"[mindwave] subscriber {getattr(cb, '__name__', cb)} raised {e!r}")
