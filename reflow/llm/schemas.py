"""Pydantic models = the JSON schemas sent to OpenAI strict structured outputs (TDD §7).

Strict mode rules: every field required, additionalProperties false, no array-length keywords in the schema
(lengths are validated in Python instead, so a bad output triggers one retry and then the fallback).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from ..config import FORMS


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecapForms(Strict):
    plain: str
    keyterm: str
    analogy: str
    sketch: str

    @model_validator(mode="after")
    def _nonempty(self) -> RecapForms:
        for f in FORMS:
            v = getattr(self, f).strip()
            if not v:
                raise ValueError(f"{f} empty")
            setattr(self, f, " ".join(v.split()))
        return self


class SceneNode(Strict):
    id: str
    label: str


class SceneEdge(Strict):
    from_id: str
    to_id: str
    label: str


class SceneStep(Strict):
    highlight: list[str]
    caption: str


class SceneGraph(Strict):
    title: str
    nodes: list[SceneNode]
    edges: list[SceneEdge]
    steps: list[SceneStep]

    @model_validator(mode="after")
    def _shape(self) -> SceneGraph:
        ids = [n.id for n in self.nodes]
        if not (2 <= len(ids) <= 8):
            raise ValueError("nodes must be 2-8")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node ids")
        idset = set(ids)
        self.edges = [
            e for e in self.edges if e.from_id in idset and e.to_id in idset and e.from_id != e.to_id
        ]
        if not self.steps:
            raise ValueError("steps empty")
        for st in self.steps:
            st.highlight = [h for h in st.highlight if h in idset]
        self.steps = self.steps[:8]
        return self


class KeyTermForm(Strict):
    term: str
    definition: str
    example: str


class SketchForm(Strict):
    line: str
    diagram: SceneGraph


class FullForms(Strict):
    plain: str
    keyterm: KeyTermForm
    analogy: str
    sketch: SketchForm


class CheckQuestion(Strict):
    question: str
    options: list[str]
    correct_index: int
    explanation: str

    @model_validator(mode="after")
    def _shape(self) -> CheckQuestion:
        if len(self.options) != 4:
            raise ValueError("exactly 4 options")
        if not (0 <= self.correct_index < 4):
            raise ValueError("correct_index out of range")
        if len({o.strip().lower() for o in self.options}) != 4:
            raise ValueError("options must be distinct")
        return self


class GapNote(Strict):
    what_was_said: str
    key_term: str
    definition: str
    connection: str


class GapPackage(Strict):
    note: GapNote
    question: CheckQuestion
    forms: FullForms


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema with additionalProperties=false and all properties required, recursively."""
    schema = model.model_json_schema()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for k in ("minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "default"):
                node.pop(k, None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema
