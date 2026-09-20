# Demo plan (HackMIT 2026, 3 minutes) and the student cases the stack must pass

Written 20 Sep 2026. Builds on `docs/DEMO-RUNBOOK.md` (checklist, fallbacks) and `docs/PRODUCT.md` (screens). The
demo shows the two jobs in the order a student lives them: **Listen** (the button and the headset notice the
lapse, one-glance catch-up in the student's best way) then **Restudy** (private tutoring that explains each missed
moment in the way that works for this student, checks it, and learns). Everything below is exercised with a
simulated EEG signal (labelled "practice" on screen) by `scripts/e2e_cases.py`; the real headset path is the EEG
team's and slots into the same beats.

## The story (Ana, one lecture)

| Time | Beat | On screen | Say | Must be true |
|---|---|---|---|---|
| 0:00 | Hook | Title | "Every lecture loses you a few times and you never notice. NeuroPace notices the moment it happens, catches you up in one glance, and later re-teaches only what you missed, in the way that works for you. We don't believe in learning styles. We measure what works, on you." | |
| 0:15 | Listen | Dashboard, Start session, the practice lecture "How GPS finds you" (or the live microphone with a teammate lecturing). Transcript streams; brain waves; focus ring "Steady" | "The headset watches whether Ana is with it. The transcript is Deepgram." | Session starts in under 3 s; words flow; the waves say *live from your headset* (real) or *practice signal* (sim), never one for the other |
| 0:35 | The button | Judge presses the pad (or Space). Flash "Catching you up"; one dim line at the bottom: "You missed: <one line> · Now: <last words>", labelled with Ana's best family | "One glance, under a second, no network call: NeuroPace has been writing a four-way recap every 20 seconds in the background. This one is *by comparison*, because that is what has worked for Ana." Press F: "Same idea, as a picture. Same idea, by doing." | Tap to card < 1 s; the line is generated (`source llm|cache`), not the verbatim transcript; F cycles the four families |
| 0:55 | The headset notices | Wearer relaxes (real) or `state drowsy` (virtual). ~10 s later the totem pulses and the chip "Want a quick catch-up?" appears. "Show me" opens the card with "you drifted · since 1:12" | "She did not press anything. It noticed before she did. It only offers; it never interrupts." | EEG flag within 30 s of the drift; chip, never an auto-shown card (P4); a tap after the drift links to it ("from where you drifted") |
| 1:15 | End | "End lecture" then Lecture done: "2 moments to restudy · 1 time you asked · 2 catch-ups" | "The notes are being written for only those two moments." | Notes for every moment in under 30 s (`package_source llm`); a failed one says so and offers a retry |
| 1:30 | Private tutoring | Moment 1 opens: "Pictures usually work best for you, so here it is that way." Where you were. The picture (diagram, animation, curve, timeline, side by side) revealed beat by beat while the tutor voice reads it | "Every explanation is a template the model fills with only what the lecturer said. The voice is Deepgram. The picture advances with the voice." | Voice starts within 1 s; highlight follows the beat; Space skips |
| 1:55 | Miss, then another way | The check. Miss on purpose: "Not yet. Let's try it another way." The card dissolves into *by comparison*: story, then the mapping pairs. Check again: hit. "That's it." | "A miss is not a grade. It is a signal: this way did not land, try the next. Every pair of explanation and answer scores that family for Ana." | The second family differs from the first; the hit credits the family shown right before it |
| 2:20 | Lesson done, You | "2 moments landed · Pictures rescued you once and held your attention 92%". You: the four families ranked, rescued and held-attention bars, "still learning · 5 of 12" | "Understanding first, attention second. Until twelve explanations are scored it says it is still learning. Honest." | Ranking matches the tally; preferred appears only at 12+ |
| 2:40 | For the team | Insights: lecture overview, n = 3 learners, the 40 s peak in segment 3, reveal the planted bad segment | "Across learners the only shared view is this: where the room was lost. It grades the lecture, never a student." | Loss map ready at n ≥ 2; the planted segment ranks first on the seeded sessions |
| 2:55 | Close | | "Learner-owned data. Deepgram in, OpenAI out, and the only thing anyone else sees is how good the lecture was." | |

