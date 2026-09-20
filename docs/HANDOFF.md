# NeuroPace (Reflow) handoff for agents

State as of 19 Sep 2026, late night. Main is `8a1cb94` on github.com/brianzliu/neuropace. Read this, then `docs/PRODUCT.md` (product decisions) and `docs/TDD.md` (contracts). This file is not committed.

## What the product does

A student wears a NeuroSky MindWave Mobile 2 during a lecture. NeuroPace transcribes the lecture (Deepgram), tracks focus from the EEG, and when the student drifts (or presses a button) it shows a one-line catch-up. After the lecture it generates study material only for the moments they missed and restudies them, learning which kind of explanation works for this student.

## Ground rules from the user

- No CodeRabbit on this repo. Push with `CR_GATE=skip git push origin main` in its own tool call (a hook blocks any command containing `git push`).
- No API keys on student screens. Keys live in `.env` (gitignored) and on the Team page only.
- Signal processing runs on the laptop, never on the Arduino. The Arduino pad is optional; keyboard is the fallback (Space, T, on-screen button, terminal keys in `neuropace serve`).
- Nothing synthetic is shown as real without a label. Simulated headsets show "practice signal"; offline generation says "(offline)".
- Design: the teammate's Pocket Studio theme and shell stay. Our features go into it. Where the two differ in substance (feature, quality), ours wins.
- Never claim done without saying what was verified and how.
- No em dashes anywhere.

## Repo layout

```
neuropace/              Python package (renamed from reflow on 19 Sep; reflow/ is an import shim)
  api/routes.py         REST; api/ws.py websocket; api/app.py lifespan, orphan recovery
  core/session.py       SessionRuntime: one object per running session, 1 Hz step()
  core/review.py        ReviewEngine: restudy, two modes (tutor | manual)
  core/tally.py         preference model: Beta posteriors, Thompson pick, combined ranking
  core/gaps.py          regenerate packages, recover orphaned sessions
  llm/schemas.py        strict pydantic models: GapCore, the ten templates, pick_artifact
  llm/prompts.py        CORE_INSTRUCTIONS and one instruction per template (PROMPT_VERSION 5)
  llm/artifacts.py      build_package: two-stage generation with fallbacks
  llm/client.py         OpenAI or OpenRouter, strict JSON schema, cache, retries
  llm/fallback.py       extractive "(offline)" stand-ins (tests and REFLOW_ALLOW_OFFLINE_LLM=1 only)
  signal/headset.py     make_headset routing: sim | fake | replay:<dir> | serial:<port> | device path
  signal/features.py    FocusEngine: EMA, own-baseline z, 15 s window, drop detector
  signal/virtual_headset.py  a MindWave on a pty, real ThinkGear bytes
  tts.py                Deepgram Aura text to speech, cached under data/cache/tts
  totem/bridge.py       Arduino pad or keyboard; totem/uno_q.py teammate's optional relay
mindwave/               teammate's EEG pipeline (ThinkGear reader, 4 s windows, blinks, calibration)
frontend/src            Vite + React 19 + TS, react-router 7 data router
  views/Live.tsx        the lecture screen, quit-recording guard, mic auto-start
  views/Restudy.tsx     the lesson, tutor voice, ?mode=tutor|manual
  views/Artifacts.tsx   /team/artifacts/:session and /team/artifacts/sample (all ten templates)
  components/ArtifactView.tsx  the ten renderers
  components/BrainWaves.tsx, FocusCard.tsx  liveness judged from raw-chunk arrival time
  lib/tutor.ts          narration beats per template, /api/tts playback
  session-styles.css    our tokens and screen classes; styles.css/playful.css/pocket.css are the theme
tests/                  124 tests, `uv run pytest -q` (about 50 s)
docs/                   PRODUCT.md, TDD.md, PRD.md, VERIFICATION.md, DEMO-RUNBOOK.md
```

## Running it

