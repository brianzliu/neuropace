# Reflow: Technical Design Document

**Companion to:** `docs/PRD.md` (requirement IDs FR-*, NFR-*, P* are referenced below).
**Status:** v1.0, frozen for the build. Anything not written here is an implementation detail; anything written here is a contract that tests enforce.

---

## 1. Stack and conventions

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.13 (uv), FastAPI + uvicorn, Starlette WebSockets, numpy, pyserial, `openai` 3.x (Responses API, JSON-schema structured output), `websockets` 17 (Deepgram live client), httpx (Deepgram prerecorded), SQLite (stdlib) | One process, async, no native audio deps (audio is captured in the browser) |
| Frontend | Vite 6 + React 19 + TypeScript 5.9 + react-router 7. No UI framework. One CSS file with custom properties. Canvas for the focus trace, inline SVG for diagrams | Built once to `frontend/dist` and served by FastAPI at `/`, so the demo is one process |
| Firmware | Arduino UNO R4 WiFi (core `arduino:renesas_uno` 1.6.0), `Arduino_CapacitiveTouch` 1.4, `Arduino_LED_Matrix`, USB CDC serial 115200 | Verified to compile with `arduino-cli`. A Minima build flag drops the matrix |
| Tests | pytest (backend), `tsc --noEmit` + `vite build` (frontend), `arduino-cli compile` (firmware), `scripts/smoke_e2e.py` (full session over HTTP + WS with everything simulated) | NFR-7: < 60 s, no network, no hardware |
| Style | ruff (E, F, I, B, UP), TypeScript `strict`. No em dashes anywhere, including comments | House rule |
| Config | `.env` + env vars prefixed `REFLOW_`, plus `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL` | `reflow doctor` prints the effective values |
| IDs | `lrn_`, `lec_`, `sess_`, `flag_`, `gap_`, `card_` + 8 hex chars | Greppable in logs |
| Time | `lecture_time`: float seconds on the lecture's own timeline. Live: monotonic since session start. Recorded: the media player's current time, reported by the client | Every learner of the same lecture shares one timeline, which is what the loss map pools |

Repository layout:

```
reflow/                      Python package
  cli.py                     reflow serve | doctor | replay | ingest-lecture | study-analyze | sim | kaggle-check
  config.py                  Settings from env
  ids.py, clock.py
  signal/thinkgear.py        ThinkGear packet parser (sync, checksum, RAW, POOR_SIGNAL, eSense, ASIC_EEG_POWER)
  signal/features.py         Band powers, E index, artifact rejection, EMA, baseline, z, 15 s window, drop detector
  signal/blinks.py           Blink counter on raw
  signal/simulate.py         Synthetic 512 Hz EEG with controllable state
  signal/headset.py          HeadsetSource: SerialHeadset | SimulatedHeadset | ReplayHeadset
  totem/bridge.py            TotemBridge: SerialTotem | SimulatedTotem; line protocol
  transcribe/transcript.py   Transcript store (words on lecture_time, sentence boundaries, text_between)
  transcribe/deepgram_live.py     WS client, PCM in, words out
  transcribe/deepgram_prerecorded.py
  transcribe/scripted.py     Scripted transcript source (replays a word-timed script in real time)
  llm/schemas.py             Pydantic models = the JSON schemas
  llm/prompts.py             Prompt text, versioned
  llm/fallback.py            Extractive offline generator
  llm/client.py              OpenAI Responses + cache + fallback + timeouts
  core/spans.py              Trigger time -> span (lead-in, sentence snapping, merging)
  core/recaps.py             Rolling recap scheduler and lookup
  core/tally.py              Beta posteriors, Thompson pick, population prior
  core/review.py             Review state machine
  core/lossmap.py            Pooled loss map
  core/session.py            SessionRuntime: wires sources, detector, recaps, flags, catch-ups, event log
  store/db.py                SQLite schema + repositories
  api/app.py                 FastAPI app factory, static serving
  api/routes.py              REST
  api/ws.py                  WebSocket endpoint
  eval/reflow_eval.py        gate / detector / outcome (from the spec's toolkit)
  eval/bandit_sim.py, eval/lossmap_sim.py, eval/kaggle_check.py
frontend/                    Vite app (see §9)
firmware/totem/totem.ino     UNO R4 sketch
study/                       lecture script, quiz.json, protocol, analysis notes
data/                        runtime: reflow.db, sessions/*.jsonl, lectures/<id>/
scripts/smoke_e2e.py         end-to-end check with everything simulated
```

