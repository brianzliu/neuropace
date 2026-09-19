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
    """One glance line per family: the live catch-up shows the learner's best one."""

    words: str
    analogy: str
    visual: str
    doing: str

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


class KeyIdea(Strict):
    term: str
    definition: str
    example: str


class ChartPoint(Strict):
    label: str
    value: float


class Chart(Strict):
    """Only numbers the lecturer actually said. applicable=false when the moment has no quantities."""

    applicable: bool
    kind: str  # bar | line
    title: str
    unit: str
    points: list[ChartPoint]
    takeaway: str

    @model_validator(mode="after")
    def _shape(self) -> Chart:
        self.kind = "line" if self.kind.strip().lower() == "line" else "bar"
        if self.applicable and not (2 <= len(self.points) <= 8):
            self.applicable = False
        return self


class Steps(Strict):
    """The idea as an ordered procedure; applicable when the moment describes a process or method."""

    applicable: bool
    title: str
    steps: list[str]

    @model_validator(mode="after")
    def _shape(self) -> Steps:
        self.steps = [x.strip() for x in self.steps if x.strip()][:8]
        if len(self.steps) < 2:
            self.applicable = False
        return self


class WorkedExample(Strict):
    """A concrete instance carried through to its result, one line per beat. Always produced."""

    title: str
    lines: list[str]
    result: str

    @model_validator(mode="after")
    def _shape(self) -> WorkedExample:
        self.lines = [x.strip() for x in self.lines if x.strip()][:8]
        if not self.lines:
            raise ValueError("example needs lines")
        return self


class Artifacts(Strict):
    """Every way of explaining one moment, produced together so restudy never waits (docs/PRODUCT.md §4)."""

    summary: str
    key_idea: KeyIdea
    analogy: str
    diagram: SceneGraph
    chart: Chart
    steps: Steps
    example: WorkedExample


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
    artifacts: Artifacts


FAMILY_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "words": ("summary", "key_idea"),
    "analogy": ("analogy",),
    "visual": ("chart", "diagram"),
    "doing": ("steps", "example"),
}


def pick_artifact(artifacts: dict, family: str) -> tuple[str, dict | str]:
    """The artifact a family shows for this moment: content decides inside the family (chart only with numbers,
    steps only for a process). Returns (kind, content)."""
    if family == "words":
        return "words", {"summary": artifacts.get("summary", ""), "key_idea": artifacts.get("key_idea", {})}
    if family == "analogy":
        return "analogy", artifacts.get("analogy", "")
    if family == "visual":
        chart = artifacts.get("chart") or {}
        if chart.get("applicable"):
            return "chart", chart
        return "diagram", artifacts.get("diagram", {})
    steps = artifacts.get("steps") or {}
    if steps.get("applicable"):
        return "steps", steps
    return "example", artifacts.get("example", {})


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
