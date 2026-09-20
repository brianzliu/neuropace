import pytest

from neuropace.config import FORMS, Settings
from neuropace.core.review import ReviewEngine
from neuropace.llm.fallback import gap_package
from neuropace.store.db import DB

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
                "source": "key",
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
                "package": pkg,
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


def _teach_then_ask(eng, card):
    """A moment opens with an explanation; reading it leads to the check."""
    assert card["kind"] == "reteach" and card["reteach"]["content"] and card["reteach"]["why"]
    return eng.advance(card["id"])["next"]


def test_teach_first_then_check_and_three_hits_end_the_lesson(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=5, catchup_form="analogy")
    s.review_stop_streak = 3  # opt-in study rule; off by default
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    st = eng.start()
    card = st["card"]
    assert card["kind"] == "reteach", "a missed moment is explained before it is checked (PRODUCT.md §5)"
    assert card["reteach"]["context"] is not None and card["reteach"]["said"] == TEXT
    credited = []
    for _ in range(3):
        q = _teach_then_ask(eng, card)
        assert q["kind"] == "question" and len(q["question"]["options"]) == 4
        r = eng.answer(q["id"], _correct_choice(db, q))
        assert r["outcome"] == "hit" and r["credited_form"] == card["form"]
        credited.append(card["form"])
        card = r["next"]
    assert r["done"] and card is None and r["progress"]["streak"] == 3 and r["progress"]["gaps_closed"] == 3
    tally = db.get_tally(lr["id"])
    assert sum(v["attempts"] for v in tally.values()) == 3 and sum(v["rescues"] for v in tally.values()) == 3
    for f in credited:
        assert tally[f]["rescues"] >= 1


def test_by_default_review_runs_through_every_moment(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=5)
    assert s.review_stop_streak == 0
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    hits = 0
    while card is not None:
        q = _teach_then_ask(eng, card)
        r = eng.answer(q["id"], _correct_choice(db, q))
        hits += 1
        card = r["next"]
    assert hits == 5 and r["done"] and r["progress"]["gaps_closed"] == 5


def test_miss_reteaches_in_the_next_family_then_a_hit_credits_it(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], seed=2)
    first = eng.start()["card"]
    q = _teach_then_ask(eng, first)
    wrong = (_correct_choice(db, q) + 1) % 4
    r = eng.answer(q["id"], wrong)
    assert r["outcome"] == "miss" and r["credited_form"] == first["form"] and r["next"]["kind"] == "reteach"
    assert r["next"]["form"] != first["form"] and r["next"]["reteach"]["artifact"]
    assert db.get_tally(lr["id"])[first["form"]] == {"rescues": 0, "attempts": 1}
    q2 = eng.advance(r["next"]["id"])["next"]
    assert q2["kind"] == "question" and q2["forms_used"] == [first["form"], r["next"]["form"]]
    r3 = eng.answer(q2["id"], _correct_choice(db, q2))
    assert r3["outcome"] == "hit" and r3["credited_form"] == r["next"]["form"]
    assert db.get_tally(lr["id"])[r["next"]["form"]] == {"rescues": 1, "attempts": 1}
    assert r3["done"] and r3["progress"]["gaps_closed"] == 1


def test_the_tutor_says_why_this_family(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    for _ in range(12):
        db.tally_add(lr["id"], "visual", rescue=True)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], seed=1)
    assert "works best for you" in eng._why("visual")
    assert "not tried" in eng._why("doing")
    db.tally_add(lr["id"], "doing", rescue=False)
    assert eng._why("doing").startswith("Let's try it by doing")


def test_drop_switches_form_without_scoring(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1, catchup_form="plain")
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    r = eng.drop(card["id"], focus_ratio=0.2)
    assert r["outcome"] == "drop" and r["next"]["kind"] == "reteach" and r["next"]["form"] != card["form"]
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0
    assert db.get_card(card["id"])["focus_ratio"] == 0.2
    with pytest.raises(ValueError):
        eng.advance(card["id"])


def test_gap_exhausts_after_all_forms_and_review_moves_on(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=2)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    forms_seen = []
    for _ in range(4):
        assert card["kind"] == "reteach" and card["gap_id"] == "gap_0"
        forms_seen.append(card["form"])
        q = eng.advance(card["id"])["next"]
        r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
        assert r["outcome"] == "miss"
        card = r["next"]
    assert sorted(forms_seen) == sorted(FORMS)
    assert card["gap_id"] == "gap_1" and card["kind"] == "reteach" and r["progress"]["gaps_exhausted"] == 1


def test_rebuild_from_db_resumes_mid_review(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=2)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    q = eng.advance(card["id"])["next"]
    r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
    eng2 = ReviewEngine(db, s, sess["id"], lr["id"])
    st = eng2.start()
    assert st["card"]["id"] == r["next"]["id"] and st["progress"]["cards_answered"] == 1
    assert st["tally"]["total_attempts"] == 1


def test_manual_review_checks_first_and_explains_only_after_a_miss(tmp_path):
    """Review on my own (docs/PRODUCT.md §5): the quiz first; nothing is scored for a cold check."""
    s, db, lr, sess = _setup(tmp_path, n_gaps=2)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], seed=3, mode="manual")
    st = eng.start()
    card = st["card"]
    assert card["kind"] == "question" and st["progress"]["mode"] == "manual"
    r = eng.answer(card["id"], _correct_choice(db, card))
    assert r["outcome"] == "hit" and r["credited_form"] is None
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0
    assert r["next"]["kind"] == "question" and r["next"]["gap_id"] == "gap_1"
    r2 = eng.answer(r["next"]["id"], (_correct_choice(db, r["next"]) + 1) % 4)
    assert r2["outcome"] == "miss" and r2["next"]["kind"] == "reteach" and r2["next"]["reteach"]["why"]
    q = eng.advance(r2["next"]["id"])["next"]
    r3 = eng.answer(q["id"], _correct_choice(db, q))
    assert r3["credited_form"] == r2["next"]["form"] and r3["done"]
    with pytest.raises(ValueError):
        ReviewEngine(db, s, sess["id"], lr["id"], mode="nope")


def test_missing_family_shows_words_and_scores_what_was_actually_shown(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    rows = db.get_gaps(sess["id"])
    rows[0]["package"]["artifacts"] = {"summary": "The grounded explanation.", "key_idea": {}}
    db.replace_gaps(sess["id"], rows)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng._new_card(eng.gaps[0], "reteach", "analogy")
    shown = eng._present(card)
    assert shown["form"] == "words" and shown["reteach"]["content"]["summary"]
    q = eng.advance(card["id"])["next"]
    result = eng.answer(q["id"], _correct_choice(db, q))
    assert result["credited_form"] == "words"
    assert db.get_tally(lr["id"])["analogy"]["attempts"] == 0
