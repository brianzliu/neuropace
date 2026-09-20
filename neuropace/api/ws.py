"""WebSocket endpoint (TDD §9.2). Text frames = JSON control, binary frames = PCM16 audio."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    app = websocket.app
    rt = app.state.runtimes.get(session_id)
    await websocket.accept()
    if rt is None:
        sess = app.state.db.get_session(session_id)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "text": "session is not running" if sess else "unknown session",
                    "status": (sess or {}).get("status"),
                }
            )
        )
        await websocket.close(code=4404)
        return
    q = rt.subscribe()
    await websocket.send_text(json.dumps(rt.snapshot(), ensure_ascii=False))

    async def sender() -> None:
        try:
            while True:
                msg = await q.get()
                await websocket.send_text(json.dumps(msg, ensure_ascii=False))
        except (asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
            pass

    send_task = asyncio.create_task(sender())
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await rt.handle_audio(message["bytes"])
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            await handle_client_message(app, rt, data)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await send_task
        rt.unsubscribe(q)


async def handle_client_message(app, rt, data: dict) -> None:
    t = data.get("type")
    if rt.calibration_pending and t not in ("end", "ping", "audio_stop"):
        return
    if t == "tap":
        rt.tap(source="key")
    elif t == "force_flag":
        rt.force_flag()
    elif t == "sim_headset":
        with contextlib.suppress(ValueError):
            rt.set_sim_headset(str(data.get("state", "focused")))
    elif t == "calibrate":
        rt.calibrate(str(data.get("phase", "")))
    elif t == "media_time":
        rt.set_media_time(float(data.get("t", 0.0)), bool(data.get("playing", False)))
    elif t == "open_catchup":
        rt.open_catchup(str(data.get("flag_id", "")))
    elif t == "dismiss_catchup":
        rt.dismiss_catchup(str(data.get("flag_id", "")))
    elif t == "audio_start":
        await rt.audio_start(int(data.get("sample_rate", 16000)))
    elif t == "audio_stop":
        await rt.audio_stop()
    elif t == "end":
        await end_session(app, rt.id)
    elif t == "ping":
        rt.broadcast({"type": "pong"})


async def end_session(app, session_id: str) -> list[dict]:
    rt = app.state.runtimes.get(session_id)
    if rt is None:
        return app.state.db.get_gaps(session_id)
    gaps = await rt.end()
    app.state.runtimes.pop(session_id, None)
    return gaps
