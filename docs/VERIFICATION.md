# Verification record (19 Sep 2026, updated after the mindwave bridge merge)

What was checked, how, and what is still unverified. Re-run the commands before the demo; the outcomes below are from the build day on Joaquin's laptop (macOS, Python 3.13.14, Node 24, pnpm 11.13, arduino-cli with core arduino:renesas_uno 1.6.0).

## Same-screen launch and proactive visual lessons: 20 Sep 2026

The popup came from `window.open`; the live overlay accepted only four strings; tutoring selected precomputed formats and waited for manual advancement. The new path reuses the existing artifact builder and sandboxed renderers, with bounded live generation and answer-specific model selection after misses.

Browser session `sess_4dcba6bc` used a labelled practice transcript and real model/TTS calls. Dashboard Start session kept the same tab (one before and after). Catch me up displayed a generated pendulum animation; screenshots one second apart showed its bob on opposite sides of the pivot. The transcript continued, and switching to the worked example revealed its next step. Tutoring began with the animation and reached its check without a Got it click. Choosing constant speed made the model select an analogy with a reason addressing that specific misconception. Natural playback led to the next check; the correct answer ended at Every moment covered. Saved cards confirm animation/read, question/miss, analogy/read, question/hit.

A planning ambiguity initially selected a timeline for physical motion. Prompt version 11 distinguishes spatial oscillation from chronology. Direct provider checks then selected animation for the motion example and plot for numerical growth. Before the final prompt wording change, the combined checks passed 247 backend tests and 73 frontend tests; the final browser/provider pass, frontend build, lint/format, and rebuilt wheel also passed. This pass does not claim new EEG-accuracy evidence.

## Judge demo rehearsal with EEG unavailable: 20 Sep 2026

Claude's completed non-EEG demo fixes are present in local commit `4947e46`; the remaining local work keeps the primary-effort correction and adds an explicit button-only continuation. Real/replay devices no longer report a fake state or accept simulator state controls.

The full browser rehearsal `sess_5989ed1d` passed on a separate demo learner: Start session, headset unavailable, Continue with button only, real microphone capture of the spoken compound-interest lesson, Catch me up, End lecture, Private tutoring, Cole narration with a chart revealing $110 and $121, an intentional $10 answer to the second-year-interest question, re-teaching in words, then the correct $11 answer and Every moment covered. The session captured 176 words, created one real key/tap flag, used a generated cached recap, and saved one LLM-generated study gap. It finished reviewed with two answers, one closed moment, and no outstanding runtime. No EEG flag or attention score was fabricated; the learner baseline stayed unset and restudy did not start a headset session.

An unreviewed saved copy of that recorded rehearsal is available at `/lecture/sess_ec7e5f55`, titled Saved demo: compound interest. It is a cached-content backup, not a new live capture. The original completed rehearsal is unchanged.

Final combined checks: 205 backend tests, 18 frontend tests, TypeScript/Vite build, Ruff lint/format, diff checks, and isolated wheel startup passed. The required demo sequence is in `docs/DEMO-RUNBOOK.md`. Live EEG remains optional for completing the demo; physical camera/Arduino, hosted deployment, loss-map presentation, and new accuracy studies are outside this pass.

## Focus input correction after the live release check: 20 Sep 2026

The real session `sess_4e931769` completed 30/30 clean calibration seconds and kept streaming after a headset power cycle. Microphone capture, manual catch-ups, sample-workspace switching, the new whiteboard, browser narration, and the packaged installation worked. A fresh review session loaded the saved personal baseline unchanged. The full software readiness command passed with 188 backend and 18 frontend tests before the input correction below.

The wearer confirmed silent counting during calibration and silent eyes-open daydreaming during the spoken check. The microphone captured “Begin now” at lecture time 267.179 and the stop cue at 304.639. The monitored interval had 35/35 valid focus ticks and 281 raw chunks. The old beta-based score stayed positive (w15 1.175 to 2.569), so the unchanged -1.25 trigger could not fire. It also stayed above the trigger for 30 seconds on either side. Two actual EEG flags at 94.608 and 172.607 verified the real event path, but were outside the confirmed drift interval.