Backup for the tutoring beat: a session ended earlier the same day with notes already generated (`/lecture/<id>`),
in case generation is slow on the venue network. Backup for templates: `/team/artifacts/sample`.

## Preconditions (run before the slot, in this order)

1. `uv run neuropace doctor`: Deepgram ok, the model provider ok (OpenRouter `openai/gpt-4.1-mini` has credit;
   an OpenAI key from the booth goes in `.env` as `OPENAI_API_KEY` + `NEUROPACE_LLM_PROVIDER=openai`), frontend built.
2. `.env`: `NEUROPACE_BASELINE_SECONDS=30` for the demo (the spec's 180 s means no EEG flag can fire in a 3-minute demo
   without a stored baseline). With the real headset the 30 s startup calibration replaces it.
3. Seed the demo learner and the loss map: `uv run python scripts/demo_seed.py` (see below) creates the returning
   learner with 12+ scored explanations favouring pictures, three ended sessions on the GPS lecture with drifts and
   taps in segment 3, and one ended session with notes ready as the tutoring backup.
4. `uv run python scripts/e2e_cases.py --base http://127.0.0.1:8765` passes end to end (about 5 minutes, real model calls).
5. Browser: one window at 125% zoom, mic permission granted, `/` open on the demo learner. Voice on (V) in restudy.
6. Rehearse the script five times with the virtual headset, saying "simulated" whenever a forced trigger is used.

## Student cases (definition of done)

Each case is one learner's path through the whole stack with simulated EEG. `scripts/e2e_cases.py` drives the
real HTTP + WebSocket API the browser uses and asserts each row; the browser pass covers the screens.

| # | Case | Path | Asserts |
|---|---|---|---|
| A | First lecture, presses the button once | practice lecture, sim headset, tap after the baseline, end, private tutoring, hit | baseline ready; catch-up < 1 s, generated, in the best family with all four forms; one moment with note, question, plan, analogy, planned visual and doing (all valid against the template schemas); tutoring opens with an explanation, its reason and "where you were"; the hit credits that family; tally 1/12; profile counts the moment |
| B | Drifts twice, never presses | sim headset drifting after the baseline, chip opened once, ignored once, manual review | EEG flag within 45 s, chip and totem pulse, no auto-shown card; second drift is a second moment; review on my own asks first, explains only after a miss, credits only explained checks |
| C | Drifts, then presses | drift flag open, tap | the tap confirms the lapse: `linked_eeg`, the span starts where focus dropped, one merged moment |
| D | Returning student with a preference | four practice lectures with four taps each, tutoring where only pictures land, then a fifth lecture | 12+ scored explanations, preferred = pictures, the tutor says "Pictures usually work best for you" when it picks them, the catch-up carries the best family |
| E | Nothing lands | one moment, tutoring, four misses | all four families shown once each, the moment ends "still tricky", the dashboard says "Try another explanation" |
| F | Focus during restudy | headset-only review session, drift, drop on an explanation | waves and focus stream without a transcript, a drift flags (labelled simulated) and never offers a catch-up; a drop switches the family without scoring |
| G | The model goes down | invalid key mid-run, tap, end, restore key, regenerate | catch-up shows the verbatim transcript labelled; notes fail honestly and block restudy with a retry; regenerate writes them and restudy opens |
| H | A different lecture | "Compound interest, the snowball" ingested from text, taps on the numbers, the procedure, the doubling rule, the snowball | every planned template validates; the numeric span plans a chart or a curve; the procedure plans steps; the artifacts are saved for review under `data/verification/` |
| I | Recorded lecture, three learners | recorded mode with the video clock, drift in segment 3, tap, focused in segment 4 | the drift pauses the video and shows the card; the loss map is ready at n = 3 and ranks the planted segment first |
| K | Study participant | named participant, randomized catch-ups, six taps, quiz before and after | shown and withheld catch-ups both logged; the four study numbers compute |
| N | Live microphone path | Deepgram live over the WebSocket with synthesized speech, no browser | the spoken words come back as transcript, a tap catches up, the moment gets notes |
| L | Screens | ego-browser pass per beat | see `docs/VERIFICATION.md` |

## Rehearsal commands

