"""Minimal consumer of the pipeline: the shape any downstream code takes.

    python example_consumer.py            # live headset on COM3
    python example_consumer.py --fake     # synthetic EEG, runs a short auto-calibration
    python example_consumer.py --ws       # instead: subscribe to a running run_pipeline.py over WebSocket

Once a second the pipeline hands you a FeatureFrame (fields documented in mindwave/pipeline.py).
frame.valid is False when the electrode is off the skin, the window is mostly blink/movement
artifact, or the headset is disconnected: skip those frames, the smoothed values hold.
The calibrated z-scores are None until calibrate("done"); the raw indices, alpha ratio, blink
rate and NeuroSky's own attention/meditation are available from the first frame.
"""
from __future__ import annotations

import json
import sys

from mindwave import FakeSource, MindWaveSource, Pipeline


def run_in_process(fake: bool) -> None:
    source = FakeSource() if fake else MindWaveSource("COM3")
    pipe = Pipeline(source)
    pipe.serve()                                    # optional: WebSocket feed on ws://127.0.0.1:8765
    pipe.start()
    if fake:                                        # demo only; normally the wearer drives calibration
        pipe.auto_calibrate(eyes_closed_s=6, easy_s=12, hard_s=12)
    try:
        for f in pipe.frames():
            if not f.valid:
                print(f"{f.t:.0f}  invalid (quality={f.quality}, artifacts={f.artifact_coverage:.0%})")
                continue
            alpha = "--" if f.alpha_ratio is None else f"{f.alpha_ratio:.2f}x"
            line = (f"{f.t:.0f}  effort={f.effort:+.2f}  engagement={f.engagement:+.2f}  "
                    f"alpha={alpha}  blinks/min={f.blink_rate:.0f}  neurosky_attention={f.attention}")
            if f.calibrated:
                line += f"  |  z_effort={f.z_effort_ema:+.2f}  z_engagement={f.z_engagement_ema:+.2f}"
            else:
                line += f"  |  uncalibrated ({f.cal_phase or 'idle'})"
            print(line)
    except KeyboardInterrupt:
        pass
    finally:
        pipe.stop()


def run_over_websocket(url: str = "ws://127.0.0.1:8765") -> None:
    from websockets.sync.client import connect

    with connect(url) as ws:
        ws.send(json.dumps({"type": "status"}))
        for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "features":
                print(f"{msg['t']:.0f}  valid={msg['valid']}  effort={msg['effort']}  "
                      f"z_effort={msg['z_effort_ema']}  quality={msg['quality']}  "
                      f"blinks/min={msg['blink_rate']}")
            elif msg["type"] == "blink":
                print("blink", msg)
            elif msg["type"] == "status":
                print("status", {k: msg[k] for k in ("connected", "quality", "calibrated", "cal_phase")})


if __name__ == "__main__":
    if "--ws" in sys.argv:
        run_over_websocket()
    else:
        run_in_process(fake="--fake" in sys.argv)
