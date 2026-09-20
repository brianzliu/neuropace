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

## 4. Ways to explain something: the template catalogue

An artifact is one generated way of presenting one missed moment. Each has a **glance** version (one line, for the live catch-up) and a **full** version (for restudy). Every full version is a **template**: a fixed rendering in the app whose data slots the model fills. The model never designs a layout; it answers a narrow question ("the points of this chart", "the events of this timeline") in its own strict schema, and the app draws it. That keeps generation honest, cheap and testable: each template has a sample page and its own validator.

Generation is two calls deep. A light **core** call per moment returns the note, the check question, the words family and a **plan**: which visual template and which doing template the content calls for. Then one focused call per template (the comparison, the planned visual, the planned doing) runs in parallel. If a planned template fails, the family's default is generated instead (diagram, worked example); if that fails too, the family shows the words content, so a card is never empty.

| Family | Template | What the model supplies | When the plan picks it | Rendering |
|---|---|---|---|---|
| **In words** | summary + key idea | 1 to 3 sentences; the term, its definition, one example | always | text, the term set large |
| **By comparison** | analogy | a short everyday story, 2 to 5 explicit mappings (idea = everyday thing), and where the comparison breaks | always | story, then the mapping pairs one per beat, then the caveat |
| **As a picture** | diagram | 3 to 7 nodes, labelled edges, 2 to 6 captioned steps | the default when nothing below fits | layered SVG graph revealed step by step |
| | chart | 2 to 8 named categories with the number the lecturer said, a unit, a takeaway | two or more comparable numbers for named things | bars grow in (or a line) |
| | plot | 1 to 3 series of x/y points, axis labels, up to 4 annotations, a flag saying whether the numbers are the lecturer's or only the described shape | a quantity changing with another: a curve, a trend, two curves crossing | curves draw themselves; "shape only" badge when illustrative |
| | timeline | 3 to 8 events in order, each with a when, a label and a one-line detail | dated events or the phases of a process | a line with dots, one event per beat |
| | compare | two named things, 2 to 6 aspects with both sides, a verdict | two things contrasted aspect by aspect | two-column table, one row per beat |
| | animation | a self-contained inline SVG or canvas animation (one script, no external resources) with a caption | a mechanism in motion: orbiting, travelling, flowing, oscillating, sorting | runs in a sandboxed iframe (scripts only: no network, storage or access to the app); Replay button |
| **By doing** | steps | 2 to 8 ordered actions | a procedure, method or algorithm | numbered list, one step per beat |
| | worked example | a title, 2 to 8 lines, the result | the default: any concrete instance with a result | monospace lines, the result last |

Decisions and reasons:

- **Four families, not ten arms.** The preference model must learn from few cards (about ten moments per lecture). The spec's simulation shows four arms need 60 to 150 scored cards to find a real preference; ten would need more than a semester. So the thing we measure is the family. Inside a family the template is chosen by content (the plan), never by preference.
- **Templates over free-form generation.** A model asked for "a visualization" produces something different every time and nothing the app can check. A model asked for "2 to 8 points with a label and a value" produces data the app renders the same way every time, validates (2 to 8 points, distinct options, safe animation code) and can show on a sample page without any model at all (`/team/artifacts/sample`).
- **Animation is the one template that carries code**, because motion cannot be reduced to a data table without losing the point. It is fenced: inline SVG or canvas plus one script, under 6000 characters, no network, no storage, no `parent`, rendered in an iframe with `sandbox="allow-scripts"` and nothing else. The validator rejects anything that reaches outside, and a rejected animation falls back to the diagram.
- **Everything is grounded.** Every template is built from the transcript span and the minute before it. Charts use only numbers the lecturer said; a plot with no numbers behind it says "shape only". If the span cannot support a template the plan does not pick it.
- **Not included in the scripted flows above, on purpose:** mnemonics (weak evidence, rarely grounded), flashcards (that is what the check question already is), images from image models (not grounded, slow). Free text chat is deliberately kept out of Restudy and Listen, which stay scripted — it exists as its own mode, §5a.

## 5. Restudy, rethought: teach first, then check, then strengthen

The first version of restudy opened every moment with a quiz. That was backwards for the thing restudy is for: a missed moment is material the student never heard. There is nothing to retrieve yet, so a cold question measures nothing and feels like a test of something you were never taught. Retrieval practice is powerful for material you have met once; it comes second, not first. The lesson now runs in three beats per moment, and a fourth kind of session comes later.

**1. Where you were.** One line of context (how the missed span connects to what the student did hear) and, folded away, the lecturer's own words for the span. The whole transcript is one click away on the lecture page, with the missed moments highlighted in it, because "where in the lecture was this?" is the first thing a student asks.

