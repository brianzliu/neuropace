# Agent B — Dashboard compartments (Home)

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `PLAN.md` §0 + Part II §2 (gap notes → review), `docs/PRD.md` §12 FR-D1–D4.

## Mission

Turn `Home.tsx` (currently 142 lines doing everything) into three clean compartments with ONE session launcher, without changing dashboard API semantics.

## Current state (verified)

`frontend/src/views/Home.tsx`:
- Toolbar (~lines 104–108): title + `New session` launcher → `openStudio()`.
- Profile toolbar (~109–113): learner picker + add-profile disclosure.
- Review overview (~117–121): concept count + LLM `summary` + `organization_source` label (`Organizing…` / `Suggested order · based on your saved notes` / `Review queue · unfinished concepts first`).
- Up-next concept list (~122–127) with per-concept `Review session` / `Source notes` links; empty state has a SECOND `Start a session` button (~line 126) — **this is the duplicate to remove**.
- Curriculum/syllabus editor (~128–134): paste + file upload (PDF/TXT/MD, 2 MB), extract-topics preview, self-reported checkboxes ("Marked by you · review results are tracked separately").
- Sessions sidebar (~136–139): recent sessions with Notes/Review/Replay links or `Open live session`.
- Data: `api.dashboard(learnerId, organize)` + focus-refresh reload; types in `frontend/src/lib/dashboardTypes.ts`.

## Do

1. **Delete the duplicate:** remove the empty-state `Start a session` button; replace with a muted hint pointing at the single toolbar `NewSessionButton` (shared component from Agent A). Toolbar launcher keeps the label `New session` + sub-caption `Opens your live studio`.
2. Extract three section components under `frontend/src/components/dashboard/` (new): `ReviewQueue.tsx` (overview + up-next list), `SessionsSidebar.tsx`, `CurriculumSection.tsx` (progress + syllabus form). `Home.tsx` becomes composition + data fetching only.
3. Keep every honesty string intact: `organization_source` labels, `Suggested order · based on your saved notes`, `Marked by you`, `review results are tracked separately`, simulation/offline wording. LLM summary/order display only; never let it edit completion.
4. Syllabus flow stays: paste + upload, `Extract topics` preview step, user edits before save, 100-topic cap, checkbox = self-reported coverage. Surface parse errors (`syllabusMessage`) as `role="status"`.
5. Profile switcher stays on dashboard (Studio must NOT become the second profile-creation place — flag it to Agent C if Setup duplicates it).
6. Loading/empty/error states per section (not one page-level spinner): `Loading your saved moments…`, `Nothing to untangle. Yet.`, `needs review` hints.
7. Learner scoping: switching profiles reloads; no cross-learner pooling on this page (LossMap aggregation lives in Insights).

## Do NOT

- Don't change `neuropace/core/dashboard.py`, syllabus parse limits (2 MB / 30 pages / 30k chars), organizer ID validation, or cache behavior.
- Don't invent mastery/completion; don't add streaks, grades, or AI branding.
- Don't touch `Setup.tsx`/`Live.tsx`/BLE code (Agents C/E).
- Don't change theme tokens (Agent F).

## Steps

1. `git status --short --branch` + `git diff --stat` first; coordinate `NewSessionButton` contract with Agent A.
2. Extract the three section components; wire props; remove duplicate launcher.
3. Verify: synthetic profile flow (create → syllabus paste/upload → check 1 of 3 topics → reload persists), organize=true/false labels, sidebar links route into Library shell paths.
4. `cd frontend && npm run build`.

## Acceptance

- [ ] Dashboard shows one `New session` launcher, zero other start-language buttons.
- [ ] Three visual compartments with headings; 390px stacks cleanly, sidebar below main.
- [ ] Syllabus paste + PDF/TXT/MD upload → preview → edit → save works; errors announced.
- [ ] Learner switch isolates data; completion checkboxes persist after reload.
- [ ] LLM vs deterministic ordering labels correct in all states.
- [ ] Frontend build green.

## Commit + push regularly (required)

- Own only: `views/Home.tsx`, `components/dashboard/*` (new). `dashboardTypes.ts` additive-only.
- Checks before each commit: `cd frontend && npm run build`.
- Small commits + frequent pushes to `design/playful-learning-themes`: `git add <your files> && git commit -m "dashboard: <what> (agent B)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`. Never force-push; stop on cross-agent conflicts and report.
- Final message: SHAs pushed + synthetic dashboard flow result.
