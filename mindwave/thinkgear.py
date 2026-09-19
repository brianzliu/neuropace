"""ThinkGear serial protocol (NeuroSky MindWave Mobile 2).

Packet: AA AA <len> <payload> <chk>, chk = ~sum(payload) & 0xFF.
Payload rows: code < 0x80 carries one value byte; code >= 0x80 carries a length byte then data.
0x55 is EXCODE (skip). Codes used here:
    0x02 POOR_SIGNAL   0 = best contact ... 200 = electrode off the skin (1 Hz)
    0x04 ATTENTION     0-100 eSense (1 Hz)
    0x05 MEDITATION    0-100 eSense (1 Hz)
    0x80 RAW           int16 big-endian ADC counts, 512 Hz
    0x83 ASIC_EEG_POWER  8 x uint24 big-endian, arbitrary units (1 Hz):
         delta, theta, low-alpha, high-alpha, low-beta, high-beta, low-gamma, mid-gamma
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

SYNC = 0xAA
EXCODE = 0x55
POOR_SIGNAL, ATTENTION, MEDITATION, RAW, ASIC_EEG_POWER = 0x02, 0x04, 0x05, 0x80, 0x83
MAX_PAYLOAD = 169

FS = 512
# ADC counts -> microvolts. NeuroSky: 1.8 V reference / 4096 counts / gain 2000. Approximate; every
# index downstream is log- or z-scored, so this constant only labels plot axes.
UV_PER_RAW = 1.8 / 4096 / 2000 * 1e6
ASIC_BAND_NAMES = ("delta", "theta", "low_alpha", "high_alpha",
                   "low_beta", "high_beta", "low_gamma", "mid_gamma")


@dataclass(slots=True)
class Raw:
    t: float
    value: int          # ADC counts (int16)


@dataclass(slots=True)
class Quality:
    t: float
    poor_signal: int    # 0 best ... 200 no contact


@dataclass(slots=True)
class Esense:
    t: float
    attention: int
    meditation: int


@dataclass(slots=True)
class Bands:
    t: float
    values: tuple[int, ...]     # 8 ASIC band powers, order = ASIC_BAND_NAMES


@dataclass(slots=True)
class Control:
    """A calibration command replayed from a session log."""
    t: float
    phase: str


Event = Raw | Quality | Esense | Bands | Control


class PacketParser:
    """Feed bytes in any chunking; get back checksum-verified payloads."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        buf = self._buf
        buf += data
        out: list[bytes] = []
        i, total = 0, len(buf)
        while True:
            j = buf.find(b"\xaa\xaa", i)
            if j < 0:
                i = max(i, total - 1)           # keep a trailing lone 0xAA
                break
            k = j + 2
            while k < total and buf[k] == SYNC:  # extra sync bytes are allowed
                k += 1
            if k >= total:
                i = j
                break
            n = buf[k]
            if n > MAX_PAYLOAD:
                i = k
                continue
            end = k + 1 + n                     # index of the checksum byte
            if end >= total:
                i = j
                break
            payload = bytes(buf[k + 1:end])
            if (~sum(payload) & 0xFF) == buf[end]:
                out.append(payload)
                i = end + 1
            else:
                i = j + 1
        del buf[:i]
        return out


def parse_payload(payload: bytes) -> dict[int, int | bytes]:
    out: dict[int, int | bytes] = {}
    i, n = 0, len(payload)
    while i < n:
        code = payload[i]
        i += 1
        if code == EXCODE:
            continue
        if code < 0x80:
            if i < n:
                out[code] = payload[i]
            i += 1
        else:
            if i >= n:
                break
            length = payload[i]
            i += 1
            out[code] = payload[i:i + length]
            i += length
    return out


def events_from_payload(d: dict[int, int | bytes], t: float) -> list[Event]:
    ev: list[Event] = []
    raw = d.get(RAW)
    if isinstance(raw, bytes) and len(raw) == 2:
        ev.append(Raw(t, int.from_bytes(raw, "big", signed=True)))
    if POOR_SIGNAL in d:
        ev.append(Quality(t, int(d[POOR_SIGNAL])))
    if ATTENTION in d or MEDITATION in d:
        ev.append(Esense(t, int(d.get(ATTENTION, 0)), int(d.get(MEDITATION, 0))))
    bands = d.get(ASIC_EEG_POWER)
    if isinstance(bands, bytes) and len(bands) == 24:
        ev.append(Bands(t, tuple(int.from_bytes(bands[j:j + 3], "big") for j in range(0, 24, 3))))
    return ev


class ThinkGearReader(threading.Thread):
    """Reads the headset's COM port on a background thread and pushes Events into `out`.

    Reconnects every `retry_s` if the port cannot be opened or drops (headset switched off,
    out of range). `connected` is True while data has arrived in the last 3 s.
    """

    def __init__(self, port: str, out: queue.Queue, baud: int = 57600, retry_s: float = 2.0) -> None:
        super().__init__(daemon=True, name=f"thinkgear-{port}")
        self.port, self.baud, self.out, self.retry_s = port, baud, out, retry_s
        self._stop = threading.Event()
        self.last_data_t = 0.0
        self.error: str | None = None
        self.samples = 0
        self.dropped = 0

    @property
    def connected(self) -> bool:
        return time.time() - self.last_data_t < 3.0

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        import serial  # pyserial

        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as ser:
                    self.error = None
                    parser = PacketParser()
                    while not self._stop.is_set():
                        data = ser.read(max(1, ser.in_waiting))
                        if not data:
                            continue
                        t = time.time()
                        self.last_data_t = t
                        for payload in parser.feed(data):
                            for ev in events_from_payload(parse_payload(payload), t):
                                if isinstance(ev, Raw):
                                    self.samples += 1
                                try:
                                    self.out.put_nowait(ev)
                                except queue.Full:
                                    self.dropped += 1
            except (serial.SerialException, OSError) as e:
                self.error = str(e)
                self._stop.wait(self.retry_s)
