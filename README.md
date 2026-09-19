# Reflow

**It notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.**

HackMIT 2026 · Education track · NeuroSky MindWave Mobile 2 + Arduino UNO R4 · Deepgram + OpenAI.

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Technical design (the contract every module follows): [`docs/TDD.md`](docs/TDD.md)
- Demo runbook and rehearsal checklist: [`docs/DEMO-RUNBOOK.md`](docs/DEMO-RUNBOOK.md)
- Study protocol (the four numbers): [`study/PROTOCOL.md`](study/PROTOCOL.md)

## What it does

1. **In the lecture.** Headset on, totem on the desk. Deepgram transcribes with word timestamps. Focus drops (relative to your own first 3 minutes) and pad taps mark spans with an 8 s lead-in.
2. **Live catch-up.** Every 20 s Reflow writes a rolling one-line recap in four forms. **Tap the pad** and the recap for the span you missed appears in under a second: *"You missed: … Now: …"*, one glance, then it fades. An **EEG flag** only offers one: the totem pulses and a "catch-up ready" chip appears.
3. **Gap notes.** When the lecture ends you get notes for your flagged spans only: what was said, the key term, how it connects to what you did hear. Grounded in the transcript.
4. **Adaptive review.** One card per gap, check question first. Miss it, or lose focus, and the same idea is re-taught in another form: plain, key term, analogy, or a sketch that dissolves into an animated diagram. Stop after three straight hits.
5. **Your tally.** Which form rescued which misses, scored by quiz answers only. It picks the form of your next live catch-up. New learners start from the average across learners.
6. **Lecture loss map.** Across learners, the 40 seconds where the room was lost. Anonymous and aggregate: it grades the lecture, never a student.

Everything runs with no hardware and no API keys (simulated headset, simulated totem, scripted transcript, offline recaps), and every simulated thing is labelled on screen.

## Quick start

```bash
# backend (Python 3.13 via uv)
uv sync
cp .env.example .env            # add DEEPGRAM_API_KEY and OPENAI_API_KEY when you have them
uv run reflow doctor            # keys, services, serial ports, frontend build

# frontend (built once, served by the backend)
cd frontend && pnpm install && pnpm build && cd ..

# run everything in one process
uv run reflow serve             # http://127.0.0.1:8765
```

Open the URL, create a learner, pick the demo lecture ("How GPS finds you", scripted, with a planted bad segment 3), start a live session with headset `sim` and totem `sim`, and press `T` to tap. Press `1`/`2` to switch the simulated headset between focused and drifting and watch the EEG flag arrive as a chip and a totem pulse.

Frontend development with hot reload: `cd frontend && pnpm dev` (proxies `/api`, `/ws`, `/media` to the backend on 8765).

## Hardware

- **Headset:** pair the MindWave Mobile 2 over Bluetooth Classic. It appears as `/dev/cu.MindWaveMobile-SerialPort` (or similar; COM3 on Windows) and is auto-detected; the team's `mindwave/` pipeline reads it (see the EEG bridge section). Force a port with `REFLOW_HEADSET_PORT`, or `REFLOW_HEADSET_PORT=sim` to simulate.
- **Totem:** flash `firmware/totem/totem.ino` to an UNO R4 WiFi (or Minima) with `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem && arduino-cli upload -p /dev/cu.usbmodemXXXX --fqbn arduino:renesas_uno:unor4wifi firmware/totem`. Jumper D2 to a foil pad. The board is auto-detected on `usbmodem*`; `REFLOW_TOTEM_PORT=sim` simulates it. If capacitive touch misbehaves, set `USE_CAPTOUCH 0` in the sketch and wire a pushbutton between D2 and GND.
- **Hour-1 gate:** with the headset on a real forehead the live view must show blink ticks on the trace. If it does not, the raw stream is not real; fix pairing before anything else.

## EEG bridge (`mindwave/`)

The headset front end is the team's standalone `mindwave/` pipeline, built and validated on the real MindWave Mobile 2: ThinkGear reader with reconnect, 4 s Welch windows, blink detection in its own 0.5 to 8 Hz band, three-anchor calibration (eyes closed, easy, hard), session recording and bit-exact replay. Read [`EEG_PIPELINE.md`](EEG_PIPELINE.md) and [`mindwave/README.md`](mindwave/README.md) before touching it.

