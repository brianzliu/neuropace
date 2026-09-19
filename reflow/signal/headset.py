"""Headset sources (TDD §2.1, §3): a real NeuroSky over Bluetooth SPP, a simulator, or a replay of raw samples.

All sources deliver TGEvents to a callback on the asyncio loop; the SessionRuntime routes them into the FocusEngine.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

from .simulate import STATES, SimulatedEEG
from .thinkgear import TGEvent, ThinkGearParser

log = logging.getLogger(__name__)

HEADSET_BAUD = 57600
EventCallback = Callable[[list[TGEvent]], None]


def list_serial_ports() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except Exception:  # pragma: no cover
        return []
    return [(p.device, p.description or "") for p in list_ports.comports()]


def autodetect_headset_port(probe: bool = True) -> str | None:
    """Delegates to mindwave.ports (name match on macOS/Linux, probed Bluetooth COM ports on Windows)."""
    from mindwave.ports import find_headset_port

    return find_headset_port(probe=probe)


def resolve_headset(setting: str | None, probe: bool = True) -> str:
    """Turn a session/env headset setting into a concrete one before the runtime is built.
    "auto"/None becomes a device path (probing may take a second or two per candidate) or "sim"."""
    s = (setting or "auto").strip()
    if s != "auto":
        return s
    port = autodetect_headset_port(probe=probe)
    return port or "sim"


class SimulatedHeadset:
    kind = "simulated"

    def __init__(self, on_events: EventCallback, seed: int = 11, chunk_hz: int = 8) -> None:
        self.on_events = on_events
        self.sim = SimulatedEEG(seed=seed)
        self.parser = ThinkGearParser()
        self.chunk_hz = chunk_hz
        self.port = "sim"
        self.connected = True
        self._task: asyncio.Task | None = None

    @property
    def state(self) -> str:
        return self.sim.state

    def set_state(self, state: str) -> None:
        if state not in STATES:
            raise ValueError(state)
        self.sim.set_state(state)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="sim-headset")

    async def _run(self) -> None:
        n = self.sim.fs // self.chunk_hz
        period = 1.0 / self.chunk_hz
        next_t = time.monotonic()
        i = 0
        try:
            while True:
                i += 1
                data = self.sim.next_bytes(n, with_status=(i % self.chunk_hz == 0))
                self.on_events(self.parser.feed(data))
                next_t += period
                await asyncio.sleep(max(0.0, next_t - time.monotonic()))
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class SerialHeadset:
    """Reads the ThinkGear byte stream from a serial port in a thread and hands events to the loop."""

    kind = "real"

    def __init__(self, port: str, on_events: EventCallback, baud: int = HEADSET_BAUD) -> None:
        self.port = port
        self.baud = baud
        self.on_events = on_events
        self.parser = ThinkGearParser()
        self.connected = False
        self._stop = False
        self._thread_task: asyncio.Task | None = None
        self.state = "real"

    def set_state(self, state: str) -> None:  # parity with the simulator; no-op
        return None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._thread_task = loop.run_in_executor(None, self._reader, loop)

    def _reader(self, loop: asyncio.AbstractEventLoop) -> None:
        import serial  # pyserial

        while not self._stop:
            try:
                with serial.Serial(self.port, self.baud, timeout=0.2) as ser:
                    self.connected = True
                    log.info("headset connected on %s", self.port)
                    while not self._stop:
                        data = ser.read(512)
                        if data:
                            events = self.parser.feed(data)
                            if events:
                                loop.call_soon_threadsafe(self.on_events, events)
            except Exception as e:  # noqa: BLE001
                self.connected = False
                log.warning("headset serial error on %s: %s (retrying in 2 s)", self.port, e)
                time.sleep(2.0)
        self.connected = False

    async def stop(self) -> None:
        self._stop = True
        if self._thread_task:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._thread_task, timeout=3.0)


class MindwaveHeadset:
    """The team's `mindwave` pipeline as a Reflow headset source (TDD §3, README "EEG bridge").

    kind: "real" (MindWaveSource on a serial port), "fake" (the pipeline's FakeSource) or "replay" (ReplaySource).
    Delivers one FeatureFrame per second to `on_frame` on the asyncio loop; the SessionRuntime feeds the engine.
    """

    def __init__(
        self,
        on_frame: Callable[[object], None],
        port: str | None = None,
        fake: bool = False,
        replay_dir: str | None = None,
        replay_speed: float = 1.0,
        log_dir: str | None = None,
        fake_state: str = "easy",
    ) -> None:
        self.on_frame = on_frame
        self.kind = "fake" if fake else ("replay" if replay_dir else "real")
        self.port = port or (f"replay:{replay_dir}" if replay_dir else "fake")
        self.replay_dir = replay_dir
        self.replay_speed = replay_speed
        self.log_dir = log_dir
        self.state = fake_state
        self.pipe = None
        self.source = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.frames = 0

    # reflow sim states -> the pipeline's fake states
    _STATE_MAP = {"focused": "easy", "drifting": "drowsy", "poor": "off"}

    @property
    def connected(self) -> bool:
        return bool(self.source is not None and self.source.connected)

    async def start(self) -> None:
        from mindwave import FakeSource, MindWaveSource, Pipeline, ReplaySource

        self._loop = asyncio.get_running_loop()
        if self.kind == "fake":
            self.source = FakeSource(state=self._STATE_MAP.get(self.state, self.state))
        elif self.kind == "replay":
            self.source = ReplaySource(self.replay_dir, speed=self.replay_speed)  # type: ignore[arg-type]
        else:
            self.source = MindWaveSource(self.port)
        self.pipe = Pipeline(self.source, log_dir=(self.log_dir if self.kind == "real" else None))
        self.pipe.on_frame(self._frame_cb)
        self.pipe.start()
        log.info("mindwave headset started: %s", self.source.describe())

    def _frame_cb(self, frame) -> None:  # pipeline thread
        self.frames += 1
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self.on_frame, frame)

    def set_state(self, state: str) -> None:
        """Fake source only. Accepts reflow names (focused/drifting/poor) or the pipeline's own states."""
        mapped = self._STATE_MAP.get(state, state)
        self.state = state
        if self.kind == "fake" and self.source is not None:
            self.source.set_state(mapped)

    def calibrate(self, phase: str) -> None:
        if self.pipe is not None:
            self.pipe.calibrate(phase)

    def status(self) -> dict:
        if self.pipe is None:
            return {}
        st = self.pipe.status()
        return {
            "calibrated": st.get("calibrated"),
            "cal_phase": st.get("cal_phase"),
            "calibration_weak": st.get("calibration_weak"),
            "alpha_closed_open_ratio": st.get("alpha_closed_open_ratio"),
            "messages": st.get("messages"),
            "quality": st.get("quality"),
            "error": st.get("error"),
            "session_dir": st.get("session_dir"),
            "frames": self.frames,
        }

    async def stop(self) -> None:
        if self.pipe is not None:
            pipe = self.pipe
            self.pipe = None
            await asyncio.get_running_loop().run_in_executor(None, pipe.stop)


def make_headset(
    port_setting: str | None,
    on_events: EventCallback,
    seed: int = 11,
    on_frame: Callable[[object], None] | None = None,
    log_dir: str | None = None,
):
    """Routing (README "EEG bridge"):
    None/"auto" -> a paired MindWave through the mindwave pipeline if a port is found, else the simulator;
    "sim" -> Reflow's simulator; "fake" -> the pipeline's FakeSource; "replay:<dir>" -> the pipeline's ReplaySource;
    "serial:<port>" -> Reflow's minimal raw reader; anything else -> a device path for the mindwave pipeline.
    """
    setting = (port_setting or "auto").strip()
    if setting == "sim":
        return SimulatedHeadset(on_events, seed=seed)
    if on_frame is None:
        # no frame consumer: fall back to the raw path
        port = None if setting == "auto" else setting
        port = port or autodetect_headset_port()
        return SerialHeadset(port, on_events) if port else SimulatedHeadset(on_events, seed=seed)
    if setting == "fake":
        return MindwaveHeadset(on_frame, fake=True)
    if setting.startswith("replay:"):
        return MindwaveHeadset(on_frame, replay_dir=setting.split(":", 1)[1])
    if setting.startswith("serial:"):
        return SerialHeadset(setting.split(":", 1)[1], on_events)
    port = autodetect_headset_port() if setting == "auto" else setting
    if port:
        return MindwaveHeadset(on_frame, port=port, log_dir=log_dir)
    return SimulatedHeadset(on_events, seed=seed)
