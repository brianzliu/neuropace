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


ARDUINO_VID = 0x2341
# also: Arduino.org-era UNOs and the CH340 USB-serial chip on classic UNO clones (Windows: "USB-SERIAL CH340")
BOARD_VIDS = {ARDUINO_VID, 0x2A03, 0x1A86}


def autodetect_totem_port(exclude: str | None = None) -> str | None:
    """An Arduino by USB vendor id (Windows shows only "USB Serial Device (COMn)"), or by name on macOS/Linux."""
    try:
        from serial.tools import list_ports
    except ImportError:  # pragma: no cover
        return None
    for p in list_ports.comports():
        dev = p.device
        if dev.startswith("/dev/tty."):
            dev = "/dev/cu." + dev[len("/dev/tty.") :]
        if exclude and dev == exclude:
            continue
        text = f"{dev} {p.description or ''} {p.hwid or ''}".lower()
        if "mindwave" in text or "bthenum" in text:
            continue
        if (
            getattr(p, "vid", None) in BOARD_VIDS
            or "usbmodem" in text
            or "arduino" in text
            or " uno" in f" {text}"
        ):
            return dev
    return None


class KeyboardTotem:
    """Fallback when no Arduino is plugged in: taps come from the keyboard (Space or T in the browser or in the
    terminal running `neuropace serve`) or the on-screen pad button. A key tap is a real learner action, not a simulation."""

    kind = "keyboard"
    hint = "no Arduino: press Space or T, or use the on-screen pad"

    def __init__(self, on_tap: TapCallback) -> None:
        self.on_tap = on_tap
        self.port = "keyboard"
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
        return {
            "connected": True,
            "kind": self.kind,
            "port": self.port,
            "dots": self.dots,
            "fit": self.fit,
            "hint": self.hint,
        }


class SerialTotem:
    """Any board that prints "TAP" (optionally followed by a count / millis) once per press: firmware/totem and
    firmware/button_test both do. Commands we send (DOT / FIT / PULSE / CLEAR) may be ignored by the firmware."""

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
    """None/"auto" -> an Arduino if one is plugged in, else the keyboard fallback; "keyboard" (or the old "sim")
    -> keyboard; anything else -> a serial port path."""
    setting = (port_setting or "auto").strip()
    if setting in ("keyboard", "sim"):
        return KeyboardTotem(on_tap)
    port = autodetect_totem_port(exclude=exclude_port) if setting == "auto" else setting
    if port:
        return SerialTotem(port, on_tap)
    return KeyboardTotem(on_tap)


SimulatedTotem = KeyboardTotem  # old name
