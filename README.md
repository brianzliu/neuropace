# Reflow

**It notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.**

HackMIT 2026 · Education track · NeuroSky MindWave Mobile 2 + Arduino UNO R4 · Deepgram + OpenAI.

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Technical design (the contract every module follows): [`docs/TDD.md`](docs/TDD.md)
- Product definition v2 (screens, artifacts, preferences): [`docs/PRODUCT.md`](docs/PRODUCT.md)
- Demo runbook and rehearsal checklist: [`docs/DEMO-RUNBOOK.md`](docs/DEMO-RUNBOOK.md)
- Study protocol (the four numbers): [`study/PROTOCOL.md`](study/PROTOCOL.md)

## What it does

The student-facing product is defined in [`docs/PRODUCT.md`](docs/PRODUCT.md): two jobs (listen, restudy), four explanation families with an artifact catalogue, a preference model scored by answers with focus as a secondary signal, and a Duolingo-derived design. The list below is the mechanism behind it.

1. **In the lecture.** Headset on, totem on the desk. Deepgram transcribes with word timestamps. Focus drops (relative to your own first 3 minutes) and pad taps mark spans with an 8 s lead-in.
2. **Live catch-up.** Every 20 s Reflow writes a rolling one-line recap in four forms. **Tap the pad** and the recap for the span you missed appears in under a second: *"You missed: … Now: …"*, one glance, then it fades. An **EEG flag** only offers one: the totem pulses and a "catch-up ready" chip appears.
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
uv run reflow doctor            # keys, services, serial ports, frontend build

# frontend (built once, served by the backend)
cd frontend && pnpm install && pnpm build && cd ..

# run everything in one process
uv run reflow serve             # http://127.0.0.1:8765
```

Open the URL, pick the demo lecture ("How GPS finds you", scripted, with a planted bad segment 3), start a live session with headset `sim` (the totem falls back to the keyboard when no Arduino is plugged in), and press Space or `T` to tap. Press `1`/`2` to switch the simulated headset between focused and drifting and watch the EEG flag arrive as a chip and a totem pulse.

Frontend development with hot reload: `cd frontend && pnpm dev` (proxies `/api`, `/ws`, `/media` to the backend on 8765).

## Hardware

- **Headset:** pair the MindWave Mobile 2 over Bluetooth Classic. It appears as `/dev/cu.MindWaveMobile-SerialPort` (or similar; COM3 on Windows) and is auto-detected; the team's `mindwave/` pipeline reads it (see the EEG bridge section). Force a port with `REFLOW_HEADSET_PORT`, or `REFLOW_HEADSET_PORT=sim` to simulate.
- **Totem:** optional. Without an Arduino the totem falls back to the keyboard: Space or T in the browser, the on-screen "Catch me up" pad, or Space/T in the terminal running `reflow serve`. Key taps are real learner actions (flag source `key`), not simulations; plugging the Arduino in mid-session switches to it automatically. To use the pad, flash `firmware/totem/totem.ino` to an UNO R4 WiFi (or Minima) with `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem && arduino-cli upload -p /dev/cu.usbmodemXXXX --fqbn arduino:renesas_uno:unor4wifi firmware/totem`. Jumper D2 to a foil pad. The board is auto-detected on `usbmodem*`; `REFLOW_TOTEM_PORT=keyboard` forces the keyboard fallback. If capacitive touch misbehaves, set `USE_CAPTOUCH 0` in the sketch and wire a pushbutton between D2 and GND.
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
| a device path | the pipeline on that serial port (what `auto` resolves to when a headset is found) |

**Brain waves on screen are the device's bytes.** The pipeline decimates the 512 Hz raw stream to 64 Hz and Reflow broadcasts it as `raw` chunks; the live and restudy screens draw those and nothing else. The label under the trace is judged from arrival time: *live from your headset* only while chunks keep coming, *waiting for the headset* within two seconds of a dropout, *practice signal* for every non-real kind. A session that started on the simulator because the headset was off keeps looking every five seconds and switches to the real device when it appears. One headset, one recording: a second lecture on the same port is refused (409) until the first ends.

**Testing without the hardware, honestly:** `uv run reflow virtual-headset --control /tmp/vh.ctl` puts a MindWave on a pseudo-terminal (macOS and Linux). It writes real ThinkGear packets (one 0x80 raw packet per sample at 512 Hz, a 1 Hz status packet with poor_signal, eSense and the eight EEG power bands) from the pipeline's `FakeSource`, so the serial reader, the parser, the pipeline and every screen above see a headset of kind `real`. Start the server with `REFLOW_HEADSET_PORT=<the printed path>`; then `echo "state drowsy" > /tmp/vh.ctl` makes the wearer drift, `state off` lifts the electrode, `pause 6` drops the link for six seconds. Windows has no pty: use `headset=fake` there (same signal, in-process).

Real sessions are recorded by the pipeline under `data/eeg/<stamp>/`. The pipeline's calibration can be driven from the live view (eyes closed, easy, hard, done) and its go/no-go from `EEG_PIPELINE.md` §7 applies unchanged. The standalone tools still work: `uv run python run_pipeline.py --fake` (use `--ws-port 8766` while Reflow is serving on 8765) and `uv run --group monitor python monitor.py --fake`.

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

`uv run reflow doctor` prints the platform and every serial port with its hardware id, which is the first thing to check when a device is not picked up.

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

- A simulated headset or scripted transcript is labelled on screen, and forced flags carry `source: "forced"`. Keyboard taps are real taps.
- No placeholder text: without `OPENAI_API_KEY` a session cannot start; during an outage the catch-up is the verbatim transcript (`source: "transcript"`) and failed notes are reported (`package_source: "failed"`) with a retry. The extractive `offline` generator only runs in automated tests (`REFLOW_ALLOW_OFFLINE_LLM=1`).
- The tally says "not enough data yet" until 12 scored cards.
- The loss map refuses to render with fewer than 2 learners.
- Every study number is reported with its interval, including nulls.

## License

MIT.
