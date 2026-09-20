from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import secrets
import statistics
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from neuropace.api.local_bridge import LocalBridgeGuard
from scripts.guided_eeg_trial import Trial, finite_values, score_trial, valid_focus
from scripts.trial_speech import speech_identity, synthesize_trial_speech

ROOT = Path(__file__).resolve().parents[1]
PHASES = [
    ("eyes_open_1", "easy", 25, "Eyes open. Look at the dot and relax."),
    ("eyes_closed", "eyes_closed", 20, "Close your eyes gently. Relax. I'll tell you when to open them."),
    (
        "concentrate",
        "hard",
        40,
        "Open your eyes. Count backwards silently from one thousand, subtracting seven each time.",
    ),
    ("daydream", "done", 30, "Stop counting. Let your mind wander. Keep your eyes open."),
    ("concentrate_again", None, 30, "Count backwards by sevens again. Start from one thousand."),
]


def prepare_cues() -> Path:
    identity = json.dumps({"phases": PHASES, "voice": speech_identity()}, sort_keys=True)
    directory = (
        ROOT
        / "data"
        / "verification"
        / ("calibration-cues-" + hashlib.sha256(identity.encode()).hexdigest()[:12])
    )
    directory.mkdir(parents=True, exist_ok=True)
    cues = {name: text for name, _, _, text in PHASES}
    cues["finish"] = "Calibration finished. You can relax."
    for name, text in cues.items():
        print("CUE", name, synthesize_trial_speech(text, directory / (name + ".wav")), flush=True)
    return directory


