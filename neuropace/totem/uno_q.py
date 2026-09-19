"""Experimental UNO Q BLE relay. No fallback silently substitutes for real hardware.

Unverified on hardware: compile/flash, pairing, BLE permissions, encrypted access, throughput.
See `firmware/uno_q_relay/README.md` "Hardware blockers". Do not present this transport as working.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

from pydantic import BaseModel, ConfigDict, Field

SERVICE = "7d840001-8e6d-4fa5-99c7-7cf726e83b01"
EVENTS = "7d840002-8e6d-4fa5-99c7-7cf726e83b01"
COMMANDS = "7d840003-8e6d-4fa5-99c7-7cf726e83b01"


class RelayFrame(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    connected: bool
    engagement: float
    quality: int = Field(ge=0, le=200)
    valid: bool
    blink_count: int = Field(ge=0, le=100)
    effort: float | None = None
    alpha_ratio: float | None = None
    blink_rate: float | None = None
    z_effort_ema: float | None = None
    z_engagement_ema: float | None = None
    artifact_coverage: float | None = None
    calibrated: bool = False
    cal_phase: str | None = None
    attention: int | None = Field(default=None, ge=0, le=100)


class RelayHeadset:
    kind = "real"
    state = "UNO Q relay"

    def __init__(self, hub):
        self.hub = hub
        self.port = hub.port
        self.last_frame = 0.0
        self.source_connected = False

    @property
    def connected(self):
        return self.hub.connected and self.source_connected and time.monotonic() - self.last_frame < 3

    async def start(self):
        await self.hub.start()

    async def stop(self):
        await self.hub.stop()

    def calibrate(self, phase):
        self.hub.command({"type": "calibrate", "phase": phase})

    def status(self):
        return {"error": self.hub.error, "transport": "UNO Q BLE relay (experimental)"}


class UnoQRelay:
    kind = "real"

    def __init__(self, address, on_tap, on_frame):
        self.address = address
        self.port = "uno-q:" + address
        self.on_tap = on_tap
        self.on_frame = on_frame
        self.headset = RelayHeadset(self)
        self.connected = False
        self.button_ready = False
        self.error = None
        self.dots = self.fit = 0
        self._task = None
        self._buffer = bytearray()
        self._last_seq = -1
        self._commands = asyncio.Queue(maxsize=8)

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    def receive(self, _characteristic, chunk):
        self._buffer.extend(chunk)
        if len(self._buffer) > 8192:
            self._buffer.clear()
            self.error = "Relay packet too large"
            return
        while b"\n" in self._buffer:
            line, _, rest = self._buffer.partition(b"\n")
            self._buffer = bytearray(rest)
            try:
                msg = json.loads(line)
                seq = msg["seq"]
                if not isinstance(seq, int) or seq <= self._last_seq:
                    continue
                if msg["type"] == "frame":
                    frame = RelayFrame.model_validate(msg["frame"])
                    self.headset.last_frame = time.monotonic()
                    self.headset.source_connected = frame.connected
                    self.on_frame(frame)
                elif msg["type"] == "tap":
                    self.on_tap(time.monotonic())
                elif msg["type"] == "status":
                    self.button_ready = msg.get("button_ready") is True
                self._last_seq = seq
            except (ValueError, KeyError, TypeError):
                self.error = "Dropped malformed relay packet"

    async def _run(self):
        try:
            from bleak import BleakClient
        except ImportError:
            self.error = "Install the bluetooth extra: uv sync --extra bluetooth"
            return
        while True:
            try:
                self._last_seq = -1
                self._buffer.clear()
                async with BleakClient(self.address) as client:
                    await client.start_notify(EVENTS, self.receive)
                    self.connected = True
                    self.error = None
                    while client.is_connected:
                        try:
                            command = await asyncio.wait_for(self._commands.get(), 1)
                        except TimeoutError:
                            continue
                        await client.write_gatt_char(COMMANDS, json.dumps(command).encode(), response=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.error = str(exc)[:200]
            finally:
                self.connected = False
                self.button_ready = False
            await asyncio.sleep(2)

    def command(self, message):
        if not self._commands.full():
            self._commands.put_nowait(message)

    def send(self, line):
        # No public LED signalling of learner gaps. These are local UI counts only.
        if line.startswith("DOT "):
            self.dots = int(line.split()[1])
        elif line.startswith("FIT "):
            self.fit = int(line.split()[1])

    def status(self):
        return {
            "connected": self.connected and self.button_ready,
            "kind": self.kind,
            "port": self.port,
            "dots": self.dots,
            "fit": self.fit,
            "error": self.error,
            "transport": "bluetooth",
            "button_ready": self.button_ready,
        }

    async def stop(self):
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self.connected = False


async def discover():
    try:
        from bleak import BleakScanner
    except ImportError:
        return {"devices": [], "error": "Install Bluetooth support with uv sync --extra bluetooth"}
    try:
        found = await BleakScanner.discover(timeout=5, service_uuids=[SERVICE])
        return {
            "devices": [{"name": d.name or "Reflow UNO Q", "address": d.address} for d in found],
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"devices": [], "error": str(exc)[:200]}
