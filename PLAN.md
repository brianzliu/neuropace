# NEUROSPACE — plan
**HackMIT 2026 · Education · NeuroSky MindWave Mobile 2 + Arduino UNO R4 · Sat 19 Sep 2026**

This file consolidates every planning document written for this project into one place. It
replaces `NEUROPACE HackMIT2026 Education Plan.md` and `NEUROPACE-2.md` as the thing to read; both are
kept in git history, not deleted, since they're the dated record of how the idea got here.

## 0. How this plan evolved, and what to read

**Current product name: Neurospace.** NeuroPace is the historical name used in earlier parts
and internal package/command identifiers. The app and hosted deployment use Neurospace.

The idea went through three passes, each written as a fresh, honest evaluation of the one before
it rather than a patch. Read them in order if you want the reasoning; read the Quick reference
below if you just want where things stand right now.

- **Part I — the original build plan.** A real-time reading assistant: EEG + webcam + behavior as
  three witnesses, watching you read *live* and dissolving the paragraph you're stuck on into a
  diagram mid-sentence. This is where the signal-processing detail, the code inventory, the
  Arduino specifics, and most of the sourced background live. Still true unless Part II or III
  overrides it.
- **Part II — the product pivot.** Two problems killed the "adapts to your learning style" framing
  and the real-time-while-reading mechanic: the learning-styles literature has no empirical
  support, and a single dry electrode can't tell *why* someone disengaged closely enough to pick a
  format for them live. Part II moves the sensor's job to *marking* lapses during a **lecture**
  (not live reading), generates gap notes from the transcript, and does the format-adaptation in a
  **review** phase afterward, where a check question — not the sensor — decides whether a
  re-teaching attempt worked. Camera and mid-sentence dissolve are dropped for scope, not because
  they were wrong.
- **Part III — the special-education addendum.** Written against Part II specifically, for the
  case where the target user is a student in an inclusion classroom with a diagnosed learning
  disability who often can't or won't self-report being lost. It finds that both of Part II's
  trigger mechanisms (EEG, pad tap) are weakest exactly where this population needs them, and adds
  a third trigger that doesn't depend on the student's state at all, plus privacy and framing
  changes that follow directly from the self-advocacy and stigma literature.

**19 Sep revision, requested product direction:** Part II now includes a dedicated Arduino
physical "I'm stuck" button, EEG timing, and a teacher/whiteboard-facing webcam with microphone.
Timestamped board images and the teacher's audio transcript supply context for a multimodal LLM
explanation when the learner presses the button. This restores the camera as **lesson content
capture**, not learner face/gaze analysis. See II.2.1 and II.4. A bounded camera-buffer and multimodal-request prototype now exists, but live capture and
model grounding still require end-to-end verification. It is not a verified classroom system. The workspace extension is recorded in `docs/PRD.md` and `docs/TDD.md`; earlier frozen
requirements remain the baseline wherever the addendum does not override them.

**Hardware correction and workspace revision, 19 Sep:** The user has an **Arduino UNO Q 4 GB**
and **NeuroSky MindWave Mobile 2 Brainwave Starter Kit**. The physical button is not built yet;
a large 3D-printed press surface will actuate a momentary switch. The earlier UNO R4 descriptions
remain historical. The current target connects the headset to the Q's Linux Bluetooth stack,
reads the switch on its MCU, and relays both to the laptop over BLE. A prototype is in
`firmware/uno_q_relay/`; board compilation, pairing, throughput, and physical wiring remain
unverified. Direct laptop EEG remains an explicit fallback, not the target architecture.

The app now separates a learner-owned review dashboard from `/session/new` and the live session
window. The dashboard prioritizes saved concepts, optionally summarizes/reorders them with the
configured LLM, lists recent sessions on the side, and accepts pasted or uploaded PDF/TXT/Markdown
syllabi. Learners review extracted topics before saving; curriculum completion is self-reported,
separate from concepts cleared by check questions. No teacher view is added.

**Current authoritative direction:** Part II's architecture (lecture capture → gap notes →
adaptive review) with Part III's additions layered on top (content-based risk flagging as a third
trigger, private output routing, configurable accommodation profile, "available to everyone"
framing). Part I remains the reference for anything Part II/III don't redefine: the EEG signal
chain, the existing `mindwave/` codebase, Arduino board specifics, and the general honesty/demo
discipline (undo on every neuropace, label simulated states, never fake a sensor).

**Tags**, carried across all three parts: **[V#]** = a source that was opened (numbering restarts
in each part — see that part's own Sources subsection). **[RUN]** = a simulation or script that
was actually executed, with output reproduced in the text. **[U]** = not independently verified;
confirm before relying on it. **[!]** = a claim that was checked and turned out wrong.
**ASSUMPTION** = a number chosen by the author, not measured.

---

## Quick reference

**Pitch, right now:** A study tool any student in the room could opt into. In a lecture, a
headset, a dedicated Arduino button, and the transcript itself flag the moments you lost the thread —
including the ones you didn't notice. Press the button for a private explanation grounded in
what the teacher just said and drew: a webcam captures the whiteboard and its microphone captures
the teacher's voice for transcription. Afterward you get notes for exactly those gaps, and a review
pass that re-teaches each one in a different form — worked example, analogy, diagram — until a
check question says it landed. It learns which form rescues you, keeps that as your playbook, and
never shows anyone else that you struggled.

**What's different from Part I's original pitch:** no claim about detecting a "learning style";
the sensor's job is timing (*when* you were lost), not diagnosis (*why*, or what to teach you
instead) — a check question does the diagnosis. No live mid-sentence dissolve; the dissolve
mechanic survives, moved into the review phase. The camera captures lesson content, not learner
state. Trigger sources remain EEG + physical button +
(Part III addition) transcript-based risk flagging.

**Immediate build priorities (Part II §8 + Part III §6 merged):**
1. Dedicated Arduino button → timestamped transcript + whiteboard context → private catch-up,
   gap note, and check question (Part II Stage A and II.2.1). Start with the working transcript-only
   path, then add synchronized board frames and multimodal generation with explicit fallbacks.
2. Focus index (EEG) as a second flag source (Part II Stage B).
3. **Content-based risk flagging** on the transcript — vocabulary density, sentence complexity,
   rate vs. baseline — as a third, state-independent flag source (Part III, promoted to Tier 1: cheap,
   same-afternoon build, and it catches the "still attending, still not understanding" failure mode
   the other two triggers miss).
4. Review player: miss or drop → re-teach in the next form; dissolve; tally (Part II Stage C).
5. Route all in-session output to a private surface — phone face-down / haptic, not a visible
   totem light (Part III).
6. Study + loss map (Part II Stage D), freeze features at hour 12.

**Kill rule:** if EEG isn't contributing usable signal by hour 5–6, ship pad tap + transcript
flagging as the two witnesses, label EEG experimental, say so out loud (Part I §12, Part II §8).

---

# Part I — original build plan

### Responsive design for cognition. The lesson neuropaces the moment you lose the thread.
**NeuroSky MindWave Mobile 2 + webcam + Arduino UNO R4**

A **real-time teaching assistant**. It watches you learn and changes the material *while you are
reading it*. It is not a post-session quiz, and it is not a chatbot.

> **Status note:** Part II moved the adaptation from "live, mid-sentence, while reading" to
> "after a lecture, during review, gated by a check question." The webcam-as-third-witness idea
> below was dropped in Part II for scope, not because it was disproven — see Appendix A. The
> signal-processing detail, code inventory, Arduino detail, and demo/build discipline in this
> Part are otherwise still current.

## I.1. The pitch (superseded by Part II/III — kept for the underlying reasoning)

**One line.** Responsive design for your brain: the lesson neuropaces the moment you lose the thread.

**Thirty seconds.** Responsive web design neuropaces a page to fit the screen. NeuroPace neuropaces a
*lesson* to fit your mind, live. A ten-second EEG headset, your webcam and your own behavior act
as three witnesses. When two agree you are overloaded, the paragraph you are stuck on dissolves
into an animated diagram built from the same content. When two agree you have checked out, the
text asks you to predict the next step or turns into a simulation. It learns which fix works for
you and hands you that playbook. Point the camera at a textbook and it neuropaces that too.

**Not an AI tutor.** An AI tutor generates explanations and waits for you to ask. NeuroPace has no
prompt box. It is a rendering layer that sits under any content and changes its *form* from a
closed loop with your brain, face and behavior.

**Why "assistant" and not "quiz".** The intervention has to land while the confusion is live. A
paragraph explained after the fact is a different, weaker product, and it throws away the one
thing the sensor is good for, which is timing.

## I.2. Novelty, with the prior art named and quoted correctly