```
uv run neuropace virtual-headset --control /tmp/vh.ctl        # a MindWave on a pty, kind "real"
NEUROPACE_HEADSET_PORT=<pty> NEUROPACE_BASELINE_SECONDS=30 uv run neuropace serve
echo "state drowsy" > /tmp/vh.ctl                               # the drift beat
echo "state easy" > /tmp/vh.ctl                                 # recovered
uv run python scripts/e2e_cases.py --base http://127.0.0.1:8765 --db data/neuropace.db
```

## Verification record, 20 Sep 2026 (02:30 to 03:30, simulated EEG, real model and voice)

Run on an isolated worktree at `326c0ac` with its own server (`NEUROPACE_BASELINE_SECONDS=20`, headset `sim`,
OpenRouter `openai/gpt-4.1-mini`, Deepgram for transcription and the Flux voice), so the EEG team's uncommitted
work on the main checkout was never touched. Everything below was seen, not assumed.

**End to end over the API** (`scripts/e2e_cases.py`, all eleven cases, 4.5 minutes): 163 of 170 checks passed
the first time; the seven misses were expectations, not product faults (taps 21 s apart merge into one moment by
design; a package served from the cache survives a model outage by design; the 30 s flag cap reads 31.0 s on a
1 Hz tick; the API's catch-up count after a session counts offered chips). Measured: tap to card 1 to 5 ms; notes
for a moment in 4 to 12 s; every generated artifact valid against its template on real data (diagram, chart,
plot, animation, steps, worked example, analogy, words) on two lectures; Deepgram live returned 98% of the
spoken words; a returning learner reaches "pictures preferred" after 12 scored explanations and the tutor says
so; the loss map ranks the planted segment first on three seeded recorded sessions; the study numbers compute.

**In the browser** (ego-browser, my own pass plus five headless muse-spark testers with written reports):
dashboard, the studio popup, the practice lecture with the practice label and live-looking waves, Space to a
generated card in the best family with F cycling the four families, the drift chip and the drifted card, the
quit-recording dialog, End to the Lecture done numbers in 7 to 12 s, private tutoring with the reason line, the
voice reading and the diagram advancing with it, a miss dissolving into the next family, a hit, the lesson summary,
You, Insights with the loss map and the planted-segment reveal, the ten sample templates and the real generated
plot, chart, animation (motion confirmed by two screenshots 2 s apart) and steps, Library, notes, replay at 8x
with the catch-ups reappearing, the study quiz before and after, Team.

**Fixed in this pass** (all outside the EEG stack): a tap between two recap cycles showed the verbatim transcript
instead of the latest recap (TDD §6; now the latest recap is used when it is under one cycle old); catch-up lines
and notes quoted course key terms the lecturer had not said yet (the hints are now spelling hints only, prompt
version 10); Escape did not close the quit-recording dialog; the tutor said "As a picture usually works best for
you"; diagram node labels longer than nine characters were always truncated; the dissolving question text wrapped
mid-word; the plot's top tick overlapped its axis label, right-edge annotations clipped and series names collided
(names moved to a legend, annotations staggered); the Done screen counted ignored drift chips as catch-ups; "as a
picture · a picture" duplicated in the restudy header; leftover "Reflow" copy on student screens; "1 attempts";
the Insights segments table wrapped numbers; the study quiz always listed the correct option first (now a stable
shuffle per item and session).

**Open, for the EEG team (not changed here):** a focused wearer on the simulator still gets a drift flag every
47 s with a 30 s baseline (7 in 330 s; 2 in 330 s with a 120 s baseline), and the pipeline's own fake headset
flags every 51 s like clockwork with a 30 s baseline (6 in 330 s; 3 with 120 s), which is the 30 s cap plus the
20 s refractory: after a short baseline the detector rarely leaves the drop state. In a demo on a simulated
signal that means unprompted "Want a quick catch-up?" chips and taps merging into long moments. The real headset
path (30 s startup calibration) is theirs to measure. Also theirs: `tests/test_session.py`,
`test_product_v2.py`, `test_waves.py` and `test_mindwave_bridge.py` fail on the main checkout mid-edit.

**Not verified:** the browser's own microphone permission (automation cannot grant it; the Deepgram path behind
it is verified with synthesized speech), the real headset, the physical pad, Windows.
