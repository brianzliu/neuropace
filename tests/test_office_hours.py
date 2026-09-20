import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from neuropace.config import Settings
from neuropace.core.office_hours import OfficeHoursEngine, replay_board
from neuropace.llm.client import LLMClient
from neuropace.llm.schemas import BoardEnvelope, OfficeHoursTurn, strict_schema
from neuropace.store.db import DB


# ---------------------------------------------------------------- schemas
def test_board_envelope_clamps_to_bounds():
    e = BoardEnvelope(x=-50, y=99999, w=1, h=99999, z=0)
    assert e.x == 0.0 and e.y == 3000.0 and e.w == 40.0 and e.h == 2000.0


def test_office_hours_turn_caps_ops_and_rejects_empty_reply():
    ops = [{"op": "remove", "element_id": f"e{i}"} for i in range(10)]
    t = OfficeHoursTurn(reply_text="  hello   there  ", board_ops=ops)
    assert t.reply_text == "hello there"
    assert len(t.board_ops) == 6
    with pytest.raises(ValidationError):
        OfficeHoursTurn(reply_text="   ", board_ops=[])


def test_strict_schema_office_hours_turn_is_strict_and_flat_strings():
    sch = strict_schema(OfficeHoursTurn)
    assert sch["additionalProperties"] is False
    add = sch["$defs"]["AddElement"]
    assert add["additionalProperties"] is False
    assert set(add["required"]) == {"op", "element_id", "kind", "caption", "envelope", "content_json"}
    assert (
        add["properties"]["content_json"]["type"] == "string"
    )  # loose shape travels as a string, not a dict
    assert "minItems" not in json.dumps(sch)


# ---------------------------------------------------------------- db accessors + replay
def test_oh_message_and_board_op_round_trip(tmp_path):
    db = DB(tmp_path / "o.db")
    lr = db.create_learner("Ana")
    sess = db.create_session(learner_id=lr["id"], mode="office_hours")
    db.oh_add_message(sess["id"], 0, "user", "what is trilateration?")
    db.oh_add_message(sess["id"], 1, "agent", "it's how GPS finds you", source="llm")
    db.oh_add_board_op(
        sess["id"],
        2,
        "add",
        "el1",
        {
            "kind": "words",
            "envelope": {"x": 0, "y": 0, "w": 200, "h": 100, "z": 0},
            "content": {"summary": "s", "key_idea": {"term": "t", "definition": "d", "example": "e"}},
        },
    )
    assert db.oh_next_ord(sess["id"]) == 3
    msgs = db.oh_get_messages(sess["id"])
    assert [m["role"] for m in msgs] == ["user", "agent"]
    assert msgs[1]["source"] == "llm"
    ops = db.oh_get_board_ops(sess["id"])
    assert ops[0]["op"] == "add" and ops[0]["payload"]["kind"] == "words"
    assert db.oh_get_messages(sess["id"], upto_ord=0) == msgs[:1]


def test_replay_board_add_update_remove():
    ops = [
        {
            "ord": 0,
            "op": "add",
            "element_id": "a",
            "payload": {
                "kind": "label",
                "envelope": {"x": 0, "y": 0, "w": 10, "h": 10, "z": 0},
                "content": {"text": "hi"},
            },
        },
        {"ord": 1, "op": "update", "element_id": "a", "payload": {"envelope": {"x": 5}}},
        {
            "ord": 2,
            "op": "add",
            "element_id": "b",
            "payload": {
                "kind": "label",
                "envelope": {"x": 1, "y": 1, "w": 1, "h": 1, "z": 0},
                "content": {"text": "bye"},
            },
        },
        {"ord": 3, "op": "remove", "element_id": "b"},
        {
            "ord": 4,
            "op": "update",
            "element_id": "b",
            "payload": {"envelope": {"x": 9}},
        },  # no-op: already removed
    ]
    board = replay_board(ops)
    assert set(board) == {"a"}
    assert board["a"]["envelope"]["x"] == 5 and board["a"]["envelope"]["y"] == 0
    assert replay_board(ops[:1]) == {
        "a": {
            "id": "a",
            "kind": "label",
            "envelope": {"x": 0, "y": 0, "w": 10, "h": 10, "z": 0},
            "content": {"text": "hi"},
        }
    }


