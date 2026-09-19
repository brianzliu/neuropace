# Parallel UI cleanup — index (read this first)

Branch: `design/playful-learning-themes` (last pushed: `9ab8869`; substantial uncommitted work on top).
Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`
Plan source of truth: `PLAN.md` §0 + Part II §§2, 2.1, 4–8 + Part III §§2–6. Contracts: `docs/PRD.md`, `docs/TDD.md` (esp. §12 in each). Design log: `docs/UI_DESIGN_DIRECTIONS.md`.

## The complaint that started this

> Too much lives on one page, and "start session" appears in 2 places.

Confirmed in code today:

- `frontend/src/App.tsx` — top bar has only `Dashboard` + theme picker. Notes/Review/Replay/Quiz/Tally/LossMap exist as routes but have **no persistent tab navigation**; they are reachable only via deep links from the dashboard sidebar or the session flow. So everything feels hidden or crammed.
- `frontend/src/views/Home.tsx` — **two** "start session" entry points on the same page: toolbar `New session` button (`openStudio()`, ~line 107) and empty-state `Start a session` button (~line 126). Both call the same `openStudio()` (window.open `/session/new` + same-tab fallback).
- `frontend/src/views/Setup.tsx` (`/session/new`) — the actual `Start session` submit (~line 232). So there are effectively three places with "start" language: two launchers on Home + one submit in Studio. The fix is **one launcher, one submit**, with distinct labels.
- `Setup.tsx` also duplicates profile creation (Home already has it) and buries UNO Q discovery, EEG route, lecture picker, and study settings on one long page.
- Post-session views (`Notes`, `Review`, `Replay`, `Quiz`) each have their own ad-hoc header links (`home`, `replay`, `quiz`, …) instead of a shared per-session sub-nav.
- `Tally` and `LossMap` are orphaned deep links (from Setup/Home) with no home in the nav.

## Target tab architecture (all agents build toward this)

Main window (dashboard side) gets a persistent tab bar:

1. **Dashboard** `/` — learner-owned home. Up-next review queue first, sessions sidebar, curriculum below. Exactly ONE `New session` launcher (opens Studio window).
2. **Library** `/library/:sessionId?` (new shell — Agent D) — per-session home: Notes · Review · Replay · Quiz as sub-tabs. Deep links keep working and redirect into the shell.
3. **Insights** `/insights` (new shell — Agent E) — learner's Tally + lecture LossMap, learner-scoped, aggregate-only.
4. **Studio is NOT a tab.** `/session/new` + `/live/:id` live in the dedicated popup window only (Agent C). Dashboard never embeds the setup form.

Studio window keeps its own minimal chrome: `Setup → Live` stepper + `Back to dashboard` link. No theme churn, no dashboard widgets inside the popup.

Naming rule going forward: **"New session"** = launcher (dashboard only). **"Start session"** = submit button (Studio setup only). **"End lecture"** = Live only. Never reuse these labels elsewhere.

## Agent map (run in parallel)

| Agent | File | Owns (only these files unless coordinated) |
|---|---|---|
| A — App shell + tabs | `01-agent-app-shell-tabs.md` | `frontend/src/App.tsx`, `frontend/src/components/TopTabs.tsx` (new), `frontend/src/main.tsx` (minimal), `frontend/index.html` (title only if needed) |
| B — Dashboard compartments | `02-agent-dashboard.md` | `frontend/src/views/Home.tsx`, `frontend/src/components/dashboard/*` (new), `frontend/src/lib/dashboardTypes.ts` (read-only + additive) |
| C — Studio window (setup + live capture) | `03-agent-studio-live.md` | `frontend/src/views/Setup.tsx`, `frontend/src/views/Live.tsx`, `frontend/src/components/LiveCapture.tsx`, `frontend/src/components/LiveStage.tsx` (careful, shared with Replay) |
| D — Post-session Library | `04-agent-library.md` | `frontend/src/views/Library.tsx` (new), `Notes.tsx`, `Review.tsx`, `Replay.tsx`, `Quiz.tsx` (headers only, logic untouched) |
| E — Insights + Devices | `05-agent-insights-devices.md` | `Tally.tsx`, `LossMap.tsx`, `views/Insights.tsx` (new), `Setup.tsx` device section (coordinate with C), `reflow/totem/uno_q.py` + `firmware/uno_q_relay/*` (docs/comments only, no behavior change without hardware) |
| F — Theme polish + responsive | `06-agent-theme-polish.md` | `frontend/src/playful.css`, `Appearance.tsx`, `DeskObject.tsx`, theme tokens only |

If two agents need the same file, the table owner edits; the other proposes via chat, not a competing edit.

## Shared guardrails (all agents)

- **Do not touch** `mindwave/` signal-processing/calibration math. Do not touch `reflow_eval.py` statistics (yoked random-timing control stays).
- **Preserve labels:** simulated / fake / scripted / offline / experimental-relay wording stays visible. Never present fallback as real.
- **No instructor dashboard** of individual learner data. LossMap stays aggregate + anonymous (n shown, needs ≥2).
- **No fabricated progress:** LLM may summarize/order concepts; it never writes review outcomes or curriculum completion. Completion stays self-reported checkboxes.
- **UNO Q is prototype, not hardware-ready.** BLE permissions, App Lab compat, pairing/encryption, throughput, flashing, wiring are unverified. Docs/comments may clarify blockers; never claim success.
- **Camera/mic honesty:** explicit enable/stop, persistent indicator, 2 s JPEG sampling, 45-frame/90 s server buffer, no continuous video file, board images never durably stored in notes. Mic lifecycle cleanup in `Live.tsx` stays.
- Pocket Studio (white `#fcfcf8` / butter yellow `#f4d76a`, Chalkboard SE + fallbacks, regular weight) is the default favorite. Paper Playground and Orbit remain selectable. No prominent AI branding; audience is college students + adults.

## Commit + push regularly (all agents — user explicitly requires this)

The user asked that every agent **commit and push regularly**. Follow this exactly:

1. **Before touching anything:** `git status --short --branch` + `git diff --stat`. There is substantial uncommitted work from others — never discard it (`git checkout -- .`, `git stash -u` without intent, and `git push --force` are forbidden).
2. **Commit only your owned files** (see table). Small, passing commits: e.g. `tabs: add TopTabs shell (agent A)`, `dashboard: extract review queue section (agent B)`.
3. **Before every commit, run the checks for your area** (full matrix below). Don't commit red code.
4. **Push to the same branch often** — at minimum after each acceptance milestone and at end of session:
   `git pull --rebase origin design/playful-learning-themes` → resolve only your files → `git push origin design/playful-learning-themes`.
   Never force-push. If rebase conflicts touch another agent's files, stop, report, don't overwrite.
5. End-of-session report must include commit SHAs + push status.

## Verification matrix (use the relevant subset; A/B/F run frontend, C/D/E run both)

```
uv run ruff check reflow tests scripts
uv run pytest -q                                   # full suite, ~73 tests / ~25 s
cd frontend && npm run build                       # production build must pass
narrow-layout check: 390px wide, tabs scroll, no horizontal page scroll
simulated session → notes/review → dashboard refresh (labelled SIMULATED)
```

Processes are already running — **do not start duplicates.** Vite ≈ PID 87695 on `:5173`; backend `uv run --extra bluetooth reflow serve` on `:8765`. Check with `lsof -i :5173 -i :8765` before starting anything.

## What "done" looks like

- One "New session" launcher on the dashboard; one "Start session" submit in Studio; no other start-language buttons.
- Tabs visible on every main-window page; Studio popup has stepper chrome, not tabs.
- Dashboard reads as three compartments (Up next / Sessions / Curriculum), not one long scroll.
- Library + Insights shells exist; old deep links still work.
- Connection/capture honesty unchanged or improved; no new unverified hardware claims.
- All three themes render; 390px layout clean; build + lint + tests green; commits pushed.
