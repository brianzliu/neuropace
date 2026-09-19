"""Extractive offline generator (TDD §7). Used when there is no key, a call fails, or a call times out.

Everything here is honest and grounded by construction: it only rearranges words from the transcript.
Outputs are labelled source="offline" by the caller and the UI shows the badge.
"""

from __future__ import annotations

import re
from collections import Counter

import numpy as np

from .schemas import (
    Artifacts,
    Chart,
    CheckQuestion,
    GapNote,
    GapPackage,
    KeyIdea,
    RecapForms,
    SceneEdge,
    SceneGraph,
    SceneNode,
    SceneStep,
    Steps,
    WorkedExample,
)

STOP = set(
    """a an and are as at be been but by for from has have he her his i if in into is it its of on or our she so that the
    their them then there these they this to was we were what when which who will with would you your not can could
    also just like more most very really about over under after before because while where than too any some such only
    thing things get got make made does did do done here now well say said says one two three first second next""".split()
)

_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text.strip()) if s.strip()]


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text)


def rare_terms(span_text: str, corpus_text: str, k: int = 4, min_len: int = 6) -> list[str]:
    corpus = Counter(t.lower() for t in tokens(corpus_text))
    seen: dict[str, str] = {}
    for t in tokens(span_text):
        lt = t.lower()
        if len(lt) >= min_len and lt not in STOP and lt not in seen:
            seen[lt] = t
    ranked = sorted(seen.items(), key=lambda kv: (corpus.get(kv[0], 0), -len(kv[0])))
    return [orig for _, orig in ranked[:k]] or [t for t in tokens(span_text)[:k]] or ["this idea"]


def tail(text: str, n_words: int = 22) -> str:
    ws = text.split()
    out = " ".join(ws[-n_words:])
    return out if out else "(nothing was transcribed for this span)"


def sentence_with(term: str, text: str) -> str:
    for s in sentences(text):
        if term.lower() in s.lower():
            return s
    ss = sentences(text)
    return ss[0] if ss else tail(text)


def recap_forms(window_text: str, corpus_text: str) -> RecapForms:
    plain = tail(window_text, 22)
    term = rare_terms(window_text, corpus_text, 1)[0]
    kt = f"{term}: {tail(sentence_with(term, window_text), 16)}"
    return RecapForms(
        words=kt, analogy="(offline) " + plain, visual="(offline) " + plain, doing="(offline) " + plain
    )


def _phrases(text: str, length: int, rng: np.random.Generator, n: int, avoid: set[str]) -> list[str]:
    ws = text.split()
    cands = []
    for i in range(0, max(0, len(ws) - length + 1), max(1, length // 2)):
        p = " ".join(ws[i : i + length]).strip(" ,.;:")
        if p and p.lower() not in avoid and len(p) > 12:
            cands.append(p)
    if not cands:
        return []
    idx = rng.permutation(len(cands))[:n]
    return [cands[i] for i in idx]


_GENERIC = [
    "The lecturer paused to take a question from the room",
    "The lecturer summarized the previous week's material",
    "The lecturer announced the deadline for the assignment",
    "The lecturer showed a video clip unrelated to the topic",
]


def gap_package(span_text: str, context_text: str, corpus_text: str, seed: int = 0) -> GapPackage:
    rng = np.random.default_rng(seed)
    terms = rare_terms(span_text, corpus_text, 4)
    term = terms[0]
    sents = sentences(span_text) or [tail(span_text)]
    said = " ".join(sents[:2])
    definition = sentence_with(term, span_text)
    connection = (
        f'Just before this, the lecturer had said: "{tail(context_text, 18)}"'
        if context_text.strip()
        else "This was the first part of the lecture you heard."
    )
    note = GapNote(what_was_said=said, key_term=term, definition=definition, connection=connection)
    correct = _phrases(span_text, 6, rng, 1, set())
    correct_phrase = correct[0] if correct else tail(span_text, 6)
    avoid = {correct_phrase.lower()}
    other_text = corpus_text.replace(span_text, " ") if span_text in corpus_text else context_text
    distractors = _phrases(other_text, 6, rng, 3, avoid)
    gi = 0
    while len(distractors) < 3:
        distractors.append(_GENERIC[gi])
        gi += 1
    options = [correct_phrase] + distractors[:3]
    order = rng.permutation(4)
    options = [options[i] for i in order]
    correct_index = int(np.where(order == 0)[0][0])
    question = CheckQuestion(
        question="Which of these was said in the part you missed?",
        options=options,
        correct_index=correct_index,
        explanation=f'The lecturer said: "{correct_phrase}".',
    )
    nodes = [SceneNode(id=f"n{i + 1}", label=t) for i, t in enumerate(terms[:4])]
    if len(nodes) < 2:
        nodes.append(SceneNode(id="n2", label="the point"))
    edges = [
        SceneEdge(from_id=nodes[i].id, to_id=nodes[i + 1].id, label="then") for i in range(len(nodes) - 1)
    ]
    steps = []
    for i, n in enumerate(nodes):
        cap = sents[i] if i < len(sents) else f"{n.label} is part of this idea."
        steps.append(SceneStep(highlight=[m.id for m in nodes[: i + 1]], caption=" ".join(cap.split()[:20])))
    diagram = SceneGraph(title=f"(offline) {term}", nodes=nodes, edges=edges, steps=steps)
    artifacts = Artifacts(
        summary=tail(span_text, 60),
        key_idea=KeyIdea(term=term, definition=definition, example=tail(span_text, 30)),
        analogy="(offline) " + tail(span_text, 60),
        diagram=diagram,
        chart=Chart(applicable=False, kind="bar", title="", unit="", points=[], takeaway=""),
        steps=Steps(
            applicable=len(sents) >= 2,
            title=f"(offline) {term}",
            steps=[" ".join(s.split()[:15]) for s in sents[:6]],
        ),
        example=WorkedExample(
            title=f"(offline) {term}",
            lines=[" ".join(s.split()[:15]) for s in sents[:4]] or [tail(span_text, 15)],
            result=tail(span_text, 12),
        ),
    )
    return GapPackage(note=note, question=question, artifacts=artifacts)
