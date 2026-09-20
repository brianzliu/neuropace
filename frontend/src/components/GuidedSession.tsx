import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { GuideContext, type GuideAction, type GuideDecision, type GuideGoal, type GuideRequest } from "../lib/guide";
import Lecture from "../views/Lecture";
import Replay from "../views/Replay";
import ReviewWorkspace from "./ReviewWorkspace";
import Quiz from "../views/Quiz";
import "./guided-session.css";

const TITLES: Record<GuideAction, string> = { notes: "Get the idea", replay: "Revisit the moment", review: "Try it out", quiz: "Check what stuck", complete: "A good stopping point" };
const GOALS: { id: GuideGoal; title: string; detail: string }[] = [
  { id: "understand", title: "Make it click", detail: "Work through something that felt unclear." },
  { id: "practice", title: "Put it into practice", detail: "Try a question and learn from the answer." },
  { id: "recall", title: "See what stuck", detail: "Check what you remember from this lecture." },
];

/** A bounded learner-controlled sequence. A step never advances while someone is reading. */
export default function GuidedSession({ sessionId, learnerId }: { sessionId: string; learnerId: string }) {
  const [goal, setGoal] = useState<GuideGoal>("understand");
  const [minutes, setMinutes] = useState(10);
  const [started, setStarted] = useState(false);
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [decision, setDecision] = useState<GuideDecision | null>(null);
  const [completed, setCompleted] = useState<GuideAction[]>([]);
  const [outcome, setOutcome] = useState<GuideRequest["last_outcome"]>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(0);
  const locked = useRef(false);
  const finished = decision?.action === "complete" || decision?.done || elapsed >= minutes * 60;
  useEffect(() => () => { requestRef.current++; }, []);
  useEffect(() => {
    if (!started || paused || finished) return;
    const timer = window.setInterval(() => setElapsed(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [started, paused, finished]);
  const reportOutcome = useCallback((value: NonNullable<GuideRequest["last_outcome"]>) => setOutcome(value), []);
  const next = async (skip = false) => {
    if (locked.current) return;
    locked.current = true;
    setBusy(true); setError("");
    const token = ++requestRef.current;
    const steps = decision && decision.action !== "complete" ? [...completed, decision.action].slice(-24) : completed;
    try {
      const result = await api.guideNext(sessionId, {
        learner_id: learnerId, goal, current_step: decision?.action ?? null, completed_steps: steps,
        elapsed_seconds: elapsed, time_limit_seconds: minutes * 60,
        last_outcome: skip ? "drop" : outcome ?? (decision ? "read" : null),
      });
      if (token !== requestRef.current) return;
      if (!(result.action in TITLES)) throw new Error("The next step was not recognized. Please try again.");
      setCompleted(steps); setDecision(result); setOutcome(null); setStarted(true);
    } catch (e) { if (token === requestRef.current) setError(errorText(e)); }
    finally { if (token === requestRef.current) { locked.current = false; setBusy(false); } }
  };
  const restart = () => {
    requestRef.current++; locked.current = false; setBusy(false); setStarted(false); setDecision(null);
    setCompleted([]); setOutcome(null); setElapsed(0); setPaused(false); setError("");
  };
  if (!started) return <section className="guide-start">
    <h2>What would help today?</h2>
    <div className="guide-goals" role="group" aria-label="Study goal">
      {GOALS.map(item => <button key={item.id} className={`guide-goal${goal === item.id ? " selected" : ""}`} aria-pressed={goal === item.id} onClick={() => setGoal(item.id)} disabled={busy}>
        <span>{item.title}</span><small>{item.detail}</small>
      </button>)}
    </div>
    <div className="guide-start-footer">
      <fieldset className="guide-duration"><legend>Time for this session</legend><div className="guide-time-options">
        {[5, 10, 20].map(n => <button type="button" key={n} className={minutes === n ? "selected" : ""} aria-pressed={minutes === n} disabled={busy} onClick={() => setMinutes(n)}>{n} min</button>)}
      </div></fieldset>
      <button className="btn btn-primary btn-lg" disabled={busy} onClick={() => void next()}>{busy ? "Finding a starting point…" : "Let's begin"}</button>
    </div>
    {error && <p className="error-text" role="alert">{error} <button className="linklike" onClick={() => void next()}>Try again</button></p>}
  </section>;
  if (finished) return <section className="guide-complete">
    <span className="guide-check" aria-hidden="true">✓</span><h2>A good stopping point</h2>
    <p>{elapsed >= minutes * 60 ? "That's the time you set aside. Your submitted answers are saved." : decision?.reason}</p>
    <p>{completed.length} step{completed.length === 1 ? "" : "s"} explored. You can return whenever you need.</p>
    <div className="row"><Link className="btn btn-primary" to="/">Back to dashboard</Link><button className="btn" onClick={restart}>Choose another goal</button></div>
  </section>;
  const remaining = Math.max(0, minutes * 60 - elapsed);
  return <section className="guided-session">
    <header className="guide-current">
      <div><h2>{decision ? TITLES[decision.action] : "Getting ready"}</h2><p>{decision?.reason}</p></div>
      <div className="guide-time"><span>{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")} left</span><button className="btn btn-sm" onClick={() => setPaused(v => !v)}>{paused ? "Resume" : "Pause"}</button></div>
    </header>
    {paused && <p role="status">Your study timer is paused.</p>}
    {decision && <GuideContext.Provider value={{ decision, reportOutcome, paused }}>
      <div className="guide-step" key={`${completed.length}-${decision.action}`}>
        {decision.action === "notes" ? <Lecture /> : decision.action === "replay" ? <Replay /> : decision.action === "review" ? <ReviewWorkspace /> : decision.action === "quiz" ? <Quiz /> : null}
      </div>
    </GuideContext.Provider>}
    {error && <p className="error-text" role="alert">{error}</p>}
    <footer className="guide-controls">
      <button className="btn btn-plain" disabled={busy} onClick={() => setDecision({ action: "complete", reason: "Your submitted answers are saved. Pick this up again whenever you're ready." })}>Finish for now</button>
      <div className="row"><button className="btn" disabled={busy || paused} onClick={() => void next(true)}>Try another way</button><button className="btn btn-primary" disabled={busy || paused} onClick={() => void next()}>{busy ? "Finding your next step…" : outcome ? "Continue" : "I'm ready to continue"}</button></div>
    </footer>
  </section>;
}
