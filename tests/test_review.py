import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import neuropace.core.review as reviewmod
from neuropace.config import FORMS, Settings
from neuropace.core.review import ReviewEngine
from neuropace.llm.fallback import artifact, gap_package
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


def _planned_artifacts(db, sess, visual="animation", doing="example"):
    rows = db.get_gaps(sess["id"])
    arts = rows[0]["package"]["artifacts"]
    arts["plan"] = {
        "visual": visual,
        "doing": doing,
        "why": "Show the signal moving, then work through a distance calculation.",
    }
    text = TEXT + " Delays are 2, 4 and 6 seconds."
    for kind in (visual, doing):
        arts[kind] = artifact(kind, text, "", text).model_dump()
    db.replace_gaps(sess["id"], rows)
    return arts


@pytest.mark.parametrize("visual", ["animation", "chart", "diagram", "plot", "timeline", "compare"])
def test_tutor_leads_with_planned_visual_and_resumes_the_same_card(tmp_path, monkeypatch, visual):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    arts = _planned_artifacts(db, sess, visual=visual)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    # Even a words-first preference must not hide a generated visual in tutor mode.
    summary = eng.tally_summary()
    monkeypatch.setattr(eng, "tally_summary", lambda: {**summary, "pick": "words"})
    monkeypatch.setattr(eng, "_tally_rank", lambda: ["words", "analogy", "doing", "visual"])
    card = eng.start()["card"]
    assert card["form"] == "visual" and card["reteach"]["artifact"] == visual
    assert card["reteach"]["content"] == arts[visual]
    assert card["reteach"]["plan_reason"] == arts["plan"]["why"]
    assert card["reteach"]["visual_unavailable"] is False
    assert card["forms_used"] == ["visual"]
    assert db.get_card(card["id"])["artifact_kind"] == visual
    assert eng.start()["card"]["id"] == eng.state()["card"]["id"] == card["id"]
    assert len(db.get_cards(sess["id"])) == 1
    assert eng.progress()["cards_answered"] == 0
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0

    resumed = ReviewEngine(db, s, sess["id"], lr["id"], seed=9)
    assert resumed.start()["card"] == card
    q = resumed.advance(card["id"])["next"]
    assert q["kind"] == "question" and "reteach" not in q
    saved_order = db.get_card(q["id"])["option_order"]
    resumed = ReviewEngine(db, s, sess["id"], lr["id"], seed=11)
    assert resumed.start()["card"] == q
    assert db.get_card(q["id"])["option_order"] == saved_order
    result = resumed.answer(q["id"], _correct_choice(db, q))
    assert result["credited_form"] == "visual" and result["done"]
    assert db.get_tally(lr["id"])["visual"] == {"rescues": 1, "attempts": 1}


@pytest.mark.parametrize("doing", ["example", "steps"])
def test_tutor_misses_try_unused_doing_then_analogy_before_words(tmp_path, monkeypatch, doing):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    arts = _planned_artifacts(db, sess, doing=doing)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    monkeypatch.setattr(eng, "_tally_rank", lambda: ["words", "analogy", "doing", "visual"])
    card = eng.start()["card"]
    families = ["visual", "doing", "analogy", "words"]
    kinds = ["animation", doing, "analogy", "words"]
    for i, (family, kind) in enumerate(zip(families, kinds, strict=True)):
        assert card["form"] == family and card["reteach"]["artifact"] == kind
        assert card["forms_used"] == families[: i + 1]
        if family == "doing":
            assert card["reteach"]["content"] == arts[doing]
            assert card["reteach"]["plan_reason"] == arts["plan"]["why"]
        # Each explanation is followed by exactly one unanswered check, never an auto-answer.
        q = eng.advance(card["id"])["next"]
        assert q["kind"] == "question" and "reteach" not in q
        assert db.get_card(q["id"])["outcome"] is None
        assert eng.progress()["cards_answered"] == i
        assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == i
        r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
        assert r["outcome"] == "miss" and r["credited_form"] == family
        assert db.get_tally(lr["id"])[family] == {"rescues": 0, "attempts": 1}
        card = r["next"]
    assert card is None and r["done"] and r["progress"]["gaps_exhausted"] == 1
    assert [c["kind"] for c in db.get_cards(sess["id"])] == ["reteach", "question"] * 4