The consumer used secondary engagement as its sole input, contrary to `EEG_PIPELINE.md`'s primary-effort guidance. Mean raw effort fell from 0.3436 during counting to 0.1453 during confirmed drift, while mean engagement rose from -0.5163 to -0.3317. The correction selects the existing theta/alpha effort feature without changing the MindWave feature formulas or detector thresholds. Calibration now clears waiting-period EMA history, and saved baselines carry a metric version so legacy engagement baselines cannot be misinterpreted.

Replaying the unchanged recording through the corrected SessionRuntime, including calibration, its reset, and catch-up generation, produced one EEG flag at 283.607 (16.43 seconds after the recorded start cue), plus a chip and a non-auto-opening catch-up. This is recorded-data verification, not a fresh live accuracy result.

Fresh live confirmation then passed in `sess_9da187b6`: the new 30-second baseline was saved with metric `theta_alpha_v1`; the native spoken drift cue was captured from lecture time 14.430; a real, non-forced EEG flag fired at 43.122 (about 29 seconds after the cue began, 24 seconds after playback finished). All 40 observed focus frames, including the short cue, were usable, with w15 reaching -1.538. The browser displayed the catch-up offer, Show me opened its explicitly labelled transcript fallback, and ending the session saved one LLM-generated study gap. Tutoring opened that actual gap with a grounded pendulum explanation and voice narration. This is one successful live check, not a population-level accuracy claim.

All 197 backend tests passed, including the new input-selection, baseline-version, smoothing-reset, and connection-startup regressions. Lint/format and the isolated wheel check passed. Native Bluetooth now gets 30 seconds for its first valid packet, then retains the existing five-second stalled-stream recovery. This prevents premature handshake cancellation; it does not resolve every macOS/headset failure. A power cycle was still required for the successful fresh hardware check.

## MVP startup and tutor voice integration: 20 Sep 2026

Real-headset lecture sessions now begin with the existing 30-second focused calibration, without reconnecting the headset. Failed calibration preserves the previous baseline; recording and attention flags wait until calibration succeeds and the learner starts the lecture. Simulated practice remains labelled and does not save a personal calibration.

Learning narration uses the separate server-side Deepgram TTS credential, `flux-cole-en`, `/v2/speak`, and expressivity `2`. The actual API returned audio; transcribing the preview recovered its exact wording. Ego played multiple narration beats to completion, advanced the explanation, stopped playback, recovered through Retry voice after an injected HTTP 503, and completed the question/review flow. Re-enabling voice now restarts the current explanation.

Verification: 185 backend tests, 18 frontend tests, lint/format, TypeScript/build, the live-server scripted smoke, and isolated wheel startup passed. The wheel excludes dotenv files. Calibration success, persistence, retry, and same-connection transition were checked with controlled runtime inputs, not new human measurements.

Hardware limitation remains: the real startup check (`sess_79435283`) received zero raw chunks across 46 focus ticks. The browser stayed on Waiting for the headset, disabled calibration, and did not start the microphone. A successful physical-headset calibration-to-lecture run was not verified in this pass. No detector thresholds or EEG feature formulas were changed.

## Signal calibration audit and personal-baseline workflow: 20 Sep 2026

The completed measurement is `sess_33d42adb`, recorded under
`data/eeg/20260920-003519/`. Brief ElevenLabs prompts were played natively while the browser
showed a centre dot and the current instruction. There was no lecture or comprehension quiz.
Earlier interrupted lesson/audio attempts are not included in this analysis.

### Manual audit of the real recording

The audit is reproducible with:

```
uv run --group monitor python -m scripts.audit_eeg_calibration data/verification/trial-20260920-003412 --plots
```

The local output directory contains `manual-audit.json`, `manual-audit.png`, the original
phase markers and telemetry. Participant-level artifacts and generated speech files are now
ignored by git. They are not bundled into the distribution.

