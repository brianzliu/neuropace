from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import math
import secrets
import statistics
import subprocess
import time
import wave
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from websockets.asyncio.client import connect

from neuropace.api.local_bridge import LocalBridgeGuard

ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = {
    "focus": "Listen carefully to the water-treatment lesson. Try to understand it well enough to explain it back. Keep your eyes open and your head relaxed.",
    "drift": "Let the lesson continue, but stop following it. Silently imagine an ordinary walk through a familiar place. Keep your eyes open on the same screen. Do not close your eyes or move the headset.",
    "effort_offtask": "Ignore the lesson and silently subtract seven repeatedly from one thousand. Keep your eyes open, your head still and your jaw relaxed. This tests focused thinking about the wrong task.",
    "eyes_open_1": "Look at the centre dot with your eyes open. Relax your face. Do not deliberately change your breathing.",
    "blinks": "Keep looking at the dot. Blink once each time you hear the word blink. There will be five cues. Do not move your head.",
    "eyes_closed": "Close your eyes gently and relax. Keep your head still. Wait for the spoken instruction to open your eyes.",
    "eyes_open_2": "Open your eyes and look at the centre dot again. Relax your face and keep still.",
    "workload": "Keep your eyes open. Silently subtract seven repeatedly from one thousand. Do not speak or clench your jaw.",
    "blink": "Blink.",
}
SIGNAL_PHASES = [
    ("eyes_open_1", 25),
    ("blinks", 20),
    ("eyes_closed", 30),
    ("eyes_open_2", 25),
    ("workload", 25),
]


def valid_focus(event: dict) -> bool:
    return (
        event.get("quality") == "good"
        and event.get("state") in ("ok", "drop", "baseline")
        and not event.get("artifact", True)
        and not event.get("paused", True)
        and event.get("sim") is False
    )


def finite_values(points: list[dict], key: str) -> list[float]:
    values = [(point.get("mw") or {}).get(key) for point in points]
    return [float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(value)]


def score_trial(events: list[dict], markers: list[dict], probes: list[dict]) -> dict:
    focus = {}
    for event in events:
        if event.get("type") == "focus" and not event.get("paused", True):
            focus[(event.get("session_id"), math.floor(event["t"]))] = event
    reports = {probe["phase"]: probe["reported"] for probe in probes}
    confusion = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    blocks = []
    alpha = {"open": [], "closed": []}
    for marker in markers:
        if "t_end" not in marker:
            continue
        signal = marker["task"] == "signal"
        settle = 5 if signal else 15
        start, end = marker["t_start"] + settle, marker["t_end"]
        points = [
            p for p in focus.values() if p.get("session_id") == marker["session_id"] and start <= p["t"] < end
        ]
        clean = [point for point in points if valid_focus(point)]
        if signal:
            if marker["phase"] in ("eyes_open_1", "eyes_open_2", "eyes_closed"):
                alpha["closed" if marker["phase"] == "eyes_closed" else "open"].extend(
                    finite_values(clean, "log_alpha")
                )
            continue
        if marker["phase"] == "baseline":
            continue
        fraction = min(1.0, len(clean) / max(1, end - start))
        triggered = [
            event["flag"]
            for event in events
            if event.get("type") == "flag_open"
            and event.get("session_id") == marker["session_id"]
            and event["flag"].get("source") == "eeg"
            and event["flag"].get("simulated") is False
            and start <= event["flag"]["t_trigger"] < end
        ]
        reported = reports.get(marker["phase"])
        eligible = (
            fraction >= 0.8
            and reported in ("lecture", "elsewhere")
            and any(p.get("baseline_ready") for p in clean)
        )
        if eligible:
            truth, predicted = reported == "elsewhere", bool(triggered)
            confusion[("tp" if predicted else "fn") if truth else ("fp" if predicted else "tn")] += 1
        engagement = finite_values(clean, "engagement")
        blocks.append(
            {
                **marker,
                "reported": reported,
                "eligible": eligible,
                "valid_seconds": len(clean),
                "valid_fraction": round(fraction, 3),
                "eeg_flags": len({flag["id"] for flag in triggered}),
                "first_trigger_latency_s": min(f["t_trigger"] for f in triggered) - marker["t_start"]
                if triggered
                else None,
                "mean_engagement": statistics.mean(engagement) if engagement else None,
                "reason_excluded": None
                if eligible
                else "insufficient valid signal, baseline, or independent attention report",
            }
        )
    ratio = None
    if min(len(alpha["open"]), len(alpha["closed"])) >= 8:
        ratio = 10 ** (statistics.median(alpha["closed"]) - statistics.median(alpha["open"]))
    return {
        "blocks": blocks,
        "confusion": confusion,
        "scored_blocks": sum(confusion.values()),
        "alpha_closed_open_ratio": ratio,
        "alpha_valid_samples": {key: len(value) for key, value in alpha.items()},
        "claim_limit": "Single-wearer instructed-task diagnostic. No population accuracy or causal learning-benefit claim; no yoked timing control was run.",
    }


