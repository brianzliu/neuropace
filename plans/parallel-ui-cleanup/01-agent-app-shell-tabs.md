# Agent A — App shell, tabs, routing (single session entry)

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `PLAN.md` §0, `docs/UI_DESIGN_DIRECTIONS.md`.

## Mission

Give the main window a persistent tab bar and make "start session" exist in exactly one place. You own navigation; every other agent builds into your shell.

## Current state (verified)

- `frontend/src/App.tsx` (53 lines): header has brand + `Appearance` + single `Dashboard` link. No tabs. Routes: `/`, `/session/new`, `/live/:sessionId`, `/notes/:sessionId`, `/review/:sessionId`, `/tally/:learnerId`, `/lossmap/:lectureId`, `/replay/:sessionId`, `/quiz/:sessionId`.
- Duplicate launchers: `Home.tsx` toolbar `New session` (~line 107) + empty-state `Start a session` (~line 126), both calling `openStudio()` (window.open + same-tab fallback). Real submit lives in `Setup.tsx` (~line 232).
- `LocalConnection` wraps all routes (pairing gate) — keep it outside your tab bar, don't move it.
- `compact` header mode exists for `/live` + `/replay` — extend the idea: main window shows tabs; Studio popup shows stepper (Agent C renders the stepper, you just don't show tabs there).

## Do

1. New `frontend/src/components/TopTabs.tsx`: tabs **Dashboard `/`**, **Library** (links to most-recent session library or a session picker when none), **Insights `/insights`**. Active-state via `useLocation`; `aria-current="page"`; horizontal scroll at 390px; theme tokens only (no new palette).
2. `App.tsx`: render `<TopTabs/>` in main window; hide tabs when `compact` (live/replay) or on `/session/new` (Studio popup). Add routes `/library/:sessionId?` and `/insights` (thin shells; Agents D/E fill them — your route elements can lazy-import their components so you don't block them).
3. Keep deep links working: `/notes/:id`, `/review/:id`, `/replay/:id`, `/quiz/:id` render inside the Library shell (redirect or nested route — pick one, document it in your commit message). `/tally/:learnerId`, `/lossmap/:lectureId` render inside Insights shell.
4. Single-entry rule: delete NOTHING in Home yet (Agent B does that) but expose a prop/callback contract both agents share, e.g. Home renders `<NewSessionButton/>` from one place. Coordinate with Agent B so the merge is trivial: you define the button component + `openStudio()` helper location; B deletes the duplicate call site.
5. Unknown-route page keeps a `Back to Dashboard` link.

## Do NOT

- Don't restyle themes, don't touch `playful.css` beyond tab classes (Agent F owns tokens).
- Don't edit `Setup.tsx`, `Live.tsx`, `LiveCapture.tsx` (Agent C).
- Don't change `mindwave/`, `neuropace/` behavior, or any LLM/dashboard API.
- Don't add an instructor view or cross-learner page.

## Steps

1. `git status --short --branch` + `git diff --stat`; note others' uncommitted work, touch only your files.
2. Implement `TopTabs.tsx` + `App.tsx` wiring + new routes.
3. Manual pass: dashboard → library → insights → back; popup `/session/new` shows no tabs; 390px no page-level horizontal scroll.
4. `cd frontend && npm run build`; fix types.
5. Commit + push (see below).

## Acceptance

- [ ] Every main-window route shows the tab bar with correct active tab.
- [ ] Studio (`/session/new`) and live/replay show no main tabs.
- [ ] Exactly one shared `NewSessionButton` component exists; Home imports it (B removes the second call site — verify together).
- [ ] Old deep links (`/notes/*`, `/review/*`, `/tally/*`, …) still resolve, inside the new shells.
- [ ] Keyboard: tabs are real links, focus-visible; reduced-motion respected.
- [ ] Frontend build green.

## Commit + push regularly (required)

- Before editing: inspect `git status/diff`; never discard others' changes.
- Own only: `App.tsx`, `components/TopTabs.tsx` (new), minimal `main.tsx`/`index.html` if needed. Nothing else without coordinating.
- Checks before each commit: `cd frontend && npm run build`.
- Commit small + push often to `design/playful-learning-themes`:
  `git add <your files> && git commit -m "tabs: <what> (agent A)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`.
  Never `push --force`. If rebase hits another agent's files, stop and report.
- Final message: SHAs pushed + routes verified.
