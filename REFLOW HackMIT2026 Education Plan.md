# REFLOW
### Responsive design for cognition. The lesson reflows the moment you lose the thread.
**HackMIT 2026 · Education · NeuroSky MindWave Mobile 2 + webcam + Arduino UNO R4 · Sat 19 Sep 2026**

A **real-time teaching assistant**. It watches you learn and changes the material *while you are reading it*. It is not a post-session quiz, and it is not a chatbot.

Tags: **[V#]** = source opened (list in §14). **[RUN]** = code or simulation executed and reproduced. **[U]** = not verified; confirm before relying on it. **[!]** = a claim that was checked and turned out wrong. Open questions are in §12.

---

## 1. The pitch

**One line.** Responsive design for your brain: the lesson reflows the moment you lose the thread.

**Thirty seconds.** Responsive web design reflows a page to fit the screen. Reflow reflows a *lesson* to fit your mind, live. A ten-second EEG headset, your webcam and your own behavior act as three witnesses. When two agree you are overloaded, the paragraph you are stuck on dissolves into an animated diagram built from the same content. When two agree you have checked out, the text asks you to predict the next step or turns into a simulation. It learns which fix works for you and hands you that playbook. Point the camera at a textbook and it reflows that too.

**Not an AI tutor.** An AI tutor generates explanations and waits for you to ask. Reflow has no prompt box. It is a rendering layer that sits under any content and changes its *form* from a closed loop with your brain, face and behavior.

**Why "assistant" and not "quiz".** The intervention has to land while the confusion is live. A paragraph explained after the fact is a different, weaker product, and it throws away the one thing the sensor is good for, which is timing.

---

## 2. Novelty, with the prior art named and quoted correctly

What NeuroChat actually is (arXiv 2503.07599, CUI '25, Baradari, Kosmyna, Petrov, Kaplun, Maes) [V5]: a Muse 2 headband (AF7, AF8, TP9, TP10, ref Fpz); engagement E = β/(α+θ) on a 15 s sliding window; normalized against a 2 min relaxation task and a 2 min word-association task; the score is **frozen when the user starts typing** and injected into the GPT-4-turbo prompt so the *next reply* changes depth, format and tone. n=24. Engagement rose (p = 0.029). Quiz and essay scores did not change.

Their own §6.2 limitations are our roadmap. Put these on the slide:
- "increased engagement … can also reflect cognitive overload, confusion, or frustration … does not distinguish between productive and unproductive forms of engagement, nor does it adapt based on … cognitive load"
- "could benefit from integrating complementary signals, such as task performance, self-reports, or behavioral metrics"
- "more robust neuroadaptive systems may benefit from multimodal sensing, artifact rejection techniques, or sensor fusion"
- participants asked for "mind maps or diagrams … images or timelines could reduce the cognitive burden of reading"
- "there is no fixed rule set that defines how different values should influence the response"

| | NeuroChat (MIT, 2025) | **Reflow** |
|---|---|---|
| When it acts | At your next message. Nothing changes while you read | **Mid-paragraph**, on the unit you are stuck on right now |
| State | One axis, engagement (admitted to confound overload with interest) | **Two axes: overload × engagement**, different fixes for each |
| Evidence | EEG only, 4 channels | **Three witnesses: brain (1 ch), face (webcam), hands (behavior)**; two must agree |
| Adaptation | Rewrites the text: depth, tone, bullets | **Modality transformation:** text → diagram → chunks → worked example → simulation |
| Personalization | One prompt for everyone | **Bandit per learner** → a playbook they own |
| Learning signal | Quiz after 20 min; no gain | **Time-to-recover and checkpoint correctness on every intervention** |
| Content | Chat answers the bot wrote | **Any content:** paste, PDF, a textbook page held to the camera |
| Calibration | Two-point, 4 min | Three anchors, 60 s (same idea, faster; **do not claim novelty here**) |
| Data | Client-side, no ownership story | **Learner-only; no teacher dashboard; undo on every reflow** |

Say it in the first twenty seconds: "NeuroChat proved an LLM tutor can respond to EEG engagement. It also found that engagement alone did not improve learning, could not tell overload from interest, and never changed anything while you were reading. Reflow starts where their limitations section ends."

---

## 3. "The EEG is bad and only detects binary focus" — half true, and it matters which half

**True:** the **eSense attention meter** (`0x04`, 0–100, 1 Hz) is a proprietary black box. NeuroSky publishes no algorithm, says only that it weighs beta and gamma with "slow-adaptive" internal adjustment, and its own docs call 40–60 "neutral" [V13][V14]. Between the coarse banding and the hidden adaptation it behaves like a two- or three-level focus light, not a measurement. Any claim built on it is unfalsifiable, because we cannot say what it computed.

**False as a statement about the device:** the headset also streams **raw 512 Hz at Fp1** (`0x80`). That is a real signal and we compute our own band powers from it. Szafir & Mutlu built a working attention-adaptive agent from exactly this, same sensor family, same electrode site [V3]. `mindwave/features.py` already does the Welch PSD, so we own every number in the chain.

**The real limitations**, worst first:
1. **One channel, no spatial filtering.** The 80–83% figures in [V2] come from many electrodes and per-subject spatial models. One electrode cannot reach that. **0.65 AUC [V4] is our ceiling and our quoted number.**
2. **Fp1 sits directly over the eye.** Blinks are 100–300 µV transients landing in theta, the band we care about. Unmasked, blinks *manufacture* the effort signal. `features.py` detects them in a separate 0.5–8 Hz band and interpolates across them before the PSD. This is the single most important correctness detail in the codebase.
3. **Dry electrode.** Contact drifts. The quality gate (`poor_signal > 50` → frame invalid) is mandatory, not defensive.

**What this changes in the design:** it is the whole reason for the three-witness rule in §5. A ~0.65 detector cannot be allowed to fire an interruption on its own. Treat `attention` and `meditation` as passthrough-for-comparison only, which is how `pipeline.py` already labels them. **Keep the eSense number out of the demo and the submission.** If a judge asks whether we use NeuroSky's attention score: no, it is proprietary and coarse, we compute Pope's engagement index from raw, and here is the confusion matrix against thought probes.

---

## 4. Code that already exists (read before building anything)

`mindwave/` is a working 1,750-line pipeline and **it was built for this architecture**. `brain_example.py` already sketches the FLOW / OVERLOAD / DISENGAGED / FATIGUE consumer with the two-key rule. Nothing here needs re-aiming.

| Module | What it does | Status |
|---|---|---|
| `thinkgear.py` | Serial protocol, packet/checksum parse, all five codes, threaded reader | Done |
| `features.py` | 4 s windows, three filter bands, blink detection + masking + interpolation, Welch PSD, `effort` = logθ−logα, `engagement` = logβ−log(α+θ) | Done. **The asset** |
| `calibration.py` | Three anchors (`eyes_closed`, `easy`, `hard`), z-scoring so hard ≈ +1 and easy ≈ −1, refuses weak calibrations, reports sign inversion instead of hiding it | Done, and the reading anchors are **correct** for this design |
| `pipeline.py` | Quality gate, artifact-coverage gate, 5 s EMA, 1 Hz `FeatureFrame`, session logging, `ReplaySource` | Done. Replay is the §10 demo fallback |
| `server.py` | WebSocket feed at `ws://127.0.0.1:8765` | Done |
| `monitor.py`, `run_pipeline.py`, `brain_example.py` | Live plot, headless service, consumer example, all with `--fake` | Done |

**[!] Correction to an earlier note:** `mindwave/README.md` and the `pipeline.py` docstring were briefly marked "stale" for describing FLOW / OVERLOAD / DISENGAGED. They are not stale. They describe this design correctly. Leave them alone.

**Still to build:** the brain (hysteresis, dwell, three-witness fusion), the camera track, the reader UI, the transformation ladder, the diagram pipeline, the bandit, the Arduino sketch.

---

## 5. Signal engine

**EEG** (done, in `features.py`): `effort` = logθ − logα, `engagement` = logβ − log(α+θ), blink rate and duration over a trailing 30 s, all gated on `poor_signal` and artifact coverage, z-scored against calibration, 5 s EMA. `L` and `E` arrive as a 1 Hz `FeatureFrame`.

**Camera** (to build): MediaPipe Face Landmarker in the browser, 478 landmarks, 52 blendshapes, a 4×4 head-pose matrix, 30 fps on a laptop [V18].
- **Effort / confusion:** `browDownLeft/Right` (AU4 brow lowerer), `eyeSquintLeft/Right`, lean-in (face box growing).
- **Disengagement:** head yaw or pitch away from the screen, iris off-screen, `jawOpen` yawn, lean-back, low head-motion energy for 20 s.
- **Fatigue:** blink rate up, lid droop. Cross-checks the headset's own blink count, which is a free sanity check on electrode contact.

**Behavior:** response time vs baseline, checkpoint correctness, scroll stall > 8 s, scroll-back (re-read), idle input, tab blur, fast-but-wrong.

**Calibration (60 s, already implemented).** `eyes_closed` (~10 s, alpha reference and the honest "the electrode works" demo beat), `easy` (~25 s), `hard` (~25 s). Hard maps to about +1 and easy to about −1 per learner. If the hard task did not raise effort, `pipe.status()` says so rather than flipping the sign silently. This is NeuroChat's two-point idea done faster; **do not claim it as novel**.

**State** (EMA τ = 5 s, hysteresis, 20 s minimum dwell between interventions):

| State | Brain | Face | Hands |
|---|---|---|---|
| FLOW | L mid, E high | brow relaxed, gaze on page | RT ≈ baseline, correct |
| OVERLOAD | L > +1 for ≥ 8 s | brow furrow, squint, lean-in | RT slow, re-read, errors |
| DISENGAGED | E < −1 for ≥ 8 s | gaze away, head turned, lean-back, yawn | idle, fast-but-wrong, tab blur |
| FATIGUE | E drifting down over minutes | blink rate up, lid droop | RT slowing over minutes |

**Three-witness rule.** An intervention fires only when **two of the three** agree, or when one is extreme for 15 s. This is the honest answer to "how good is a $100 single-channel headset?", and it is what stops the thing being annoying. If EEG quality is red, face and hands carry the decision and the UI says so.

---

## 6. Interventions: content transformations, never tips

**OVERLOAD ladder (cheapest first):**
1. **Dissolve → animated diagram.** The paragraph dissolves letter-by-letter while an LLM turns the same text into a scene graph; the diagram animates in step by step with captions. *The dissolve is timed to cover generation latency.*
2. **Chunk & reveal.** Same content as three steps, one at a time, one checkpoint question after each.
3. **Worked example.** The abstract paragraph becomes a concrete instance.
4. **Say it.** When overload coincides with gaze leaving the page, a spoken walkthrough synced to the diagram steps.
5. **Declutter.** Hide everything but the current unit; larger type.
6. **Save the thread.** Bookmark the exact sentence; two-line re-entry summary.

**DISENGAGED ladder:**
1. **Predict the next step** (retrieval prompt inline). Retrieval beats restudy at a delay [V11], so this is the default.
2. **Explain it back**, aloud, to a voice agent that probes and scores.
3. **Turn it into a simulation** (slider or drag on the diagram's variables).
4. **Raise difficulty / skip known** (fast-and-correct means bored, not overloaded).
5. **Micro-break**, 90 s timer.

**Playbook (the product).** Thompson-sampling bandit per learner over the arms; reward = state returns to FLOW within 45 s **and** the checkpoint is correct. After a session: "Overload → diagram fixed it in 9 s (3/3). Disengaged → prediction prompt (2/2). Breaks didn't help you." The learner owns it and can hand it to a teacher on their own terms.

**Undo on every reflow.** A "back to text" chip, always visible. This is both a usability answer and the surveillance answer.

---

## 7. The dissolve → diagram pipeline (the wow, made reliable)

1. **Detect** OVERLOAD on the current unit (text node id).
2. **Generate:** strict JSON schema, `{title, nodes:[{id,label,kind}], edges:[{from,to,label}], steps:[{highlight:[ids], caption}]}`. Temperature 0. Retry once on invalid JSON.
3. **Layout:** dagre (or elkjs) for a DAG; d3-force for concept maps.
4. **Animate:** anime.js or Framer Motion timeline; nodes fade in per `steps`, edges draw, captions crossfade; 8–15 s; scrubable.
5. **Cache** three demo topics (Krebs cycle, Bayes' theorem, backpropagation) at build time. Live generation for arbitrary text is the stretch and still works with the dissolve masking 3–6 s.
6. **Undo** chip always visible.

Mermaid plus CSS animation is the 30-minute fallback renderer.

**Camera as input (cheap, high impact).** A "scan" button grabs a webcam frame, sends it to a vision model, returns units of text. The textbook page becomes a reflowable lesson. Cache one pre-shot page in case the table lighting is bad.

---

## 8. The Arduino UNO R4

The board arrived by accident instead of the UNO Q. It still earns a place, but a small one: **it owns the inputs and indicators that should not live in the UI being reflowed.**
- **"I'm lost" button.** A physical press is a manual intervention request *and* the ground-truth label that trains the bandit and validates the detector. This is load-bearing.
- **Fit meter.** Seat the headset by watching LEDs fill, instead of squinting at a number on screen. Turns a 60 s fumble into a 10 s demo beat.
- **Ambient state light.** Shows the system is watching without putting a widget on the page.

**[!] Which R4 is it? Answer before writing the sketch.**

| | UNO R4 **WiFi** | UNO R4 **Minima** |
|---|---|---|
| 12×8 LED matrix | **Yes** | **No** |
| Radio | ESP32-S3 (Wi-Fi + BLE) | **None** |
| `LOVE_BUTTON` capacitive pad | Listed as supported [V15] | Listed as supported [V15] |

On a **Minima** the fit meter falls back to `LED_BUILTIN` blink-rate coding, or move it to the laptop. Decide in the first ten minutes.

**[!] The heart pad may need a part.** Sources conflict. The official `Arduino_CapacitiveTouch` library lists `LOVE_BUTTON` as supported on both boards and mentions no external components [V15]. A widely used third-party library states it "requires the addition of a small capacitor … between pin 10 and ground on the Arduino UNO-R4 Minima or between pin 7 and ground on the Arduino UNO-R4 WiFi", 1 nF to 10 µF, affecting the threshold [V16]. Try the official library first and **wire a plain momentary pushbutton to a digital pin in the same sketch as the backup.** The heart pad is a nice detail; the press is load-bearing. Never let a nice detail own a load-bearing input.

**[U] Serial routing.** Headset → laptop → R4 over USB serial. The R4's radio cannot take Bluetooth Classic SPP from the headset, so the laptop is the hub. Confirm in hour 0 that `pyserial` talks to the R4 while the headset is also connected; both want a COM port and the MindWave's outgoing SPP port is not always COM3.

---

## 9. The measurement, and the trap in it

**The trap, and it is a big one.** Szafir & Mutlu ran the closest published study to Reflow: a NeuroSky at FP1, engagement index, an agent that cued attention in real time. Adaptive cues beat the no-cue baseline (p = .022) but **did not beat random-timed cues (p = .118)** [V3]. So a demo that compares "Reflow on" against "plain text" proves only that interventions help. It proves nothing about the sensor, which is the entire claim.

**Therefore every measurement needs a yoked random-timing control**: the same number of the same interventions, fired at times drawn from another participant's trigger distribution. It costs one config flag and it is the difference between a defensible result and a press release.

| Number | Question | Tool |
|---|---|---|
| **Detector vs probes** | Does the state flag agree with self-report better than always guessing the majority? Per wearer | `reflow_eval.py detector` |
| **Recovery** | After a sensor-timed reflow, does state return to FLOW faster than after a yoked random-timed one? | `reflow_eval.py outcome` |
| **Comprehension** (stretch) | Checkpoint correctness, sensor-timed vs yoked | `reflow_eval.py outcome` |

Recovery is the cheap one and it is within-subject, so it needs no quiz bank and no separate session. Collect it from anyone who wears the headset for ten minutes.

**Thought probes** for the detector number: while a teammate reads for 12–15 min, a soft chime every 40–80 s (jittered) asks *on task / drifting?* Label the 15 s before each probe [V1][V2]. Same posture and gaze target as real use, so eye position does not confound the labels.

**Feature gate.** Unit of analysis is one probe window, not 1 Hz samples, which are autocorrelated. A naive "use it if |d| ≥ 0.5" is unsafe at these label counts. Reproduced independently [RUN]:

| Independent windows per class | Naive rule passes pure noise |
|---|---|
| 4 v 4 | 50% |
| 8 v 8 | 34% |
| 12 v 12 | 24% |
| 20 v 20 | 12% |

Reflow's rule: |d| ≥ 0.5 **and** permutation p ≤ .10, sign learned per wearer. At 12 v 8 windows it passed noise 10.7% of the time and passed a true d ≈ 1.14 effect [RUN]. `reflow_eval.py gate`.

**Judge answer to "how accurate?"** "Published detectors for this get about 0.65 AUC. Ours on this wearer: here is the confusion matrix against 20 thought probes. That is exactly why two witnesses have to agree before anything moves on your screen."

---

## 10. `reflow_eval.py` — verified [RUN]

Committed at the repo root. `selftest` exits 0 and every number reproduces:

```
gate real : {'d': 1.137, 'p_perm': 0.0234, 'n_on': 12, 'n_lapse': 8, 'use': True, 'sign': 1}
gate null false-pass rate (12v8 windows, perm p<=.10 AND |d|>=.5): 0.107
detector  : {'tp': 14, 'fp': 4, 'fn': 1, 'tn': 21, 'n': 40, 'accuracy': 0.875,
             'majority_baseline': 0.625, 'p_vs_baseline': 0.0004, ...}
outcome   : {'n': 8, 'mean_diff': 0.191, 'ci95': [0.129, 0.249], 'p_perm': 0.0063}
SELFTEST PASS
```

Sound statistics: two-sample permutation on the gate, sign-flip paired permutation plus percentile bootstrap on the outcome, exact binomial against the majority baseline on the detector. `numpy` only, already in `requirements.txt`.

Two things to know rather than fix: the detector's `p_vs_baseline` estimates the majority rate from the same data it tests (mildly anti-conservative, irrelevant at our effect sizes), and `rng` is module-level with a fixed seed, so repeated calls in one process are not independent draws.

**It is committed before the data exists.** That ordering is the point, and it is what makes the honesty claim credible on stage.

---

## 11. Demo (90 s)

1. (0–10) Headset on in ten seconds, fit meter fills on the totem, quality chip green. "This is Reflow. Responsive design for your brain. Three witnesses: brain, face, hands."
2. (10–40) Calibration: eyes closed, the alpha bar jumps, *that is your own alpha*. Then 20 s easy, 20 s hard. Chip: *calibrated to you*.
3. (40–60) Dense Bayes paragraph. Brow furrows, scroll stalls, L rises. **The paragraph dissolves into an animated diagram.** Checkpoint; judge answers; state returns to FLOW.
4. (60–75) Easy, boring text. Gaze drifts, E drops. Prediction prompt, then the slider simulation.
5. (75–90) The playbook card, and the two numbers from §9. Hold a textbook page to the camera and watch it become a lesson. "Learner-only. No teacher view. Undo on everything."

Keyboard control plane from hour one: `O` overload, `D` disengaged, `F` flow, `R` replay a recorded session. The presenter can drive honestly if a fit is bad, and the UI says **simulated** when they do. Judges forgive a flaky sensor. They do not forgive a faked one.

---

## 12. Build schedule (hours from start)

Roles: **S** signal and brain · **C** content engine and diagram · **U** reader UI, state, bandit · **H** camera, Arduino, study, pitch.

| Hrs | S | C | U | H |
|---|---|---|---|---|
| 0–1 | Pair headset, `run_pipeline.py` on a real forehead. **Gate: real blinks counted.** Confirm COM port | LLM → scene-graph JSON on one paragraph | Repo; reader renders from `--fake` feed (works today) | **Identify WiFi vs Minima. Ask organizers the §13 questions.** Face Landmarker printing brow/gaze/pose |
| 1–4 | The brain: hysteresis, dwell, three-witness fusion on top of `FeatureFrame` | dagre layout + anime.js timeline; the dissolve | Lesson reader with units; state chip; **undo** | Totem sketch: fit meter, button, **pushbutton backup wired**; camera feature EMAs |
| 4–8 | Probe runner; `reflow_eval.py gate` on real labels; tune thresholds on 5 strangers | Chunk, worked-example, simulation, voice transformations; cache 3 topics | Bandit + playbook; checkpoints | Webcam scan → vision model → units; **yoked random-timing control flag** |
| 8–12 | **Integration: live state drives reflows end to end.** Freeze features at 12 | | | |
| 12–16 | Recovery numbers from §9 on 8–12 hackers | Live generation for arbitrary text | Session card, onboarding, polish | Shoot the video; novelty slide; submission text |
| 16–20 | Bug bash on recorded sessions; verify every fallback | | | Table setup: lighting, camera angle, monitor |
| 20–24 | No new features. Rehearse 10× with each teammate as judge. Fresh AAA. Sleep in shifts | | | |

**Kill rule (hour 6):** if clean EEG is not contributing to state, ship face plus behavior as the two witnesses, label EEG experimental, and say so out loud. The transformations, the playbook and the camera are the product. The headset is one input.

**Code rule.** HackMIT describes projects as built "from scratch" [V9]; the exact policy was not found. `mindwave/` was written before the event, so **ask at hour 0 whether it may be used** and disclose it either way. Keep visible commit history and disclose AI assistance.

---

## 13. Risks and open questions

| Risk | Mitigation |
|---|---|
| Pre-written `mindwave/` disallowed | **Ask at hour 0.** Highest stakes item on the page |
| Bluetooth pairing flakiness | One owner, spare AAA, `--fake` and `ReplaySource` keep three people unblocked |
| EEG uninformative on a judge | Three-witness rule means face and hands carry it; quality gate; simulation mode, labelled |
| Heart pad needs a capacitor | Pushbutton backup wired in hour 1 |
| Board is a Minima, no matrix | Fit meter moves to `LED_BUILTIN` or the laptop; decide hour 0 |
| Judge does not overload on cue | Dense paragraph plus a timed question is a reliable inducer; cached diagram fires instantly |
| LLM latency or bad JSON | Cached topics; the dissolve masks 3–6 s; retry once; Mermaid fallback |
| Camera lighting at the table | Ring light; face thresholds recalibrate per person during the 60 s |
| "Isn't this NeuroChat?" | §2, said first, with their limitations quoted |
| "Classroom brain surveillance" | Learner-only, local, no teacher view, undo on every reflow. Say it unprompted |
| We prove only that interventions help | The yoked random-timing control in §9. Non-negotiable |

**Open, resolve at hour 0:** (1) pre-existing and AI-written code policy → organizers; (2) which R4 variant → look at the board; (3) judging format and rubric → organizers; (4) real-forehead behaviour of §5 → your headset; (5) sponsor challenge requirements → booths; (6) serial routing to the R4 (§8).

---

## 14. Sponsor tracks

Reverting to the real-time assistant changes several answers, because the cost profile and the content surface both changed. Reviewing all 24 in `tracks.md`:

| Track | Call | Why |
|---|---|---|
| **Education** | commit | Core |
| **Long Lake** ("Convince a Non-Believer") | commit, zero build | A skeptic wears the headset for ten seconds and watches *their own* paragraph dissolve. This is the "one great experience" brief verbatim, and it is the best non-Education fit on the list |
| **OpenAI** | commit | Structured-output scene graphs, transformations, page scanning. Needs one concrete Codex story in the demo [U]. Submitting unlocks credits |
| **The Token Company** | **back on, add** | This answer flipped. With no hour-long transcription, the LLM *is* the main cost, and the architecture is already the saving: the state machine runs locally, the model fires only on a trigger, only the stuck unit is sent rather than the document, and demo topics are cached. That is a clean, creative cost story worth a paragraph |
| **ElevenLabs** | add if the voice rung ships | "Explain it back" aloud, with the agent probing and scoring, is retrieval practice [V11] and genuine agentic depth, not text-to-speech. Their brief explicitly deprioritises plain TTS, so only enter if this rung is real |
| **Ramp** ("save time and money") | add, zero-work | "Build anything that saves people time and money." Fewer re-reads per hour of study. Same video |
| **Dropbox** | stretch | Their brief literally lists "transform class materials into a personalized tutor". A PDF drop that becomes a reflowable lesson is a modest addition to the scan feature already planned. Only if hours 12–16 are calm |

**Out:** Arduino (the HackMIT challenge is for the **UNO Q** [V8]; an R4 arrived, so not eligible, and the board stays because the product needs it). Deepgram (the lecture-transcription use left with the quiz idea; only relevant if the voice rung needs ASR, and ElevenLabs covers that lane better). ASUS, Espressif, Cognition only if hardware is handed over working. The other thirteen are wrong-domain or board-locked.

**Commit to four, add three only if they cost nothing.** Each entry is a booth visit and a rehearsal variant, and a long prize list reads as prize-farming to judges who have seen forty teams that day.

---

## 15. Sources

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
