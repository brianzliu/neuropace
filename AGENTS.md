# AGENTS.md

Guidance for AI coding agents working in this repo.

## What this repo is

Three things, kept deliberately separate:

0. **`neuropace/`, `frontend/`, `firmware/`, `tests/`, `docs/`, `study/`** — the NeuroPace product built
   on 19 Sep 2026 against `docs/PRD.md` and `docs/TDD.md` (the contract every module follows).
   Backend `uv run neuropace serve` (Python 3.13 via uv, FastAPI), frontend Vite + React built into
   `frontend/dist`, UNO Q 4 GB BLE relay prototype as the current hardware target
   (`firmware/uno_q_relay/`, experimental and uncompiled) with the UNO R4 direct-USB sketch
   (`firmware/totem/`) retained as a fallback. `uv run pytest -q` runs the suite (no hardware, no
   network); `uv run python scripts/smoke_e2e.py` runs against a live server. `docs/VERIFICATION.md`
   records what was verified and how. The headset front end is the `mindwave/` pipeline below,
   consumed in-process (README "EEG bridge"); NeuroPace's own simulator covers the no-hardware path.

1. **`mindwave/`** — a working, standalone EEG pipeline for the NeuroSky MindWave Mobile 2. It
   turns the Bluetooth stream into one calibrated `FeatureFrame` per second (mental effort,
   engagement, alpha, blink rate, signal quality). It has no dependency on the hackathon product
   below and makes no decisions on its own — see `EEG_PIPELINE.md` and `mindwave/README.md` before
   changing anything in here.
2. **The NeuroPace plan** — `PLAN.md` is the current, consolidated product/build plan for a HackMIT
   2026 submission built on top of the pipeline. `tracks.md` is the raw sponsor-challenge text it
   references. `neuropace_eval.py` is the pre-registered evaluation toolkit for that product's claims.

Read `PLAN.md` §0 ("How this plan evolved, and what to read") before assuming any specific
mechanic (real-time neuropace, camera fusion, learning-style detection, totem LED output) is still
current — the plan explicitly tracks which ideas were superseded and why.

## Setup and running things

```
pip install -r requirements.txt
python monitor.py --fake          # live plot with simulated EEG, no headset needed
python monitor.py                 # live plot against a real headset (paired; find its COM port)
python run_pipeline.py            # headless service: WebSocket feed + session log
python example_consumer.py --fake
python neuropace_eval.py selftest    # runs the evaluation toolkit's self-check
```

The `mindwave/` tools keep their own style and are excluded from ruff; the NeuroPace package is
linted and formatted with ruff (`uv run ruff check neuropace tests scripts`). `uv run pytest -q`
covers NeuroPace and the bridge (`tests/test_mindwave_bridge.py` runs the pipeline on `FakeSource`).
`python monitor.py` needs `uv run --group monitor` (matplotlib).

`uv run python scripts/verify_readiness.py` runs backend tests, lint/format, frontend tests and
in-memory audio mutations, the frontend build, the evaluation self-test, and an isolated wheel
startup check. Add `--base http://127.0.0.1:8765` for the live-server smoke (creates test sessions
and uses the configured providers). Build the frontend before `uv build --wheel`; the wheel now
includes the SPA and practice lecture under `neuropace/_assets/`.
`uv run python scripts/verify_templates.py` makes paid live-provider calls using synthetic
transcripts. With an active, authorized ego-browser task space, `uv run python
scripts/verify_animation.py --space <id>` checks the saved pendulum fixture's full-cycle motion
in a scripts-only sandbox. The saved `data/verification/pendulum-regression.json` is the known
bad output and must fail that check when passed with `--templates`.

For microphone checks with ego-browser 0.5.0.32, click Start and return from the browser call
before checking whether capture started. Waiting for AudioWorklet initialization within the
same automation call stalled the loader, including in a minimal browser-only probe; it completed
after the call returned. Do not mistake that automation-dependent stall for a provider outage.

Personal baseline calibration: `uv run python scripts/calibrate_user.py` previews a 30-second
focused window; `--apply` saves only if at least 24 distinct seconds are clean and no missing
run exceeds two seconds. It does not fit new EEG feature weights or alter the entry/exit z
thresholds. Explicit personal baselines are reused by default; `use_stored_baseline=false`
requests a fresh baseline. Legacy automatic baselines remain opt-in. Diagnostic `cal_phase`
frames are excluded from the normal focus baseline and attention flags. Calibration failures
must preserve the previous learner baseline, including when the session is ended.
Real-headset live and recorded sessions now open with the same 30-second calibration on the
existing connection. The server holds transcript capture and attention flags until calibration
is saved and the user starts the lecture. Review sessions reuse that baseline. Explicit simulated
practice skips personal calibration. Calibration time is excluded from lecture focus samples.
The production focus input is now the pipeline's primary effort index, `log10(theta/alpha)`,
versioned as `theta_alpha_v1`. Engagement remains telemetry, not the sole decision signal.
Stored baselines with another or missing `baseline_metric` must not be reused on this scale;
leave their values intact until a new personal calibration succeeds. Starting calibration
resets the input EMA so waiting-period values cannot contaminate its fit. Raw and pipeline
inputs both use log10. Synthetic focused/drifting profiles must reflect this selected metric.
Native Bluetooth gets a 30-second first-valid-packet allowance because its connection helper
negotiates asynchronously; after a valid packet, the existing five-second stall recovery applies.
This startup allowance is not a claim that all macOS/headset reconnect failures are solved.
Judge-demo fallback: POST `personal-calibration/skip` explicitly starts button-only recording.
It cancels any partial calibration, preserves the learner baseline, marks `focus_enabled=false`,
and suppresses automatic EEG flags and focus scores while keeping real transcription and taps.
The flag persists in session baseline metadata; restudy must not start another focus session for
that recording. Never substitute simulated EEG for this fallback. Real/replay headset status
has no synthetic `state`; simulation controls are rejected outside explicit fake mode.