**2. Teach.** The moment explained in one family, chosen for this student (the preference model picks: exploit what works, explore what has not been tried), with the choice said out loud: "Pictures usually work best for you, so here it is as a curve" or "Let's try this one by comparison; we have not tried that yet". The explanation is a template filled by the model (§4), revealed beat by beat. With the voice tutor on, NeuroPace reads it: each beat is spoken (Deepgram Aura text to speech, cached per sentence), the text of the beat is highlighted as it is read, and the picture, chart, timeline, steps or animation advances in step with the voice, pausing on each part so the student can look. Space skips ahead at any time. With a headset on, the brain waves run under the card and focus is measured for the whole explanation.

**3. Check.** One question, four options, answerable from the span. A hit celebrates and moves on; a miss re-teaches the same moment in the next family and asks again. Three hits in a row end the lesson early; every moment covered ends it otherwise. A moment that misses in all four families is marked "still tricky" and comes back another day.

**One way in now: Review on my own.** This scripted engine used to have two entry points — *Private tutoring* (explained first, then checked) and *Review on my own* (checked first, explained only on a miss). Private tutoring's entry point is retired in favor of Office Hours (§5a), which now does that job as an open conversation instead of a fixed script; the button and the "explain first" ordering above are no longer reachable from the product, though the code and its family-preference scoring are unchanged for Review on my own, which is still how a student self-tests. The two are one tap apart: a corner toggle switches between Office Hours and Review on my own for the same lecture.

**4. Strengthen (designed, not yet built).** Moments that landed come back as quick checks after one day, three days and a week, from every lecture, as one short lesson on the Listen screen ("3 moments to strengthen"). Explanation only on a miss. This is the spaced part of the loop; it needs a due-date column on gaps and a lesson that spans sessions.

**How the learning profile is scored.** Every explanation shown is one trial for its family, and two things are recorded for it:

- *Understanding*: did the check right after it land? Rescues over attempts, as a Beta posterior with the population prior (the spec's bandit). This is the signal that says the explanation worked.
- *Attention*: with a headset on, the fraction of the explanation's seconds the student was not in a drop, from the same detector that flags drifts in a lecture (baseline carried over from the lecture, so it counts from the first card). This is the signal that says the explanation held them.

The ranking on You combines them, understanding first: score = 0.6 × posterior mean of rescues + 0.4 × mean attention (attention alone contributes nothing until it has been measured at least once). The top of the ranking is the student's preferred way once twelve explanations have been scored; below that NeuroPace says it is still learning. The family for the next explanation is drawn by Thompson sampling on understanding, so a new family keeps getting tried until the evidence settles. A drift during an explanation switches the family on the spot and records the low attention; it never scores understanding by itself, because attention and understanding are different things: an animation can hold your eyes without teaching, and a paragraph can bore you and still land.

**Why not A/B two explanations of the same moment side by side.** Showing family A then family B for one moment doubles the time per moment and confounds the second with the first (you already half-know it). Alternating families across moments is the same experiment without the confound, and ten moments per lecture give each family two or three trials per lecture. The only within-moment comparison is the one that matters to the student: a miss, then another way.

**Voice, where it belongs.** During a live lecture NeuroPace stays silent: the student is listening to a lecturer, and the catch-up is one line on screen. In restudy the tutor voice is the natural way to be re-explained something, and it is what makes a template reveal feel taught rather than paged through. Deepgram's text to speech is used first (the team already holds the key; sentence-level highlighting needs no word timestamps). A conversational agent now exists in a deliberately narrow form — continuous listening with no true barge-in, plus push-to-talk as a fallback — as its own mode (§5a), not folded into restudy. The fuller version (duplex audio, interrupt-anywhere mid-sentence) is still the next step after this one, not this one.

## 5a. Office Hours: an open conversation about a lecture

Restudy and Listen stay scripted on purpose (§4, §5): a fixed sequence keeps generation cheap, testable and honest. But a student who wants to just ask something — "wait, why does that follow?", "show me that again a different way" — has nowhere to type it. Office Hours is that place: a second mode, entered from the lecture page once a lecture is done, built for open-ended questions rather than a fixed lesson.

The student and the agent share one thing: a **board**. As the conversation goes, the agent explains by placing, updating and removing elements on the board — the same ten templates from the catalogue in §4 (words, analogy, diagram, chart, plot, timeline, compare, animation, steps, worked example), plus three small annotation primitives (a labelled shape, an arrow connecting two elements, a text label) for tying pieces together. The model is never handed a blank canvas to design freely: every element is one of these fixed, validated shapes, positioned on a bounded board, the same "narrow schema, app renders" discipline as everywhere else in this document. A long conversation doesn't grow the board without limit — the oldest element quietly makes way once the board is full.

**A twelfth kind, `manim`, exists but is optional and math-only.** For content the SVG `animation` template can't do justice to — an equation, a function's graph, a geometric construction, a calculus diagram — the agent can reach for a Manim Community script instead, rendered server-side and cached, in place of the sandboxed browser SVG/JS every other animation uses. It is deliberately not the default: the prompt tells the model to use it only for genuine mathematical content, and the kind isn't even mentioned to the model on a server that hasn't run `uv sync --group manim` (needs LaTeX and ffmpeg too). A script goes through the same import-allowlist-and-shape-check discipline as the SVG animation validator before it is ever executed, and a render that fails or times out just leaves the caption text on the board instead of breaking the conversation.

**Clicking a board element asks the agent to say more about it** — the same as typing a follow-up question, just aimed at something already on the board instead of typed out. The elaboration lands in the chat like any other reply.

**A timeline scrubber lets the student drag back through the conversation** and see the board and the chat exactly as they were at that point — read-only time travel, not an edit: dragging back never changes history, and a "return to now" brings the live conversation back.

**Voice agent, not a duplex conversation.** A toggle turns on continuous listening (the browser's own speech recognition — Chrome/Edge): talk whenever, it sends the moment you pause, the reply is spoken back, and listening pauses while the agent talks so the mic doesn't hear its own reply. There is no true barge-in — you cannot interrupt the agent mid-sentence by talking over it, only stop it and start again — and Firefox/Safari fall back to push-to-talk (hold a button, release to send) or typing. Replies are always spoken through the same text to speech Restudy uses. Full duplex audio with interrupt-anywhere is still future work, per §5's closing note.

## 6. Screens

**Listen (home).** One card: "Ready when you are" and *Start listening* (live microphone) or a practice lecture. Below: your lectures as tiles (title, date, "3 moments to restudy" or "all clear"). Headset and pad status as one friendly line each ("Headset on, signal good" / "No headset today, the button still works").

**Listening.** The transcript large in the middle. On the right: your brain waves (the live µV trace from the headset, labelled *live from your headset* only while chunks are actually arriving, *practice signal* when simulated, *waiting for the headset* when a paired headset goes quiet) and a focus ring with one sentence. One button, *Catch me up* (Space or the pad). When you drift, a soft prompt: "Want a quick catch-up?". The catch-up is one line at the bottom in your best family. *End lecture* at the corner. While a lecture is being recorded the screen is locked in: any sidebar item or route change asks "Do you want to quit recording?" (keep listening, or stop and go to the summary), and closing the tab gets the browser's own prompt. A headset switched on after the lecture started is picked up within five seconds and replaces the simulated focus. A *Details* toggle keeps the instrumentation for the team.

**Lecture done.** A completion screen: moments missed, the catch-ups you took, then *Review* (straight into Office Hours, which opens by walking through what was missed) or *Later*.

**Lectures.** Every past lecture as a tile with restudy progress. Opening one shows the two ways to restudy, the whole transcript with the missed moments highlighted (folded), and the moments ("What you missed") with the summary of each.

**Restudy (a lesson).** Duolingo-style lesson flow: progress bar, one card at a time. For each moment: where you were, then the explanation in the family chosen for you (with the reason said), read aloud by the tutor if you like, then the check. Miss it and the moment is explained in the next family, then asked again. Hit and it celebrates. Three in a row ends the lesson. With a headset on, the brain-wave strip stays visible, focus is measured per explanation, and a drift switches the explanation early. Lesson end: what you got, what worked ("pictures rescued you twice, and held your attention 92% of the time").

**Office Hours** (§5a). A shared board on the left, a chat on the right, entered from a finished lecture's page. Type or hold to talk; the agent replies and the board fills in as it explains, one element at a time. A scrubber above replays any earlier point in the conversation, read-only. Clicking a board element asks the agent to say more about it, right in the chat.

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
- Office Hours (§5a): an `office_hours` session mode with no headset/totem; a new event-sourced log (`oh_messages`, `oh_board_ops`) so the board and chat are always rebuildable from the DB and a timeline scrub is just a replay up to an earlier point; a conversational LLM call returning a reply plus board ops, validated the same way every template already is; a board renderer built on the existing artifact views; push-to-talk voice reusing the existing transcription and text-to-speech.
- Docs: this file; PRD §5 to §6 point here; the verification record gains the new checks.
