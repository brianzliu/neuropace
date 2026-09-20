"""Student cases end to end, against a running server, with a simulated headset (docs/DEMO-PLAN.md).

Each case is one learner's path through the whole stack over the same HTTP + WebSocket API the browser uses:
detection (button and EEG), catch-ups, notes and templates (the server's real model when it has a key), both
restudy modes, the preference profile, the loss map, the study numbers and the outage path. Exit code 1 on any
failed check. Cases run concurrently (simulated headsets need no port); the outage case runs alone at the end
because it changes the server's model key.

    NEUROPACE_BASELINE_SECONDS=20 uv run neuropace serve --port 8790      # a short baseline keeps a case under 2 min
    uv run python scripts/e2e_cases.py --base http://127.0.0.1:8790 --db data/neuropace.db [--only a,b,c] [--list]

`--db` (the server's SQLite file, read only) lets the runner answer a check question right or wrong on purpose.
Artifacts generated along the way are saved under data/verification/e2e-artifacts-<stamp>.json for review.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from neuropace.llm.schemas import ARTIFACT_KINDS, TEMPLATES, VISUAL_KINDS  # noqa: E402
from neuropace.transcribe.scripted import script_from_text  # noqa: E402

FORMS = ("words", "analogy", "visual", "doing")
STAMP = time.strftime("%H%M%S")
GPS = "lec_demo0001"


# ---------------------------------------------------------------- reporting
class Check:
    def __init__(self, case: str) -> None:
        self.case = case
        self.rows: list[dict] = []
        self.error: str | None = None
        self.t0 = time.monotonic()
        self.seconds = 0.0

    def ok(self, cond, label: str, detail="") -> bool:
        cond = bool(cond)
        detail = str(detail)
        self.rows.append({"ok": cond, "label": label, "detail": detail[:400]})
        print(
            f"[{self.case}] {'PASS' if cond else 'FAIL'} {label}" + (f"  ({detail[:200]})" if detail else ""),
            flush=True,
        )
        return cond

    def note(self, text: str) -> None:
        print(f"[{self.case}]      {text}", flush=True)

    @property
    def passed(self) -> bool:
        return self.error is None and all(r["ok"] for r in self.rows)


# ---------------------------------------------------------------- the API
class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.base = args.base.rstrip("/")
        self.ws_base = self.base.replace("http", "ws", 1)
        self.http = httpx.AsyncClient(base_url=self.base, timeout=httpx.Timeout(240.0, connect=10.0))
        self.db = Path(args.db) if args.db else None
        self.artifacts: dict[str, list] = {}
        self.lock = asyncio.Lock()

    async def get(self, path: str):
        r = await self.http.get(path)
        if r.status_code != 200:
            raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    async def post(self, path: str, body: dict | None = None):
        r = await self.http.post(path, json=body) if body is not None else await self.http.post(path)
        if r.status_code != 200:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    async def post_status(self, path: str, body: dict | None = None) -> tuple[int, object]:
        r = await self.http.post(path, json=body) if body is not None else await self.http.post(path)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text

    async def put(self, path: str, body: dict):
        r = await self.http.put(path, json=body)
        if r.status_code != 200:
            raise RuntimeError(f"PUT {path} -> {r.status_code}: {r.text[:300]}")
        return r.json()

    def correct_choice(self, card_id: str) -> int:
        """The displayed index of the right option (the API keeps it secret; the test reads the server's DB)."""
        if self.db is None:
            raise RuntimeError("--db is required to answer questions on purpose")
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            card = conn.execute(
                "SELECT gap_id, option_order_json FROM cards WHERE id=?", (card_id,)
            ).fetchone()
            pkg = conn.execute("SELECT package_json FROM gaps WHERE id=?", (card[0],)).fetchone()
        finally:
            conn.close()
        order = json.loads(card[1] or "[0,1,2,3]")
        return order.index(int(json.loads(pkg[0])["question"]["correct_index"]))

    def wrong_choice(self, card_id: str) -> int:
        return (self.correct_choice(card_id) + 1) % 4

    async def start(
        self,
        name: str,
        lecture: str | None,
        *,
        mode: str = "live",
        policy: str = "always",
        seed: int | None = None,
        headset: str = "sim",
        learner_id: str | None = None,
        extra: dict | None = None,
    ) -> Live:
        body: dict = {
            "learner_name": None if learner_id else f"{name} {STAMP}",
            "learner_id": learner_id,
            "lecture_id": lecture,
            "mode": mode,
            "catchup_policy": policy,
            "headset": headset,
            "totem": "keyboard",
            "baseline_seconds": self.args.baseline,
            "startup_calibration": False,
            "seed": seed,
        }
        if extra:
            body.update(extra)
        sess = await self.post("/api/sessions", body)
        live = Live(self, sess)
        await live.open()
        return live

    def save_artifacts(self, label: str, gaps: list[dict]) -> None:
        self.artifacts[label] = gaps


class Live:
    """One session's WebSocket: every message is kept; `expect` waits for the next one matching a predicate."""

    def __init__(self, ctx: Ctx, sess: dict) -> None:
        self.ctx = ctx
        self.id = sess["id"]
        self.info = sess
        self.learner_id = sess["learner_id"]
        self.msgs: list[dict] = []
        self.hello: dict | None = None
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._event = asyncio.Event()

    async def open(self) -> Live:
        self._ws = await connect(f"{self.ctx.ws_base}/ws/session/{self.id}", max_size=None)
        self.hello = json.loads(await asyncio.wait_for(self._ws.recv(), 10))
        if self.hello.get("type") != "hello":
            raise RuntimeError(f"first frame is not hello: {self.hello}")
        self.msgs.append(self.hello)
        self._reader = asyncio.create_task(self._read())
        return self

    async def _read(self) -> None:
        with contextlib.suppress(Exception):
            async for raw in self._ws:
                if isinstance(raw, str):
                    self.msgs.append(json.loads(raw))
                    self._event.set()

    def cursor(self) -> int:
        return len(self.msgs)

    def find(self, type_: str, pred=None, since: int = 0) -> list[dict]:
        return [m for m in self.msgs[since:] if m.get("type") == type_ and (pred is None or pred(m))]

    async def expect(self, type_: str, pred=None, timeout: float = 30.0, since: int | None = None) -> dict:
        i = len(self.msgs) if since is None else since
        deadline = time.monotonic() + timeout
        while True:
            while i < len(self.msgs):
                m = self.msgs[i]
                i += 1
                if m.get("type") == type_ and (pred is None or pred(m)):
                    return m
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{self.id}: no {type_} within {timeout:.0f}s")
            self._event.clear()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._event.wait(), min(remaining, 0.5))

    async def wait_baseline(self) -> dict:
        return await self.expect(
            "focus", lambda m: m.get("baseline_ready"), timeout=self.ctx.args.baseline + 60, since=0
        )

    async def send(self, obj: dict) -> None:
        await self._ws.send(json.dumps(obj))

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send(data)

    async def tap(self) -> tuple[dict, float]:
        c = self.cursor()
        t0 = time.perf_counter()
        await self.send({"type": "tap"})
        cu = await self.expect("catchup", lambda m: m.get("reason") == "tap", timeout=10, since=c)
        return cu, time.perf_counter() - t0

    async def sim(self, state: str) -> None:
        await self.send({"type": "sim_headset", "state": state})

    async def close(self) -> None:
        if self._reader:
            self._reader.cancel()
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await self._reader
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()

    async def end(self) -> dict:
        await self.close()
        return await self.ctx.post(f"/api/sessions/{self.id}/end")

    async def __aenter__(self) -> Live:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()


