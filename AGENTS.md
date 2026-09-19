# AGENTS.md

Guidance for AI coding agents working in this repo.

## What this repo is

Three things, kept deliberately separate:

0. **`reflow/`, `frontend/`, `firmware/`, `tests/`, `docs/`, `study/`** — the Reflow product built
   on 19 Sep 2026 against `docs/PRD.md` and `docs/TDD.md` (the contract every module follows).
   Backend `uv run reflow serve` (Python 3.13 via uv, FastAPI), frontend Vite + React built into
   `frontend/dist`, UNO Q 4 GB BLE relay prototype as the current hardware target
   (`firmware/uno_q_relay/`, experimental and uncompiled) with the UNO R4 direct-USB sketch
   (`firmware/totem/`) retained as a fallback. `uv run pytest -q` runs the suite (no hardware, no
   network); `uv run python scripts/smoke_e2e.py` runs against a live server. `docs/VERIFICATION.md`
   records what was verified and how. The headset front end is the `mindwave/` pipeline below,
   consumed in-process (README "EEG bridge"); Reflow's own simulator covers the no-hardware path.

1. **`mindwave/`** — a working, standalone EEG pipeline for the NeuroSky MindWave Mobile 2. It
   turns the Bluetooth stream into one calibrated `FeatureFrame` per second (mental effort,
   engagement, alpha, blink rate, signal quality). It has no dependency on the hackathon product
   below and makes no decisions on its own — see `EEG_PIPELINE.md` and `mindwave/README.md` before
   changing anything in here.
2. **The Reflow plan** — `PLAN.md` is the current, consolidated product/build plan for a HackMIT
   2026 submission built on top of the pipeline. `tracks.md` is the raw sponsor-challenge text it
   references. `reflow_eval.py` is the pre-registered evaluation toolkit for that product's claims.

Read `PLAN.md` §0 ("How this plan evolved, and what to read") before assuming any specific
mechanic (real-time reflow, camera fusion, learning-style detection, totem LED output) is still
current — the plan explicitly tracks which ideas were superseded and why.

## Setup and running things

```
pip install -r requirements.txt
python monitor.py --fake          # live plot with simulated EEG, no headset needed
python monitor.py                 # live plot against a real headset (paired; find its COM port)
python run_pipeline.py            # headless service: WebSocket feed + session log
python example_consumer.py --fake
python reflow_eval.py selftest    # runs the evaluation toolkit's self-check
```

The `mindwave/` tools keep their own style and are excluded from ruff; the Reflow package is
linted and formatted with ruff (`uv run ruff check reflow tests scripts`). `uv run pytest -q`
covers Reflow and the bridge (`tests/test_mindwave_bridge.py` runs the pipeline on `FakeSource`).
`python monitor.py` needs `uv run --group monitor` (matplotlib).

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

## Working on the Reflow plan

- `PLAN.md` is a single consolidated file across three chronological "parts" (original build plan
  → product pivot → special-education addendum). If you're asked to update the plan, edit the
  relevant Part in place and update the Part 0 status note / Quick reference if the current
  authoritative direction changes — don't fork a new top-level plan file.
- Citation tags (`[V#]`) are scoped **per Part**, not global — the same number means a different
  source in Part I vs Part II. Don't assume a tag number is unique across the whole document.
- `[RUN]` tags mark a claim backed by a script actually executed in this repo (`reflow_eval.py`,
  and the `bandit_sim.py` / `lossmap_sim.py` referenced from Part II, if present). Don't upgrade a
  `[U]`-tagged or `ASSUMPTION`-tagged claim to `[RUN]` without actually running something and
  keeping the reproducing script.
- Statistics discipline in `reflow_eval.py` is deliberate: outcome claims must always compare a
  sensor-timed condition against a **yoked random-timing control**, never against "no intervention"
  — see `PLAN.md` Part I §9 for why that specific comparison is the one that matters. Don't
  simplify evaluation code in a way that drops the yoked control.

## House rules

- No teacher/institutional dashboard of an individual learner's data — every part of the plan
  treats the learner's gap history as learner-owned. If you're building UI or storage for this,
  don't add a cross-learner or instructor view without it being explicitly asked for and scoped.
- Say when something is simulated. The plan is emphatic that a labelled fallback (`--fake`,
  `ReplaySource`, keyboard-forced states) is fine; a fallback presented as real data is not.
- Keep demo data synthetic. If a change starts touching real student data handling, see `PLAN.md`
  Part III §5 (FERPA/IDEA) before writing storage or access-control code.
