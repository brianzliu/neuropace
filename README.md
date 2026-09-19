# NeuroSky EEG pipeline

Takes the Bluetooth stream from a **NeuroSky MindWave Mobile 2** and outputs one record of
attention metrics per second — mental effort, engagement, alpha (relaxation / eyes closed),
blink rate, signal quality — calibrated to the wearer. Standalone: no dependence on any
application, no decision logic. Consume it in-process, over WebSocket, or from the session files.

Built and validated on the real headset.

## Quick start

```
pip install -r requirements.txt
python monitor.py --fake        # learn the display with simulated EEG, no headset needed
python monitor.py               # headset on (paired; outgoing SPP COM port, COM3 here)
python run_pipeline.py          # headless: 1 Hz metrics on ws://127.0.0.1:8765 + session log
python example_consumer.py --fake
```

## Read next

- [EEG_PIPELINE.md](EEG_PIPELINE.md) — data flow, every metric and how much to trust it, the
  signal processing, calibration, what one forehead channel can and cannot measure. Start here.
- [mindwave/README.md](mindwave/README.md) — the package API and the `FeatureFrame` fields.

## Layout

```
mindwave/             the pipeline: headset → calibrated 1 Hz FeatureFrame
monitor.py            live plot and go/no-go test
run_pipeline.py       headless service with WebSocket feed and session logging
example_consumer.py   minimal consumer, in-process and over WebSocket
sessions/             recorded runs, replayable (gitignored)
```

Also in this repo, not needed to use the pipeline: the HackMIT 2026 product plan
(`PLAN.md`, `tracks.md`) and `reflow_eval.py`, a pre-registered statistics toolkit for evaluating
that product.