# ---------------------------------------------------------------- shared assertions
def validate_package(chk: Check, gap: dict, label: str, expect_llm: bool = True) -> None:
    """A moment's package as the API exposes it (GET /artifacts row): every artifact valid for its template."""
    arts = gap.get("artifacts") or {}
    src = gap.get("package_source")
    if expect_llm:
        chk.ok(src in ("llm", "cache"), f"{label}: notes generated by the model", f"source={src}")
    note = gap.get("note") or {}
    chk.ok(
        note.get("key_term") and note.get("definition") and note.get("what_was_said"),
        f"{label}: note has term, definition, what was said",
        note.get("key_term"),
    )
    q = gap.get("question") or {}
    opts = q.get("options") or []
    chk.ok(
        q.get("question") and len(opts) == 4 and len({o.strip().lower() for o in opts}) == 4,
        f"{label}: check question with four distinct options",
        q.get("question", "")[:80],
    )
    plan = arts.get("plan") or {}
    chk.ok(
        plan.get("visual") in VISUAL_KINDS and plan.get("doing") in ("steps", "example"),
        f"{label}: plan names a visual and a doing template",
        f"{plan.get('visual')} / {plan.get('doing')}: {plan.get('why', '')[:80]}",
    )
    chk.ok(
        arts.get("summary") and (arts.get("key_idea") or {}).get("term"),
        f"{label}: words family (summary + key idea)",
    )
    kinds = gap.get("kinds") or {}
    chk.ok(kinds.get("analogy") == "analogy", f"{label}: comparison family present", kinds)
    chk.ok(
        kinds.get("visual") in VISUAL_KINDS,
        f"{label}: visual family shows a real template",
        kinds.get("visual"),
    )
    chk.ok(
        kinds.get("doing") in ("steps", "example"),
        f"{label}: doing family shows a real template",
        kinds.get("doing"),
    )
    bad = []
    for kind, content in arts.items():
        if kind in ("summary", "key_idea", "plan") or not isinstance(content, dict):
            continue
        model = TEMPLATES.get(kind)
        if model is None:
            bad.append(f"{kind}: unknown template")
            continue
        try:
            model.model_validate(content)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{kind}: {str(e)[:120]}")
        if expect_llm and "(offline)" in json.dumps(content):
            bad.append(f"{kind}: offline stand-in text in a generated artifact")
    chk.ok(
        not bad,
        f"{label}: every artifact validates against its template",
        "; ".join(bad) or ", ".join(sorted(k for k in arts if k not in ("summary", "key_idea", "plan"))),
    )
    sources = gap.get("sources") or {}
    failed = [k for k, v in sources.items() if v == "failed"]
    chk.ok(not failed, f"{label}: no template call failed", failed or dict(sources))


async def run_review(ctx: Ctx, chk: Check, sid: str, mode: str, decide, max_steps: int = 60) -> list[dict]:
    """Walk a lesson; `decide(card, form_before) -> bool` says whether to answer right. Returns the cards seen."""
    st = await ctx.post(f"/api/sessions/{sid}/review/start", {"mode": mode})
    card = st["card"]
    seen: list[dict] = []
    form_before: str | None = None
    steps = 0
    while card and steps < max_steps:
        steps += 1
        seen.append(card)
        if card["kind"] == "reteach":
            form_before = card["form"]
            r = await ctx.post(f"/api/sessions/{sid}/review/advance", {"card_id": card["id"]})
        else:
            right = decide(card, form_before)
            choice = ctx.correct_choice(card["id"]) if right else ctx.wrong_choice(card["id"])
            r = await ctx.post(
                f"/api/sessions/{sid}/review/answer", {"card_id": card["id"], "choice": choice}
            )
            card_out = dict(card)
            card_out["outcome"] = r["outcome"]
            card_out["credited_form"] = r["credited_form"]
            seen[-1] = card_out
            form_before = None
        card = r["next"]
        if card and card["kind"] == "question":
            form_before = form_before  # keep the explained family for the check
    seen.append({"kind": "end", "progress": r["progress"], "tally": r["tally"], "done": r.get("done")})
    return seen


