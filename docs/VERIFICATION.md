# Verification record (19 Sep 2026, updated after the mindwave bridge merge)

What was checked, how, and what is still unverified. Re-run the commands before the demo; the outcomes below are from the build day on Joaquin's laptop (macOS, Python 3.13.14, Node 24, pnpm 11.13, arduino-cli with core arduino:renesas_uno 1.6.0).

## Automated

| Check | Command | Result |
|---|---|---|
| Backend unit + integration tests (parser, features, blinks, spans, recaps, LLM client with a fake OpenAI, tally, review, loss map, session runtime, REST + WebSocket real-time flow, study analysis, Deepgram client parsing, mindwave bridge on `FakeSource` with a byte-level cross-check of both ThinkGear parsers, port detection on macOS and Windows listings with a fake serial module) | `uv run pytest -q` | 79 passed in about 22 s, no network, no hardware |
| Lint | `uv run ruff check neuropace tests scripts` | clean (the spec's three sim scripts are kept verbatim and excluded from style rules) |
| Frontend types + build | `cd frontend && pnpm typecheck && pnpm build` | 0 errors, 67 modules, `dist/` served by the backend |
| Firmware | `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem` and `:minima` | both compile (57 KB / 44 KB) |
| Spec toolkit | `uv run neuropace sim selftest` | SELFTEST PASS |
| Live end-to-end against a running server, everything simulated | `uv run neuropace serve` then `uv run python scripts/smoke_e2e.py --baseline 8` | 14/14 PASS; tap to catch-up 1 to 3 ms |
| Tap confirms an EEG flag (TDD §6 linking rule) | unit test on the runtime plus a live WebSocket check: simulated drift, EEG flag opens, tap 8 s later | the tap span starts at the drop (`linked_eeg` set), the card carries `since` and `span_seconds`; a tap more than 10 s after the flag closed is not linked |

## The team's EEG pipeline (`mindwave/`, merged from brianzliu/neuropace)

| Check | How | Result |
|---|---|---|
| Standalone runner still works from the merged repo | `uv run python run_pipeline.py --fake --no-ws --no-log` | one frame line per second (effort, engagement, blink rate, eSense) |
| Bridge over the API | session with `headset: "fake"`, `POST /calibrate`, WS `calibrate`, `sim_headset: drifting` | `mw` extras on focus samples, `cal_phase` follows the commands, EEG flag 22 s after the switch, `headset_kind` stored as `fake` |
| Live view on the fake headset | ego-browser: "fake headset" badge, calibration buttons, "calibrating: eyes_closed" chip | renders |
| Real MindWave through the bridge | not verified: no headset on this machine | the pipeline itself was validated on a real head by its author (`EEG_PIPELINE.md`); `auto` picks it up when a `MindWave` serial port is present |

## Generated content policy (no placeholder text)

| Check | How | Result |
|---|---|---|
| No selected model-provider key | `POST /api/sessions` with the default settings | refused with 400 explaining that an OpenAI or OpenRouter key is required; `neuropace doctor` prints REQUIRED |
| OpenAI down mid-lecture | runtime test with a failing fake client | recaps skipped with one notice; the tap catch-up shows the verbatim transcript (`source: transcript`), all four forms identical, no "(offline)" text |
| OpenAI down at session end | same test | gap package retried 3 times, stored as `package_source: failed` with the error; review refuses (409); `regenerate_packages` fills it once the API answers |
| Real OpenAI call | not verified: no key on this machine | the client is exercised with a fake OpenAI (strict schema, cache, retries, reasoning-param fallback) |

## Totem keyboard fallback

| Check | How | Result |
|---|---|---|
| No Arduino → keyboard totem | unit tests on `make_totem` and `KeyboardTotem`; `neuropace doctor` | kind `keyboard` with the hint "no Arduino: press Space or T, or use the on-screen pad" |
| Terminal keys in `neuropace serve` | server started under a pseudo-terminal, Space then L pressed in that terminal | flags `('key', simulated False)` then `('forced', simulated True)` on the running session |
| Browser/API tap source | WebSocket `tap` and `POST /tap` | source `key`, `simulated: false` (a learner action, not a simulation) |
| Arduino plugged in mid-session | unit test with a fake serial totem and a patched detector | the session switches from keyboard to the Arduino within one 5 s probe, replays FIT/DOT, records `totem_kind = real` |

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
| OpenAI | not verified: no key on this machine yet | sessions now refuse to start without the key; the client is covered by tests with a fake OpenAI (strict schema, cache, retry, timeout, reasoning-param fallback) |

## Merge with the team's NeuroPace shell (19 Sep, late night)

The teammate's 20 commits (package renamed to `neuropace`, the Pocket Studio shell with Dashboard / Library / Insights, board capture, OpenAI or OpenRouter providers, local bridge, UNO Q relay) were merged with the work above, keeping both sides: their shell and theme, our features inside it (real brain-wave labels and the headset-lost state, the quit-recording guard, the templates and the preview page, private tutoring with the voice, review on my own, the combined ranking, the virtual headset, one headset one recording). Resolved by hand in 22 files; the two "lost me" buttons became "Catch me up". Two more decisions from the user's rule (his design, our features and quality): the API-key and model inputs left the student's start screen for the Team page, and the start screen got our device line ("Headset connected.", polled every 4 s). One collision found and fixed: the theme's global `.live` layout rule matched our `pill.live` and `waves.live` state classes and stretched them to the viewport; they are `is-live` now. Verified after the merge: `uv run pytest -q` 124 passed (the union of both suites), `pnpm build` clean, and a browser pass with the virtual headset through the merged screens: dashboard, start screen without key inputs, practice lecture with "live from your headset", the quit-recording guard from the top bar, done, private tutoring with the voice reading, the templates page, Library, You, Team.

## Real brain waves, templates, tutoring (19 Sep, late night)

Asked for: brain waves that are the device's own bytes with a fallback that says so, a "quit recording?" guard, richer generation types built from type-specific data (including web animations), a rethink of restudy, and a test of the whole site as if a real headset were connected.

**The virtual headset.** `reflow virtual-headset` puts a MindWave on a pseudo-terminal: one 0x80 raw packet per sample at 512 Hz and a 1 Hz status packet (poor_signal, eSense, eight EEG power bands), from the pipeline's FakeSource. The server was started with `REFLOW_HEADSET_PORT=/dev/ttys037`, so the serial reader, the parser, the pipeline and every screen saw a headset of kind `real`; only the bytes were synthetic. Nothing above the serial port was mocked.

| Check | How | Result |
|---|---|---|
| Raw path per headset kind | `tests/test_waves.py` | simulator: 24 chunks of 8 µV samples per 3 s at 64 Hz; pipeline fake: chunks through the runtime, stream live; replay: first chunk equals the mean of the recording's first 8 samples × UV_PER_RAW, bit for bit |
| Virtual headset over the pty | `tests/test_waves.py::test_virtual_headset…` | frames with quality 0 and finite engagement, raw chunks, `state off` → poor_signal 200, `pause 4` → disconnected after 3 s and back without reopening the port |
| Live screen with the virtual headset | ego-browser | "live from your headset", trace with blinks, focus ring "Getting to know you" → "Steady"; Space → "Catching you up" + the one-line card in the student's best family |
| Drift from the device | `state drowsy` in the control file | flagged after 11 s (lecture) and 8.8 s (restudy); chip "Want a quick catch-up?"; card with "you drifted", "since 0:29" |
| Dropout and recovery | `pause 7` | waves "waiting for the headset" in 2.4 s, focus card "Headset lost"; "live from your headset" again 7.2 s later; notices "The headset stopped sending" / "Headset back" |
| Headset switched on mid-lecture | `test_headset_that_comes_on_mid_lecture…` | a session that started simulated attaches the pipeline within a few seconds, the engine restarts on the real frames, `sim: false` on focus samples |
| One headset, one recording | `test_one_headset_one_lecture_over_the_api` | second lecture on the same port → 409; a restudy session being replaced releases the port within seconds |
| Quit-recording guard | ego-browser | clicking Lectures while recording opens "Do you want to quit recording?"; Escape keeps listening; "Stop and leave" ends the lecture and lands on the summary; `beforeunload` armed while recording |
| Restudy on the wall clock | `test_restudy_session_measures_focus_on_the_wall_clock` | found and fixed: review sessions ran on a paused media clock, so no card ever had a focus ratio and no drift ever switched an explanation |
| Templates | `tests/test_artifacts.py` + `/team/artifacts/sample` | one core call then one call per planned template (asserted call by call with a fake client), failure falls back inside the family, validators reject thin data and unsafe animation code; all ten renderings captured in the browser (curve with two series and an annotation, timeline, side by side, animation running in the sandboxed iframe, chart, diagram, steps, worked example, comparison mapping, words) |
| Offline stand-in | `test_offline_stand_in_fills_every_template…` | every template filled and labelled "(offline)"; the visual rotates across diagram, animation, timeline, compare so test mode exercises each |
| Restudy: private tutoring | ego-browser | explanation first with the reason ("Let's try it in words this time"), "Where you were", the voice reading beat by beat (first beat 0.6 s after the card, highlight follows, "Skip the reading"), then the check |
| Restudy: review on my own | ego-browser | the check first, no voice toggle, explanation after a miss |
| Drift during an explanation | `state drowsy` while reading | "You drifted. Switching to another way." → the next family (side by side) |
| Lecture page | ego-browser | Private tutoring / Review on my own; "The whole lecture" with the 56 missed words highlighted out of 114 |
| You | ego-browser | ranking 1 to 4 with rescued and held-attention bars, "still learning · 10/12 explanations scored" |
| Tutor voice | `tests/test_tts.py` + curl | Deepgram Aura returns audio/mpeg (36 KB for one sentence in 3.1 s), cached per beat, 503 without a key |
| Live microphone lecture | ego-browser | "Start listening" opens the live screen and the microphone starts by itself: the browser's own permission prompt appeared, which is the expected behaviour; not verified past the prompt (needs a person to allow it) |
| Suite | `uv run pytest -q` | 106 passed (see the git log for the exact run) |

Not verified: a real MindWave on a real forehead (still no hardware here), a real OpenAI pass over the templates (no key on this machine; the stand-ins are labelled), Windows execution.

## Product v2, streamlined (19 Sep, night)

After the user's note that the screens carried purposeless boxes and repeated content: Home is one button ("Start listening", or "Back to the lecture" while one runs, or "Try a practice lecture" when live is unavailable) plus at most one "Next up"; the practice lecture is a fallback link, not a peer choice; Lectures is the only history; a lecture leads with Restudy and lists its moments as expandable rows; Restudy is a single column (progress, card, brain waves only with a headset; preferences appear at the lesson end and on You); You is one column with one footer line for the device. Orphaned "running" sessions from a previous server process are closed at startup with their flags kept as moments. Verified in the browser: Home, Lectures, Lecture, Restudy, You.

## Product v2 (19 Sep, night)

Backend: four explanation families with a migration from the old form keys, the artifact catalogue (summary, key idea, analogy, diagram, chart with real numbers only, steps for processes, worked example) chosen inside a family by content, headset-only restudy sessions that stream brain waves and flag drifts, per-card focus ratio, profile and reset. `uv run pytest -q`: 83 passed, including the migration, artifact choice, the restudy stream and focus recording.

Frontend: rebuilt as the consumer product in `docs/PRODUCT.md` with a Duolingo-derived design system: Listen (one decision, one button), Listening (transcript, live brain waves with theta/alpha/beta, focus ring, one "I'm lost" button, catch-up HUD, Details for the team), Lecture done, Lectures, one lecture's moments, Restudy as a lesson (progress bar, question, artifact explanation with progressive reveal, three in a row, lesson complete with what worked), You (streak, moments, how you learn best with rescued and held-attention bars, start fresh), For the team (readiness, technical session, replay, loss map, quiz). Verified with `pnpm typecheck`, `pnpm build` and ego-browser screenshots of every screen in light and dark.

Not verified: a real OpenAI generation of the artifact catalogue (no key on this machine; the schema is tested with a fake client), a real headset in restudy.

## Single learner per device (19 Sep, late evening)

The learner picker is gone: every session belongs to this device's learner `lrn_me` ("you"), created on demand; `/api/learners/me` and `/tally/me` resolve to it. A study participant name can still be given under Advanced options (created on first use, reused case-insensitively) so the study keeps tallies apart. Verified: `uv run pytest -q` (79 passed, including the default and named-participant paths) and a browser run where Start listening with no learner produced a session on `lrn_me` and the tally page read "What works for you".

## Consumer pass (19 Sep, late evening)

After the user's note that the app read as a developer tool, the shell became a sidebar-and-content window and every student-facing screen was rebuilt around one decision at a time: Home is "Ready when you are" with learner chips, lecture cards and one "Start listening" button; the live screen is the transcript, a calm focus ring with a sentence, the catch-up HUD and one "Lost me" button; notes and review use plain-language copy ("What you missed", "Make it stick", "What works for you"). Ports, z-scores, headset and pad status, rolling recaps, calibration and the simulated-headset keys now live behind "Details" on the live screen and "Advanced options" under Setup on Home, so demos and judges can still see everything. Verified in the browser (ego-browser) in light and dark.

## Design system pass (19 Sep, evening)

The frontend was rebuilt on a macOS-style design system (tokens for light and dark, toolbar with segmented navigation and theme control, grouped inset lists, capsules, HUD catch-up card, notification-style chip, sheet review card). Verified with `pnpm typecheck`, `pnpm build`, and ego-browser screenshots of every view in light and dark: Home, Live (Space tap, HUD, chip, focus trace), Notes, Review (question, the four re-teach forms, diagram, done), Tally, Loss map, Replay, Quiz. Two fixes after review: the HUD now sits over the document column instead of covering the inspector, and the HUD and chip are more opaque so they stay legible over the trace in dark mode.

## In the browser (ego-browser, built frontend served by the backend)

Home (doctor strip, session form; headset choices auto / sim / fake / custom) → live session on the scripted demo lecture with simulated headset and totem → `T` tap showed the one-line catch-up in under a second with the form label and OFFLINE badge → `F` cycled the form → `2` (drifting) produced an EEG flag: drop band on the trace, "catch-up ready" chip, totem pulse in the status strip → chip opened the card → `E` ended the session → notes page with the gap, key term and connection → review: question card, `D` walked through plain, key term, analogy and the sketch form with the stepped diagram, Continue → question → hit → done screen → tally page ("not enough data yet (1/12)", population prior shown) → loss map (n = 3, peak 40 s window, segment ranking, reveal of the planted segment) → replay page (108 events, speed selector) → quiz page (15 items, phase selector).

Screenshots from that pass were taken during the session and are not part of the repo.

## Calibration measured on the simulator

See `docs/TDD.md` §3.3. With the defaults (enter −1.25, exit −0.6, 30 s cap, 20 s refractory, 180 s baseline) a focused simulated wearer gets about 5 flags per 10 minutes and a drift is flagged after a median of about 11 s.

## On-device status (asked on 19 Sep, evening)

Nothing has run on the physical devices. This Mac has no MindWave paired (Bluetooth shows only AirPods and a speaker) and no Arduino on USB, so the serial port list is empty apart from the system ports. To test on device: pair the headset (System Settings, Bluetooth, pin 0000), plug the UNO R4 in, flash `firmware/totem/totem.ino`, then `uv run neuropace doctor` should show both ports and a live session with headset `auto` uses the real pipeline. The pipeline itself was validated on a real head by its author on a Windows laptop. The current target is the UNO Q 4 GB relay (`firmware/uno_q_relay/`), which has not been compiled, flashed, or paired; its blockers are listed there. The R4 steps above are the direct fallback route.

## Not verified (needs the hardware or the event)

### Vercel deployment, 19 Sep 2026

**Historical deployment:** The existing Vercel hostname is
https://neurospace-hackmit.vercel.app. It remains an allowed origin until the deployment is
moved, but the product, package, CLI, and interface now use NeuroPace. Local connection copy
uses `uv run neuropace serve`.

- Production: https://reflow-neuropace.vercel.app, deployment
  `dpl_DhSociVPcNKQvZhiN7TccTduxkLw`, confirmed Ready by `vercel inspect`.
- `pnpm build` passed locally and on Vercel. Only the frontend directory was deployed.
- `uv run pytest -q`: 76 passed. Includes hosted-origin HTTP pairing, CORS preflight,
  media token enforcement, and WebSocket origin/token rejection and acceptance.
- `uv run ruff check neuropace tests scripts` passed.
- HTTPS checks returned 200 for `/`, `/session/new`, `/review/deployment-check`, and both
  generated JS/CSS assets. The deployed bundle contains the local connection screen and
  loopback backend address.
- A browser was unavailable to the UI automation tool, so the hosted browser-to-localhost
  permission flow, audio, camera, and media playback remain unverified in a real browser.
  The already-running local backend needs a restart to load the pairing changes.

### Remaining hardware and service checks

- A real MindWave Mobile 2 on a real forehead: pairing, the serial port name, blink ticks on the trace, the false-flag rate and the drift latency of a real wearer (the hour-1 gate).
- A real UNO R4 with a foil pad (fallback route): touch threshold (`TOUCH_THRESHOLD` in the sketch), USB port name, LED matrix rendering.
- A real UNO Q 4 GB: relay compile/flash, headset pairing and BLE permissions, App Lab compatibility, encrypted access, throughput/dropped frames, D2/GND wiring, and an end-to-end tap + feature-frame test. Blockers are listed in `firmware/uno_q_relay/README.md`.
- OpenAI structured outputs with a real key and the event's model id (`neuropace doctor` reports availability and alternatives).
- Browser microphone capture in the live view (getUserMedia + AudioWorklet): the server side of that path is verified; the browser side compiled and is exercised only by hand.
- HackMIT's rule on pre-written code and AI assistance; the Deepgram and OpenAI booth requirements beyond the challenges PDF.

### Pocket Studio and main integration, 19 Sep 2026

The current product name is **NeuroPace**. Historical deployment URLs and CLI aliases
remain compatible. Main's lecture, quiz, and restudy flow is merged with the Pocket
Studio dashboard, syllabus, camera capture, and local device bridge.

- Full backend suite: `uv run pytest -q`, **92 passed**.
- `uv run ruff check neuropace tests scripts` passed.
- `npm --prefix frontend run build` passed, including TypeScript checking.
- Safari preview used an isolated temporary server on port 8766 with synthetic
  sessions, simulated EEG, keyboard input, and explicitly enabled offline fixtures.
  Dashboard concepts, activity, syllabus progress, Library, quiz questions and selection,
  restudy, and the prominent Start session page were checked visually.
- This verification did not exercise physical hardware, microphone/camera permissions,
  external model generation, or production deployment. The existing local data and
  backend on port 8765 were left untouched.