def prepare(base: str) -> dict:
    fixture = ROOT / "study" / "guided_lesson.json"
    digest = hashlib.sha256(fixture.read_bytes() + b"Samantha-125-v1").hexdigest()[:12]
    directory = ROOT / "data" / "verification" / ("guided-media-" + digest)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    with httpx.Client(base_url=base, timeout=300) as client:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if client.get("/api/lectures/" + manifest["lecture_id"]).is_success:
                return manifest
        lesson = json.loads(fixture.read_text())
        sections, all_frames, offset = [], [], 0.0
        for section in lesson["sections"]:
            source = directory / (section["id"] + ".txt")
            audio = directory / (section["id"] + ".wav")
            source.write_text(section["text"])
            subprocess.run(
                [
                    "say",
                    "-v",
                    "Samantha",
                    "-r",
                    "125",
                    "--data-format=LEI16@16000",
                    "-o",
                    str(audio),
                    "-f",
                    str(source),
                ],
                check=True,
                timeout=90,
            )
            with wave.open(str(audio), "rb") as handle:
                assert (
                    handle.getnchannels() == 1
                    and handle.getsampwidth() == 2
                    and handle.getframerate() == 16000
                )
                data = handle.readframes(handle.getnframes())
                duration = handle.getnframes() / handle.getframerate()
            minimum = 180 if section["id"] == "baseline" else 40
            if duration < minimum:
                raise RuntimeError(
                    f"Narration {section['id']} too short: {duration:.1f}s, minimum {minimum}s"
                )
            sections.append({**section, "t_start": offset, "t_end": offset + duration})
            all_frames.append(data)
            offset += duration
        combined = directory / "lecture.wav"
        with wave.open(str(combined), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            for data in all_frames:
                handle.writeframes(data)
        for name, text in INSTRUCTIONS.items():
            audio = directory / ("cue-" + name + ".wav")
            subprocess.run(
                ["say", "-v", "Samantha", "-r", "170", "--data-format=LEI16@16000", "-o", str(audio), text],
                check=True,
                timeout=30,
            )
        quiz = [
            {
                "id": item["id"],
                "segment": item["id"],
                "t_start": item["t_start"],
                "t_end": item["t_end"],
                "question": item["question"],
                "options": item["options"],
                "correct_index": item["correct_index"],
            }
            for item in sections
            if "question" in item
        ]
        segments = [
            {"id": item["id"], "title": item["id"], "t_start": item["t_start"], "t_end": item["t_end"]}
            for item in sections
        ]
        with combined.open("rb") as handle:
            response = client.post(
                "/api/lectures",
                data={"title": lesson["title"], "segments": json.dumps(segments), "quiz": json.dumps(quiz)},
                files={"file": ("lecture.wav", handle, "audio/wav")},
            )
        response.raise_for_status()
        manifest = {
            "lecture_id": response.json()["id"],
            "title": lesson["title"],
            "directory": str(directory),
            "sections": sections,
            "duration": offset,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print("Prepared narrated lesson", manifest["lecture_id"], "seconds", round(offset), flush=True)
        return manifest


class Trial:
    def __init__(self, base: str, manifest: dict):
        self.base = base
        self.manifest = manifest
        self.directory = ROOT / "data" / "verification" / ("trial-" + time.strftime("%Y%m%d-%H%M%S"))
        self.directory.mkdir(parents=True, exist_ok=False)
        self.client = httpx.AsyncClient(base_url=base, timeout=120)
        self.lock = asyncio.Lock()
        self.session_id = None
        self.sessions = []
        self.ws = None
        self.reader = None
        self.events = []
        self.markers = []
        self.probes = []
        self.ratings = []
        self.focus = None
        self.recent = deque(maxlen=10)
        self.raw_at = 0.0
        self.raw = deque(maxlen=256)
        self.stage = "idle"
        self.error = None
        self.config = None
        self.catchups = {}
        self.opened = []
        self.result = None
        self.last_client = time.monotonic()
        self.started = time.monotonic()

    def log(self, kind: str, data: dict):
        row = {"kind": kind, "wall": time.time(), **data}
        with (self.directory / "trial.jsonl").open("a") as handle:
            handle.write(json.dumps(row, allow_nan=False) + "\n")

    async def api(self, path: str, body: dict):
        response = await self.client.post(path, json=body)
        if not response.is_success:
            raise HTTPException(response.status_code, response.text[:500])
        return response.json()

    async def begin_session(self, mode: str):
        session = await self.api(
            "/api/sessions",
            {
                **(
                    {"learner_id": self.manifest["learner_id"]}
                    if self.manifest.get("learner_id")
                    else {"learner_name": self.directory.name}
                ),
                "lecture_id": self.manifest["lecture_id"] if mode in ("live", "recorded") else None,
                "mode": mode,
                "headset": "auto",
                "totem": "keyboard",
                "baseline_seconds": self.manifest.get("baseline_seconds", 180) if mode == "review" else 180,
                "use_stored_baseline": self.manifest.get("use_stored_baseline", False)
                if mode == "live"
                else False,
                "auto_pause": False,
                "catchup_policy": "always",
            },
        )
        self.session_id = session["id"]
        self.sessions.append(self.session_id)
        if session["headset"]["kind"] != "real":
            await self.end_session()
            raise HTTPException(409, "This trial requires the real headset. Simulated input is not accepted.")
        self.focus = None
        self.recent.clear()
        self.raw.clear()
        self.raw_at = 0
        self.ws = await connect(self.base.replace("http", "ws", 1) + "/ws/session/" + self.session_id)
        self.reader = asyncio.create_task(self.consume(self.ws, self.session_id))
        self.log("session_start", {"session_id": self.session_id, "mode": mode})

    async def consume(self, ws, session_id):
        try:
            async for raw in ws:
                message = json.loads(raw)
                event = {**message, "session_id": session_id}
                self.events.append(event)
                self.log("event", event)
                kind = message["type"]
                if kind == "hello":
                    self.config = message["config"]
                elif kind == "focus":
                    self.focus = message
                    self.recent.append(message)
                elif kind == "raw":
                    self.raw_at = time.monotonic()
                    self.raw.extend(message["uv"])
                elif kind == "catchup":
                    self.catchups[message["flag_id"]] = message
                elif kind == "error":
                    self.error = message.get("text", "Session error")
        except Exception as error:
            self.error = str(error)
            self.log("stream_error", {"error": self.error})

    async def end_session(self):
        if self.session_id:
            sid, self.session_id = self.session_id, None
            ended = await self.api("/api/sessions/" + sid + "/end", {})
            self.log(
                "session_end",
                {"session_id": sid, "baseline": ended["session"].get("baseline"), "gaps": ended["gaps"]},
            )
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self.reader:
            await self.reader
            self.reader = None

    def state(self):
        return {
            "stage": self.stage,
            "session_id": self.session_id,
            "sessions": self.sessions,
            "focus": self.focus,
            "raw": list(self.raw),
            "stream_live": time.monotonic() - self.raw_at < 2,
            "fit_ready": len(self.recent) == 10
            and sum(valid_focus(p) for p in self.recent) >= 8
            and time.monotonic() - self.raw_at < 2,
            "error": self.error,
            "config": self.config,
            "catchups": list(self.catchups.values()),
            "opened": self.opened,
            "result": self.result,
            "probes": self.probes,
            "markers": self.markers,
            "directory": str(self.directory),
        }

    async def watchdog(self):
        while True:
            await asyncio.sleep(5)
            if self.session_id and (
                time.monotonic() - self.last_client > 20 or time.monotonic() - self.started > 1800
            ):
                async with self.lock:
                    self.error = "Trial stopped because the controller stopped reporting or the 30-minute limit was reached."
                    self.stage = "aborted"
                    await self.end_session()
                    self.log("abort", {"reason": self.error})


class ClockIn(BaseModel):
    t: float = Field(ge=0, le=3600, allow_inf_nan=False)
    playing: bool
    visible: bool = True


class MarkerIn(BaseModel):
    phase: str
    task: str
    action: str
    t: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)


class ProbeIn(BaseModel):
    phase: str
    reported: str


class SubmitIn(BaseModel):
    answers: dict[str, int]
    ratings: list[dict] = Field(default_factory=list, max_length=100)


def make_app(trial: Trial) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        watchdog = asyncio.create_task(trial.watchdog())
        yield
        watchdog.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watchdog
        await trial.end_session()
        await trial.client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(LocalBridgeGuard, origins=(), token=secrets.token_urlsafe(24))

    @app.get("/")
    async def home():
        return FileResponse(Path(__file__).with_suffix(".html"))

    @app.get("/audio/{name}")
    async def audio(name: str):
        allowed = {"lecture.wav"} | {"cue-" + key + ".wav" for key in INSTRUCTIONS}
        if name not in allowed:
            raise HTTPException(404)
        return FileResponse(Path(trial.manifest["directory"]) / name)

    @app.get("/manifest")
    async def manifest():
        return {
            "title": trial.manifest["title"],
            "duration": trial.manifest["duration"],
            "sections": [
                {k: v for k, v in section.items() if k not in ("correct_index", "text")}
                for section in trial.manifest["sections"]
            ],
            "instructions": INSTRUCTIONS,
            "signal_phases": SIGNAL_PHASES,
        }

    @app.get("/state")
    async def state():
        return trial.state()

    @app.post("/heartbeat")
    async def heartbeat():
        trial.last_client = time.monotonic()
        return {"ok": True}

    @app.post("/fit")
    async def fit():
        async with trial.lock:
            if trial.stage != "idle":
                raise HTTPException(409, "A trial is already underway")
            trial.last_client = time.monotonic()
            await trial.begin_session("review")
            trial.stage = "fit"
        return trial.state()

    @app.post("/signal")
    async def signal():
        if trial.stage != "fit" or not trial.state()["fit_ready"]:
            raise HTTPException(409, "Wait for ten seconds of sufficiently clean signal before starting")
        trial.stage = "signal"
        return {"ok": True}

    @app.post("/marker")
    async def marker(body: MarkerIn):
        allowed = {phase for phase, _ in SIGNAL_PHASES} | {
            section["id"] for section in trial.manifest["sections"]
        }
        if body.phase not in allowed or body.action not in ("start", "end") or not trial.session_id:
            raise HTTPException(400, "Invalid phase marker")
        t = body.t if body.t is not None else (trial.focus or {}).get("t", 0)
        if body.action == "start":
            trial.markers.append(
                {"phase": body.phase, "task": body.task, "session_id": trial.session_id, "t_start": t}
            )
        else:
            match = next(
                (
                    item
                    for item in reversed(trial.markers)
                    if item["phase"] == body.phase and "t_end" not in item
                ),
                None,
            )
            if match is None or t < match["t_start"]:
                raise HTTPException(400, "Phase was not started")
            match["t_end"] = t
        trial.log("marker", body.model_dump() | {"t": t, "session_id": trial.session_id})
        return {"ok": True}

    @app.post("/lesson")
    async def lesson():
        async with trial.lock:
            if trial.stage != "signal":
                raise HTTPException(409, "Complete the signal checks first")
            await trial.end_session()
            await trial.begin_session("recorded")
            trial.stage = "lesson"
        return trial.state()

    @app.post("/clock")
    async def clock(body: ClockIn):
        trial.last_client = time.monotonic()
        if trial.stage == "lesson" and trial.ws:
            await trial.ws.send(json.dumps({"type": "media_time", "t": body.t, "playing": body.playing}))
            if not body.visible:
                trial.log("hidden_tab", {"t": body.t})
        return {"ok": True}

    @app.post("/probe")
    async def probe(body: ProbeIn):
        if body.reported not in ("lecture", "elsewhere", "mixed") or body.phase not in {
            section["id"] for section in trial.manifest["sections"]
        }:
            raise HTTPException(400, "Invalid attention report")
        trial.probes = [probe for probe in trial.probes if probe["phase"] != body.phase] + [body.model_dump()]
        trial.log("probe", body.model_dump())
        return {"ok": True}

    @app.post("/catchup/{flag_id}")
    async def catchup(flag_id: str):
        if flag_id not in trial.catchups or not trial.ws:
            raise HTTPException(404)
        await trial.ws.send(json.dumps({"type": "open_catchup", "flag_id": flag_id}))
        if flag_id not in trial.opened:
            trial.opened.append(flag_id)
            trial.log("catchup_opened", {"flag_id": flag_id, "t": (trial.focus or {}).get("t")})
        return trial.catchups[flag_id]

    @app.post("/finish")
    async def finish():
        async with trial.lock:
            if trial.stage != "lesson":
                raise HTTPException(409, "The lesson is not running")
            await trial.end_session()
            trial.stage = "quiz"
        return {"ok": True}

    @app.post("/submit")
    async def submit(body: SubmitIn):
        if trial.stage != "quiz":
            raise HTTPException(409, "Complete the lesson first")
        sections = [section for section in trial.manifest["sections"] if "question" in section]
        if set(body.answers) != {section["id"] for section in sections} or any(
            choice not in range(4) for choice in body.answers.values()
        ):
            raise HTTPException(400, "Answer every question")
        quiz = await trial.api(
            "/api/sessions/" + trial.sessions[-1] + "/quiz", {"phase": "before", "answers": body.answers}
        )
        trial.ratings = body.ratings
        trial.result = score_trial(trial.events, trial.markers, trial.probes) | {
            "quiz": quiz,
            "ratings": trial.ratings,
            "sessions": trial.sessions,
            "config": trial.config,
        }
        (trial.directory / "result.json").write_text(json.dumps(trial.result, indent=2, allow_nan=False))
        trial.log("result", trial.result)
        trial.stage = "done"
        return trial.result

    @app.post("/stop")
    async def stop():
        async with trial.lock:
            trial.stage = "aborted"
            await trial.end_session()
            trial.log("abort", {"reason": "participant stop"})
        return {"ok": True}

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=8776)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    manifest = prepare(args.base)
    if not args.prepare_only:
        trial = Trial(args.base, manifest)
        print("Guided trial on http://localhost:" + str(args.port), "evidence:", trial.directory, flush=True)
        uvicorn.run(make_app(trial), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
