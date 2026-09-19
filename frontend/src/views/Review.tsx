import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { FORM_LABEL, type Card, type KeyTermContent, type Progress, type SketchContent, type TallySummary } from "../lib/types";
import { range } from "../lib/format";
import { useSimBadge } from "../lib/useSimBadge";
import { SimFlash, SourceBadge } from "../components/Badges";
import Dissolve from "../components/Dissolve";
import Diagram from "../components/Diagram";
import TallyPanel from "../components/TallyPanel";
import { LibraryFrame, useLibrary } from "./Library";

type Phase = "idle" | "answering" | "feedback" | "dissolving" | "reteach" | "done";

export default function Review() {
  const { sessionId = "" } = useParams();
  const library = useLibrary();
  if (library) return <ReviewSession sessionId={library.sessionId} />;
  return (
    <LibraryFrame sessionId={sessionId} tab="review">
      <ReviewSession sessionId={sessionId} />
    </LibraryFrame>
  );
}

function ReviewSession({ sessionId }: { sessionId: string }) {
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
  const sim = useSimBadge();
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
        setErr(String(e));
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
    sim.flash("SIMULATED FOCUS DROP");
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
  }, [card, phase, sessionId, sim, applyNext]);

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

  if (err) return <div className="panel error">{err}</div>;
  if (!progress || !tally) return <div className="panel muted">preparing review…</div>;

  return (
    <div className="review">
      <SimFlash visible={sim.visible} label={sim.label} />
      <div className="col">
        <div className="progress-line">
          <span>
            gaps closed {progress.gaps_closed}/{progress.gaps_total}
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
        <div className="panel card">
          {phase === "done" || !card ? (
            <div className="done-screen">
              <h2>Review done</h2>
              <div className="muted">
                {progress.streak >= progress.stop_streak ? `${progress.stop_streak} straight hits.` : "Every gap is closed or exhausted."} {progress.gaps_closed}/{progress.gaps_total} gaps closed.
              </div>
              <div className="row">
                <Link to="/">Back to Dashboard — your review queue is updated</Link>
                {learnerId ? <Link to={`/tally/${learnerId}`}>your tally</Link> : null}
                {lectureId ? <Link to={`/lossmap/${lectureId}`}>lecture loss map</Link> : null}
              </div>
            </div>
          ) : card.kind === "question" && card.question ? (
            <>
              <div className="q">
                <Dissolve text={card.question.question} active={phase === "dissolving"} />
              </div>
              <div className="options">
                {card.question.options.map((o, i) => {
                  let cls = "";
                  if (correctIdx !== null) {
                    if (i === correctIdx) cls = "correct";
                    else if (i === chosen) cls = "wrong";
                  }
                  return (
                    <button key={i} className={cls} disabled={phase !== "answering"} onClick={() => void answer(i)}>
                      <span className="k">{i + 1}</span>
                      <Dissolve text={o} active={phase === "dissolving"} />
                    </button>
                  );
                })}
              </div>
              {outcome ? (
                <div>
                  <span className={"outcome " + outcome}>{outcome === "hit" ? "Hit." : outcome === "miss" ? "Miss. Re-teaching in another form…" : "Focus drop. Switching form…"}</span>{" "}
                  {outcome !== "drop" && explanation ? <span className="muted">{explanation}</span> : null}
                  {credited ? <span className="dim small"> · scored form: {FORM_LABEL[credited as keyof typeof FORM_LABEL] ?? credited}</span> : null}
                </div>
              ) : (
                <div className="dim small">press 1 to 4 · D simulates a focus drop on this card</div>
              )}
            </>
          ) : card.kind === "reteach" && card.reteach ? (
            <div className="reteach">
              <div className="form-name">re-taught as: {FORM_LABEL[card.reteach.form]}</div>
              <ReteachBody card={card} step={step} />
              <div className="row">
                {sketch && step < nSteps - 1 ? (
                  <button onClick={() => setStep((s) => s + 1)}>
                    Next step ({step + 1}/{nSteps}) <span className="dim">space</span>
                  </button>
                ) : null}
                <button className="primary" onClick={() => void advance()}>
                  Continue to the question
                </button>
                <span className="dim small">D simulates a focus drop</span>
              </div>
            </div>
          ) : null}
        </div>
      </div>
      <div className="col">
        <TallyPanel tally={tally} compact />
        {card ? (
          <div className="panel small muted">
            forms used on this gap: {card.forms_used.length ? card.forms_used.map((f) => FORM_LABEL[f]).join(", ") : "none yet"}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ReteachBody({ card, step }: { card: Card; step: number }) {
  const r = card.reteach!;
  const c = r.content;
  if (c === null || c === undefined) return <div className="dim">no content for this form</div>;
  if (r.form === "keyterm" && typeof c === "object" && "term" in c) {
    const k = c as KeyTermContent;
    return (
      <>
        <div className="kt-term">{k.term}</div>
        <div>{k.definition}</div>
        <div className="muted">Example: {k.example}</div>
      </>
    );
  }
  if (r.form === "sketch" && typeof c === "object" && "diagram" in c) {
    const s = c as SketchContent;
    const cap = s.diagram.steps[Math.min(step, s.diagram.steps.length - 1)]?.caption ?? "";
    return (
      <>
        <div className="sketch-line">{s.line}</div>
        <Diagram graph={s.diagram} step={step} />
        <div className="caption" key={step}>
          {cap}
        </div>
      </>
    );
  }
  return <div>{typeof c === "string" ? c : JSON.stringify(c)}</div>;
}
