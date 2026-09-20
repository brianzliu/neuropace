# Demo runbook (3 minutes) and rehearsal checklist

## Before judging (do all of these, in order)

1. `uv run reflow doctor`: both keys present, Deepgram ok, OpenAI model ok (if not, set `OPENAI_MODEL` to one of the listed alternatives), headset port found, totem port found, frontend built.
2. Fresh AAA in the headset. Spare AAA in your pocket.
3. Calibrated wearer: the teammate who wears the headset in the live beat runs one full session earlier (3 min baseline). Their learner then has a stored baseline; start the demo session with "use stored baseline" so the trace is live from second one. The UI labels "stored baseline".
4. Recorded replay session ready: one real session of the demo lecture with a tap and an EEG flag, ended, notes generated, review not yet started. Note its session id. Open `/replay/:id` once to check it plays.
5. Loss map ready: `/lossmap/:lectureId` shows n ≥ 2 and a ranking. Do not click "reveal" until the beat.
6. Study number ready: `uv run reflow study-analyze --lecture LEC_ID` output copied onto the slide, with its interval.
7. Browser: one window, zoom so the transcript is readable at 3 m, mic permission already granted for the site, `/live` open on the demo learner.
8. Rehearse the script below ten times. Say "simulated" out loud whenever `L`, `1`/`2`/`3` or a simulated headset is used. Space or `T` is the keyboard pad: a real tap, say "keyboard instead of the pad".

## Script

| Time | Beat | Say | Do |
|---|---|---|---|
| 0:00 | Pitch | "NeuroChat restyled every reply and found no learning gain. We don't believe in learning styles. We test it on you, and show you the data." | Title slide |
| 0:20 | Live | "Teammate lectures. Transcript and focus stream. Judge, tap the pad when you drift." | Live session, deepgram transcript, headset on the calibrated wearer, judge holds the totem |
| 0:45 | Catch-up | "One line, one glance, under a second. And here is the same recap as an analogy, because this learner's data says analogies land." | Judge taps; press `F` to cycle the form on the visible card |
| 1:20 | Replay | "A real session at 4×. Flags, taps, the chip. Then the notes for only what was missed, and one review card." | `/replay/:id` then `/notes/:id` then `/review/:id`: miss on purpose, watch the dissolve into the diagram, hit |
| 2:10 | Loss map | "Twelve learners, the 40 seconds where the room was lost. Here is the segment we planted." | `/lossmap/:lectureId`, click reveal. Read the flagged-vs-unflagged number with its interval |
| 2:50 | Close | "Learner-owned data. The only shared view grades the lecture." | End |

## Rehearsing without the headset (the honest way)

`uv run reflow virtual-headset --control /tmp/vh.ctl` puts a MindWave on a pseudo-terminal and prints its path. Start the server with `REFLOW_HEADSET_PORT=<path> uv run reflow serve`: Reflow sees a real headset (no practice badge, "live from your headset"). Then, from another terminal: `echo "state drowsy" > /tmp/vh.ctl` (a drift within about ten seconds, the chip appears), `echo "state easy" > /tmp/vh.ctl` (recovered), `echo "state off" > /tmp/vh.ctl` (electrode off: "Adjust the headset"), `echo "pause 6" > /tmp/vh.ctl` (a dropout: "Headset lost", then back). Everything above the serial port is the code that runs on the real device; only the bytes are synthetic.

Restudy has two ways in: *Private tutoring* (explained first, the tutor voice reads it and the picture advances with the voice, then the check) and *Review on my own* (the check first, an explanation only on a miss, no voice). `/team/artifacts/sample` shows all ten explanation templates with built-in data; `/team/artifacts/<session>` shows what the model filled for a real session.

## If something breaks

| Symptom | Do |
|---|---|
| No transcript in the live beat | Say "scripted transcript" and start a session on the demo lecture (`lecture = How GPS finds you`); the pad still works |
| No EEG flag fires in 60 s | Say so. The judge's tap carries the beat. Never press `L` without saying "simulated" |
| No OpenAI key or the API is down | The app refuses to start a session without a key; mid-lecture the card shows the verbatim transcript (labelled) and failed notes offer a retry. Check `reflow doctor` before the slot |
| Headset poor signal | Reseat, check the ear clip, wait for the quality chip to go green; otherwise headset `sim` and say "simulated headset" |
| Totem not detected | Reconnect USB (a running session picks it up within 5 s) or use the keyboard fallback: Space/`T` or the on-screen pad. A key tap is a real tap; say "keyboard instead of the pad" |
| OpenAI down | Cards carry the `offline` badge; say "offline recap, extractive". The flow is the same |
| Browser mic blocked | Reload, allow mic, or switch to the scripted lecture |

## Codex story (fill in during the event, one concrete sentence)

Record here the one concrete way Codex changed the build, with the commit hash:

- _example shape_: "Codex wrote the ThinkGear parser test that caught a checksum bug in split packets (commit …)."

## Sponsor booths (verify at hour 0)

- Deepgram: confirm the streaming call in `reflow/transcribe/deepgram_live.py` qualifies; ask about `keyterm` limits on nova-3.
- OpenAI: confirm credits and the model id; put it in `.env` as `OPENAI_MODEL`.
- HackMIT organizers: rule on code written before hacking opened and on AI assistance. Disclose AI help in the submission.
