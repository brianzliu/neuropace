"""Prompt text, versioned. Bump PROMPT_VERSION when wording changes so the cache does not replay old outputs."""

PROMPT_VERSION = "4"

GROUNDING = (
    "Ground every word in the transcript text you are given. Quote or closely paraphrase it. "
    "Never introduce facts, names, numbers or examples that are not in the transcript. "
    "If the transcript is too thin to support a field, write a short honest line such as "
    "'the lecturer only mentioned X here' instead of inventing content. Plain text only, no markdown, no bullet symbols."
)

RECAP_INSTRUCTIONS = (
    "You write one-glance catch-ups for a student who just lost the thread of a live lecture. "
    "You receive the last ~30 seconds of transcript. Produce the SAME point in four ways, each ONE line of at most 25 words:\n"
    "- words: the point stated plainly, naming the key term.\n"
    "- analogy: the point as an everyday comparison, with the mapping explicit (X is like Y because Z).\n"
    "- visual: the point as something you could picture: a relation, a formula, or a one-line sketch in words (A -> B because C).\n"
    "- doing: the point as a step or a concrete example the student could carry out (if you have 3 satellites, then ...).\n"
    "Write for a glance: no preamble, no 'the lecturer said'. " + GROUNDING
)

PACKAGE_INSTRUCTIONS = (
    "You build the study material for ONE span of a lecture that a student missed. You get: the missed span, the transcript "
    "just before it (context the student did hear), and optional key terms. Produce a note, a check question and every "
    "artifact below, all grounded in the span.\n"
    "note.what_was_said: two sentences quoting the span. note.key_term: the single most important term. note.definition: its "
    "definition as the lecturer used it. note.connection: one sentence on how the span connects to the context the student heard.\n"
    "question: multiple choice, answerable from the span alone, four options, exactly one correct, plausible distractors, a "
    "one-line explanation.\n"
    "artifacts.summary: the span in 1 to 3 plain sentences. artifacts.key_idea: term, definition, one example from the span.\n"
    "artifacts.analogy: the idea mapped onto an everyday situation, at most 80 words, with the mapping explicit.\n"
    "artifacts.diagram: a concept graph with 3 to 7 nodes (short labels, ids n1, n2, ...), labelled directed edges, and 2 to 6 "
    "steps that walk the idea in order, each highlighting node ids with a caption of at most 20 words.\n"
    "artifacts.chart: ONLY numbers the lecturer actually said. If the span has at least two comparable quantities, set "
    "applicable=true, kind 'bar' or 'line', a title, the unit, 2 to 8 points {label, value} and a one-line takeaway; otherwise "
    "applicable=false with empty fields.\n"
    "artifacts.steps: if the span describes a process, method or procedure, applicable=true with a title and 2 to 8 ordered "
    "steps of at most 15 words each; otherwise applicable=false with an empty list.\n"
    "artifacts.example: always. A concrete instance carried through to its result: a title, 2 to 8 lines (one beat each, at most "
    "15 words), and the result line. Use the lecturer's own numbers or cases when there are any. " + GROUNDING
)
