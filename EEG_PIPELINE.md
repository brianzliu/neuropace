# EEG pipeline — NeuroSky MindWave Mobile 2 → attention metrics

A standalone tool. It takes the headset's Bluetooth stream and outputs one record of attention
metrics per second: mental effort, engagement, alpha (relaxation / eyes closed), blink rate, and
signal quality, calibrated to the wearer. It makes no decisions and knows nothing about any
application; what a metric *means* for a given use is the consumer's business.

**Status (Sat 19 Sep):** built and validated on the real headset. Every go/no-go check below has
passed on a team member's head.

---

## 1. Data flow

```
 MindWave Mobile 2 ──Bluetooth SPP (COM3)──▶  thinkgear.py     packets → events: 512 Hz raw, 1 Hz quality/eSense
                                                    │
                                                    ▼
                                              pipeline.py      ring buffer, 4 s window, 1 s hop
                                                features.py      three filter bands, blink mask, Welch PSD, indices
                                                calibration.py   per-wearer z-scores, 5 s EMA
                                                    │
                                        FeatureFrame, once per second
                                                    │
                     ┌──────────────────────────────┼──────────────────────────────┐
                     ▼                              ▼                              ▼
             in-process API                  server.py                       sessions/<stamp>/
             pipe.frames() / on_frame()      ws://127.0.0.1:8765              raw.int16 · events.jsonl
                                             JSON, 1 Hz + live trace          features.jsonl — replayable
```

One Python process on the laptop. Three ways to consume the output; all carry the same fields.

## 2. The metrics

Every field is on `FeatureFrame` in `mindwave/pipeline.py`. The ones that matter:

| metric | formula | what it tracks | how much to trust it |
|---|---|---|---|
| `effort` | log θ − log α | **Mental workload.** Frontal theta rises and alpha falls with concentration. | Primary. Measured +0.27 relaxed → +0.55 concentrating. Real, modest; use the smoothed value. |
| `engagement` | log β − log(α+θ) | **Alertness** (Pope engagement index). | Secondary. Forehead beta is partly frontalis muscle (frowning), so it corroborates, never leads. |
| `z_effort_ema`, `z_engagement_ema` | calibrated + smoothed | The same two, on a **personal scale**: the wearer's easy phase ≈ −1, hard phase ≈ +1. | **Use these.** `None` until calibration is done. |
| `alpha_ratio` | α now ÷ α during the easy phase | **Relaxation, eyes closed.** | Very reliable for eyes closed: ≈ 8× measured. Weak as an eyes-open signal. |
| `blink_rate`, `blink_dur_ms` | trailing 30 s | **Fatigue** (rate and duration rise), **absorption** (rate falls). | Reliable. The electrode sits over the eye. Gated on contact. |
| `quality` | NeuroSky `poor_signal` | **Contact.** 0 best … 200 off the skin. | The gate. Above 50 nothing else is meaningful. |
| `valid` | — | quality ≤ 50 **and** < 50 % of the window artifact **and** headset connected. | Skip invalid frames; the EMAs hold. |
| `attention`, `meditation` | NeuroSky eSense, 0–100 | Their proprietary numbers. | Passthrough for comparison only; the algorithm is a black box. |
| `log_theta` … `log_gamma` | own Welch PSD | The raw ingredients. | For plots and for anyone who wants a different index. |

Also: `artifact_coverage`, `blink_count`, `calibrated`, `cal_phase`, `calibration_weak`, `t`, `n`.

## 3. Outputs

**In-process (Python)**

```python
from mindwave import Pipeline, MindWaveSource
pipe = Pipeline(MindWaveSource("COM3"))
pipe.calibrate("eyes_closed")        # then "easy", "hard", "done" — or pipe.auto_calibrate()
for f in pipe.frames():              # one FeatureFrame per second
    if f.valid:
        f.effort, f.engagement, f.alpha_ratio, f.blink_rate, f.z_effort_ema, ...
```

or `pipe.on_frame(callback)`, `pipe.on_blink(callback)`, `pipe.on_raw(callback)`, `pipe.on_status(callback)`.

**WebSocket** — `pipe.serve()` or `run_pipeline.py`; `ws://127.0.0.1:8765`, JSON, one object per message.