## 2. Architecture

```
 browser mic ──PCM16──► WS /ws/session/{id} ──► DeepgramLive ──words──►┐
 NeuroSky (BT SPP) ──► SerialHeadset ──raw 512 Hz──► FocusDetector ──►│
 UNO R4 (USB) ──────► SerialTotem ──TAP──────────────────────────────►│  SessionRuntime
 browser keys/buttons (labelled simulated) ──────────────────────────►│  (one asyncio task per session)
                                                                      │
        ┌── every 20 s: RecapScheduler ──► LLM (async, cached) ◄──────┤
        │                                                             │
        ▼                                                             ▼
   recaps ring buffer                       events: words | focus | flag | catchup | chip | recap | totem
        │                                                             │
        └── tap/eeg flag ──► Spans ──► catch-up lookup (no network) ──┘──► WS broadcast + JSONL log + SQLite
```

Session end → `GapBuilder` merges flags into gaps → one LLM call per gap (parallel) produces note + question + full forms + diagram → stored. Review and tally are REST-driven state machines over stored gaps. Loss map is a pure function over stored focus samples and flags for all sessions of one lecture.

### 2.1 Degradation matrix (NFR-4, FR-O2)

| Missing | Replacement | Label shown |
|---|---|---|
| Headset | `SimulatedHeadset` (state set from UI: focused / drifting / poor) | "SIMULATED HEADSET" |
| Totem | `SimulatedTotem` (taps from `T` key / button) | "SIMULATED TOTEM"; taps carry `source: "sim_tap"` |
| Deepgram key or connection | `ScriptedTranscript` (word-timed script replayed in real time) or, in recorded mode, a cached transcript | "SCRIPTED TRANSCRIPT" |
| OpenAI key or a failed call | `fallback.py` extractive recap / note / question | `source: "offline"` badge |
| Frontend build | `reflow serve` prints the `pnpm build` command and still serves the API | n/a |

## 3. Signal engine (FR-L5, FR-L6, FR-L7)

### 3.0 Front end: the team's `mindwave` pipeline

For a real headset (and for the `fake` and `replay` options) the raw-to-index stage is the team's standalone `mindwave/` package (see `EEG_PIPELINE.md`): reconnecting ThinkGear reader, 4 s window hopping 1 s, blink detection in a 0.5 to 8 Hz band with masking and interpolation, Welch PSD, `engagement = log10 β − log10(α+θ)`, contact and artifact gates (`valid`), blink counts, optional three-anchor calibration, session recording and bit-exact replay. `reflow.signal.headset.MindwaveHeadset` runs `mindwave.Pipeline` on its thread and hands each `FeatureFrame` to the asyncio loop; `SessionRuntime._on_frame` calls `FocusEngine.feed_frame(engagement, quality, valid, blink_count, extra)`.

In that external mode the engine skips §3.2's own FFT and applies only the spec's decision layer to the frame's index: EMA, own-baseline z, 15 s window, drop detector, refractory, lead-in. `x` is the log10 engagement (z-scores are scale-free, so log10 vs ln changes nothing downstream); `e = 10^x`. A frame that is not `valid` counts as an artifact second; `quality > 50` or no frame for 3 s counts as bad signal. Reflow's own simulator (§3.4) still exercises the raw path below, so both parsers stay tested (`tests/test_mindwave_bridge.py` cross-checks them byte for byte).

The pipeline's calibration (`eyes_closed`, `easy`, `hard`, `done`, `reset`) is driven from the live view or `POST /api/sessions/{id}/calibrate`; its z-scores ride along on focus samples as `mw.*` fields for display but never replace the spec's first-3-minutes baseline as the flag source.

### 3.1 ThinkGear parser (Reflow's minimal reader, used by the simulator and `serial:<port>`)

