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


# ---------------------------------------------------------------- templates (docs/PRODUCT.md §4)
# Each template is a fixed rendering in the frontend; the model fills only its data slots, in its own call
# with its own schema and prompt. The plan (stage one) says which visual and which doing template fit a moment.

VISUAL_KINDS: tuple[str, ...] = ("diagram", "chart", "plot", "timeline", "compare", "animation")
DOING_KINDS: tuple[str, ...] = ("steps", "example")
ARTIFACT_KINDS: tuple[str, ...] = ("words", "analogy", *VISUAL_KINDS, *DOING_KINDS)


class Plan(Strict):
    """Which templates fit this moment. Content decides inside a family; the family is what we learn about."""

    visual: str
    doing: str
    why: str

    @model_validator(mode="after")
    def _shape(self) -> Plan:
        self.visual = self.visual.strip().lower()
        self.doing = self.doing.strip().lower()
        if self.visual not in VISUAL_KINDS:
            self.visual = "diagram"
        if self.doing not in DOING_KINDS:
            self.doing = "example"
        return self


class Mapping(Strict):
    idea: str
    everyday: str


class Analogy(Strict):
    """The idea mapped onto an everyday situation with the mapping made explicit, and where it breaks."""

    story: str
    mapping: list[Mapping]
    caveat: str

    @model_validator(mode="after")
    def _shape(self) -> Analogy:
        self.story = " ".join(self.story.split())
        if not self.story:
            raise ValueError("story empty")
        self.mapping = [m for m in self.mapping if m.idea.strip() and m.everyday.strip()][:5]
        if not self.mapping:
            raise ValueError("mapping empty")
        return self


class ChartPoint(Strict):
    label: str
    value: float


class Chart(Strict):
    """Categories with one number each (bars or a line), only numbers the lecturer actually said."""

    kind: str  # bar | line
    title: str
    unit: str
    points: list[ChartPoint]
    takeaway: str

    @model_validator(mode="after")
    def _shape(self) -> Chart:
        self.kind = "line" if self.kind.strip().lower() == "line" else "bar"
        if not (2 <= len(self.points) <= 8):
            raise ValueError("chart needs 2-8 points")
        return self


class XY(Strict):
    x: float
    y: float


class Series(Strict):
    name: str
    points: list[XY]


class Annotation(Strict):
    x: float
    y: float
    text: str


class Plot(Strict):
    """A relationship on numeric axes (a curve, a trend, two curves crossing). illustrative=true when the lecturer
    described the shape but gave no numbers: the axes then carry no units and the UI says 'shape only'."""

    title: str
    x_label: str
    y_label: str
    series: list[Series]
    annotations: list[Annotation]
    illustrative: bool
    takeaway: str

    @model_validator(mode="after")
    def _shape(self) -> Plot:
        self.series = [s for s in self.series if len(s.points) >= 2][:3]
        if not self.series:
            raise ValueError("plot needs a series with 2+ points")
        for s in self.series:
            s.points = sorted(s.points, key=lambda q: q.x)[:60]
        self.annotations = self.annotations[:4]
        return self


class TimelineEvent(Strict):
    when: str
    label: str
    detail: str


class Timeline(Strict):
    """Things in order: dated events or the phases of a process, each with a one-line detail."""

    title: str
    events: list[TimelineEvent]
    takeaway: str

    @model_validator(mode="after")
    def _shape(self) -> Timeline:
        self.events = [e for e in self.events if e.label.strip()][:8]
        if len(self.events) < 2:
            raise ValueError("timeline needs 2-8 events")
        return self


class CompareRow(Strict):
    aspect: str
    left_value: str
    right_value: str


class Compare(Strict):
    """Two things the lecturer contrasted, aspect by aspect, with the one-line verdict."""

    title: str
    left: str
    right: str
    rows: list[CompareRow]
    verdict: str

    @model_validator(mode="after")
    def _shape(self) -> Compare:
        self.rows = [r for r in self.rows if r.aspect.strip()][:6]
        if len(self.rows) < 2:
            raise ValueError("compare needs 2-6 rows")
        if not self.left.strip() or not self.right.strip():
            raise ValueError("compare needs both sides")
        return self


class Steps(Strict):
    """The idea as an ordered procedure."""

    title: str
    steps: list[str]

    @model_validator(mode="after")
    def _shape(self) -> Steps:
        self.steps = [x.strip() for x in self.steps if x.strip()][:8]
        if len(self.steps) < 2:
            raise ValueError("steps needs 2-8 steps")
        return self


