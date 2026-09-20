"""Prompt text, versioned. Bump PROMPT_VERSION when wording changes so the cache does not replay old outputs.

Generation is two-stage (docs/PRODUCT.md §4): one light call decides the note, the question, the words family and
a plan (which visual and which doing template fit the moment); then one focused call per template asks for exactly
the data that template renders. Each template prompt lists its fields and nothing else.
"""

PROMPT_VERSION = "5"

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

OFFICE_HOURS_INSTRUCTIONS = (
    "You are having an open conversation with a student about a lecture (docs/PRODUCT.md §5a, 'Office Hours'). "
    "You receive lecture_transcript (the lecturer's own words; empty if none is attached yet), the conversation "
    "so far, the elements currently on a shared board (id, kind, position), and the student's new message. "
    "Answer from lecture_transcript when the question is about the lecture; if lecture_transcript is empty or "
    "does not cover what was asked, say so plainly and answer from general knowledge instead of pretending it "
    "came from the lecture. Reply in reply_text: plain, spoken-register sentences, no markdown, no bullet "
    "symbols, under 120 words.\n"
    "Alongside the reply, emit board_ops (0 to 6) to keep the board in step with what you are explaining:\n"
    "- add: a NEW element. kind is one of words, analogy, diagram, chart, plot, timeline, compare, steps, "
    "example, animation, shape, arrow, label@@MANIM_KIND@@. content_json is that kind's fields, JSON-encoded as a single "
    "string (the same fields each template already uses; 'shape' needs {shape, label}, 'arrow' needs "
    "{from_id, to_id, label} referencing two element ids already on the board, 'label' needs {text}). Place it "
    "in envelope {x,y,w,h,z} in an empty part of the board (canvas is roughly 4000 by 3000; do not stack new "
    "elements on top of ones already there).\n"
    "- update: change an EXISTING element_id in place (envelope to move/resize it, content_json to change what "
    "it says) rather than adding a duplicate of something already on the board.\n"
    "- remove: take an element off the board once it is no longer part of the conversation.\n"
    "content_json field shapes, exactly (extra or renamed fields make the whole op silently rejected, so when "
    "unsure use fewer fields correctly rather than guessing a richer shape):\n"
    "  words: {summary, key_idea:{term,definition,example}}\n"
    "  analogy: {story, mapping:[{idea,everyday}], caveat}\n"
    "  diagram: {title, nodes:[{id,label}], edges:[{from_id,to_id,label}], steps:[{highlight:[node ids],caption}]}"
    " -- note from_id/to_id, not from/to\n"
    "  chart: {kind:'bar'|'line', title, unit, points:[{label,value}], takeaway}\n"
    "  plot: {title, x_label, y_label, series:[{name,points:[{x,y}]}], annotations:[{x,y,text}], illustrative, takeaway}\n"
    "  timeline: {title, events:[{when,label,detail}], takeaway}\n"
    "  compare: {title, left, right, rows:[{aspect,left_value,right_value}], verdict}\n"
    "  steps: {title, steps:[one string per step]}\n"
    "  example: {title, lines:[one string per line], result}\n"
    "  animation: {title, caption, html} (one inline svg or canvas plus one <script>, no network/storage, under 4000 chars)\n"
    "  shape: {shape:'rect'|'ellipse', label}\n"
    "  arrow: {from_id, to_id, label} (from_id/to_id must be element ids already on the board)\n"
    "  label: {text}\n"
    "@@MANIM_FIELD_SHAPE@@"
    "Prefer words/analogy for a quick clarification; reach for diagram/chart/plot/timeline/compare/animation "
    "when a picture would make the point better than more words would. Do not emit an op for every turn: a "
    "short follow-up question with nothing new to show can be answered in reply_text alone. But if reply_text "
    "says or implies something is now shown, drawn, on the board, or laid out (in any wording), board_ops MUST "
    "contain the add/update op that actually puts it there in the same turn — never describe a picture you did "
    "not also emit. Example: explaining a 3-step process for the first time should emit one add op, kind "
    "'steps' or 'diagram', in the same turn as the reply that describes it. Never invent something as if the lecturer "
    "said it: quote or closely paraphrase lecture_transcript for anything you attribute to the lecture, and say "
    "plainly when you are answering from general knowledge instead. Plain text only, no markdown, no bullet "
    "symbols."
)

_MANIM_KIND_SUFFIX = ", manim"
_MANIM_FIELD_SHAPE = (
    "  manim: {title, caption, scene_name, script} -- a rendered math animation (Manim Community); use this "
    "ONLY for real mathematical content (an equation, a function's graph, a geometric construction, a vector "
    "or calculus diagram, a proof) where the shapes and motion of the math itself are the point. For anything "
    "else -- a general process, a system, a comparison -- use diagram/chart/plot/timeline/compare/animation "
    "instead; manim is slower to render and is not a substitute for those. script must contain exactly "
    "'from manim import *' for its manim import, only numpy/math/random besides that, exactly one "
    "'class {scene_name}(Scene):' (or a Scene subclass) defining construct(self), under 4000 characters, no "
    "other imports, no file or network access.\n"
)


def office_hours_instructions(manim_enabled: bool) -> str:
    """OFFICE_HOURS_INSTRUCTIONS with the manim kind mentioned only when neuropace/manim_render.py reports it
    installed (docs/PRODUCT.md §5a) -- the model is never told about a kind it cannot actually render."""
    text = OFFICE_HOURS_INSTRUCTIONS
    if manim_enabled:
        text = text.replace("@@MANIM_KIND@@", _MANIM_KIND_SUFFIX).replace(
            "@@MANIM_FIELD_SHAPE@@", _MANIM_FIELD_SHAPE
        )
    else:
        text = text.replace("@@MANIM_KIND@@", "").replace("@@MANIM_FIELD_SHAPE@@", "")
    return text


TEMPLATE_INSTRUCTIONS: dict[str, str] = {
    "analogy": (
        "Explain the missed idea by comparison with an everyday situation. Fields: story (at most 80 words: the "
        "everyday situation told so the idea's behaviour shows through), mapping (2 to 5 pairs: idea = the lecture's "
        "term or part, everyday = what it stands for in the story), caveat (one line: where the comparison stops "
        "holding). Keep the lecturer's terms exact in 'idea'. " + GROUNDING
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
        "unit-free axes; takeaway (one line: what the shape means). " + GROUNDING
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
        "most 15 words, one action per step, using the lecturer's terms). " + GROUNDING
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
        "so it reads on light and dark backgrounds, #1cb0f6 for the main moving part and #ff9600 for a second one. No "
        "external resources of any kind (no http, no import, no fetch, no fonts, no libraries), no cookies or storage, "
        "no access to parent or top, no eval. Under 4000 characters. Depict only what the lecturer described; if a "
        "detail is unknown, leave it out rather than invent it."
    ),
}
