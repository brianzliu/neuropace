"""Cross-platform port detection without hardware: fake port listings and a fake serial module."""

from __future__ import annotations

import sys

from mindwave.ports import (
    PortInfo,
    describe_ports,
    find_headset_port,
    headset_candidates,
    normalize,
    probe_thinkgear,
)
from neuropace.signal.simulate import SimulatedEEG
from neuropace.totem.bridge import ARDUINO_VID

MAC_PORTS = [
    PortInfo("/dev/cu.debug-console", "n/a", "n/a"),
    PortInfo("/dev/cu.Bluetooth-Incoming-Port", "n/a", "n/a"),
    PortInfo("/dev/tty.MindWaveMobile-SerialPo", "n/a", "n/a"),
    PortInfo("/dev/cu.usbmodem2101", "Arduino UNO R4 WiFi", "USB VID:PID=2341:1002", 0x2341, 0x1002),
]
WIN_PORTS = [
    PortInfo("COM1", "Communications Port (COM1)", "ACPI\\PNP0501\\1"),
    PortInfo(
        "COM3",
        "Standard Serial over Bluetooth link (COM3)",
        "BTHENUM\\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0000\\7&1A2B3C4D&0&000000000000_00000000",
    ),
    PortInfo(
        "COM4",
        "Standard Serial over Bluetooth link (COM4)",
        "BTHENUM\\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&000F\\7&1A2B3C4D&0&E0E5CF12345_C00000000",
    ),
    PortInfo("COM5", "USB Serial Device (COM5)", "USB VID:PID=2341:1002\\ABCDEF", 0x2341, 0x1002),
]


class _FakeSerial:
    """Serial stand-in: COM4 streams ThinkGear packets, everything else is silent."""

    stream = SimulatedEEG(seed=9).next_bytes(2048, with_status=True)

    def __init__(self, port, baud, timeout=0.2):
        self.port = port
        self.pos = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        if self.port != "COM4":
            return b""
        chunk = self.stream[self.pos : self.pos + n]
        self.pos += n
        return chunk


class FakeSerialModule:
    Serial = _FakeSerial


def test_named_port_wins_on_macos_and_tty_maps_to_cu(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    named, bluetooth = headset_candidates(MAC_PORTS)
    assert named == ["/dev/cu.MindWaveMobile-SerialPo"] and bluetooth == []
    assert find_headset_port(probe=False, ports=MAC_PORTS) == "/dev/cu.MindWaveMobile-SerialPo"
    assert normalize("/dev/tty.X") == "/dev/cu.X"


def test_windows_bluetooth_ports_are_probed_and_the_outgoing_one_is_found(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    named, bluetooth = headset_candidates(WIN_PORTS)
    assert named == [] and bluetooth == ["COM3", "COM4"]
    assert find_headset_port(probe=False, ports=WIN_PORTS) is None, "never guess without probing"
    assert (
        find_headset_port(probe=True, ports=WIN_PORTS, serial_module=FakeSerialModule, probe_seconds=0.3)
        == "COM4"
    )


def test_probe_rejects_silent_and_unopenable_ports():
    assert probe_thinkgear("COM3", seconds=0.2, serial_module=FakeSerialModule) is False

    class Broken:
        class Serial:
            def __init__(self, *a, **k):
                raise OSError("busy")

    assert probe_thinkgear("COM4", seconds=0.2, serial_module=Broken) is False
    assert "COM4" in describe_ports(WIN_PORTS)


def test_totem_autodetect_uses_arduino_vid_on_windows_and_skips_bluetooth(monkeypatch):
    from serial.tools import list_ports

    from neuropace.totem import bridge

    class P:
        def __init__(self, info):
            self.device, self.description, self.hwid, self.vid, self.pid = (
                info.device,
                info.description,
                info.hwid,
                info.vid,
                info.pid,
            )

    monkeypatch.setattr(list_ports, "comports", lambda: [P(i) for i in WIN_PORTS])
    assert bridge.autodetect_totem_port(exclude="COM4") == "COM5"
    monkeypatch.setattr(list_ports, "comports", lambda: [P(i) for i in MAC_PORTS])
    assert bridge.autodetect_totem_port(exclude="/dev/cu.MindWaveMobile-SerialPo") == "/dev/cu.usbmodem2101"
    assert ARDUINO_VID == 0x2341
