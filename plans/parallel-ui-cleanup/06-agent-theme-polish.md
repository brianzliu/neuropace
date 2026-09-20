# Agent F — Playful theme polish + responsive + a11y

Branch: `design/playful-learning-themes`. Workdir: `/Users/brianliu/Documents/personal/coding/neuropace`.
Read first: `plans/parallel-ui-cleanup/00-README.md`, `docs/UI_DESIGN_DIRECTIONS.md` (esp. "Final steering applied"), `frontend/src/playful.css`, `frontend/src/components/Appearance.tsx`, `frontend/src/components/DeskObject.tsx`.

## Mission

Make the cleanup look intentional: Pocket Studio (white/yellow, light rounded lettering) as the polished default, Paper Playground + Orbit intact, new tabs/shells themed, 390px clean, reduced-motion + keyboard correct. No layout logic changes — tokens and CSS only.

## Current state (verified)

- Three themes in `Appearance.tsx` (`pocket`/`paper`/`orbit`), persisted `neuropace.theme`, miniature previews. Pocket override: white `#fcfcf8`, butter yellow `#f4d76a`, charcoal `#3e3d32`, lilac paper; Chalkboard SE + Comic Sans/Trebuchet fallbacks, regular weight. No bold-blue styling, no AI branding.
- `playful.css` holds tokens + tactile 3D (CSS perspective/gradients/inset shadows, press displacement). `DeskObject.tsx` = CSS 3D button tutorial, labelled preview, no recorded data (lives in Session studio per latest steering).
- New surfaces from Agents A–E (TopTabs, dashboard sections, Library, Insights, Studio stepper) will arrive unstyled or roughly styled — you theme them.
- Unverified: narrow/mobile rendering, all three themes post-cleanup, theme persistence across new routes.

## Do

1. Token pass: confirm Pocket defaults (white/yellow/charcoal/lilac, Chalkboard SE regular) across dashboard, new tabs, Library, Insights, Studio. Paper + Orbit render the same components with their own tokens (desk/paper/ink/raspberry/shell/yellow; midnight/lavender/frosted). Body text stays readable (Orbit glass restricted to object/setup panel, not body copy).
2. Style the new chrome: tab bar (active state, `aria-current` visible, 390px horizontal scroll), section headings, status pills (Connected/Simulated/Pending/Off — color + text, never color-alone), Library sub-tabs, Insights cards, Studio stepper. Tactile press depth on primary actions only; no endless motion.
3. Responsive: 390px — tabs scroll, dashboard stacks (main → sidebar), curriculum/syllabus form full-width, Studio steps stack, tables/pills wrap. No page-level horizontal scroll. Small-screen keeps left-aligned text (object tutorial + empty states centered only).
4. A11y: focus-visible outlines, real buttons/links, `aria-pressed`/`aria-current`, decorative objects `aria-hidden`, `prefers-reduced-motion` disables transitions, sim/offline badges remain text (not color-only).
5. Theme persistence + switching smoke: switch Pocket → Paper → Orbit → reload → choice holds; new routes inherit theme.

## Do NOT

- Don't move JSX between files or change labels/copy (Agents A–E own that).
- Don't touch `mindwave/`, `neuropace/`, firmware, or API logic.
- Don't add mascots, streaks, grades, scores, flashing, autoplay, or AI branding.
- Don't claim mobile verification beyond what you actually render-test (Safari + a 390px viewport at minimum; say which).

## Steps

1. `git status --short --branch` + `git diff --stat`; work after (or alongside) A–E, styling only.
2. Theme the new shells; screenshot/record each theme at desktop + 390px (note which you actually viewed).
3. Reduced-motion + keyboard pass (Tab through tabs, launcher, syllabus form, Studio controls).
4. `cd frontend && npm run build`.

## Acceptance

- [ ] All three themes render dashboard/tabs/Library/Insights/Studio without unstyled flashes.
- [ ] 390px: no page horizontal scroll; tabs + sub-tabs scroll; sections stack.
- [ ] Status/sim/offline pills legible in all themes (text + color).
- [ ] Keyboard + reduced-motion pass done.
- [ ] Frontend build green.

## Commit + push regularly (required)

- Own only: `playful.css`, `Appearance.tsx`, `DeskObject.tsx`, theme-only classes in new components (coordinate — if a class lives in another agent's file, ask them to apply your token, don't edit their file yourself).
- Checks before each commit: `cd frontend && npm run build`.
- Small commits + frequent pushes to `design/playful-learning-themes`: `git add <your files> && git commit -m "theme: <what> (agent F)" && git pull --rebase origin design/playful-learning-themes && git push origin design/playful-learning-themes`. Never force-push; stop on cross-agent conflicts and report.
- Final message: SHAs pushed + themes/viewports actually viewed.
