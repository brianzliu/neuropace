import numpy as np

from reflow.config import FORMS, Settings
from reflow.core import tally as T
from reflow.store.db import DB


def test_population_prior_and_posteriors():
    s = Settings()
    pop = {
        "plain": {"rescues": 8, "attempts": 10},
        "keyterm": {"rescues": 0, "attempts": 0},
        "analogy": {"rescues": 1, "attempts": 10},
        "sketch": {"rescues": 0, "attempts": 0},
    }
    prior = T.population_prior(pop, s.tally_prior_pseudocount)
    assert abs(prior["words"][0] + prior["words"][1] - 2.0) < 1e-9
    assert prior["words"][0] > prior["analogy"][0]
    assert abs(prior["visual"][0] - 1.0) < 1e-9  # no data -> 0.5 mean
    post = T.posteriors({f: {"rescues": 0, "attempts": 0} for f in FORMS}, prior)
    assert post["words"].posterior_mean > post["analogy"].posterior_mean
    assert post["words"].rate is None


def test_thompson_pick_is_seeded_and_prefers_strong_arm():
    s = Settings()
    prior = T.population_prior({f: {"rescues": 0, "attempts": 0} for f in FORMS}, s.tally_prior_pseudocount)
    learner = {f: {"rescues": 0, "attempts": 0} for f in FORMS}
    learner["analogy"] = {"rescues": 30, "attempts": 40}
    learner["words"] = {"rescues": 10, "attempts": 40}
    learner["visual"] = {"rescues": 20, "attempts": 40}
    learner["doing"] = {"rescues": 18, "attempts": 40}
    post = T.posteriors(learner, prior)
    picks = [T.thompson_pick(post, np.random.default_rng(i)) for i in range(200)]
    assert picks.count("analogy") > 150
    # untried arms keep being explored: with two arms at Beta(1,1) the strong arm is picked far less often
    learner2 = {f: {"rescues": 0, "attempts": 0} for f in FORMS}
    learner2["analogy"] = {"rescues": 30, "attempts": 40}
    picks2 = [T.thompson_pick(T.posteriors(learner2, prior), np.random.default_rng(i)) for i in range(200)]
    assert 40 < picks2.count("analogy") < 150
    assert T.thompson_pick(post, np.random.default_rng(3)) == T.thompson_pick(post, np.random.default_rng(3))
    assert T.rank(post)[0] == "analogy"


def test_summary_enough_data_threshold_and_db_roundtrip(tmp_path):
    s = Settings()
    db = DB(tmp_path / "t.db")
    lr = db.create_learner("x")
    for i in range(11):
        db.tally_add(lr["id"], "visual", rescue=(i % 2 == 0))
    summ = T.summary(db.get_tally(lr["id"]), db.population_tally(), s, np.random.default_rng(0))
    assert not summ["enough_data"] and summ["total_attempts"] == 11
    db.tally_add(lr["id"], "doing", rescue=True)
    summ = T.summary(db.get_tally(lr["id"]), db.population_tally(), s, np.random.default_rng(0))
    assert summ["enough_data"] and summ["forms"]["visual"]["rescues"] == 6


def test_tally_finds_true_preference_like_bandit_sim():
    """75% vs 55% arms, quiz-scored Thompson sampling: after 150 cards the posterior-mean argmax is the best arm most of the time."""
    s = Settings()
    p_true = {"words": 0.55, "visual": 0.75, "analogy": 0.55, "doing": 0.55}
    prior = T.population_prior({f: {"rescues": 0, "attempts": 0} for f in FORMS}, s.tally_prior_pseudocount)
    hits = 0
    sims = 120
    for k in range(sims):
        rng = np.random.default_rng(1000 + k)
        counts = {f: {"rescues": 0, "attempts": 0} for f in FORMS}
        for _ in range(150):
            post = T.posteriors(counts, prior)
            arm = T.thompson_pick(post, rng)
            y = rng.random() < p_true[arm]
            counts[arm]["attempts"] += 1
            counts[arm]["rescues"] += int(y)
        hits += T.rank(T.posteriors(counts, prior))[0] == "visual"
    assert hits / sims >= 0.8


def test_combined_ranking_puts_understanding_first_and_attention_second():
    """docs/PRODUCT.md §5: score = 0.6 x rescues posterior + 0.4 x mean focus; attention only once measured."""
    import numpy as np

    from reflow.config import Settings
    from reflow.core import tally as t

    s = Settings()
    learner = {"words": {"rescues": 6, "attempts": 8}, "visual": {"rescues": 6, "attempts": 8}}
    pop = {}
    focus = {"visual": {"mean_focus": 0.95, "n": 4}, "words": {"mean_focus": 0.55, "n": 4}}
    summ = t.summary(learner, pop, s, np.random.default_rng(0), focus=focus)
    assert summ["rank"][0] == "visual", "same understanding: the family that held attention ranks first"
    assert summ["forms"]["visual"]["score"] > summ["forms"]["words"]["score"]
    assert summ["preferred"] == "visual" and summ["enough_data"]
    plain = t.summary(learner, pop, s, np.random.default_rng(0), focus=None)
    assert plain["forms"]["visual"]["score"] == plain["forms"]["visual"]["posterior_mean"]
    assert plain["rank"] == plain["rank_understanding"]
    few = t.summary({"visual": {"rescues": 2, "attempts": 2}}, pop, s, np.random.default_rng(0))
    assert few["preferred"] is None and not few["enough_data"]