class WorkedExample(Strict):
    """A concrete instance carried through to its result, one line per beat."""

    title: str
    lines: list[str]
    result: str

    @model_validator(mode="after")
    def _shape(self) -> WorkedExample:
        self.lines = [x.strip() for x in self.lines if x.strip()][:8]
        if not self.lines:
            raise ValueError("example needs lines")
        return self


ANIMATION_MAX_CHARS = 6000
_ANIMATION_FORBIDDEN = (
    "http://",
    "https://",
    "//cdn",
    "import ",
    "import(",
    "fetch(",
    "xmlhttprequest",
    "websocket",
    "document.cookie",
    "localstorage",
    "sessionstorage",
    "indexeddb",
    "window.parent",
    "window.top",
    "parent.",
    "top.location",
    "<iframe",
    "<link",
    "<object",
    "<embed",
    "<form",
    "eval(",
    "new function",
)


class Animation(Strict):
    """A small self-contained web animation of the mechanism in motion (inline SVG or canvas plus one script).
    Rendered in a sandboxed iframe with scripts only: no network, no storage, no access to the app."""

    title: str
    caption: str
    html: str

    @model_validator(mode="after")
    def _shape(self) -> Animation:
        html = self.html.strip()
        # the svg namespace is the one URL an inline svg legitimately carries
        low = (
            html.lower().replace("http://www.w3.org/2000/svg", "").replace("http://www.w3.org/1999/xlink", "")
        )
        if len(html) > ANIMATION_MAX_CHARS:
            raise ValueError(f"animation html over {ANIMATION_MAX_CHARS} chars")
        if not ("<svg" in low or "<canvas" in low):
            raise ValueError("animation needs inline svg or canvas")
        if "<script" not in low:
            raise ValueError("animation needs an inline script")
        for bad in _ANIMATION_FORBIDDEN:
            if bad in low:
                raise ValueError(f"animation must not use {bad.strip()!r}")
        self.html = html
        self.caption = " ".join(self.caption.split())
        return self


TEMPLATES: dict[str, type[Strict]] = {
    "analogy": Analogy,
    "diagram": SceneGraph,
    "chart": Chart,
    "plot": Plot,
    "timeline": Timeline,
    "compare": Compare,
    "steps": Steps,
    "example": WorkedExample,
    "animation": Animation,
}


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


class GapCore(Strict):
    """Stage one for a missed moment: the note, the check question, the words family, and the plan."""

    note: GapNote
    question: CheckQuestion
    summary: str
    key_idea: KeyIdea
    plan: Plan


FAMILY_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "words": ("summary", "key_idea"),
    "analogy": ("analogy",),
    "visual": VISUAL_KINDS,
    "doing": DOING_KINDS,
}


def _words_content(artifacts: dict) -> dict:
    return {"summary": artifacts.get("summary", ""), "key_idea": artifacts.get("key_idea", {})}


def _present(v: object) -> bool:
    """An artifact exists: non-empty, and not a legacy 'applicable: false' placeholder."""
    return bool(v) and not (isinstance(v, dict) and v.get("applicable") is False)


def pick_artifact(artifacts: dict, family: str) -> tuple[str, dict | str]:
    """The artifact a family shows for this moment. The plan names the visual and the doing template that fit;
    if that one is missing (its call failed) the family's default is used, and if even that is missing the
    words content is shown so a card is never empty. Packages from before the plan (chart/steps with an
    `applicable` flag) still work."""
    if family == "words":
        return "words", _words_content(artifacts)
    if family == "analogy":
        return "analogy", artifacts.get("analogy") or ""
    plan = artifacts.get("plan") or {}
    if family == "visual":
        order = [plan.get("visual"), "diagram"] if plan else []
        if not plan:  # legacy package
            chart = artifacts.get("chart") or {}
            order = ["chart", "diagram"] if chart.get("applicable") else ["diagram"]
        for kind in order:
            if kind and _present(artifacts.get(kind)):
                return kind, artifacts[kind]
        return "words", _words_content(artifacts)
    order = [plan.get("doing"), "example"] if plan else []
    if not plan:
        steps = artifacts.get("steps") or {}
        order = ["steps", "example"] if steps.get("applicable") else ["example"]
    for kind in order:
        if kind and _present(artifacts.get(kind)):
            return kind, artifacts[kind]
    return "words", _words_content(artifacts)


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