@pytest.mark.parametrize("available", ["doing", "analogy", "words"])
def test_tutor_missing_visuals_falls_back_honestly_and_skips_unavailable_families(tmp_path, available):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    arts = _planned_artifacts(db, sess)
    rows = db.get_gaps(sess["id"])
    keep = ["summary", "key_idea", "plan"]
    if available == "doing":
        keep.append("example")
    if available == "analogy":
        keep.append("analogy")
    rows[0]["package"]["artifacts"] = {k: arts[k] for k in keep}
    # A legacy placeholder is not a visual, even when named by the stored plan.
    rows[0]["package"]["artifacts"]["animation"] = {"applicable": False}
    db.replace_gaps(sess["id"], rows)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    card = eng.start()["card"]
    assert card["form"] == available and card["reteach"]["form"] == available
    assert card["reteach"]["artifact"] == ("example" if available == "doing" else available)
    assert card["reteach"]["visual_unavailable"] is True
    assert card["forms_used"] == [available]
    q = eng.advance(card["id"])["next"]
    r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
    assert r["credited_form"] == available
    assert db.get_tally(lr["id"])["visual"]["attempts"] == 0
    if available != "words":
        card = r["next"]
        assert card["form"] == "words" and card["reteach"]["visual_unavailable"] is True
        q = eng.advance(card["id"])["next"]
        r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
    assert r["done"] and r["next"] is None and r["progress"]["gaps_exhausted"] == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_tutor_uses_available_default_visual_when_planned_artifact_is_missing(tmp_path, legacy):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    rows = db.get_gaps(sess["id"])
    arts = rows[0]["package"]["artifacts"]
    if legacy:
        arts.pop("plan")
    else:
        arts["plan"]["visual"] = "animation"
    db.replace_gaps(sess["id"], rows)
    card = ReviewEngine(db, s, sess["id"], lr["id"]).start()["card"]
    assert card["form"] == "visual" and card["reteach"]["artifact"] == "diagram"
    assert card["reteach"]["visual_unavailable"] is False
    if legacy:
        assert "plan_reason" not in card["reteach"]


def test_manual_keeps_quiz_first_and_tally_rank_even_with_a_visual_plan(tmp_path, monkeypatch):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    _planned_artifacts(db, sess)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], mode="manual")
    monkeypatch.setattr(eng, "_tally_rank", lambda: ["words", "visual", "doing", "analogy"])
    q = eng.start()["card"]
    assert q["kind"] == "question" and q["forms_used"] == []
    r = eng.answer(q["id"], (_correct_choice(db, q) + 1) % 4)
    assert r["credited_form"] is None and r["next"]["form"] == "words"
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0
    q = eng.advance(r["next"]["id"])["next"]
    r = eng.answer(q["id"], _correct_choice(db, q))
    assert r["credited_form"] == "words" and r["done"]
    assert db.get_tally(lr["id"])["words"] == {"rescues": 1, "attempts": 1}