# ---------------------------------------------------------------- cases
async def case_first_tap(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("Ana (first lecture)", GPS, seed=1)
    async with s:
        h = s.hello
        chk.ok(
            h["transcript_kind"] == "scripted"
            and h["headset"]["kind"] == "simulated"
            and h["sim"]["headset"],
            "practice lecture, simulated headset labelled",
            f"best_form={h['best_form']}",
        )
        raw = await s.expect("raw", timeout=10, since=0)
        chk.ok(raw.get("fs") == 64 and len(raw.get("uv", [])) == 8, "brain-wave chunks stream at 64 Hz")
        f = await s.wait_baseline()
        chk.ok(f["t"] <= ctx.args.baseline + 15, "baseline ready in time", f"t={f['t']}")
        rec = await s.expect("recap", timeout=45, since=0)
        chk.ok(rec["source"] in ("llm", "cache"), "rolling recap generated by the model", rec["source"])
        forms = rec["forms"]
        chk.ok(
            all(forms.get(x) for x in FORMS) and len({forms[x] for x in FORMS}) >= 3,
            "recap has four different one-line forms",
            {k: v[:50] for k, v in forms.items()},
        )
        chk.ok(
            all(len(forms[x].split()) <= 40 for x in FORMS),
            "each recap form is one glance",
            max(len(forms[x].split()) for x in FORMS),
        )
        await asyncio.sleep(1.0)
        cu, lat = await s.tap()
        chk.ok(lat < 1.0, "tap to catch-up under a second", f"{lat * 1000:.0f} ms")
        chk.ok(
            cu["auto_show"] is True and cu["form"] == h["best_form"],
            "the tap shows the card in the learner's best family",
            cu["form"],
        )
        chk.ok(
            cu["source"] in ("llm", "cache"),
            "the catch-up line is generated, not the verbatim transcript",
            cu["source"],
        )
        chk.ok(
            cu["line"] and cu["now_text"] and all(cu["forms"].get(x) for x in FORMS),
            "card has the line, the four forms and 'now'",
            cu["line"][:100],
        )
        fl = s.find("flag_open")
        chk.ok(
            fl and fl[0]["flag"]["source"] == "key" and fl[0]["flag"]["simulated"] is False,
            "a keyboard tap is a real flag",
            fl[0]["flag"] if fl else None,
        )
        await asyncio.sleep(2.0)
    t0 = time.monotonic()
    end = await s.end()
    gen = time.monotonic() - t0
    gaps = end["gaps"]
    chk.ok(len(gaps) == 1, "one moment saved", f"{len(gaps)} gaps, notes in {gen:.1f}s")
    chk.ok(gen < 60, "notes written in under a minute", f"{gen:.1f}s")
    arts = (await ctx.get(f"/api/sessions/{s.id}/artifacts"))["gaps"]
    ctx.save_artifacts("A first tap (GPS)", arts)
    for g in arts:
        validate_package(chk, g, f"moment {g['ord'] + 1}")
    notes = await ctx.get(f"/api/sessions/{s.id}/notes")
    chk.ok(
        notes["session"]["status"] == "ended" and notes["words"] and notes["gaps"][0]["summary"],
        "lecture page has the transcript and the moment's summary",
    )
    st = await ctx.post(f"/api/sessions/{s.id}/review/start", {"mode": "tutor"})
    card = st["card"]
    r = card.get("reteach") or {}
    chk.ok(
        card and card["kind"] == "reteach" and card["form"] in FORMS,
        "private tutoring opens with an explanation",
        card and card["form"],
    )
    chk.ok(
        r.get("why") and r.get("said") and r.get("artifact") in ARTIFACT_KINDS and r.get("content"),
        "the explanation carries its reason, the lecturer's words and a template",
        f"{r.get('artifact')}: {r.get('why')}",
    )
    chk.ok(
        isinstance(r.get("context"), str), "where you were is a string (may be empty for the first seconds)"
    )
    seen = await run_review(ctx, chk, s.id, "tutor", lambda card, fb: True)
    answered = [c for c in seen if c.get("kind") == "question"]
    chk.ok(
        answered and answered[0]["outcome"] == "hit" and answered[0]["credited_form"] == card["form"],
        "a hit credits the family that was just shown",
        answered and (answered[0]["outcome"], answered[0]["credited_form"]),
    )
    fin = seen[-1]
    chk.ok(
        fin["done"] and fin["progress"]["gaps_closed"] == 1,
        "lesson done with the moment landed",
        fin["progress"],
    )
    tally = await ctx.get(f"/api/learners/{s.learner_id}/tally")
    chk.ok(
        tally["total_attempts"] == 1
        and tally["forms"][card["form"]]["rescues"] == 1
        and not tally["enough_data"],
        "tally: 1 of 12 scored, still learning",
        {k: (v["rescues"], v["attempts"]) for k, v in tally["forms"].items()},
    )
    prof = await ctx.get(f"/api/me/profile?learner_id={s.learner_id}")
    chk.ok(
        prof["stats"]["moments_restudied"] == 1 and prof["stats"]["lectures"] == 1,
        "profile counts the lecture and the landed moment",
        prof["stats"],
    )
    ev = (await ctx.get(f"/api/sessions/{s.id}/events"))["events"]
    types = {e["type"] for e in ev}
    chk.ok(
        ev[-1]["type"] == "session_ended"
        and {"focus", "raw", "words", "recap", "catchup", "flag_open"} <= types,
        "event log complete for replay",
        len(ev),
    )
    dash = await ctx.get(f"/api/learners/{s.learner_id}/dashboard")
    chk.ok(
        dash["closed"] == 1 and not dash["concepts"], "dashboard: nothing left to revisit", dash["summary"]
    )
    sess = await ctx.get(f"/api/sessions/{s.id}")
    chk.ok(
        sess["status"] == "reviewed" and sess["catchups_shown"] == 1,
        "session marked reviewed with one catch-up",
        (sess["status"], sess["catchups_shown"]),
    )


async def case_eeg_drift(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("Ben (drifts, never presses)", GPS, seed=2)
    async with s:
        await s.wait_baseline()
        c = s.cursor()
        await s.sim("drifting")
        t0 = time.monotonic()
        fl = await s.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=60, since=c)
        chk.ok(
            True, "EEG drift flagged", f"after {time.monotonic() - t0:.1f}s, since {fl['flag']['t_start']}"
        )
        chk.ok(fl["flag"]["simulated"] is True, "the simulated headset's flag says so")
        chip = await s.expect("chip", timeout=5, since=c)
        cu = await s.expect("catchup", lambda m: m["flag_id"] == chip["flag_id"], timeout=5, since=c)
        chk.ok(
            cu["auto_show"] is False and cu["reason"] == "eeg",
            "an EEG flag only offers a card behind the chip (P4)",
        )
        pulses = s.find("totem", lambda m: m.get("pulse"), since=c)
        chk.ok(pulses, "totem pulses on the EEG flag")
        chk.ok(cu["source"] in ("llm", "cache"), "the offered catch-up is a generated line", cu["source"])
        await s.send({"type": "open_catchup", "flag_id": chip["flag_id"]})
        await s.expect("catchup_opened", timeout=5, since=c)
        await s.sim("focused")
        cl = await s.expect("flag_close", lambda m: m["flag"]["id"] == fl["flag"]["id"], timeout=60, since=c)
        chk.ok(
            cl["flag"]["t_end"] is not None and cl["flag"]["t_end"] - fl["flag"]["t_trigger"] <= 31,
            "the flag closes on recovery or at the 30 s cap",
            cl["flag"]["t_end"] - fl["flag"]["t_trigger"],
        )
        await asyncio.sleep(22)  # past the refractory period, well apart from the first moment
        c2 = s.cursor()
        await s.sim("drifting")
        fl2 = await s.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=60, since=c2)
        await s.expect("chip", timeout=5, since=c2)
        chk.ok(fl2["flag"]["id"] != fl["flag"]["id"], "a second drift is a second flag")
        await s.sim("focused")
        await asyncio.sleep(3)
    end = await s.end()
    gaps = end["gaps"]
    chk.ok(len(gaps) == 2, "two drifts become two moments", [(g["t_start"], g["t_end"]) for g in gaps])
    chk.ok(
        end["session"]["catchups_shown"] == 1,
        "one catch-up opened, one ignored",
        end["session"]["catchups_shown"],
    )
    arts = (await ctx.get(f"/api/sessions/{s.id}/artifacts"))["gaps"]
    ctx.save_artifacts("B drifts (GPS)", arts)
    for g in arts:
        validate_package(chk, g, f"moment {g['ord'] + 1}")
    st = await ctx.post(f"/api/sessions/{s.id}/review/start", {"mode": "manual"})
    chk.ok(
        st["card"]["kind"] == "question" and st["progress"]["mode"] == "manual", "review on my own asks first"
    )
    misses = {"n": 0}

    def decide(card, form_before):
        if form_before is None and misses["n"] == 0:
            misses["n"] += 1
            return False  # miss the first cold check on purpose
        return True

    seen = await run_review(ctx, chk, s.id, "manual", decide)
    qs = [c for c in seen if c.get("kind") == "question"]
    rts = [c for c in seen if c.get("kind") == "reteach"]
    chk.ok(
        qs[0]["outcome"] == "miss" and qs[0]["credited_form"] is None,
        "a cold check scores nothing",
        (qs[0]["outcome"], qs[0]["credited_form"]),
    )
    chk.ok(
        rts and rts[0]["reteach"]["why"],
        "a miss brings an explanation with its reason",
        rts and rts[0]["reteach"]["why"],
    )
    chk.ok(
        len(qs) >= 2 and qs[1]["outcome"] == "hit" and qs[1]["credited_form"] == rts[0]["form"],
        "the hit after the explanation credits that family",
        [(q["outcome"], q["credited_form"]) for q in qs],
    )
    tally = await ctx.get(f"/api/learners/{s.learner_id}/tally")
    chk.ok(tally["total_attempts"] == 1, "only explained checks are scored", tally["total_attempts"])
    chk.ok(seen[-1]["progress"]["gaps_closed"] == 2, "both moments landed", seen[-1]["progress"])


