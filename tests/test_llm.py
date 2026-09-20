import asyncio
import json

import pytest
from pydantic import ValidationError

from neuropace.config import FORMS, Settings
from neuropace.llm import fallback
from neuropace.llm.artifacts import build_package
from neuropace.llm.client import LLMClient
from neuropace.llm.schemas import CheckQuestion, GapCore, RecapForms, SceneGraph, strict_schema
from neuropace.store.db import DB

SPAN = "The pseudorange observable is corrupted by several additive error terms. The ionospheric delay is dispersive and proportional to total electron content divided by frequency squared."
CTX = "Three distances narrow you to two points, and one of them is out in space. This method is called trilateration."


def test_strict_schema_shape():
    sch = strict_schema(GapCore)
    assert sch["additionalProperties"] is False
    assert set(sch["required"]) == {"note", "question", "summary", "key_idea", "plan"}
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
    assert r.words.split(": ", 1)[-1] in SPAN and "(offline)" in r.analogy
    p = fallback.gap_package(SPAN, CTX, CTX + " " + SPAN, seed=1)
    q = p["question"]
    assert len(q["options"]) == 4 and 0 <= q["correct_index"] < 4
    assert q["options"][q["correct_index"]] in SPAN
    arts = p["artifacts"]
    assert 2 <= len(arts["diagram"]["nodes"]) <= 8 and arts["example"]["lines"]
    assert p["note"]["key_term"].lower() in SPAN.lower()


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


class FakeChatCompletions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outputs.pop(0)
        message = type("Message", (), {"content": out})()
        return type("Response", (), {"choices": [type("Choice", (), {"message": message})()]})()


class FakeOpenRouter:
    def __init__(self, outputs):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions(outputs)})()


GOOD_RECAP = json.dumps({"words": "p", "analogy": "a", "visual": "v", "doing": "d"})


def test_llm_uses_strict_format_and_caches(tmp_path):
    s = Settings(data_dir=tmp_path, openai_model="gpt-5-mini", allow_offline_llm=True)
    db = DB(s.db_path)
    fake = FakeClient([GOOD_RECAP])
    c = LLMClient(s, db, client=fake)
    forms, source = asyncio.run(c.recap("some words here", "corpus"))
    assert source == "llm" and forms.words == "p"
    call = fake.responses.calls[0]
    assert call["text"]["format"]["strict"] is True and call["text"]["format"]["type"] == "json_schema"
    assert call["reasoning"] == {"effort": "minimal"} and "temperature" not in call
    forms2, source2 = asyncio.run(c.recap("some words here", "corpus"))
    assert source2 == "cache" and forms2.words == "p" and len(fake.responses.calls) == 1


def test_openrouter_uses_chat_completions_and_strict_schema(tmp_path):
    s = Settings(
        data_dir=tmp_path,
        llm_provider="openrouter",
        openrouter_model="openai/gpt-4o-mini",
        allow_offline_llm=True,
    )
    fake = FakeOpenRouter([GOOD_RECAP])
    client = LLMClient(s, DB(s.db_path), client=fake)
    forms, source = asyncio.run(client.recap("some words", "corpus"))
    assert source == "llm" and forms.words == "p"
    call = fake.chat.completions.calls[0]
    assert call["model"] == "openai/gpt-4o-mini"
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["extra_body"] == {"provider": {"require_parameters": True}}


def test_llm_retries_once_on_invalid_then_falls_back(tmp_path):
    s = Settings(data_dir=tmp_path, allow_offline_llm=True)
    db = DB(s.db_path)
    fake = FakeClient(['{"words": ""}', '{"nope": 1}'])
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
    pkg, source = asyncio.run(build_package(c, SPAN, CTX, CTX + " " + SPAN))
    assert source == "offline" and pkg["artifacts"]["plan"] and pkg["sources"]["core"] == "offline"


def test_gemini_uses_google_compatible_schema_without_router_options(tmp_path):
    s = Settings(data_dir=tmp_path, llm_provider="gemini")
    fake = FakeOpenRouter([GOOD_RECAP])
    client = LLMClient(s, DB(s.db_path), client=fake)
    forms, source = asyncio.run(client.recap("some words", "corpus"))
    assert source == "llm" and forms.words == "p"
    call = fake.chat.completions.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["reasoning_effort"] == "none" and "extra_body" not in call


@pytest.mark.asyncio
async def test_exhausted_billing_stops_repeated_generation_calls(tmp_path):
    class NoCredit(RuntimeError):
        status_code = 402

    fake = FakeClient([NoCredit("insufficient credit")])
    client = LLMClient(Settings(data_dir=tmp_path), None, client=fake)
    assert await client.gap_core("span", "") == (None, "offline")
    assert await client.gap_core("other span", "") == (None, "offline")
    assert len(fake.responses.calls) == 1


@pytest.mark.asyncio
async def test_schema_retry_quota_wait_does_not_consume_network_timeout(tmp_path, monkeypatch):
    client = LLMClient(
        Settings(data_dir=tmp_path, recap_timeout_seconds=0.02),
        None,
        client=FakeClient(["{}", GOOD_RECAP]),
    )

    async def quota_wait():
        await asyncio.sleep(0.03)

    monkeypatch.setattr(client, "_rate_limit", quota_wait)
    forms, source = await client.recap("span", "")
    assert source == "llm" and forms.words == "p"


def test_scene_node_palette_is_bounded_and_legacy_nodes_work():
    from neuropace.llm.schemas import SceneNode

    legacy = SceneNode(id="n1", label="Clock")
    assert legacy.shape == "card"
    assert legacy.tone == "butter"
    for shape in ("card", "pill", "ellipse", "diamond"):
        assert SceneNode(id="n1", label="Clock", shape=shape, tone="mint").shape == shape
    with pytest.raises(ValidationError):
        SceneNode(id="n1", label="Clock", shape="<svg>")
    with pytest.raises(ValidationError):
        SceneNode(id="n1", label="Clock", tone="url(https://example.com)")
    schema = strict_schema(SceneNode)
    assert {"shape", "tone"} <= set(schema["required"])
    assert "default" not in schema["properties"]["shape"]
