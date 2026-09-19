"""Deepgram streaming client (TDD §5.1): PCM16 frames in, word-timed transcript out, on lecture time."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import Callable
from urllib.parse import urlencode

from .transcript import Word

log = logging.getLogger(__name__)
WordsCallback = Callable[[list[Word], bool], None]

DEEPGRAM_WS = "wss://api.deepgram.com/v1/listen"


class DeepgramLive:
    kind = "deepgram"

    def __init__(
        self,
        api_key: str,
        on_words: WordsCallback,
        clock,
        sample_rate: int = 16000,
        model: str = "nova-3",
        keyterms: list[str] | None = None,
        language: str = "en",
    ) -> None:
        self.api_key = api_key
        self.on_words = on_words
        self.clock = clock
        self.sample_rate = sample_rate
        self.model = model
        self.keyterms = keyterms or []
        self.language = language
        self.ws = None
        self.connected = False
        self.error: str | None = None
        self.stream_t0: float | None = None
        self._reader: asyncio.Task | None = None
        self._keepalive: asyncio.Task | None = None
        self._last_audio = 0.0
        self._reconnects = 0
        self.words_received = 0

    def url(self) -> str:
        params: list[tuple[str, str]] = [
            ("model", self.model),
            ("encoding", "linear16"),
            ("sample_rate", str(self.sample_rate)),
            ("channels", "1"),
            ("punctuate", "true"),
            ("smart_format", "true"),
            ("interim_results", "true"),
            ("language", self.language),
        ]
        for k in self.keyterms[:50]:
            params.append(("keyterm", k))
        return DEEPGRAM_WS + "?" + urlencode(params)

    async def start(self) -> None:
        from websockets.asyncio.client import connect

        try:
            self.ws = await connect(
                self.url(), additional_headers={"Authorization": f"Token {self.api_key}"}, open_timeout=10
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"deepgram connect failed: {e}"
            log.warning(self.error)
            self.connected = False
            return
        self.connected = True
        self.error = None
        self._reader = asyncio.create_task(self._read(), name="deepgram-reader")
        self._keepalive = asyncio.create_task(self._keep(), name="deepgram-keepalive")

    async def _keep(self) -> None:
        try:
            while self.connected and self.ws is not None:
                await asyncio.sleep(5.0)
                if time.monotonic() - self._last_audio > 4.5:
                    with contextlib.suppress(Exception):
                        await self.ws.send(json.dumps({"type": "KeepAlive"}))
        except asyncio.CancelledError:
            pass

    async def _read(self) -> None:
        assert self.ws is not None
        try:
            async for msg in self.ws:
                if isinstance(msg, bytes):
                    continue
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue
                self._handle(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            self.error = f"deepgram stream closed: {e}"
            log.warning(self.error)
        finally:
            self.connected = False

    def _handle(self, data: dict) -> None:
        if data.get("type") != "Results":
            if data.get("type") == "Error":
                self.error = str(data)
            return
        try:
            alt = data["channel"]["alternatives"][0]
        except (KeyError, IndexError):
            return
        t0 = self.stream_t0 if self.stream_t0 is not None else 0.0
        words = [
            Word(
                w.get("punctuated_word") or w.get("word", ""),
                round(t0 + float(w["start"]), 3),
                round(t0 + float(w["end"]), 3),
            )
            for w in alt.get("words", [])
        ]
        is_final = bool(data.get("is_final"))
        if words:
            if is_final:
                self.words_received += len(words)
            self.on_words(words, is_final)

    async def send_audio(self, pcm: bytes) -> None:
        if not pcm:
            return
        if self.stream_t0 is None:
            self.stream_t0 = self.clock.now()
        if not self.connected or self.ws is None:
            if self._reconnects < 3:
                self._reconnects += 1
                await self.start()
                self.stream_t0 = self.clock.now()
            if not self.connected or self.ws is None:
                return
        try:
            await self.ws.send(pcm)
            self._last_audio = time.monotonic()
        except Exception as e:  # noqa: BLE001
            self.connected = False
            self.error = f"deepgram send failed: {e}"

    async def stop(self) -> None:
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.send(json.dumps({"type": "CloseStream"}))
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.ws.close(), timeout=3.0)
        for t in (self._reader, self._keepalive):
            if t:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        self.connected = False