Stream framing: `0xAA 0xAA <len ≤ 169> <payload len bytes> <checksum>` where checksum = `(~sum(payload)) & 0xFF`. Payload rows: single-byte codes `< 0x80` carry one value byte; codes `≥ 0x80` carry a length byte then data.

| Code | Meaning | Decoding |
|---|---|---|
| `0x02` | POOR_SIGNAL | 0 good … 200 off-head |
| `0x04` | ATTENTION eSense | 0-100 (recorded, not used by the detector) |
| `0x05` | MEDITATION eSense | 0-100 (recorded) |
| `0x80` | RAW | int16 big-endian, 512 Hz |
| `0x83` | ASIC_EEG_POWER | 8 × uint24 big-endian: delta, theta, low-α, high-α, low-β, high-β, low-γ, mid-γ (recorded, 1 Hz) |

Port: `REFLOW_HEADSET_PORT`, else the first port whose name contains `MindWave`; baud 57600. `sim` forces the simulator.

### 3.2 Features (once per second)

- Window: last 2 s of raw (1024 samples), Hann, rFFT. Band power = Σ|X|² over θ 4-8 Hz, α 8-13 Hz, β 13-30 Hz.
- Artifact rejection: segment peak-to-peak `p2p > max(400, 3.5 × rolling_median_p2p)` (median over the last 30 clean segments) → `artifact = true`, sample excluded from E, baseline, z.
- Quality gate: `poor_signal > 50` → `quality = "bad"`, sample excluded, flags suppressed.
- E = β / (α + θ); `x = ln(E)`; EMA at 1 Hz with τ = 8 s: `x_ema += a·(x − x_ema)`, `a = 1 − e^(−1/8)`.
- Baseline (first `REFLOW_BASELINE_SECONDS`, default 180, of listening): μ, σ of `x_ema` over valid samples; σ floor 0.05. Ready when ≥ 60% of the baseline seconds were valid, or when the baseline period ends with ≥ 30 valid samples. A stored learner baseline (`learners.baseline_mu/sigma`) may be used when the session is created with `use_stored_baseline = true`; the UI labels "stored baseline".
- `z = (x_ema − μ) / σ`. `w15` = mean z over the last 15 s of valid samples (needs ≥ 8).
- Drop detector (hysteresis + refractory): enter `drop` when `w15 < −1.25`; exit when `w15 > −0.6` or 30 s after entry. Calibrated on the simulator (see §3.4); tunable with `REFLOW_DROP_ENTER_Z` / `REFLOW_DROP_EXIT_Z`. Refractory: no new entry within 20 s of the previous exit. Suppressed while baseline not ready or quality bad.
- EEG flag: `t_trigger = t_enter`, `t_start = t_enter − 8` (lead-in), `t_end = t_exit`. Broadcast `flag_open` at entry and `flag_close` at exit.
- Blinks (`signal/blinks.py`): 250 ms blocks; blink when block `p2p > max(300, 3 × rolling_median_block_p2p)`; refractory 300 ms. Emitted as `blink: true` on the next focus sample and counted.

### 3.3 Detector calibration (measured on the simulator, 19 Sep 2026)

False flags per 10 min on a focused simulated wearer with a 180 s baseline, and latency to flag a drift (10 seeds each):

| enter / exit z | false flags per 10 min (mean, max) | drift latency median, max |
|---|---|---|
| −1.0 / −0.5 | 5.7, 10 | 9 s, 57 s |
| −1.25 / −0.6 | 4.8, 10 | 11 s, 58 s |
| −1.5 / −0.75 | 3.2, 8 | 11 s, 59 s |
| −2.0 / −1.0 | 2.2, 7 | 14 s, 64 s |

Requiring the enter condition to persist for 3 or 5 consecutive seconds did not change the false-flag rate (the excursions are sustained), so persistence is not used. Because every false flag costs its cap plus the 20 s refractory, and a false flag in progress delays a real detection, the cap is 30 s (a real lapse that lasts longer simply re-flags after the refractory and merges into one gap). −1.25 / −0.6 is the default: real mind-wandering shifts the index by a fraction of a sigma (AUC about 0.65), so sensitivity matters more than the simulator's false-flag count, and a wrong flag only costs a chip (P4). Re-measure on a real forehead at hour 1 and tune with the env vars.