Learning TTS uses `DEEPGRAM_TTS_API_KEY` (falls back to `DEEPGRAM_API_KEY` for older setups),
`NEUROPACE_TTS_MODEL=flux-cole-en`, and `NEUROPACE_TTS_EXPRESSIVITY=2`. Local `.env.tts` is
loaded alongside `.env`, ignored by git, and must never be bundled. Flux uses `/v2/speak`;
Aura compatibility uses `/v1/speak`. `npm test` in `frontend/` includes playback failure and
cancellation checks. Browser voice failures show Retry voice and leave the explanation readable.

For local raw-data audits, use `uv run --group monitor python -m scripts.audit_eeg_calibration
<local-trial-directory> --plots`. The audit reconstructs logged features from 512 Hz raw
samples and labels focused-only replay as exploratory, not a new live validation. Raw and
participant-level trial artifacts stay under ignored `data/verification/` subdirectories.
`uv run python scripts/verify_personal_calibration.py` runs the four in-memory calibration
mutations and is included in the readiness runner.

## Working in `mindwave/`

- This code was written against a **real headset** and the numbers in `EEG_PIPELINE.md` (AUC,
  blink artifact behavior, calibration anchors) are load-bearing claims, not defaults to casually
  change. If you touch `features.py` (filtering, blink masking, band-power math) or
  `calibration.py` (z-scoring, anchor logic), re-read `EEG_PIPELINE.md` first and check whether the
  change invalidates a number quoted there or in `PLAN.md`.
- `pipeline.py`'s FLOW / OVERLOAD / DISENGAGED / FATIGUE naming is intentional, not stale — do not
  "clean it up" without reading `PLAN.md` Part I §4 first (there's a note about this exact mistake
  having been made once already).
- Every module that touches the headset should keep working with `--fake` / `ReplaySource` so the
  rest of the team (and any agent) can develop and test without the physical device connected.
- Treat NeuroSky's own `attention`/`meditation` eSense scores as passthrough-for-comparison only,
  never as an input to a decision. See `PLAN.md` Part I §3 for why.

## Working on the NeuroPace plan

- `PLAN.md` is a single consolidated file across three chronological "parts" (original build plan
  → product pivot → special-education addendum). If you're asked to update the plan, edit the
  relevant Part in place and update the Part 0 status note / Quick reference if the current
  authoritative direction changes — don't fork a new top-level plan file.
- Citation tags (`[V#]`) are scoped **per Part**, not global — the same number means a different
  source in Part I vs Part II. Don't assume a tag number is unique across the whole document.
- `[RUN]` tags mark a claim backed by a script actually executed in this repo (`neuropace_eval.py`,
  and the `bandit_sim.py` / `lossmap_sim.py` referenced from Part II, if present). Don't upgrade a
  `[U]`-tagged or `ASSUMPTION`-tagged claim to `[RUN]` without actually running something and
  keeping the reproducing script.
- Statistics discipline in `neuropace_eval.py` is deliberate: outcome claims must always compare a
  sensor-timed condition against a **yoked random-timing control**, never against "no intervention"
  — see `PLAN.md` Part I §9 for why that specific comparison is the one that matters. Don't
  simplify evaluation code in a way that drops the yoked control.

## House rules

- MVP workflow: prioritize the smallest useful implementation and direct live checks. Do not expand test harnesses, documentation, or architecture beyond what is needed to make the requested behavior work. Keep verification focused on the changed behavior. The user explicitly prefers a direct browser pass over large new test matrices or custom test harnesses.
- Current demo interaction (20 Sep): Start session navigates in the same tab. Live catch-ups immediately show a recap and asynchronously add existing generated ArtifactView formats, staying open until dismissed. Older one-line-only HUD requirements do not govern this new path. Tutor mode leads with the generated visual plan, advances after natural narration completion, and can use the model to select an available unused format after a wrong answer. Manual review stays question-first. Do not replace actual visual generation with a text label or a canned animation.

- No teacher/institutional dashboard of an individual learner's data — every part of the plan
  treats the learner's gap history as learner-owned. If you're building UI or storage for this,
  don't add a cross-learner or instructor view without it being explicitly asked for and scoped.
- Say when something is simulated. The plan is emphatic that a labelled fallback (`--fake`,
  `ReplaySource`, keyboard-forced states) is fine; a fallback presented as real data is not.
- Keep demo data synthetic. If a change starts touching real student data handling, see `PLAN.md`
  Part III §5 (FERPA/IDEA) before writing storage or access-control code.