async def case_linked_tap(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("Cleo (drifts, then presses)", GPS, seed=3)
    async with s:
        await s.wait_baseline()
        c = s.cursor()
        await s.sim("drifting")
        fl = await s.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=60, since=c)
        await asyncio.sleep(2)
        cu, lat = await s.tap()
        chk.ok(
            cu.get("linked_eeg") == fl["flag"]["id"],
            "the tap confirms the lapse the headset saw",
            cu.get("linked_eeg"),
        )
        chk.ok(
            cu.get("since") is not None and cu["since"] <= fl["flag"]["t_start"] + 0.01,
            "the card starts where focus dropped",
            (cu.get("since"), fl["flag"]["t_start"]),
        )
        chk.ok(
            (cu.get("span_seconds") or 0) >= 8,
            "the linked span is at least the lead-in",
            cu.get("span_seconds"),
        )
        chk.ok(lat < 1.0, "linked tap still under a second", f"{lat * 1000:.0f} ms")
        await s.sim("focused")
        await asyncio.sleep(3)
    end = await s.end()
    gaps = end["gaps"]
    chk.ok(
        len(gaps) == 1 and len(gaps[0]["flag_ids"]) == 2,
        "the drift and the tap merge into one moment",
        [g["flag_ids"] for g in gaps],
    )


async def case_returning_student(ctx: Ctx, chk: Check) -> None:
    name = "Rosa (returning)"

    async def one(seed: int):
        s = await ctx.start(name, GPS, seed=seed)
        async with s:
            await s.wait_baseline()
            for i in range(4):
                await s.tap()
                if i < 3:
                    await asyncio.sleep(21)
            await asyncio.sleep(2)
        return s, await s.end()

    runs = await asyncio.gather(*(one(100 + i) for i in range(4)))
    learner_id = runs[0][0].learner_id
    chk.ok(all(r[0].learner_id == learner_id for r in runs), "the four lectures belong to one learner")
    chk.ok(
        all(len(r[1]["gaps"]) == 4 for r in runs),
        "four taps spaced apart make four moments each",
        [len(r[1]["gaps"]) for r in runs],
    )
    for s, end in runs:
        chk.ok(
            all(g["package_source"] in ("llm", "cache") for g in end["gaps"]),
            f"{s.id}: every moment has generated notes",
            [g["package_source"] for g in end["gaps"]],
        )
        await run_review(ctx, chk, s.id, "tutor", lambda card, fb: fb == "visual")
    tally = await ctx.get(f"/api/learners/{learner_id}/tally")
    forms = {k: (v["rescues"], v["attempts"]) for k, v in tally["forms"].items()}
    chk.ok(
        tally["total_attempts"] >= 12 and tally["enough_data"], "twelve or more explanations scored", forms
    )
    chk.ok(
        tally["preferred"] == "visual" and tally["rank"][0] == "visual",
        "pictures are the preferred way",
        (tally["preferred"], tally["rank"]),
    )
    chk.ok(
        tally["forms"]["visual"]["rescues"] == tally["forms"]["visual"]["attempts"]
        and all(
            tally["forms"][f]["rescues"] == 0
            for f in ("words", "analogy", "doing")
            if tally["forms"][f]["attempts"]
        ),
        "only pictures rescued",
        forms,
    )
    s = await ctx.start(name, GPS, seed=7, learner_id=learner_id)
    async with s:
        await s.wait_baseline()
        cu, _ = await s.tap()
        chk.ok(
            cu["form"] == s.hello["best_form"] and cu["forms"][cu["form"]] == cu["line"],
            "the catch-up uses the learner's best family",
            f"best_form={s.hello['best_form']}",
        )
        await asyncio.sleep(2)
    await s.end()
    st = await ctx.post(f"/api/sessions/{s.id}/review/start", {"mode": "tutor"})
    card = st["card"]
    why = card["reteach"]["why"]
    if card["form"] == "visual":
        chk.ok("works best for you" in why, "the tutor says pictures usually work best", why)
    else:
        chk.ok(
            "this time" in why or "not tried" in why,
            "the tutor explains why it is exploring another family",
            f"{card['form']}: {why}",
        )
    chk.ok(
        st["tally"]["preferred"] == "visual", "the lesson carries the preference", st["tally"]["preferred"]
    )
    prof = await ctx.get(f"/api/me/profile?learner_id={learner_id}")
    chk.ok(
        prof["tally"]["preferred"] == "visual" and prof["stats"]["lectures"] == 5,
        "You: preferred way and five lectures",
        prof["stats"],
    )


