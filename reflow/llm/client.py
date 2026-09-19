"""OpenAI Responses client with strict JSON-schema outputs, disk cache, timeouts and the offline fallback (TDD §7)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import Settings
from ..store.db import DB
from . import fallback
from .prompts import PACKAGE_INSTRUCTIONS, PROMPT_VERSION, RECAP_INSTRUCTIONS
from .schemas import GapPackage, RecapForms, strict_schema

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """No key, or the API kept failing, and offline placeholders are not allowed (the default)."""


def _is_reasoning_model(model: str) -> bool:
    m = model.lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


class LLMClient:
    def __init__(self, settings: Settings, db: DB | None, client: Any | None = None) -> None:
        self.s = settings
        self.db = db
        self.model = settings.openai_model
        self.enabled = bool(settings.openai_api_key) or client is not None
        self._client = client
        if self._client is None and settings.openai_api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.stats = {
            "calls": 0,
            "cache_hits": 0,
            "fallbacks": 0,
            "errors": 0,
            "timeouts": 0,
            "unavailable": 0,
        }
        self._use_reasoning = _is_reasoning_model(self.model)
        self.last_error: str | None = None

    @property
    def offline_allowed(self) -> bool:
        return bool(self.s.allow_offline_llm)

    def _unavailable(self, task: str) -> LLMUnavailable:
        self.stats["unavailable"] += 1
        reason = "no OPENAI_API_KEY" if not self.enabled else (self.last_error or "OpenAI call failed")
        return LLMUnavailable(f"{task}: {reason}")

    # ---- public tasks ----
    async def recap(
        self, window_text: str, corpus_text: str, keyterms: list[str] | None = None
    ) -> tuple[RecapForms, str]:
        payload = {"transcript_last_30s": window_text, "key_terms": keyterms or []}
        obj, source = await self._structured(
            "recap", RECAP_INSTRUCTIONS, payload, RecapForms, self.s.recap_timeout_seconds, 400
        )
        if obj is None:
            if not self.offline_allowed:
                raise self._unavailable("recap")
            self.stats["fallbacks"] += 1
            return fallback.recap_forms(window_text, corpus_text), "offline"
        return obj, source

    async def gap_package(
        self,
        span_text: str,
        context_text: str,
        corpus_text: str,
        keyterms: list[str] | None = None,
        seed: int = 0,
    ) -> tuple[GapPackage, str]:
        payload = {"missed_span": span_text, "context_before_span": context_text, "key_terms": keyterms or []}
        obj: GapPackage | None = None
        source = "offline"
        attempts = 3 if self.enabled else 1
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(2.0 * attempt)
            obj, source = await self._structured(
                "package", PACKAGE_INSTRUCTIONS, payload, GapPackage, self.s.package_timeout_seconds, 2500
            )
            if obj is not None:
                break
        if obj is None:
            if not self.offline_allowed:
                raise self._unavailable("gap package")
            self.stats["fallbacks"] += 1
            return fallback.gap_package(span_text, context_text, corpus_text, seed=seed), "offline"
        return obj, source

    # ---- machinery ----
    def _key(self, task: str, payload: dict) -> str:
        raw = "|".join(
            [task, self.model, PROMPT_VERSION, json.dumps(payload, sort_keys=True, ensure_ascii=False)]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _structured(
        self, task: str, instructions: str, payload: dict, model_cls: type[T], timeout: float, max_tokens: int
    ) -> tuple[T | None, str]:
        key = self._key(task, payload)
        if self.db is not None:
            cached = self.db.cache_get(key)
            if cached is not None:
                try:
                    self.stats["cache_hits"] += 1
                    return model_cls.model_validate(cached), "cache"
                except ValidationError:
                    pass
        if not self.enabled or self._client is None:
            return None, "offline"
        user_input = json.dumps(payload, ensure_ascii=False)
        fmt = {
            "type": "json_schema",
            "name": model_cls.__name__,
            "schema": strict_schema(model_cls),
            "strict": True,
        }
        try:
            obj = await asyncio.wait_for(
                self._call(instructions, user_input, fmt, model_cls, max_tokens), timeout=timeout
            )
        except TimeoutError:
            self.stats["timeouts"] += 1
            self.last_error = f"timed out after {timeout:.0f}s"
            log.warning("llm %s timed out after %.0fs", task, timeout)
            return None, "offline"
        except Exception as e:  # noqa: BLE001
            self.stats["errors"] += 1
            self.last_error = str(e)[:300]
            log.warning("llm %s failed: %s", task, e)
            return None, "offline"
        if obj is None:
            return None, "offline"
        if self.db is not None:
            self.db.cache_put(key, task, self.model, obj.model_dump())
        return obj, "llm"

    async def _call(
        self, instructions: str, user_input: str, fmt: dict, model_cls: type[T], max_tokens: int
    ) -> T | None:
        text = await self._raw(instructions, user_input, fmt, max_tokens)
        try:
            return model_cls.model_validate_json(text)
        except ValidationError as e:
            log.info("llm output invalid, retrying once: %s", str(e)[:200])
            retry_input = (
                user_input
                + f"\n\nYour previous output was rejected: {str(e)[:300]}. Return a corrected object."
            )
            text = await self._raw(instructions, retry_input, fmt, max_tokens)
            return model_cls.model_validate_json(text)

    async def _raw(self, instructions: str, user_input: str, fmt: dict, max_tokens: int) -> str:
        assert self._client is not None
        kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": user_input,
            "text": {"format": fmt},
            "max_output_tokens": max_tokens,
        }
        if self._use_reasoning:
            kwargs["reasoning"] = {"effort": "minimal"}
        self.stats["calls"] += 1
        try:
            resp = await self._client.responses.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "reasoning" in msg and self._use_reasoning:
                self._use_reasoning = False
                kwargs.pop("reasoning", None)
                self.stats["calls"] += 1
                resp = await self._client.responses.create(**kwargs)
            else:
                raise
        text = getattr(resp, "output_text", None) or ""
        if not text.strip():
            raise RuntimeError("empty model output")
        return text
