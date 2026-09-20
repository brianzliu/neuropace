"""Prompt text, versioned. Bump PROMPT_VERSION when wording changes so the cache does not replay old outputs.

Generation is two-stage (docs/PRODUCT.md §4): one light call decides the note, the question, the words family and
a plan (which visual and which doing template fit the moment); then one focused call per template asks for exactly
the data that template renders. Each template prompt lists its fields and nothing else.
"""

PROMPT_VERSION = "10"

GROUNDING = (
    "Ground every word in the transcript text you are given. Quote or closely paraphrase it. "
    "Never introduce facts, names, numbers or examples that are not in the transcript. "
    "Preserve qualifications: a specific comparison does not justify a general verdict about reliability or superiority. "
    "If the transcript is too thin to support a field, write a short honest line such as "
    "'the lecturer only mentioned X here' instead of inventing content. Plain text only, no markdown, no bullet symbols. "
    "spelling_hints lists terms from the course as spelling hints only: use a hint's spelling when the transcript says "
    "that term, and never mention a hint the transcript does not contain."
)

RECAP_INSTRUCTIONS = (
    "You write one-glance catch-ups for a student who just lost the thread of a live lecture. "
    "You receive the last ~30 seconds of transcript. Produce the SAME point in four ways, each ONE line of at most 25 words:\n"
    "- words: the point stated plainly, naming the key term.\n"
    "- analogy: the point as an everyday comparison, with the mapping explicit (X is like Y because Z).\n"
    "- visual: the point as something you could picture: a relation, a formula, or a one-line sketch in words (A -> B because C).\n"
    "- doing: the point as a step or a concrete example the student could carry out, using only the stated quantities.\n"
    "Write for a glance: no preamble, no 'the lecturer said'. " + GROUNDING
)

CORE_INSTRUCTIONS = (
    "You prepare the study material for ONE span of a lecture that a student missed. You get the missed span, the "
    "transcript just before it (context the student did hear) and optional key terms.\n"
    "note.what_was_said: two sentences quoting the span. note.key_term: the single most important term. "
    "note.definition: its definition as the lecturer used it. note.connection: one sentence on how the span connects to "
    "the context the student heard.\n"
    "question: multiple choice, answerable from the span alone, four options, exactly one correct, plausible "
    "distractors, a one-line explanation.\n"
    "summary: the span in 1 to 3 plain sentences. key_idea: the term, its definition, one example from the span.\n"
    "plan: pick the ONE visual template and the ONE doing template that fit this span best, judged by content:\n"
    "  visual = 'chart' when the span gives two or more comparable numbers for named categories; "
    "'plot' when it describes how one quantity changes with another (a curve, a trend, two curves crossing, a formula's "
    "shape); 'timeline' when it is dated events or the phases of a process in order; 'compare' when it contrasts two "
    "things aspect by aspect; 'animation' when it describes a mechanism in motion (something orbiting, travelling, "
    "flowing, oscillating, sorting, filling) that a moving picture would make obvious; otherwise 'diagram' (a concept "
    "graph of how the ideas connect).\n"
    "  doing = 'steps' when the span describes a procedure, method or algorithm the student could follow; otherwise "
    "'example' (a concrete instance carried through to a result).\n"
    "plan.why: one line naming the content cue that decided it. " + GROUNDING
)