```
out  {"type":"features", ...every FeatureFrame field...}                    1 Hz
     {"type":"raw", "t", "fs":64, "uv":[8 values]}                          8 Hz, a 64 Hz µV trace for plotting
     {"type":"blink", "t", "amplitude_uv", "duration_ms"}                   per blink
     {"type":"status", "connected", "quality", "calibrated", "cal_phase", "messages", ...}   on change
in   {"type":"calibrate", "phase":"eyes_closed"|"easy"|"hard"|"done"|"reset"}
     {"type":"status"}    {"type":"ping"}
```

**Session files** — every real run writes `sessions/<stamp>/`: `raw.int16` (512 Hz ADC counts),
`events.jsonl` (quality, eSense, ASIC bands, blinks, calibration commands, each stamped with the
sample index), `features.jsonl` (one FeatureFrame per line), `session.json`. `ReplaySource`
replays a session bit-exactly, calibration commands included, at 1×, faster, or as fast as
possible. Consumers can be developed against a replay with no headset in the room.

## 4. Signal processing

One dry electrode at Fp1 (left forehead), referenced to the earlobe. Analog front end ≈ 3–100 Hz,
512 Hz, 12-bit; counts × 0.22 ≈ µV (approximate; every index is log- or z-scored, so the
constant only labels plot axes).

**Window:** 4 s, hopping 1 s. Per window:

1. **Three filter bands, deliberately.** Analysis 3–45 Hz (feeds the PSD). Detection 0.5–8 Hz
   (finds blinks). Display 0.5–45 Hz (the monitor). A blink is a 200–400 ms deflection — energy at
   1–3 Hz — so detecting it *after* the 3 Hz analysis high-pass cuts its amplitude 3–7× and turns
   the smooth deflection into a narrow spike, destroying the duration signature. This was a real
   bug on day one; the reasoning is in the `features.py` docstring so nobody re-derives it.
2. **Blink / movement detector** on the detection band: threshold max(5 × robust σ, 40 µV);
   excursions of 50–800 ms are blinks, longer ones movement. Both are masked (padded 100 ms) and
   linearly interpolated across in the analysis band. Measured duration is inflated ≈ 1.5× by the
   0.5 Hz edge, so `blink_dur_ms` is a relative number. Real blinks measured 90–414 µV.
3. **Welch PSD** (512-point segments) → band powers θ 4–8, α 8–13, β 13–30, γ 30–45 Hz → log10.
   Own PSD, not NeuroSky's ASIC bands: theirs are undocumented, non-linear and not comparable
   across sessions.
4. **Indices** as in §2.
5. **Gates.** `quality` > 50 → frame invalid and no blinks counted (an off-head channel is pure
   noise and otherwise manufactures a stream of phantom blinks — observed, fixed). Artifact
   coverage > 50 % → invalid (30 % rejected a quarter of windows at a normal blink rate).
6. **EMA** τ = 5 s on each index and each z-score, held across invalid frames.

## 5. Calibration

Band powers at Fp1 vary wildly between people and sessions, so every scale is personal. Three
anchors, driven by `pipe.calibrate(phase)`, the `calibrate` WebSocket message, or keys 1/2/3/0
in the monitor:

| phase | ~duration | what the wearer does | used for |
|---|---|---|---|
| `eyes_closed` | 10 s | eyes shut, relax | alpha reference (`alpha_closed_open_ratio`) |
| `easy` | 25 s | read something easy | low anchor |
| `hard` | 25 s | count down from 1000 by 7s, out loud | high anchor |
| `done` | — | — | finalize |

Per index: μ = midpoint of the easy and hard means, σ = max(pooled sd, half the easy→hard gap),
so easy ≈ −1 and hard ≈ +1. Needs 8 valid windows per anchor for full strength (3 minimum, else
`calibration_weak`). The first 4 s of each phase are ignored (the window still straddles the
previous phase). If the hard task did **not** raise effort the result says `inverted` in
`status()["messages"]` rather than flipping the sign silently.

## 6. What one forehead channel can and cannot measure

