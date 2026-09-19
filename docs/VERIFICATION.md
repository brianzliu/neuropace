# Verification record (19 Sep 2026)

What was checked, how, and what is still unverified. Re-run the commands before the demo; the outcomes below are from the build day on Joaquin's laptop (macOS, Python 3.13.14, Node 24, pnpm 11.13, arduino-cli with core arduino:renesas_uno 1.6.0).

## Automated

| Check | Command | Result |
|---|---|---|
| Backend unit + integration tests (parser, features, blinks, spans, recaps, LLM client with a fake OpenAI, tally, review, loss map, session runtime, REST + WebSocket real-time flow, study analysis, Deepgram client parsing) | `uv run pytest -q` | 55 passed in about 17 s, no network, no hardware |
| Lint | `uv run ruff check reflow tests scripts` | clean (the spec's three sim scripts are kept verbatim and excluded from style rules) |
| Frontend types + build | `cd frontend && pnpm typecheck && pnpm build` | 0 errors, 67 modules, `dist/` served by the backend |
| Firmware | `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem` and `:minima` | both compile (57 KB / 44 KB) |
| Spec toolkit | `uv run reflow sim selftest` | SELFTEST PASS |
| Live end-to-end against a running server, everything simulated | `uv run reflow serve` then `uv run python scripts/smoke_e2e.py --baseline 8` | 14/14 PASS; tap to catch-up 1 to 3 ms |

## Against real services

| Check | How | Result |
|---|---|---|
| Deepgram prerecorded | `transcribe_file` on a 17.6 s wav synthesized with macOS `say` | 54 words with timestamps in 0.4 s |
| Deepgram streaming | `DeepgramLive` fed 100 ms PCM frames at real-time pace, mic started 2 s into the lecture | 49 final words, interim results flowing, first word stamped at 2.12 s lecture time (offset correct) |
| Microphone path through the server | WebSocket `audio_start` + binary PCM into a `transcript=deepgram` session | words broadcast on lecture time, tap produced a catch-up from the live transcript, gap built at session end |
| OpenAI | not verified: no key on this machine yet | recaps and notes ran in the labelled `offline` fallback; the client is covered by tests with a fake OpenAI (strict schema, cache, retry, timeout, reasoning-param fallback) |

## In the browser (ego-browser, built frontend served by the backend)

Home (doctor strip, session form) → live session on the scripted demo lecture with simulated headset and totem → `T` tap showed the one-line catch-up in under a second with the form label and OFFLINE badge → `F` cycled the form → `2` (drifting) produced an EEG flag: drop band on the trace, "catch-up ready" chip, totem pulse in the status strip → chip opened the card → `E` ended the session → notes page with the gap, key term and connection → review: question card, `D` walked through plain, key term, analogy and the sketch form with the stepped diagram, Continue → question → hit → done screen → tally page ("not enough data yet (1/12)", population prior shown) → loss map (n = 3, peak 40 s window, segment ranking, reveal of the planted segment) → replay page (108 events, speed selector) → quiz page (15 items, phase selector).

Screenshots from that pass were taken during the session and are not part of the repo.

## Calibration measured on the simulator

See `docs/TDD.md` §3.3. With the defaults (enter −1.25, exit −0.6, 30 s cap, 20 s refractory, 180 s baseline) a focused simulated wearer gets about 5 flags per 10 minutes and a drift is flagged after a median of about 11 s.

## Not verified (needs the hardware or the event)

- A real MindWave Mobile 2 on a real forehead: pairing, the serial port name, blink ticks on the trace, the false-flag rate and the drift latency of a real wearer (the hour-1 gate).
- A real UNO R4 with a foil pad: touch threshold (`TOUCH_THRESHOLD` in the sketch), USB port name, LED matrix rendering.
- OpenAI structured outputs with a real key and the event's model id (`reflow doctor` reports availability and alternatives).
- Browser microphone capture in the live view (getUserMedia + AudioWorklet): the server side of that path is verified; the browser side compiled and is exercised only by hand.
- HackMIT's rule on pre-written code and AI assistance; the Deepgram and OpenAI booth requirements beyond the challenges PDF.
