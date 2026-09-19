import asyncio
import json

import pytest
from pydantic import ValidationError

from reflow.config import FORMS, Settings
from reflow.llm import fallback
from reflow.llm.client import LLMClient
from reflow.llm.schemas import CheckQuestion, GapPackage, RecapForms, SceneGraph, strict_schema
from reflow.store.db import DB

SPAN = "The pseudorange observable is corrupted by several additive error terms. The ionospheric delay is dispersive and proportional to total electron content divided by frequency squared."
CTX = "Three distances narrow you to two points, and one of them is out in space. This method is called trilateration."


def test_strict_schema_shape():
    sch = strict_schema(GapPackage)
    assert sch["additionalProperties"] is False
    assert set(sch["required"]) == {"note", "question", "forms"}
    q = sch["$defs"]["CheckQuestion"]
    assert q["additionalProperties"] is False and set(q["required"]) == {
        "question",
        "options",
        "correct_index",
        "explanation",
    }
    assert "minItems" not in json.dumps(sch)


def test_schema_validators_catch_bad_outputs():
    with pytest.raises(ValidationError):
        CheckQuestion(question="q", options=["a", "b", "c"], correct_index=0, explanation="e")
    with pytest.raises(ValidationError):
        CheckQuestion(question="q", options=["a", "a", "c", "d"], correct_index=0, explanation="e")
    with pytest.raises(ValidationError):
        SceneGraph(
            title="t",
            nodes=[{"id": "n1", "label": "x"}],
            edges=[],
            steps=[{"highlight": ["n1"], "caption": "c"}],
        )
    g = SceneGraph(
        title="t",
        nodes=[{"id": "n1", "label": "x"}, {"id": "n2", "label": "y"}],
        edges=[
            {"from_id": "n1", "to_id": "zz", "label": "bad"},
            {"from_id": "n1", "to_id": "n2", "label": "ok"},
        ],
        steps=[{"highlight": ["n1", "nope"], "caption": "c"}],
    )
    assert [e.to_id for e in g.edges] == ["n2"] and g.steps[0].highlight == ["n1"]


def test_fallback_outputs_are_valid_and_grounded():
    r = fallback.recap_forms(SPAN, CTX + " " + SPAN)
    assert all(getattr(r, f) for f in FORMS)
    assert r.plain in SPAN
    p = fallback.gap_package(SPAN, CTX, CTX + " " + SPAN, seed=1)
    assert len(p.question.options) == 4 and 0 <= p.question.correct_index < 4
    assert p.question.options[p.question.correct_index] in SPAN
    assert 2 <= len(p.forms.sketch.diagram.nodes) <= 8
    assert p.note.key_term.lower() in SPAN.lower()


class FakeResponses:
    def __init__(self, outputs: list[str | Exception]):
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return type("R", (), {"output_text": out})()


class FakeClient:
    def __init__(self, outputs):
        self.responses = FakeResponses(outputs)


GOOD_RECAP = json.dumps({"plain": "p", "keyterm": "k: d", "analogy": "a", "sketch": "s"})


def test_llm_uses_strict_format_and_caches(tmp_path):
    s = Settings(data_dir=tmp_path, openai_model="gpt-5-mini", allow_offline_llm=True)
    db = DB(s.db_path)
    fake = FakeClient([GOOD_RECAP])
    c = LLMClient(s, db, client=fake)
    forms, source = asyncio.run(c.recap("some words here", "corpus"))
    assert source == "llm" and forms.plain == "p"
    call = fake.responses.calls[0]
    assert call["text"]["format"]["strict"] is True and call["text"]["format"]["type"] == "json_schema"
    assert call["reasoning"] == {"effort": "minimal"} and "temperature" not in call
    forms2, source2 = asyncio.run(c.recap("some words here", "corpus"))
    assert source2 == "cache" and forms2.plain == "p" and len(fake.responses.calls) == 1


def test_llm_retries_once_on_invalid_then_falls_back(tmp_path):
    s = Settings(data_dir=tmp_path, allow_offline_llm=True)
    db = DB(s.db_path)
    fake = FakeClient(['{"plain": ""}', '{"nope": 1}'])
    c = LLMClient(s, db, client=fake)
    forms, source = asyncio.run(c.recap("the words in the window", "corpus"))
    assert source == "offline" and isinstance(forms, RecapForms)
    assert len(fake.responses.calls) == 2 and c.stats["errors"] == 1 and c.stats["fallbacks"] == 1


def test_llm_drops_reasoning_param_when_rejected(tmp_path):
    s = Settings(data_dir=tmp_path, openai_model="gpt-5-mini", allow_offline_llm=True)
    db = DB(s.db_path)
    fake = FakeClient([RuntimeError("Unsupported parameter: 'reasoning'"), GOOD_RECAP])
    c = LLMClient(s, db, client=fake)
    _, source = asyncio.run(c.recap("w", "c"))
    assert source == "llm" and "reasoning" not in fake.responses.calls[1]


def test_llm_timeout_falls_back(tmp_path):
    s = Settings(data_dir=tmp_path, recap_timeout_seconds=0.05, allow_offline_llm=True)
    db = DB(s.db_path)

    class Slow:
        class responses:  # noqa: N801
            @staticmethod
            async def create(**kwargs):
                await asyncio.sleep(1.0)
                return type("R", (), {"output_text": GOOD_RECAP})()

    c = LLMClient(s, db, client=Slow())
    _, source = asyncio.run(c.recap("w", "c"))
    assert source == "offline" and c.stats["timeouts"] == 1


def test_no_key_means_offline_without_network(tmp_path):
    s = Settings(data_dir=tmp_path, openai_api_key=None, allow_offline_llm=True)
    c = LLMClient(s, DB(s.db_path))
    assert not c.enabled
    pkg, source = asyncio.run(c.gap_package(SPAN, CTX, CTX + " " + SPAN))
    assert source == "offline" and isinstance(pkg, GapPackage)
