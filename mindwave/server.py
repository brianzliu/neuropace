"""WebSocket feed (ws://127.0.0.1:8765 by default).

Messages out (JSON, one object per message):
    {"type":"features", ...FeatureFrame fields...}                                           1 Hz
    {"type":"raw", "t", "fs": 64, "uv": [8 values]}                                          8 Hz
    {"type":"blink", "t", "amplitude_uv", "duration_ms"}                                     per blink
    {"type":"status", "connected", "quality", "calibrated", "cal_phase", ...}                on change
Messages in:
    {"type":"calibrate", "phase": "eyes_closed"|"easy"|"hard"|"done"|"reset"}
    {"type":"status"}    {"type":"ping"}
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import Pipeline


class WebSocketServer:
    def __init__(self, pipeline: "Pipeline", host: str = "127.0.0.1", port: int = 8765) -> None:
        self.pipeline, self.host, self.port = pipeline, host, port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._stop_event: asyncio.Event | None = None
        self._clients: set = set()
        self._thread: threading.Thread | None = None
        self.started = threading.Event()
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="mindwave-ws")
        self._thread.start()
        self.started.wait(5)
        if self.error or not self.started.is_set():
            print(f"[mindwave] WebSocket server failed to start on {self.host}:{self.port}: {self.error}")
            return
        p = self.pipeline
        p.on_frame(lambda f: self.push(f.to_dict()))
        p.on_blink(self.push)
        p.on_raw(self.push)
        p.on_status(self.push)
        print(f"[mindwave] WebSocket feed on ws://{self.host}:{self.port}")

    def stop(self) -> None:
        if self._loop is not None and self._stop_event is not None:
            try:
                self._loop.call_soon_threadsafe(self._stop_event.set)
            except RuntimeError:
                pass

    def push(self, msg: dict) -> None:
        """Thread-safe: called from the pipeline thread."""
        if self._loop is None or self._queue is None or not self._clients:
            return
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, json.dumps(msg))
        except RuntimeError:
            pass  # loop already closed

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception as e:
            self.error = str(e)
            self.started.set()

    async def _main(self) -> None:
        try:
            from websockets.asyncio.server import serve
        except ImportError:  # websockets < 13
            from websockets.server import serve
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
        async with serve(self._handler, self.host, self.port):
            self.started.set()
            sender = asyncio.create_task(self._broadcast_loop())
            await self._stop_event.wait()
            sender.cancel()

    async def _broadcast_loop(self) -> None:
        assert self._queue is not None
        while True:
            msg = await self._queue.get()
            targets = list(self._clients)
            if not targets:
                continue
            results = await asyncio.gather(*(ws.send(msg) for ws in targets), return_exceptions=True)
            for ws, r in zip(targets, results):
                if isinstance(r, Exception):
                    self._clients.discard(ws)

    async def _handler(self, ws) -> None:
        self._clients.add(ws)
        try:
            await ws.send(json.dumps(self.pipeline.status()))
            latest = self.pipeline.latest
            if latest is not None:
                await ws.send(latest.to_json())
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                kind = msg.get("type") if isinstance(msg, dict) else None
                if kind == "calibrate":
                    try:
                        self.pipeline.calibrate(str(msg.get("phase")))
                    except ValueError as e:
                        await ws.send(json.dumps({"type": "error", "message": str(e)}))
                        continue
                    await ws.send(json.dumps(self.pipeline.status()))
                elif kind == "status":
                    await ws.send(json.dumps(self.pipeline.status()))
                elif kind == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
        except Exception:
            pass  # connection closed
        finally:
            self._clients.discard(ws)