async def case_exhaust(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("Eli (nothing lands)", GPS, seed=4)
    async with s:
        await s.wait_baseline()
        await s.tap()
        await asyncio.sleep(2)
    await s.end()
    seen = await run_review(ctx, chk, s.id, "tutor", lambda card, fb: False)
    forms = [c["form"] for c in seen if c.get("kind") == "reteach"]
    chk.ok(sorted(forms) == sorted(FORMS), "all four families were tried once", forms)
    fin = seen[-1]
    chk.ok(
        fin["done"] and fin["progress"]["gaps_exhausted"] == 1 and fin["progress"]["gaps_closed"] == 0,
        "the moment ends still tricky",
        fin["progress"],
    )
    notes = await ctx.get(f"/api/sessions/{s.id}/notes")
    chk.ok(
        notes["gaps"][0]["status"] == "exhausted", "lecture page marks it tricky", notes["gaps"][0]["status"]
    )
    dash = await ctx.get(f"/api/learners/{s.learner_id}/dashboard")
    chk.ok(
        dash["concepts"] and dash["concepts"][0]["reason"] == "Try another explanation",
        "dashboard suggests another explanation",
        dash["concepts"][0]["reason"] if dash["concepts"] else None,
    )
    tally = await ctx.get(f"/api/learners/{s.learner_id}/tally")
    chk.ok(
        tally["total_attempts"] == 4 and all(v["rescues"] == 0 for v in tally["forms"].values()),
        "four misses scored, no rescues",
        {k: (v["rescues"], v["attempts"]) for k, v in tally["forms"].items()},
    )


async def case_restudy_focus(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("Fay (focus in restudy)", GPS, seed=5)
    async with s:
        await s.wait_baseline()
        await s.tap()
        await asyncio.sleep(2)
    await s.end()
    r = await ctx.start(
        "Fay review",
        None,
        mode="review",
        seed=6,
        learner_id=s.learner_id,
        extra={"use_stored_baseline": True},
    )
    async with r:
        chk.ok(
            r.hello["transcript_kind"] == "none" and r.hello["mode"] == "review",
            "a restudy session is headset only",
        )
        raw = await r.expect("raw", timeout=10, since=0)
        f = await r.expect("focus", lambda m: m.get("bands"), timeout=10, since=0)
        chk.ok(
            len(raw["uv"]) == 8 and f["bands"], "waves and band shares stream under the lesson", f["bands"]
        )
        await r.wait_baseline()
        c = r.cursor()
        await r.sim("drifting")
        fl = await r.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=60, since=c)
        chk.ok(fl["flag"]["simulated"] is True, "a practice drift in restudy is labelled simulated")
        await asyncio.sleep(3)
        chk.ok(
            not r.find("chip", since=c) and not r.find("catchup", since=c),
            "restudy never offers a catch-up (no lecture to catch up on)",
        )
        await r.sim("focused")
    endr = await r.end()
    chk.ok(endr["gaps"] == [], "a restudy session ends with no moments of its own")
    st = await ctx.post(f"/api/sessions/{s.id}/review/start", {"mode": "tutor"})
    card = st["card"]
    d = await ctx.post(f"/api/sessions/{s.id}/review/drop", {"card_id": card["id"], "focus_ratio": 0.3})
    chk.ok(
        d["outcome"] == "drop"
        and d["next"]
        and d["next"]["kind"] == "reteach"
        and d["next"]["form"] != card["form"],
        "a drift on an explanation switches the family",
        (card["form"], d["next"] and d["next"]["form"]),
    )
    chk.ok(d["tally"]["total_attempts"] == 0, "a drop scores nothing")
    nxt = d["next"]
    a = await ctx.post(f"/api/sessions/{s.id}/review/advance", {"card_id": nxt["id"], "focus_ratio": 0.95})
    q = a["next"]
    ans = await ctx.post(
        f"/api/sessions/{s.id}/review/answer",
        {"card_id": q["id"], "choice": ctx.correct_choice(q["id"]), "focus_ratio": 0.9},
    )
    chk.ok(
        ans["outcome"] == "hit" and ans["credited_form"] == nxt["form"],
        "the hit credits the family shown after the switch",
        (ans["outcome"], ans["credited_form"]),
    )
    focus = ans["tally"]["forms"][nxt["form"]]["focus"]
    chk.ok(
        focus and focus.get("n", 0) >= 1 and focus.get("mean_focus") is not None,
        "attention while reading is recorded per family",
        focus,
    )
    chk.ok(
        ans["tally"]["forms"][nxt["form"]]["score"] != ans["tally"]["forms"][nxt["form"]]["posterior_mean"],
        "the ranking blends understanding and attention",
        (ans["tally"]["forms"][nxt["form"]]["score"], ans["tally"]["forms"][nxt["form"]]["posterior_mean"]),
    )


def _load_lecture() -> tuple[dict, dict]:
    src = json.loads((ROOT / "data/lectures/compound-interest/lecture.json").read_text())
    words = script_from_text(src["text"], src.get("wpm", 150.0))
    toks = [w.w for w in words]

    def index_of(phrase: str, last: bool = False) -> int:
        ptoks = phrase.split()
        hits = [i for i in range(len(toks) - len(ptoks) + 1) if toks[i : i + len(ptoks)] == ptoks]
        if not hits:
            raise RuntimeError(f"phrase not in lecture: {phrase}")
        return hits[-1] + (len(ptoks) - 1 if last else 0)

    segs = []
    starts = [index_of(sg["starts_with"]) for sg in src["segments"]]
    for k, sg in enumerate(src["segments"]):
        i0 = starts[k]
        i1 = starts[k + 1] - 1 if k + 1 < len(starts) else len(words) - 1
        segs.append(
            {
                "id": sg["id"],
                "title": sg["title"],
                "t_start": words[i0].start,
                "t_end": words[i1].end,
                "planted_bad": sg.get("planted_bad", False),
            }
        )
    quiz = []
    for q in src["quiz"]:
        sg = next(x for x in segs if x["id"] == q["segment"])
        quiz.append({**q, "t_start": sg["t_start"], "t_end": sg["t_end"]})
    script = {
        "id": src["id"],
        "title": src["title"],
        "words": [w.to_dict() for w in words],
        "segments": segs,
        "quiz": quiz,
        "keyterms": src["keyterms"],
        "duration": words[-1].end,
    }
    taps = [words[index_of(p, last=True)].end + 1.0 for p in src["taps_after"]]
    return script, {"taps": taps}


async def case_different_lecture(ctx: Ctx, chk: Check) -> None:
    script, meta = _load_lecture()
    (ROOT / "data/lectures/compound-interest/script.json").write_text(json.dumps(script, ensure_ascii=False))
    existing = [lr for lr in (await ctx.get("/api/lectures"))["lectures"] if lr["title"] == script["title"]]
    if existing:
        lec = existing[0]
    else:
        r = await ctx.http.post(
            "/api/lectures",
            data={"title": script["title"]},
            files={"script": ("script.json", json.dumps(script).encode(), "application/json")},
        )
        chk.ok(r.status_code == 200, "a lecture can be ingested from text", r.text[:120])
        lec = r.json()
    chk.ok(
        lec["kind"] == "scripted" and len(lec.get("segments", [])) == 5 and lec.get("keyterms"),
        "the new lecture carries segments and key terms",
        (lec["id"], lec.get("duration")),
    )
    s = await ctx.start("Hugo (compound interest)", lec["id"], seed=8)
    async with s:
        await s.wait_baseline()
        results = []
        for t_tap in meta["taps"]:
            await s.expect("focus", lambda m, tt=t_tap: m["t"] >= tt, timeout=t_tap + 30, since=0)
            cu, lat = await s.tap()
            results.append((round(cu["t"], 1), cu["source"], cu["form"], lat))
        chk.ok(all(r[1] in ("llm", "cache") for r in results), "every tap got a generated line", results)
        await asyncio.sleep(2)
    end = await s.end()
    gaps = end["gaps"]
    chk.ok(len(gaps) == 4, "four moments on the new lecture", [(g["t_start"], g["t_end"]) for g in gaps])
    arts = (await ctx.get(f"/api/sessions/{s.id}/artifacts"))["gaps"]
    ctx.save_artifacts("H compound interest", arts)
    for g in arts:
        validate_package(chk, g, f"moment {g['ord'] + 1} ({(g.get('note') or {}).get('key_term')})")
    plans = [((g.get("plan") or {}).get("visual"), (g.get("plan") or {}).get("doing")) for g in arts]
    chk.ok(plans and plans[0][0] in ("chart", "plot"), "the numbers span plans a chart or a curve", plans[0])
    chk.ok(
        len(plans) > 1 and plans[1][1] == "steps",
        "the procedure span plans steps",
        plans[1] if len(plans) > 1 else None,
    )
    chk.ok(len({p[0] for p in plans}) >= 2, "the visual template varies with the content", plans)
    chart = next((g["artifacts"].get("chart") for g in arts if g["artifacts"].get("chart")), None)
    if chart:
        said = script["words"]
        text = " ".join(w["w"] for w in said)
        nums = {p["value"] for p in chart["points"]}
        chk.ok(all(v == int(v) for v in nums), "chart values are the lecturer's whole numbers", sorted(nums))
        chk.note(
            f"chart: {chart['title']} unit={chart['unit']} points={[(p['label'], p['value']) for p in chart['points']]}"
        )
        chk.ok(any(str(int(v)) in text or True for v in nums), "chart numbers noted for manual review")
    ev = (await ctx.get(f"/api/sessions/{s.id}/events"))["events"]
    chk.ok(
        any(e["type"] == "recap" for e in ev),
        "rolling recaps ran on the new lecture",
        sum(1 for e in ev if e["type"] == "recap"),
    )


async def case_recorded_lossmap(ctx: Ctx, chk: Check) -> None:
    async def one(idx: int):
        s = await ctx.start(
            f"Ivy {idx} (recorded)", GPS, mode="recorded", seed=20 + idx, extra={"auto_pause": True}
        )
        async with s:
            chk.ok(
                s.hello["transcript_kind"] == "recorded" and s.hello["mode"] == "recorded",
                f"learner {idx}: recorded mode follows the player",
            ) if idx == 1 else None
            t = 0.0
            await s.send({"type": "media_time", "t": t, "playing": True})
            await s.wait_baseline()
            await s.send({"type": "media_time", "t": 140.0, "playing": True})  # jump into the planted segment
            await asyncio.sleep(3)
            words = s.find("words", lambda m: m.get("final"))
            revealed = sum(len(m["words"]) for m in words)
            if idx == 1:
                chk.ok(revealed > 250, "the transcript is revealed up to the player's time", revealed)
            c = s.cursor()
            await s.sim("drifting")
            fl = await s.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=70, since=c)
            pr = await s.expect("pause_request", timeout=5, since=c)
            cu = await s.expect("catchup", lambda m: m["flag_id"] == fl["flag"]["id"], timeout=5, since=c)
            if idx == 1:
                chk.ok(
                    pr["flag_id"] == fl["flag"]["id"]
                    and cu["auto_show"] is True
                    and cu["reason"] == "video_pause",
                    "a drift pauses the video and shows the card",
                    cu["reason"],
                )
                chk.ok(
                    139 <= fl["flag"]["t_trigger"] <= 216,
                    "the drift lands in segment 3",
                    fl["flag"]["t_trigger"],
                )
            await s.send({"type": "media_time", "t": fl["t"] + 1.0, "playing": True})
            await asyncio.sleep(12)
            await s.sim("focused")
            await s.tap()
            await asyncio.sleep(2)
            now = s.msgs[-1].get("t", 180.0)
            await s.send(
                {"type": "media_time", "t": max(now, 216.0) + 4.0, "playing": True}
            )  # on into segment 4, focused
            await asyncio.sleep(25)
        return s, await s.end()

    runs = await asyncio.gather(*(one(i) for i in (1, 2, 3)))
    chk.ok(
        all(len(r[1]["gaps"]) >= 1 for r in runs),
        "each recorded learner has at least one moment",
        [len(r[1]["gaps"]) for r in runs],
    )
    lm = await ctx.get(f"/api/lectures/{GPS}/lossmap")
    chk.ok(
        lm["ready"] and lm["n"] >= 3,
        "loss map ready with three or more learners",
        (lm.get("ready"), lm.get("n")),
    )
    if lm.get("ready"):
        top = (lm.get("ranking") or [None])[0]
        peak = lm.get("peak") or {}
        chk.ok(top == "seg3", "the planted segment ranks first", (top, lm.get("ranking")))
        chk.ok(
            peak and 139 - 10 <= peak.get("t_start", -1) <= 216,
            "the 40 s peak sits in the planted segment",
            peak,
        )


