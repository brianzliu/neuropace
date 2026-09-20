"""REST routes (TDD §9.1)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..core import tally as tallymod
from ..core.gaps import regenerate_packages
from ..core.lossmap import compute_lossmap
from ..core.next_step import NextStepIn, next_step
from ..core.office_hours import OfficeHoursEngine
from ..core.review import ReviewEngine
from ..core.review_recommendation import ReviewRecommendationIn, recommend_review
from ..core.session import SessionRuntime
from ..core.study import analyze, lossmap_inputs
from ..doctor import detect_devices, run_doctor
from ..ids import new_id
from ..signal.headset import headset_port_key, resolve_headset
from ..transcribe.scripted import script_from_text

router = APIRouter()


def _db(request: Request):
    return request.app.state.db


def _s(request: Request):
    return request.app.state.settings


# ---------------------------------------------------------------- health / doctor
@router.get("/health")
def health(request: Request):
    # voice: the tutor can speak (a Deepgram key is set); cheap, no network
    return {
        "ok": True,
        "version": __version__,
        "time": time.time(),
        "voice": bool(_s(request).tts_api_key),
    }


@router.get("/doctor")
async def doctor(request: Request):
    return await run_doctor(_s(request))


class TTSIn(BaseModel):
    text: str


@router.post("/tts")
async def tts(body: TTSIn, request: Request):
    """The tutor voice for one beat of an explanation (mp3), cached on disk."""
    from ..tts import TTSUnavailable, synthesize

    try:
        audio = await synthesize(_s(request), body.text)
    except TTSUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return Response(
        content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


class ManimRenderIn(BaseModel):
    title: str
    caption: str
    scene_name: str
    script: str


@router.post("/manim/render")
async def manim_render_route(body: ManimRenderIn, request: Request):
    """A math animation for Office Hours' "manim" board kind (docs/PRODUCT.md §5a), rendered on first
    request and disk-cached after (same shape as /tts). Optional end to end: 503s when manim isn't
    installed on this server, so a board that used it just falls back to its caption text."""
    from pydantic import ValidationError

    from ..llm.schemas import ManimAnimation
    from ..manim_render import ManimUnavailable
    from ..manim_render import render as render_manim

    try:
        validated = ManimAnimation(
            title=body.title, caption=body.caption, scene_name=body.scene_name, script=body.script
        )
    except ValidationError as e:
        raise HTTPException(400, str(e)) from e
    try:
        video = await render_manim(_s(request), validated.script, validated.scene_name)
    except ManimUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return Response(
        content=video, media_type="video/mp4", headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/devices")
async def devices(request: Request):
    """Headset and pad detection only (no network calls): cheap enough for the Listen screen to poll."""
    return await detect_devices(_s(request))


@router.get("/settings/deepgram")
def deepgram_key_status(request: Request):
    return {"configured": bool(_s(request).deepgram_api_key)}


@router.put("/settings/deepgram")
async def set_deepgram_key(request: Request):
    # Keep credentials in this backend process only, never in learner data or responses.
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Enter a valid Deepgram API key.") from None
    key = body.get("api_key") if isinstance(body, dict) else None
    if not isinstance(key, str) or not key.strip() or len(key) > 512 or any(c.isspace() for c in key.strip()):
        raise HTTPException(400, "Enter a valid Deepgram API key.")
    _s(request).deepgram_api_key = key.strip()
    return {"configured": True}


class ModelSettingsIn(BaseModel):
    provider: str
    api_key: str | None = None
    model: str | None = None


def _model_settings(request: Request) -> dict:
    s = _s(request)
    return {
        "provider": s.llm_provider,
        "model": s.llm_model,
        "models": {p: getattr(s, f"{p}_model") for p in ("openai", "openrouter", "gemini")},
        "configured": {p: bool(getattr(s, f"{p}_api_key")) for p in ("openai", "openrouter", "gemini")},
    }


@router.get("/settings/model")
def model_settings(request: Request):
    return _model_settings(request)


@router.put("/settings/model")
def set_model_settings(body: ModelSettingsIn, request: Request):
    from ..llm.client import LLMClient

    provider = body.provider.lower().strip()
    if provider not in ("openai", "openrouter", "gemini"):
        raise HTTPException(400, "Provider must be OpenAI, OpenRouter or Gemini.")
    key = body.api_key.strip() if isinstance(body.api_key, str) else ""
    if key and (len(key) > 512 or any(c.isspace() for c in key)):
        raise HTTPException(400, "Enter a valid API key.")
    model = body.model.strip() if isinstance(body.model, str) else ""
    if not model or len(model) > 200 or any(c.isspace() for c in model):
        raise HTTPException(400, "Enter a valid model name.")
    s = _s(request)
    if not (key or getattr(s, f"{provider}_api_key")):
        raise HTTPException(400, f"Enter an API key for {provider.title()}.")
    if key:
        setattr(s, f"{provider}_api_key", key)
    setattr(s, f"{provider}_model", model)
    s.llm_provider = provider
    # A key/model change can repair an outage during a lecture. In-flight calls
    # finish on their original client; subsequent work shares the new quota queue.
    llm = LLMClient(s, _db(request))
    request.app.state.llm = llm
    for runtime in request.app.state.runtimes.values():
        runtime.llm = llm
        runtime.recaps.llm = llm
    return _model_settings(request)


class DemoModeIn(BaseModel):
    enabled: bool


@router.get("/settings/demo")
def demo_mode(request: Request):
    return {"enabled": request.app.state.demo.enabled, "synthetic": True}


@router.put("/settings/demo")
def set_demo_mode(body: DemoModeIn, request: Request):
    """Switch between the learner's database and an isolated synthetic workspace."""
    if any(runtime.status == "running" for runtime in request.app.state.runtimes.values()):
        raise HTTPException(409, "End the live session before switching sample data.")

    from ..llm.client import LLMClient

    demo = request.app.state.demo
    demo.set_enabled(body.enabled)
    request.app.state.db = demo.database(request.app.state.llm) if body.enabled else request.app.state.real_db
    request.app.state.reviews.clear()
    request.app.state.llm = LLMClient(_s(request), _db(request))
    return {"enabled": demo.enabled, "synthetic": True}


