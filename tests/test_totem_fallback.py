"""Keyboard fallback for the totem: no Arduino -> keys and the on-screen pad are the pad."""

from __future__ import annotations

import threading

import pytest

from reflow import keys
from reflow.clock import ManualClock
from reflow.core.session import SessionRuntime
from reflow.totem.bridge import KeyboardTotem, SerialTotem, SimulatedTotem, make_totem


def test_make_totem_routes_to_keyboard_without_an_arduino(monkeypatch):
    from reflow.totem import bridge

    monkeypatch.setattr(bridge, "autodetect_totem_port", lambda exclude=None: None)
    assert make_totem("auto", lambda t: None).kind == "keyboard"
    assert make_totem(None, lambda t: None).kind == "keyboard"
    assert isinstance(make_totem("keyboard", lambda t: None), KeyboardTotem)
    assert make_totem("sim", lambda t: None).kind == "keyboard"  # old name still accepted
    assert SimulatedTotem is KeyboardTotem
    monkeypatch.setattr(bridge, "autodetect_totem_port", lambda exclude=None: "/dev/cu.usbmodem2101")
    real = make_totem("auto", lambda t: None)
    assert isinstance(real, SerialTotem) and real.port == "/dev/cu.usbmodem2101"
    assert make_totem("keyboard", lambda t: None).kind == "keyboard", (
        "an explicit keyboard choice ignores the Arduino"
    )


def test_keyboard_totem_status_carries_the_hint_and_tracks_commands():
    k = KeyboardTotem(lambda t: None)
    k.send("DOT 3")
    k.send("FIT 8")
    k.send("PULSE")
    st = k.status()
    assert st["kind"] == "keyboard" and st["connected"] and st["dots"] == 3 and st["fit"] == 8
    assert "Space" in st["hint"] and k.last_pulse is not None


def test_terminal_key_listener_maps_keys(monkeypatch):
    pressed = iter([[" "], ["x", "t"], ["L"], []])
    monkeypatch.setattr(keys, "key_poller", lambda: lambda: next(pressed, []))
    taps, forces = [], []
    done = threading.Event()

    def on_tap():
        taps.append(1)
        if len(taps) == 2:
            done.set()

    stop = keys.start_key_listener(on_tap, lambda: forces.append(1), interval=0.01)
    assert stop is not None
    done.wait(2.0)
    import time

    time.sleep(0.1)
    stop.set()
    assert len(taps) == 2 and len(forces) == 1


def test_listener_is_off_without_a_tty(monkeypatch):
    monkeypatch.setattr(keys, "key_poller", lambda: None)
    assert keys.start_key_listener(lambda: None, lambda: None) is None


class _FakeSerialTotem:
    kind = "real"

    def __init__(self, port, on_tap):
        self.port, self.on_tap, self.sent, self.connected, self.dots, self.fit = port, on_tap, [], True, 0, 0

    async def start(self):
        return None

    async def stop(self):
        return None

    def send(self, line):
        self.sent.append(line)

    def status(self):
        return {
            "connected": True,
            "kind": self.kind,
            "port": self.port,
            "dots": self.dots,
            "fit": self.fit,
            "hint": None,
        }


@pytest.mark.asyncio
async def test_arduino_plugged_in_mid_session_replaces_the_keyboard_totem(settings, db, llm, monkeypatch):
    from reflow.totem import bridge

    lec = db.get_lecture("lec_demo0001", full=True)
    lrn = db.create_learner("Ana")
    sess = db.create_session(learner_id=lrn["id"], lecture_id=lec["id"], mode="live", seed=1)
    rt = SessionRuntime(
        settings,
        db,
        llm,
        sess,
        lrn,
        lec,
        "scripted",
        headset_port="sim",
        totem_port="auto",
        drive_manually=True,
    )
    rt.clock = ManualClock(0.0)
    await rt.start()
    assert rt.totem.kind == "keyboard"
    q = rt.subscribe()
    monkeypatch.setattr(bridge, "autodetect_totem_port", lambda exclude=None: "/dev/cu.usbmodem2101")
    monkeypatch.setattr(bridge, "SerialTotem", _FakeSerialTotem)
    await rt._attach_totem_if_found()
    assert rt.totem.kind == "real" and rt.totem.port == "/dev/cu.usbmodem2101"
    assert rt.totem.sent[:1] == ["CLEAR"] and any(s.startswith("DOT") for s in rt.totem.sent)
    assert db.get_session(rt.id)["totem_kind"] == "real"
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    assert any(m["type"] == "totem" and m["kind"] == "real" for m in msgs)
    assert any(m["type"] == "notice" and "attached" in m["text"] for m in msgs)
    # a pad tap from the bridge is source "tap"; the browser/terminal is "key"; neither is simulated
    rt._on_totem_tap(0.0)
    rt.tap()
    srcs = [(f["source"], f["simulated"]) for f in rt.flags.values()]
    assert srcs == [("tap", False), ("key", False)]
    await rt.end()
