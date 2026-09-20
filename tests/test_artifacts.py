"""Generation templates (docs/PRODUCT.md §4): one light core call plus one focused call per template, each template
with its own schema, failures falling back inside the family, and the offline stand-in filling every template."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from reflow.config import Settings
from reflow.llm import fallback
from reflow.llm.artifacts import build_package, package_artifact_kinds
from reflow.llm.client import LLMClient, LLMUnavailable
from reflow.llm.schemas import (
    ARTIFACT_KINDS,
    TEMPLATES,
    Animation,
    Compare,
    GapCore,
    Plot,
    Timeline,
    pick_artifact,
    strict_schema,
)
from reflow.store.db import DB

SPAN = (
    "The pseudorange observable is corrupted by several additive error terms. The ionospheric delay is dispersive "
    "and proportional to total electron content divided by frequency squared. The receiver clock adds 30 meters, "
    "the satellite clock adds 2 meters, and multipath adds 5 meters."
)
CTX = "Three distances narrow you to two points, and one of them is out in space."
CORPUS = CTX + " " + SPAN

CORE = {
    "note": {"what_was_said": "x", "key_term": "ionospheric delay", "definition": "d", "connection": "c"},
    "question": {"question": "q", "options": ["a", "b", "c", "d"], "correct_index": 1, "explanation": "e"},
    "summary": "s",
    "key_idea": {"term": "ionospheric delay", "definition": "d", "example": "e"},
    "plan": {"visual": "plot", "doing": "steps", "why": "a curve was described"},
}
ANALOGY = {
    "story": "like fog slowing a runner",
    "mapping": [{"idea": "delay", "everyday": "fog"}],
    "caveat": "c",
}
PLOT = {
    "title": "delay vs frequency",
    "x_label": "frequency",
    "y_label": "delay",
    "series": [{"name": "delay", "points": [{"x": 1, "y": 4}, {"x": 2, "y": 1}, {"x": 3, "y": 0.4}]}],
    "annotations": [{"x": 2, "y": 1, "text": "L2"}],
    "illustrative": True,
    "takeaway": "falls with the square of frequency",
}
STEPS = {
    "title": "correct a pseudorange",
    "steps": ["measure", "subtract the clock", "subtract the ionosphere"],
}
DIAGRAM = {
    "title": "t",
    "nodes": [{"id": "n1", "label": "a"}, {"id": "n2", "label": "b"}],
    "edges": [{"from_id": "n1", "to_id": "n2", "label": "adds"}],
    "steps": [{"highlight": ["n1"], "caption": "c"}],
}


class FakeResponses:
    """Answers by task: the instructions text identifies which template is being asked for."""

    def __init__(self, by_task: dict[str, list]):
        self.by_task = {k: list(v) for k, v in by_task.items()}
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        name = kwargs["text"]["format"]["name"]
        outs = self.by_task[name]
        out = outs.pop(0) if len(outs) > 1 else outs[0]
        if isinstance(out, Exception):
            raise out
        return type("R", (), {"output_text": json.dumps(out) if not isinstance(out, str) else out})()


class FakeClient:
    def __init__(self, by_task):
        self.responses = FakeResponses(by_task)


def _client(tmp_path, by_task, offline=False):
    s = Settings(data_dir=tmp_path, openai_model="gpt-5-mini", allow_offline_llm=offline)
    return LLMClient(s, DB(s.db_path), client=FakeClient(by_task))


def test_every_template_has_a_strict_schema_and_the_core_is_light():
    core = strict_schema(GapCore)
    assert set(core["required"]) == {"note", "question", "summary", "key_idea", "plan"}
    assert "minItems" not in json.dumps(core)
    for kind, model in TEMPLATES.items():
        sch = strict_schema(model)
        assert sch["additionalProperties"] is False and "minItems" not in json.dumps(sch), kind
    assert set(TEMPLATES) == set(ARTIFACT_KINDS) - {"words"}


def test_two_stage_generation_asks_each_template_for_its_own_data(tmp_path):
    c = _client(
        tmp_path,
        {"GapCore": [CORE], "Analogy": [ANALOGY], "Plot": [PLOT], "Steps": [STEPS]},
    )
    pkg, source = asyncio.run(build_package(c, SPAN, CTX, CORPUS, ["pseudorange"]))
    assert source == "llm" and pkg["sources"] == {
        "core": "llm",
        "analogy": "llm",
        "plot": "llm",
        "steps": "llm",
    }
    names = [call["text"]["format"]["name"] for call in c._client.responses.calls]
    assert names == ["GapCore", "Analogy", "Plot", "Steps"], (
        "one core call, then exactly the planned templates"
    )
    plot_call = next(call for call in c._client.responses.calls if call["text"]["format"]["name"] == "Plot")
    assert "series" in plot_call["instructions"] and "illustrative" in plot_call["instructions"]
    assert json.loads(plot_call["input"])["key_term"] == "ionospheric delay"
    assert package_artifact_kinds(pkg) == {
        "words": "words",
        "analogy": "analogy",
        "visual": "plot",
        "doing": "steps",
    }
    kind, content = pick_artifact(pkg["artifacts"], "visual")
    assert kind == "plot" and content["illustrative"] is True and len(content["series"][0]["points"]) == 3
    # a second build is served from the cache, call for call
    pkg2, source2 = asyncio.run(build_package(c, SPAN, CTX, CORPUS, ["pseudorange"]))
    assert source2 == "cache" and pkg2["artifacts"] == pkg["artifacts"]
    assert len(c._client.responses.calls) == 4


def test_a_failed_template_falls_back_inside_its_family(tmp_path, monkeypatch):
    bad = RuntimeError("boom")
    c = _client(
        tmp_path,
        {
            "GapCore": [CORE],
            "Analogy": [ANALOGY],
            "Plot": [bad, bad, bad],
            "SceneGraph": [DIAGRAM],
            "Steps": [bad, bad, bad],
            "WorkedExample": [bad, bad, bad],
        },
    )
    c.s.package_timeout_seconds = 5

    async def fast(*a, **k):
        return None

    real_run = asyncio.run
    monkeypatch.setattr(asyncio, "sleep", fast)  # no backoff waits in the test; restored by pytest
    pkg, source = real_run(build_package(c, SPAN, CTX, CORPUS))
    assert source == "llm"
    assert pkg["sources"]["plot"] == "failed" and pkg["sources"]["diagram"] == "llm"
    assert pkg["sources"]["steps"] == "failed" and pkg["sources"]["example"] == "failed"
    kinds = package_artifact_kinds(pkg)
    assert kinds["visual"] == "diagram", "the planned visual failed: the family default is shown"
    assert kinds["doing"] == "words", (
        "both doing templates failed: the words content keeps the card non-empty"
    )


def test_core_failure_is_unavailable_unless_offline_is_allowed(tmp_path, monkeypatch):
    bad = RuntimeError("down")
    c = _client(tmp_path, {"GapCore": [bad, bad, bad, bad, bad, bad]})

    async def fast(*a, **k):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast)
    with pytest.raises(LLMUnavailable):
        asyncio.run(build_package(c, SPAN, CTX, CORPUS))
    c2 = _client(tmp_path / "b", {"GapCore": [bad, bad, bad, bad, bad, bad]}, offline=True)
    pkg, source = asyncio.run(build_package(c2, SPAN, CTX, CORPUS))
    assert source == "offline" and pkg["sources"]["core"] == "offline"


def test_template_validators_reject_thin_or_unsafe_data():
    with pytest.raises(ValidationError):
        Plot(
            title="t",
            x_label="x",
            y_label="y",
            series=[{"name": "s", "points": [{"x": 1, "y": 1}]}],
            annotations=[],
            illustrative=True,
            takeaway="t",
        )
    with pytest.raises(ValidationError):
        Timeline(title="t", events=[{"when": "1", "label": "a", "detail": "d"}], takeaway="t")
    with pytest.raises(ValidationError):
        Compare(
            title="t",
            left="a",
            right="",
            rows=[{"aspect": "x", "left_value": "1", "right_value": "2"}] * 2,
            verdict="v",
        )
    ok = "<div><svg viewBox='0 0 600 260' xmlns='http://www.w3.org/2000/svg'><circle id='c' r='5'/></svg><script>requestAnimationFrame(function f(){});</script></div>"
    assert Animation(title="t", caption="c", html=ok).html.startswith("<div>")
    for bad in (
        ok.replace("<script>", "<script src='https://x.y/z.js'></script><script>"),
        ok.replace("<script>", "<script>fetch('/api');"),
        ok.replace("<script>", "<script>window.parent.postMessage(1,'*');"),
        ok.replace("<script>", "<script>localStorage.x=1;"),
        "<div><p>no drawing</p><script>1</script></div>",
        ok + "x" * 7000,
    ):
        with pytest.raises(ValidationError):
            Animation(title="t", caption="c", html=bad)


def test_offline_stand_in_fills_every_template_and_labels_itself():
    pkg = fallback.gap_package(SPAN, CTX, CORPUS, seed=0)
    arts = pkg["artifacts"]
    assert arts["plan"]["visual"] == "plot", "three numbers in the span: a plot"
    assert set(arts) >= {"summary", "key_idea", "plan", "analogy", "plot", "steps", "diagram", "example"}
    for kind in (
        "analogy",
        "diagram",
        "chart",
        "plot",
        "timeline",
        "compare",
        "steps",
        "example",
        "animation",
    ):
        obj = fallback.artifact(kind, SPAN, CTX, CORPUS, seed=1)
        assert obj is not None, kind
        assert TEMPLATES[kind].model_validate(obj.model_dump())
        dumped = json.dumps(obj.model_dump())
        assert "(offline)" in dumped, f"{kind} must say it is the stand-in"
    no_numbers = "First the satellite sends the time. Then the phone hears it late. Finally the delay becomes distance."
    visuals = {fallback.plan_for(no_numbers, no_numbers, seed=s).visual for s in range(4)}
    assert visuals == {"diagram", "animation", "timeline", "compare"}, (
        "test mode exercises every visual template"
    )
    assert (
        fallback.artifact("chart", no_numbers, "", "", 0) is None
        and fallback.artifact("plot", no_numbers, "", "", 0) is None
    )


def test_pick_artifact_handles_packages_from_before_the_plan():
    legacy = {
        "summary": "s",
        "key_idea": {"term": "k", "definition": "d", "example": "e"},
        "analogy": "a string analogy",
        "diagram": DIAGRAM,
        "chart": {
            "applicable": True,
            "kind": "bar",
            "points": [{"label": "a", "value": 1}, {"label": "b", "value": 2}],
        },
        "steps": {"applicable": False, "steps": []},
        "example": {"title": "t", "lines": ["l"], "result": "r"},
    }
    assert pick_artifact(legacy, "visual")[0] == "chart" and pick_artifact(legacy, "doing")[0] == "example"
    assert pick_artifact(legacy, "analogy") == ("analogy", "a string analogy")
    planned = {**legacy, "plan": {"visual": "animation", "doing": "steps", "why": "w"}}
    assert pick_artifact(planned, "visual")[0] == "diagram", "planned animation missing: the family default"
    assert pick_artifact(planned, "doing")[0] == "example"
    planned["animation"] = {"title": "t", "caption": "c", "html": "<div><svg/><script>1</script></div>"}
    assert pick_artifact(planned, "visual")[0] == "animation"
