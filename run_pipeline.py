"""Run the MindWave signal pipeline as a service.

Prints one line per second, serves the WebSocket feed on ws://127.0.0.1:8765 and logs the
session to sessions/<stamp>/ (raw.int16, events.jsonl, features.jsonl).

    python run_pipeline.py                                   # live headset, port found automatically
    python run_pipeline.py --port COM4                       # or name it (COMn, /dev/cu.MindWave..., /dev/rfcomm0)
    python run_pipeline.py --fake                            # synthetic EEG, no headset
    python run_pipeline.py --replay sessions/<stamp> --speed 4
    python run_pipeline.py --no-ws --no-log

Keys (any terminal):  1 eyes_closed  2 easy  3 hard  0 done  r reset  a auto-calibrate
                      fake source: c closed  e easy  h hard  d drowsy  o off-head  b blink
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from mindwave import FakeSource, MindWaveSource, Pipeline, ReplaySource
from mindwave.keys import KEY_HELP, apply_key
from mindwave.ports import describe_ports, find_headset_port


def add_source_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--port", default="auto", help="the headset's serial port (default: find it; COMn on Windows, /dev/cu.MindWave... on macOS)")
    ap.add_argument("--fake", action="store_true", help="synthetic EEG instead of the headset")
    ap.add_argument("--replay", metavar="DIR", help="replay a recorded session directory")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed; 0 = as fast as possible")
    ap.add_argument("--no-log", action="store_true", help="do not record this session")
    ap.add_argument("--log-dir", default="sessions")


def build_source(args):
    if args.fake:
        return FakeSource()
    if args.replay:
        return ReplaySource(args.replay, speed=args.speed)
    port = args.port
    if port == "auto":
        port = find_headset_port()
        if port is None:
            print("no MindWave port found (is the headset on and paired?). Serial ports:\n" + describe_ports()
                  + "\nName it with --port, or use --fake / --replay.")
            sys.exit(2)
    return MindWaveSource(port)


def log_dir_for(args):
    """Synthetic and replayed runs are never worth recording."""
    return None if (args.no_log or args.replay or args.fake) else args.log_dir


def _num(v, width=6):
    return f"{v:+{width}.2f}" if v is not None else " " * (width - 1) + "-"


def _int(v, width=3):
    return f"{v:{width}d}" if v is not None else " " * (width - 1) + "-"


def print_frame(f) -> None:
    stamp = time.strftime("%H:%M:%S", time.localtime(f.t))
    cal = f.cal_phase or ("cal" + ("(weak)" if f.calibration_weak else "") if f.calibrated else "uncal")
    print(f"{stamp} q={f.quality:3d} {'ok ' if f.valid else 'BAD'} "
          f"eff={f.effort:+.2f} eng={f.engagement:+.2f} "
          f"z_eff={_num(f.z_effort_ema)} z_eng={_num(f.z_engagement_ema)} "
          f"blink/min={f.blink_rate:4.1f} att={_int(f.attention)} med={_int(f.meditation)} {cal}", flush=True)


def key_poller():
    """Non-blocking single-key reader: msvcrt on Windows, termios cbreak on macOS/Linux; None without a tty."""
    if os.name == "nt":
        try:
            import msvcrt
        except ImportError:
            return None

        def poll_nt():
            keys = []
            while msvcrt.kbhit():
                keys.append(msvcrt.getwch())
            return keys

        return poll_nt
    if not sys.stdin.isatty():
        return None
    import atexit
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old))

    def poll_posix():
        keys = []
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if not ch:
                break
            keys.append(ch)
        return keys

    return poll_posix


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_source_args(ap)
    ap.add_argument("--no-ws", action="store_true", help="do not serve the WebSocket feed")
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--quiet", action="store_true", help="do not print frames")
    args = ap.parse_args()

    source = build_source(args)
    pipe = Pipeline(source, log_dir=log_dir_for(args))
    if not args.quiet:
        pipe.on_frame(print_frame)
    if not args.no_ws:
        pipe.serve(port=args.ws_port)
    pipe.start()
    print(f"source: {source.describe()}   log: {pipe.session_dir or 'off'}")
    poll = key_poller()
    print(KEY_HELP if poll else "(no interactive terminal: keyboard control off)")
    try:
        while True:
            if poll:
                for k in poll():
                    msg = apply_key(k, pipe, source)
                    if msg:
                        print(f"[key] {msg}", flush=True)
            if isinstance(source, ReplaySource) and not source.connected:
                print("replay finished")
                break
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        pipe.stop()


if __name__ == "__main__":
    main()
