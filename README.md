# NeuroPace

Previously called Reflow. The `reflow` Python package, existing data files, and old CLI
command remain compatible; use `uv run neuropace serve` to start the app.

**It notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.**

HackMIT 2026 · Education track · NeuroSky MindWave Mobile 2 + Arduino UNO Q 4 GB (UNO R4 direct path stays as a fallback) · Deepgram + OpenAI.

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Technical design (the contract every module follows): [`docs/TDD.md`](docs/TDD.md)
- Product definition v2 (screens, artifacts, preferences): [`docs/PRODUCT.md`](docs/PRODUCT.md)
- Demo runbook and rehearsal checklist: [`docs/DEMO-RUNBOOK.md`](docs/DEMO-RUNBOOK.md)
- Study protocol (the four numbers): [`study/PROTOCOL.md`](study/PROTOCOL.md)

## What it does

The student-facing product is defined in [`docs/PRODUCT.md`](docs/PRODUCT.md): two jobs (listen, restudy), four explanation families with an artifact catalogue, a preference model scored by answers with focus as a secondary signal, and a Duolingo-derived design. The list below is the mechanism behind it.

1. **In the lecture.** Headset on, totem on the desk. Deepgram transcribes with word timestamps. Focus drops (relative to your own first 3 minutes) and pad taps mark spans with an 8 s lead-in.
2. **Live catch-up.** Every 20 s NeuroPace writes a rolling one-line recap in four forms. **Tap the pad** and the recap for the span you missed appears in under a second: *"You missed: … Now: …"*, one glance, then it fades. An **EEG flag** only offers one: the totem pulses and a "catch-up ready" chip appears.
3. **Gap notes.** When the lecture ends you get notes for your flagged spans only: what was said, the key term, how it connects to what you did hear. Grounded in the transcript.
4. **Adaptive review.** One card per gap, check question first. Miss it, or lose focus, and the same idea is re-taught in another form: plain, key term, analogy, or a sketch that dissolves into an animated diagram. Stop after three straight hits.
5. **Your tally.** Which form rescued which misses, scored by quiz answers only. It picks the form of your next live catch-up. New learners start from the average across learners.
6. **Lecture loss map.** Across learners, the 40 seconds where the room was lost. Anonymous and aggregate: it grades the lecture, never a student.

Everything runs with no hardware (simulated headset, keyboard totem, scripted transcript) and every simulated thing is labelled on screen. An OpenAI key is required for a session: recaps, gap notes, check questions and re-teach forms are generated, never templated. If the API is down mid-lecture the catch-up shows the verbatim transcript (labelled), and notes that could not be generated say so with a retry button.

## Quick start

```bash
# backend (Python 3.13 via uv)
uv sync
cp .env.example .env            # add DEEPGRAM_API_KEY and OPENAI_API_KEY when you have them
uv run neuropace doctor            # keys, services, serial ports, frontend build

# frontend (built once, served by the backend)
cd frontend && pnpm install && pnpm build && cd ..

# run everything in one process
uv run neuropace serve             # http://127.0.0.1:8765
```

Open the URL, pick the demo lecture ("How GPS finds you", scripted, with a planted bad segment 3), start a live session with headset `sim` (the totem falls back to the keyboard when no Arduino is plugged in), and press Space or `T` to tap. Press `1`/`2` to switch the simulated headset between focused and drifting and watch the EEG flag arrive as a chip and a totem pulse.

Frontend development with hot reload: `cd frontend && pnpm dev` (proxies `/api`, `/ws`, `/media` to the backend on 8765).

## Hosted interface

The frontend is deployed at https://neurospace-hackmit.vercel.app. On the same laptop as your
browser and hardware, run `uv run neuropace serve` and paste the printed pairing code into the
hosted connection screen. Allow local network access when prompted. Restart an older backend
to load the hosted-interface changes. The local URL remains available as a fallback.

The frontend deploys from `frontend/` with `vercel --prod`; only frontend files are uploaded.
`REFLOW_UI_ORIGINS` configures exact allowed origins on the backend. Add preview URLs explicitly
when testing them. `VITE_BACKEND_URL` can override the default `http://127.0.0.1:8765` at build
time. Never put API keys or pairing codes in Vite environment variables. For hosted pairing,
use `neuropace serve` without `--reload` so the terminal prints the current pairing code.