| Check | Measured result |
|---|---|
| Raw input | 93,687 real samples at the nominal 512 Hz rate; no int16 rail clipping |
| Raw-to-feature reconstruction | All 179 logged four-second windows reproduced from raw data; maximum error 0.000049975, within the stored four-decimal rounding |
| Signal availability | 179 valid pipeline windows; 192 runtime ticks included startup without usable signal; 178 runtime ticks reported poor_signal=0 |
| Band routing | Independent 6, 10 and 20 Hz input checks selected theta, alpha and beta respectively |
| Eyes-closed response | Alpha power increased about 3.8 times; the recomputed eyes-closed spectrum had a clear 9 Hz alpha peak |
| Artifact review | Median masked fraction was zero in the eyes-open, eyes-closed and counting windows, and 5.71% during the instructed daydream block |
| Actual live automatic attention flags | Zero |

The actual engagement ratio, expressed as a geometric mean of beta/(alpha+theta), was
approximately 0.485 during the first counting block, 0.406 during daydreaming and 0.642
during counting again. The raw index varied substantially within blocks. Theta/alpha effort
was higher during daydreaming than during counting, so it must not simply be renamed an
attention score. Forehead beta/gamma can contain muscle activity; good contact alone does
not prove that every change is cognitive.

### Why the live detector did not fire, and what the replay establishes

The live diagnostic's automatic focus baseline included deliberate eyes-closed and relaxed
periods. That is not an appropriate focused-lecture reference. During the later daydream
block, its 15-second z average reached only -0.63, above the unchanged -1.25 entry threshold.
The diagnostic exposed baseline contamination, not an end-to-end successful attention test.

An exploratory replay kept the same feature, smoothing, sigma floor, -1.25 entry, -0.6 exit,
cap and refractory logic. Its reference was fitted only on the first counting block, then
run forward through the later data. It entered a drop at session time 137.008, ten seconds
after the recorded daydream phase began, and exited at 151.008. It produced no entry during
the later counting block. Daydream minimum w15 was -1.954; later counting minimum was -0.795.
No threshold was selected using those later outcomes.

Important distinction: this replay used the legacy `baseline_seconds=30` rehearsal rule,
which finalizes after 18 clean samples. The new explicit personal-calibration workflow below
waits for the full 30-second window. The replay is not a live validation of that new workflow.
One instructed daydream block and one later counting block cannot establish sensitivity,
specificity or a personal optimum. Task labels remain instructed conditions rather than
independent verification of the participant's actual mental state. Adjacent EEG windows overlap
and must not be treated as independent participants. A future focused-only live run and a
real-lesson outcome check are still required before claiming reliable catch-up effectiveness.

### Changes made after the audit

- Explicit pipeline diagnostic phases no longer update the normal focus baseline/EMA or
  open attention-lapse flags. Raw waves and diagnostic band measurements continue. Both
  contamination and spurious-flag regression tests failed before the guard and passed after it.
- `scripts/calibrate_user.py` measures a focused 30-second window after clean-signal preflight.
  Default mode is a preview. `--apply` saves a personal baseline only after at least 24 distinct
  seconds pass the existing contact/artifact gates, with no missing run longer than two seconds.
  Simulated, paused, nonfinite and diagnostic-phase samples cannot qualify. The stored values
  are the mean and sample deviation of the existing smoothed log engagement, with the existing
  sigma floor. Feature weights and entry/exit z thresholds are unchanged.
- Saving is compare-and-set against the prior baseline timestamp. A newer calibration cannot
  be overwritten; failures, previews and session shutdown preserve the previous baseline.
  Tests also cover a fresh consumer session loading the saved values.
- The additive `baseline_source` field distinguishes explicit personal calibration from old
  automatic references. A new session reuses an explicit personal baseline by default;
  `use_stored_baseline=false` still requests a fresh baseline. Legacy automatic references
  retain the old opt-in behavior. Profile reset clears the new metadata too.
- No baseline from the mixed diagnostic was applied to the device learner. On the restarted
  server, the device's `baseline_source` remained null. The new 30-second routine was verified
  with hermetic data and API tests, not a new live wearer calibration in this pass.