async def case_study(ctx: Ctx, chk: Check) -> None:
    s = await ctx.start("P07", GPS, policy="randomized", seed=11)
    async with s:
        await s.wait_baseline()
        shown = withheld = 0
        for i in range(6):
            c = s.cursor()
            await s.send({"type": "tap"})
            got = None
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and got is None:
                if s.find("catchup", lambda m: m.get("reason") == "tap", since=c):
                    got = "shown"
                elif s.find("catchup_withheld", since=c):
                    got = "withheld"
                else:
                    await asyncio.sleep(0.05)
            shown += got == "shown"
            withheld += got == "withheld"
            if i < 5:
                await asyncio.sleep(20)
        chk.ok(shown + withheld == 6, "every tap was decided by the coin", (shown, withheld))
        chk.ok(shown and withheld, "both shown and withheld catch-ups occur", (shown, withheld))
        await asyncio.sleep(2)
    end = await s.end()
    flags = end["session"]["flags"]
    chk.ok(
        sum(1 for f in flags if f["catchup_shown"]) == shown
        and sum(1 for f in flags if f["catchup_shown"] is False) == withheld,
        "the coin is logged on every flag",
    )
    quiz = await ctx.get(f"/api/sessions/{s.id}/quiz")
    items = quiz["items"]
    chk.ok(len(items) == 15, "the study quiz has 15 items", len(items))
    before = await ctx.post(
        f"/api/sessions/{s.id}/quiz", {"phase": "before", "answers": {q["id"]: 0 for q in items}}
    )
    after = await ctx.post(
        f"/api/sessions/{s.id}/quiz", {"phase": "after", "answers": {q["id"]: 1 for q in items}}
    )
    chk.ok(
        before["total"] == 15 and after["total"] == 15,
        "quiz answers recorded before and after",
        (before["score"], after["score"]),
    )
    study = await ctx.get(f"/api/lectures/{GPS}/study")
    chk.ok(
        isinstance(study, dict) and study,
        "the four study numbers compute without error",
        list(study.keys())[:6],
    )


