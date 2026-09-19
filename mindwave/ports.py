"""Find the headset's serial port on macOS, Windows and Linux.

macOS   the paired MindWave shows up as /dev/cu.MindWaveMobile-SerialPo (the device name is in the
        port name), so a name match is enough. /dev/tty.* twins are mapped to /dev/cu.*.
Windows paired SPP devices are listed as "Standard Serial over Bluetooth link (COMn)" with a BTHENUM
        hardware id and NO device name, and there are two ports per device (incoming/outgoing) of
        which only the outgoing one delivers data. Candidates are therefore probed: open, read for a
        moment, and look for checksum-valid ThinkGear packets.
Linux   /dev/rfcomm0 after `rfcomm bind`; name match.

`find_headset_port()` is the one entry point; pass `probe=False` to avoid opening ports.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from .thinkgear import PacketParser, RAW, parse_payload

HEADSET_NAMES = ("mindwave", "neurosky", "thinkgear")
PROBE_SECONDS = 1.5
PROBE_MIN_PACKETS = 3


@dataclass
class PortInfo:
    device: str
    description: str = ""
    hwid: str = ""
    vid: int | None = None
    pid: int | None = None

    @property
    def text(self) -> str:
        return f"{self.device} {self.description} {self.hwid}".lower()


def normalize(device: str) -> str:
    """macOS lists both /dev/tty.X and /dev/cu.X; the cu (call-out) device is the one to open."""
    if sys.platform == "darwin" and device.startswith("/dev/tty."):
        return "/dev/cu." + device[len("/dev/tty."):]
    return device


def list_serial_ports() -> list[PortInfo]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    out: list[PortInfo] = []
    for p in list_ports.comports():
        out.append(PortInfo(p.device, p.description or "", p.hwid or "", getattr(p, "vid", None), getattr(p, "pid", None)))
    return out


def headset_candidates(ports: list[PortInfo]) -> tuple[list[str], list[str]]:
    """(named, bluetooth): ports that carry the headset's name, and anonymous Bluetooth serial ports
    worth probing (Windows BTHENUM, Linux rfcomm). The Mac's own Bluetooth-Incoming-Port is excluded."""
    named: list[str] = []
    bluetooth: list[str] = []
    for p in ports:
        t = p.text
        dev = normalize(p.device)
        if any(n in t for n in HEADSET_NAMES):
            if dev not in named:
                named.append(dev)
        elif "bthenum" in t or dev.startswith("/dev/rfcomm"):
            if dev not in bluetooth:
                bluetooth.append(dev)
    return named, bluetooth


def probe_thinkgear(port: str, seconds: float = PROBE_SECONDS, baud: int = 57600, serial_module=None) -> bool:
    """True if checksum-valid ThinkGear packets with RAW rows arrive on `port` within `seconds`."""
    ser_mod = serial_module
    if ser_mod is None:
        try:
            import serial as ser_mod
        except ImportError:
            return False
    parser = PacketParser()
    packets = 0
    try:
        with ser_mod.Serial(port, baud, timeout=0.2) as ser:
            t_end = time.monotonic() + seconds
            while time.monotonic() < t_end:
                data = ser.read(256)
                if not data:
                    continue
                for payload in parser.feed(data):
                    if RAW in parse_payload(payload):
                        packets += 1
                        if packets >= PROBE_MIN_PACKETS:
                            return True
    except Exception:
        return False
    return packets >= PROBE_MIN_PACKETS


def find_headset_port(probe: bool = True, ports: list[PortInfo] | None = None, serial_module=None,
                      probe_seconds: float = PROBE_SECONDS) -> str | None:
    """The headset's port, or None. Named ports win; anonymous Bluetooth ports are probed (needs the
    headset switched on and paired). With probe=False only a named port is returned."""
    ports = list_serial_ports() if ports is None else ports
    named, bluetooth = headset_candidates(ports)
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        if probe:
            for dev in named:
                if probe_thinkgear(dev, probe_seconds, serial_module=serial_module):
                    return dev
        return named[0]
    if probe:
        for dev in bluetooth:
            if probe_thinkgear(dev, probe_seconds, serial_module=serial_module):
                return dev
    return None


def describe_ports(ports: list[PortInfo] | None = None) -> str:
    ports = list_serial_ports() if ports is None else ports
    if not ports:
        return "no serial ports found"
    return "\n".join(f"  {p.device:32s} {p.description}  [{p.hwid}]" for p in ports)