### 3.4 Simulated headset

512 Hz synthetic: θ 6 Hz, α 10 Hz, β 20 Hz sinusoids with slow phase drift + Gaussian noise (σ = 20) + a blink bump (amplitude 350, width 100 ms) every 3-6 s. Amplitudes by state: focused (25, 30, 35), drifting (45, 38, 18), poor → `poor_signal = 200`. The simulator emits real ThinkGear-encoded bytes into the same parser, so the parser is exercised in every simulated run.

## 4. Totem (FR-L12)

Serial line protocol, 115200 baud, `\n` terminated ASCII.

| Direction | Line | Meaning |
|---|---|---|
| totem → laptop | `HELLO totem 1 <board>` | On boot and on `PING` |
| totem → laptop | `TAP <millis>` | One debounced touch (≥ 250 ms between taps) |
| totem → laptop | `PONG` | Reply to `PING` |
| laptop → totem | `PING` | Liveness |
| laptop → totem | `FIT <0-8>` | Fit meter: number of lit LEDs in row 0 |
| laptop → totem | `DOT <n>` | Show n saved-span dots (rows 2-6, 12 per row, cap 60) |
| laptop → totem | `PULSE` | Sweep row 7 for 2 s (the "catch-up ready" pulse) |
| laptop → totem | `CLEAR` | Clear matrix |

Port: `REFLOW_TOTEM_PORT`, else the first port whose name contains `usbmodem` and is not the headset. `sim` forces the simulator. Auto-reconnect every 2 s. Firmware falls back to a pushbutton on D2 (INPUT_PULLUP) when `USE_CAPTOUCH` is 0.

## 5. Transcription (FR-L2, FR-L3)

### 5.1 Live (Deepgram streaming)

- Browser: `getUserMedia` → `AudioContext({sampleRate: 16000})` → AudioWorklet → Int16 PCM frames of ~100 ms, sent as binary WS frames after a text `audio_start {sample_rate}` message.
- Backend → `wss://api.deepgram.com/v1/listen?model=nova-3&encoding=linear16&sample_rate=<sr>&channels=1&punctuate=true&smart_format=true&interim_results=true&keyterm=<k>…` with header `Authorization: Token <key>`. `{"type":"KeepAlive"}` every 5 s without audio; `{"type":"CloseStream"}` at end.
- Word time → lecture time: `lecture_time = stream_t0 + word.start`, where `stream_t0` is the lecture time at which the first audio frame was forwarded.
- Only `is_final` words are appended to the transcript store; interim words are broadcast with `final: false` for display and replaced on the next result.
- Model is configurable (`REFLOW_DEEPGRAM_MODEL`, default `nova-3`).

### 5.2 Recorded (Deepgram prerecorded)

`POST https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&punctuate=true` with the media bytes; cache the word list in `lectures.transcript_json`. During a recorded session the client sends `media_time {t, playing}` at 4 Hz; the backend reveals words with `end ≤ t` and stamps focus samples with the current media time (samples while paused are marked `paused` and excluded from flags and the loss map).

### 5.3 Scripted

`data/lectures/<id>/script.json`: `{words:[{w, start, end}], segments:[…]}`. Replayed at real time in live mode without a key. The demo lecture ships in the repo.

## 6. Spans, recaps, catch-ups (FR-L4, FR-L8, FR-L9, FR-L10)

