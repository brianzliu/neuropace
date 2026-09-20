from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import time
import wave
from collections import deque
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

from scripts.guided_eeg_trial import score_trial
from scripts.trial_speech import speech_identity, synthesize_trial_speech

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
CUES = {
    "focus": "We'll start now. Listen to the lesson and try to follow what it's saying. Keep your eyes open and sit comfortably.",
    "drift": "Now let the lesson fade into the background. Think about something you'd like to do tomorrow. Keep your eyes open. I'll tell you when to come back.",
    "recover": "Come back to the lesson now. Follow what the narrator is explaining. Stay relaxed and keep your eyes open.",
    "finish": "That's the end of this short run. You can relax. I'll check how your signal changed.",
    "contact": "We don't have enough clean signal to calibrate yet. Please check that the forehead sensor and ear clip are touching your skin.",
}
PHASES = [("baseline", "focus", 0, 75), ("daydream", "drift", 75, 120), ("refocus", "focus", 120, 165)]


def prepare_native() -> dict:
    fixture = json.loads((ROOT / "study" / "guided_lesson.json").read_text())
    text = "\n\n".join(section["text"] for section in fixture["sections"][:2])
    identity = json.dumps({"text": text, "cues": CUES, "voice": speech_identity()}, sort_keys=True)
    directory = (
        ROOT
        / "data"
        / "verification"
        / ("native-media-" + hashlib.sha256(identity.encode()).hexdigest()[:12])
    )
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    with httpx.Client(base_url=BASE, timeout=180) as client:
        if manifest_path.exists():
            cached = json.loads(manifest_path.read_text())
            if client.get("/api/lectures/" + cached["lecture_id"]).is_success:
                return cached
        for name, words in {**CUES, "lecture": text}.items():
            print("SPEECH", name, synthesize_trial_speech(words, directory / (name + ".wav")), flush=True)
        with wave.open(str(directory / "lecture.wav"), "rb") as audio:
            if audio.getnframes() / audio.getframerate() < 165:
                raise RuntimeError("Narration is too short for the fixed test windows")
        with (directory / "lecture.wav").open("rb") as audio:
            response = client.post(
                "/api/lectures",
                data={"title": "Native guided EEG demo: synthetic water-treatment lesson"},
                files={"file": ("lecture.wav", audio, "audio/wav")},
            )
        response.raise_for_status()
        manifest = {
            "lecture_id": response.json()["id"],
            "directory": str(directory),
            "voice": speech_identity(),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return manifest


async def run_trial(manifest: dict):
    directory = ROOT / "data" / "verification" / ("native-trial-" + time.strftime("%Y%m%d-%H%M%S"))
    directory.mkdir(parents=True, exist_ok=False)
    media = Path(manifest["directory"])
    events, markers = [], []
    focus = None
    recent = deque(maxlen=10)
    raw_at = 0.0
    players = set()
    error = None
    session = None

    async def play(name, wait=True, volume=1.0):
        process = await asyncio.create_subprocess_exec(
            "afplay", "-v", str(volume), str(media / (name + ".wav"))
        )
        players.add(process)
        if wait:
            await asyncio.wait_for(process.wait(), timeout=30)
            players.discard(process)
            if process.returncode:
                raise RuntimeError("Native speech playback failed")
        return process

    async with httpx.AsyncClient(base_url=BASE, timeout=120) as client:
        response = await client.post(
            "/api/sessions",
            json={
                "learner_name": directory.name,
                "lecture_id": manifest["lecture_id"],
                "mode": "recorded",
                "headset": "auto",
                "totem": "keyboard",
                "baseline_seconds": 60,
                "use_stored_baseline": False,
                "auto_pause": False,
                "catchup_policy": "always",
            },
        )
        response.raise_for_status()
        session = response.json()
        sid = session["id"]
        print("NATIVE TRIAL SESSION", sid, "EVIDENCE", directory, flush=True)
        try:
            if session["headset"]["kind"] != "real":
                raise RuntimeError("Real headset required; simulated data will not be accepted")
            async with connect(BASE.replace("http", "ws", 1) + "/ws/session/" + sid) as ws:

                async def collect():
                    nonlocal focus, raw_at
                    with (directory / "events.jsonl").open("a") as log:
                        async for packet in ws:
                            message = json.loads(packet)
                            event = {**message, "session_id": sid, "observed_wall": time.time()}
                            events.append(event)
                            log.write(json.dumps(event) + "\n")
                            log.flush()
                            if message["type"] == "focus":
                                focus = message
                                recent.append(
                                    message.get("quality") == "good" and not message.get("artifact", True)
                                )
                            elif message["type"] == "raw":
                                raw_at = time.monotonic()
                            elif message["type"] == "flag_open":
                                print("FLAG", json.dumps(message["flag"]), flush=True)
                            elif message["type"] == "catchup":
                                print(
                                    "CATCHUP OFFER",
                                    json.dumps(
                                        {
                                            k: message.get(k)
                                            for k in (
                                                "flag_id",
                                                "reason",
                                                "source",
                                                "line",
                                                "since",
                                                "auto_show",
                                            )
                                        }
                                    ),
                                    flush=True,
                                )

                collector = asyncio.create_task(collect())
                try:
                    deadline = time.monotonic() + 120
                    print("WAITING FOR CLEAN CONTACT; the spoken start cue will begin the task", flush=True)
                    while not (len(recent) == 10 and sum(recent) >= 8 and time.monotonic() - raw_at < 2):
                        if time.monotonic() >= deadline:
                            await play("contact")
                            raise RuntimeError("Clean-contact preflight did not pass")
                        await asyncio.sleep(1)
                    await play("focus")
                    await play("lecture", wait=False, volume=0.55)
                    start = time.monotonic()
                    phase = 0
                    markers.append({"phase": "baseline", "task": "focus", "session_id": sid, "t_start": 0})
                    while time.monotonic() - start < 165:
                        t = time.monotonic() - start
                        await ws.send(json.dumps({"type": "media_time", "t": t, "playing": True}))
                        if phase < 2 and t >= PHASES[phase + 1][2]:
                            boundary = PHASES[phase + 1][2]
                            markers[-1]["t_end"] = boundary
                            if not focus or not focus.get("baseline_ready"):
                                await play("contact")
                                raise RuntimeError(
                                    "Baseline did not complete; stopping rather than pretending to test attention"
                                )
                            phase += 1
                            name, task, _, _ = PHASES[phase]
                            markers.append(
                                {"phase": name, "task": task, "session_id": sid, "t_start": boundary}
                            )
                            print("TASK", name, "at", boundary, flush=True)
                            await play("drift" if phase == 1 else "recover", wait=False)
                        await asyncio.sleep(0.25)
                    markers[-1]["t_end"] = 165
                    await ws.send(json.dumps({"type": "media_time", "t": 165, "playing": False}))
                finally:
                    collector.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await collector
        except Exception as exc:
            error = str(exc)
            print("TRIAL ERROR", error, flush=True)
        finally:
            for player in players:
                if player.returncode is None:
                    player.terminate()
            for player in players:
                await asyncio.wait_for(player.wait(), timeout=5)
            if error is None:
                await play("finish")
            ended = await client.post("/api/sessions/" + sid + "/end")
            ended.raise_for_status()
            (directory / "session.json").write_text(json.dumps(ended.json(), indent=2))
            (directory / "markers.json").write_text(json.dumps(markers, indent=2))
            result = score_trial(events, markers, []) | {
                "session_id": sid,
                "error": error,
                "independent_reports": "pending participant confirmation",
                "baseline_seconds": 60,
                "voice": manifest["voice"],
            }
            (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False))
            print("NATIVE TRIAL RESULT", json.dumps(result, indent=2), flush=True)
    if error:
        raise SystemExit(error)


if __name__ == "__main__":
    asyncio.run(run_trial(prepare_native()))