Reflow consumes it in-process: the pipeline turns raw into one `FeatureFrame` per second, and Reflow's focus engine applies the spec's own-baseline z-score, 15 s window and drop detector on the frame's `engagement` index (log10 beta minus log10(alpha plus theta), the same E = beta/(alpha+theta) on a log scale). Session start options:

| `headset` | What runs |
|---|---|
| `auto` | a paired MindWave if a port is found (`mindwave.MindWaveSource`), otherwise Reflow's simulator |
| `sim` | Reflow's synthetic EEG (`focused` / `drifting` / `poor`), the demo keys 1/2/3 |
| `fake` | the pipeline's own `FakeSource` (keys map focused to easy, drifting to drowsy, poor to off) |
| `replay:<dir>` | the pipeline's `ReplaySource` on a recorded `sessions/<stamp>` directory |
| `serial:<port>` | Reflow's minimal raw ThinkGear reader, for debugging only |

Real sessions are recorded by the pipeline under `data/eeg/<stamp>/`. The pipeline's calibration can be driven from the live view (eyes closed, easy, hard, done) and its go/no-go from `EEG_PIPELINE.md` §7 applies unchanged. The standalone tools still work: `uv run python run_pipeline.py --fake` (use `--ws-port 8766` while Reflow is serving on 8765) and `uv run --group monitor python monitor.py --fake`.

Two copies of the evaluation toolkit exist on purpose: the root `reflow_eval.py` is the pipeline team's pre-registered version (yoked random-timing control, `power` command); `reflow/eval/reflow_eval.py` is the REFLOW-3 version that `reflow study-analyze` uses.

## Commands

| Command | Purpose |
|---|---|
| `uv run reflow serve` | API + built frontend on one port |
| `uv run reflow doctor` | keys, Deepgram, OpenAI model (lists alternatives if the configured one is missing), ports, build |
| `uv run reflow ingest-lecture --title T --file lecture.m4a --meta study/meta.json` | transcribe a recorded lecture with Deepgram and register segments/quiz |
| `uv run reflow ingest-script script.json` | register a scripted lecture (words or plain text) |
| `uv run reflow replay SESSION_ID --speed 4` | print a session's event log at speed |
| `uv run reflow study-analyze --lecture LEC_ID` | the four study numbers with intervals |
| `uv run reflow sim selftest|bandit|lossmap` | the spec's simulations |
| `uv run reflow kaggle-check EEG_data.csv` | hour-0 feature check on the Wang et al. confusion data |
| `uv run pytest -q` | the test suite (no network, no hardware, about 15 s) |
| `uv run python scripts/smoke_e2e.py` | end-to-end against a running server, prints tap-to-catch-up latency |

## Layout

```
reflow/        Python package: signal engine, totem bridge, Deepgram, OpenAI, session runtime, review, tally, loss map, API, CLI
mindwave/      the team's standalone MindWave pipeline (headset -> calibrated FeatureFrame per second); run_pipeline.py, monitor.py, example_consumer.py use it directly
frontend/      Vite + React app (live, notes, review, tally, loss map, replay, quiz)
firmware/      UNO R4 totem sketch
study/         lecture script with the planted flaw, quiz, protocol
tests/         pytest suite
data/          runtime data (sqlite, session logs, lectures); the demo lecture script is committed
docs/          PRD, TDD, demo runbook
```

## Sponsor challenges

- **Deepgram:** live streaming transcription (`reflow/transcribe/deepgram_live.py`) and prerecorded transcription for recorded lectures. Both are in the product path.
- **OpenAI:** rolling recaps, gap notes, check questions, re-teach forms and diagram scene graphs as strict JSON-schema structured outputs (`reflow/llm/`). The Codex story for the demo is recorded in the runbook.
- **Long Lake:** pitch framing only. No prompt box. Reflow notices for you.

## Honesty rules baked in

- A simulated headset, totem, or transcript is labelled on screen, and forced flags carry `source: "forced"`.
- Offline (non-LLM) recaps and notes carry `source: "offline"` and a badge.
- The tally says "not enough data yet" until 12 scored cards.
- The loss map refuses to render with fewer than 2 learners.
- Every study number is reported with its interval, including nulls.

## License

MIT.
