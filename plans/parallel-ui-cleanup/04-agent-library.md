# Agent D — Post-session Library (Notes · Review · Replay · Quiz)

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `PLAN.md` Part II §§2, 6–8, `docs/PRD.md` FR-N1–N5, FR-R1–R6, FR-L13–L14, FR-S1–S4.

## Mission

Give every finished session one home. Today Notes/Review/Replay/Quiz are four orphaned routes with ad-hoc header links; put them behind a shared Library shell with per-session sub-tabs and leave their logic alone.

## Current state (verified)

- `Notes.tsx` (97 lines): gap notes for flagged spans only; `nothing flagged; nothing to review` empty state; running-session `End it and build notes`; header links `replay / quiz / home`.
- `Review.tsx` (281 lines): one card per gap, question-first, miss/drop → next form → dissolve → hit; `D` sim drop; tally panel; ends after 3 straight hits or exhaustion. Logic is delicate — header-only changes.
- `Replay.tsx` (155 lines): event-log playback at 4× through `LiveStage` (FR-L14). Shares `LiveStage` with Live — coordinate with Agent C.
- `Quiz.tsx` (91 lines): before/after review phases, 15-item study quiz, resubmit-replaces semantics.
- Cross-links today: Notes ↔ Replay/Quiz, Setup → Tally/LossMap, sidebar → Notes/Review/Replay. No consistent back-navigation.

## Do

1. New `frontend/src/views/Library.tsx`: route `/library/:sessionId?`. Layout: session picker (recent sessions, learner-scoped) + sub-tabs **Notes · Review · Replay · Quiz** for the selected session. Sub-tabs are the ONLY in-library navigation; each child view keeps its content but replaces its ad-hoc header with the shared shell header (`← Library`, session title, status).
2. Keep deep links working: `/notes/:id`, `/review/:id`, `/replay/:id`, `/quiz/:id` render the same components inside the shell (Agent A wires routes; you own the shell + header refactor).
3. Preserve all semantics: notes-only-for-flags, check-question-first, form order (best-first, no repeat, sketch dissolve), 3-hit stop, tally crediting, quiz before/after phases, replay 4×.
4. Preserve every honesty string: `nothing flagged; nothing to review`, simulated-D disclosure, offline recaps, scripted-transcript labels.
5. Post-session → dashboard loop: after Review done / Quiz submitted, show `Back to Dashboard — your review queue is updated` (dashboard refetches on focus already; don't add new polling).
6. Empty states: no sessions → point at `New session` (launcher lives on dashboard; link there, don't duplicate the button).

## Do NOT

- Don't change review state machine, tally scoring, quiz grading, gap merging (8 s min / 90 s max), or event-log format.
- Don't touch `Live.tsx` logic, `LiveCapture.tsx`, BLE, or dashboard API.
- Don't add cross-learner views or instructor pages.
- `LiveStage.tsx` shared with Agent C: headers/props only, no behavior change without C's sign-off.

## Steps

1. `git status --short --branch` + `git diff --stat` first.
2. Build `Library.tsx` shell + session picker; refactor the four headers to use it.
3. Drill (simulated, labelled): new session → flag via T → end → Library Notes (gap exists) → Review (miss → re-teach → hit) → Quiz before/after → Replay 4× → dashboard queue updates.
4. `cd frontend && npm run build`; `uv run pytest -q` (notes/review/tally coverage must stay green).

## Acceptance

- [ ] One Library home per session with 4 sub-tabs; no orphaned headers.
- [ ] Deep links still work inside the shell.
- [ ] Review/quiz/tally semantics byte-identical (tests green).
- [ ] Simulated drill completes end-to-end with labels intact.
- [ ] 390px: sub-tabs scroll, content stacks, no page horizontal scroll.
- [ ] Build + tests green.

## Commit + push regularly (required)

- Own only: `views/Library.tsx` (new), headers of `Notes.tsx`, `Review.tsx`, `Replay.tsx`, `Quiz.tsx`. No logic edits in Review/Quiz without noting it in the commit message.
- Checks before each commit: frontend build; pytest before push.
- Small commits + frequent pushes to `design/playful-learning-themes`: `git add <your files> && git commit -m "library: <what> (agent D)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`. Never force-push; stop on cross-agent conflicts and report.
- Final message: SHAs pushed + drill result.