@router.get("/devices/status")
async def device_status(request: Request):
    from ..signal.headset import autodetect_headset_port
    from ..totem.bridge import autodetect_totem_port

    hp = await asyncio.to_thread(autodetect_headset_port, False)
    tp = await asyncio.to_thread(autodetect_totem_port, hp)
    return {
        "headset": {"port": hp, "kind": "real" if hp else "simulated", "setting": _s(request).headset_port},
        "totem": {"port": tp, "kind": "real" if tp else "simulated", "setting": _s(request).totem_port},
    }


@router.get("/devices/uno-q")
async def scan_uno_q():
    from ..totem.uno_q import discover

    return await discover()


# ---------------------------------------------------------------- learners
class LearnerIn(BaseModel):
    name: str


@router.get("/learners")
def list_learners(request: Request):
    return {"learners": _db(request).list_learners()}


@router.post("/learners")
def create_learner(body: LearnerIn, request: Request):
    return _db(request).create_learner(body.name)


@router.get("/learners/{learner_id}")
def get_learner(learner_id: str, request: Request):
    db = _db(request)
    lr = db.default_learner() if learner_id == "me" else db.get_learner(learner_id)
    if not lr:
        raise HTTPException(404, "unknown learner")
    return lr


@router.get("/learners/{learner_id}/tally")
def learner_tally(learner_id: str, request: Request):
    db = _db(request)
    if learner_id == "me":
        learner_id = db.default_learner()["id"]
    if not db.get_learner(learner_id):
        raise HTTPException(404, "unknown learner")
    return tallymod.summary(
        db.get_tally(learner_id),
        db.population_tally(),
        _s(request),
        np.random.default_rng(),
        focus=db.card_focus_by_form(learner_id),
    )


@router.get("/learners/{learner_id}/dashboard")
async def learner_dashboard(learner_id: str, request: Request, organize: bool = False):
    from ..core.dashboard import dashboard_data, organize_dashboard

    db = _db(request)
    if not db.get_learner(learner_id):
        raise HTTPException(404, "unknown learner")
    data = dashboard_data(db, learner_id)
    if not organize:
        data.pop("_session_inputs", None)
        return data
    return await organize_dashboard(request.app.state.llm, data)


@router.get("/me/profile")
def me_profile(request: Request, learner_id: str | None = None):
    """The device learner's profile: streak, moments, and how they learn best (docs/PRODUCT.md §5)."""
    db = _db(request)
    me = db.get_learner(learner_id) if learner_id else db.default_learner()
    if not me:
        raise HTTPException(404, "unknown learner")
    stats = db.profile_stats(me["id"])
    tally = tallymod.summary(
        db.get_tally(me["id"]),
        db.population_tally(),
        _s(request),
        np.random.default_rng(),
        focus=db.card_focus_by_form(me["id"]),
    )
    return {"learner": me, "stats": stats, "tally": tally, "calibrated": me.get("baseline_mu") is not None}


@router.post("/me/reset")
def me_reset(request: Request, learner_id: str | None = None):
    db = _db(request)
    me = db.get_learner(learner_id) if learner_id else db.default_learner()
    if not me:
        raise HTTPException(404, "unknown learner")
    db.reset_profile(me["id"])
    return {"ok": True, "learner": db.get_learner(me["id"])}