- Tap span: `t_end = t_tap`, `t_start = t_tap − 8`. Snap `t_start` back to the nearest earlier sentence start within 20 s of `t_tap`; snap `t_end` forward to the end of the sentence in progress when it arrives (cap `t_tap + 5`).
- EEG span: `t_start = t_enter − 8`, `t_end = t_exit` (cap 30 s), same snapping.
- Rolling recap every 20 s: input = words in `[t − 30, t]` (skip if < 12 words). One LLM call returns `RecapForms {plain, keyterm, analogy, sketch}`, each ≤ 25 words. Stored with `(t_from, t_to)` in a ring of the last 30 recaps. Timeout 15 s; a late result is discarded (NFR-2).
- Catch-up lookup on a trigger at `t`: the latest recap with `t_to ≤ t + 2` and `t_to ≥ t_start − 5`; else the latest recap; else an immediate offline recap built from the span text. `now_text` = the last ≤ 12 final words ending at or before `t`.
- Card: `{flag_id, form: best_form, line: forms[best_form], now_text, forms, source, ttl_s: 6}`. Tap → `auto_show: true`. EEG → `chip` (+ totem `PULSE`); in recorded mode with `auto_pause` → `pause_request` + card `auto_show: true`.
- Policy `randomized`: coin flip per flagged lapse (seeded per session, logged as `catchup_shown`). Withheld lapses still become gaps.
- `best_form` = tally Thompson pick, drawn once per session at start and re-drawn after every review outcome. The demo's "show a second form" key cycles `forms` locally on the client, no backend call.

## 7. LLM layer (FR-N2, FR-N3, FR-N4, FR-O4)

- Client: `AsyncOpenAI().responses.create(model, instructions, input, text={"format": {"type":"json_schema","name","schema","strict": true}}, max_output_tokens, reasoning={"effort":"minimal"})`. If the API rejects `reasoning` (non-reasoning model), retry once without it. No `temperature` is sent.
- Output parsed from `response.output_text` into the Pydantic model; one retry on validation error; then fallback.
- Cache: `llm_cache(key PRIMARY KEY, task, model, output_json, created_at)`, `key = sha256(task | model | prompt_version | canonical_json(input))`.
- Schemas (all `additionalProperties: false`, all fields required, as strict mode demands):

```
RecapForms      {plain, keyterm, analogy, sketch}                      each ≤ 25 words, one line, no markdown
SceneGraph      {title, nodes:[{id,label}] (3-7), edges:[{from,to,label}] (2-8), steps:[{highlight:[id], caption}] (2-6)}
FullForms       {plain (≤ 80 words), keyterm:{term, definition, example}, analogy (≤ 80 words), sketch:{line, diagram: SceneGraph}}
CheckQuestion   {question, options:[4], correct_index (0-3), explanation}
GapNote         {what_was_said, key_term, definition, connection}
GapPackage      {note: GapNote, question: CheckQuestion, forms: FullForms}
```

- Grounding rule in every prompt: use only the given transcript text; quote it; never introduce facts that are not in it; if the span is too thin, say so inside the field rather than inventing.
- Fallback (`fallback.py`): plain = last ~22 words of the span; keyterm = the rarest non-stopword token ≥ 6 letters (by frequency in the whole transcript) with the sentence it appears in; analogy and sketch = the plain line prefixed `(offline)`; question = "Which phrase was said in this part of the lecture?" with three distractor phrases from elsewhere in the transcript; diagram = nodes from the top 4 terms in a chain.

## 8. Core state

### 8.1 SQLite schema

```
learners(id PK, name, created_at, baseline_mu, baseline_sigma, baseline_at)
lectures(id PK, title, kind ('scripted'|'media'), media_path, transcript_json, segments_json, quiz_json, keyterms_json, created_at)
sessions(id PK, learner_id FK, lecture_id FK NULL, mode ('live'|'recorded'), catchup_policy ('always'|'randomized'),
         headset_kind, totem_kind, transcript_kind, best_form, status ('running'|'ended'|'reviewed'),
         started_at, ended_at, baseline_json, seed)
focus_samples(session_id, t, e, x, z, w15, quality, state, artifact, blink, paused)    index (session_id, t)
words(session_id, idx, w, start, end)                                                index (session_id, start)
flags(id PK, session_id, source ('tap'|'sim_tap'|'eeg'|'forced'), t_trigger, t_start, t_end,
      catchup_shown, catchup_form, opened, created_at)
recaps(session_id, t_from, t_to, forms_json, source)
gaps(id PK, session_id, ord, t_start, t_end, span_text, context_text, flag_ids_json, package_json, package_source,
     status ('open'|'closed'|'exhausted'))
cards(id PK, session_id, gap_id, ord, kind ('question'|'reteach'), form, shown_at, outcome ('hit'|'miss'|'drop'|NULL), choice)
tally(learner_id, form, rescues, attempts, PRIMARY KEY (learner_id, form))
quiz_answers(session_id, item_id, phase ('before'|'after'), choice, correct, PRIMARY KEY (session_id, item_id, phase))
llm_cache(key PK, task, model, output_json, created_at)
```

