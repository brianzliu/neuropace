# Agent E — Insights + Devices (Tally · LossMap · UNO Q)

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `PLAN.md` Part II §§3–6 + Part III §§1–4, 6, `docs/PRD.md` FR-T1–T5, FR-M1–M3, FR-H1, `firmware/uno_q_relay/README.md`, `reflow/totem/uno_q.py`.

## Mission

Give Tally + LossMap a learner-safe home and make the UNO Q story honest and blockered. No behavior change to scoring, pooling, or BLE transport without hardware.

## Current state (verified)

- `Tally.tsx` (46 lines): per-learner rescues/attempts, `We don't believe in learning styles…` line, population prior (pseudo-count 2), `not enough data yet` until 12 scored cards. Quiz-answers-only scoring (P6). Orphaned deep link.
- `LossMap.tsx` (101 lines): aggregate anonymous pooled loss, 40 s peak, `needs 2 or more learners (n so far)`, planted-bad reveal. Grades the lecture, never a student.
- Devices: `Setup.tsx` UNO Q scan (`GET /api/devices/uno-q`, custom Reflow service), route selector (`uno-q:<address>` replaces headset/totem with shared BLE relay), `GET /api/devices/status` refresh, `DoctorStrip` (deepgram/openai/headset/totem/baseline). Backend `reflow/totem/uno_q.py`: frame validation, bounded JSON reassembly, duplicate-sequence rejection, nonfinite rejection, 3 s EEG staleness. Firmware `firmware/uno_q_relay/{sketch/sketch.ino (D2/GND debounce, RouterBridge count), python/main.py (App Lab/BlueZ/Bless prototype, mindwave.Pipeline unchanged), README.md}`. NOT compiled/flashed/tested; no arduino-cli; permissions/pairing/throughput unverified.
- Target topology (authoritative): EEG pairs to UNO Q; button → Q MCU; Q relays both → laptop BLE. Direct-computer EEG = explicit fallback.

## Do

1. New `frontend/src/views/Insights.tsx` (`/insights`, Agent A routes it): two cards — **My review preferences** (Tally, learner-scoped) + **Lecture overview** (LossMap per lecture picker). Keep every honesty string: `not enough data yet`, `needs 2 or more learners`, `n = …`, `grades the lecture, never a student`, population-prior note. No per-learner traces on the LossMap card, ever.
2. Devices pass (UI copy only + comments): consolidate device disclosure into one `DeviceStatus` block reused by Setup (owner: Agent C — you propose, C applies, or vice versa; don't double-edit). Copy must state: UNO Q = `Experimental relay`; scan finds custom Reflow service only; selection routes headset+button through relay; verification happens in live session; direct + simulated remain labelled fallbacks. Button hardware copy: `not built yet — momentary switch under a larger 3D-printed press surface (planned)`.
3. Doc pass: update stale hardware mentions (any remaining `UNO R4` as current target → `UNO Q 4 GB`; R4 stays only as historical/fallback). `PLAN.md` current-direction note + `docs/PRD.md`/`TDD.md` §12 already carry the correction — mirror it, don't rewrite it. `firmware/uno_q_relay/README.md`: add/keep a **Hardware blockers** checklist (compile, flash, pair, BLE permission, App Lab compat, encrypted access, throughput, wiring D2/GND, end-to-end tap + feature-frame test). Code comments only; no transport behavior change.
4. Keep tests green: `tests/test_dashboard_capture.py` (BLE fragmentation/validation/staleness) + `tests/test_local_bridge.py` must pass untouched.

## Do NOT

- Don't change tally scoring (quiz-only), Thompson-sampling prior, loss-map binning/pooling, or BLE validation/staleness logic.
- Don't add teacher/institutional views, per-student tables, or IEP-goal tracking.
- Don't claim hardware works. Words like `verified`, `ready`, `working relay` are banned unless a physical test actually ran (it hasn't).
- Don't touch `mindwave/` math or review flow.

## Steps

1. `git status --short --branch` + `git diff --stat`; agree file handoff with Agent C for the device block.
2. Build Insights shell; re-home Tally/LossMap content into it (headers only).
3. Hardware honesty pass (copy + README blockers + stale R4 sweep via grep).
4. `uv run ruff check reflow tests scripts`, `uv run pytest -q`, `cd frontend && npm run build`.

## Acceptance

- [ ] `/insights` shows Tally + LossMap with all honesty strings; no individual-learner data on LossMap.
- [ ] Device copy states experimental relay + fallback + unbuilt button; no success claims.
- [ ] README lists concrete hardware blockers.
- [ ] No stale "current = UNO R4" statements remain (history/fallback mentions ok).
- [ ] Lint + tests + build green.

## Commit + push regularly (required)

- Own only: `views/Insights.tsx` (new), `views/Tally.tsx`, `views/LossMap.tsx` (headers), docs/comments in `firmware/uno_q_relay/*`. `Setup.tsx` device block only via Agent C handoff.
- Checks before each commit: ruff + pytest; build before push.
- Small commits + frequent pushes to `design/playful-learning-themes`: `git add <your files> && git commit -m "insights: <what> (agent E)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`. Never force-push; stop on cross-agent conflicts and report.
- Final message: SHAs pushed + blocker list confirmed.