# ---------------------------------------------------------------- lectures
@router.get("/lectures")
def list_lectures(request: Request):
    return {"lectures": _db(request).list_lectures()}


@router.get("/lectures/{lecture_id}")
def get_lecture(lecture_id: str, request: Request, full: int = 0):
    lec = _db(request).get_lecture(lecture_id, full=bool(full))
    if not lec:
        raise HTTPException(404, "unknown lecture")
    return lec


@router.post("/lectures")
async def create_lecture(
    request: Request,
    title: str = Form(...),
    file: UploadFile | None = File(None),
    script: UploadFile | None = File(None),
    text: str | None = Form(None),
    segments: str | None = Form(None),
    quiz: str | None = Form(None),
    keyterms: str | None = Form(None),
):
    s, db = _s(request), _db(request)
    lid = new_id("lec")
    words: list[dict] | None = None
    media_path: str | None = None
    kind = "scripted"
    kt = json.loads(keyterms) if keyterms else []
    if script is not None:
        data = json.loads((await script.read()).decode())
        words = data.get("words") or [
            w.to_dict() for w in script_from_text(data["text"], data.get("wpm", 150.0))
        ]
        segments = segments or json.dumps(data.get("segments", []))
        quiz = quiz or json.dumps(data.get("quiz", []))
        kt = kt or data.get("keyterms", [])
    elif text:
        words = [w.to_dict() for w in script_from_text(text)]
    if file is not None:
        kind = "media"
        dest_dir = s.lectures_dir / lid
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "media.bin").suffix or ".bin"
        dest = dest_dir / f"media{ext}"
        with dest.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        media_path = str(dest)
        if words is None:
            if not s.deepgram_api_key:
                raise HTTPException(400, "media upload needs DEEPGRAM_API_KEY (or attach a script)")
            from ..transcribe.deepgram_prerecorded import transcribe_file

            words = [
                w.to_dict() for w in await transcribe_file(dest, s.deepgram_api_key, s.deepgram_model, kt)
            ]
    if not words:
        raise HTTPException(400, "provide a media file, a script JSON, or text")
    lec = db.create_lecture(
        title=title,
        kind=kind,
        words=words,
        segments=json.loads(segments) if segments else [],
        quiz=json.loads(quiz) if quiz else [],
        keyterms=kt,
        media_path=media_path,
        lecture_id=lid,
    )
    lec.pop("words", None)
    return lec


@router.get("/lectures/{lecture_id}/lossmap")
def lecture_lossmap(lecture_id: str, request: Request):
    s, db = _s(request), _db(request)
    lec = db.get_lecture(lecture_id)
    if not lec:
        raise HTTPException(404, "unknown lecture")
    sessions = [
        x for x in db.list_sessions(lecture_id=lecture_id) if x["status"] in ("ended", "reviewed", "running")
    ]
    inputs = [x for x in lossmap_inputs(db, sessions, s) if x["samples"] or x["taps"]]
    out = compute_lossmap(inputs, lec.get("duration") or 0.0, lec.get("segments"), s)
    out["lecture"] = {"id": lec["id"], "title": lec["title"], "duration": lec.get("duration")}
    return out