The hosted site requires the local service. It does not provide a cloud backend or a remote
connection to someone else's laptop. EEG processing and session storage stay local; configured
transcription and explanation providers still receive the inputs needed for their requests.

## Hardware

- **Headset:** pair the MindWave Mobile 2 over Bluetooth Classic. It appears as `/dev/cu.MindWaveMobile-SerialPort` (or similar; COM3 on Windows) and is auto-detected; the team's `mindwave/` pipeline reads it (see the EEG bridge section). Force a port with `REFLOW_HEADSET_PORT`, or `REFLOW_HEADSET_PORT=sim` to simulate.
- **Totem (current target):** the UNO Q 4 GB relay in `firmware/uno_q_relay/` is the target path: the headset and a momentary switch connect to the Q, which relays both to the laptop over BLE. It is **experimental and uncompiled**; the concrete hardware blockers are listed in `firmware/uno_q_relay/README.md`. The physical button is **not built yet** — a momentary switch under a larger 3D-printed press surface is planned. Direct + simulated routes below stay labelled fallbacks.
- **Totem:** optional. Without an Arduino the totem falls back to the keyboard: Space or T in the browser, the on-screen "Lost me" pad, or Space/T in the terminal running `reflow serve`. Key taps are real learner actions (flag source `key`), not simulations; plugging the Arduino in mid-session switches to it automatically. To use the pad, flash `firmware/totem/totem.ino` to an UNO R4 WiFi (or Minima) with `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem && arduino-cli upload -p /dev/cu.usbmodemXXXX --fqbn arduino:renesas_uno:unor4wifi firmware/totem`. Jumper D2 to a foil pad. The board is auto-detected on `usbmodem*`; `REFLOW_TOTEM_PORT=keyboard` forces the keyboard fallback. If capacitive touch misbehaves, set `USE_CAPTOUCH 0` in the sketch and wire a pushbutton between D2 and GND.

- **Hour-1 gate:** with the headset on a real forehead the live view must show blink ticks on the trace. If it does not, the raw stream is not real; fix pairing before anything else.

## EEG bridge (`mindwave/`)

The headset front end is the team's standalone `mindwave/` pipeline, built and validated on the real MindWave Mobile 2: ThinkGear reader with reconnect, 4 s Welch windows, blink detection in its own 0.5 to 8 Hz band, three-anchor calibration (eyes closed, easy, hard), session recording and bit-exact replay. Read [`EEG_PIPELINE.md`](EEG_PIPELINE.md) and [`mindwave/README.md`](mindwave/README.md) before touching it.

NeuroPace consumes it in-process: the pipeline turns raw into one `FeatureFrame` per second, and NeuroPace's focus engine applies the spec's own-baseline z-score, 15 s window and drop detector on the frame's `engagement` index (log10 beta minus log10(alpha plus theta), the same E = beta/(alpha+theta) on a log scale). Session start options:

| `headset` | What runs |
|---|---|
| `auto` | a paired MindWave if a port is found (`mindwave.MindWaveSource`), otherwise NeuroPace's simulator |
| `sim` | NeuroPace's synthetic EEG (`focused` / `drifting` / `poor`), the demo keys 1/2/3 |
| `fake` | the pipeline's own `FakeSource` (keys map focused to easy, drifting to drowsy, poor to off) |
| `replay:<dir>` | the pipeline's `ReplaySource` on a recorded `sessions/<stamp>` directory |
| `serial:<port>` | NeuroPace's minimal raw ThinkGear reader, for debugging only |

Real sessions are recorded by the pipeline under `data/eeg/<stamp>/`. The pipeline's calibration can be driven from the live view (eyes closed, easy, hard, done) and its go/no-go from `EEG_PIPELINE.md` §7 applies unchanged. The standalone tools still work: `uv run python run_pipeline.py --fake` (use `--ws-port 8766` while NeuroPace is serving on 8765) and `uv run --group monitor python monitor.py --fake`.

Two copies of the evaluation toolkit exist on purpose: the root `reflow_eval.py` is the pipeline team's pre-registered version (yoked random-timing control, `power` command); `reflow/eval/reflow_eval.py` is the REFLOW-3 version that `reflow study-analyze` uses.

