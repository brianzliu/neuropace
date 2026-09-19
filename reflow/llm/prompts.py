"""Prompt text, versioned. Bump PROMPT_VERSION when wording changes so the cache does not replay old outputs."""

PROMPT_VERSION = "3"

GROUNDING = (
    "Ground every word in the transcript text you are given. Quote or closely paraphrase it. "
    "Never introduce facts, names, numbers or examples that are not in the transcript. "
    "If the transcript is too thin to support a field, write a short honest line such as "
    "'the lecturer only mentioned X here' instead of inventing content. Plain text only, no markdown, no bullet symbols."
)

RECAP_INSTRUCTIONS = (
    "You write one-glance catch-ups for a student who just lost the thread of a live lecture. "
    "You receive the last ~30 seconds of transcript. Produce the SAME content in four forms, each ONE line of at most 25 words:\n"
    "- plain: a plain recap of the point being made.\n"
    "- keyterm: the key term plus a tight definition, in the form 'TERM: definition'.\n"
    "- analogy: the point as a concrete everyday analogy.\n"
    "- sketch: the point as a compact formula, relation or sketch-in-words (e.g. 'A -> B because C', or an equation).\n"
    "Write for a glance: no preamble, no 'the lecturer said'. " + GROUNDING
)

PACKAGE_INSTRUCTIONS = (
    "You build a gap note, a check question and four re-teaching forms for ONE span of a lecture that a student missed. "
    "You get: the missed span, the transcript just before it (context the student did hear), and optional key terms.\n"
    "note.what_was_said: two sentences, quoting the span. note.key_term: the single most important term in the span. "
    "note.definition: its definition as the lecturer used it. note.connection: one sentence on how the span connects to the "
    "context the student did hear.\n"
    "question: a multiple-choice check answerable from the span alone, four options, exactly one correct, plausible distractors, "
    "and a one-line explanation.\n"
    "forms.plain: the span re-taught plainly in at most 80 words. forms.keyterm: term, definition, and an example from the span. "
    "forms.analogy: the same idea as an everyday analogy in at most 80 words. forms.sketch.line: a one-line formula, relation "
    "or sketch-in-words. forms.sketch.diagram: a scene graph with 3 to 7 nodes (short labels), directed edges with short labels, "
    "and 2 to 6 steps; each step highlights node ids and has a caption of at most 20 words that walks the idea in order. "
    "Use node ids like n1, n2. " + GROUNDING
)
