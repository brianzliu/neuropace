"""Totem bridge (TDD §4): UNO R4 over USB serial, or a simulator. Line protocol, 115200 baud."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

log = logging.getLogger(__name__)

TOTEM_BAUD = 115200
TapCallback = Callable[[float], None]  # called with wall-clock monotonic time of the tap


def autodetect_totem_port(exclude: str | None = None) -> str | None:
    from .._ports import list_serial_ports

    for dev, desc in list_serial_ports():
        name = (dev + " " + desc).lower()
        if dev == exclude:
            continue
        if ("usbmodem" in name or "arduino" in name or "uno" in name) and "mindwave" not in name:
            if dev.startswith("/dev/tty."):
                return dev.replace("/dev/tty.", "/dev/cu.")
            return dev
    return None


class SimulatedTotem:
    kind = "simulated"

    def __init__(self, on_tap: TapCallback) -> None:
        self.on_tap = on_tap
        self.port = "sim"
        self.connected = True
        self.dots = 0
        self.fit = 0
        self.last_pulse: float | None = None
        self.sent: list[str] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def send(self, line: str) -> None:
        self.sent.append(line)
        parts = line.split()
        if parts and parts[0] == "DOT" and len(parts) > 1:
            self.dots = int(parts[1])
        elif parts and parts[0] == "FIT" and len(parts) > 1:
            self.fit = int(parts[1])
        elif parts and parts[0] == "PULSE":
            self.last_pulse = time.monotonic()
        elif parts and parts[0] == "CLEAR":
            self.dots, self.fit = 0, 0

    def status(self) -> dict:
        return {"connected": True, "kind": self.kind, "port": self.port, "dots": self.dots, "fit": self.fit}


class SerialTotem:
    kind = "real"

    def __init__(self, port: str, on_tap: TapCallback, baud: int = TOTEM_BAUD) -> None:
        self.port = port
        self.baud = baud
        self.on_tap = on_tap
        self.connected = False
        self.dots = 0
        self.fit = 0
        self.board = "?"
        self._stop = False
        self._ser = None
        self._task: asyncio.Task | None = None
        self._outq: list[str] = []

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._task = loop.run_in_executor(None, self._io, loop)

    def _io(self, loop: asyncio.AbstractEventLoop) -> None:
        import serial

        while not self._stop:
            try:
                with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
                    self._ser = ser
                    time.sleep(1.5)  # the R4 resets on open
                    ser.write(b"PING\n")
                    self.connected = True
                    log.info("totem connected on %s", self.port)
                    buf = b""
                    while not self._stop:
                        while self._outq:
                            ser.write((self._outq.pop(0) + "\n").encode())
                        chunk = ser.read(64)
                        if not chunk:
                            continue
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            self._handle(line.decode(errors="ignore").strip(), loop)
            except Exception as e:  # noqa: BLE001
                self.connected = False
                self._ser = None
                log.warning("totem serial error on %s: %s (retrying in 2 s)", self.port, e)
                time.sleep(2.0)
        self.connected = False

    def _handle(self, line: str, loop: asyncio.AbstractEventLoop) -> None:
        if not line:
            return
        parts = line.split()
        if parts[0] == "TAP":
            loop.call_soon_threadsafe(self.on_tap, time.monotonic())
        elif parts[0] == "HELLO" and len(parts) >= 4:
            self.board = parts[3]
        elif parts[0] in ("PONG", "TOUCH"):
            return
        else:
            log.debug("totem: %s", line)

    def send(self, line: str) -> None:
        parts = line.split()
        if parts and parts[0] == "DOT" and len(parts) > 1:
            self.dots = int(parts[1])
        elif parts and parts[0] == "FIT" and len(parts) > 1:
            self.fit = int(parts[1])
        elif parts and parts[0] == "CLEAR":
            self.dots, self.fit = 0, 0
        self._outq.append(line)

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "kind": self.kind,
            "port": self.port,
            "dots": self.dots,
            "fit": self.fit,
        }

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._task, timeout=3.0)


def make_totem(port_setting: str | None, on_tap: TapCallback, exclude_port: str | None = None):
    if port_setting == "sim":
        return SimulatedTotem(on_tap)
    port = port_setting or autodetect_totem_port(exclude=exclude_port)
    if port:
        return SerialTotem(port, on_tap)
    return SimulatedTotem(on_tap)