Plus `data/sessions/<id>.jsonl`: every broadcast message, one per line, for replay (FR-L14).

### 8.2 Tally (FR-T1..T5)

```
p_pop(form)   = (Σ_learners rescues(form) + 1) / (Σ_learners attempts(form) + 2)
prior(form)   = Beta(2·p_pop, 2·(1 − p_pop))
post(form)    = Beta(prior_a + rescues, prior_b + attempts − rescues)     (this learner)
pick          = argmax_form sample(post(form))                              (Thompson, seeded rng)
enough_data   = Σ_form attempts ≥ 12
rescue_rate   = rescues / attempts  (null if attempts = 0)
```

### 8.3 Review state machine (FR-R1..R6)

```
start(session): gaps in chronological order; streak = 0; for each gap forms_order = tally rank (posterior mean, desc)
card = question(gap[0])
answer(card, choice):
   hit  -> credit(form_before) if form_before; gap closed; streak += 1; if streak == 3 or no open gaps: done
   miss -> debit(form_before) if form_before; streak = 0;
           next_form = first of forms_order not used for this gap; if none: gap exhausted -> next gap
           else card = reteach(gap, next_form) ; after it, card = question(gap) again, form_before = next_form
drop(card): like miss for the switch, but no tally change (P6)
form_before for the first question of a gap = the live catch-up form if one was shown for any flag of that gap, else null
```

Rescue/attempt accounting: `credit(f)`: rescues += 1, attempts += 1. `debit(f)`: attempts += 1.

### 8.4 Loss map (FR-M1..M3)

```
bins of 10 s over the lecture length
per session s, bin b: z_sb = mean z over valid, unpaused samples in b (null if none)
                     tap_sb = 1 if any tap/sim_tap flag has t_trigger in b else 0
                     eeg_sb = 1 if any eeg flag overlaps b else 0
                     loss_sb = −z_sb + 1.0·tap_sb + 0.5·eeg_sb           (null z → use 0 for z if a tap exists, else null)
pooled_b = mean over sessions with non-null loss_sb ; n_b = count
peak     = argmax over windows of 4 consecutive bins of Σ pooled_b (report [t0, t0 + 40])
segments = rank by mean pooled_b over the segment's bins
```

Requires ≥ 2 sessions; otherwise returns `{n, ready: false}`.

### 8.5 Study analysis (FR-S4)

- Number 1: for each session, items whose span overlaps a flag (`flagged`) vs the rest; per-participant proportion correct in phase `before`; `paired_outcome(unflagged, flagged)`.
- Number 2: loss map segment ranking; report the rank of the planted segment and the peak window.
- Number 3: for lapses under `randomized`, items overlapping the missed span (benefit) and items overlapping `[t_end, t_end + 20]` (cost), shown vs withheld, per participant; `paired_outcome` on each.
- Number 4: tally rescues/attempts per form, pooled and per learner, descriptive.

## 9. API

### 9.1 REST (`/api`)

