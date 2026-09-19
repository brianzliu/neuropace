import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { FORM_LABEL, type Card, type KeyTermContent, type Progress, type SketchContent, type TallySummary } from "../lib/types";
import { range } from "../lib/format";
import { flash } from "../lib/flash";
import { SourceBadge } from "../components/Badges";
import Dissolve from "../components/Dissolve";
import Diagram from "../components/Diagram";
import TallyPanel from "../components/TallyPanel";
import { Group, Row } from "../components/Inspector";

type Phase = "idle" | "answering" | "feedback" | "dissolving" | "reteach" | "done";

export default function Review() {
  const { sessionId = "" } = useParams();
  const [card, setCard] = useState<Card | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [tally, setTally] = useState<TallySummary | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [err, setErr] = useState<string | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [correctIdx, setCorrectIdx] = useState<number | null>(null);
  const [explanation, setExplanation] = useState("");
  const [credited, setCredited] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<"hit" | "miss" | "drop" | null>(null);
  const [step, setStep] = useState(0);
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [lectureId, setLectureId] = useState<string | null>(null);
  const pendingNext = useRef<Card | null>(null);
  const busy = useRef(false);

  const applyNext = useCallback((next: Card | null, done: boolean) => {
    setChosen(null);
    setCorrectIdx(null);
    setOutcome(null);
    setStep(0);
    if (done || !next) {
      setCard(null);
      setPhase("done");
      return;
    }
    setCard(next);
    setPhase(next.kind === "question" ? "answering" : "reteach");
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [st, sess] = await Promise.all([api.reviewStart(sessionId), api.session(sessionId)]);
        if (cancelled) return;
        setLearnerId(sess.learner_id);
        setLectureId(sess.lecture_id);
        setProgress(st.progress);
        setTally(st.tally);
        applyNext(st.card, st.progress.done);
      } catch (e) {
        setErr(errorText(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, applyNext]);

  const answer = useCallback(
    async (choice: number) => {
      if (!card || card.kind !== "question" || phase !== "answering" || busy.current) return;
      busy.current = true;
      setChosen(choice);
      try {
        const r = await api.reviewAnswer(sessionId, card.id, choice);
        setCorrectIdx(r.correct_index);
        setExplanation(r.explanation);
        setCredited(r.credited_form);
        setOutcome(r.outcome);
        setProgress(r.progress);
        setTally(r.tally);
        setPhase("feedback");
        pendingNext.current = r.next;
        const done = r.done;
        window.setTimeout(() => {
          if (r.outcome === "miss" && r.next && r.next.kind === "reteach") {
            setPhase("dissolving");
            window.setTimeout(() => applyNext(pendingNext.current, done), 750);
          } else {
            applyNext(pendingNext.current, done);
          }
        }, r.outcome === "hit" ? 1100 : 1400);
      } catch (e) {
        setErr(String(e));
      } finally {
        busy.current = false;
      }
    },
    [card, phase, sessionId, applyNext],
  );

  const drop = useCallback(async () => {
    if (!card || busy.current || (phase !== "answering" && phase !== "reteach")) return;
    busy.current = true;
    flash("SIMULATED FOCUS DROP");
    try {
      const r = await api.reviewDrop(sessionId, card.id);
      setOutcome("drop");
      setProgress(r.progress);
      setTally(r.tally);
      setPhase("dissolving");
      window.setTimeout(() => applyNext(r.next, r.done), 750);
    } catch (e) {
      setErr(String(e));
    } finally {
      busy.current = false;
    }
  }, [card, phase, sessionId, applyNext]);

  const advance = useCallback(async () => {
    if (!card || card.kind !== "reteach" || busy.current) return;
    busy.current = true;
    try {
      const r = await api.reviewAdvance(sessionId, card.id);
      setProgress(r.progress);
      setTally(r.tally);
      applyNext(r.next, r.done);
    } catch (e) {
      setErr(String(e));
    } finally {
      busy.current = false;
    }
  }, [card, sessionId, applyNext]);

  const sketch = card?.kind === "reteach" && card.reteach?.form === "sketch" ? (card.reteach.content as SketchContent | null) : null;
  const nSteps = sketch?.diagram.steps.length ?? 0;

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const k = ev.key;
      if (phase === "answering" && ["1", "2", "3", "4"].includes(k)) void answer(Number(k) - 1);
      else if (k.toLowerCase() === "d") void drop();
      else if (phase === "reteach" && (k === " " || k === "ArrowRight")) {
        ev.preventDefault();
        if (sketch && step < nSteps - 1) setStep((s) => s + 1);
        else void advance();
      } else if (phase === "reteach" && k === "Enter") void advance();
      else return;
      ev.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, answer, drop, advance, sketch, step, nSteps]);

  if (err) {
    return (
      <div className="page narrow">
        <div className="card stack">
          <div className="t-headline">Not quite ready</div>
          <div className="label-2">{err}</div>
          <div className="row">
            <Link className="btn" to={`/notes/${sessionId}`}>
              Back to notes
            </Link>
          </div>
        </div>
      </div>
    );
  }
  if (!progress || !tally) return <div className="page narrow"><div className="loading">Preparing review…</div></div>;

  return (
    <div className="page">
      <div className="review-layout">
        <div className="review-sheet">
          <div className="progress-row">
            <span>
              gaps closed <b className="tabular">{progress.gaps_closed}/{progress.gaps_total}</b>
              {progress.gaps_exhausted ? ` (${progress.gaps_exhausted} exhausted)` : ""}
            </span>
            <span className="streak">
              streak {progress.streak}/{progress.stop_streak}
            </span>
            <span>cards {progress.cards_answered}</span>
            {card ? (
              <span className="mono">
                gap {card.gap_ord + 1} · {range(card.t_start, card.t_end)}
              </span>
            ) : null}
            {card ? <SourceBadge source={card.package_source} /> : null}
          </div>
          <div className="sheet">
            {phase === "done" || !card ? (
              <div className="done">
                <div className="mark">✓</div>
                <h2 className="t-title2">That is it. Nicely done.</h2>
                <div className="label-2">
                  {progress.streak >= progress.stop_streak ? `${progress.stop_streak} straight hits.` : "Every gap is closed or exhausted."} {progress.gaps_closed}/{progress.gaps_total} gaps closed.
                </div>
                <div className="row">
                  {learnerId ? <Link className="btn" to={`/tally/${learnerId}`}>What works for you</Link> : null}
                  {lectureId ? <Link className="btn" to={`/lossmap/${lectureId}`}>Loss map</Link> : null}
                  <Link className="btn btn-plain" to={`/notes/${sessionId}`}>Notes</Link>
                </div>
              </div>
            ) : card.kind === "question" && card.question ? (
              <div className="stack">
                <div className="question">
                  <Dissolve text={card.question.question} active={phase === "dissolving"} />
                </div>
                <div className="options">
                  {card.question.options.map((o, i) => {
                    let cls = "";
                    if (correctIdx !== null) {
                      if (i === correctIdx) cls = " correct";
                      else if (i === chosen) cls = " wrong";
                    }
                    const disabled = phase !== "answering";
                    return (
                      <div
                        key={i}
                        role="button"
                        tabIndex={disabled ? -1 : 0}
                        aria-disabled={disabled}
                        className={"group-row" + (disabled ? "" : " clickable") + cls}
                        onClick={() => !disabled && void answer(i)}
                        onKeyDown={(e) => e.key === "Enter" && !disabled && void answer(i)}
                      >
                        <span className="kbd">{i + 1}</span>
                        <span className="txt">
                          <Dissolve text={o} active={phase === "dissolving"} />
                        </span>
                      </div>
                    );
                  })}
                </div>
                {outcome ? (
                  <div className="t-subhead">
                    <span className={"outcome " + outcome}>{outcome === "hit" ? "Hit." : outcome === "miss" ? "Miss. Re-teaching in another form…" : "Focus drop. Switching form…"}</span>{" "}
                    {outcome !== "drop" && explanation ? <span className="label-2">{explanation}</span> : null}
                    {credited ? <span className="label-3"> · scored form: {FORM_LABEL[credited as keyof typeof FORM_LABEL] ?? credited}</span> : null}
                  </div>
                ) : (
                  <div className="t-footnote label-2">
                    Press <span className="kbd">1</span> to <span className="kbd">4</span>. <span className="kbd">D</span> simulates a focus drop on this card.
                  </div>
                )}
              </div>
            ) : card.kind === "reteach" && card.reteach ? (
              <div className="reteach">
                <div className="group-header" style={{ padding: 0 }}>Re-taught as {FORM_LABEL[card.reteach.form]}</div>
                <ReteachBody card={card} step={step} />
                <div className="row">
                  {sketch && step < nSteps - 1 ? (
                    <button className="btn" onClick={() => setStep((s) => s + 1)}>
                      Next step ({step + 1}/{nSteps}) <span className="kbd">space</span>
                    </button>
                  ) : null}
                  <button className="btn btn-primary" onClick={() => void advance()}>
                    Continue to the question
                  </button>
                  <span className="t-footnote label-2">
                    <span className="kbd">D</span> simulates a focus drop
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className="inspector">
          <TallyPanel tally={tally} compact />
          {card ? (
            <Group title="This gap">
              <Row label="forms used">
                <span>{card.forms_used.length ? card.forms_used.map((f) => FORM_LABEL[f]).join(", ") : "none yet"}</span>
              </Row>
            </Group>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ReteachBody({ card, step }: { card: Card; step: number }) {
  const r = card.reteach!;
  const c = r.content;
  if (c === null || c === undefined) return <div className="label-2">no content for this form</div>;
  if (r.form === "keyterm" && typeof c === "object" && "term" in c) {
    const k = c as KeyTermContent;
    return (
      <>
        <div className="kt-term">{k.term}</div>
        <div className="prose">{k.definition}</div>
        <div className="prose label-2">Example: {k.example}</div>
      </>
    );
  }
  if (r.form === "sketch" && typeof c === "object" && "diagram" in c) {
    const s = c as SketchContent;
    const cap = s.diagram.steps[Math.min(step, s.diagram.steps.length - 1)]?.caption ?? "";
    return (
      <>
        <div className="sketch-line">{s.line}</div>
        <div className="diagram-card">
          <Diagram graph={s.diagram} step={step} />
        </div>
        <div className="caption" key={step}>
          {cap}
        </div>
      </>
    );
  }
  return <div className="prose">{typeof c === "string" ? c : JSON.stringify(c)}</div>;
}