@router.get("/lectures/{lecture_id}/study")
def lecture_study(lecture_id: str, request: Request):
    try:
        return analyze(_db(request), _s(request), lecture_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


# ---------------------------------------------------------------- sessions
class SessionIn(BaseModel):
    learner_id: str | None = None  # default: this device's single learner ("me")
    learner_name: str | None = None  # study only: a participant name, created on first use
    lecture_id: str | None = None
    mode: str = "live"
    catchup_policy: str = "always"
    baseline_seconds: float | None = None
    use_stored_baseline: bool | None = None
    startup_calibration: bool = True
    auto_pause: bool = True
    headset: str = "auto"  # auto | sim | fake | replay:<dir> | serial:<port> | <device path>
    totem: str = "auto"  # auto | keyboard | <serial port>
    transcript: str = "auto"  # auto | scripted | deepgram | recorded
    seed: int | None = None


def _session_public(request: Request, sess: dict) -> dict:
    rt: SessionRuntime | None = request.app.state.runtimes.get(sess["id"])
    db = _db(request)
    out = dict(sess)
    out["running"] = rt is not None and rt.status == "running"
    out["flags"] = [rt._flag_public(f) for f in rt.flags.values()] if rt else db.get_flags(sess["id"])
    out["gaps"] = len(db.get_gaps(sess["id"]))
    out["words"] = rt.words_total if rt else len(db.get_words(sess["id"]))
    out["catchups_shown"] = (
        rt.catchups_shown if rt else sum(1 for f in out["flags"] if f.get("catchup_shown"))
    )
    if rt:
        out["headset"] = rt.headset_status()
        out["startup_calibration"] = rt.startup_calibration_status()
        out["totem"] = rt.totem.status()
        out["best_form"] = rt.best_form
        out["transcript_kind"] = rt.transcript_kind
    return out


@router.get("/sessions")
def list_sessions(request: Request, lecture_id: str | None = None, learner_id: str | None = None):
    return {
        "sessions": [_session_public(request, x) for x in _db(request).list_sessions(lecture_id, learner_id)]
    }


@router.post("/sessions")
async def create_session(body: SessionIn, request: Request):
    # Resolve and reserve devices atomically: parallel requests must not open two readers.
    async with request.app.state.session_start_lock:
        return await _create_session(body, request)


async def _create_session(body: SessionIn, request: Request):
    app = request.app
    s, db = _s(request), _db(request)
    if body.learner_name and body.learner_name.strip():
        learner = db.learner_by_name(body.learner_name) or db.create_learner(body.learner_name)
    elif body.learner_id:
        learner = db.get_learner(body.learner_id)
        if not learner:
            raise HTTPException(404, "unknown learner")
    else:
        learner = db.default_learner()
    lecture = db.get_lecture(body.lecture_id, full=True) if body.lecture_id else None
    if body.lecture_id and not lecture:
        raise HTTPException(404, "unknown lecture")
    if body.mode not in ("live", "recorded", "review", "office_hours"):
        raise HTTPException(400, "mode must be live, recorded, review or office_hours")
    if not app.state.llm.enabled and not s.allow_offline_llm:
        raise HTTPException(
            400,
            "An OpenAI, OpenRouter or Gemini API key is missing: recaps, gap notes and review cards need one. "
            "Add a key on the Team page or to .env and restart "
            "(NEUROPACE_ALLOW_OFFLINE_LLM=1 is for automated tests only).",
        )
    if body.mode == "office_hours":
        # an open conversation, not a lecture capture: no headset/totem/transcript, so skip that machinery
        # entirely (docs/PRODUCT.md §5a).
        seed = body.seed if body.seed is not None else int(time.time() * 1000) % 2_000_000_000
        sess = db.create_session(
            learner_id=learner["id"],
            lecture_id=(lecture or {}).get("id"),
            mode="office_hours",
            catchup_policy=body.catchup_policy,
            seed=seed,
            auto_pause=body.auto_pause,
        )
        app.state.office_hours[sess["id"]] = OfficeHoursEngine(
            db, s, app.state.llm, sess["id"], learner["id"], lecture
        )
        return _session_public(request, db.get_session(sess["id"]))  # type: ignore[arg-type]
    if body.catchup_policy not in ("always", "randomized"):
        raise HTTPException(400, "catchup_policy must be always or randomized")
    # transcript kind
    tk = body.transcript
    if body.mode == "review":
        tk = "none"  # restudy: headset only, so focus can be measured card by card
    elif tk == "auto":
        if body.mode == "recorded":
            tk = "recorded"
        elif lecture and lecture.get("words"):
            tk = "scripted"
        else:
            tk = "deepgram"
    if body.mode == "review":
        pass
    elif tk in ("scripted", "recorded") and not (lecture and lecture.get("words")):
        raise HTTPException(400, f"transcript={tk} needs a lecture with words")
    if tk == "deepgram" and not s.deepgram_api_key:
        raise HTTPException(400, "live microphone needs DEEPGRAM_API_KEY; pick a scripted lecture instead")
    if body.mode == "recorded" and tk != "recorded":
        raise HTTPException(400, "recorded mode uses the lecture transcript")
    settings = dataclasses.replace(s)
    if body.baseline_seconds is not None:
        settings.baseline_seconds = max(5.0, float(body.baseline_seconds))
    baseline = None
    use_stored = body.use_stored_baseline
    if use_stored is None:
        use_stored = learner.get("baseline_source") == "personal"
    if use_stored and learner.get("baseline_mu") is not None:
        baseline = {"mu": learner["baseline_mu"], "sigma": learner["baseline_sigma"], "stored": True}
    seed = body.seed if body.seed is not None else int(time.time() * 1000) % 2_000_000_000
    sess = db.create_session(
        learner_id=learner["id"],
        lecture_id=(lecture or {}).get("id"),
        mode=body.mode,
        catchup_policy=body.catchup_policy,
        baseline=baseline,
        seed=seed,
        auto_pause=body.auto_pause,
    )
    headset_setting = settings.headset_port if body.headset == "auto" else body.headset
    hp = await asyncio.to_thread(resolve_headset, headset_setting)
    # one headset, one session: two readers on the same serial port would split the bytes and corrupt both.
    # A lecture that is still recording wins (409). A session that is ending, or a headset-only restudy session
    # being replaced by the next screen, is given a few seconds to let go of the port.
    deadline = time.monotonic() + 4.0
    while True:
        holders = [
            o
            for o in app.state.runtimes.values()
            if o.headset.kind in ("real", "virtual")
            and headset_port_key(getattr(o.headset, "port", None)) == headset_port_key(hp)
            and o.status in ("running", "ending")
        ]
        lectures = [o for o in holders if o.status == "running" and o.mode != "review"]
        if lectures:
            db.update_session(sess["id"], status="ended", ended_at=time.time())
            raise HTTPException(
                409,
                f"The headset is already in use by a lecture that is still recording ({lectures[0].id}). End it first.",
            )
        if not holders:
            break
        if time.monotonic() > deadline:
            db.update_session(sess["id"], status="ended", ended_at=time.time())
            raise HTTPException(
                409, "The headset is still in use by another session. Close it and try again."
            )
        await asyncio.sleep(0.1)
    tp = (settings.totem_port or "auto") if body.totem == "auto" else body.totem
    rt = SessionRuntime(
        settings,
        db,
        app.state.llm,
        sess,
        learner,
        lecture,
        tk,
        headset_port=hp,
        totem_port=tp,
        headset_auto=(headset_setting or "auto") == "auto",
        device_lock=app.state.session_start_lock,
        runtimes=app.state.runtimes,
        startup_calibration=body.startup_calibration,
    )
    app.state.runtimes[sess["id"]] = rt
    await rt.start()
    return _session_public(request, db.get_session(sess["id"]))  # type: ignore[arg-type]


class BoardFrameIn(BaseModel):
    image: str = Field(max_length=220_000)


@router.delete("/sessions/{session_id}/board")
async def clear_board(session_id: str, request: Request):
    runtime = request.app.state.runtimes.get(session_id)
    if runtime:
        await runtime.board.stop()
    return {"ok": True}


@router.post("/sessions/{session_id}/board")
async def capture_board(session_id: str, body: BoardFrameIn, request: Request):
    runtime = request.app.state.runtimes.get(session_id)
    if runtime is None or runtime.status != "running":
        raise HTTPException(409, "session is not running")
    if runtime.mode != "live":
        raise HTTPException(400, "board capture is available in live sessions only")
    try:
        return runtime.board.add(body.image)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    sess = _db(request).get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    return _session_public(request, sess)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, request: Request):
    from .ws import end_session as _end

    db = _db(request)
    if not db.get_session(session_id):
        raise HTTPException(404, "unknown session")
    gaps = await _end(request.app, session_id)
    return {
        "gaps": [_gap_public(g) for g in gaps],
        "session": _session_public(request, db.get_session(session_id)),
    }  # type: ignore[arg-type]


