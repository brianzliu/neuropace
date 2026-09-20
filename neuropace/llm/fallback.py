"""Extractive offline generator (TDD §7). Used when there is no key, a call fails, or a call times out.

Everything here is honest and grounded by construction: it only rearranges words from the transcript.
Outputs are labelled source="offline" by the caller and the UI shows the badge.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np

from .schemas import (
    XY,
    Analogy,
    Animation,
    Chart,
    ChartPoint,
    CheckQuestion,
    Compare,
    CompareRow,
    GapNote,
    KeyIdea,
    Mapping,
    Plan,
    Plot,
    RecapForms,
    SceneEdge,
    SceneGraph,
    SceneNode,
    SceneStep,
    Series,
    Steps,
    Strict,
    Timeline,
    TimelineEvent,
    WorkedExample,
)

STOP = set(
    """a an and are as at be been but by for from has have he her his i if in into is it its of on or our she so that the
    their them then there these they this to was we were what when which who will with would you your not can could
    also just like more most very really about over under after before because while where than too any some such only
    thing things get got make made does did do done here now well say said says one two three first second next""".split()
)

# rare_terms() picks a "key term" purely by length + corpus rarity; without this, a common linking
# verb or adverb that only happens to appear once in a short transcript (e.g. "transfers", "usually")
# outranks the real named concept just for being an unusually long word. -ly words are excluded by
# suffix below; these are the common verb forms that survive that filter.
_GENERIC_FILLER = set(
    """transfers transfer reduces reduce increases increase shows show means mean causes cause
    creates create produces produce provides provide allows allow requires require involves involve
    includes include affects affect changes change carries carry becomes become remains remain
    appears appear occurs occur happens happen results result leads lead gives give takes take
    describes describe explains explain represents represent determines determine depends depend
    relates relate connects connect combines combine reflects reflect suggests suggest indicates
    indicate demonstrates demonstrate reveals reveal captures capture builds build moves move
    larger smaller higher lower greater faster slower similar several various particular specific
    general common important significant possible current recent previous following different""".split()
)

_SENT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text.strip()) if s.strip()]


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]+", text)


def rare_terms(span_text: str, corpus_text: str, k: int = 4, min_len: int = 6) -> list[str]:
    corpus = Counter(t.lower() for t in tokens(corpus_text))
    seen: dict[str, str] = {}
    order: dict[str, int] = {}
    for i, t in enumerate(tokens(span_text)):
        lt = t.lower()
        if (
            len(lt) >= min_len
            and lt not in STOP
            and lt not in _GENERIC_FILLER
            and not lt.endswith("ly")
            and lt not in seen
        ):
            seen[lt] = t
            order[lt] = i
    # Tiebreak on where the word first appears, not its length: preferring the longest word among
    # equally-rare candidates is what let long common words like "transfers" outrank a real term.
    ranked = sorted(seen.items(), key=lambda kv: (corpus.get(kv[0], 0), order[kv[0]]))
    return [orig for _, orig in ranked[:k]] or [t for t in tokens(span_text)[:k]] or ["this idea"]


def key_phrase(span_text: str, corpus_text: str) -> str:
    """A single rare word ("citric", "standard") means nothing pulled out of context — real concepts
    are usually named in 2-3 words ("citric acid cycle", "standard error"). Grows rare_terms()'s pick
    into the short phrase it's actually part of, by walking outward through the span's own words
    until hitting a stopword/filler or a sentence boundary. Still purely extractive: every word in
    the result was already in the span, in that order."""
    toks = tokens(span_text)
    if not toks:
        return "this idea"
    term = rare_terms(span_text, corpus_text, 1)[0]
    try:
        i0 = next(i for i, t in enumerate(toks) if t.lower() == term.lower())
    except StopIteration:
        return term

    def blocked(tok: str) -> bool:
        lt = tok.lower()
        return lt in STOP or lt in _GENERIC_FILLER

    lo = i0
    while lo > 0 and (i0 - lo) < 1 and not blocked(toks[lo - 1]):
        lo -= 1
    hi = i0
    while hi < len(toks) - 1 and (hi - i0) < 2 and not blocked(toks[hi + 1]):
        hi += 1
    return " ".join(toks[lo : hi + 1])


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


def _numbers(text: str) -> list[tuple[str, float]]:
    """(label, value) for numbers written as digits, label = the word before the number."""
    out: list[tuple[str, float]] = []
    for m in re.finditer(r"(?:([A-Za-z][A-Za-z'-]+)\s+)?(-?\d[\d,]*(?:\.\d+)?)", text):
        try:
            val = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        out.append(((m.group(1) or "value").strip(), val))
    return out[:8]


def _animation_html(terms: list[str]) -> str:
    """A canned, self-contained animation: a signal travelling along the key terms in order (offline stand-in)."""
    labels = [t[:14] for t in (terms or ["idea"])[:4]]
    n = len(labels)
    xs = [80 + i * (440 // max(1, n - 1)) if n > 1 else 300 for i in range(n)]
    nodes = "".join(
        f"<circle cx='{x}' cy='130' r='26' fill='none' stroke='currentColor' stroke-width='2'/>"
        f"<text x='{x}' y='185' text-anchor='middle' font-family='system-ui' font-size='15' fill='currentColor'>{lab}</text>"
        for x, lab in zip(xs, labels, strict=True)
    )
    lines = "".join(
        f"<line x1='{xs[i] + 26}' y1='130' x2='{xs[i + 1] - 26}' y2='130' stroke='currentColor' stroke-width='2'/>"
        for i in range(n - 1)
    )
    return (
        "<div><svg viewBox='0 0 600 260' width='100%' xmlns='http://www.w3.org/2000/svg'>"
        f"{lines}{nodes}<circle id='dot' cx='{xs[0]}' cy='130' r='10' fill='#1cb0f6'/>"
        "<text x='300' y='40' text-anchor='middle' font-family='system-ui' font-size='14' fill='currentColor'>"
        "(offline) the idea moves through the key terms in order</text></svg>"
        "<script>(function(){var xs=" + json.dumps(xs) + ";var dot=document.getElementById('dot');"
        "var T=5000;function f(t){var p=(t%T)/T*(xs.length-1);var i=Math.min(xs.length-2,Math.floor(p));"
        "var u=xs.length>1?p-i:0;var x=xs.length>1?xs[i]+(xs[i+1]-xs[i])*u:xs[0];dot.setAttribute('cx',x);"
        "requestAnimationFrame(f);}requestAnimationFrame(f);})();</script></div>"
    )


def artifact(kind: str, span_text: str, context_text: str, corpus_text: str, seed: int = 0) -> Strict | None:
    """One template filled extractively (tests only). None when the span cannot support that template."""
    terms = rare_terms(span_text, corpus_text, 4)
    term = terms[0]
    sents = sentences(span_text) or [tail(span_text)]
    short = lambda s, n=15: " ".join(s.split()[:n])  # noqa: E731
    if kind == "analogy":
        return Analogy(
            story="(offline) " + tail(span_text, 60),
            mapping=[
                Mapping(idea=t, everyday="(offline) no everyday comparison available") for t in terms[:3]
            ],
            caveat="(offline) the extractive stand-in cannot map ideas onto everyday situations",
        )
    if kind == "diagram":
        nodes = [
            SceneNode(id=f"n{i + 1}", label=t, shape="card", tone=("butter", "peach", "mint", "lilac")[i])
            for i, t in enumerate(terms[:4])
        ]
        if len(nodes) < 2:
            nodes.append(SceneNode(id="n2", label="the point"))
        edges = [
            SceneEdge(from_id=nodes[i].id, to_id=nodes[i + 1].id, label="then") for i in range(len(nodes) - 1)
        ]
        steps = []
        for i, n in enumerate(nodes):
            cap = sents[i] if i < len(sents) else f"{n.label} is part of this idea."
            steps.append(SceneStep(highlight=[m.id for m in nodes[: i + 1]], caption=short(cap, 20)))
        return SceneGraph(title=f"(offline) {term}", nodes=nodes, edges=edges, steps=steps)
    if kind == "chart":
        nums = _numbers(span_text)
        if len(nums) < 2:
            return None
        return Chart(
            kind="bar",
            title=f"(offline) numbers said about {term}",
            unit="as said",
            points=[ChartPoint(label=lab, value=val) for lab, val in nums],
            takeaway="(offline) the numbers as they appeared in the transcript",
        )
    if kind == "plot":
        nums = _numbers(span_text)
        if len(nums) < 3:
            return None
        return Plot(
            title=f"(offline) values in order, {term}",
            x_label="order said",
            y_label="value",
            series=[
                Series(name="as said", points=[XY(x=float(i + 1), y=v) for i, (_, v) in enumerate(nums)])
            ],
            annotations=[],
            illustrative=False,
            takeaway="(offline) each number in the order the lecturer said it",
        )
    if kind == "timeline":
        if len(sents) < 3:
            return None
        ordinals = ["first", "then", "next", "after that", "later", "then", "finally", "last"]
        events = [
            TimelineEvent(when=ordinals[min(i, len(ordinals) - 1)], label=short(s, 6), detail=short(s, 20))
            for i, s in enumerate(sents[:8])
        ]
        return Timeline(
            title=f"(offline) {term}, in order",
            events=events,
            takeaway="(offline) the span, sentence by sentence",
        )
    if kind == "compare":
        if len(terms) < 2:
            return None
        a, b = terms[0], terms[1]
        rows = [
            CompareRow(
                aspect="what was said",
                left_value=short(sentence_with(a, span_text), 12),
                right_value=short(sentence_with(b, span_text), 12),
            ),
            CompareRow(
                aspect="mentioned",
                left_value=f"{span_text.lower().count(a.lower())} times",
                right_value=f"{span_text.lower().count(b.lower())} times",
            ),
        ]
        return Compare(
            title=f"(offline) {a} vs {b}",
            left=a,
            right=b,
            rows=rows,
            verdict="(offline) two terms from the span, side by side",
        )
    if kind == "steps":
        if len(sents) < 2:
            return None
        return Steps(title=f"(offline) {term}", steps=[short(s) for s in sents[:6]])
    if kind == "example":
        return WorkedExample(
            title=f"(offline) {term}",
            lines=[short(s) for s in sents[:4]] or [tail(span_text, 15)],
            result=tail(span_text, 12),
        )
    if kind == "animation":
        return Animation(
            title=f"(offline) {term} in motion",
            caption="(offline) a marker travels through the key terms in the order they were said",
            html=_animation_html(terms),
        )
    raise ValueError(kind)


def plan_for(span_text: str, corpus_text: str, seed: int = 0) -> Plan:
    """The offline plan: numbers pick a chart or a plot, otherwise the visual rotates with the seed so every
    template gets exercised in test mode; steps when there are two or more sentences."""
    nums = _numbers(span_text)
    sents = sentences(span_text)
    terms = rare_terms(span_text, corpus_text, 4)
    if len(nums) >= 3:
        visual = "plot"
    elif len(nums) >= 2:
        visual = "chart"
    else:
        visual = ["diagram", "animation", "timeline", "compare"][seed % 4]
        if visual == "timeline" and len(sents) < 3:
            visual = "diagram"
        if visual == "compare" and len(terms) < 2:
            visual = "diagram"
    doing = "steps" if len(sents) >= 2 else "example"
    return Plan(visual=visual, doing=doing, why="(offline) chosen by counts of numbers, sentences and terms")


def gap_package(span_text: str, context_text: str, corpus_text: str, seed: int = 0) -> dict:
    """The whole package, extractively (tests only): every field the two-stage generator would produce."""
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
    note = GapNote(what_was_said=said, key_term=key_phrase(span_text, corpus_text), definition=definition, connection=connection)
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
    plan = plan_for(span_text, corpus_text, seed)
    artifacts: dict = {
        "summary": tail(span_text, 60),
        "key_idea": KeyIdea(term=term, definition=definition, example=tail(span_text, 30)).model_dump(),
        "plan": plan.model_dump(),
    }
    sources: dict = {"core": "offline"}
    for kind in ("analogy", plan.visual, plan.doing, "diagram", "example"):
        if kind in artifacts:
            continue
        obj = artifact(kind, span_text, context_text, corpus_text, seed)
        if obj is not None:
            artifacts[kind] = obj.model_dump()
            sources[kind] = "offline"
    return {
        "note": note.model_dump(),
        "question": question.model_dump(),
        "artifacts": artifacts,
        "sources": sources,
    }
