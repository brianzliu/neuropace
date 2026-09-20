# Agent C — Session Studio window (setup + live capture honesty)

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `PLAN.md` Part II §§2, 2.1, 4 + Part III §§2, 5, `docs/PRD.md` §12 FR-H1, FR-C1–C3, `firmware/uno_q_relay/README.md`.

## Mission

Make the popup Studio (`/session/new` → `/live/:id`) a clean two-step workspace with honest connection/capture states and leak-free media lifecycle. This is the ONLY place session setup lives.

## Current state (verified)

- `frontend/src/views/Setup.tsx` (275 lines): hero + `DeskObject` tutorial, UNO Q BLE scan (`/api/devices/uno-q`), connection-route selector, profile + lecture + mode pickers, settings disclosure (catch-up policy, baseline, headset `auto/sim/fake/custom`, totem `auto/sim`), doctor strip (15 s refresh), `Start session` submit (~line 232) → `nav(/live/:id)` staying inside the popup.
- `frontend/src/views/Live.tsx` (273 lines): socket + `LiveStage`, `LiveCapture` (only when `hello.mode === "live"`), board-explanation `<details>`, controls (`I'm confused · simulated button` T, force flag L, form cycle F, sim states 1/2/3, mic start/stop, end lecture E). Mic cleanup via `micGeneration` + unmount effect already exists — preserve it.
- `frontend/src/components/LiveCapture.tsx` (58 lines): explicit enable/stop, `getUserMedia` env camera, JPEG POST every 2 s, 90 s/45-frame server buffer (`neuropace/core/board.py`), `DELETE` buffer clear on stop/unmount, `frames received` counter. No continuous video file.
- Backend: `POST/DELETE /api/sessions/{id}/board`, async multimodal on allowed button catch-up (recent transcript + ≤4 preceding frames, honors randomized withholding, offline-labelled failures, image payloads not logged).

## Do

1. Restructure Setup into a 2-step Studio layout WITHOUT changing semantics: Step 1 Devices (UNO Q scan + route + doctor strip + headset/totem selects), Step 2 Lecture (profile read-only default from dashboard + lecture/mode + study settings). Keep the single `Start session` submit at the end. Remove the duplicate profile-creation form — link back to dashboard instead (`Back to dashboard` already exists; keep it).
2. Connection honesty: each of EEG / button / mic-transcription / board-camera gets a `Connected · Simulated · Pending · Off` pill driven by actual state (doctor + hello + mic/board state). Pending copy for UNO Q relay: `connection pending — verified in live session`. Never show green for sim.
3. "I'm confused" flow: on-screen button keeps `· simulated button` suffix; physical button path unchanged. Press saves the moment immediately; board explanation arrives async in the expandable panel with `Transcript recap; board explanation loading` → result or `Transcript only; board unavailable` / `Offline · board not interpreted`. Never replace visible text mid-reading; never override randomized withholding.
4. Media lifecycle: audit + keep the unmount/stop cleanup in `Live.tsx` + `LiveCapture.tsx` (mic tracks stopped, interval cleared, AbortController aborted, buffer DELETE with keepalive). Add the same DELETE on session end. Verify no camera/mic indicator lingers after end/unmount.
5. Studio chrome: `Setup → Live` stepper header in popup; `Back to dashboard` link; `DeskObject` 3D tutorial stays labelled preview with no recorded data.

## Do NOT

- Don't change board buffer limits (45 frames/90 s), 2 s sampling, ≤4 frames/request, or withholding logic.
- Don't claim BLE/hardware readiness; UNO Q copy stays `Experimental relay`.
- Don't touch `mindwave/` math, tally scoring, or dashboard API.
- Don't add video recording, durable board-image notes, or face/gaze analysis.

## Steps

1. `git status --short --branch` + `git diff --stat`; don't disturb others' files.
2. Restructure Setup sections; add the 4-pill status row in Setup + Live; keep all existing state keys.
3. Lifecycle audit: open/close camera, start/stop mic, end session, unmount — confirm tracks stop + buffer cleared (Network tab: DELETE board).
4. Simulated drill: scripted lecture → T (sim tap) → catch-up <1 s → end → notes exist.
5. `uv run ruff check neuropace tests scripts`, `uv run pytest -q`, `cd frontend && npm run build`.

## Acceptance

- [ ] Studio is the only setup surface; dashboard links into it via popup + same-tab fallback.
- [ ] Four status pills reflect real state in both Setup and Live.
- [ ] "I'm confused" saves instantly; board explanation is async, labelled, non-replacing, withholding-safe.
- [ ] Camera/mic stop on end/unmount; no orphaned indicators; buffer cleared.
- [ ] 3D tutorial still labelled preview, no data recorded.
- [ ] Lint + tests + build green.

## Commit + push regularly (required)

- Own only: `views/Setup.tsx`, `views/Live.tsx`, `components/LiveCapture.tsx`, careful shared `components/LiveStage.tsx` (coordinate with Agent D who also renders it).
- Checks before each commit: ruff + pytest subset at minimum; build before push.
- Small commits + frequent pushes to `design/playful-learning-themes`: `git add <your files> && git commit -m "studio: <what> (agent C)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`. Never force-push; stop on cross-agent conflicts and report.
- Final message: SHAs pushed + simulated drill + media-cleanup results.