What NeuroChat actually is (arXiv 2503.07599, CUI '25, Baradari, Kosmyna, Petrov, Kaplun, Maes)
[V5]: a Muse 2 headband (AF7, AF8, TP9, TP10, ref Fpz); engagement E = β/(α+θ) on a 15 s sliding
window; normalized against a 2 min relaxation task and a 2 min word-association task; the score is
**frozen when the user starts typing** and injected into the GPT-4-turbo prompt so the *next
reply* changes depth, format and tone. n=24. Engagement rose (p = 0.029). Quiz and essay scores did
not change.

Their own §6.2 limitations are our roadmap. Put these on the slide:
- "increased engagement … can also reflect cognitive overload, confusion, or frustration … does
  not distinguish between productive and unproductive forms of engagement, nor does it adapt based
  on … cognitive load"
- "could benefit from integrating complementary signals, such as task performance, self-reports,
  or behavioral metrics"
- "more robust neuroadaptive systems may benefit from multimodal sensing, artifact rejection
  techniques, or sensor fusion"
- participants asked for "mind maps or diagrams … images or timelines could reduce the cognitive
  burden of reading"
- "there is no fixed rule set that defines how different values should influence the response"

| | NeuroChat (MIT, 2025) | **NeuroPace (Part I design)** |
|---|---|---|
| When it acts | At your next message. Nothing changes while you read | **Mid-paragraph**, on the unit you are stuck on right now |
| State | One axis, engagement (admitted to confound overload with interest) | **Two axes: overload × engagement**, different fixes for each |
| Evidence | EEG only, 4 channels | **Three witnesses: brain (1 ch), face (webcam), hands (behavior)**; two must agree |
| Adaptation | Rewrites the text: depth, tone, bullets | **Modality transformation:** text → diagram → chunks → worked example → simulation |
| Personalization | One prompt for everyone | **Bandit per learner** → a playbook they own |
| Learning signal | Quiz after 20 min; no gain | **Time-to-recover and checkpoint correctness on every intervention** |
| Content | Chat answers the bot wrote | **Any content:** paste, PDF, a textbook page held to the camera |
| Calibration | Two-point, 4 min | Three anchors, 60 s (same idea, faster; **do not claim novelty here**) |
| Data | Client-side, no ownership story | **Learner-only; no teacher dashboard; undo on every neuropace** |

Say it in the first twenty seconds: "NeuroChat proved an LLM tutor can respond to EEG engagement.
It also found that engagement alone did not improve learning, could not tell overload from
interest, and never changed anything while you were reading. NeuroPace starts where their limitations
section ends."

## I.3. "The EEG is bad and only detects binary focus" — half true, and it matters which half

**True:** the **eSense attention meter** (`0x04`, 0–100, 1 Hz) is a proprietary black box.
NeuroSky publishes no algorithm, says only that it weighs beta and gamma with "slow-adaptive"
internal adjustment, and its own docs call 40–60 "neutral" [V13][V14]. Between the coarse banding
and the hidden adaptation it behaves like a two- or three-level focus light, not a measurement. Any
claim built on it is unfalsifiable, because we cannot say what it computed.

**False as a statement about the device:** the headset also streams **raw 512 Hz at Fp1** (`0x80`).
That is a real signal and we compute our own band powers from it. Szafir & Mutlu built a working
attention-adaptive agent from exactly this, same sensor family, same electrode site [V3].
`mindwave/features.py` already does the Welch PSD, so we own every number in the chain.

**The real limitations**, worst first:
1. **One channel, no spatial filtering.** The 80–83% figures in [V2] come from many electrodes and
   per-subject spatial models. One electrode cannot reach that. **0.65 AUC [V4] is our ceiling and
   our quoted number.**
2. **Fp1 sits directly over the eye.** Blinks are 100–300 µV transients landing in theta, the band
   we care about. Unmasked, blinks *manufacture* the effort signal. `features.py` detects them in
   a separate 0.5–8 Hz band and interpolates across them before the PSD. This is the single most
   important correctness detail in the codebase.
3. **Dry electrode.** Contact drifts. The quality gate (`poor_signal > 50` → frame invalid) is
   mandatory, not defensive.

**What this changes in the design:** it is the whole reason for the three-witness rule in I.5. A
~0.65 detector cannot be allowed to fire an interruption on its own. Treat `attention` and
`meditation` as passthrough-for-comparison only, which is how `pipeline.py` already labels them.
**Keep the eSense number out of the demo and the submission.** If a judge asks whether we use
NeuroSky's attention score: no, it is proprietary and coarse, we compute Pope's engagement index
from raw, and here is the confusion matrix against thought probes.

## I.4. Code that already exists (read before building anything)

`mindwave/` is a working ~1,750-line pipeline and **it was built for this architecture**.
`brain_example.py` already sketches the FLOW / OVERLOAD / DISENGAGED / FATIGUE consumer with the
two-key rule. Nothing here needs re-aiming, and it's the shared foundation under Part II and III
as well — neither pivot touches this layer.

| Module | What it does | Status |
|---|---|---|
| `thinkgear.py` | Serial protocol, packet/checksum parse, all five codes, threaded reader | Done |
| `features.py` | 4 s windows, three filter bands, blink detection + masking + interpolation, Welch PSD, `effort` = logθ−logα, `engagement` = logβ−log(α+θ) | Done. **The asset** |
| `calibration.py` | Three anchors (`eyes_closed`, `easy`, `hard`), z-scoring so hard ≈ +1 and easy ≈ −1, refuses weak calibrations, reports sign inversion instead of hiding it | Done, and the reading anchors are **correct** for this design |
| `pipeline.py` | Quality gate, artifact-coverage gate, 5 s EMA, 1 Hz `FeatureFrame`, session logging, `ReplaySource` | Done. Replay is the demo fallback |
| `server.py` | WebSocket feed at `ws://127.0.0.1:8765` | Done |
| `monitor.py`, `run_pipeline.py`, `example_consumer.py` | Live plot, headless service, consumer example, all with `--fake` | Done |

**[!] Correction to an earlier note:** `mindwave/README.md` and the `pipeline.py` docstring were
briefly marked "stale" for describing FLOW / OVERLOAD / DISENGAGED. They are not stale. They
describe this design correctly. Leave them alone.

**Still to build (as of Part I):** the brain (hysteresis, dwell, three-witness fusion), the camera
track, the reader UI, the transformation ladder, the diagram pipeline, the bandit, the Arduino
sketch. Part II supersedes some of this list — see Part II §8 for what's actually still open.

## I.5. Signal engine (still current — Part II §3 and Part III §3 build directly on this)

**EEG** (done, in `features.py`): `effort` = logθ − logα, `engagement` = logβ − log(α+θ), blink
rate and duration over a trailing 30 s, all gated on `poor_signal` and artifact coverage, z-scored
against calibration, 5 s EMA. `L` and `E` arrive as a 1 Hz `FeatureFrame`.

**Camera** (designed, not built; dropped from Part II's scope, kept here for the record and as a
stretch — see Appendix A): MediaPipe Face Landmarker in the browser, 478 landmarks, 52 blendshapes,
a 4×4 head-pose matrix, 30 fps on a laptop [V18].
- **Effort / confusion:** `browDownLeft/Right` (AU4 brow lowerer), `eyeSquintLeft/Right`, lean-in
  (face box growing).
- **Disengagement:** head yaw or pitch away from the screen, iris off-screen, `jawOpen` yawn,
  lean-back, low head-motion energy for 20 s.
- **Fatigue:** blink rate up, lid droop. Cross-checks the headset's own blink count, which is a
  free sanity check on electrode contact.

**Behavior:** response time vs baseline, checkpoint correctness, scroll stall > 8 s, scroll-back
(re-read), idle input, tab blur, fast-but-wrong.

**Calibration (60 s, already implemented).** `eyes_closed` (~10 s, alpha reference and the honest
"the electrode works" demo beat), `easy` (~25 s), `hard` (~25 s). Hard maps to about +1 and easy to
about −1 per learner. If the hard task did not raise effort, `pipe.status()` says so rather than
flipping the sign silently. This is NeuroChat's two-point idea done faster; **do not claim it as
novel**.

**State** (EMA τ = 5 s, hysteresis, 20 s minimum dwell between interventions):

| State | Brain | Face | Hands |
|---|---|---|---|
| FLOW | L mid, E high | brow relaxed, gaze on page | RT ≈ baseline, correct |
| OVERLOAD | L > +1 for ≥ 8 s | brow furrow, squint, lean-in | RT slow, re-read, errors |
| DISENGAGED | E < −1 for ≥ 8 s | gaze away, head turned, lean-back, yawn | idle, fast-but-wrong, tab blur |
| FATIGUE | E drifting down over minutes | blink rate up, lid droop | RT slowing over minutes |

**Three-witness rule.** An intervention fires only when **two of the three** agree, or when one is
extreme for 15 s. This is the honest answer to "how good is a $100 single-channel headset?", and it
is what stops the thing being annoying. If EEG quality is red, face and hands carry the decision
and the UI says so. (Part II reduces this to a two-source rule — EEG + pad tap — since the camera
witness was dropped; Part III adds a third, state-independent source back in.)

## I.6. Interventions: content transformations, never tips

**OVERLOAD ladder (cheapest first):**
1. **Dissolve → animated diagram.** The paragraph dissolves letter-by-letter while an LLM turns
   the same text into a scene graph; the diagram animates in step by step with captions. *The
   dissolve is timed to cover generation latency.*
2. **Chunk & reveal.** Same content as three steps, one at a time, one checkpoint question after
   each.
3. **Worked example.** The abstract paragraph becomes a concrete instance.
4. **Say it.** When overload coincides with gaze leaving the page, a spoken walkthrough synced to
   the diagram steps.
5. **Declutter.** Hide everything but the current unit; larger type.
6. **Save the thread.** Bookmark the exact sentence; two-line re-entry summary.

**DISENGAGED ladder:**
1. **Predict the next step** (retrieval prompt inline). Retrieval beats restudy at a delay [V11],
   so this is the default.
2. **Explain it back**, aloud, to a voice agent that probes and scores.
3. **Turn it into a simulation** (slider or drag on the diagram's variables).
4. **Raise difficulty / skip known** (fast-and-correct means bored, not overloaded).
5. **Micro-break**, 90 s timer.

**Playbook (the product).** Thompson-sampling bandit per learner over the arms; reward = state
returns to FLOW within 45 s **and** the checkpoint is correct. After a session: "Overload →
diagram fixed it in 9 s (3/3). Disengaged → prediction prompt (2/2). Breaks didn't help you." The
learner owns it and can hand it to a teacher on their own terms.

**Undo on every neuropace.** A "back to text" chip, always visible. This is both a usability answer
and the surveillance answer. This rule carries through unchanged into Part II and III.

## I.7. The dissolve → diagram pipeline (the wow, made reliable)

1. **Detect** OVERLOAD on the current unit (text node id).
2. **Generate:** strict JSON schema, `{title, nodes:[{id,label,kind}], edges:[{from,to,label}],
   steps:[{highlight:[ids], caption}]}`. Temperature 0. Retry once on invalid JSON.
3. **Layout:** dagre (or elkjs) for a DAG; d3-force for concept maps.
4. **Animate:** anime.js or Framer Motion timeline; nodes fade in per `steps`, edges draw, captions
   crossfade; 8–15 s; scrubable.
5. **Cache** three demo topics (Krebs cycle, Bayes' theorem, backpropagation) at build time. Live
   generation for arbitrary text is the stretch and still works with the dissolve masking 3–6 s.
6. **Undo** chip always visible.

Mermaid plus CSS animation is the 30-minute fallback renderer.

**Camera as input (cheap, high impact; dropped from Part II's scope).** A "scan" button grabs a
webcam frame, sends it to a vision model, returns units of text. The textbook page becomes a
neuropaceable lesson. Cache one pre-shot page in case the table lighting is bad.

## I.8. The Arduino UNO R4

The board arrived by accident instead of the UNO Q. It still earns a place, but a small one: **it
owns the inputs and indicators that should not live in the UI being neuropaceed.**
- **"I'm lost" button.** A physical press is a manual intervention request *and* the ground-truth
  label that trains the bandit and validates the detector. This is load-bearing.
- **Fit meter.** Seat the headset by watching LEDs fill, instead of squinting at a number on
  screen. Turns a 60 s fumble into a 10 s demo beat.
- **Ambient state light.** Shows the system is watching without putting a widget on the page.
  **Superseded by Part III §2:** for the special-ed pivot, route this output to a private surface
  instead — see Part III.

**[!] Which R4 is it? Answer before writing the sketch.**

| | UNO R4 **WiFi** | UNO R4 **Minima** |
|---|---|---|
| 12×8 LED matrix | **Yes** | **No** |
| Radio | ESP32-S3 (Wi-Fi + BLE) | **None** |
| `LOVE_BUTTON` capacitive pad | Listed as supported [V15] | Listed as supported [V15] |

On a **Minima** the fit meter falls back to `LED_BUILTIN` blink-rate coding, or move it to the
laptop. Decide in the first ten minutes.

**[!] The heart pad may need a part.** Sources conflict. The official `Arduino_CapacitiveTouch`
library lists `LOVE_BUTTON` as supported on both boards and mentions no external components [V15].
A widely used third-party library states it "requires the addition of a small capacitor … between
pin 10 and ground on the Arduino UNO-R4 Minima or between pin 7 and ground on the Arduino UNO-R4
WiFi", 1 nF to 10 µF, affecting the threshold [V16]. Try the official library first and **wire a
plain momentary pushbutton to a digital pin in the same sketch as the backup.** The heart pad is a
nice detail; the press is load-bearing. Never let a nice detail own a load-bearing input.

**[U] Serial routing.** Headset → laptop → R4 over USB serial. The R4's radio cannot take
Bluetooth Classic SPP from the headset, so the laptop is the hub. Confirm in hour 0 that `pyserial`
talks to the R4 while the headset is also connected; both want a COM port and the MindWave's
outgoing SPP port is not always COM3.

## I.9. The measurement, and the trap in it

**The trap, and it is a big one.** Szafir & Mutlu ran the closest published study to NeuroPace: a
NeuroSky at FP1, engagement index, an agent that cued attention in real time. Adaptive cues beat
the no-cue baseline (p = .022) but **did not beat random-timed cues (p = .118)** [V3]. So a demo
that compares "NeuroPace on" against "plain text" proves only that interventions help. It proves
nothing about the sensor, which is the entire claim.

**Therefore every measurement needs a yoked random-timing control**: the same number of the same
interventions, fired at times drawn from another participant's trigger distribution. It costs one
config flag and it is the difference between a defensible result and a press release.

| Number | Question | Tool |
|---|---|---|
| **Detector vs probes** | Does the state flag agree with self-report better than always guessing the majority? Per wearer | `neuropace_eval.py detector` |
| **Recovery** | After a sensor-timed neuropace, does state return to FLOW faster than after a yoked random-timed one? | `neuropace_eval.py outcome` |
| **Comprehension** (stretch) | Checkpoint correctness, sensor-timed vs yoked | `neuropace_eval.py outcome` |

Recovery is the cheap one and it is within-subject, so it needs no quiz bank and no separate
session. Collect it from anyone who wears the headset for ten minutes.

**Thought probes** for the detector number: while a teammate reads for 12–15 min, a soft chime
every 40–80 s (jittered) asks *on task / drifting?* Label the 15 s before each probe [V1][V2]. Same
posture and gaze target as real use, so eye position does not confound the labels.

**Feature gate.** Unit of analysis is one probe window, not 1 Hz samples, which are autocorrelated.
A naive "use it if |d| ≥ 0.5" is unsafe at these label counts. Reproduced independently [RUN]:

| Independent windows per class | Naive rule passes pure noise |
|---|---|
| 4 v 4 | 50% |
| 8 v 8 | 34% |
| 12 v 12 | 24% |
| 20 v 20 | 12% |

NeuroPace's rule: |d| ≥ 0.5 **and** permutation p ≤ .10, sign learned per wearer. At 12 v 8 windows it
passed noise 10.7% of the time and passed a true d ≈ 1.14 effect [RUN]. `neuropace_eval.py gate`.

**Judge answer to "how accurate?"** "Published detectors for this get about 0.65 AUC. Ours on this
wearer: here is the confusion matrix against 20 thought probes. That is exactly why two witnesses
have to agree before anything moves on your screen."

## I.10. `neuropace_eval.py` — verified [RUN]

Committed at the repo root and still the evaluation toolkit for Part II and III, unchanged.
`selftest` exits 0 and every number reproduces:

```
gate real : {'d': 1.137, 'p_perm': 0.0234, 'n_on': 12, 'n_lapse': 8, 'use': True, 'sign': 1}
gate null false-pass rate (12v8 windows, perm p<=.10 AND |d|>=.5): 0.107
detector  : {'tp': 14, 'fp': 4, 'fn': 1, 'tn': 21, 'n': 40, 'accuracy': 0.875,
             'majority_baseline': 0.625, 'p_vs_baseline': 0.0004, ...}
outcome   : {'n': 8, 'mean_diff': 0.191, 'ci95': [0.129, 0.249], 'p_perm': 0.0063}
SELFTEST PASS
```

Sound statistics: two-sample permutation on the gate, sign-flip paired permutation plus percentile
bootstrap on the outcome, exact binomial against the majority baseline on the detector. `numpy`
only, already in `requirements.txt`.

Two things to know rather than fix: the detector's `p_vs_baseline` estimates the majority rate from
the same data it tests (mildly anti-conservative, irrelevant at our effect sizes), and `rng` is
module-level with a fixed seed, so repeated calls in one process are not independent draws.

**It is committed before the data exists.** That ordering is the point, and it is what makes the
honesty claim credible on stage.

## I.11. Demo (90 s) — superseded by Part II §7's ~3 min script; kept for the original beats

1. (0–10) Headset on in ten seconds, fit meter fills on the totem, quality chip green. "This is
   NeuroPace. Responsive design for your brain. Three witnesses: brain, face, hands."
2. (10–40) Calibration: eyes closed, the alpha bar jumps, *that is your own alpha*. Then 20 s easy,
   20 s hard. Chip: *calibrated to you*.
3. (40–60) Dense Bayes paragraph. Brow furrows, scroll stalls, L rises. **The paragraph dissolves
   into an animated diagram.** Checkpoint; judge answers; state returns to FLOW.
4. (60–75) Easy, boring text. Gaze drifts, E drops. Prediction prompt, then the slider simulation.
5. (75–90) The playbook card, and the two numbers from I.9. Hold a textbook page to the camera and
   watch it become a lesson. "Learner-only. No teacher view. Undo on everything."

Keyboard control plane from hour one: `O` overload, `D` disengaged, `F` flow, `R` replay a recorded
session. The presenter can drive honestly if a fit is bad, and the UI says **simulated** when they
do. Judges forgive a flaky sensor. They do not forgive a faked one. This discipline (label
simulated states, never fake a sensor) carries through unchanged into Part II and III.

## I.12. Build schedule (hours from start) — superseded by Part II §8's stage table; kept as the detailed hour-by-hour reference

The original hour ranges predate A+ and are retained as the earlier baseline, not a promise
that the camera extension fits for free. A+ is part of the requested product direction; first
validate capture quality and end-to-end latency, then revise the schedule. Transcript-only mode
remains a labelled fallback, not completion of the whiteboard feature.

Roles: **S** signal and brain · **C** content engine and diagram · **U** reader UI, state, bandit ·
**H** camera, Arduino, study, pitch.

| Hrs | S | C | U | H |
|---|---|---|---|---|
| 0–1 | Pair headset, `run_pipeline.py` on a real forehead. **Gate: real blinks counted.** Confirm COM port | LLM → scene-graph JSON on one paragraph | Repo; reader renders from `--fake` feed (works today) | **Identify WiFi vs Minima. Ask organizers the I.13 questions.** Face Landmarker printing brow/gaze/pose |
| 1–4 | The brain: hysteresis, dwell, three-witness fusion on top of `FeatureFrame` | dagre layout + anime.js timeline; the dissolve | Lesson reader with units; state chip; **undo** | Totem sketch: fit meter, button, **pushbutton backup wired**; camera feature EMAs |
| 4–8 | Probe runner; `neuropace_eval.py gate` on real labels; tune thresholds on 5 strangers | Chunk, worked-example, simulation, voice transformations; cache 3 topics | Bandit + playbook; checkpoints | Webcam scan → vision model → units; **yoked random-timing control flag** |
| 8–12 | **Integration: live state drives neuropaces end to end.** Freeze features at 12 | | | |
| 12–16 | Recovery numbers from I.9 on 8–12 hackers | Live generation for arbitrary text | Session card, onboarding, polish | Shoot the video; novelty slide; submission text |
| 16–20 | Bug bash on recorded sessions; verify every fallback | | | Table setup: lighting, camera angle, monitor |
| 20–24 | No new features. Rehearse 10× with each teammate as judge. Fresh AAA. Sleep in shifts | | | |

**Kill rule (hour 6):** if clean EEG is not contributing to state, ship face plus behavior as the
two witnesses, label EEG experimental, and say so out loud. The transformations, the playbook and
the camera are the product. The headset is one input.

**Code rule.** HackMIT describes projects as built "from scratch" [V9]; the exact policy was not
found. `mindwave/` was written before the event, so **ask at hour 0 whether it may be used** and
disclose it either way. Keep visible commit history and disclose AI assistance.

## I.13. Risks and open questions

| Risk | Mitigation |
|---|---|
| Pre-written `mindwave/` disallowed | **Ask at hour 0.** Highest stakes item on the page |
| Bluetooth pairing flakiness | One owner, spare AAA, `--fake` and `ReplaySource` keep three people unblocked |
| EEG uninformative on a judge | Two-of-three witness rule means other signals carry it; quality gate; simulation mode, labelled |
| Heart pad needs a capacitor | Pushbutton backup wired in hour 1 |
| Board is a Minima, no matrix | Fit meter moves to `LED_BUILTIN` or the laptop; decide hour 0 |
| Judge does not overload on cue | Dense paragraph plus a timed question is a reliable inducer; cached diagram fires instantly |
| LLM latency or bad JSON | Cached topics; the dissolve masks 3–6 s; retry once; Mermaid fallback |
| Camera lighting at the table | Ring light; face thresholds recalibrate per person during the 60 s (only relevant if camera is revived, see Appendix A) |
| "Isn't this NeuroChat?" | I.2, said first, with their limitations quoted |
| "Classroom brain surveillance" | Learner-only, local, no teacher view, undo on every neuropace. Say it unprompted |
| We prove only that interventions help | The yoked random-timing control in I.9. Non-negotiable |

**Open, resolve at hour 0:** (1) pre-existing and AI-written code policy → organizers; (2) which R4
variant → look at the board; (3) judging format and rubric → organizers; (4) real-forehead
behaviour of I.5 → your headset; (5) sponsor challenge requirements → booths; (6) serial routing to
the R4 (I.8).

## I.14. Sponsor tracks — superseded by Part II §5 (updated for the pivot); kept for the full reasoning

Reviewing all 24 in `tracks.md`:

| Track | Call | Why |
|---|---|---|
| **Education** | commit | Core |
| **Long Lake** ("Convince a Non-Believer") | commit, zero build | A skeptic wears the headset for ten seconds and watches *their own* paragraph dissolve. This is the "one great experience" brief verbatim, and it is the best non-Education fit on the list |
| **OpenAI** | commit | Structured-output scene graphs, transformations, page scanning. Needs one concrete Codex story in the demo [U]. Submitting unlocks credits |
| **The Token Company** | **back on, add** | This answer flipped. With no hour-long transcription, the LLM *is* the main cost, and the architecture is already the saving: the state machine runs locally, the model fires only on a trigger, only the stuck unit is sent rather than the document, and demo topics are cached. That is a clean, creative cost story worth a paragraph |
| **ElevenLabs** | add if the voice rung ships | "Explain it back" aloud, with the agent probing and scoring, is retrieval practice [V11] and genuine agentic depth, not text-to-speech. Their brief explicitly deprioritises plain TTS, so only enter if this rung is real |
| **Ramp** ("save time and money") | add, zero-work | "Build anything that saves people time and money." Fewer re-reads per hour of study. Same video |
| **Dropbox** | stretch | Their brief literally lists "transform class materials into a personalized tutor". A PDF drop that becomes a neuropaceable lesson is a modest addition to the scan feature already planned. Only if hours 12–16 are calm |

**Out:** Arduino (the HackMIT challenge is for the **UNO Q** [V8]; an R4 arrived, so not eligible,
and the board stays because the product needs it). Deepgram (the lecture-transcription use left
with the quiz idea; only relevant if the voice rung needs ASR, and ElevenLabs covers that lane
better) — **note: Part II brings a lecture back into the product, which flips this call again, see
Part II §5.** ASUS, Espressif, Cognition only if hardware is handed over working. The other
thirteen are wrong-domain or board-locked.

**Commit to four, add three only if they cost nothing.** Each entry is a booth visit and a
rehearsal variant, and a long prize list reads as prize-farming to judges who have seen forty teams
that day.

## I.15. Sources (Part I numbering)

- [V1] Conrad & Newman 2021, Front. Hum. Neurosci. 15:697532 — frontiersin.org/articles/10.3389/fnhum.2021.697532/full
- [V2] Dhindsa et al. 2019, PLOS ONE 14(9):e0222276 — journals.plos.org/plosone/article?id=10.1371/journal.pone.0222276
- [V3] Szafir & Mutlu 2012, CHI — cs.usfca.edu/~byuksel/affectivecomputing/readings/papers5/szafir2012.pdf. NeuroSky Mindset at FP1, E = β/(α+θ), baseline from 3 min, 15 s windows, n=30. **Adaptive beat no-cue (p=.022) but not random-timing (p=.118)**
- [V4] "EEG complexity measures for detecting mind wandering during video-based learning", Sci. Rep. 2024 — nature.com/articles/s41598-024-58889-9 (abstract). Mean AUC 0.646
- [V5] NeuroChat, ACM CUI '25 — arxiv.org/abs/2503.07599 ; media.mit.edu/publications/neurochat-acm-cui2025. Muse 2, 4 ch, E = β/(α+θ), 15 s window, two-point calibration, score injected into the next prompt. §6.2 is our roadmap
- [V8] github.com/jimbruges/hack-mit-arduino-resources ("HackMIT 2026 … Arduino UNO Q challenge")
- [V9] hackmit.org (event description)
- [V10] ARTFul, CHI 2013 — peopleandrobots.wisc.edu/publications/artful-adaptive-review-technology-for-flipped-learning-inproceedings. Attention-selected review, +29% recall, same gain in less time
- [V11] APS Observer, "Test-Enhanced Learning" (61% vs 40% at a week); Roediger & Karpicke 2006 (restudy wins at 5 min, so do not demo a retention win the same night)
- [V12] Smilek et al. 2010 via APS/ScienceDaily — sciencedaily.com/releases/2010/04/100429153959.htm. Blink rate rises with mind-wandering
- [V13] NeuroSky eSense docs — developer.neurosky.com/docs/doku.php?id=esenses_tm (0–100, 40–60 "neutral", proprietary, "slow-adaptive")
- [V14] NeuroSky eSense white paper — frontiernerds.com/files/neurosky-e-sense-white-paper.pdf (beta/gamma weighting, algorithm undisclosed)
- [V15] github.com/arduino-libraries/Arduino_CapacitiveTouch (supported pins incl. `LOVE_BUTTON`; no external parts mentioned)
- [V16] github.com/delta-G/LoveButton ("requires … a small capacitor … between pin 10 and ground on the … Minima or between pin 7 and ground on the … WiFi")
- [V17] ThinkGear serial protocol — developer.neurosky.com/docs/doku.php?id=thinkgear_communications_protocol (data codes, band ranges, blink strength unavailable over serial)
- [V18] MediaPipe Face Landmarker — developers.google.com/mediapipe/solutions/vision/face_landmarker/web_js (478 landmarks, 52 blendshapes, 4×4 pose matrix)

---

# Part II — the product pivot

### It notices where the lecture lost you, writes notes for exactly that, and re-teaches it until it lands.
**NeuroSky MindWave Mobile 2 + Arduino UNO R4**

## II.1. Evaluation of the combined idea

| Part | Verdict | Why |
|---|---|---|
| Notes for the moments you lost focus in a lecture | **Keep** | A lapse you didn't notice can't be bookmarked; mind-wandering in lectures goes with lower learning [V1]. Notes *only where you lapsed* is the differentiator; whole-lecture notes are a commodity |
| Review that re-teaches each gap, adapting as you go | **Keep** | Attention-selected review improved recall 29% and matched full review in less time [V10]; brain-adaptive changes at unit boundaries improved learning [V16] |
| "Your learning style, as evidenced by EEG" | **Change the claim, keep the mechanism** | Two problems, below |

**Problem 1: the literature.** Matching instruction to a learner's style has no empirical support
across decades of studies, including a powered 2024 test (N=222) [V13]. Pitching "we detect your
learning style" at MIT invites the word *neuromyth*.

**Problem 2: the sensor.** In simulation, EEG at realistic accuracy identifies the better of four
explanation formats 34–45% of the time (chance 25%); quiz answers reach 94% in 150 cards, and
adding EEG to them makes it worse [RUN].

**The version that survives both:** NeuroPace does not assume you have a style. In review, each gap is
taught in one form; if your focus drops or you miss the check question, the next card re-teaches it
in a different form. NeuroPace keeps a **per-learner tally of which form rescued which misses, scored
by quiz answers only.** If you truly have a preference (75% vs 55%), the tally finds it with 77%
probability after 60 cards and 94% after 150; if you have none, it costs nothing (success rate
0.601 vs 0.60) [RUN]. At ~10 gaps a lecture that is a few weeks of real use. Pitch line: *"We don't
believe in learning styles. We test it on you, and show you the data."* That is more original than
claiming styles exist, and it is defensible.

**What EEG does in each phase**

| Phase | EEG's job | What decides |
|---|---|---|
| Lecture | Marks *when* you drifted, including lapses you never noticed | EEG + heart pad flag spans; a wrong flag costs one unneeded note |
| Review | Soft trigger to switch form at the next card boundary | The check question decides whether a form worked |
| Across learners | Pooled drops show *where the lecture* lost people | Averaging: 12 learners find a planted bad segment about 60–85% of the time with fused signals, 40–60% EEG alone (chance 20%) [RUN]; fused accuracy is an ASSUMPTION |

**Scope check.** This is one pipeline, not two products: the review player's cards are simply the
gap spans from the lecture. The risk is time, so the build order in II.8 produces a complete demo
at every stage.

## II.2. The product

1. **In the lecture.** Headset on, totem on the desk, laptop ignored. Deepgram transcribes with
   word timestamps; a teacher/board-facing webcam supplies timestamped whiteboard frames.
   Focus drops (relative to your own first 3 minutes) and dedicated Arduino button presses mark
   spans, with an 8 s lead-in. A button press requests a private explanation using the matching
   transcript and board images (II.2.1). EEG flags offer an optional catch-up; they do not claim
   to diagnose confusion. Keep output private as required by Part III §2.
2. **Gap notes.** When the lecture ends you get notes for your flagged spans only: what was said,
   the key term, how it connects to the part you did hear. Grounded in the transcript and available timestamped board images, with source references.
   Missing or unreadable board content is disclosed, not invented.
3. **Adaptive review.** One card per gap, check question first. Miss it, or lose focus on the card
   → the same idea re-taught in another form: worked example → analogy → animated diagram. The
   text-to-diagram "dissolve" (Part I §7) lives here. Stop after three straight hits.
4. **Your tally.** A small panel: forms tried, rescues per form, and an honest "not enough data
   yet" until there is.
5. **Lecture loss map** (when several learners took the same lecture): the 40 seconds where the
   room was lost. Aggregate and anonymous; it grades the lecture, never a student.

**Prior art, said first:** NeuroChat restyles every reply and found no learning gain [V5]; ARTFul
picks topics to re-show from pre-authored content [V10]; Wang et al. detect confusing clips
offline [V14]; AXIS picks explanations from ratings, no sensing [V17]. NeuroPace: passive lapse
capture in live lectures → generated gap notes → re-teaching verified by recall.

### II.2.1. Button-triggered explanations from voice and whiteboard (prototype)

**Input and ownership.** The current target is Arduino UNO Q 4 GB. Its MCU reads the button,
and its Linux side runs the unchanged MindWave pipeline from a Bluetooth-paired headset and
relays feature frames and button events over BLE. The laptop captures webcam frames and
microphone audio. The prototype and bring-up gates are documented in `firmware/uno_q_relay/README.md`.
Direct laptop EEG and the older USB totem remain explicit fallback routes. The camera faces the teaching area, not the learner. A webcam's
built-in microphone can capture the teacher's voice; use a separate microphone if speech is not
clear enough. Audio transcription and image capture are separate streams synchronized to one
session clock. The Arduino does not process audio, images, or LLM requests.

**On a press:**

1. Debounce the physical switch and send one event per press with an event ID. Acknowledge the
   press immediately in the learner's private UI and save its session timestamp. Preserve the
   existing `tap` event semantics so manual flags still feed notes, replay, and evaluation.
2. Select the relevant transcript span and board frames from a rolling buffer. Retain the
   existing 8-second flag lead-in; use a wider preceding context window for explanation, initially
   60 seconds, so "this arrow" or "the second term" can refer to an earlier drawing. If an EEG
   span already exists, associate the request with that span rather than creating duplicate gaps.
3. Send the transcript plus a small set of timestamped board images to a multimodal LLM. Include
   the latest readable frame at or before the press and earlier changed frames, so an erased
   equation can still be referenced. Never use future lecture content for a live explanation.
4. Return a short explanation of the selected passage, connecting spoken references to visible
   equations, labels, and arrows. Attach transcript timestamps and image IDs. Distinguish what
   the teacher said or drew from an added worked example; do not infer illegible symbols as fact.
5. Show a quiet, static catch-up on the learner's screen. Make the fuller explanation and board
   excerpt available on demand and in gap notes. A later check question decides whether the
   explanation helped; neither EEG nor the button establishes correctness or a learning style.

**Latency and failures.** A press saves the moment immediately, without waiting for generation.
Use an available cached transcript recap while the multimodal explanation is pending, labelled
"Transcript recap; board explanation loading". Do not replace text mid-reading: offer the completed
explanation for the learner to open. If camera access is denied, the board is obscured, or image
processing fails, say "Transcript only; board unavailable". If transcription is incomplete,
identify that limitation too. On model failure, preserve the saved moment and the existing labelled
offline recap. Do not promise sub-second fresh multimodal generation.

**Initial engineering assumptions, not measured claims.** Try one board frame every 2 seconds,
a 90-second local rolling image buffer, and at most 4 distinct frames per request. These are tuning
starting points, not requirements supported by a run. Keep stable frame IDs, capture timestamps,
transcript word timestamps, source availability, and generation provenance on each request. Bound
image size, queue length, and request frequency; coalesce repeated presses without losing saved
moments. Check whiteboard readability at the actual distance before committing to this camera.

**Verification gate.** Use synthetic lesson content recorded by consenting adult teammates. Cover
an equation referenced as "this term", an erased diagram, an obscured board, microphone/camera
denial, slow or failed generation, repeated presses, and a press overlapping an EEG flag. Verify
frame/transcript alignment and source citations, and measure press acknowledgement and explanation
latency separately. Compare transcript-only versus transcript-plus-board explanations on questions
that require the drawing. Treat this as a separate content-grounding evaluation; any outcome claim
about sensor timing must still use the yoked random-timing control from Part I §9. No new accuracy
or learning-benefit claim is [RUN] until a reproducing script has actually been executed.

## II.3. Signal engine

**Hardware facts [U].** One dry electrode at Fp1, 512 Hz raw; blink strength not in the serial
stream; R4 radio is BLE-only, headset is Bluetooth Classic, so headset → laptop → R4 over USB.

- **Focus index** E = β/(α+θ), exponentially smoothed, judged against the wearer's own first 3
  minutes of listening, in 15 s windows. Same scheme, same electrode site as Szafir & Mutlu's
  NeuroSky study [V3]; direction agrees with lecture studies (theta up, beta down during
  mind-wandering) [V1][V2].
- Reject segments with outlier peak-to-peak before the FFT (blinks land in theta at Fp1). Gate on
  the poor-signal byte. z-score per learner before pooling.
- Realistic accuracy: about 0.65 AUC for band-power mind-wandering detection [V4]; weak-but-above-
  chance for confusion on this headset class [V14][V15]. Every use above is chosen so a wrong flag
  is cheap.
- **Hour-0 check without hardware:** run your feature code on the public Wang et al. Kaggle data,
  split by subject and video. Distrust anything above ~75%.

This reuses the exact feature math already built in `mindwave/features.py` (Part I §5); nothing new
to implement here beyond the 15 s windowing against a per-learner 3-minute baseline instead of a
calibration task.

## II.4. Physical input hub (UNO Q 4 GB; earlier UNO R4 route retained)

The primary manual input is a **dedicated momentary pushbutton labelled "I'm stuck"**, connected
to an appropriate UNO Q MCU digital input and ground with a pull-up configuration. Confirm the exact
board and wiring before implementation. Firmware debounces the switch and emits one button count increment per press; the Q Linux relay forwards each increment as a BLE
`tap` event to the laptop. A capacitive foil/heart pad is an optional alternative, not a
required part. Both request the same catch-up and save the same kind of flagged moment.

The target pairs the headset to the UNO Q Linux side and runs the existing MindWave pipeline
there. The current direct-laptop connection is retained for bring-up and fallback. The webcam and microphone also connect to the laptop. Hardware failure must not stop
capture: retain the on-screen/keyboard input, explicitly labelled simulated, and label simulated
EEG separately. Default acknowledgement and catch-up output are private; do not expose learner
struggles through desk LEDs. The original board/sponsor discussion remains in Part I §8.

## II.5. Tracks

Education · **Deepgram** (native again: word timestamps turn a moment into a transcript span) [U] ·
**OpenAI** (notes, check questions, re-teach forms as structured output; one Codex story) [U] ·
Long Lake as pitch framing [U]. Nothing else. This revises Part I §14's Deepgram call: a real
lecture transcript is now core to the product, not just a stretch tied to a voice rung.

## II.6. The measurement: one study, three numbers

One recorded 8-min lecture, 5 segments, **segment 3 deliberately bad** (jargon, no example). 15
quiz items written beforehand. 10–12 hackers, ~20 min each: fit, watch with headset + pad, gap
notes, adaptive review, final quiz.

| Number | Claim it tests | Tool / power |
|---|---|---|
| Recall on flagged vs unflagged spans, before review | The flags mean something | `neuropace_eval.py outcome`; n=10 gives ~72% power for a 25-point gap, n=6 only 22% [RUN] |
| Does the pooled loss map rank segment 3 first? | The crowd signal finds bad teaching; ground truth known | `lossmap_sim.py` for expectations |
| Rescues per form in review | Descriptive only at this n; say so | tally panel |

Don't compare question-first vs re-reading tonight: restudy wins at short delays [V11]. Report
every number with its interval, including nulls.

## II.7. Demo (~3 min; format is an open question) — current

1. (0–20 s) Pitch. Name NeuroChat. "We don't believe in learning styles; we test it on you."
2. (20–70 s) Show a consenting teammate teaching a synthetic lesson with a whiteboard. Press the
   real Arduino button; show the saved moment, matching board image and transcript, and the
   private explanation. Show EEG as the independent passive timing source. Use a labelled replay
   if live classroom capture is unavailable; never present prerecorded generation as live.
3. (70–130 s) That learner's gap notes, then live review: judge answers a card, misses or taps the
   pad → dissolve into the diagram form → hit.
4. (130–170 s) Loss map from your study with the planted segment revealed; the flagged-vs-unflagged
   number.
5. (170–180 s) "Learner-owned data. The only shared view grades the lecture."

Say "simulated" aloud if a forced trigger is ever used.

## II.8. Build order (each stage is a complete demo) — current

| Stage | Hrs | Deliverable |
|---|---|---|
| A | 0–4 | Dedicated Arduino button → transcript span → gap note → check question. **Gate at hr 1: real blinks on a real forehead** |
| A+ | Re-estimate before build | Webcam + microphone capture → synchronized board frames/transcript → button-triggered multimodal explanation; source references, private display, explicit fallbacks |
| B | 4–6 | Focus index as a second flag source; live trace |
| C | 6–8 | Review player: miss or drop → re-teach in next form; dissolve; tally |
| D | 8–12 | Study (II.6) + loss map. **Freeze at 12** |
| — | 12–end | Replay recording, slides, rehearsal, fresh AAA, sleep in shifts |

The original hour ranges predate A+ and are retained as the earlier baseline, not a promise
that the camera extension fits for free. A+ is part of the requested product direction; first
validate capture quality and end-to-end latency, then revise the schedule. Transcript-only mode
remains a labelled fallback, not completion of the whiteboard feature.

Roles: **S** signal · **A** Deepgram + LLM · **U** UI · **H** totem, lecture recording with planted
flaw, recruiting.

**Kill rule (hr 5):** no usable EEG → everything runs on pad + quiz; EEG shown as experimental
overlay.

**Code rule:** HackMIT says projects are built "from scratch" [V9]; exact policy not found. Code
in-event, visible commits, disclose AI help, ask about anything written earlier.

**Part III adds** content-based transcript risk-flagging as a third source into Stage B/C (Tier 1,
same-afternoon build — see Part III §6), and a 3–4 field accommodation-profile config into Stage C
or a later dashboard pass (Tier 2).

## II.9. Verified vs open

**Ran today:** `bandit_sim.py`, `lossmap_sim.py`, `neuropace_eval.py selftest`, per-learner tally null
check.
**Open:** whiteboard capture readability, audio quality, multimodal grounding, latency/cost,
retention controls, and synchronization (II.2.1, all unverified); HackMIT code rule; judging format; real-forehead performance; Deepgram/OpenAI challenge
requirements; fused-signal AUC 0.76 and the 60–90% "bad segment loses learners" range are
ASSUMPTIONS; simulations assume independent noise across learners; everything tagged [U].

## II.10. Sources (Part II numbering — note some V-numbers are reused across parts for the *same*
source, but V13, V14, V15, V16, V17 here refer to *different* sources than the same numbers in
Part I; don't cross-reference by number alone)

- [V1] Conrad & Newman 2021 — frontiersin.org/articles/10.3389/fnhum.2021.697532/full
- [V2] Dhindsa et al. 2019 — journals.plos.org/plosone/article?id=10.1371/journal.pone.0222276
- [V3] Szafir & Mutlu, CHI 2012 — cs.usfca.edu/~byuksel/affectivecomputing/readings/papers5/szafir2012.pdf
- [V4] Sci. Rep. 2024, mind-wandering in video learning — nature.com/articles/s41598-024-58889-9
- [V5] NeuroChat — arxiv.org/abs/2503.07599
- [V8] github.com/jimbruges/hack-mit-arduino-resources
- [V9] hackmit.org
- [V10] ARTFul — peopleandrobots.wisc.edu/publications/artful-adaptive-review-technology-for-flipped-learning-inproceedings
- [V11] Roediger & Karpicke 2006 abstract; APS Observer "Test-Enhanced Learning"
- [V13] Pashler et al. PSPI — bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/07/Pashler_McDaniel_Rohrer_Bjork_2009_PSPI.pdf ; 10.3389/fpsyg.2018.01538 ; 10.1007/s11251-024-09689-1
- [V14] Wang et al. 2013 — people.csail.mit.edu/zp/moocshop2013/paper_8.pdf
- [V15] arXiv 2607.01795
- [V16] BACh, CHI 2016 — cs.usfca.edu/~byuksel/yukselCHI2016.pdf
- [V17] AXIS, L@S 2016 — kgajos.seas.harvard.edu/papers/williams16axis.pdf

---

# Part III — special education pivot

### What changes if this is built for students who don't (or can't) speak up when they're lost
**Addendum to Part II**

## III.0. A scope assumption, stated up front

"Special ed kids who have learning disabilities, who can't speak up for themselves" covers a wide
range, and the right design differs a lot depending on which end of it you mean. This addendum
assumes the largest, most common group in an **inclusion classroom**: students with diagnosed
learning disabilities (dyslexia, ADHD, auditory processing disorder, working-memory-related LD) who
are verbal and could, in principle, ask a question — but often don't, for reasons documented below
that have nothing to do with willingness. That's different from designing for non-verbal or
minimally-verbal AAC users (augmentative and alternative communication), which is a real and
important population but needs a different input mechanism entirely (switch access, AAC-device
integration) and isn't a good fit for a two-day build. If a different population was meant, this
addendum needs a rewrite, not a patch. Everything below assumes the inclusion-classroom LD
population.

## III.1. The problem this pivot actually surfaces

Part II's trigger design was EEG (passive) **or** a capacitive pad tap (active, self-reported). For
a general audience that's a reasonable pair. For this population, both legs are weaker than they
look, for two different reasons:

**The EEG leg detects the wrong failure mode for a lot of these students.** The focus index in
Parts I/II (beta/theta ratio) was built and validated in the literature it cites for
*mind-wandering* — attention leaving the room entirely. But a student with dyslexia struggling to
decode unfamiliar vocabulary in real time, or a student with auditory processing disorder losing
the thread of a multi-clause sentence, is often still looking at the teacher, still trying, still
"on task" by any observable or EEG-visible measure — and still not understanding. That's a
comprehension failure *without* disengagement, and it's arguably the more common failure mode for
exactly this population. An EEG signal tuned to catch wandering attention will systematically
under-flag it.

**The button leg depends on the exact skill this population is described as lacking.** "Can't speak
up for themselves" isn't just a turn of phrase — it's a documented pattern. Students with learning
disabilities are less likely to ask questions or request help in class specifically because of
limited confidence and fear of being seen as "stupid" or a "trouble-maker," and self-advocacy
(knowing what to ask for and being willing to ask for it) is something special education explicitly
has to teach as a separate skill, not something these students arrive with [V23]. A nonverbal
button tap lowers the bar versus raising your hand, but it's still an active, visible, self-
initiated signal — and the visibility part matters here specifically, see III.3.

Put together: the two mechanisms Part II already has are each weakest at the point where this
population needs them most. That's worth saying in the pitch, the same way Part I said it about
learning styles and Part II said it about screen time — not as a reason to abandon the idea, but
because building on top of an unstated weak spot is how these tools end up quietly failing the
people they're pitched to help.

## III.2. What actually helps, given that

**Add a trigger that doesn't depend on the student's own state at all.** Alongside EEG and the pad,
flag spans of the transcript that are *intrinsically* likely to cause a comprehension gap,
independent of whether the student shows any physiological or behavioral sign: new-vocabulary
density against a running glossary, sentence complexity, and speaking rate relative to the
lecture's own baseline. This is pure NLP on the Deepgram transcript — no new hardware, no new
signal to validate on real foreheads, and it directly targets the "still attending, still failing"
case the EEG leg misses. For a student with a documented processing profile, these spans can be
surfaced automatically rather than waiting on a signal the student has to produce. This is
genuinely cheap to build (a word-frequency list and a readability-style score are both
same-afternoon work) and it's the single highest-leverage addition this pivot suggests — it belongs
in Tier 1, not the stretch tier.

**Make the in-lecture output private, not a lit-up totem.** Part II's LED matrix flashed a dot that
anyone nearby could see change. For a general audience that's a minor design detail; for this
population it's a direct hit on the exact mechanism that makes self-advocacy hard — being visibly
marked as struggling in front of peers is precisely what the literature says drives students to
hide their difficulties and avoid help-seeking rather than use it [V23]. It's also the single
most-cited reason assistive technology gets abandoned once students have it: not that it doesn't
work, but that using it visibly announces a disability, and the social cost outweighs the benefit
for a lot of students who never told their peers they have an LD in the first place [V24]. Route
the totem's in-lecture output (Part II §2 step 1) to something only the student can see or feel — a
phone screen face-down until glanced at, a discreet vibration, not a matrix that lights up on the
desk.

**Keep the multi-form re-teach mechanic — it's already the right idea.** Parts I/II's "worked
example → analogy → diagram, cycle until it lands" is, without having been framed this way, already
the core move of Universal Design for Learning: offering the same content through more than one
means of representation, on the logic that no single format works for every learner and the fix is
to design for that variability up front rather than retrofit it later [V21]. Nothing needs to change
here — it's worth naming explicitly in the pitch, because it means this pivot isn't inventing new
pedagogy, it's pointing an already-sound mechanism at a population that needs it more.

**Make the accommodation profile configurable, not fixed.** Special education already works this
way — accommodations are individualized per IEP, not one-size-fits-all. Let alert modality (visual /
haptic / short audio), trigger sensitivity, and pad placement be settings, not defaults baked into
the build. For the hackathon, a config object with three or four fields is enough to demonstrate the
idea without engineering per-student calibration.

## III.3. Pitch it as available to everyone, not issued to "the special ed kid"

This follows directly from III.2's stigma point but deserves its own line because it's a framing
decision, not just a hardware one. The same research that explains why visible AT gets abandoned
also points at the fix: when a tool is something any student could plausibly be using — the way
headphones now double as an assistive-listening device without anyone assuming the wearer has a
diagnosis — the stigma drops, because nobody nearby can tell who's using it for what [V24]. Pitching
NeuroPace as "the device for kids with learning disabilities" recreates exactly the visibility problem
you're trying to solve. Pitching it as a study tool any student in the room could opt into, with
accommodation profiles underneath for students who need them, gets you the same accessibility
benefit without singling anyone out. This is a five-minute framing change for the pitch, not a build
item — but it's the kind of thing that's much easier to get right before the deck is finished than
after.

## III.4. What not to claim

**Don't claim it detects or diagnoses a learning disability.** It doesn't, and a single dry-
electrode consumer headset at the accuracy Part I already established (0.65 AUC for mind-wandering
detection, I.9) isn't close to a diagnostic instrument. The tool's job is noticing a moment of
difficulty for a student who is already identified and already has accommodations in place, not
identifying who has an LD.

**Don't claim it replaces accommodations or IEP services.** It's a study aid. A progress log of
which topics generated gaps and how they were resolved could be a genuinely useful thing for a
student or parent to bring to an IEP meeting as one data point — but that's different from claiming
the tool tracks IEP goals, and the pitch shouldn't blur the two. Special-education progress
monitoring is a formal, legally-structured process; this is informal support that might inform a
conversation within it.

**Say the accuracy caveat out loud, and say why it matters more here.** Part I was honest that a
wrong EEG flag "costs one unneeded note." For this population, the more consequential error is the
other direction — a real gap that the system doesn't catch, in a student who was also the least
likely to flag it themselves. If the pitch implies broader coverage than the tech delivers, the risk
isn't just an inflated demo — a teacher or aide who trusts the device to catch what they'd otherwise
have watched for themselves is a real form of automation complacency, and for a student with limited
self-advocacy, that's the one time the human backstop mattered most.

## III.5. Data handling, if this ever touches real students

If this moves past a hackathon demo with consenting adult testers, it moves into territory with real
legal weight. Special-education records — including anything that documents a student's disability-
related difficulties — are protected under IDEA in addition to the general protections FERPA already
gives all student education records, and disclosure requires parental consent outside specific
exceptions [V25]. That means the account/storage layer, if it's ever populated with a real minor's
actual gap history, needs access controls designed in from the start (who can see a given student's
data, parental consent on file, no default public or classmate-visible view) rather than bolted on
after a general-purpose note-taking product already exists. For the hackathon: keep the demo data
synthetic or from consenting adult teammates, and say in the pitch that you know this is the next
real engineering item, not an afterthought.

**Camera/audio extension, planned product requirements.** Before capture, explain which camera
and microphone are active, what is saved, and whether selected transcript/images will be sent to
an external model provider. Obtain agreement from the teacher and any recorded participants for
the demo. Frame/crop to the board, avoid audience faces, and show a persistent recording indicator
with pause/stop controls. Do not perform face recognition, gaze tracking, or learner emotion
inference. These are product requirements, not a statement of legal compliance.

Keep the rolling image buffer local and ephemeral; discard unselected frames as they age out.
Save only the selected board excerpts and transcript spans needed for learner-owned notes, with
an explicit session retention setting and delete action. Do not retain raw audio by default after
transcription. Document external-provider retention before enabling upload; do not imply local
processing when sending content off-device. Demo lessons remain synthetic. Classroom deployment,
especially with minors, requires a separately scoped consent and access-control implementation.

## III.6. Build order — what this adds to Part II's stages

| Tier | Addition | Why here |
|---|---|---|
| **1 — must ship** | Content-based risk flagging (vocabulary/complexity/rate heuristics on the transcript) as a third trigger source, independent of EEG and the pad | Cheap (transcript-only, no new hardware), and it's the direct fix for the failure mode III.1 identifies — arguably stronger evidence for the demo than the EEG story alone |
| **1 — must ship** | Route the in-lecture output to a private surface (phone, not a visible totem) | This is a UI routing decision on infrastructure Part II already has; no new build, just a different default |
| **2 — dashboard MVP** | A 3–4 field accommodation-profile config (alert modality, sensitivity) | Small addition to whatever settings surface the dashboard already needs |
| **out of scope for this hackathon** | AAC/switch-access input, formal IEP-goal integration, real access-control/consent infrastructure for minors' data | Each of these is a real, separate build with its own requirements-gathering (ideally with actual special-ed teachers and students) — naming them as roadmap is more honest than a shallow version in the two days you have |

## III.7. Sources opened for this pivot (Part III numbering)

- [V21] *(carried over)* CAST evidence base on Universal Design for Learning and multiple means of representation — udlguidelines.cast.org/representation/comprehension/background-knowledge/background-knowledge-research
- [V23] Barriers to self-advocacy in students with learning disabilities — LD@School, *Self-Advocacy* — ldatschool.ca/wp-content/uploads/2014/06/Self-Advocacy.pdf; Manitoba Dept. of Education, *Supporting Self-Advocacy*, Module 7 — edu.gov.mb.ca/k12/docs/support/learn_disabilities/module7.pdf
- [V24] Stigma as the primary driver of assistive-technology abandonment among students with (often invisible) learning disabilities — Fennell, *Technology and Disability Identity: "Now You See Me, Now You Don't"* (2016 PhD thesis) — yorkspace.library.yorku.ca/items/b1e1cb67-e567-4c97-ac71-3ab76ecc5328; on ubiquitous consumer tech lowering AT visibility/stigma — adlit.org/ask-the-experts/todd-cunningham/stigma-and-assistive-technology
- [V25] FERPA and IDEA privacy protections for special-education records — U.S. Dept. of Education guidance via ferpa.education.arizona.edu/node/63 (IDEA Part B, 34 CFR 300.560–300.577, incorporates and cross-references FERPA)

---

## Appendix A: ideas explored and set aside (not disproven — kept in case they're worth reviving)

- **Real-time, mid-sentence neuropace while reading** (Part I's core mechanic). Set aside in Part II
  because a single dry electrode can't reliably tell *why* someone is stuck closely enough to pick
  an intervention live; moving the format-adaptation into a review phase, gated by a check
  question, is more defensible with the sensor actually available. Revive if the project moves
  toward a browser-reading-companion product rather than a lecture-companion product.
- **Camera as a third witness** (Part I §5, MediaPipe Face Landmarker). Still excluded; the
  restored teacher/whiteboard camera in II.2.1 supplies lesson content, not learner-state signals.
  Originally dropped from Part II for
  build-time scope, not because the signal is bad — brow furrow and gaze-off-screen are reasonable
  overload/disengagement cues. Would restore a two-of-three fusion rule instead of Part II's
  two-source (EEG + pad) rule.
- **"Scan a textbook page" camera input** (Part I §7). Dropped alongside the camera track. Directly
  overlaps with the Dropbox sponsor track's "transform class materials into a personalized tutor"
  brief (Part I §14) if revived.
- **"Detects your learning style" framing.** Explicitly retracted in Part II §1 for lack of
  empirical support in the literature — do not bring this framing back even informally in pitch
  language.

---

## Appendix B: technical reference (moved from README, 20 Sep 2026)

README.md is now the consumer-facing front door. Everything below is the operational detail a
contributor needs — setup, keys, hardware, platform notes, commands — moved here so the README
stays about what the product does, not how to run it.

### Quick start

```bash
# backend (Python 3.13 via uv)
uv sync
git-crypt unlock ~/Downloads/neuropace.git-crypt.key   # team key decrypts .env + .env.tts (see "API keys")
uv run neuropace doctor            # keys, services, serial ports, frontend build

# frontend (built once, served by the backend)
cd frontend && pnpm install && pnpm build && cd ..

# run everything in one process
uv run neuropace serve             # http://127.0.0.1:8765
```

Open the URL, pick the demo lecture ("How GPS finds you", scripted, with a planted bad segment 3),
start a live session with headset `sim` (the totem falls back to the keyboard when no Arduino is
plugged in), and press Space or `T` to tap. Press `1`/`2` to switch the simulated headset between
focused and drifting and watch the EEG flag arrive as a chip and a totem pulse.

The dashboard's **Show sample data** switch opens an isolated synthetic workspace with three past
lectures, review concepts, activity, and syllabus progress. Switching it off returns to the learner's original data.
Its database (`data/neuropace-demo.db`) and switch state (`data/demo-mode.json`) are local runtime
files covered by `.gitignore`.

Frontend development with hot reload: `cd frontend && pnpm dev` (proxies `/api`, `/ws`, `/media`
to the backend on 8765).

### API keys

`.env` (Deepgram, OpenRouter, OpenAI, Gemini) and `.env.tts` (Deepgram TTS voice) are
committed, but encrypted with [git-crypt](https://github.com/AGWA/git-crypt): the repo is
public and both files are unreadable without the team key. Approved collaborators receive
`neuropace.git-crypt.key` by direct message from Joaquin. Never commit, upload or post that
file anywhere.

```bash
brew install git-crypt        # Windows: scoop install git-crypt (or use WSL); Linux: apt install git-crypt
git pull
git-crypt unlock ~/Downloads/neuropace.git-crypt.key
uv run neuropace doctor       # confirms the keys are picked up
```

After `unlock`, both files are plaintext on disk and stay encrypted in every commit, so
editing `.env` and pushing is how the team adds or rotates a key. Real environment variables
win over `.env`, so keep personal overrides (`NEUROPACE_BASELINE_SECONDS=30`, serial ports)
in your shell rather than in the shared file. `git-crypt status` lists what is encrypted.

Without the team key, ask an approved collaborator for access. Do not replace the tracked
encrypted files with plaintext or bypass encryption. A configured language-model provider
is required to start a session; live transcription and narration also require their provider keys.

#### Entering a Deepgram key in the app

Open **Start session → Lecture transcription**, paste your Deepgram API key, and
choose **Save key**. It applies to new sessions immediately. The key is held only
in the local backend process and must be entered again after restarting it. Saving
does not validate the key with Deepgram; authentication happens when transcription
connects. For configuration that survives restarts, set `DEEPGRAM_API_KEY` in `.env`,
which is git-crypt encrypted in the repo (see "API keys" above).

#### Choosing OpenAI or OpenRouter

Open **Start session → Explanation model**. Choose OpenAI or OpenRouter, enter a
model name and that provider's API key, then save. Both keys can remain available
in the running local server, so switching back does not require pasting the key
again. The change applies to new sessions. For setup that survives restarts, use
`OPENAI_API_KEY` and `OPENAI_MODEL`, or `OPENROUTER_API_KEY` and
`OPENROUTER_MODEL`, then set `NEUROPACE_LLM_PROVIDER` to `openai` or `openrouter`.

### Hosted interface

The frontend is deployed at https://neurospace-hackmit.vercel.app. On the same laptop as your
browser and hardware, run `uv run neuropace serve` and paste the printed pairing code into the
hosted connection screen. Allow local network access when prompted. Restart an older backend
to load the hosted-interface changes. The local URL remains available as a fallback.

The frontend deploys from `frontend/` with `vercel --prod`; only frontend files are uploaded.
`NEUROPACE_UI_ORIGINS` configures exact allowed origins on the backend. Add preview URLs explicitly
when testing them. `VITE_BACKEND_URL` can override the default `http://127.0.0.1:8765` at build
time. Never put API keys or pairing codes in Vite environment variables. For hosted pairing,
use `neuropace serve` without `--reload` so the terminal prints the current pairing code.

The hosted site requires the local service. It does not provide a cloud backend or a remote
connection to someone else's laptop. EEG processing and session storage stay local; configured
transcription and explanation providers still receive the inputs needed for their requests.

### Hardware

- **Headset:** pair the MindWave Mobile 2 over Bluetooth Classic. It appears as `/dev/cu.MindWaveMobile-SerialPort` (or similar; COM3 on Windows) and is auto-detected; the team's `mindwave/` pipeline reads it (see the EEG bridge section). Force a port with `NEUROPACE_HEADSET_PORT`, or `NEUROPACE_HEADSET_PORT=sim` to simulate.
- **Totem (current target):** the UNO Q 4 GB relay in `firmware/uno_q_relay/` is the target path: the headset and a momentary switch connect to the Q, which relays both to the laptop over BLE. It is **experimental and uncompiled**; the concrete hardware blockers are listed in `firmware/uno_q_relay/README.md`. The physical button is **not built yet** — a momentary switch under a larger 3D-printed press surface is planned. Direct + simulated routes below stay labelled fallbacks.
- **Totem:** optional. Without an Arduino the totem falls back to the keyboard: Space or T in the browser, the on-screen "Catch me up" pad, or Space/T in the terminal running `neuropace serve`. Key taps are real learner actions (flag source `key`), not simulations; plugging the Arduino in mid-session switches to it automatically. To use the pad, flash `firmware/totem/totem.ino` to an UNO R4 WiFi (or Minima) with `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/totem && arduino-cli upload -p /dev/cu.usbmodemXXXX --fqbn arduino:renesas_uno:unor4wifi firmware/totem`. Jumper D2 to a foil pad. The board is auto-detected on `usbmodem*`; `NEUROPACE_TOTEM_PORT=keyboard` forces the keyboard fallback. If capacitive touch misbehaves, set `USE_CAPTOUCH 0` in the sketch and wire a pushbutton between D2 and GND.

- **Hour-1 gate:** with the headset on a real forehead the live view must show blink ticks on the trace. If it does not, the raw stream is not real; fix pairing before anything else.

### EEG bridge (`mindwave/`)

The headset front end is the team's standalone `mindwave/` pipeline, built and validated on the real MindWave Mobile 2: ThinkGear reader with reconnect, 4 s Welch windows, blink detection in its own 0.5 to 8 Hz band, three-anchor calibration (eyes closed, easy, hard), session recording and bit-exact replay. Read [`EEG_PIPELINE.md`](../EEG_PIPELINE.md) and [`mindwave/README.md`](../mindwave/README.md) before touching it.

NeuroPace consumes it in-process: the pipeline turns raw into one `FeatureFrame` per second, and NeuroPace's focus engine applies the spec's own-baseline z-score, 15 s window and drop detector on the frame's `engagement` index (log10 beta minus log10(alpha plus theta), the same E = beta/(alpha+theta) on a log scale). Session start options:

| `headset` | What runs |
|---|---|
| `auto` | a paired MindWave if a port is found (`mindwave.MindWaveSource`), otherwise NeuroPace's simulator |
| `sim` | NeuroPace's synthetic EEG (`focused` / `drifting` / `poor`), the demo keys 1/2/3 |
| `fake` | the pipeline's own `FakeSource` (keys map focused to easy, drifting to drowsy, poor to off) |
| `replay:<dir>` | the pipeline's `ReplaySource` on a recorded `sessions/<stamp>` directory |
| `serial:<port>` | NeuroPace's minimal raw ThinkGear reader, for debugging only |
| a device path | the pipeline on that serial port (what `auto` resolves to when a headset is found) |

**Brain waves on screen are the device's bytes.** The pipeline decimates the 512 Hz raw stream to 64 Hz and NeuroPace broadcasts it as `raw` chunks; the live and restudy screens draw those and nothing else. The label under the trace is judged from arrival time: *live from your headset* only while chunks keep coming, *waiting for the headset* within two seconds of a dropout, *practice signal* for every non-real kind. A session that started on the simulator because the headset was off keeps looking every five seconds and switches to the real device when it appears. One headset, one recording: a second lecture on the same port is refused (409) until the first ends.

**Testing without the hardware, honestly:** `uv run neuropace virtual-headset --control /tmp/vh.ctl` puts a MindWave on a pseudo-terminal (macOS and Linux). It writes real ThinkGear packets (one 0x80 raw packet per sample at 512 Hz, a 1 Hz status packet with poor_signal, eSense and the eight EEG power bands) from the pipeline's `FakeSource`, so the serial reader, the parser, the pipeline and every screen above see a headset of kind `real`. Start the server with `REFLOW_HEADSET_PORT=<the printed path>`; then `echo "state drowsy" > /tmp/vh.ctl` makes the wearer drift, `state off` lifts the electrode, `pause 6` drops the link for six seconds. Windows has no pty: use `headset=fake` there (same signal, in-process).
Real sessions are recorded by the pipeline under `data/eeg/<stamp>/`. The pipeline's calibration can be driven from the live view (eyes closed, easy, hard, done) and its go/no-go from `EEG_PIPELINE.md` §7 applies unchanged. The standalone tools still work: `uv run python run_pipeline.py --fake` (use `--ws-port 8766` while NeuroPace is serving on 8765) and `uv run --group monitor python monitor.py --fake`.

Two copies of the evaluation toolkit exist on purpose: the root `neuropace_eval.py` is the pipeline team's pre-registered version (yoked random-timing control, `power` command); `neuropace/eval/neuropace_eval.py` is the NEUROPACE-3 version that `neuropace study-analyze` uses.

### Platforms

| | macOS | Windows |
|---|---|---|
| Toolchain | uv, pnpm, arduino-cli via Homebrew | uv, pnpm, arduino-cli installers; `copy .env.example .env` instead of `cp` |
| Headset port | `/dev/cu.MindWaveMobile-SerialPo` after pairing in System Settings; found by name | two "Standard Serial over Bluetooth link (COMn)" ports per paired device with no name; auto-detect probes each for ThinkGear packets (headset must be on), or set `NEUROPACE_HEADSET_PORT=COM3` (the outgoing port) |
| Totem port | `/dev/cu.usbmodem…`, found by name | "USB Serial Device (COMn)", found by Arduino's USB vendor id 0x2341 |
| `run_pipeline.py` keys | termios (any terminal) | msvcrt (cmd, PowerShell) |
| `monitor.py` | matplotlib macosx backend: `uv run --group monitor python monitor.py --fake` | matplotlib TkAgg; same command |
| Status | this build was developed and verified here (tests, smoke, browser) | code reviewed for Windows paths, COM naming, console encoding and event loop; not yet executed on a Windows machine |

`uv run neuropace doctor` prints the platform and every serial port with its hardware id, which is the first thing to check when a device is not picked up.

### Commands

| Command | Purpose |
|---|---|
| `uv run neuropace serve` | API + built frontend on one port |
| `uv run neuropace doctor` | keys, Deepgram, selected OpenAI/OpenRouter model, ports, build |
| `uv run neuropace ingest-lecture --title T --file lecture.m4a --meta study/meta.json` | transcribe a recorded lecture with Deepgram and register segments/quiz |
| `uv run neuropace ingest-script script.json` | register a scripted lecture (words or plain text) |
| `uv run neuropace replay SESSION_ID --speed 4` | print a session's event log at speed |
| `uv run neuropace study-analyze --lecture LEC_ID` | the four study numbers with intervals |
| `uv run neuropace sim selftest|bandit|lossmap` | the spec's simulations |
| `uv run neuropace kaggle-check EEG_data.csv` | hour-0 feature check on the Wang et al. confusion data |
| `uv run pytest -q` | the test suite (no network, no hardware, about 15 s) |
| `uv run python scripts/smoke_e2e.py` | end-to-end against a running server, prints tap-to-catch-up latency |

### Layout

```
neuropace/        Python package: signal engine, totem bridge, Deepgram, OpenAI, session runtime, review, tally, loss map, API, CLI
mindwave/      the team's standalone MindWave pipeline (headset -> calibrated FeatureFrame per second); run_pipeline.py, monitor.py, example_consumer.py use it directly
frontend/      Vite + React app (live, notes, review, tally, loss map, replay, quiz)
firmware/      uno_q_relay/ (UNO Q 4 GB BLE relay prototype, current target, uncompiled) + totem/ (UNO R4 direct-USB fallback sketch)
study/         lecture script with the planted flaw, quiz, protocol
tests/         pytest suite
data/          runtime data (sqlite, session logs, lectures); the demo lecture script is committed
docs/          PRD, TDD, demo runbook
```

### Sponsor challenges — implementation

- **Deepgram:** live streaming transcription (`neuropace/transcribe/deepgram_live.py`) and prerecorded transcription for recorded lectures. Both are in the product path.
- **OpenAI/OpenRouter:** rolling recaps, gap notes, check questions, re-teach forms and diagram scene graphs as strict JSON-schema structured outputs (`neuropace/llm/`).
- **Long Lake:** pitch framing only. No prompt box. NeuroPace notices for you.

### Honesty rules baked in

- A simulated headset or scripted transcript is labelled on screen, and forced flags carry `source: "forced"`. Keyboard taps are real taps.
- No placeholder text: without a key for the selected OpenAI or OpenRouter provider, a session cannot start; during an outage the catch-up is the verbatim transcript (`source: "transcript"`) and failed notes are reported (`package_source: "failed"`) with a retry. The extractive `offline` generator only runs in automated tests (`NEUROPACE_ALLOW_OFFLINE_LLM=1`).
- The tally says "not enough data yet" until 12 scored cards.
- The loss map refuses to render with fewer than 2 learners.
- Every study number is reported with its interval, including nulls.