Commands:

```
uv run python scripts/calibrate_user.py
uv run python scripts/calibrate_user.py --apply
```

### Verification after the last implementation edit

`uv run python scripts/verify_readiness.py` passed: **181 backend tests**, **15 frontend
tests**, lint, format (97 Python files), TypeScript/Vite build, evaluation self-test, wheel
build and isolated distribution startup. All **4 personal-calibration mutants** and all
**5 audio mutants** were killed. `git diff --check` passed. The backend was restarted as
PID 84124, and a fresh HTTP client verified both personal-calibration endpoints in the live
OpenAPI schema. No scientific accuracy percentage is implied by these software tests.

Browser audio delivery remains unresolved and was explicitly deferred by the user; the
successful native ElevenLabs playback is not labelled a browser fix. No commit or push was made.

## Latest battery retest: 19 Sep 2026, 23:31

The user tried another battery before any proposed transport change. The implementation,
Bluetooth helper, reconnect policy and running backend were unchanged for both tests.
The previous streaming/reconnect failure did not reproduce with this battery.

| Check | Result |
|---|---|
| 60 s recording, `sess_71ff3e3e` | 3,216 decimated raw samples (402 display chunks). First data after 9.84 s; maximum subsequent inter-chunk gap 0.240 s; stream live at end, newest chunk age 0.10 s. Bluetooth continuity passed. |
| Signal quality in that recording | 17/60 good and valid focus ticks; insufficient valid input to complete the 30 s test baseline. The combined test command exited nonzero for this reason, not for a Bluetooth dropout. Its generic "No sustained stream" exit text was misleading and is not the interpretation used here. |
| Fresh session after ending, `sess_6d323e42`, 45 s | 2,312 decimated raw samples (289 chunks). First data after 9.25 s; maximum subsequent gap 0.208 s; stream live at end, newest chunk age 0.01 s. Reconnect passed without a headset reset between these sessions. |
| Fresh calibration in the second session | 29/45 good and valid focus ticks, including 27 ticks with poor_signal=0. A new baseline completed (`stored: false`, `ready: true`); the test did not rely on the previous saved baseline. |

Both runs reported `kind: real`, `simulated: false`. The initial no-signal ticks include
connection and feature-window startup. Brief poor-contact readings remained during the
second run, but they did not interrupt the Bluetooth byte stream. Recordings are under
`data/eeg/20260919-233122/` and `data/eeg/20260919-233302/`. Both lectures were ended cleanly.

**Current conclusion:** this battery replacement/power cycle restored continuous Bluetooth
streaming and session-to-session reconnect in the unchanged app. Contact still determines
whether a frame can be used for focus. The earlier five-second native-startup watchdog
concern is a possible robustness issue, not an established cause of the historical failures;
no transport change was applied. This result supersedes the Bluetooth blocker recorded below,
but is not a long-duration reliability claim or a verification of the other deferred hardware.

## Battery replacement retest: 19 Sep 2026, 23:15

The user replaced the headset battery. Both checks below used the same running backend
and unchanged implementation. EEG was real; the lecture transcript was the labelled GPS
practice script, so no microphone capture was needed.

| Check | Result |
|---|---|
| Repeat the prior 60 s test, session `sess_5d16dccc` | 1,968 decimated raw display samples (246 chunks); 21/60 focus ticks had good signal; the 30 s test baseline became ready. First raw data arrived after 10.47 s. The original minimum gate passed, but the maximum inter-chunk gap was 8.32 s and the stream was no longer live at the end. |
| Browser | Observed real waves, "LIVE FROM YOUR HEADSET" and "Steady" after calibration. The view also showed the appropriate adjustment/lost-signal states when quality or liveness deteriorated. |
| Concurrent device ownership | A second lecture requesting the same headset returned 409; the first session kept running. |
| End and reacquire, session `sess_610e113e` | Only 16 decimated display samples (2 chunks) in 60 s; zero good or valid focus ticks; zero pipeline feature frames. The stream was not live at the end. Reconnect check failed. |
| Stored baseline | The second session correctly loaded the first test learner's baseline (`stored: true`, `ready: true`), but this did not count as live or valid EEG. No simulated frames were substituted. |

