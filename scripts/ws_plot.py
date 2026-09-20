"""Live EEG trace from a remote pipeline's WebSocket feed — the "serial plotter" for the UNO Q.

    adb forward tcp:8766 tcp:8765                      # USB: the Q's :8765 appears on the laptop's :8766
    uv run --group monitor python scripts/ws_plot.py ws://127.0.0.1:8766
    uv run --group monitor python scripts/ws_plot.py ws://192.168.137.50:8765   # over the hotspot instead

Draws the pipeline's 64 Hz decimated trace ("raw" messages), marks blinks, and shows the last
frame's quality / validity / blink rate in the title. Ctrl-C or close the window to stop.
"""
from __future__ import annotations

import json
import sys
import threading
from collections import deque

import matplotlib.pyplot as plt
import numpy as np

SECONDS = 8
FS_TRACE = 64


def main(url: str) -> None:
    from websockets.sync.client import connect

    buf: deque[float] = deque([0.0] * SECONDS * FS_TRACE, maxlen=SECONDS * FS_TRACE)
    state = {"title": "waiting for frames…", "blink_at": 0, "n": 0, "alive": True}
    lock = threading.Lock()

    def reader() -> None:
        while state["alive"]:
            try:
                with connect(url) as ws:
                    print(f"connected to {url}")
                    for raw in ws:
                        msg = json.loads(raw)
                        t = msg.get("type")
                        with lock:
                            if t == "raw":
                                buf.extend(msg["uv"])
                                state["n"] += len(msg["uv"])
                            elif t == "features":
                                q, ok, br = msg["quality"], msg["valid"], msg["blink_rate"]
                                state["title"] = (f"quality={q} ({'ok' if ok else 'BAD'})   "
                                                  f"blink/min={br:.1f}   effort={msg['effort']:+.2f}   "
                                                  f"{'calibrated' if msg['calibrated'] else 'uncalibrated'}")
                            elif t == "blink":
                                state["blink_at"] = state["n"]
                                print("blink", msg)
                        if not state["alive"]:
                            break
            except Exception as e:  # noqa: BLE001 — reconnect forever
                print(f"disconnected ({e}); retrying in 2 s")
                threading.Event().wait(2)

    threading.Thread(target=reader, daemon=True).start()

    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(-SECONDS * FS_TRACE, 0) / FS_TRACE
    (line,) = ax.plot(x, np.zeros_like(x), lw=0.8)
    mark = ax.axvline(-100, color="tab:red", lw=1.5)
    ax.set_xlim(-SECONDS, 0)
    ax.set_ylim(-200, 200)
    ax.set_xlabel("seconds ago")
    ax.set_ylabel("µV (0.5–45 Hz, decimated)")
    fig.tight_layout()

    try:
        while plt.fignum_exists(fig.number):
            with lock:
                y = np.array(buf)
                title = state["title"]
                age = (state["n"] - state["blink_at"]) / FS_TRACE
            line.set_ydata(y)
            if len(y) and np.max(np.abs(y)) > 0:
                lim = max(50.0, float(np.percentile(np.abs(y), 99)) * 1.5)
                ax.set_ylim(-lim, lim)
            mark.set_xdata([-age, -age] if age < SECONDS else [-100, -100])
            ax.set_title(title, fontsize=10)
            fig.canvas.draw_idle()
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass
    state["alive"] = False


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:8766")
