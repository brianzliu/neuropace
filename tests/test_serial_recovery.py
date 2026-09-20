"""Serial liveness must mean valid packets, and silence must recover without restarting the app."""

import queue
import time

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