```
cp .env.example .env            # DEEPGRAM_API_KEY is set; OPENAI_API_KEY is still empty
uv sync && cd frontend && pnpm install && pnpm build && cd ..
uv run neuropace serve --port 8765
```

Without an OpenAI key, sessions refuse to start (400). For local testing only: `NEUROPACE_ALLOW_OFFLINE_LLM=1` (or `REFLOW_...`, both work) enables the labelled extractive stand-ins.

Restart the server after any backend change; `pnpm build` after any frontend change (the server serves `frontend/dist`).

### Rehearsing with a headset that is not there

```
uv run neuropace virtual-headset --control /tmp/vh.ctl     # prints /dev/ttysNNN
NEUROPACE_HEADSET_PORT=/dev/ttysNNN NEUROPACE_ALLOW_OFFLINE_LLM=1 uv run neuropace serve
echo "state drowsy" > /tmp/vh.ctl    # drift within about 10 s
echo "state easy" > /tmp/vh.ctl      # back
echo "state off" > /tmp/vh.ctl       # electrode off, poor_signal 200
echo "pause 6" > /tmp/vh.ctl         # Bluetooth dropout for 6 s
```

The app sees kind `real`; only the bytes are synthetic. macOS and Linux only (needs a pty); on Windows use `headset=fake`.

## How the data flows

1. Headset bytes: `mindwave.MindWaveSource` reads the serial port, `mindwave.Pipeline` parses ThinkGear, computes one `FeatureFrame` per second (engagement = log10 beta minus log10(alpha plus theta), quality, valid, blinks) and a 64 Hz decimated raw trace.
2. `neuropace.signal.headset.MindwaveHeadset` hands frames and raw chunks to the asyncio loop.
3. `SessionRuntime._on_frame` feeds `FocusEngine.feed_frame`; `_on_raw_chunk` broadcasts `{"type":"raw","fs":64,"uv":[8 values]}` and records the arrival time.
4. `SessionRuntime.step()` runs once a second: focus sample with state baseline | ok | drop | bad | nosignal, drop detector events open EEG flags, headset status broadcast on change (connected, stream live), totem and headset hot-plug probes every 5 s.
5. A tap (pad or key) or an EEG flag builds a catch-up from the recap ring (rolling LLM recaps of the last 30 s; verbatim transcript if the API is down).
6. `end()` merges flags into gaps and calls `build_package` per gap.
7. The frontend reduces websocket messages in `lib/sessionState.ts`; `BrainWaves` and `FocusCard` judge "live" from `rawAt` (chunk within 2 s), never from a flag alone.

Headset routing: `auto` resolves to a device path when `mindwave.ports.find_headset_port` finds one, else `sim`. A session that started on `sim` with `auto` keeps probing and swaps in the real device (`_attach_headset_if_found`). A second lecture on the same real port gets 409.

## Generation (docs/PRODUCT.md section 4)

Per missed moment, `build_package`:

1. Core call, schema `GapCore`: note, check question, summary, key idea, and a plan `{visual, doing, why}`. The plan names which visual template (diagram, chart, plot, timeline, compare, animation) and which doing template (steps, example) the content calls for.
2. In parallel, one focused call per template: analogy, the planned visual, the planned doing. Each has its own strict schema and prompt (`TEMPLATE_INSTRUCTIONS[kind]`).
3. If the planned template fails, the family default is generated (diagram, example). If that fails, the family shows the words content (`pick_artifact`).

Package shape stored on the gap row:

```
{"note", "question", "artifacts": {"summary", "key_idea", "plan", "analogy", <visual>, <doing>, ...}, "sources": {kind: "llm"|"cache"|"failed"}}
```

Families (what the preference model learns about): words, analogy, visual, doing. Templates are chosen inside a family by content, never by preference. Animation is model-written inline SVG or canvas plus one script, validated (no network, storage, parent access, under 6000 chars) and rendered in `<iframe sandbox="allow-scripts">`.

