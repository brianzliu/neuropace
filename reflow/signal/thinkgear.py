"""ThinkGear stream parser and encoder (TDD §3.1).

Framing: 0xAA 0xAA <len <= 169> <payload> <checksum>, checksum = (~sum(payload)) & 0xFF.
Rows: codes < 0x80 carry one value byte; codes >= 0x80 carry a length byte then data.
0x55 EXCODE prefixes are honoured (rows with an EXCODE level > 0 are ignored, as the spec allows).
"""

from __future__ import annotations

from dataclasses import dataclass

SYNC = 0xAA
EXCODE = 0x55
MAX_PAYLOAD = 169

CODE_POOR_SIGNAL = 0x02
CODE_ATTENTION = 0x04
CODE_MEDITATION = 0x05
CODE_BLINK = 0x16
CODE_RAW = 0x80
CODE_EEG_POWER = 0x83

EEG_POWER_BANDS = (
    "delta",
    "theta",
    "low_alpha",
    "high_alpha",
    "low_beta",
    "high_beta",
    "low_gamma",
    "mid_gamma",
)


@dataclass(slots=True)
class TGEvent:
    kind: str  # raw | poor_signal | attention | meditation | blink | eeg_power
    value: int | dict[str, int]


class ThinkGearParser:
    """Incremental parser. Feed arbitrary byte chunks, get decoded events back in order."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.packets = 0
        self.bad_checksums = 0
        self.resyncs = 0

    def feed(self, data: bytes) -> list[TGEvent]:
        self._buf.extend(data)
        events: list[TGEvent] = []
        buf = self._buf
        i = 0
        n = len(buf)
        while True:
            # find sync pair
            j = buf.find(b"\xaa\xaa", i)
            if j < 0:
                # keep a trailing 0xAA in case the pair is split across chunks
                keep = 1 if n and buf[-1] == SYNC else 0
                i = n - keep
                break
            if j > i:
                self.resyncs += 1
            k = j + 2
            # skip any extra sync bytes
            while k < n and buf[k] == SYNC:
                k += 1
            if k >= n:
                i = j
                break
            plen = buf[k]
            if plen > MAX_PAYLOAD:
                self.resyncs += 1
                i = k
                continue
            end = k + 1 + plen + 1
            if end > n:
                i = j  # wait for more bytes
                break
            payload = buf[k + 1 : k + 1 + plen]
            chk = buf[k + 1 + plen]
            if ((~sum(payload)) & 0xFF) != chk:
                self.bad_checksums += 1
                i = j + 2
                continue
            events.extend(self._parse_payload(payload))
            self.packets += 1
            i = end
        del buf[:i]
        return events

    @staticmethod
    def _parse_payload(payload: bytearray) -> list[TGEvent]:
        out: list[TGEvent] = []
        i = 0
        n = len(payload)
        while i < n:
            ex = 0
            while i < n and payload[i] == EXCODE:
                ex += 1
                i += 1
            if i >= n:
                break
            code = payload[i]
            i += 1
            if code >= 0x80:
                if i >= n:
                    break
                length = payload[i]
                i += 1
            else:
                length = 1
            data = payload[i : i + length]
            i += length
            if ex > 0 or len(data) != length:
                continue
            if code == CODE_RAW and length == 2:
                out.append(TGEvent("raw", int.from_bytes(data, "big", signed=True)))
            elif code == CODE_POOR_SIGNAL:
                out.append(TGEvent("poor_signal", data[0]))
            elif code == CODE_ATTENTION:
                out.append(TGEvent("attention", data[0]))
            elif code == CODE_MEDITATION:
                out.append(TGEvent("meditation", data[0]))
            elif code == CODE_BLINK:
                out.append(TGEvent("blink", data[0]))
            elif code == CODE_EEG_POWER and length == 24:
                vals = {
                    band: int.from_bytes(data[3 * b : 3 * b + 3], "big")
                    for b, band in enumerate(EEG_POWER_BANDS)
                }
                out.append(TGEvent("eeg_power", vals))
        return out


def encode_packet(rows: list[tuple[int, bytes]]) -> bytes:
    """Build one ThinkGear packet from (code, data) rows."""
    payload = bytearray()
    for code, data in rows:
        payload.append(code)
        if code >= 0x80:
            payload.append(len(data))
        payload.extend(data)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too long")
    chk = (~sum(payload)) & 0xFF
    return bytes([SYNC, SYNC, len(payload)]) + bytes(payload) + bytes([chk])


def encode_raw(value: int) -> bytes:
    v = max(-32768, min(32767, int(value)))
    return encode_packet([(CODE_RAW, v.to_bytes(2, "big", signed=True))])


def encode_status(
    poor_signal: int, attention: int = 0, meditation: int = 0, eeg_power: dict | None = None
) -> bytes:
    rows: list[tuple[int, bytes]] = [
        (CODE_POOR_SIGNAL, bytes([max(0, min(200, poor_signal))])),
        (CODE_ATTENTION, bytes([max(0, min(100, attention))])),
        (CODE_MEDITATION, bytes([max(0, min(100, meditation))])),
    ]
    if eeg_power:
        data = b"".join(int(eeg_power.get(b, 0)).to_bytes(3, "big") for b in EEG_POWER_BANDS)
        rows.append((CODE_EEG_POWER, data))
    return encode_packet(rows)