async def test_miss_planner_selects_analogy_for_the_actual_wrong_answer_and_preserves_scoring(tmp_path):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    _planned_artifacts(db, sess)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    eng.gaps[0]["context_text"] = "The satellite sends a timestamp."
    eng.gaps[0]["package"]["artifacts"]["animation"]["html"] = "<script>secret-artifact</script>"
    first = eng.start()["card"]
    q = eng.advance(first["id"])["next"]
    correct = _correct_choice(db, q)
    wrong = (correct + 1) % 4
    reason = "A comparison can separate travel time from distance."

    async def structured(task, instructions, payload, model_cls, timeout, max_tokens):
        assert 0 < timeout <= 10 and max_tokens <= 400
        assert "misconception" in instructions and "attention" in instructions
        assert payload["question"] == q["question"]["question"]
        assert payload["selected_answer"] == q["question"]["options"][wrong]
        assert payload["expected_answer"] == q["question"]["options"][correct]
        assert payload["span_text"] == TEXT
        assert payload["context_text"] == eng.gaps[0]["context_text"]
        assert payload["available_formats"] == [
            {"form": "doing", "artifact": "example"},
            {"form": "analogy", "artifact": "analogy"},
            {"form": "words", "artifact": "words"},
        ]
        assert "secret-artifact" not in repr(payload) and "<script>" not in repr(payload)
        assert "api_key" not in repr(payload)
        assert model_cls.model_json_schema()["additionalProperties"] is False
        return model_cls(form="analogy", reason=reason), "llm"

    llm = SimpleNamespace(_structured=AsyncMock(side_effect=structured))
    await eng.plan_after_miss(llm, q["id"], wrong)
    llm._structured.assert_awaited_once()
    assert eng.state()["card"]["id"] == q["id"]
    assert db.get_card(q["id"])["outcome"] is None and eng.cards_answered == 0
    assert sum(v["attempts"] for v in db.get_tally(lr["id"]).values()) == 0
    result = eng.answer(q["id"], wrong)
    card = result["next"]
    assert result["credited_form"] == "visual" and card["form"] == "analogy"
    assert card["reteach"]["plan_reason"] == reason
    assert eng.state()["card"]["reteach"]["plan_reason"] == reason
    assert card["forms_used"] == ["visual", "analogy"]
    assert db.get_card(card["id"])["form"] == "analogy"
    resumed = ReviewEngine(db, s, sess["id"], lr["id"])
    assert resumed.start()["card"]["id"] == card["id"]
    q2 = resumed.advance(card["id"])["next"]
    assert q2["kind"] == "question" and db.get_card(q2["id"])["outcome"] is None
    result = resumed.answer(q2["id"], _correct_choice(db, q2))
    assert result["credited_form"] == "analogy" and result["done"]
    assert db.get_tally(lr["id"])["visual"] == {"rescues": 0, "attempts": 1}
    assert db.get_tally(lr["id"])["analogy"] == {"rescues": 1, "attempts": 1}
    assert db.get_tally(lr["id"])["doing"]["attempts"] == 0


@pytest.mark.parametrize(
    "failure", ["used", "unavailable", "words", "invalid", "blank", "error", "timeout", "none"]
)
async def test_miss_planner_invalid_or_failed_choices_fall_back_to_rich_first(tmp_path, failure):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    if failure == "unavailable":
        eng.gaps[0]["package"]["artifacts"].pop("analogy")
    q = eng.advance(eng.start()["card"]["id"])["next"]
    wrong = (_correct_choice(db, q) + 1) % 4

    async def structured(task, instructions, payload, model_cls, timeout, max_tokens):
        if failure == "error":
            raise RuntimeError("provider error")
        if failure == "timeout":
            raise TimeoutError
        if failure == "none":
            return None, "offline"
        form = {"used": "visual", "unavailable": "analogy", "words": "words", "invalid": "chat"}.get(
            failure, "analogy"
        )
        return model_cls(
            form=form, reason="   " if failure == "blank" else "Try a different explanation."
        ), "llm"

    llm = SimpleNamespace(_structured=AsyncMock(side_effect=structured))
    await eng.plan_after_miss(llm, q["id"], wrong)
    llm._structured.assert_awaited_once()
    result = eng.answer(q["id"], wrong)
    assert result["next"]["form"] == "doing" and result["credited_form"] == "visual"
    assert result["next"]["reteach"]["plan_reason"] == eng.gaps[0]["package"]["artifacts"]["plan"]["why"]


