# NeuroPace, product definition v2 (consumer)

Written 19 Sep 2026 after the reevaluation. This supersedes the student-facing parts of `docs/PRD.md`; the spec's signal engine, statistics and study protocol stay as they are. Everything below is a decision, with the reason next to it.

## 1. Where we were, honestly

- The backend does what the spec asked and is tested: focus index from the headset, taps, rolling recaps, gap notes, four re-teach forms, a review that switches form on a miss, a tally scored by answers, a pooled loss map, the study analysis.
- The app exposed that machinery in the spec's own words: forms, tally, flags, gaps, policies, loss map, replay, quiz, ports, keys. Three visual passes changed the skin, not the product. A student cannot tell what the app is for from its screens.
- Removing the learner picker was correct for a single device, but it had consequences nobody wrote down: the loss map needs several learners, so it is a team tool; the quiz exists for the study; replay exists for the demo. They stay, but off the student's path.
- Visualisations were an afterthought: one "sketch" form with a concept graph. There was no catalogue of ways to explain something and no rule for choosing one.

## 2. The two jobs (from the PRD, restated in the student's words)

1. **Listen.** NeuroPace follows the lecture with me. It watches whether I am with it. When I press the button (or it notices I drifted) it picks up the part I did not get and shows it to me in a simpler way, the way that works for me if it already knows.
2. **Restudy.** Afterwards, I can go back to any lecture and study only the parts I did not get. NeuroPace tries different ways of explaining each one, keeps the one that lands, and learns which ways work for me.

Everything on a student screen serves one of these. Everything else is under "For the team".

## 3. Who uses what

| Person | Screens | Never sees |
|---|---|---|
| Student (one per device) | Listen, Lectures, Restudy, You | ports, keys, z-scores, policies, tallies as tables, "simulated" internals (only a plain "practice mode" label) |
| Team, judges | For the team: setup status, signal details, replay, loss map, study quiz and numbers | nothing hidden |

Consequences of one learner per device: the profile ("You") is the device's. If someone else sits down, "You" offers "Not you? Start fresh", which resets the profile and the stored calibration. The study names participants under the team page; their sessions do not touch the device profile.

## 4. Ways to explain something: the artifact catalogue

An artifact is one generated way of presenting one missed moment. Each has a **glance** version (one line, for the live catch-up) and a **full** version (for restudy). The model produces every applicable artifact for a moment at once, so nothing waits on a network call during restudy.

| Family | Artifact | What it is | When it applies | Rendering |
|---|---|---|---|---|
| **In words** | summary | 1 to 3 sentences, grounded in the transcript | always | text |
| | key idea | the term, its definition as the lecturer used it, one example from the lecture | always | text with the term set large |
| **By comparison** | analogy | the idea mapped onto an everyday situation, with the mapping made explicit ("X is like Y because…") | always | text |
| **As a picture** | diagram | a concept graph (3 to 7 nodes, labelled edges) revealed step by step with captions | always | animated SVG (exists) |
| | chart | a small bar or line chart of numbers the lecturer actually gave, with one takeaway line | only when the moment contains quantities; the model marks it inapplicable otherwise | SVG, bars grow in |
| **By doing** | steps | the idea as an ordered procedure, one step at a time | processes, methods, algorithms | animated list, one step per beat |
| | worked example | a concrete instance carried through to its result, line by line | anything with a calculation or a case | animated lines, result last |

Decisions and reasons:

- **Four families, not seven arms.** The preference model must learn from few cards (about ten moments per lecture). The spec's simulation shows four arms need 60 to 150 scored cards to find a real preference; seven would need far more than a semester. So the thing we measure is the family. Inside a family the artifact is chosen by content, not by preference: a chart when there are numbers, else a diagram; steps for a process, else a worked example. The model says which applies.
- **Animation is a presentation mode, not an artifact.** Diagram, steps, worked example and chart all reveal progressively. A free-form "animation" artifact would be unreliable to generate and impossible to ground; we do not add one.
- **Everything is grounded.** Every artifact is built from the transcript span and the minute before it. Charts use only numbers the lecturer said. If the span cannot support an artifact the model marks it inapplicable rather than inventing content.
- **Not included, on purpose:** mnemonics (weak evidence, rarely grounded), flashcards (that is what the check question already is), free text chat (the product has no prompt box), images from image models (not grounded, slow).

