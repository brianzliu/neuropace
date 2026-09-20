import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { GuideContext, useGuidedStep, type GuideStepContext } from "../lib/guide";
import type { FocusMsg, HeadsetStatus } from "../lib/types";
import Restudy from "../views/Restudy";
import OfficeHours from "../views/OfficeHours";
import "./review-workspace.css";

/** One workspace, two teaching tools. Mood is self-reported; EEG never diagnoses it. */
export default function ReviewWorkspace() {
  const { sessionId = "" } = useParams();
  const guide = useGuidedStep();
  const guideRef = useRef(guide); guideRef.current = guide;
  const [view, setView] = useState<"practice" | "board">("practice");
  const [mood, setMood] = useState("ready");
  const [reason, setReason] = useState("");
  const [officeId, setOfficeId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [signal, setSignal] = useState("Waiting for headset");
  const [suggestBoard, setSuggestBoard] = useState(false);
  const creating = useRef(false);
  const alive = useRef(true);
  const officeRef = useRef<string | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (officeRef.current) void api.endSession(officeRef.current).catch(() => undefined);
    };
  }, []);
  const openBoard = useCallback(async (why: string) => {
    setView("board"); setReason(why); setSuggestBoard(false);
    if (officeRef.current || creating.current) return;
    creating.current = true; setLoading(true); setError("");
    try {
      const notes = await api.notes(sessionId);
      const target = notes.gaps.find(g => g.id === guideRef.current?.decision.target_gap_id) ?? notes.gaps.find(g => g.status === "open");
      const office = await api.createSession({ mode: "office_hours", learner_id: notes.session.learner_id, lecture_id: notes.session.lecture_id });
      if (!alive.current) { void api.endSession(office.id); return; }
      officeRef.current = office.id;
      setPrompt(target ? `Help me understand this saved lecture moment. Explain one idea using the board, then ask one short question. Lecture excerpt: ${target.span_text}` : "Explain one main idea from this lecture on the board, then ask one short question.");
      setOfficeId(office.id);
    } catch (e) { if (alive.current) setError(errorText(e)); }
    finally { creating.current = false; if (alive.current) setLoading(false); }
  }, [sessionId]);
  const reportOutcome = useCallback<GuideStepContext["reportOutcome"]>((outcome) => {
    guideRef.current?.reportOutcome(outcome);
    if (outcome === "miss" || outcome === "drop") {
      setSuggestBoard(true);
      setReason(outcome === "miss" ? "That answer needs another look. We can draw it out together." : "Try a different explanation when you're ready.");
    } else if (outcome === "hit") setReason("That answer was right. Keep the explanation nearby if you need it.");
  }, []);
  const onSignal = useCallback((headset: HeadsetStatus | null, frame: FocusMsg | null) => {
    const simulated = !!headset && (headset.kind !== "real" || !!headset.simulated || !!frame?.sim);
    setSignal(simulated ? "Simulated EEG · not used to adapt" : headset?.connected ? "EEG connected" : "No live EEG · your answers guide review");
    if (headset?.kind === "real" && headset.connected && !simulated && frame?.quality === "good" && frame.baseline_ready && !frame.artifact && !frame.paused && frame.state === "drop") {
      setSuggestBoard(true); setReason("Your focus signal changed. A drawn explanation is available if it would help.");
    }
  }, []);
  const paused = !!guide?.paused;
  return <section className="review-workspace">
    <div className="review-workspace-tools">
      <div className="segmented" role="group" aria-label="Review activity">
        <button className={view === "practice" ? "is-active" : ""} onClick={() => setView("practice")}>Try a question</button>
        <button className={view === "board" ? "is-active" : ""} onClick={() => void openBoard("Let's work through this idea together.")}>Draw it out</button>
      </div>
      <label>How is it going?<select value={mood} onChange={e => {
        setMood(e.target.value);
        if (e.target.value === "stuck") void openBoard("You said you're stuck. Let's take it one idea at a time.");
        if (e.target.value === "ready") setView("practice");
        if (e.target.value === "tired") setReason("Keep this short, or use Pause above to take a break.");
      }}><option value="ready">Ready to try</option><option value="stuck">I'm stuck</option><option value="tired">Need a breather</option></select></label>
    </div>
    <p className="review-signal">{signal}</p>
    {reason && <div className="review-adaptation" role="status"><span>{reason}</span>{suggestBoard && <button className="btn btn-sm" onClick={() => void openBoard(reason)}>Show me another way</button>}</div>}
    <div hidden={view !== "practice"}>
      {guide ? <GuideContext.Provider value={{ ...guide, reportOutcome }}><Restudy workspaceActive={view === "practice" && !paused} onFocusState={onSignal} /></GuideContext.Provider> : <Restudy />}
    </div>
    {view === "board" && <div className="review-board-pane">
      {loading && <p role="status">Opening your whiteboard…</p>}
      {error && <div className="callout danger">{error}<button className="btn" onClick={() => void openBoard(reason)}>Try again</button></div>}
      {officeId && <OfficeHours embeddedSessionId={officeId} originalSessionId={sessionId} openingPrompt={prompt} embedded paused={paused} />}
    </div>}
  </section>;
}