def create_calibration_app(cues: Path, live_check: bool = False) -> FastAPI:
    manifest = {"lecture_id": "lec_demo0001" if live_check else None, "directory": str(cues)}
    if live_check:
        manifest.update(learner_id="me", baseline_seconds=3600, use_stored_baseline=True)
    trial = Trial("http://127.0.0.1:8765", manifest)
    display = {
        "phase": "fit",
        "instruction": "Keep your eyes open and relax while we check contact.",
        "remaining": 0,
    }
    job = None

    async def speak(name):
        player = await asyncio.create_subprocess_exec("afplay", str(cues / (name + ".wav")))
        try:
            await asyncio.wait_for(player.wait(), timeout=20)
            if player.returncode:
                raise RuntimeError("Speech playback failed")
        finally:
            if player.returncode is None:
                player.terminate()
                await asyncio.wait_for(player.wait(), timeout=5)

    async def hold(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            display["remaining"] = max(0, round(deadline - time.monotonic()))
            await asyncio.sleep(0.25)

    async def wait_for_signal():
        deadline = time.monotonic() + 90
        while not (
            trial.state()["fit_ready"]
            and (trial.focus or {}).get("quality") == "good"
            and not (trial.focus or {}).get("artifact", True)
        ):
            if time.monotonic() > deadline:
                raise RuntimeError("Clean signal did not recover; live check stopped")
            await asyncio.sleep(0.5)

    async def execute_live_check():
        display.update(phase="focused_baseline", instruction=PHASES[2][3], remaining=38)
        await speak("concentrate")
        await hold(8)
        await wait_for_signal()
        started = await trial.api(f"/api/sessions/{trial.session_id}/personal-calibration/start", {})
        await hold(started["duration_seconds"] + 0.25)
        baseline = await trial.api(
            f"/api/sessions/{trial.session_id}/personal-calibration/finish", {"apply": True}
        )
        trial.log("personal_baseline_saved", baseline)
        print("FOCUSED BASELINE SAVED", json.dumps(baseline), flush=True)
        await trial.end_session()
        display.update(
            phase="reconnecting",
            instruction="Keep counting silently while the headset reconnects.",
            remaining=0,
        )
        await trial.begin_session("live")
        await wait_for_signal()
        for name, cue_name, seconds, task in (
            ("focused_check", "concentrate_again", 20, "focus"),
            ("daydream", "daydream", 35, "drift"),
            ("refocus", "concentrate_again", 35, "focus"),
        ):
            text = next(item[3] for item in PHASES if item[0] == cue_name)
            display.update(phase=name, instruction=text, remaining=seconds)
            await speak(cue_name)
            marker = {
                "phase": name,
                "task": task,
                "session_id": trial.session_id,
                "t_start": trial.focus["t"],
            }
            trial.markers.append(marker)
            trial.log("live_check_phase", marker)
            print("LIVE PHASE", name, flush=True)
            await hold(seconds)
            marker["t_end"] = trial.focus["t"]
        snapshot = await trial.client.get(f"/api/sessions/{trial.session_id}")
        snapshot.raise_for_status()
        flags = [
            flag for flag in snapshot.json()["flags"] if flag["source"] == "eeg" and not flag["simulated"]
        ]
        measurements = []
        for marker in trial.markers:
            points = [
                event
                for event in trial.events
                if event.get("type") == "focus"
                and event["session_id"] == marker["session_id"]
                and marker["t_start"] <= event["t"] < marker["t_end"]
            ]
            clean = [point for point in points if valid_focus(point)]
            values = [point["w15"] for point in clean if point.get("w15") is not None]
            measurements.append(
                {
                    **marker,
                    "total_ticks": len(points),
                    "valid_ticks": len(clean),
                    "minimum_w15": min(values) if values else None,
                    "maximum_w15": max(values) if values else None,
                    "eeg_flags": [
                        flag for flag in flags if marker["t_start"] <= flag["t_trigger"] < marker["t_end"]
                    ],
                }
            )
        trial.result = {
            "scope": "Fresh live instructed-task check; scripted content tests catch-up dispatch, not learning benefit.",
            "baseline": baseline,
            "measurements": measurements,
            "all_eeg_flags": flags,
            "catchups": list(trial.catchups.values()),
            "opened": trial.opened,
            "session_id": trial.session_id,
        }
        (trial.directory / "live-check.json").write_text(json.dumps(trial.result, indent=2, allow_nan=False))
        display.update(phase="saving", instruction="Finished. You can relax.", remaining=0)
        await speak("finish")
        await trial.end_session()
        trial.stage = "done"
        display["phase"] = "done"
        print("LIVE CHECK COMPLETE", trial.directory, flush=True)

    async def execute():
        trial.stage = "signal"
        try:
            if live_check:
                await execute_live_check()
                return
            await trial.api("/api/sessions/" + trial.session_id + "/calibrate", {"phase": "reset"})
            for name, command, seconds, text in PHASES:
                display.update(phase=name, instruction=text, remaining=seconds)
                await speak(name)
                if command:
                    await trial.api("/api/sessions/" + trial.session_id + "/calibrate", {"phase": command})
                marker = {
                    "phase": name,
                    "task": "signal",
                    "session_id": trial.session_id,
                    "t_start": (trial.focus or {}).get("t", 0),
                }
                trial.markers.append(marker)
                trial.log("calibration_phase", marker)
                print("PHASE", name, seconds, flush=True)
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    display["remaining"] = max(0, round(deadline - time.monotonic()))
                    await asyncio.sleep(0.25)
                marker["t_end"] = (trial.focus or {}).get("t", marker["t_start"])
            status = await trial.client.get("/api/sessions/" + trial.session_id)
            status.raise_for_status()
            trial.result = score_trial(trial.events, trial.markers, [])
            measurements = []
            for marker in trial.markers:
                clean = [
                    event
                    for event in trial.events
                    if event.get("type") == "focus"
                    and marker["t_start"] + 5 <= event["t"] < marker["t_end"]
                    and valid_focus(event)
                ]
                means = {}
                for key in ("effort", "engagement", "log_theta", "log_alpha", "log_beta"):
                    values = finite_values(clean, key)
                    means[key] = statistics.mean(values) if values else None
                measurements.append({**marker, "valid_samples": len(clean), "means": means})
            trial.result.update(
                measurements=measurements,
                headset=status.json().get("headset"),
                scope="Signal and workload calibration only. No lecture or comprehension outcome was measured.",
            )
            (trial.directory / "calibration.json").write_text(
                json.dumps(trial.result, indent=2, allow_nan=False)
            )
            await trial.end_session()
            await speak("finish")
            trial.stage = "done"
            display.update(phase="done", instruction="Finished. You can relax.", remaining=0)
            print("CALIBRATION COMPLETE", trial.directory, flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            trial.error = str(error)
            trial.stage = "aborted"
            display.update(instruction="Calibration stopped. " + trial.error, remaining=0)
            print("CALIBRATION ERROR", trial.error, flush=True)
        finally:
            await trial.end_session()

    async def stop():
        nonlocal job
        trial.stage = "aborted"
        if job and not job.done():
            job.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await job
        await trial.end_session()
        display.update(phase="stopped", instruction="Stopped.", remaining=0)

    @asynccontextmanager
    async def lifespan(app):
        async def watch():
            while True:
                await asyncio.sleep(5)
                if trial.session_id and time.monotonic() - trial.last_client > 20:
                    await stop()
                    trial.error = "Visual controller disconnected; calibration stopped."

        watcher = asyncio.create_task(watch())
        yield
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
        await stop()
        await trial.client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(LocalBridgeGuard, origins=(), token=secrets.token_urlsafe(24))

    @app.get("/")
    async def home():
        return FileResponse(Path(__file__).with_suffix(".html"))

    @app.get("/state")
    async def state():
        return trial.state() | {"display": display, "live_check": live_check}

    @app.post("/heartbeat")
    async def heartbeat():
        trial.last_client = time.monotonic()
        return {"ok": True}

    @app.post("/fit")
    async def fit():
        async with trial.lock:
            if trial.stage != "idle":
                raise HTTPException(409, "Calibration is already underway")
            trial.last_client = time.monotonic()
            await trial.begin_session("review")
            trial.stage = "fit"
        return {"ok": True}

    @app.post("/start")
    async def start():
        nonlocal job
        async with trial.lock:
            if trial.stage != "fit" or not trial.state()["fit_ready"]:
                raise HTTPException(409, "Waiting for clean contact")
            trial.stage = "signal"
            job = asyncio.create_task(execute())
        return {"ok": True}

    @app.post("/catchup/{flag_id}")
    async def open_catchup(flag_id: str):
        if flag_id not in trial.catchups or not trial.ws:
            raise HTTPException(404)
        await trial.ws.send(json.dumps({"type": "open_catchup", "flag_id": flag_id}))
        if flag_id not in trial.opened:
            trial.opened.append(flag_id)
            trial.log("catchup_opened", {"flag_id": flag_id})
        return trial.catchups[flag_id]

    @app.post("/stop")
    async def stop_route():
        await stop()
        return {"ok": True}

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-check", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        create_calibration_app(prepare_cues(), live_check=args.live_check),
        host="127.0.0.1",
        port=8776,
        access_log=False,
    )