## 5. How NeuroPace learns what works for you

- Every restudy card is scored by the **check question** afterwards: a family shown right before a correct answer earns a rescue; before a miss, an attempt. This is the only thing that changes the choice of family (the spec's principle: quiz answers decide).
- With a headset on during restudy, NeuroPace also measures **how much of each card you stayed focused** (fraction of the card's seconds not flagged as a drop). It is shown on your profile as "held your attention" and it switches the explanation early when you drift on a card; it never scores a family by itself, because focus and understanding are different things.
- The live catch-up uses your best family for the one-liner. New profiles start from the average across everyone and say so ("still learning what works for you").
- The profile shows, per family: tried, rescued, held your attention. Below twelve scored cards it says it is still learning.

## 6. Screens

**Listen (home).** One card: "Ready when you are" and *Start listening* (live microphone) or a practice lecture. Below: your lectures as tiles (title, date, "3 moments to restudy" or "all clear"). Headset and pad status as one friendly line each ("Headset on, signal good" / "No headset today, the button still works").

**Listening.** The transcript large in the middle. On the right: your brain waves (the live µV trace) and a focus ring with one sentence. One button, *I'm lost* (Space or the pad). When you drift, a soft prompt: "Want a quick catch-up?". The catch-up is one line at the bottom in your best family. *End lecture* at the corner. A *Details* toggle keeps the instrumentation for the team.

**Lecture done.** A completion screen: moments missed, the catch-ups you took, *Restudy now* or *Later*.

**Lectures.** Every past lecture as a tile with restudy progress. Opening one shows its moments ("What you missed") with the summary of each, and *Restudy*.

**Restudy (a lesson).** Duolingo-style lesson flow: progress bar, one card at a time. Question first. Miss it and the moment is explained in the next family (the artifact that fits the content), then asked again. Hit and it celebrates. Three in a row ends the lesson. With a headset on, the brain-wave strip stays visible and a drift switches the explanation early. Lesson end: what you got, what worked ("pictures rescued you twice").

**You.** Streak of days with a lecture, moments restudied, and "how you learn best" with the four families. "Not you? Start fresh."

**For the team** (gear icon): setup readiness in plain words plus the technical detail, signal panel, replay of any session, lecture loss map, the study quiz and numbers, and a session's event log.

## 7. Design philosophy (from Duolingo, applied)

- **One thing per screen, one primary button.** Every screen has exactly one big action.
- **Chunky, tactile controls.** Buttons with a solid bottom edge that press down; big radii; bold labels. Progress bars everywhere progress exists.
- **Immediate, warm feedback.** Right answers get a green flash and a line of praise; wrong answers get an honest "not yet" and a different explanation, never a red wall.
- **Bite-sized units and streaks.** A lecture's restudy is a lesson of a few cards; days with a lecture make a streak.
- **Character through motion and color, not mascots.** Progressive reveals, springs on buttons, a confetti-free completion screen that still feels like an event.
- **Plain language, second person, present tense.** No jargon from the spec on a student screen.

Our own constraint on top: **say when something is practice.** A simulated headset or a practice transcript shows a small "practice" label; forced triggers are for the team page only.

## 8. What changes in the code

- Backend: artifact schema (`GapPackage.artifacts` with applicability flags), four families (`words`, `analogy`, `visual`, `doing`) replacing the old form keys everywhere including the tally, a `review` session mode (headset only) so restudy can measure focus, a live brain-wave stream, per-card focus ratio, a profile endpoint, a reset endpoint, and migrations for existing databases.
- Frontend: rebuilt on the screens in §6 with the Duolingo-derived system in §7, artifact renderers (chart, steps, example, diagram), a brain-wave canvas, a lesson flow, and the team pages moved behind the gear.
- Docs: this file; PRD §5 to §6 point here; the verification record gains the new checks.