| Method, path | Body → response |
|---|---|
| `GET /health` | `{ok, version}` |
| `GET /doctor` | `{keys:{deepgram, openai}, openai_model:{name, available, alternatives}, headset:{port, kind}, totem:{port, kind}, frontend_built}` |
| `GET/POST /learners` | `{name}` → learner |
| `GET /learners/{id}/tally` | `{forms:{form:{rescues, attempts, rate, posterior_mean}}, pick, enough_data, total_attempts}` |
| `GET/POST /lectures` | `POST` multipart `{title, file?, script?, segments?, quiz?, keyterms?}` → lecture (media is transcribed via Deepgram prerecorded when a key exists) |
| `GET /lectures/{id}` | lecture without transcript words; `?full=1` includes them |
| `GET /lectures/{id}/lossmap` | §8.4 output |
| `POST /sessions` | `{learner_id, lecture_id?, mode, catchup_policy?, baseline_seconds?, use_stored_baseline?, auto_pause?}` → session |
| `GET /sessions/{id}` | session + counts + best_form + flags + gaps summary |
| `GET /sessions/{id}/events` | the JSONL as a JSON array (replay) |
| `POST /sessions/{id}/end` | ends the runtime, builds gaps and packages → `{gaps:[…]}` |
| `GET /sessions/{id}/notes` | `{gaps:[{id, t_start, t_end, span_text, note, question(without correct_index)}]}` |
| `POST /sessions/{id}/review/start` | → `{card, progress}` |
| `POST /sessions/{id}/review/answer` | `{card_id, choice}` → `{outcome, correct_index, explanation, next: card or null, done, streak, tally}` |
| `POST /sessions/{id}/review/drop` | `{card_id}` → `{next, …}` |
| `POST /sessions/{id}/review/advance` | `{card_id}` after a reteach card is read → `{next}` |
| `GET/POST /sessions/{id}/quiz` | `POST {phase, answers:{item_id: choice}}` → `{score, per_item}` |
| `POST /sessions/{id}/sim/headset` | `{state}` (also available over WS) |

Card shape: `{id, kind, gap_id, gap_ord, form, question?: {question, options}, reteach?: {form, content}, simulated_hint}` where `content` is the form's full-size payload (`plain` string, `keyterm` object, `analogy` string, `sketch` {line, diagram}).

### 9.2 WebSocket `/ws/session/{id}`

Text frames are JSON with a `type`; binary frames are PCM16 audio.

Server → client:

| type | payload |
|---|---|
| `hello` | `{session, learner, config, best_form, words, flags, recaps, focus, totem, headset, transcript_kind}` |
| `words` | `{words:[{w,start,end}], final}` |
| `focus` | `{t, e, x, z, w15, quality, state, baseline_ready, baseline_progress, artifact, blink, sim, paused}` |
| `flag_open` / `flag_close` | `{flag}` |
| `catchup` | `{flag_id, form, line, now_text, forms, source, ttl_s, auto_show, reason}` |
| `chip` | `{flag_id}` |
| `recap` | `{t_from, t_to, forms, source, best_form}` |
| `totem` | `{connected, kind, dots, fit, pulse}` |
| `headset` | `{connected, kind, port}` |
| `pause_request` | `{flag_id}` |
| `session_ended` | `{gaps}` |
| `notice` | `{level, text}` |

Client → server:

| type | payload |
|---|---|
| `tap` | `{}` (server stamps `source: "sim_tap"`; a real totem tap never comes from the client) |
| `force_flag` | `{}` (opens an EEG-style flag with `source: "forced"`, labelled simulated) |
| `sim_headset` | `{state: "focused"|"drifting"|"poor"}` |
| `media_time` | `{t, playing}` |
| `open_catchup` / `dismiss_catchup` | `{flag_id}` |
| `audio_start` / `audio_stop` | `{sample_rate}` / `{}` |
| `end` | `{}` |

## 10. Frontend (§ FR-L11, FR-N5, FR-R*, FR-T4, FR-M*)

Routes: `/` home (learners, lectures, start session, doctor status) · `/live/:sessionId` · `/notes/:sessionId` · `/review/:sessionId` · `/tally/:learnerId` · `/lossmap/:lectureId` · `/replay/:sessionId` · `/quiz/:sessionId`.

Live view layout: transcript column (final words normal, interim dim), focus trace canvas (180 s, z axis, −1.0 and −0.5 lines, drop bands, tap marks, blink ticks, baseline progress bar), status strip (headset kind, quality, totem kind, transcript kind, best form, policy), catch-up overlay (bottom center, one line, `opacity .85`, fades over `ttl_s`), chip (right edge), video element in recorded mode. Keys: `T` tap (simulated), `L` force flag (simulated), `F` cycle form on the visible card, `1/2/3` headset sim state, `E` end session. Every simulated action shows a "SIMULATED" badge for 2 s (P9).