- **Effort / workload** — the most replicated single-channel finding (frontal theta with working
  memory load; Gevins & Smith 2003). Fz is the textbook site; Fp1 sees it attenuated and mixed
  with ocular activity. Real, modest.
- **Eyes-closed alpha** — the largest, most reliable thing this headset does (≈ 8× on a team
  member). Not an eyes-open signal.
- **Blinks** — both directions: absorbed → fewer; fatigued or disengaged → more and longer.
  Well validated, free here.
- **Engagement / "focus"** — the most intuitive metric and the least trustworthy at the forehead.
  The engagement index flipped positive the moment concentration began on a team member, but
  forehead beta is partly muscle. Corroborate with it; don't lead with it.
- **Eyes-open alpha rise (mind-wandering)** — the most replicated EEG marker of a wandering mind,
  weak at Fp1, visible only in aggregate.
- **Not feasible:** anything event-locked (error-related negativity), single-trial memory
  encoding, anything needing a posterior electrode.

Prior art on this exact headset: Wang et al. 2013 classified "confused" vs. not on students
watching MOOC videos at roughly 60–70 %. Treat that as the ceiling for one channel on its own.

## 7. Running and testing

```
pip install -r requirements.txt
python monitor.py --fake        # learn the display; keys c/e/h/d/o set the simulated state; nothing recorded
python monitor.py               # headset on: the banner must go green; then 1 → 2 → 3 → 0
python run_pipeline.py          # headless: console lines + WebSocket + session log
python run_pipeline.py --replay sessions/<stamp> --speed 4
python example_consumer.py --fake
```

Go/no-go on a new head (`python monitor.py`):

1. quality reaches 0–30 within ~20 s of putting it on
2. five deliberate blinks → five red marks in the trace
3. `1`, eyes closed 10 s; `2`, easy reading 25 s → alpha closed/open ≥ 1.5×
4. `3`, count down from 1000 by 7s out loud 25 s; `0` → effort hard > easy, no `inverted`

If 3 fails on someone, alpha is too weak on them: drop it and lean on theta + blinks.

Fit is everything: pad flat on bare forehead above the left eyebrow with no hair under it, ear
clip on the fleshy earlobe with both metal contacts touching. Windows lists paired SPP devices as
"Not connected" until something opens the COM port — that is normal. The headset must be
switched on before the port opens; the reader retries every 2 s and reports the error in
`status()`.

## 8. Module map

| file | job |
|---|---|
| `mindwave/thinkgear.py` | ThinkGear protocol: chunk-safe parser, checksum, typed events, reconnecting reader thread |
| `mindwave/sources.py` | `MindWaveSource` (COM port) · `ReplaySource` (session, bit-exact) · `FakeSource` (synthetic, five states) |
| `mindwave/features.py` | per-window processing: bands, blink detector, interpolation, PSD, indices |
| `mindwave/calibration.py` | three-anchor calibration, z-scores, EMA |
| `mindwave/pipeline.py` | ring buffer, frame assembly, gates, blink counting, logging, fan-out; defines `FeatureFrame` |
| `mindwave/server.py` | WebSocket broadcaster |
| `mindwave/keys.py` | keyboard bindings shared by the console runner and the monitor |
| `run_pipeline.py` | headless service |
| `monitor.py` | live plot; go/no-go |
| `example_consumer.py` | minimal consumer, in-process and over WebSocket |

## 9. Decisions and why

| decision | why |
|---|---|
| Own PSD rather than NeuroSky's ASIC bands | Theirs are undocumented and not comparable across sessions. Ours can be defended to a reviewer. |
| Three filter bands | Blinks live at 1–3 Hz and cannot be detected in the analysis band (§4). |
| Blinks as a metric, not just an artifact | The channel over the eye is the best blink sensor available; blink rate is a validated fatigue marker and costs nothing. |
| Three-anchor calibration | Fp1 band powers are not comparable between people; personal scales are the single biggest reliability win. Eyes-closed doubles as the demonstration. |
| No decisions in the pipeline | Thresholds, states and fusion with other data belong to the consumer. Keeping them out keeps this reusable and testable. |
| Log everything from the first run | Replay is the development path without hardware and the fallback with it. |
| Everything behind a `Source` interface | A different headset is a one-file swap. |
