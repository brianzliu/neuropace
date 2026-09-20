"""Per-learner form tally (TDD §8.2): Beta posteriors with a population prior, Thompson pick, ranking."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from ..config import FORM_LABELS, FORMS, Settings

Counts = dict[str, dict]  # form -> {"rescues": int, "attempts": int}


@dataclass(slots=True)
class FormStat:
    form: str
    rescues: int
    attempts: int
    prior_a: float
    prior_b: float
    post_a: float
    post_b: float
    posterior_mean: float
    rate: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def population_prior(pop: Counts, pseudocount: float) -> dict[str, tuple[float, float]]:
    out = {}
    for f in FORMS:
        c = pop.get(f, {"rescues": 0, "attempts": 0})
        p = (c["rescues"] + 1.0) / (c["attempts"] + 2.0)
        out[f] = (pseudocount * p, pseudocount * (1.0 - p))
    return out


def posteriors(learner: Counts, prior: dict[str, tuple[float, float]]) -> dict[str, FormStat]:
    out = {}
    for f in FORMS:
        c = learner.get(f, {"rescues": 0, "attempts": 0})
        a0, b0 = prior[f]
        a = a0 + c["rescues"]
        b = b0 + (c["attempts"] - c["rescues"])
        out[f] = FormStat(
            form=f,
            rescues=int(c["rescues"]),
            attempts=int(c["attempts"]),
            prior_a=round(a0, 4),
            prior_b=round(b0, 4),
            post_a=round(a, 4),
            post_b=round(b, 4),
            posterior_mean=round(a / (a + b), 4),
            rate=(round(c["rescues"] / c["attempts"], 3) if c["attempts"] else None),
        )
    return out


def thompson_pick(post: dict[str, FormStat], rng: np.random.Generator) -> str:
    samples = {f: float(rng.beta(st.post_a, st.post_b)) for f, st in post.items()}
    return max(FORMS, key=lambda f: samples[f])


def rank(post: dict[str, FormStat]) -> list[str]:
    return sorted(FORMS, key=lambda f: (-post[f].posterior_mean, FORMS.index(f)))


UNDERSTANDING_WEIGHT = 0.6
ATTENTION_WEIGHT = 0.4


def combined_score(post: dict[str, FormStat], focus: dict[str, dict] | None) -> dict[str, float]:
    """Understanding first, attention second (docs/PRODUCT.md §5): 0.6 x posterior mean of rescues plus
    0.4 x mean focus while reading, when focus has been measured for that family at all."""
    out = {}
    for f in FORMS:
        u = post[f].posterior_mean
        fo = (focus or {}).get(f) or {}
        m = fo.get("mean_focus")
        out[f] = (
            round(UNDERSTANDING_WEIGHT * u + ATTENTION_WEIGHT * float(m), 4) if m is not None else round(u, 4)
        )
    return out


def combined_rank(scores: dict[str, float]) -> list[str]:
    return sorted(FORMS, key=lambda f: (-scores[f], FORMS.index(f)))


def summary(
    learner: Counts, pop: Counts, s: Settings, rng: np.random.Generator, focus: dict[str, dict] | None = None
) -> dict:
    prior = population_prior(pop, s.tally_prior_pseudocount)
    post = posteriors(learner, prior)
    total = sum(st.attempts for st in post.values())
    forms = {f: st.to_dict() for f, st in post.items()}
    scores = combined_score(post, focus)
    for f in FORMS:
        forms[f]["label"] = FORM_LABELS[f]
        forms[f]["focus"] = (focus or {}).get(f, {"mean_focus": None, "n": 0})
        forms[f]["score"] = scores[f]
    ranking = combined_rank(scores)
    enough = total >= s.tally_enough_attempts
    return {
        "forms": forms,
        "rank": ranking,
        "rank_understanding": rank(post),
        "preferred": ranking[0] if enough else None,
        "pick": thompson_pick(post, rng),
        "enough_data": enough,
        "total_attempts": total,
        "needed_attempts": s.tally_enough_attempts,
        "population": {f: pop.get(f, {"rescues": 0, "attempts": 0}) for f in FORMS},
    }
