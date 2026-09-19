# mindwave — NeuroSky MindWave Mobile 2 → attention metrics

One dry electrode at Fp1, reference on the earlobe, 512 Hz raw. The package turns that into
**one `FeatureFrame` of attention metrics per second**, calibrated to the wearer. It owns
filtering, artifact gating, band powers, blink detection, calibration z-scores and a 5 s EMA.
It makes no decisions and depends on no application. Full write-up: [../EEG_PIPELINE.md](../EEG_PIPELINE.md).

```
pip install -r requirements.txt
python monitor.py --fake          # learn the display, no headset
python monitor.py                 # live plot + go/no-go
python run_pipeline.py            # headless: console + WebSocket + session log
python example_consumer.py --fake
```

## Consuming it

```python
from mindwave import Pipeline, MindWaveSource
pipe = Pipeline(MindWaveSource("COM3"))
pipe.serve()                        # optional WebSocket feed, ws://127.0.0.1:8765
pipe.calibrate("eyes_closed")       # then "easy", "hard", "done"  — or pipe.auto_calibrate()
for f in pipe.frames():             # one frame per second
    if f.valid:
        f.effort, f.engagement, f.alpha_ratio, f.blink_rate      # from the first frame
        f.z_effort_ema, f.z_engagement_ema                       # None until calibrated
```

| field | meaning |
|---|---|
| `valid` | False when the electrode is off (`quality` > 50), the 4 s window is > 50 % blink/movement artifact, or the headset is disconnected. Skip the frame; EMAs hold. |
| `effort` | log θ − log α — mental workload, rises with concentration. Primary. |
| `engagement` | log β − log(α+θ) — alertness (Pope index). Secondary; forehead beta is partly muscle. |
| `z_effort_ema` / `z_engagement_ema` | the same, calibrated so the wearer's easy phase ≈ −1 and hard ≈ +1, smoothed. The values to act on. |
| `alpha_ratio` | alpha now vs. the easy phase — relaxation, eyes closed (≈ 8× measured). |
| `blink_rate`, `blink_dur_ms` | trailing 30 s — up with fatigue, down when absorbed. |
| `quality` | NeuroSky `poor_signal`: 0 best … 200 off-head. |
| `attention`, `meditation`, `asic_bands` | NeuroSky's own numbers, passthrough for comparison only. |
| `cal_phase`, `calibrated`, `calibration_weak` | calibration state. |

Calibration: `eyes_closed` (~10 s), `easy` (~25 s), `hard` (~25 s), then `done`. Needs ≥ 8 valid
windows per anchor for full strength (≥ 3 to work at all). If the hard task did **not** raise
effort, `pipe.status()["messages"]` says so rather than the sign being flipped silently.

## WebSocket feed

`ws://127.0.0.1:8765`, JSON, one object per message: `features` (1 Hz, every frame field),
`raw` (8 Hz chunks of a 64 Hz µV trace for plotting), `blink`, `status`.
Send `{"type":"calibrate","phase":"easy"}` etc. to drive calibration remotely.

## Sessions and replay

Every real run logs to `sessions/<stamp>/` (`raw.int16`, `events.jsonl`, `features.jsonl`).
`ReplaySource("sessions/<stamp>", speed=4)` plays it back bit-exactly, calibration commands
included, so consumers can be developed without the headset.
