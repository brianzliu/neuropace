import numpy as np
import pytest

from reflow.config import FORMS, Settings
from reflow.core.review import ReviewEngine
from reflow.llm.fallback import gap_package
from reflow.store.db import DB

TEXT = "Radio travels at the speed of light. Multiply the delay by the speed of light and you get the distance. One distance puts you on a sphere. Three spheres give two points. A fourth satellite fixes the clock error."


def _setup(tmp_path, n_gaps=3, catchup_form=None, seed=0):
    s = Settings()
    db = DB(tmp_path / "r.db")
    lr = db.create_learner("Ana")
    sess = db.create_session(learner_id=lr["id"], mode="live", best_form="plain", seed=seed)
    rows, flags = [], []
    for i in range(n_gaps):
        fid = f"flag_{i}"
        db.upsert_flag(
            {
                "id": fid,
                "session_id": sess["id"],
                "source": "sim_tap",
                "t_trigger": 10.0 * i + 8,
                "t_start": 10.0 * i,
                "t_end": 10.0 * i + 8,
                "catchup_shown": catchup_form is not None,
                "catchup_form": catchup_form,
            }
        )
        pkg = gap_package(TEXT, "", TEXT, seed=i)
        rows.append(
            {
                "id": f"gap_{i}",
                "ord": i,
                "t_start": 10.0 * i,
                "t_end": 10.0 * i + 8,
                "span_text": TEXT,
                "flag_ids": [fid],
                "package": pkg.model_dump(),
                "package_source": "offline",
                "status": "open",
            }
        )
        flags.append(fid)
    db.replace_gaps(sess["id"], rows)
    return s, db, lr, sess


def _correct_choice(db, card):
    gap = next(
        g
        for g in db.get_gaps(
            card["session_id"] if "session_id" in card else db.get_card(card["id"])["session_id"]
        )
        if g["id"] == card["gap_id"]
    )
    order = db.get_card(card["id"])["option_order"]
    return order.index(gap["package"]["question"]["correct_index"])


def test_three_straight_hits_stop_and_first_question_credits_catchup_form(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=5, catchup_form="analogy")
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    st = eng.start()
    card = st["card"]
    assert card["kind"] == "question" and len(card["question"]["options"]) == 4
    for i in range(3):
        r = eng.answer(card["id"], _correct_choice(db, card))
        assert r["outcome"] == "hit" and r["credited_form"] == "analogy"
        card = r["next"]
    assert r["done"] and card is None and r["progress"]["streak"] == 3 and r["progress"]["gaps_closed"] == 3
    assert db.get_tally(lr["id"])["analogy"] == {"rescues": 3, "attempts": 3}


def test_miss_reteach_in_next_form_then_hit_credits_that_form(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], seed=2)
    card = eng.start()["card"]
    wrong = (_correct_choice(db, card) + 1) % 4
    r = eng.answer(card["id"], wrong)
    assert r["outcome"] == "miss" and r["credited_form"] is None and r["next"]["kind"] == "reteach"
    assert r["next"]["form"] in FORMS and r["next"]["reteach"]["content"]
    assert db.get_tally(lr["id"]) == {
        f: {"rescues": 0, "attempts": 0} for f in FORMS
    }  # no catch-up form: nothing scored
    r2 = eng.advance(r["next"]["id"])
    q = r2["next"]
    assert q["kind"] == "question" and q["forms_used"] == [r["next"]["form"]]
    r3 = eng.answer(q["id"], _correct_choice(db, q))
    assert r3["outcome"] == "hit" and r3["credited_form"] == r["next"]["form"]
    assert db.get_tally(lr["id"])[r["next"]["form"]] == {"rescues": 1, "attempts": 1}
    assert r3["done"] and r3["progress"]["gaps_closed"] == 1


def test_drop_switches_form_without_scoring(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1, catchup_form="plain")
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    r = eng.drop(card["id"])
    assert (
        r["outcome"] == "drop"
        and r["next"]["kind"] == "reteach"
        and r["next"]["form"] != "plain"
        or r["next"]["form"] in FORMS
    )
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0
    with pytest.raises(ValueError):
        eng.answer(card["id"], 0)


def test_gap_exhausts_after_all_forms_and_review_moves_on(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=2)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    forms_seen = []
    for _ in range(4):
        r = eng.answer(card["id"], (_correct_choice(db, card) + 1) % 4)
        assert r["outcome"] == "miss"
        nxt = r["next"]
        if nxt["kind"] == "reteach":
            forms_seen.append(nxt["form"])
            card = eng.advance(nxt["id"])["next"]
        else:
            card = nxt
    assert sorted(forms_seen) == sorted(FORMS)
    r = eng.answer(card["id"], (_correct_choice(db, card) + 1) % 4)
    assert r["next"]["gap_id"] == "gap_1" and r["progress"]["gaps_exhausted"] == 1


def test_rebuild_from_db_resumes_mid_review(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=2)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    r = eng.answer(card["id"], (_correct_choice(db, card) + 1) % 4)
    eng2 = ReviewEngine(db, s, sess["id"], lr["id"])
    st = eng2.start()
    assert st["card"]["id"] == r["next"]["id"] and st["progress"]["cards_answered"] == 1
    assert np.isclose(st["tally"]["total_attempts"], 0)
