"""Bounded, ephemeral whiteboard capture and asynchronous button explanations."""

from __future__ import annotations

import asyncio
import base64
from collections import deque

from ..ids import new_id


class BoardCapture:
    def __init__(self, runtime):
        self.rt = runtime
        self.frames: deque[dict] = deque(maxlen=45)
        self.task: asyncio.Task | None = None

    def prune(self, now: float) -> None:
        while self.frames and self.frames[0]["t"] < now - 90:
            self.frames.popleft()

    def add(self, image: str) -> dict:
        if not image.startswith("data:image/jpeg;base64,") or len(image) > 220_000:
            raise ValueError("Expected a JPEG frame under 220 KB")
        try:
            raw = base64.b64decode(image.split(",", 1)[1], validate=True)
        except ValueError as exc:
            raise ValueError("Invalid image encoding") from exc
        if not raw.startswith(b"\xff\xd8\xff"):
            raise ValueError("Invalid JPEG frame")
        now = self.rt.clock.now()
        if self.frames and now - self.frames[-1]["t"] < 1:
            raise ValueError("Capture at most one frame per second")
        while self.frames and self.frames[0]["t"] < now - 90:
            self.frames.popleft()
        frame = {"id": new_id("frame"), "t": round(now, 3), "image": image}
        self.frames.append(frame)
        return {"id": frame["id"], "t": frame["t"]}

    def on_tap(self, flag: dict) -> None:
        # Never defeat the study's randomized catch-up withholding.
        if not flag.get("catchup_shown") or not self.frames:
            return
        if self.task and not self.task.done():
            self.rt.broadcast(
                {
                    "type": "notice",
                    "level": "info",
                    "text": "Moment saved; a board explanation is already being prepared.",
                }
            )
            return
        t = flag["t_trigger"]
        frames = [f for f in self.frames if max(0, t - 60) <= f["t"] <= t]
        if not frames:
            return
        picks = sorted(set([0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1]))
        selected = [frames[i] for i in picks]
        transcript = self.rt.transcript.text_between(max(0, t - 60), t)
        self.task = asyncio.create_task(self._explain(flag["id"], t, transcript, selected))

    async def _explain(self, flag_id: str, t: float, transcript: str, frames: list[dict]) -> None:
        self.rt.broadcast(
            {
                "type": "board_explanation",
                "status": "pending",
                "flag_id": flag_id,
                "text": "",
                "frames": [],
                "source": "pending",
            }
        )
        text, source = await self.rt.llm.board_explanation(transcript, frames)
        if self.rt.status == "running":
            self.rt.broadcast(
                {
                    "type": "board_explanation",
                    "status": "ready",
                    "flag_id": flag_id,
                    "text": text,
                    "source": source,
                    "t": t,
                    "frames": [{"id": f["id"], "t": f["t"]} for f in frames],
                }
            )

    async def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.frames.clear()
