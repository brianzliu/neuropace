import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { readLocalSetting } from "../lib/storage";
import type { Devices, LectureFull, SessionPublic } from "../lib/types";

/** Main's direct recording flow in the separate Pocket Studio window. */
export default function Setup() {
  const navigate = useNavigate();
  const [practice, setPractice] = useState<LectureFull | null>(null);
  const [running, setRunning] = useState<SessionPublic | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [devices, setDevices] = useState<Devices | null>(null);
  // the headset is often switched on after this screen opens: ask every few seconds, cheaply
  useEffect(() => {
    let alive = true;
    const load = () => api.devices().then((d) => alive && setDevices(d)).catch(() => undefined);
    void load();
    const id = window.setInterval(load, 4000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  const statusLine = !devices
    ? ""
    : [
        devices.headset.kind === "real" ? "Headset connected." : "Turn your headset on before you start; without one, focus is simulated for practice.",
        devices.totem.kind === "real" ? "Pad connected." : "Press Space whenever you want a catch-up.",
      ].join(" ");
  useEffect(() => {
    let alive = true;
    const learnerId = readLocalSetting("learner") || "me";
    Promise.allSettled([api.lectures(), api.learner(learnerId).then(l => api.sessions({learner_id: l.id}))]).then(([lectures, sessions]) => {
      if (!alive) return;
      if (lectures.status === "fulfilled") setPractice(lectures.value.lectures.find(l => l.kind === "scripted") ?? null);
      if (sessions.status === "fulfilled") setRunning(sessions.value.sessions.find(s => s.status === "running" && s.mode !== "review" && s.mode !== "office_hours") ?? null);
    });
    return () => { alive = false; };
  }, []);
  const start = async (lectureId: string | null) => {
    setBusy(true); setError("");
    try {
      const learnerId = readLocalSetting("learner") || undefined;
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
    {statusLine ? <p className={"small" + (devices?.headset.kind === "real" ? " ok-text" : " muted")}>{statusLine}</p> : null}
    {practice && !running && <button className="linklike" disabled={busy} onClick={() => void start(practice.id)}>Try a practice lecture</button>}
    <Link className="advanced-link" to="/session/advanced">Devices and session options</Link>
  </section>;
}
