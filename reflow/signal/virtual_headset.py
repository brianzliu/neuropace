"""A MindWave you can plug in without hardware: real ThinkGear bytes on a pseudo-terminal (macOS and Linux).

The app cannot tell it from the headset. The server opens the pty's slave path as a serial port
(REFLOW_HEADSET_PORT=/dev/ttysNNN), the pipeline's ThinkGearReader parses the same 0xAA 0xAA packets, and every layer
above sees a headset of kind "real": no simulated flag, no practice badge. The signal is the pipeline's FakeSource
(alpha, theta and beta sinusoids on pink noise, blinks, wearer states) encoded exactly as the headset encodes it: one
0x80 raw packet per sample at 512 Hz, and one status packet per second (0x02 poor_signal, 0x04 attention,
0x05 meditation, 0x83 eight-band EEG power).

Control, for demos and tests: a control file whose content is one command, read every quarter second:
  state <easy|hard|drowsy|eyes_closed|off>   the wearer's state ("off" = electrode off the skin, poor_signal 200)
  blink                                       one blink
  pause <seconds>                             stop sending for that long (a Bluetooth dropout, then recovery)
Windows has no pty: use headset "fake" (the same signal, in-process) or a com0com pair with this writer's bytes.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from .thinkgear import encode_raw, encode_status

_BAND_NAMES = ("delta", "theta", "low_alpha", "high_alpha", "low_beta", "high_beta", "low_gamma", "mid_gamma")


class VirtualHeadset:
    def __init__(self, state: str = "easy", control_path: str | None = None, seed: int = 0) -> None:
        self.state = state
        self.control_path = Path(control_path) if control_path else None
        self.seed = seed
        self.path: str | None = None
        self.master: int | None = None
        self._slave: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.bytes_sent = 0
        self.bytes_dropped = 0
        self.samples = 0
        self.paused_until = 0.0
        self.source = None
        self.log = print

    # ---- lifecycle ----
    def open(self) -> str:
        if sys.platform == "win32":  # pragma: no cover
            raise RuntimeError("virtual headset needs a pty; on Windows use headset 'fake'")
        import pty
        import tty

        self.master, self._slave = pty.openpty()
        tty.setraw(self._slave)
        os.set_blocking(self.master, False)
        self.path = os.ttyname(self._slave)
        return self.path

    def start(self) -> str:
        if self.path is None:
            self.open()
        self._thread = threading.Thread(target=self.run, daemon=True, name="virtual-headset")
        self._thread.start()
        return self.path  # type: ignore[return-value]

    def stop(self) -> None:
        self._stop.set()
        if self.source is not None:
            self.source.stop()
        if self._thread is not None:
            self._thread.join(timeout=3)
        for fd in (self.master, self._slave):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.master = self._slave = None

    # ---- the wire ----
    def _write(self, data: bytes) -> None:
        if self.master is None:
            return
        if time.monotonic() < self.paused_until:
            self.bytes_dropped += len(data)
            return
        try:
            n = os.write(self.master, data)
            self.bytes_sent += n
            if n < len(data):  # the reader is behind: a real link would drop these too
                self.bytes_dropped += len(data) - n
        except BlockingIOError:
            self.bytes_dropped += len(data)  # nobody is reading yet
        except OSError:
            self.bytes_dropped += len(data)

    def _control(self) -> None:
        if self.control_path is None or not self.control_path.exists():
            return
        try:
            cmd = self.control_path.read_text(encoding="utf-8").strip()
            self.control_path.unlink()
        except OSError:
            return
        if not cmd:
            return
        self.command(cmd)

    def command(self, cmd: str) -> None:
        parts = cmd.split()
        if not parts:
            return
        if parts[0] == "state" and len(parts) > 1 and self.source is not None:
            try:
                self.source.set_state(parts[1])
                self.state = parts[1]
                self.log(f"[virtual headset] state -> {parts[1]}")
            except ValueError as e:
                self.log(f"[virtual headset] {e}")
        elif parts[0] == "blink" and self.source is not None:
            self.source.blink()
            self.log("[virtual headset] blink")
        elif parts[0] == "pause" and len(parts) > 1:
            secs = float(parts[1])
            self.paused_until = time.monotonic() + secs
            self.log(f"[virtual headset] pause {secs:.0f} s (no bytes on the wire)")
        else:
            self.log(f"[virtual headset] unknown command {cmd!r}")

    def run(self) -> None:
        """Encode FakeSource events as they come (real-time paced) and push them down the pty."""
        from mindwave.sources import FakeSource
        from mindwave.thinkgear import Bands, Esense, Quality, Raw

        self.source = FakeSource(state=self.state, realtime=True, seed=self.seed)
        buf = bytearray()
        quality, attention, meditation = 0, 50, 50
        bands: dict[str, int] | None = None
        pending_status = False
        next_control = time.monotonic()
        for ev in self.source.events():
            if self._stop.is_set():
                break
            if isinstance(ev, Raw):
                buf += encode_raw(ev.value)
                self.samples += 1
                if len(buf) >= 8 * 32:  # a 62.5 ms block, like a Bluetooth SPP burst
                    self._write(bytes(buf))
                    buf.clear()
            elif isinstance(ev, Quality):
                quality = ev.poor_signal
                pending_status = True
            elif isinstance(ev, Esense):
                attention, meditation = ev.attention, ev.meditation
                pending_status = True
            elif isinstance(ev, Bands):
                bands = dict(zip(_BAND_NAMES, ev.values, strict=False))
                pending_status = True
            if pending_status and isinstance(ev, Bands):
                buf += encode_status(quality, attention, meditation, eeg_power=bands)
                pending_status = False
            now = time.monotonic()
            if now >= next_control:
                next_control = now + 0.25
                self._control()
        if buf:
            self._write(bytes(buf))


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="a MindWave on a pseudo-terminal (see the module docstring)")
    p.add_argument("--state", default="easy", help="easy | hard | drowsy | eyes_closed | off")
    p.add_argument("--control", help="control file path (state/blink/pause commands)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--port-file", help="write the device path here for scripts")
    args = p.parse_args(argv)
    vh = VirtualHeadset(state=args.state, control_path=args.control, seed=args.seed)
    path = vh.start()
    if args.port_file:
        Path(args.port_file).write_text(path + "\n", encoding="utf-8")
    print(f"virtual headset on {path}")
    print(f"  serve with:  REFLOW_HEADSET_PORT={path} uv run reflow serve")
    if args.control:
        print(f"  control:     echo 'state drowsy' > {args.control}   (state | blink | pause <s>)")
    try:
        while True:
            time.sleep(5)
            print(
                f"  sent {vh.bytes_sent / 1024:.0f} KiB, dropped {vh.bytes_dropped / 1024:.0f} KiB, "
                f"state {vh.state}",
                flush=True,
            )
    except KeyboardInterrupt:
        pass
    finally:
        vh.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
