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


def autodetect_headset_port() -> str | None:
    for dev, desc in list_serial_ports():
        name = (dev + " " + desc).lower()
        if "mindwave" in name or "neurosky" in name or "thinkgear" in name:
            if dev.startswith("/dev/tty."):
                return dev.replace("/dev/tty.", "/dev/cu.")
            return dev
    return None


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


def make_headset(port_setting: str | None, on_events: EventCallback, seed: int = 11):
    """port_setting: None = auto-detect (simulate if none found), "sim" = simulate, else a device path."""
    if port_setting == "sim":
        return SimulatedHeadset(on_events, seed=seed)
    port = port_setting or autodetect_headset_port()
    if port:
        return SerialHeadset(port, on_events)
    return SimulatedHeadset(on_events, seed=seed)