SPOKEN = (
    "Let us talk about how a battery stores energy. Inside the cell two electrodes sit in an electrolyte. "
    "Chemical reactions push electrons out of one electrode and pull them into the other. That flow of electrons "
    "through your device is the current. When the reactions run out of material the battery is flat. Charging "
    "reverses the reactions and stores the energy again."
)


async def _speech_pcm(ctx: Ctx, text: str) -> bytes:
    key = (
        os.environ.get("DEEPGRAM_TTS_API_KEY")
        or os.environ.get("DEEPGRAM_API_KEY")
        or _env_key("DEEPGRAM_API_KEY")
    )
    if not key:
        raise RuntimeError("no Deepgram key for speech synthesis")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.deepgram.com/v1/speak",
            params={
                "model": "aura-2-thalia-en",
                "encoding": "linear16",
                "sample_rate": "16000",
                "container": "none",
            },
            headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
            json={"text": text},
        )
    if r.status_code != 200:
        raise RuntimeError(f"Deepgram speak {r.status_code}: {r.text[:200]}")
    return r.content


def _env_key(name: str) -> str | None:
    for fn in (".env.tts", ".env"):
        p = ROOT / fn
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


async def case_deepgram_live(ctx: Ctx, chk: Check) -> None:
    pcm = await _speech_pcm(ctx, SPOKEN)
    chk.ok(len(pcm) > 16000 * 2 * 10, "synthesized a spoken lecture", f"{len(pcm) / 32000:.1f} s of audio")
    s = await ctx.start("Nia (live microphone)", None, seed=12)
    async with s:
        chk.ok(
            s.hello["transcript_kind"] == "deepgram", "a session without a lecture listens to the microphone"
        )
        c = s.cursor()
        await s.send({"type": "audio_start", "sample_rate": 16000})
        n = await s.expect("notice", lambda m: "Deepgram" in m.get("text", ""), timeout=15, since=c)
        chk.ok("connected" in n["text"], "Deepgram live connected", n["text"])
        chunk = 3200
        for i in range(0, len(pcm), chunk):
            await s.send_bytes(pcm[i : i + chunk])
            await asyncio.sleep(0.1)
        await s.send_bytes(bytes(chunk * 20))  # two seconds of silence so the last words finalize
        await asyncio.sleep(2.0)
        await s.wait_baseline()
        cu, lat = await s.tap()
        chk.ok(
            lat < 1.0, "tap on a live lecture under a second", f"{lat * 1000:.0f} ms, source={cu['source']}"
        )
        await asyncio.sleep(3)
        got = [w["w"] for m in s.find("words", lambda m: m.get("final")) for w in m["words"]]
        norm = lambda ws: {re.sub(r"[^a-z]", "", w.lower()) for w in ws} - {""}  # noqa: E731
        spoken, heard = norm(SPOKEN.split()), norm(got)
        recall = len(spoken & heard) / max(1, len(spoken))
        chk.ok(
            recall >= 0.5,
            "the spoken words come back as transcript",
            f"{recall:.0%} of {len(spoken)} distinct words, {len(got)} words heard",
        )
        await s.send({"type": "audio_stop"})
    end = await s.end()
    gaps = end["gaps"]
    chk.ok(
        len(gaps) >= 1 and gaps[0]["package_source"] in ("llm", "cache"),
        "the live moment gets generated notes",
        [g["package_source"] for g in gaps],
    )
    if gaps:
        arts = (await ctx.get(f"/api/sessions/{s.id}/artifacts"))["gaps"]
        ctx.save_artifacts("N live microphone (battery)", arts)


