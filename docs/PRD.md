# NeuroPace: Product Requirements Document

**Event:** HackMIT 2026, Education track. Sat 19 Sep 2026.
**Source spec:** `~/Downloads/NEUROPACE-3.md` (the only spec this document derives from; earlier iterations are superseded).
**Status:** v1.0 for the signal engine, statistics and study. The student-facing product (screens, explanation families, artifacts, preferences) was redefined on 19 Sep in `docs/PRODUCT.md`, which supersedes §5 to §8 below where they differ.

---

## 1. One-line product

NeuroPace notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.

## 2. Problem

Mind-wandering during lectures goes with lower learning, and the lapses that hurt most are the ones you never noticed, so you cannot bookmark them. Whole-lecture notes are a commodity. Nobody makes notes for exactly the 40 seconds you missed, and nobody re-teaches those 40 seconds in a different form until you can answer a question about them.

## 3. Users

| User | Situation | What they get |
|---|---|---|
| **Learner** (primary) | Sits in a live lecture or watches a recorded one, wearing a NeuroSky MindWave Mobile 2 with a small desk "totem" (Arduino UNO Q 4 GB relay as the current target; the UNO R4 direct path stays as a fallback) | Instant one-glance catch-ups, gap notes for only the spans they missed, an adaptive review, and a personal tally of which explanation form works for them |
| **Lecturer** (secondary, aggregate only) | Several learners took the same lecture | An anonymous loss map: where the room was lost. It grades the lecture, never a student |
| **Judge / study participant** | The 3-minute demo and the 20-minute study | The same product, with any forced trigger announced as "simulated" |

## 4. Design principles (from the spec, each one binding)

| ID | Principle | Consequence for the build |
|---|---|---|
| P1 | Capture lapses passively | EEG flags spans without any learner action |
| P2 | Spend review time only on the gaps | Notes and review cover flagged spans only |
| P3 | Re-teach at card boundaries, never mid-sentence | Form switches happen only between cards; the live catch-up never changes form while visible |
| P4 | A tap gets an instant catch-up; an EEG flag only offers one | Only a tap auto-shows the card. An EEG flag pulses the totem and shows a "catch-up ready" chip. Exception: recorded video may auto-pause and show the card |
| P5 | Catch-ups are one glance, dim, and static in a live hall | One line, low contrast, no animation, fades after a few seconds. Animated diagrams only in review and paused video |
| P6 | Quiz answers decide what worked; EEG decides when and where | The tally is scored by check-question answers only. EEG never updates the tally |
| P7 | Test for personal preferences; don't assume them | No learning-style questionnaire. The tally starts from the population average and shows "not enough data yet" |
| P8 | Pool learners to judge the lecture | Loss map is aggregate, anonymous, z-scored per learner before pooling |
| P9 | Never fake a trigger silently | Any simulated headset, simulated tap, or forced flag is labelled on screen and said aloud |

## 5. Scope

### 5.1 In scope (must ship)

Stages A to D of the spec's build order. Each stage is a complete demo on its own.

- **Stage A:** pad tap → transcript span → instant one-line catch-up (from rolling recaps) → gap note → check question.
- **Stage B:** focus index as second flag source; live focus trace; totem pulse + "catch-up ready" chip; auto-pause for recorded video.
- **Stage C:** review player: miss or focus drop → re-teach in the next form; text-to-diagram dissolve; tally feeding the live form choice.
- **Stage D:** the study (§9) and the loss map. Feature freeze at hour 12.

### 5.2 Out of scope

