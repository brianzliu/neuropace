"""Terminal keys for `reflow serve`: the keyboard totem without a browser (Space/T = lost me, L = force flag).

Windows uses msvcrt; macOS and Linux put the tty in cbreak mode. Nothing starts unless stdin is an interactive
terminal, so tests, services and `--reload` workers are unaffected.
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable

KEY_TAP = {" ", "t", "T"}
KEY_FORCE = {"l", "L"}


def key_poller() -> Callable[[], list[str]] | None:
    if os.name == "nt":
        try:
            import msvcrt
        except ImportError:  # pragma: no cover
            return None

        def poll_nt() -> list[str]:
            keys = []
            while msvcrt.kbhit():
                keys.append(msvcrt.getwch())
            return keys

        return poll_nt
    try:
        if not sys.stdin.isatty():
            return None
    except (AttributeError, ValueError):
        return None
    import atexit
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old))

    def poll_posix() -> list[str]:
        keys = []
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if not ch:
                break
            keys.append(ch)
        return keys

    return poll_posix


def start_key_listener(
    on_tap: Callable[[], None], on_force: Callable[[], None], interval: float = 0.05
) -> threading.Event | None:
    """Poll the terminal on a daemon thread; returns a stop event, or None when there is no interactive terminal."""
    poll = key_poller()
    if poll is None:
        return None
    stop = threading.Event()

    def run() -> None:
        while not stop.is_set():
            for k in poll():
                if k in KEY_TAP:
                    on_tap()
                elif k in KEY_FORCE:
                    on_force()
            stop.wait(interval)

    threading.Thread(target=run, daemon=True, name="reflow-keys").start()
    return stop