Review view: card with the question; on miss the text dissolves (per-character opacity with random delays over 700 ms) into the next form; the sketch form renders the scene graph with a layered layout (longest-path layering, evenly spaced) and steps animate: nodes fade in, edges draw with `stroke-dashoffset`, captions crossfade; `Space` advances a step; "Continue" returns to the question.

Replay view: loads `/api/sessions/{id}/events` and plays it at 4× using the same components as the live view, badge "REPLAY 4×".

## 11. CLI

```
reflow serve [--host --port --reload]         start API + static frontend
reflow doctor                                  environment check (FR-O1)
reflow ingest-lecture --title T --file media   Deepgram prerecorded -> lecture row (needs key)
reflow ingest-script --title T --script s.json [--segments --quiz --keyterms]
reflow replay SESSION_ID [--speed 4]           print events to stdout at speed (headless check)
reflow study-analyze --lecture LEC_ID          the four numbers (§8.5)
reflow sim bandit|lossmap|selftest             the spec's simulations
reflow kaggle-check PATH/EEG_data.csv          hour-0 feature check on Wang et al. data
```

## 12. Testing

| Suite | Covers |
|---|---|
| `tests/test_thinkgear.py` | Framing, checksum, RAW sign, EEG power decoding, resync after garbage, simulator round-trip |
| `tests/test_features.py` | Band powers on synthetic tones, artifact rejection, baseline readiness, z, w15, hysteresis, refractory, lead-in, suppression during bad quality |
| `tests/test_blinks.py` | Blink bump counted once, noise not counted |
| `tests/test_spans.py` | Lead-in, sentence snapping caps, merging into gaps with min/max lengths |
| `tests/test_recaps.py` | Scheduler cadence, ring lookup rules, `now_text`, offline immediate recap |
| `tests/test_llm.py` | Schema strictness, cache hit, fallback on error/timeout, fallback outputs valid |
| `tests/test_tally.py` | Prior from population, Thompson pick reproducible with seed, enough_data threshold, matches `bandit_sim` behaviour on a 75/55 arm set |
| `tests/test_review.py` | State machine paths: hit-first, miss→reteach→hit, drop not scored, exhaustion, three-straight stop |
| `tests/test_lossmap.py` | Pooled peak on a planted drop, n < 2 gate, tap weighting, paused exclusion |
| `tests/test_api.py` | REST + WS end-to-end with simulated sources: session → tap → catch-up < 1 s → end → notes → review → tally |
| `tests/test_eval.py` | `reflow_eval` selftest passes, study analysis on synthetic sessions |
| `scripts/smoke_e2e.py` | Same as `test_api` against a running server, prints timings |
| frontend | `tsc --noEmit`, `vite build` |
| firmware | `arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi` and `:minima` |

## 13. Parameters (single source of truth: `reflow/config.py`)

| Name | Default | Used by |
|---|---|---|
| `baseline_seconds` | 180 | detector |
| `lead_in_seconds` | 8 | spans |
| `tap_snap_back_max` | 20 | spans |
| `tap_end_extend_max` | 5 | spans |
| `eeg_flag_max_seconds` | 30 | detector |
| `eeg_refractory_seconds` | 20 | detector |
| `drop_enter_z` / `drop_exit_z` | −1.25 / −0.6 | detector (env `REFLOW_DROP_ENTER_Z`, `REFLOW_DROP_EXIT_Z`) |
| `window_seconds` | 15 | detector |
| `ema_tau_seconds` | 8 | features |
| `recap_period_seconds` | 20 | recaps |
| `recap_window_seconds` | 30 | recaps |
| `recap_timeout_seconds` | 15 | llm |
| `catchup_ttl_seconds` | 6 | ui |
| `gap_merge_gap_seconds` | 10 | spans |
| `gap_min_seconds` / `gap_max_seconds` | 8 / 90 | spans |
| `tally_prior_pseudocount` | 2 | tally |
| `tally_enough_attempts` | 12 | tally |
| `review_stop_streak` | 3 | review |
| `lossmap_bin_seconds` / `lossmap_window_bins` | 10 / 4 | lossmap |
