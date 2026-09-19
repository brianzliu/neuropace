# Verification record (19 Sep 2026, updated after the mindwave bridge merge)

What was checked, how, and what is still unverified. Re-run the commands before the demo; the outcomes below are from the build day on Joaquin's laptop (macOS, Python 3.13.14, Node 24, pnpm 11.13, arduino-cli with core arduino:renesas_uno 1.6.0).

## Automated

| Check | Command | Result |
|---|---|---|
| Backend unit + integration tests (parser, features, blinks, spans, recaps, LLM client with a fake OpenAI, tally, review, loss map, session runtime, REST + WebSocket real-time flow, study analysis, Deepgram client parsing, mindwave bridge on `FakeSource` with a byte-level cross-check of both ThinkGear parsers, port detection on macOS and Windows listings with a fake serial module) | `uv run pytest -q` | 69 passed in about 22 s, no network, no hardware |
| Lint | `uv run ruff check reflow tests scripts` | clean (the spec's three sim scripts are kept verbatim and excluded from style rules) |
| Frontend types + build | `cd frontend && pnpm typecheck && pnpm build` | 0 errors, 67 modules, `dist/` served by the backend |
| Firmware | `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem` and `:minima` | both compile (57 KB / 44 KB) |
| Spec toolkit | `uv run reflow sim selftest` | SELFTEST PASS |
| Live end-to-end against a running server, everything simulated | `uv run reflow serve` then `uv run python scripts/smoke_e2e.py --baseline 8` | 14/14 PASS; tap to catch-up 1 to 3 ms |
| Tap confirms an EEG flag (TDD §6 linking rule) | unit test on the runtime plus a live WebSocket check: simulated drift, EEG flag opens, tap 8 s later | the tap span starts at the drop (`linked_eeg` set), the card carries `since` and `span_seconds`; a tap more than 10 s after the flag closed is not linked |

## The team's EEG pipeline (`mindwave/`, merged from brianzliu/neuropace)

| Check | How | Result |
|---|---|---|
| Standalone runner still works from the merged repo | `uv run python run_pipeline.py --fake --no-ws --no-log` | one frame line per second (effort, engagement, blink rate, eSense) |
| Bridge over the API | session with `headset: "fake"`, `POST /calibrate`, WS `calibrate`, `sim_headset: drifting` | `mw` extras on focus samples, `cal_phase` follows the commands, EEG flag 22 s after the switch, `headset_kind` stored as `fake` |
| Live view on the fake headset | ego-browser: "fake headset" badge, calibration buttons, "calibrating: eyes_closed" chip | renders |
| Real MindWave through the bridge | not verified: no headset on this machine | the pipeline itself was validated on a real head by its author (`EEG_PIPELINE.md`); `auto` picks it up when a `MindWave` serial port is present |

## Platforms

| Check | How | Result |
|---|---|---|
| macOS: `run_pipeline.py` without a headset | `uv run python run_pipeline.py --no-ws --no-log` | clear message listing the serial ports, exit 2 (no more silent `COM3` default) |
| macOS: console keys in `run_pipeline.py` | driven through a pseudo-terminal: `d`, `2`, `b` | `[key] fake state -> drowsy`, `[key] calibrate easy`, `[key] fake blink` (termios poller; Windows keeps msvcrt) |
| macOS: `monitor.py --fake` | launched for 8 s | window opens, no traceback (matplotlib via `uv run --group monitor`) |
| macOS: `example_consumer.py --fake` | 6 s | frames printed, auto-calibration prompts |
| Windows port naming | unit tests with a Windows-style listing (two `BTHENUM` COM ports, `USB Serial Device` totem) and a fake serial module | the outgoing Bluetooth port is found by probing for ThinkGear packets; never guessed without probing; the totem is found by Arduino's vendor id |
| Windows execution | none available here | not run; the code was reviewed for path handling, COM names, console encoding (ASCII output only) and the asyncio/threads mix |

## Against real services

| Check | How | Result |
|---|---|---|
| Deepgram prerecorded | `transcribe_file` on a 17.6 s wav synthesized with macOS `say` | 54 words with timestamps in 0.4 s |
| Deepgram streaming | `DeepgramLive` fed 100 ms PCM frames at real-time pace, mic started 2 s into the lecture | 49 final words, interim results flowing, first word stamped at 2.12 s lecture time (offset correct) |
| Microphone path through the server | WebSocket `audio_start` + binary PCM into a `transcript=deepgram` session | words broadcast on lecture time, tap produced a catch-up from the live transcript, gap built at session end |
| OpenAI | not verified: no key on this machine yet | recaps and notes ran in the labelled `offline` fallback; the client is covered by tests with a fake OpenAI (strict schema, cache, retry, timeout, reasoning-param fallback) |

## In the browser (ego-browser, built frontend served by the backend)

Home (doctor strip, session form; headset choices auto / sim / fake / custom) → live session on the scripted demo lecture with simulated headset and totem → `T` tap showed the one-line catch-up in under a second with the form label and OFFLINE badge → `F` cycled the form → `2` (drifting) produced an EEG flag: drop band on the trace, "catch-up ready" chip, totem pulse in the status strip → chip opened the card → `E` ended the session → notes page with the gap, key term and connection → review: question card, `D` walked through plain, key term, analogy and the sketch form with the stepped diagram, Continue → question → hit → done screen → tally page ("not enough data yet (1/12)", population prior shown) → loss map (n = 3, peak 40 s window, segment ranking, reveal of the planted segment) → replay page (108 events, speed selector) → quiz page (15 items, phase selector).

Screenshots from that pass were taken during the session and are not part of the repo.

## Calibration measured on the simulator

See `docs/TDD.md` §3.3. With the defaults (enter −1.25, exit −0.6, 30 s cap, 20 s refractory, 180 s baseline) a focused simulated wearer gets about 5 flags per 10 minutes and a drift is flagged after a median of about 11 s.

## On-device status (asked on 19 Sep, evening)

Nothing has run on the physical devices. This Mac has no MindWave paired (Bluetooth shows only AirPods and a speaker) and no Arduino on USB, so the serial port list is empty apart from the system ports. To test on device: pair the headset (System Settings, Bluetooth, pin 0000), plug the UNO R4 in, flash `firmware/totem/totem.ino`, then `uv run reflow doctor` should show both ports and a live session with headset `auto` uses the real pipeline. The pipeline itself was validated on a real head by its author on a Windows laptop.

## Not verified (needs the hardware or the event)

- A real MindWave Mobile 2 on a real forehead: pairing, the serial port name, blink ticks on the trace, the false-flag rate and the drift latency of a real wearer (the hour-1 gate).
- A real UNO R4 with a foil pad: touch threshold (`TOUCH_THRESHOLD` in the sketch), USB port name, LED matrix rendering.
- OpenAI structured outputs with a real key and the event's model id (`reflow doctor` reports availability and alternatives).
- Browser microphone capture in the live view (getUserMedia + AudioWorklet): the server side of that path is verified; the browser side compiled and is exercised only by hand.
- HackMIT's rule on pre-written code and AI assistance; the Deepgram and OpenAI booth requirements beyond the challenges PDF.
