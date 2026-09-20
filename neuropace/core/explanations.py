from __future__ import annotations

import asyncio
import logging

from ..llm.artifacts import build_package
from ..llm.schemas import pick_artifact

log = logging.getLogger(__name__)


class CatchupExplanations:
    def __init__(self, runtime):
        self.rt = runtime
        self.states: dict[str, dict] = {}
        self.jobs: dict[str, asyncio.Task] = {}
        self.packages: dict[tuple[str, str], tuple[dict, str]] = {}

    @staticmethod
    def _key(span: str, context: str) -> tuple[str, str]:
        return " ".join(span.split()), " ".join(context.split())

    def snapshot(self) -> list[dict]:
        return list(self.states.values())

    def _publish(self, flag_id: str, **state) -> dict:
        result = {"flag_id": flag_id, **state}
        self.states[flag_id] = result
        self.rt.broadcast({"type": "catchup_explanation", **result})
        return result

    def request(self, flag_id: str) -> dict:
        flag = self.rt.flags.get(flag_id)
        if flag is None or not flag.get("catchup_shown"):
            raise ValueError("No offered catch-up exists for this moment")
        if self.rt.status != "running" or self.rt.review_only:
            raise ValueError("Visual catch-ups require a running lecture")
        existing = self.states.get(flag_id)
        if existing and existing["status"] == "ready":
            return existing
        job = self.jobs.get(flag_id)
        if job is not None and not job.done():
            return self.states[flag_id]
        if sum(not task.done() for task in self.jobs.values()) >= 2:
            return self._publish(
                flag_id, status="failed", error="Another visual is still preparing. Retry in a moment."
            )
        start = max(0.0, flag["t_start"])
        end = min(
            self.rt.clock.now(), flag.get("t_end") or self.rt.clock.now(), start + self.rt.s.gap_max_seconds
        )
        span = self.rt.transcript.text_between(start, end)
        context = self.rt.transcript.text_between(max(0.0, start - 60.0), start)
        if len(span.split()) < 6:
            return self._publish(
                flag_id,
                status="failed",
                error="There is not enough lecture text for a visual yet. Let the speaker finish a sentence, then tap Catch me up again.",
            )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._publish(
                flag_id, status="failed", error="Reconnect to the lecture and retry the visual."
            )
        state = self._publish(flag_id, status="pending")
        self.jobs[flag_id] = loop.create_task(
            self._generate(flag_id, span, context, self.rt.transcript.text_between(0, end)),
            name=f"catchup-visual-{flag_id}",
        )
        return state

    async def _generate(self, flag_id: str, span: str, context: str, corpus: str) -> None:
        try:
            package, source = await asyncio.wait_for(
                build_package(self.rt.llm, span, context, corpus, self.rt.keyterms, seed=self.rt.seed),
                timeout=min(45.0, self.rt.s.package_timeout_seconds),
            )
            self.packages[self._key(span, context)] = package, source
            artifacts = package.get("artifacts") or {}
            options = []
            seen = set()
            for family in ("visual", "doing", "analogy", "words"):
                kind, content = pick_artifact(artifacts, family)
                if kind in seen or not content:
                    continue
                seen.add(kind)
                options.append(
                    {"form": "words" if kind == "words" else family, "artifact": kind, "content": content}
                )
            options.sort(key=lambda option: option["artifact"] == "words")
            if not any(option["artifact"] != "words" for option in options):
                self._publish(
                    flag_id,
                    status="failed",
                    error="The visual could not be prepared. Retry or keep reading the recap.",
                )
                return
            self._publish(flag_id, status="ready", options=options, plan=artifacts.get("plan"), source=source)
        except asyncio.CancelledError:
            self._publish(flag_id, status="failed", error="Visual preparation stopped with the session.")
            raise
        except Exception as error:
            log.warning("Live visual unavailable for %s (%s)", flag_id, type(error).__name__)
            self._publish(
                flag_id,
                status="failed",
                error="Visual explanation is temporarily unavailable. Retry or keep reading the recap.",
            )

    def match(self, span: str, context: str) -> tuple[dict, str] | None:
        result = self.packages.get(self._key(span, context))
        if result is None:
            return None
        package, source = result
        return package, "offline" if source == "offline" else "cache"

    async def finish(self) -> None:
        if self.jobs:
            await asyncio.gather(*self.jobs.values(), return_exceptions=True)

    async def stop(self) -> None:
        for job in self.jobs.values():
            if not job.done():
                job.cancel()
        await self.finish()