Recordings: `data/eeg/20260919-231537/` and `data/eeg/20260919-231706/`.
Both test lectures were ended cleanly. The test learner was "Readiness hardware check";
the device learner's calibration was not reset or overwritten by these tests.

**Conclusion:** battery replacement/power cycling restored usable EEG temporarily. It did
not establish reliable sustained streaming or session-to-session reconnect. Contact varied
in the first run; the second had insufficient data to infer actual contact quality from
the default quality value. The remaining cause is unknown, and the hardware readiness
blocker stays open. No implementation changes or fresh software-suite claims accompany
this hardware-only retest.

## Latest readiness pass: 19 Sep 2026, after the state handoff

This section is the current evidence. Sections below it are historical runs, including
older statements that no headset or provider key was available. Base commit:
`8a1cb94a5e5166d5ce0070e55358e6a41ba3f626`, with the prior agents' uncommitted work preserved.
No commit, push, deployment, repository dependency change, or learner reset was performed.

### Changes and differential checks

- **Installed distribution:** the original wheel built successfully but a fresh consumer
  outside the checkout found neither the SPA nor the practice lecture. The source checkout
  passed because those assets were outside the Python package. The wheel now includes them
  under `neuropace/_assets`; app serving and doctor share the same resource paths.
  `scripts/verify_distribution.py` first failed on the old wheel, then passed on the rebuilt
  wheel in an isolated subprocess and directory. It checks SPA routes, every bundled asset,
  health, the seeded practice lecture, and the native Swift helper.
- **Microphone startup and cancellation:** five new regression cases initially failed because
  pending browser operations never settled and cancellation did not release late-granted
  capture. Permission, context startup and worklet loading now have bounded waits; leaving
  or ending aborts pending startup. Tracks and blob URLs are released on failure, and a
  browser context whose close never resolves cannot prevent session end. Successful PCM16
  conversion, idempotent stop, permission denial and unavailable-socket behavior remain tested.
- **Honest completion:** the UI used to say "You stayed with it the whole way" even when
  microphone startup failed and zero words were captured. Both zero-word and ordinary
  zero-gap regression cases failed first. The completion screen now distinguishes missing
  capture from no saved moments, without making an unsupported claim about attention.
- **Generated motion:** the first live-provider pendulum output passed schema validation but
  only moved from x=300 to x=380, never left of the pivot. Prompt version 9 explicitly requires
  a signed full-cycle sinusoid and checks both extremes. A fresh generated sample passed the
  sandboxed browser fixture check: 121 frames, x=253.27 to x=346.73 around pivot x=300,
  displacement per 50 ms of 2.512 near the bottom versus 0.061 near the extreme. The saved
  old output still fails the exact same checker with "Pendulum does not swing to both sides".
  This is evidence for this fixture, not a guarantee about every future generated explanation.

### Final automated run

Entry point: `uv run python scripts/verify_readiness.py --base http://127.0.0.1:8765`.
Executed after the last implementation edit, against a newly started backend process.

| Check | Result |
|---|---|
| `uv run pytest -q` | 135 passed in 51.52 s; baseline was also 135, no tests removed |
| `uv run ruff check neuropace tests scripts` | clean |
| `uv run ruff format --check neuropace tests scripts` | 84 files already formatted |
| `cd frontend && pnpm test` | 15 passed: 12 audio cases and 3 completion cases |
| `cd frontend && node audio.mutations.mjs` | 5/5 in-memory mutants killed: timeout, cancellation, cleanup, PCM scaling, idempotence |
| `cd frontend && pnpm build` | TypeScript check and Vite build passed, 102 modules |
| `uv run neuropace sim selftest` | SELFTEST PASS |
| `uv build --wheel` and `scripts/verify_distribution.py` | isolated distribution startup passed |
| `git diff --check` | clean |
| Live-server smoke | SMOKE PASS, session `sess_79ed8062`, tap-to-catch-up 3 ms, LLM gap package, review and tally updated |