Legacy packages (before the plan, with `applicable` flags) still render; `pick_artifact` handles both.

## Restudy (docs/PRODUCT.md section 5)

Two modes over one `ReviewEngine`, chosen by `POST /sessions/{id}/review/start {"mode": "tutor"|"manual"}` and the `?mode=` query on `/restudy/:id`.

- Private tutoring: each moment opens with an explanation in the family the model picks (Thompson sample; first unused by rank if already used for this gap), with `why` said out loud ("Pictures usually work best for you, so here it is that way"), `context` (where you were) and `said` (the span). The tutor voice reads beats (`lib/tutor.ts`, `POST /api/tts`) and advances the template's reveal step with the voice. Then the check.
- Review on my own: the check first, explanation only after a miss, no voice. A cold check scores nothing.

Scoring: every explanation-then-check pair credits or debits its family (rescues over attempts, Beta posterior with population prior). With a headset, the focus ratio of each explanation is stored on the card. `tally.summary` returns `rank` (0.6 understanding + 0.4 attention), `rank_understanding`, `preferred` (top once 12 explanations are scored), `pick` (Thompson on understanding). A drift during an explanation calls `review/drop`: switch family, no tally change.

Restudy sessions are headset-only runtimes (`mode: "review"`) on the wall clock with the lecture's stored baseline (`use_stored_baseline: true`), so focus counts from the first card.

## Key endpoints

| Path | Purpose |
|---|---|
| `GET /api/health` | `{ok, version, voice}` (voice = a Deepgram key is set) |
| `GET /api/doctor` | network checks: deepgram, openai, openrouter, tts, headset, totem |
| `GET /api/devices` | headset and pad detection only, cached 4 s, polled by the start screen |
| `POST /api/sessions` | `{lecture_id?, mode, headset?, totem?, baseline_seconds?, use_stored_baseline?}`; 409 if the real port is already recording |
| `POST /api/sessions/{id}/end` | builds gaps and packages |
| `GET /api/sessions/{id}/artifacts` | every artifact per moment, for the team preview |
| `POST /api/sessions/{id}/review/start\|answer\|drop\|advance` | the lesson |
| `POST /api/tts` | `{text}` to mp3, cached |
| `WS /ws/session/{id}` | hello snapshot, then words, focus, raw, flag_open, catchup, chip, headset, totem, notice, session_ended |

## Verification habit

```
uv run pytest -q                      # 124 passed
uv run ruff check neuropace tests && uv run ruff format --check neuropace tests
cd frontend && pnpm exec tsc --noEmit && pnpm build
```

Then a browser pass with the virtual headset (ego-browser was used): start screen shows "Headset connected.", practice lecture shows "live from your headset", `state drowsy` produces the chip, `pause 6` shows "Headset lost" then recovery, leaving the live screen asks "Do you want to quit recording?", both restudy modes, `/team/artifacts/sample` for all ten templates. Record the pass in `docs/VERIFICATION.md`.

## Known gaps and open items

- No OpenAI key on this machine: real generation of the templates has never run. First thing to do when a key exists: a full lecture, then `/team/artifacts/<session>` to inspect every template, especially animations.
- No real MindWave here: the pipeline was validated on a real head by its author on Windows; our numbers (drift latency, false flags) come from the simulator and the virtual headset.
- The live-microphone lecture stops at the browser's permission prompt in automation; verify by hand once.
- "Strengthen" (spaced re-checks across lectures) and a conversational voice agent are designed in PRODUCT.md, not built.
- The teammate's UNO Q relay (`uno-q:` headset setting) runs the pipeline on the board. Never chosen by `auto`; the user does not want signal processing on a board.
- The teammate's Home dashboard replaced ours (his design decision); our "Next up" and device line live on `/session/new` now.
- Windows execution has not been run; ports and console handling were reviewed only.