# ---------------------------------------------------------------- engine
TURN_JSON = json.dumps(
    {
        "reply_text": "Trilateration finds you from three distances.",
        "board_ops": [
            {
                "op": "add",
                "element_id": "el1",
                "kind": "label",
                "caption": "Three spheres narrow it down to two points.",
                "envelope": {"x": 100, "y": 100, "w": 200, "h": 80, "z": 0},
                "content_json": json.dumps({"text": "3 spheres -> 2 points"}),
            }
        ],
    }
)


class _FakeResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    async def create(self, **kwargs):
        out = self.outputs.pop(0)
        return type("R", (), {"output_text": out})()


class _FakeClient:
    def __init__(self, outputs):
        self.responses = _FakeResponses(outputs)


def _engine(tmp_path, outputs):
    s = Settings(data_dir=tmp_path, openai_model="gpt-5-mini", allow_offline_llm=True)
    db = DB(s.db_path)
    lr = db.create_learner("Ana")
    sess = db.create_session(learner_id=lr["id"], mode="office_hours")
    llm = LLMClient(s, db, client=_FakeClient(outputs))
    return db, sess, OfficeHoursEngine(db, s, llm, sess["id"], lr["id"], None)


@pytest.mark.asyncio
async def test_send_message_persists_turn_and_applies_ops(tmp_path):
    db, sess, eng = _engine(tmp_path, [TURN_JSON])
    reply = await eng.send_message("What is trilateration?")
    assert reply["role"] == "agent" and reply["related_element_ids"] == ["el1"]
    assert "el1" in eng.board and eng.board["el1"]["kind"] == "label"
    msgs = db.oh_get_messages(sess["id"])
    assert [m["role"] for m in msgs] == ["user", "agent"]

    rebuilt = OfficeHoursEngine(db, eng.s, eng.llm, sess["id"], sess["learner_id"], None)
    assert rebuilt.board == eng.board
    assert [m["text"] for m in rebuilt.messages] == [m["text"] for m in eng.messages]


@pytest.mark.asyncio
async def test_expand_element_reuses_send_message_path(tmp_path):
    _, _, eng = _engine(tmp_path, [TURN_JSON, TURN_JSON])
    await eng.send_message("teach me trilateration")
    reply = await eng.expand_element("el1")
    assert reply["role"] == "agent"
    with pytest.raises(ValueError):
        await eng.expand_element("nope")


@pytest.mark.asyncio
async def test_offline_llm_gives_a_labeled_reply_not_a_silent_failure(tmp_path):
    s = Settings(data_dir=tmp_path, allow_offline_llm=True)
    db = DB(s.db_path)
    lr = db.create_learner("Ana")
    sess = db.create_session(learner_id=lr["id"], mode="office_hours")
    llm = LLMClient(s, db)  # no key, no fake client: disabled
    eng = OfficeHoursEngine(db, s, llm, sess["id"], lr["id"], None)
    reply = await eng.send_message("hello?")
    assert reply["source"] == "failed" and reply["role"] == "agent"


# ---------------------------------------------------------------- API
def test_create_session_office_hours_skips_runtime_and_round_trips(app, settings):
    settings.allow_offline_llm = True
    with TestClient(app) as c:
        lr = c.post("/api/learners", json={"name": "Judge"}).json()
        r = c.post("/api/sessions", json={"learner_id": lr["id"], "mode": "office_hours"})
        assert r.status_code == 200
        sess = r.json()
        assert sess["mode"] == "office_hours"
        assert sess["id"] not in app.state.runtimes

        msg = c.post(f"/api/sessions/{sess['id']}/office_hours/message", json={"text": "hi"}).json()
        assert msg["role"] == "agent"

        snap = c.get(f"/api/sessions/{sess['id']}/office_hours").json()
        assert len(snap["messages"]) == 2

        first_ord = snap["messages"][0]["ord"]
        partial = c.get(f"/api/sessions/{sess['id']}/office_hours?upto_ord={first_ord}").json()
        assert len(partial["messages"]) == 1
