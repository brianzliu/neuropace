import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { GuideContext, useGuidedStep, type GuideStepContext, type MissDetail, type ReviewMode } from "../lib/guide";
import type { FocusMsg, HeadsetStatus } from "../lib/types";
import ExplainDeck from "./ExplainDeck";
import OfficeHours from "../views/OfficeHours";
import "./review-workspace.css";

/** One workspace, two teaching tools. Mood is self-reported; EEG never diagnoses it. */
export default function ReviewWorkspace() {
  const { sessionId = "" } = useParams();
  const guide = useGuidedStep();
  const guideRef = useRef(guide); guideRef.current = guide;
  const [view, setView] = useState<"practice" | "board">("practice");
  const [mood, setMood] = useState("ready");
  const [learnerId, setLearnerId] = useState("");
  const [officeId, setOfficeId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [, setSignal] = useState("Waiting for headset");
  const creating = useRef(false);
  const alive = useRef(true);
  const officeRef = useRef<string | null>(null);
  const driftHandled = useRef(false);
  const lastMissRef = useRef<MissDetail | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  const openBoard = useCallback(async () => {
    setView("board");
    if (officeRef.current || creating.current) return;
    creating.current = true; setLoading(true); setError("");
    try {
      const notes = await api.notes(sessionId);
      const target = notes.gaps.find(g => g.id === guideRef.current?.decision.target_gap_id) ?? notes.gaps.find(g => g.status === "open");
      const office = await api.officeHoursOpen(sessionId);
      if (!alive.current) return;
      officeRef.current = office.id;
      const miss = lastMissRef.current;
      setPrompt(
        miss
          ? `I just got this question wrong: "${miss.question}" — I answered "${miss.chosenText}" but the correct answer was "${miss.correctText}" (${miss.explanation}). Explain why on the board, one idea at a time, then check my understanding with one short question.`
          : target
            ? `Help me understand this saved lecture moment. Explain one idea using the board, then ask one short question. Lecture excerpt: ${target.span_text}`
            : "Explain one main idea from this lecture on the board, then ask one short question.",
      );
      setOfficeId(office.id);
    } catch (e) { if (alive.current) setError(errorText(e)); }
    finally { creating.current = false; if (alive.current) setLoading(false); }
  }, [sessionId]);
  const recommend = useCallback(async (currentMode: ReviewMode, useBoardOnError = false) => {
    if (!learnerId) return;
    try {
      const result = await api.reviewRecommendation(sessionId, {
        learner_id: learnerId,
        current_mode: currentMode,
        conversation_session_id: officeRef.current,
      });
      if (!alive.current) return;
      if (result.mode === "whiteboard") await openBoard();
      else { driftHandled.current = false; setView("practice"); }
    } catch (e) {
      if (!alive.current) return;
      if (useBoardOnError) await openBoard();
      else setError(errorText(e));
    }
  }, [learnerId, openBoard, sessionId]);
  useEffect(() => {
    api.session(sessionId).then(session => setLearnerId(session.learner_id)).catch(e => setError(errorText(e)));
  }, [sessionId]);
  useEffect(() => {
    if (learnerId) void recommend("practice");
  }, [learnerId, recommend]);
  const reportOutcome = useCallback<GuideStepContext["reportOutcome"]>((outcome, missDetail) => {
    guideRef.current?.reportOutcome(outcome);
    if (outcome === "miss" || outcome === "drop") {
      lastMissRef.current = outcome === "miss" ? missDetail ?? null : null;
      void recommend("practice", true);
    }
  }, [recommend]);
  const onSignal = useCallback((headset: HeadsetStatus | null, frame: FocusMsg | null) => {
    const simulated = !!headset && (headset.kind !== "real" || !!headset.simulated || !!frame?.sim);
    setSignal(simulated ? "Simulated EEG · not used to adapt" : headset?.connected ? "EEG connected" : "No live EEG · your answers guide review");
    if (headset?.kind === "real" && headset.connected && !simulated && frame?.quality === "good" && frame.baseline_ready && !frame.artifact && !frame.paused && frame.state === "drop") {
      if (!driftHandled.current) {
        driftHandled.current = true;
        void openBoard();
      }
    }
  }, [openBoard]);
  const paused = !!guide?.paused;
  return <section className="review-workspace">
    <div className="review-workspace-tools">
      <fieldset className="review-mood"><legend>How is it going?</legend><div>
        {[["ready", "Ready to try", "mood-ready"], ["tired", "Need a breather", "mood-tired"], ["stuck", "I'm stuck", "mood-stuck"]].map(([value, label, tier]) => <button type="button" key={value} aria-pressed={mood === value} className={tier + (mood === value ? " selected" : "")} onClick={() => {
          setMood(value);
          if (value === "stuck") void openBoard();
          if (value === "ready") { driftHandled.current = false; setView("practice"); }
        }}>{label}</button>)}
        <button type="button" className="mood-draw" onClick={() => {
          if (view === "practice") void openBoard();
          else { driftHandled.current = false; setView("practice"); }
        }}>{view === "practice" ? "Draw this out" : "Try a question"}</button>
      </div></fieldset>
    </div>
    <div hidden={view !== "practice"}>
      {guide ? <GuideContext.Provider value={{ ...guide, reportOutcome }}><ExplainDeck active={view === "practice" && !paused} onFocusState={onSignal} /></GuideContext.Provider> : <ExplainDeck active={view === "practice"} onFocusState={onSignal} />}
    </div>
    {view === "board" && <div className="review-board-pane">
      {loading && <p role="status">Opening your whiteboard…</p>}
      {error && <div className="callout danger">{error}<button className="btn" onClick={() => void openBoard()}>Try again</button></div>}
      {officeId && <OfficeHours sessionId={officeId} original={sessionId} openingPrompt={prompt} paused={paused} onTurnComplete={() => void recommend("whiteboard")} />}
    </div>}
  </section>;
}
