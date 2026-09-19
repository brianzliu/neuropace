import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { Doctor, LectureFull, SessionPublic } from "../lib/types";

/** Main's direct recording flow in the separate Pocket Studio window. */
export default function Setup() {
  const navigate = useNavigate();
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [practice, setPractice] = useState<LectureFull | null>(null);
  const [running, setRunning] = useState<SessionPublic | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    const learnerId = localStorage.getItem("reflow.learner") || "me";
    Promise.allSettled([api.doctor(), api.lectures(), api.learner(learnerId).then(l => api.sessions({learner_id: l.id}))]).then(([devices, lectures, sessions]) => {
      if (!alive) return;
      if (devices.status === "fulfilled") setDoctor(devices.value);
      if (lectures.status === "fulfilled") setPractice(lectures.value.lectures.find(l => l.kind === "scripted") ?? null);
      if (sessions.status === "fulfilled") setRunning(sessions.value.sessions.find(s => s.status === "running" && s.mode !== "review") ?? null);
    });
    return () => { alive = false; };
  }, []);
  const start = async (lectureId: string | null) => {
    setBusy(true); setError("");
    try {
      const learnerId = localStorage.getItem("reflow.learner") || undefined;
      const session = await api.createSession({learner_id: learnerId, lecture_id: lectureId, mode: "live", headset: "auto", totem: "auto"});
      navigate(`/live/${session.id}`);
    } catch (e) { setError(errorText(e)); setBusy(false); }
  };
  return <section className="quick-start">
    <div className="recording-object" aria-hidden="true"><span /><i /><i /><i /></div>
    <h1>Ready when you are.</h1>
    <p>Record your lecture. Come back to the parts you want to understand.</p>
    {error && <div className="callout danger" role="alert">{error}</div>}
    {running ? <Link className="btn btn-primary btn-lg btn-block" to={`/live/${running.id}`}>Resume session</Link> : <button className="btn btn-primary btn-lg btn-block" disabled={busy} onClick={() => void start(null)}>{busy ? "Starting…" : "Start session"}</button>}
    <p className="small muted">Your microphone starts in the live window. Enable whiteboard capture there when you’re ready.</p>
    {doctor && !doctor.keys.deepgram && <p className="small error">Live recording needs transcription setup. You can use the practice lecture below.</p>}
    {practice && !running && <button className="linklike" disabled={busy} onClick={() => void start(practice.id)}>Try a practice lecture</button>}
    <Link className="advanced-link" to="/session/advanced">Devices and session options</Link>
  </section>;
}