- Any sponsor challenge other than Deepgram, OpenAI, and Long Lake framing (Arduino's challenge requires the UNO Q).
- A teacher dashboard with per-student data. Only the anonymous loss map is shared.
- Multi-channel EEG, workload/overload states, glasses, thermal printers.
- Comparing question-first review against re-reading (restudy wins at short delays; not measurable tonight).
- Cloud accounts and cloud backend deployment. Capture, storage, and hardware connections run
  on one laptop. The React interface may be hosted on Vercel and connect directly to the local
  service using an explicit origin allowlist and a per-process pairing code.

## 6. Functional requirements

### 6.1 Lecture mode

| ID | Requirement |
|---|---|
| FR-L1 | A session has a learner, a mode (`live` or `recorded`), and a lecture timeline in seconds (`lecture_time`). All events (words, focus samples, flags, taps, catch-ups) are stamped on that timeline |
| FR-L2 | In `live` mode the laptop microphone is captured in the browser and transcribed by Deepgram streaming with word timestamps. Words appear in the UI within 2 s of being spoken (network permitting) |
| FR-L3 | In `recorded` mode a media file is transcribed once by Deepgram prerecorded (cached), and the transcript is revealed in sync with the player. The player's current time is the lecture timeline |
| FR-L4 | A **tap** on the totem pad, or, when no Arduino is present, Space/`T` or the on-screen pad (the keyboard fallback; a real learner action, not a simulation) marks a span ending at the tap time with an 8 s lead-in, snapped outward to word boundaries |
| FR-L5 | The **focus index** E = β/(α+θ) is computed from the headset's 512 Hz raw stream once per second, EMA-smoothed, and z-scored against the wearer's own baseline from the first 3 minutes of listening (configurable; a stored baseline for a calibrated wearer is allowed and labelled) |
| FR-L6 | An **EEG flag** opens when the 15 s mean of z(E) stays below the drop threshold and closes when it recovers or after 30 s. The span starts 8 s before the drop was detected. Flags are suppressed while the poor-signal byte is above the gate, during baseline collection, and within 20 s of the previous EEG flag |
| FR-L7 | Raw segments with outlier peak-to-peak amplitude (blinks) are excluded before the FFT. Blinks are also counted and shown as ticks on the trace (the hour-1 hardware gate: "real blinks on a real forehead") |
| FR-L8 | Every 20 s the backend writes a **rolling recap** of the last ~30 s of transcript in all four form families (glance size) plus a plain line. The learner's current best form is marked. Generation never blocks the UI. If the model is unavailable the catch-up shows the verbatim transcript, labelled; it never shows templated text |
| FR-L9 | On a **tap**, the catch-up card for the flagged span appears in under 1 s. If the EEG had already flagged the lapse (flag open, or closed within 10 s), the tap confirms it: the span starts where focus dropped (up to 60 s back) and the card says since when: "You missed: <glance in the learner's best form>. Now: <the last few words spoken>". It is one line, dim, static, and fades after ~6 s (configurable). A key shows the same recap in a second form (demo) |
| FR-L10 | On an **EEG flag** without a tap, the totem pulses and a small "catch-up ready" chip appears at the screen edge. Opening it shows the card; ignoring it costs nothing. In `recorded` mode the player may pause and show the card automatically (setting, default on) |
| FR-L11 | The live view shows: streaming transcript, focus trace (last 3 min) with baseline and threshold, blink ticks, signal quality, flags as bands, taps as marks, totem status, headset kind (`real`/`simulated`), and the current best form |
| FR-L12 | The totem shows a fit meter while the baseline is collected and one dot per saved span afterwards |
| FR-L13 | A session can be ended by the learner; ending triggers gap-note generation |
| FR-L14 | Every session writes an append-only event log that can be replayed at 4× in the UI without the backend |

### 6.2 Gap notes

| ID | Requirement |
|---|---|
| FR-N1 | At session end, overlapping or adjacent flagged spans are merged into **gaps** (minimum 8 s, maximum 90 s each) |
| FR-N2 | For each gap the system produces a note with: what was said (grounded in the transcript span, quoting it), the key term and its definition, and how it connects to the part the learner did hear (the 60 s of transcript before the gap) |
| FR-N3 | For each gap the system produces a **check question**: multiple choice, four options, exactly one correct, answerable from the span alone, plus a one-line explanation |
| FR-N4 | For each gap the system pre-generates the full-size teaching in all four form families, including a diagram scene graph for the sketch family, so the review never waits on a network call |
| FR-N5 | Notes are shown only for flagged spans. A session with no flags shows "nothing flagged; nothing to review" |

### 6.3 Adaptive review

| ID | Requirement |
|---|---|
| FR-R1 | Review presents one card per gap, check question first |
| FR-R2 | A **hit** (correct answer) closes the gap. A **miss**, or a focus drop while the card is open, re-teaches the same gap in the next form, then asks again |
| FR-R3 | The form order for a gap is: the learner's best form first (from the tally), then the remaining forms by tally rank, never repeating a form for the same gap. When the sketch form is reached, the text dissolves into an animated diagram built from the scene graph |
| FR-R4 | Review ends after three straight hits, or when every gap has been closed or exhausted (all four forms shown) |
| FR-R5 | Every card outcome is written to the tally: the form shown immediately before a hit earns a rescue; the form shown before a miss earns a miss. The first question of a gap (no re-teach yet) credits the form used in that gap's live catch-up, if one was shown |
| FR-R6 | Keyboard: `Enter`/`1-4` answer, `D` simulate a focus drop on the card (labelled simulated) |

### 6.4 Tally

| ID | Requirement |
|---|---|
| FR-T1 | Four families: `plain` (plain recap), `keyterm` (key term + definition), `analogy`, `sketch` (sketch or formula; diagram in full size). Each has a glance-sized and a full-sized version |
| FR-T2 | Per learner, per form: rescues and attempts, persisted across sessions |
| FR-T3 | The live catch-up form is chosen by Thompson sampling over Beta posteriors whose prior is the population average across all learners (pseudo-count 2). A brand-new learner therefore starts from the average |
| FR-T4 | The panel shows rescues/attempts per form, the current pick, and "not enough data yet" until the learner has at least 12 scored cards |
| FR-T5 | The tally is updated by quiz answers only (P6) |

### 6.5 Loss map

| ID | Requirement |
|---|---|
| FR-M1 | For a lecture with ≥ 2 sessions, the loss map pools per-learner z-scored focus in 10 s bins plus tap counts, and reports the 40 s window with the highest pooled loss and the ranking of the lecture's segments |
| FR-M2 | The map is anonymous and aggregate: no per-learner traces are exposed on that view |
| FR-M3 | The map states n (learners) and says "needs 2 or more learners" below that |

### 6.6 Study support

| ID | Requirement |
|---|---|
| FR-S1 | A lecture manifest holds segment boundaries and the 15 pre-written quiz items with the lecture-time span each item covers |
| FR-S2 | Per session, the catch-up policy can be `always` or `randomized`; under `randomized`, each flagged lapse is independently shown or withheld by a logged coin flip |
| FR-S3 | A final quiz view records the learner's 15 answers before and after review (the study uses the before-review answers for the flagged-vs-unflagged number) |
| FR-S4 | `neuropace study-analyze` produces the four numbers of spec §6 with intervals, including nulls: flagged vs unflagged recall (before review), loss-map rank of the planted bad segment, catch-up benefit and cost, rescues per form |

### 6.7 Operations

| ID | Requirement |
|---|---|
| FR-O1 | `neuropace doctor` reports: keys present, Deepgram reachable, selected OpenAI/OpenRouter model available, headset port, totem port, frontend build present |
| FR-O2 | Everything runs with no hardware: simulated headset, keyboard totem, scripted transcript, all labelled. A key for the selected OpenAI/OpenRouter provider is required to start a session; the extractive offline generator exists for automated tests only |
| FR-O3 | One command starts the whole product: `uv run neuropace serve` |
| FR-O4 | LLM outputs are cached on disk by content hash, so replays and re-runs are free and instant |

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Tap → catch-up visible: < 1 s (no network call on the tap path) |
| NFR-2 | Rolling recap cadence: 20 s; a recap call that takes longer than 15 s is dropped, not queued |
| NFR-3 | Focus sample cadence: 1 Hz; UI trace latency < 500 ms |
| NFR-4 | No single failure (Deepgram down, OpenAI down, headset unplugged, totem unplugged) stops the session. Each degrades to its labelled fallback |
| NFR-5 | Cost: about $0.04 per lecture hour on a small model for recaps; notes and review cards are a few cents per session |
| NFR-6 | Privacy: learner data stays on the laptop's SQLite. The only shared view is the loss map |
| NFR-7 | The whole test suite runs in < 60 s without network or hardware |

## 8. Demo requirements (3 minutes)

| Beat | Time | Needs |
|---|---|---|
| Pitch | 0-20 s | Name NeuroChat. "We don't believe in learning styles; we test it on you" |
| Live | 20-80 s | Teammate lectures 60 s; transcript + trace stream; judge taps the pad; catch-up in < 1 s; show the same recap in a second form: "this learner's data says analogies land" |
| Replay | 80-130 s | A real session at 4× with flags; that learner's gap notes; one review card: miss → dissolve into diagram → hit |
| Loss map | 130-170 s | The study's map with the planted segment revealed; the flagged-vs-unflagged number with its interval |
| Close | 170-180 s | "Learner-owned data. The only shared view grades the lecture" |

Rule: say "simulated" aloud whenever a forced trigger is used (P9). The UI labels it too.

## 9. Study requirements (spec §6)

One recorded 8-min lecture in 5 segments, segment 3 deliberately bad (jargon, no example). 15 quiz items written before anyone is tested (3 per segment). 10 to 12 participants, ~20 min each: fit, baseline, watch without pausing with headset + pad and live catch-ups (randomized per lapse), gap notes, adaptive review, final quiz.

Four numbers, each with an interval:
1. Recall on flagged vs unflagged spans, before review (`paired_outcome`). n=10 gives ~72% power for a 25-point gap.
2. Does the pooled loss map rank segment 3 first?
3. Catch-up benefit (recall on the missed span) and cost (recall on the 20 s after it), catch-up shown vs withheld.
4. Rescues per form in review (descriptive).

## 10. Sponsor-challenge compliance (verified against the HackMIT 2026 challenges PDF)

| Challenge | Requirement (from the PDF) | How NeuroPace meets it |
|---|---|---|
| Deepgram | "your project must call a Deepgram API" | Streaming transcription in live mode; prerecorded transcription for recorded lectures. Both calls are in the product path, not a side feature |
| OpenAI | Build with the OpenAI API; show how Codex helped; share one concrete Codex story in the demo | Structured outputs (JSON schema) for recaps, notes, questions, re-teach forms, diagrams. Codex story: to be recorded during the event (see `docs/DEMO-RUNBOOK.md`). Only teams submitting to this challenge get credits |
| Long Lake | An experience a skeptic would try, love, and use again | Pitch framing only: no prompt box, nothing to type, the product notices for you |

## 11. Acceptance criteria per stage

| Stage | Demo that must pass |
|---|---|
| A | Start a live session with a scripted transcript and no hardware. Press `T` at 40 s. A one-line card appears in < 1 s with the recap covering 32-40 s. End the session. A gap note and a 4-option question exist for that span |
| B | Simulated headset toggled to "drifting" produces an EEG flag within 30 s: totem pulses, chip appears, trace shows the drop band. In recorded mode the video pauses and shows the card |
| C | Review a session with 2 gaps: miss the first question → card re-teaches in the next form → sketch form dissolves into a stepped diagram → hit. Tally shows the outcome and "not enough data yet" |
| D | Two sessions on the demo lecture produce a loss map with a 40 s peak and a segment ranking. `neuropace study-analyze` prints the four numbers with intervals on synthetic data |

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Headset pairing fails / EEG uninformative on the wearer | Kill rule at hour 5: pad + quiz carry the product; EEG shown as an experimental overlay. Simulated headset keeps everyone unblocked |
| Deepgram down or noisy hall | Scripted transcript mode; close mic; keyterm prompting from the lecture's key terms; recorded lecture as fallback |
| OpenAI latency or bad JSON | Recaps are precomputed every 20 s; strict JSON schema; one retry; extractive fallback labelled offline; disk cache |
| Totem/serial flakiness | Auto-reconnect; `T` key and on-screen button labelled simulated |
| Study shows nothing | Report the null with its interval |
| "Isn't this NeuroChat / ARTFul?" | Say it first, in the first 20 s |
| Code-provenance rules | Code written in-event with visible commits; AI assistance disclosed in the submission |

## 13. Open questions (owner: team, resolve at hour 0)

1. HackMIT's rule on code written before hacking opened and on AI assistance.
2. Judging format and time per team.
3. Real-forehead performance of the focus index on the team's headset (the hour-1 gate).
4. Deepgram and OpenAI booth requirements beyond the PDF text.
5. Which OpenAI model id is available on the event credits (`neuropace doctor` lists them).

## 12. Workspace and UNO Q extension, 19 Sep 2026

User-directed amendment to v1.0. Earlier requirements remain in force except the hardware and
navigation changes below. This extension is a prototype, with hardware verification outstanding.

- **FR-D1:** `/` is the selected learner's dashboard: unresolved concepts first, recent sessions
  in a side column, and curriculum coverage below. It never pools individual learners' notes.
- **FR-D2:** The configured LLM may summarize saved notes and propose a review order. Unknown or
  repeated gap IDs invalidate the suggestion. Missing model access uses deterministic ordering.
  Suggestions cannot modify review outcomes or curriculum completion.
- **FR-D3:** Paste a syllabus or upload PDF/TXT/Markdown, limited to 2 MB and 30 PDF pages. Preview
  and edit extracted topics before saving. Scanned PDFs without text require pasted text.
  Topic checkboxes track self-reported coverage, not demonstrated mastery.
- **FR-D4:** New session opens a dedicated studio window with a same-tab popup-blocked fallback.
  Session setup, device detection, live capture, and review are separate views.
- **FR-H1:** Current target hardware is UNO Q 4 GB and MindWave Mobile 2. A planned large printed
  press surface actuates a momentary switch. The Q MCU debounces it; Q Linux runs the existing
  EEG pipeline and relays feature frames and button events to the laptop over BLE. This is an
  experimental transport until tested on the board. Direct laptop EEG remains available.
- **FR-C1:** Live sessions offer explicit camera start/stop with capture disclosure. JPEG frames
  are sampled every 2 s, capped at 45 frames/90 s in server memory, and cleared at stop/end.
  No continuous video file is recorded. Microphone transcription remains separately enabled.
- **FR-C2:** An allowed button catch-up may asynchronously request an explanation from recent
  transcript and at most four preceding board frames. Never override randomized withholding.
  Keep the immediate transcript catch-up; offer the board explanation separately, without
  replacing text mid-reading. Label generation failure as offline and board not interpreted.
- **FR-C3:** Board explanations are model output with supplied frame timestamps, not validated
  image understanding. Full classroom video recording, durable board-image notes, automatic
  syllabus mastery inference, and production BLE access controls are not implemented.