The primary server was restarted as PID 76517 on port 8765 after confirming no lecture was
running. The effective provider/model is OpenRouter / `openai/gpt-4.1-mini`, prompt version 9.
The served frontend bundle is `index-Crcc4QLr.js`. No provider credentials were changed.

Additional opt-in check: `uv run python scripts/verify_templates.py` produced all nine
schema-valid artifacts from the real provider, with 9 calls, no fallback, no error and no
timeout. Outputs are in `data/verification/templates.json`. With an authorized active
browser workspace, `uv run python scripts/verify_animation.py --space <id>` checks the
saved pendulum fixture. Passing `--templates data/verification/pendulum-regression.json`
is a negative control and must fail.

### Browser and real-service evidence

- Ego Lite 0.5.0.32, Chromium 152.0.7977.54. Initial live microphone capture worked. A browser
  restart did not by itself resolve the apparent intermittent stall. The differential was
  the automation call: waiting inside the same call for AudioWorklet loading stalled it;
  clicking Start and returning let loading complete before the next call. Minimal probes
  at native 48 kHz, explicit 48 kHz and 16 kHz showed the same in-call stall. Browser tooling
  interference is established; the exact browser-internal cause is not.
- On the final frontend build, `sess_c77c2300` captured 76 final words through the real
  microphone, AudioWorklet, session WebSocket and Deepgram. Stop and restart both worked.
  Catch-up rendered within the viewport, and ending produced an LLM core, analogy, diagram
  and worked example. The transcript itself is not reproduced in this document.
- The quit-recording dialog was exercised both ways: Keep listening returned to the lecture;
  Stop and leave ended it and opened its completion page. No microphone was left recording.
- The zero-transcript session `sess_d1b35ad0` showed the new honest completion message.
- All ten sample tabs were available; the animation iframe used `sandbox="allow-scripts"`.
  Two screenshots showed the signal dots moving. The separate generated-pendulum check
  measured its motion in a scripts-only, no-network iframe rather than executing generated
  JavaScript in the host process.
- A fresh temporary-data server on port 8775 exercised the no-device practice route. The UI
  labelled EEG and transcription as simulated. Private tutoring (`sess_a7ad17d6`) explained
  first, read the explanation, accepted the correct answer and showed one moment landed.
  Manual review (`sess_6a35ec82`) opened with the question and no voice, then revealed an
  explanation after an intentionally wrong answer. Advancing that explanation and selecting
  the reshuffled correct option completed the moment.

### Remaining readiness limits

**A fully ready hardware claim is blocked.** Real bytes were observed in `sess_c02ce884`
(302 raw chunks, newest age 0.06 s, kind real, simulated false), but contact quality was 200.
Later sessions showed intermittent RFCOMM failure or no bytes. A dedicated 60 s check after
backend restart (`sess_e2e54619`, 30 s test baseline) saw zero raw samples, zero good focus
frames and no completed baseline. It failed explicitly and was ended cleanly. No competing
native reader remained after it ended. The cause of this intermittent hardware failure is
not established; the native Bluetooth transport and signal math were not rewritten.

The earlier, separate hardware success reported in `docs/STATE-2026-09-19.md` remains useful
historical evidence (94,088 raw samples, 181 frames and four EEG flags), but it does not turn
this failed fresh check into a pass.

Other limits: camera/whiteboard and physical Arduino tests remain deferred from the prior
scope; Windows execution and hosted-deployment verification were not performed. Strengthen
and conversational voice tutoring remain explicitly future features in `docs/PRODUCT.md`.
No claim is made that arbitrary generated content is factually perfect. Changed-line coverage
and randomized suite ordering were not measured; there is no configured frontend lint gate.
The added audio boundary/property checks and mutation tests do not replace those layers.
Spec approval was not obtained separately (autonomous run); no independent subagent review
was used. These limits prevent describing the entire product as "100% ready".

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
