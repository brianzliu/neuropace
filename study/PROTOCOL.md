# Study protocol: one study, four numbers (spec §6, PRD §9)

**Goal.** Measure whether the flags mean something, whether the crowd signal finds bad teaching, whether the live catch-up helps more than it interrupts, and which forms rescued misses. Report every number with its interval, including nulls.

## Materials

- One recorded lecture, about 8 minutes, 5 segments, **segment 3 deliberately bad** (jargon, no example). The repo ships a scripted stand-in with exactly this shape (`data/lectures/demo/script.json`, "How GPS finds you", segment 3 planted) for rehearsal. Record your own for the study: `uv run neuropace ingest-lecture --title "…" --file lecture.m4a --meta study/meta.json` where `meta.json` holds `segments` (with `planted_bad: true` on segment 3), `quiz` (15 items, 3 per segment, each with `t_start`/`t_end` on the lecture timeline) and `keyterms`.
- 15 quiz items written **before** anyone is tested, from the transcript.
- One headset, one totem, one laptop. Fresh AAA. Spare AAA.

## Participants

10 to 12 hackers, about 20 minutes each. n=10 gives about 72% power for a 25-point gap; n=6 only 22%. Six is nearly uninformative; recruit ten.

## Procedure (per participant)

1. **Consent and fit** (3 min). Explain: one dry electrode, learner-owned data, only the anonymous loss map is shared. Fit the headset; the live view must show blink ticks. Baseline collects for 3 minutes of listening (the first 3 minutes of the lecture count; set `baseline_seconds` to 180).
2. **Watch without pausing** (8 min). Recorded mode with `auto_pause` **off** (the hard case), headset + pad, catch-up policy **randomized** (each flagged lapse is shown a card or withheld by a logged coin). Tell them: "tap the pad the moment you notice you drifted".
3. **Quiz, phase `before`** (3 min). All 15 items, random order, on the `/quiz/:sessionId` page. This is the recall used for numbers 1 and 3.
4. **Gap notes and adaptive review** (4 min). Notes, then review until three straight hits or exhaustion.
5. **Quiz, phase `after`** (optional, 2 min). Not used for the headline numbers; restudy wins at short delays, so no question-first vs re-reading claim tonight.

## The four numbers

Run `uv run neuropace study-analyze --lecture LEC_ID` (or open `/api/lectures/LEC_ID/study`).

| Number | Claim | How it is computed |
|---|---|---|
| 1. Recall on flagged vs unflagged spans, before review | The flags mean something | Per participant: proportion correct on items whose span overlaps a flag vs the rest; `paired_outcome` (sign-flip permutation + bootstrap CI) |
| 2. Does the pooled loss map rank segment 3 first? | The crowd signal finds bad teaching | Pooled z-scored focus + taps in 10 s bins; segment ranking; report the planted segment's rank and the 40 s peak |
| 3. Catch-up benefit and cost | The catch-up helps more than it interrupts | Under `randomized`: recall on the missed span (benefit) and on the 20 s after it (cost), shown vs withheld, per participant; `paired_outcome` on each. About 5 lapses a person: expect wide intervals and say so |
| 4. Rescues per form | Descriptive only at this n | Tally, pooled and per learner |

## Reporting rules

- Say n, the mean difference, the 95% CI and the permutation p. "n=11, flagged spans 22 points worse, 95% CI 6 to 37" earns more trust than any adjective.
- A null is reportable. The product stands without it (pad + quiz carry it).
- Never quote the simulated numbers as study results. The simulations (`uv run neuropace sim …`) set expectations only.
- Kill rule (hour 5): no usable EEG on real foreheads means the study runs on pad flags only and EEG is shown as an experimental overlay.

## Timeline

One headset, about 20 min per person, so roughly 3.5 hours for ten people. Start recruiting at hour 6, freeze at hour 12.
