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
    assert abs(prior["plain"][0] + prior["plain"][1] - 2.0) < 1e-9
    assert prior["plain"][0] > prior["analogy"][0]
    assert abs(prior["keyterm"][0] - 1.0) < 1e-9  # no data -> 0.5 mean
    post = T.posteriors({f: {"rescues": 0, "attempts": 0} for f in FORMS}, prior)
    assert post["plain"].posterior_mean > post["analogy"].posterior_mean
    assert post["plain"].rate is None


def test_thompson_pick_is_seeded_and_prefers_strong_arm():
    s = Settings()
    prior = T.population_prior({f: {"rescues": 0, "attempts": 0} for f in FORMS}, s.tally_prior_pseudocount)
    learner = {f: {"rescues": 0, "attempts": 0} for f in FORMS}
    learner["analogy"] = {"rescues": 30, "attempts": 40}
    learner["plain"] = {"rescues": 10, "attempts": 40}
    learner["keyterm"] = {"rescues": 20, "attempts": 40}
    learner["sketch"] = {"rescues": 18, "attempts": 40}
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
        db.tally_add(lr["id"], "keyterm", rescue=(i % 2 == 0))
    summ = T.summary(db.get_tally(lr["id"]), db.population_tally(), s, np.random.default_rng(0))
    assert not summ["enough_data"] and summ["total_attempts"] == 11
    db.tally_add(lr["id"], "sketch", rescue=True)
    summ = T.summary(db.get_tally(lr["id"]), db.population_tally(), s, np.random.default_rng(0))
    assert summ["enough_data"] and summ["forms"]["keyterm"]["rescues"] == 6


def test_tally_finds_true_preference_like_bandit_sim():
    """75% vs 55% arms, quiz-scored Thompson sampling: after 150 cards the posterior-mean argmax is the best arm most of the time."""
    s = Settings()
    p_true = {"plain": 0.55, "keyterm": 0.75, "analogy": 0.55, "sketch": 0.55}
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
        hits += T.rank(T.posteriors(counts, prior))[0] == "keyterm"
    assert hits / sims >= 0.8
