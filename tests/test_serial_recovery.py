"""Serial liveness must mean valid packets, and silence must recover without restarting the app."""

import queue
import sys
import threading
import time
from types import SimpleNamespace

from mindwave.thinkgear import ThinkGearReader
from neuropace.signal.thinkgear import encode_raw


def test_reader_reopens_silent_link_and_stop_releases_port(monkeypatch):
    import serial

    now = [0.0]
    monkeypatch.setattr("mindwave.thinkgear.time.monotonic", lambda: now[0])
    opens = []

    class Port:
        in_waiting = 8

        def __init__(self, *args, **kwargs):
            self.index = len(opens)
            self.closed = False
            opens.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def read(self, n):
            time.sleep(0.002)
            if self.index == 0:
                now[0] += 2
                return b"garbage"  # noise cannot keep the connection alive
            return encode_raw(123)

        def cancel_read(self):
            pass

    monkeypatch.setattr(serial, "Serial", Port)
    out = queue.Queue()
    reader = ThinkGearReader("test", out, retry_s=0.001)
    reader.start()
    try:
        sample = out.get(timeout=2)
        assert sample.value == 123
        assert len(opens) >= 2 and opens[0].closed
        assert reader.connected
    finally:
        reader.stop()
    assert not reader.is_alive() and all(p.closed for p in opens)


def test_native_reader_allows_slow_first_packet_then_recovers_stall(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("mindwave.thinkgear.time.monotonic", lambda: now[0])
    opens = []
    waiting = threading.Event()
    cancelled = threading.Event()

    class Port:
        in_waiting = 8

        def __init__(self, *args, **kwargs):
            self.index = len(opens)
            self.opened_at = now[0]
            self.closed_at = None
            opens.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed_at = now[0]

        def read(self, n):
            if self.index < 2:
                now[0] += 2
                if self.index == 0 and now[0] - self.opened_at == 16:
                    return encode_raw(123)
                return b"garbage"
            waiting.set()
            cancelled.wait(timeout=2)
            return b""

        def cancel_read(self):
            cancelled.set()

    monkeypatch.setitem(sys.modules, "mindwave.macos_transport", SimpleNamespace(MacRFCOMMTransport=Port))
    out = queue.Queue()
    reader = ThinkGearReader("test", out, retry_s=0.001)
    reader.transport = "native Bluetooth"
    reader.start()
    try:
        assert waiting.wait(timeout=2)
        assert len(opens) == 3
        assert opens[0].closed_at - opens[0].opened_at == 22
        assert out.get_nowait().value == 123
        assert out.empty()
        assert opens[1].closed_at - opens[1].opened_at == 32
    finally:
        reader.stop()
    assert cancelled.is_set()
    assert not reader.is_alive() and all(p.closed_at is not None for p in opens)