## Platforms

| | macOS | Windows |
|---|---|---|
| Toolchain | uv, pnpm, arduino-cli via Homebrew | uv, pnpm, arduino-cli installers; `copy .env.example .env` instead of `cp` |
| Headset port | `/dev/cu.MindWaveMobile-SerialPo` after pairing in System Settings; found by name | two "Standard Serial over Bluetooth link (COMn)" ports per paired device with no name; auto-detect probes each for ThinkGear packets (headset must be on), or set `REFLOW_HEADSET_PORT=COM3` (the outgoing port) |
| Totem port | `/dev/cu.usbmodem…`, found by name | "USB Serial Device (COMn)", found by Arduino's USB vendor id 0x2341 |
| `run_pipeline.py` keys | termios (any terminal) | msvcrt (cmd, PowerShell) |
| `monitor.py` | matplotlib macosx backend: `uv run --group monitor python monitor.py --fake` | matplotlib TkAgg; same command |
| Status | this build was developed and verified here (tests, smoke, browser) | code reviewed for Windows paths, COM naming, console encoding and event loop; not yet executed on a Windows machine |

`uv run neuropace doctor` prints the platform and every serial port with its hardware id, which is the first thing to check when a device is not picked up.

## Commands

| Command | Purpose |
|---|---|
| `uv run neuropace serve` | API + built frontend on one port |
| `uv run neuropace doctor` | keys, Deepgram, OpenAI model (lists alternatives if the configured one is missing), ports, build |
| `uv run neuropace ingest-lecture --title T --file lecture.m4a --meta study/meta.json` | transcribe a recorded lecture with Deepgram and register segments/quiz |
| `uv run neuropace ingest-script script.json` | register a scripted lecture (words or plain text) |
| `uv run neuropace replay SESSION_ID --speed 4` | print a session's event log at speed |
| `uv run neuropace study-analyze --lecture LEC_ID` | the four study numbers with intervals |
| `uv run neuropace sim selftest|bandit|lossmap` | the spec's simulations |
| `uv run neuropace kaggle-check EEG_data.csv` | hour-0 feature check on the Wang et al. confusion data |
| `uv run pytest -q` | the test suite (no network, no hardware, about 15 s) |
| `uv run python scripts/smoke_e2e.py` | end-to-end against a running server, prints tap-to-catch-up latency |

## Layout

```
reflow/        Python package: signal engine, totem bridge, Deepgram, OpenAI, session runtime, review, tally, loss map, API, CLI
mindwave/      the team's standalone MindWave pipeline (headset -> calibrated FeatureFrame per second); run_pipeline.py, monitor.py, example_consumer.py use it directly
frontend/      Vite + React app (live, notes, review, tally, loss map, replay, quiz)
firmware/      uno_q_relay/ (UNO Q 4 GB BLE relay prototype, current target, uncompiled) + totem/ (UNO R4 direct-USB fallback sketch)
study/         lecture script with the planted flaw, quiz, protocol
tests/         pytest suite
data/          runtime data (sqlite, session logs, lectures); the demo lecture script is committed
docs/          PRD, TDD, demo runbook
```

## Sponsor challenges

- **Deepgram:** live streaming transcription (`reflow/transcribe/deepgram_live.py`) and prerecorded transcription for recorded lectures. Both are in the product path.
- **OpenAI:** rolling recaps, gap notes, check questions, re-teach forms and diagram scene graphs as strict JSON-schema structured outputs (`reflow/llm/`). The Codex story for the demo is recorded in the runbook.
- **Long Lake:** pitch framing only. No prompt box. NeuroPace notices for you.

## Honesty rules baked in

- A simulated headset or scripted transcript is labelled on screen, and forced flags carry `source: "forced"`. Keyboard taps are real taps.
- No placeholder text: without `OPENAI_API_KEY` a session cannot start; during an outage the catch-up is the verbatim transcript (`source: "transcript"`) and failed notes are reported (`package_source: "failed"`) with a retry. The extractive `offline` generator only runs in automated tests (`REFLOW_ALLOW_OFFLINE_LLM=1`).
- The tally says "not enough data yet" until 12 scored cards.
- The loss map refuses to render with fewer than 2 learners.
- Every study number is reported with its interval, including nulls.

## License

MIT.