@router.post("/sessions/{session_id}/tap")
def session_tap(session_id: str, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if not rt:
        raise HTTPException(404, "session is not running")
    if rt.calibration_pending:
        raise HTTPException(409, "Finish calibration before requesting a catch-up")
    return rt._flag_public(rt.tap(source="key"))


class SimHeadsetIn(BaseModel):
    state: str


@router.post("/sessions/{session_id}/sim/headset")
def sim_headset(session_id: str, body: SimHeadsetIn, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if not rt:
        raise HTTPException(404, "session is not running")
    try:
        rt.set_sim_headset(body.state)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return rt.headset_status()


class PersonalCalibrationIn(BaseModel):
    apply: bool = False


@router.post("/sessions/{session_id}/personal-calibration/start")
async def personal_calibration_start(session_id: str, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if rt is None:
        raise HTTPException(404, "session is not running")
    try:
        return rt.begin_personal_calibration()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/sessions/{session_id}/personal-calibration/finish")
async def personal_calibration_finish(session_id: str, body: PersonalCalibrationIn, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if rt is None:
        raise HTTPException(404, "session is not running")
    try:
        return rt.finish_personal_calibration(apply=body.apply)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.post("/sessions/{session_id}/personal-calibration/continue")
async def personal_calibration_continue(session_id: str, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if rt is None:
        raise HTTPException(404, "session is not running")
    try:
        return await rt.complete_startup_calibration()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class CalibrateIn(BaseModel):
    phase: str


@router.post("/sessions/{session_id}/calibrate")
def session_calibrate(session_id: str, body: CalibrateIn, request: Request):
    rt = request.app.state.runtimes.get(session_id)
    if not rt:
        raise HTTPException(404, "session is not running")
    rt.calibrate(body.phase)
    return rt.headset_status()


@router.get("/sessions/{session_id}/events")
def session_events(session_id: str, request: Request):
    s = _s(request)
    if not _db(request).get_session(session_id):
        raise HTTPException(404, "unknown session")
    path = s.sessions_dir / f"{session_id}.jsonl"
    events: list[dict] = []
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return {"session_id": session_id, "events": events}


def _gap_public(g: dict) -> dict:
    """What the notes page shows for one missed moment. The check question and the generated artifacts stay
    server-side: review hands them out card by card, and /artifacts is the team's preview of the rest."""
    pkg = g.get("package") or {}
    return {
        "id": g["id"],
        "ord": g["ord"],
        "t_start": g["t_start"],
        "t_end": g["t_end"],
        "span_text": g["span_text"],
        "flag_ids": g.get("flag_ids", []),
        "status": g["status"],
        "note": pkg.get("note"),
        "summary": (pkg.get("artifacts") or {}).get("summary"),
        "package_source": g.get("package_source"),
        "error": pkg.get("error"),
    }


@router.get("/sessions/{session_id}/notes")
def session_notes(session_id: str, request: Request):
    db = _db(request)
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    return {
        "session": _session_public(request, sess),
        "gaps": [_gap_public(g) for g in db.get_gaps(session_id)],
    }


@router.get("/sessions/{session_id}/artifacts")
def session_artifacts(session_id: str, request: Request):
    """Every generated artifact of every moment, for the team's preview (the check answers stay out)."""
    db = _db(request)
    if not db.get_session(session_id):
        raise HTTPException(404, "unknown session")
    out = []
    for g in db.get_gaps(session_id):
        pkg = g.get("package") or {}
        out.append(
            {
                **_gap_public(g),
                "artifacts": pkg.get("artifacts") or {},
                "sources": pkg.get("sources") or {},
            }
        )
    return {"gaps": out}


@router.post("/sessions/{session_id}/regenerate")
async def session_regenerate(session_id: str, request: Request, only_failed: int = 1):
    """Re-run gap note generation (after an OpenAI outage, or with a new key)."""
    db = _db(request)
    if not db.get_session(session_id):
        raise HTTPException(404, "unknown session")
    if request.app.state.runtimes.get(session_id):
        raise HTTPException(409, "end the session first")
    gaps = await regenerate_packages(db, request.app.state.llm, session_id, only_failed=bool(only_failed))
    request.app.state.reviews.pop(session_id, None)
    return {
        "gaps": [_gap_public(g) for g in gaps],
        "failed": sum(1 for g in gaps if g.get("package_source") == "failed"),
    }


# ---------------------------------------------------------------- review
def _review(request: Request, session_id: str) -> ReviewEngine:
    app = request.app
    db = _db(request)
    eng = app.state.reviews.get(session_id)
    if eng is None:
        sess = db.get_session(session_id)
        if not sess:
            raise HTTPException(404, "unknown session")
        if sess["status"] == "running":
            raise HTTPException(409, "end the session first")
        missing = [
            g for g in db.get_gaps(session_id) if not g.get("package") or g.get("package_source") == "failed"
        ]
        if missing:
            raise HTTPException(
                409,
                f"{len(missing)} gap(s) have no generated notes yet: retry generation from the notes page",
            )
        eng = ReviewEngine(db, _s(request), session_id, sess["learner_id"], seed=int(sess.get("seed") or 0))
        app.state.reviews[session_id] = eng
    return eng


class AnswerIn(BaseModel):
    card_id: str
    choice: int
    focus_ratio: float | None = (
        None  # fraction of the card's seconds not in a drop (headset on), client-measured
    )


class CardIn(BaseModel):
    card_id: str
    focus_ratio: float | None = None


class ReviewStartIn(BaseModel):
    mode: str = "tutor"  # tutor (explained first, the voice can read it) | manual (the check first, no voice)


@router.post("/sessions/{session_id}/review/start")
def review_start(session_id: str, request: Request, body: ReviewStartIn | None = None):
    eng = _review(request, session_id)
    mode = (body.mode if body else "tutor").strip().lower()
    if mode not in ReviewEngine.MODES:
        raise HTTPException(400, "mode must be tutor or manual")
    eng.mode = mode  # only decides how the next moment opens; a card already open stays
    out = eng.start()
    if out["progress"]["done"]:
        _db(request).update_session(session_id, status="reviewed")
    return out


@router.get("/sessions/{session_id}/review")
def review_state(session_id: str, request: Request):
    return _review(request, session_id).state()


@router.post("/sessions/{session_id}/review/answer")
def review_answer(session_id: str, body: AnswerIn, request: Request):
    eng = _review(request, session_id)
    try:
        out = eng.answer(body.card_id, body.choice, body.focus_ratio)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if out["done"]:
        _db(request).update_session(session_id, status="reviewed")
    return out


@router.post("/sessions/{session_id}/review/drop")
def review_drop(session_id: str, body: CardIn, request: Request):
    eng = _review(request, session_id)
    try:
        out = eng.drop(body.card_id, body.focus_ratio)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if out["done"]:
        _db(request).update_session(session_id, status="reviewed")
    return out


@router.post("/sessions/{session_id}/review/advance")
def review_advance(session_id: str, body: CardIn, request: Request):
    eng = _review(request, session_id)
    try:
        return eng.advance(body.card_id, body.focus_ratio)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class AskIn(BaseModel):
    card_id: str
    text: str


@router.post("/sessions/{session_id}/review/ask")
async def review_ask(session_id: str, body: AskIn, request: Request):
    """One question about the card on screen, one answer; nothing is remembered between asks."""
    eng = _review(request, session_id)
    text = " ".join((body.text or "").split())
    if not text:
        raise HTTPException(400, "empty question")
    card = _db(request).get_card(body.card_id)
    if card is None or card["session_id"] != session_id:
        raise HTTPException(400, "unknown card")
    gap = next((g for g in eng.gaps if g["id"] == card["gap_id"]), None)
    if gap is None:
        raise HTTPException(400, "unknown card")
    pkg = gap.get("package") or {}
    shown = ""
    presented = eng._present(card)
    if presented and presented.get("reteach"):
        shown = json.dumps(presented["reteach"].get("content") or {}, ensure_ascii=False)[:1500]
    reply, source = await request.app.state.llm.review_ask(
        text, gap.get("span_text") or "", gap.get("context_text") or "", pkg.get("note") or {}, shown
    )
    if reply is None:
        return {
            "reply": "I couldn't reach the model just now. Here is what was said: "
            + (gap.get("span_text") or "")[:400],
            "source": "offline",
        }
    return {"reply": reply, "source": source}


# ---------------------------------------------------------------- office hours (docs/PRODUCT.md §5a)


@router.post("/sessions/{session_id}/office_hours/open")
def office_hours_open(session_id: str, request: Request):
    """The one whiteboard conversation for a lecture session: found if it exists, created once otherwise."""
    app = request.app
    s, db = _s(request), _db(request)
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    if sess["mode"] == "office_hours":
        return _session_public(request, sess)
    existing = db.child_session(session_id, "office_hours")
    if existing:
        return _session_public(request, existing)
    if not app.state.llm.enabled and not s.allow_offline_llm:
        raise HTTPException(400, "The whiteboard needs an OpenAI, OpenRouter or Gemini API key.")
    lecture = db.get_lecture(sess["lecture_id"], full=True) if sess.get("lecture_id") else None
    oh = db.create_session(
        learner_id=sess["learner_id"],
        lecture_id=sess.get("lecture_id"),
        mode="office_hours",
        catchup_policy=sess.get("catchup_policy") or "always",
        seed=int(time.time() * 1000) % 2_000_000_000,
        parent_session_id=session_id,
    )
    app.state.office_hours[oh["id"]] = OfficeHoursEngine(
        db, s, app.state.llm, oh["id"], sess["learner_id"], lecture
    )
    return _session_public(request, oh)


def _office_hours(request: Request, session_id: str) -> OfficeHoursEngine:
    app = request.app
    eng = app.state.office_hours.get(session_id)
    if eng is None:
        db = _db(request)
        sess = db.get_session(session_id)
        if not sess or sess["mode"] != "office_hours":
            raise HTTPException(404, "unknown office hours session")
        lecture = db.get_lecture(sess["lecture_id"], full=True) if sess.get("lecture_id") else None
        eng = OfficeHoursEngine(db, _s(request), app.state.llm, session_id, sess["learner_id"], lecture)
        app.state.office_hours[session_id] = eng
    return eng


@router.get("/sessions/{session_id}/office_hours")
def office_hours_state(session_id: str, request: Request, upto_ord: int | None = None):
    return _office_hours(request, session_id).snapshot(upto_ord)


class OHMessageIn(BaseModel):
    text: str


@router.post("/sessions/{session_id}/office_hours/message")
async def office_hours_message(session_id: str, body: OHMessageIn, request: Request):
    eng = _office_hours(request, session_id)
    try:
        return await eng.send_message(body.text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/sessions/{session_id}/office_hours/message/stream")
async def office_hours_message_stream(session_id: str, body: OHMessageIn, request: Request):
    """Same turn as office_hours_message, as Server-Sent Events: the reply text and each board element
    arrive as soon as the model finishes them instead of all at once at the end. See
    OfficeHoursEngine.send_message_stream for the event shapes."""
    eng = _office_hours(request, session_id)

    async def gen():
        try:
            async for event in eng.send_message_stream(body.text):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class OHExpandIn(BaseModel):
    element_id: str


@router.post("/sessions/{session_id}/office_hours/expand")
async def office_hours_expand(session_id: str, body: OHExpandIn, request: Request):
    eng = _office_hours(request, session_id)
    try:
        return await eng.expand_element(body.element_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


async def _transcribe_clip(request: Request, file: UploadFile) -> str:
    """One bounded push-to-talk clip in, its text out (Deepgram prerecorded)."""
    import mimetypes
    import tempfile

    from ..transcribe.deepgram_prerecorded import transcribe_file

    s = _s(request)
    if not s.deepgram_api_key:
        raise HTTPException(400, "push-to-talk needs DEEPGRAM_API_KEY; type your question instead")
    content = await file.read(20_000_001)
    if len(content) > 20_000_000:
        raise HTTPException(413, "Keep a push-to-talk clip under 20 MB")
    suffix = mimetypes.guess_extension(file.content_type or "") or Path(file.filename or "").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(content)
        tmp.flush()
        try:
            words = await transcribe_file(tmp.name, s.deepgram_api_key, s.deepgram_model)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"transcription failed: {e}") from e
    text = " ".join(w.w for w in words).strip()
    if not text:
        raise HTTPException(400, "Could not hear anything in that clip; try again")
    return text


@router.post("/transcribe")
async def transcribe_clip(request: Request, file: UploadFile = File(...)):
    """Hold-to-talk for any text box (Review's Ask): the clip's words, nothing else."""
    return {"text": await _transcribe_clip(request, file)}


@router.post("/sessions/{session_id}/office_hours/voice")
async def office_hours_voice(session_id: str, request: Request, file: UploadFile = File(...)):
    """Push-to-talk (docs/PRODUCT.md §5a): one bounded clip in, transcribed, run through the same turn path
    as typed chat. No streaming, no barge-in: releasing the button ends the clip."""
    eng = _office_hours(request, session_id)
    text = await _transcribe_clip(request, file)
    try:
        reply = await eng.send_message(text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"text": text, "reply": reply}


# ---------------------------------------------------------------- quiz (study)
class QuizIn(BaseModel):
    phase: str = "before"
    answers: dict[str, int]


@router.get("/sessions/{session_id}/quiz")
def quiz_get(session_id: str, request: Request):
    db = _db(request)
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    lec = db.get_lecture(sess["lecture_id"]) if sess.get("lecture_id") else None
    items = []
    for q in (lec or {}).get("quiz") or []:
        items.append(
            {"id": q["id"], "question": q["question"], "options": q["options"], "segment": q.get("segment")}
        )
    return {"items": items, "answers": db.get_quiz_answers(session_id)}


@router.post("/sessions/{session_id}/quiz")
def quiz_post(session_id: str, body: QuizIn, request: Request):
    db = _db(request)
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    if body.phase not in ("before", "after"):
        raise HTTPException(400, "phase must be before or after")
    lec = db.get_lecture(sess["lecture_id"]) if sess.get("lecture_id") else None
    items = {q["id"]: q for q in (lec or {}).get("quiz") or []}
    rows: list[dict[str, Any]] = []
    for iid, choice in body.answers.items():
        q = items.get(iid)
        if not q:
            continue
        rows.append(
            {"item_id": iid, "choice": int(choice), "correct": int(choice) == int(q["correct_index"])}
        )
    db.set_quiz_answers(session_id, body.phase, rows)
    score = sum(r["correct"] for r in rows)
    return {"phase": body.phase, "score": score, "total": len(rows), "per_item": rows}


# ---------------------------------------------------------------- guided study navigation


@router.post("/sessions/{session_id}/next-step")
async def session_next_step(session_id: str, body: NextStepIn, request: Request):
    db = _db(request)
    session = db.get_session(session_id)
    if not session or session["learner_id"] != body.learner_id:
        raise HTTPException(404, "unknown session")
    if session["status"] not in ("ended", "reviewed"):
        raise HTTPException(409, "end the session first")
    return await next_step(db, request.app.state.llm, session, body)


@router.post("/sessions/{session_id}/review/recommendation")
async def review_recommendation(session_id: str, body: ReviewRecommendationIn, request: Request):
    db = _db(request)
    session = db.get_session(session_id)
    if not session or session["learner_id"] != body.learner_id:
        raise HTTPException(404, "unknown session")
    if session["status"] not in ("ended", "reviewed"):
        raise HTTPException(409, "end the session first")
    for linked_id in (body.focus_session_id, body.conversation_session_id):
        if linked_id:
            linked = db.get_session(linked_id)
            if not linked or linked["learner_id"] != body.learner_id:
                raise HTTPException(404, "unknown session")
            if linked_id == body.conversation_session_id and (
                linked["mode"] != "office_hours" or linked.get("lecture_id") != session.get("lecture_id")
            ):
                raise HTTPException(400, "conversation must belong to this lecture")
    runtime = request.app.state.runtimes.get(body.focus_session_id or session_id)
    return await recommend_review(db, request.app.state.llm, session, body, runtime)