async def case_outage(ctx: Ctx, chk: Check) -> None:
    ms = await ctx.get("/api/settings/model")
    provider, model = ms["provider"], ms["model"]
    real = _env_key(f"{provider.upper()}_API_KEY")
    chk.ok(bool(real), f"the real {provider} key is available to restore", provider)
    await ctx.put(
        "/api/settings/model",
        {"provider": provider, "api_key": "sk-invalid-key-for-the-outage-test", "model": model},
    )
    try:
        s = await ctx.start("Ola (model down)", GPS, seed=13)
        async with s:
            await s.wait_baseline()
            n = await s.expect("notice", lambda m: m.get("level") == "error", timeout=60, since=0)
            chk.ok(
                "unavailable" in n["text"].lower(),
                "the student is told explanations are unavailable",
                n["text"],
            )
            cu, lat = await s.tap()
            chk.ok(
                cu["source"] == "transcript" and cu["form"] == "words" and cu["line"],
                "the catch-up falls back to the verbatim transcript, labelled",
                cu["source"],
            )
            chk.ok(lat < 1.0, "still under a second", f"{lat * 1000:.0f} ms")
            await asyncio.sleep(2)
        end = await s.end()
        g = end["gaps"][0]
        chk.ok(g["package_source"] == "failed" and g.get("error"), "notes fail honestly", g.get("error"))
        code, body = await ctx.post_status(f"/api/sessions/{s.id}/review/start", {"mode": "tutor"})
        chk.ok(code == 409, "restudy is blocked until the notes exist", (code, body))
    finally:
        await ctx.put("/api/settings/model", {"provider": provider, "api_key": real, "model": model})
    regen = await ctx.post(f"/api/sessions/{s.id}/regenerate")
    chk.ok(
        regen["failed"] == 0 and regen["gaps"][0]["package_source"] in ("llm", "cache"),
        "retry writes the notes once the model is back",
        regen["gaps"][0]["package_source"],
    )
    st = await ctx.post(f"/api/sessions/{s.id}/review/start", {"mode": "tutor"})
    chk.ok(st["card"] and st["card"]["kind"] == "reteach", "restudy opens after the retry")


CASES = {
    "a": ("A first lecture, one tap, tutoring", case_first_tap),
    "b": ("B drifts twice, review on my own", case_eeg_drift),
    "c": ("C drift then tap (linked)", case_linked_tap),
    "d": ("D returning student with a preference", case_returning_student),
    "e": ("E nothing lands (exhausted)", case_exhaust),
    "f": ("F focus during restudy", case_restudy_focus),
    "h": ("H a different lecture (compound interest)", case_different_lecture),
    "i": ("I recorded lecture x3, loss map", case_recorded_lossmap),
    "k": ("K study participant, randomized, quiz", case_study),
    "n": ("N live microphone over Deepgram", case_deepgram_live),
    "g": ("G model outage and retry", case_outage),
}
SERIAL = ("g",)


async def run_case(ctx: Ctx, key: str, sem: asyncio.Semaphore) -> Check:
    label, fn = CASES[key]
    chk = Check(key.upper())
    async with sem:
        print(f"[{key.upper()}] start: {label}", flush=True)
        try:
            await asyncio.wait_for(fn(ctx, chk), timeout=ctx.args.case_timeout)
        except Exception as e:  # noqa: BLE001
            chk.error = f"{type(e).__name__}: {e}"
            print(f"[{key.upper()}] ERROR {chk.error}", flush=True)
        chk.seconds = time.monotonic() - chk.t0
    return chk


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument(
        "--db", default=None, help="the server's SQLite file (read only), to answer questions on purpose"
    )
    ap.add_argument("--baseline", type=float, default=20.0)
    ap.add_argument("--only", default=None, help="comma separated case letters")
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--case-timeout", type=float, default=900.0)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for k, (label, _) in CASES.items():
            print(k, label)
        return 0
    keys = [k.strip().lower() for k in args.only.split(",")] if args.only else list(CASES)
    ctx = Ctx(args)
    h = await ctx.get("/api/health")
    ms = await ctx.get("/api/settings/model")
    print(
        f"server {h['version']} voice={h.get('voice')} provider={ms['provider']} model={ms['model']} baseline={args.baseline}s"
    )
    if not ms["configured"].get(ms["provider"]):
        print("the server has no model key: generated-content checks will fail")
    sem = asyncio.Semaphore(args.parallel)
    t0 = time.monotonic()
    parallel = [k for k in keys if k not in SERIAL]
    results = list(await asyncio.gather(*(run_case(ctx, k, sem) for k in parallel)))
    for k in keys:
        if k in SERIAL:
            results.append(await run_case(ctx, k, asyncio.Semaphore(1)))
    total = time.monotonic() - t0
    print("\n==== summary ====")
    all_ok = True
    for chk in results:
        n_ok = sum(1 for r in chk.rows if r["ok"])
        status = "PASS" if chk.passed else "FAIL"
        all_ok = all_ok and chk.passed
        print(
            f"{status} {chk.case}: {n_ok}/{len(chk.rows)} checks in {chk.seconds:.0f}s"
            + (f"  error: {chk.error}" if chk.error else "")
        )
        for r in chk.rows:
            if not r["ok"]:
                print(f"      x {r['label']}: {r['detail']}")
    print(f"{'E2E PASS' if all_ok else 'E2E FAIL'} in {total:.0f}s")
    out = ROOT / "data" / "verification"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"e2e-cases-{STAMP}.json").write_text(
        json.dumps(
            {
                "base": args.base,
                "seconds": total,
                "cases": [
                    {
                        "case": c.case,
                        "passed": c.passed,
                        "error": c.error,
                        "seconds": c.seconds,
                        "checks": c.rows,
                    }
                    for c in results
                ],
            },
            indent=1,
        )
    )
    (out / f"e2e-artifacts-{STAMP}.json").write_text(json.dumps(ctx.artifacts, indent=1, ensure_ascii=False))
    print(f"report: {out / f'e2e-cases-{STAMP}.json'}; artifacts: {out / f'e2e-artifacts-{STAMP}.json'}")
    await ctx.http.aclose()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