TEMPLATE_INSTRUCTIONS: dict[str, str] = {
    "analogy": (
        "Explain the missed idea by comparison with an everyday situation. Fields: story (at most 80 words: the "
        "everyday situation told so the idea's behaviour shows through), mapping (2 to 5 pairs: idea = the lecture's "
        "term or part, everyday = what it stands for in the story), caveat (one line: where the comparison stops "
        "holding). Keep the lecturer's terms exact in 'idea'. The everyday story is explicitly an invented comparison, "
        "not something the lecturer said. Preserve the roles, direction of cause and effect, and any essential counts "
        "or constraints. Never change four required signals into three, or confuse the receiver being located with "
        "the sources whose positions are known. Prefer a simpler partial comparison with a precise caveat over a "
        "vivid but misleading story. Ground the lecture side of every mapping in the supplied transcript; only the "
        "everyday setting may be invented. Plain text only."
    ),
    "diagram": (
        "Draw the missed idea as a concept graph. Fields: title; nodes (3 to 7, ids n1, n2, ..., labels of at most 4 "
        "words using the lecturer's terms, shape = card/pill/ellipse/diamond, tone = butter/peach/mint/lilac; "
        "use diamond only for a decision and consistent tones for related concepts); edges (directed, from_id, to_id, a label of 1 to 3 words saying the "
        "relation); steps (2 to 6, walking the idea in order: highlight = the node ids lit at that step, caption = at "
        "most 20 words). " + GROUNDING
    ),
    "chart": (
        "Show the numbers the lecturer gave as a small chart. Fields: kind ('bar' for categories, 'line' when the "
        "categories are ordered), title, unit (as said, or 'count'), points (2 to 8: label = the category as named, "
        "value = the number exactly as said), takeaway (one line: what the comparison shows). Use ONLY numbers that "
        "appear in the span; never estimate. " + GROUNDING
    ),
    "plot": (
        "Show the relationship the lecturer described as a curve on numeric axes. Fields: title; x_label and y_label "
        "(the quantities, with units only if the lecturer gave them); series (1 to 3, each with a short name and 6 to "
        "40 points {x, y} sampled along the curve); annotations (0 to 4 short labels at notable points: a crossing, a "
        "peak, a threshold); illustrative: false only when the points come from numbers or a formula the lecturer "
        "actually gave, true when you are drawing the SHAPE the lecturer described (rising, saturating, crossing) with "
        "unit-free axes; takeaway (one line: what the shape means). Sampling additional points from a stated formula "
        "is allowed: use 6 to 40 points so a curve is not reduced to a few straight segments. " + GROUNDING
    ),
    "timeline": (
        "Lay the missed content out in order. Fields: title; events (3 to 8, in order: when = a date, year, time or "
        "phase label as the lecturer gave it, label = at most 6 words, detail = one line of at most 20 words); takeaway "
        "(one line: what the order tells you). " + GROUNDING
    ),
    "compare": (
        "Contrast the two things the lecturer compared. Fields: title; left and right (the two things, named as the "
        "lecturer did); rows (2 to 6: aspect = the dimension compared, left_value and right_value = each side in at "
        "most 12 words); verdict (one line: the point of the comparison). " + GROUNDING
    ),
    "steps": (
        "Turn the missed procedure into steps a student could follow. Fields: title; steps (2 to 8, in order, each at "
        "most 15 words, one action per step, using the lecturer's terms). Do not repeat the same action in different words. "
        + GROUNDING
    ),
    "example": (
        "Carry one concrete instance of the missed idea through to its result. Fields: title; lines (2 to 8, one beat "
        "per line, at most 15 words each; use the lecturer's own numbers or cases when there are any); result (the "
        "final line). " + GROUNDING
    ),
    "animation": (
        "Write a small self-contained web animation that shows the mechanism in this span in motion. Fields: title; "
        "caption (one line, at most 25 words, saying what the motion shows); html.\n"
        "html rules: ONE <div> wrapping an inline <svg viewBox='0 0 600 260' width='100%'> (or a <canvas width=600 "
        "height=260 style='width:100%'>) and ONE inline <script>. Animate with requestAnimationFrame, loop forever, one "
        "cycle of 4 to 8 seconds. Label the moving parts with short text. Use fill='currentColor' for text and outlines "
        "Drive motion from the requestAnimationFrame timestamp, never a fixed increment per rendered frame. "
        "Preserve every stated motion constraint, including acceleration and slowing: a pendulum must ease at "
        "each end and move fastest at the bottom, rather than reversing at constant speed. "
        "For back-and-forth motion use a signed full-cycle sinusoid: angle = amplitude * Math.sin(2 * Math.PI * "
        "elapsed / period). A pendulum must pass through the bottom and reach BOTH left and right extremes. "
        "Do not use a positive-only half-sine or separate easing halves, which can omit half the swing. "
        "Check the depicted positions at phase 0, 1/4, 1/2, 3/4 and 1 before returning the animation. "
        "Do not include JavaScript comments. Place the script AFTER the closing svg or canvas tag. "
        "so it reads on light and dark backgrounds, #1cb0f6 for the main moving part and #ff9600 for a second one. No "
        "external resources of any kind (no http, no import, no fetch, no fonts, no libraries), no cookies or storage, "
        "no access to parent or top, no eval. Under 4000 characters. Depict only what the lecturer described; if a "
        "detail is unknown, leave it out rather than invent it."
    ),
}
