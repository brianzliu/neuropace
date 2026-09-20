# Judge demo: one lecture, one catch-up, one learning loop

## Scope

The judge wears the headset. Show real waves when packets are arriving, but do not depend on an automatic EEG flag to complete the demo. The judge's Catch me up button is a real input, not a simulated lapse. No loss map, study statistics, camera setup, or physical-pad setup in this demo.

## Before the slot

1. Keep `uv run neuropace serve --port 8765` running. Use the local app at http://localhost:8765/session/new. Do not deploy or restart services between judges.
2. Check `uv run neuropace doctor`: transcription, the selected model provider, and TTS must be available. The current tutor voice is Deepgram Cole / Flux with expressivity 2.
3. Put a fresh AAA in the headset and have a spare. If Bluetooth stalls, power-cycle the headset once. Do not keep the judges waiting through repeated reconnect attempts.
4. Use a separate judge/demo learner, not another person's learned profile. Fit the forehead sensor and ear clip. Run the normal 30-second calibration if the signal is clean.
5. If connection or calibration is not ready, click **Continue with button only**. Say: "The signal isn't clean enough for automatic prompts, so use this button whenever you want a catch-up." Recording, notes, and tutoring still work. Any waveform displayed remains real; no attention score is invented.
6. Confirm the browser says **Microphone on**, and check that a few spoken words appear. Keep other conversations away from the microphone. Use a quiet speaker or have a teammate read the lesson below.
7. Keep a previously generated session open as an explicitly labelled saved-lecture backup: http://localhost:8765/lecture/sess_8f4856e0. Never describe saved material as generated live.

## The live sequence

1. **Listen:** Start a fresh lecture. The teammate teaches the short example below while the judge sees the transcript and, when available, real brain waves.
2. **Catch up:** After the core explanation has been spoken, ask the judge to click **Catch me up**. The recap appears immediately and a generated visual follows. Use the format tabs and step controls, then **Back to lecture**. Recording continues while the panel is open; failures show a retry without hiding the recap.
3. **Save:** Click **End lecture**. Open **Private tutoring** once the moment's notes are ready.
4. **Learn:** Cole narrates the model's visual plan and the tutor moves to a check after playback. Use **Pause tutor** for more viewing time or Space to skip the reading. A wrong answer can make the model choose another available explanation to address that misconception.
5. **Adapt:** Answer one question incorrectly on purpose. Show the next explanation family. Answer correctly, then show the lesson completion. A new learner remains labelled as still learning; do not claim a measured preference from one answer.

## Short lesson to read aloud

Suppose you save one hundred dollars in an account that pays ten percent interest each year. After the first year, you have one hundred and ten dollars.

With compound interest, the second year pays interest on all one hundred and ten dollars, not just your original deposit. Ten percent of one hundred and ten is eleven dollars, so you finish the second year with one hundred and twenty one dollars.

Simple interest would pay ten dollars each year, giving you one hundred and twenty dollars instead. The extra dollar comes from earning interest on your interest. That is why compound growth accelerates over time.

## If something is unavailable

- **EEG:** Use the explicit button-only continuation. If EEG drops after recording starts, recording and the button continue. Never force an EEG flag or present simulated data as real.
- **Microphone:** Allow permission and retry the microphone. If it remains unavailable, explicitly announce a recorded/practice lecture and use the saved-lecture backup.
- **Model/network:** The live card can show the labelled transcript. Failed notes offer Retry; use the already generated saved lecture rather than waiting through an outage during judging.
- **Voice:** Click Retry voice once. The explanation remains readable and its Next / Got it controls still work.

Finish after this loop. Additional experiments and non-demo screens are outside this pass.
