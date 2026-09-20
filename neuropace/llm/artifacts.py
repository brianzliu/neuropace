"""Build one missed moment's package in two stages (docs/PRODUCT.md §4).

Stage one (`gap_core`): note, check question, the words family and a plan naming the visual and the doing template
that fit the content. Stage two: one focused call per template (analogy, the planned visual, the planned doing),
in parallel. A template whose call fails falls back to the family's default (diagram, example); if even that fails
the family shows the words content, so restudy never shows an empty card.

The package is a plain dict (stored as JSON on the gap row):
  {"note", "question", "artifacts": {"summary", "key_idea", "plan", "analogy", <visual kind>, <doing kind>, ...},
   "sources": {"core": "llm"|"cache", "<kind>": "llm"|"cache"|"failed"}}
"""

from __future__ import annotations

import asyncio
import logging

from . import fallback
from .client import LLMClient, LLMUnavailable
from .schemas import pick_artifact

log = logging.getLogger(__name__)


async def build_package(
    llm: LLMClient,
    span_text: str,
    context_text: str,
    corpus_text: str,
    keyterms: list[str] | None = None,
    seed: int = 0,
) -> tuple[dict, str]:
    """Returns (package, source). source is "llm" or "cache" for a generated package, "offline" for the extractive
    stand-in (tests only). Raises LLMUnavailable when OpenAI is required and stage one failed."""
    if not llm.enabled:
        if not llm.offline_allowed:
            raise llm.unavailable("gap package")
        llm.stats["fallbacks"] += 1
        return fallback.gap_package(span_text, context_text, corpus_text, seed=seed), "offline"
    core, source = await llm.gap_core(span_text, context_text, keyterms)
    if core is None:
        if not llm.offline_allowed:
            raise llm.unavailable("gap package")
        llm.stats["fallbacks"] += 1
        return fallback.gap_package(span_text, context_text, corpus_text, seed=seed), "offline"

    note = core.note.model_dump()
    artifacts: dict = {
        "summary": core.summary,
        "key_idea": core.key_idea.model_dump(),
        "plan": core.plan.model_dump(),
    }
    sources: dict = {"core": source}

    async def fill(kind: str) -> None:
        obj, src = await llm.gap_artifact(kind, span_text, context_text, note, keyterms)
        if obj is None:
            sources[kind] = "failed"
            log.warning("artifact %s failed for a moment (%s)", kind, llm.last_error)
            return
        artifacts[kind] = obj.model_dump()
        sources[kind] = src

    await asyncio.gather(fill("analogy"), fill(core.plan.visual), fill(core.plan.doing))
    # the family defaults, only when the planned template failed
    if core.plan.visual != "diagram" and "diagram" not in artifacts and core.plan.visual not in artifacts:
        await fill("diagram")
    if core.plan.doing != "example" and "example" not in artifacts and core.plan.doing not in artifacts:
        await fill("example")
    return {
        "note": note,
        "question": core.question.model_dump(),
        "artifacts": artifacts,
        "sources": sources,
    }, source


def package_artifact_kinds(package: dict) -> dict[str, str]:
    """Which artifact each family would show for this package (for the team's preview and the tests)."""
    arts = (package or {}).get("artifacts") or {}
    return {fam: pick_artifact(arts, fam)[0] for fam in ("words", "analogy", "visual", "doing")}


__all__ = ["LLMUnavailable", "build_package", "package_artifact_kinds"]