@pytest.mark.parametrize(
    "skip",
    [
        "correct",
        "manual",
        "stale",
        "foreign",
        "noncurrent",
        "reteach",
        "single",
        "disabled",
        "invalid_choice",
    ],
)
async def test_miss_planner_skips_ineligible_requests_without_calling_model(tmp_path, skip):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"], mode="manual" if skip == "manual" else "tutor")
    first = eng.start()["card"]
    q = first if first["kind"] == "question" else eng.advance(first["id"])["next"]
    choice = (_correct_choice(db, q) + 1) % 4
    card_id = q["id"]
    if skip == "correct":
        choice = _correct_choice(db, q)
    elif skip == "stale":
        eng.answer(card_id, choice)
    elif skip == "foreign":
        foreign = db.create_session(learner_id=lr["id"], mode="live", best_form="plain", seed=0)
        card = {**db.get_card(card_id), "id": "foreign_card", "session_id": foreign["id"]}
        db.add_card(card)
        eng.current = card
        card_id = card["id"]
    elif skip == "noncurrent":
        eng._new_card(eng.gaps[0], "question", None)
    elif skip == "reteach":
        card_id = eng._new_card(eng.gaps[0], "reteach", "doing")["id"]
    elif skip == "single":
        eng._forms_used["gap_0"] = ["visual", "doing", "analogy"]
    elif skip == "invalid_choice":
        choice = -1
    llm = SimpleNamespace(enabled=skip != "disabled", _structured=AsyncMock())
    await eng.plan_after_miss(llm, card_id, choice)
    llm._structured.assert_not_awaited()


async def test_miss_planner_has_an_overall_timeout(tmp_path, monkeypatch):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    q = eng.advance(eng.start()["card"]["id"])["next"]
    wrong = (_correct_choice(db, q) + 1) % 4
    monkeypatch.setattr(reviewmod, "_MISS_PLAN_TIMEOUT", 0.01)
    cancelled = asyncio.Event()

    async def structured(*args):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    await asyncio.wait_for(eng.plan_after_miss(SimpleNamespace(_structured=structured), q["id"], wrong), 0.5)
    assert cancelled.is_set()
    assert eng.answer(q["id"], wrong)["next"]["form"] == "doing"


@pytest.mark.parametrize("change", ["answered", "noncurrent"])
async def test_miss_planner_discards_decision_if_card_changes_during_await(tmp_path, change):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    q = eng.advance(eng.start()["card"]["id"])["next"]
    wrong = (_correct_choice(db, q) + 1) % 4

    async def structured(task, instructions, payload, model_cls, timeout, max_tokens):
        if change == "answered":
            db.update_card(q["id"], outcome="drop")
        else:
            eng._new_card(eng.gaps[0], "question", None)
        return model_cls(form="analogy", reason="This result is now stale."), "llm"

    await eng.plan_after_miss(SimpleNamespace(_structured=structured), q["id"], wrong)
    assert eng._miss_plan is None


@pytest.mark.parametrize("action", ["drop", "different_answer"])
async def test_miss_planner_decision_is_bound_to_the_scored_answer(tmp_path, action):
    s, db, lr, sess = _setup(tmp_path, n_gaps=1)
    eng = ReviewEngine(db, s, sess["id"], lr["id"])
    q = eng.advance(eng.start()["card"]["id"])["next"]
    correct = _correct_choice(db, q)
    wrong = (correct + 1) % 4

    async def structured(task, instructions, payload, model_cls, timeout, max_tokens):
        return model_cls(form="analogy", reason="Only for the planned wrong answer."), "llm"

    await eng.plan_after_miss(SimpleNamespace(_structured=structured), q["id"], wrong)
    result = eng.drop(q["id"]) if action == "drop" else eng.answer(q["id"], (correct + 2) % 4)
    assert result["next"]["form"] == "doing"
    assert eng._miss_plan is None
    assert result["next"]["reteach"]["plan_reason"] == eng.gaps[0]["package"]["artifacts"]["plan"]["why"]
