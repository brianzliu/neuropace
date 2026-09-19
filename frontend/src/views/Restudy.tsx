import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { ARTIFACT_LABEL, FORM_ICON, FORM_LABEL, FORMS, type Card, type Progress, type TallySummary } from "../lib/types";
import { flash } from "../lib/flash";
import { useFocusSession } from "../lib/focusSession";
import Dissolve from "../components/Dissolve";
import ArtifactView from "../components/ArtifactView";
import BrainWaves from "../components/BrainWaves";

type Phase = "idle" | "answering" | "feedback" | "dissolving" | "reteach" | "done" | "blocked";

/** Restudy, as a lesson (docs/PRODUCT.md §6): one card at a time, question first, a different explanation on a miss,
 * three in a row to finish. With a headset on, focus is measured per explanation and a drift switches it early. */
export default function Restudy() {
  const { sessionId = "" } = useParams();
  const [card, setCard] = useState<Card | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [tally, setTally] = useState<TallySummary | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [err, setErr] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [correctIdx, setCorrectIdx] = useState<number | null>(null);
  const [explanation, setExplanation] = useState("");
  const [outcome, setOutcome] = useState<"hit" | "miss" | "drop" | null>(null);
  const [step, setStep] = useState(0);
  const [nSteps, setNSteps] = useState(1);
  const [lectureTitle, setLectureTitle] = useState<string>("");
  const [hits, setHits] = useState(0);
  const pendingNext = useRef<Card | null>(null);
  const busy = useRef(false);
  const focus = useFocusSession(true);
  const focusRef = useRef(focus);
  focusRef.current = focus;

  const applyNext = useCallback(
    (next: Card | null, done: boolean) => {
      setChosen(null);
      setCorrectIdx(null);
      setOutcome(null);
      setStep(0);
      setNSteps(1);
      if (done || !next) {
        setCard(null);
        setPhase("done");
        return;
      }
      setCard(next);
      setPhase(next.kind === "question" ? "answering" : "reteach");
      focusRef.current.startCard();
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const sess = await api.session(sessionId);
        if (sess.lecture_id) {
          api.lecture(sess.lecture_id).then((l) => !cancelled && setLectureTitle(l.title)).catch(() => undefined);
        }
        const st = await api.reviewStart(sessionId);
        if (cancelled) return;
        setProgress(st.progress);
        setTally(st.tally);
        applyNext(st.card, st.progress.done);
      } catch (e) {
        const text = errorText(e);
        if (/not ready|no generated notes|end the session/i.test(text)) {
          setBlocked(text);
          setPhase("blocked");
        } else {
          setErr(text);
        }
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
        const r = await api.reviewAnswer(sessionId, card.id, choice, focusRef.current.endCard());
        setCorrectIdx(r.correct_index);
        setExplanation(r.explanation);
        setOutcome(r.outcome);
        setProgress(r.progress);
        setTally(r.tally);
        if (r.outcome === "hit") setHits((h) => h + 1);
        setPhase("feedback");
        pendingNext.current = r.next;
        const done = r.done;
        window.setTimeout(
          () => {
            if (r.outcome === "miss" && r.next && r.next.kind === "reteach") {
              setPhase("dissolving");
              window.setTimeout(() => applyNext(pendingNext.current, done), 750);
            } else {
              applyNext(pendingNext.current, done);
            }
          },
          r.outcome === "hit" ? 1300 : 1700,
        );
      } catch (e) {
        setErr(errorText(e));
      } finally {
        busy.current = false;
      }
    },
    [card, phase, sessionId, applyNext],
  );

  const drop = useCallback(
    async (simulated: boolean) => {
      if (!card || busy.current || (phase !== "answering" && phase !== "reteach")) return;
      busy.current = true;
      if (simulated) flash("SIMULATED DRIFT");
      try {
        const r = await api.reviewDrop(sessionId, card.id, focusRef.current.endCard());
        setOutcome("drop");
        setProgress(r.progress);
        setTally(r.tally);
        setPhase("feedback");
        const nxt = r.next;
        const done = r.done;
        window.setTimeout(() => {
          setPhase("dissolving");
          window.setTimeout(() => applyNext(nxt, done), 750);
        }, 1200);
      } catch (e) {
        setErr(errorText(e));
      } finally {
        busy.current = false;
      }
    },
    [card, phase, sessionId, applyNext],
  );

  // a real drift on an explanation switches it early (only after the card had a moment to land)
  const driftSeen = useRef(0);
  useEffect(() => {
    if (focus.driftSeq === driftSeen.current) return;
    driftSeen.current = focus.driftSeq;
    if (phase === "reteach" && card) void drop(false);
  }, [focus.driftSeq, phase, card, drop]);

  const advance = useCallback(async () => {
    if (!card || card.kind !== "reteach" || busy.current) return;
    busy.current = true;
    try {
      const r = await api.reviewAdvance(sessionId, card.id, focusRef.current.endCard());
      setProgress(r.progress);
      setTally(r.tally);
      applyNext(r.next, r.done);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      busy.current = false;
    }
  }, [card, sessionId, applyNext]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const k = ev.key;
      if (phase === "answering" && ["1", "2", "3", "4"].includes(k)) void answer(Number(k) - 1);
      else if (k.toLowerCase() === "d") void drop(true);
      else if (phase === "reteach" && (k === " " || k === "ArrowRight" || k === "Enter")) {
        ev.preventDefault();
        if (step < nSteps - 1) setStep((s) => s + 1);
        else void advance();
      } else return;
      ev.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, answer, drop, advance, step, nSteps]);

  const onSteps = useCallback((n: number) => setNSteps(Math.max(1, n)), []);
  const pct = useMemo(() => {
    if (!progress) return 0;
    const total = Math.max(1, progress.gaps_total);
    return Math.round(((progress.gaps_closed + progress.gaps_exhausted) / total) * 100);
  }, [progress]);
  const headsetOn = !!focus.headset?.connected;

  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (phase === "blocked") {
    return (
      <div className="page narrow">
        <div className="complete">
          <div className="t-title1">Not quite ready</div>
          <p className="sub">{blocked}</p>
          <Link className="btn btn-blue" to={`/lecture/${sessionId}`}>
            Back to the lecture
          </Link>
        </div>
      </div>
    );
  }
  if (!progress || !tally) return <div className="page narrow"><div className="loading">Getting your moments ready…</div></div>;

  return (
    <div className="page">
      <div className="lesson-top">
        <Link className="btn btn-plain btn-sm" to={`/lecture/${sessionId}`} title="Back to the lecture">
          ✕
        </Link>
        <div className="progress" title={`${progress.gaps_closed} of ${progress.gaps_total} moments done`}>
          <i style={{ width: `${pct}%` }} />
        </div>
        <span className="streak" title="three in a row finishes the lesson">
          {progress.streak}/{progress.stop_streak} in a row
        </span>
      </div>

      <div className="lesson">
        <div className="stack">
          {lectureTitle ? <div className="eyebrow">{lectureTitle}</div> : null}
          <div className="lesson-card">
            {phase === "done" || !card ? (
              <div className="complete">
                <div className="big-mark">✓</div>
                <h2 className="t-title1">{progress.streak >= progress.stop_streak ? "Three in a row. Lesson done." : "Every moment covered."}</h2>
                <div className="stats">
                  <div className="stat green">
                    <div className="v">{progress.gaps_closed}</div>
                    <div className="k">moments landed</div>
                  </div>
                  <div className="stat">
                    <div className="v">{hits}</div>
                    <div className="k">right answers</div>
                  </div>
                  <div className="stat orange">
                    <div className="v">{progress.gaps_exhausted}</div>
                    <div className="k">still tricky</div>
                  </div>
                </div>
                <WhatWorked tally={tally} />
                <div className="row">
                  <Link className="btn btn-primary btn-lg" to="/lectures">
                    Back to lectures
                  </Link>
                  <Link className="btn btn-plain" to="/you">
                    What works for you
                  </Link>
                </div>
              </div>
            ) : card.kind === "question" && card.question ? (
              <>
                <div className="eyebrow">Moment {card.gap_ord + 1} · quick check</div>
                <div className="question">
                  <Dissolve text={card.question.question} active={phase === "dissolving"} />
                </div>
                <div className="options">
                  {card.question.options.map((o, i) => {
                    let cls = "option";
                    if (correctIdx !== null) {
                      if (i === correctIdx) cls += " correct";
                      else if (i === chosen) cls += " wrong";
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
                  <div className={"feedback " + outcome}>
                    <div>
                      <div className="fb-title">{outcome === "hit" ? "That's it." : outcome === "miss" ? "Not yet. Let's try it another way." : "You drifted. Let's try it another way."}</div>
                      {outcome !== "drop" && explanation ? <div className="fb-body">{explanation}</div> : null}
                    </div>
                  </div>
                ) : (
                  <div className="label-2 t-footnote">
                    Press <kbd className="kbd">1</kbd> to <kbd className="kbd">4</kbd>
                  </div>
                )}
              </>
            ) : card.kind === "reteach" && card.reteach ? (
              <div className="reteach">
                <div className="row between">
                  <span className="artifact-kind">
                    <span className="family-icon">{FORM_ICON[card.reteach.form]}</span>
                    {FORM_LABEL[card.reteach.form]}
                    {ARTIFACT_LABEL[card.reteach.artifact] !== FORM_LABEL[card.reteach.form] ? ` · ${ARTIFACT_LABEL[card.reteach.artifact]}` : ""}
                  </span>
                  {card.reteach.key_term ? <span className="badge accent">{card.reteach.key_term}</span> : null}
                </div>
                <ArtifactView kind={card.reteach.artifact} content={card.reteach.content} step={step} onSteps={onSteps} />
                {outcome === "drop" ? (
                  <div className="feedback drop">
                    <div className="fb-title">You drifted. Switching to another way.</div>
                  </div>
                ) : null}
                <div className="row">
                  {step < nSteps - 1 ? (
                    <button className="btn btn-blue" onClick={() => setStep((s) => s + 1)}>
                      Next ({step + 1}/{nSteps}) <span className="kbd">space</span>
                    </button>
                  ) : (
                    <button className="btn btn-primary" onClick={() => void advance()}>
                      Got it, ask me <span className="kbd">space</span>
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <aside className="lesson-side">
          <BrainWaves samples={focus.raw} bands={focus.bands} connected={headsetOn} compact label="Your focus" />
          <div className="card">
            <div className="card-header">
              <span className="card-title">What works for you</span>
            </div>
            <FamilyList tally={tally} />
            {!tally.enough_data ? <div className="t-footnote label-2" style={{ marginTop: 8 }}>Still learning: {tally.total_attempts} of {tally.needed_attempts} answers.</div> : null}
          </div>
          {!headsetOn ? <div className="t-footnote label-2">Put the headset on to measure how each explanation holds your attention.</div> : null}
          <div className="t-footnote label-3">
            <kbd className="kbd">D</kbd> simulates a drift (team)
          </div>
        </aside>
      </div>
    </div>
  );
}

export function FamilyList({ tally }: { tally: TallySummary }) {
  return (
    <div className="family-list">
      {FORMS.map((f) => {
        const st = tally.forms[f];
        return (
          <div key={f} className={"family" + (tally.pick === f ? " pick" : "")}>
            <span className="f-icon">{FORM_ICON[f]}</span>
            <span>
              <div className="f-name">{FORM_LABEL[f]}</div>
              <div className="f-sub">{st.attempts ? `${st.rescues} of ${st.attempts} rescues` : "not tried yet"}{st.focus?.mean_focus != null ? ` · held ${Math.round(st.focus.mean_focus * 100)}%` : ""}</div>
            </span>
            <span className="f-num">{tally.pick === f ? "next" : ""}</span>
          </div>
        );
      })}
    </div>
  );
}

function WhatWorked({ tally }: { tally: TallySummary }) {
  const best = [...FORMS].sort((a, b) => tally.forms[b].rescues - tally.forms[a].rescues)[0];
  const st = tally.forms[best];
  if (!st || st.rescues === 0) return <p className="sub">Reflow is still learning which explanations land for you.</p>;
  return (
    <p className="sub">
      {FORM_LABEL[best]} rescued you {st.rescues} time{st.rescues === 1 ? "" : "s"}. That is what you will see first next time.
    </p>
  );
}
