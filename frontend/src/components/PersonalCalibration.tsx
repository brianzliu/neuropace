import { useState } from "react";
import { api, errorText } from "../lib/api";
import type { HeadsetStatus, StartupCalibration } from "../lib/types";

export default function PersonalCalibration({ sessionId, calibration, headset, connected, ending, onEnd }: {
  sessionId: string;
  calibration: StartupCalibration;
  headset: HeadsetStatus | null;
  connected: boolean;
  ending: boolean;
  onEnd: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const collecting = calibration.status === "collecting";
  const saved = calibration.status === "saved";
  const signal = !connected ? "Connection lost. Reconnecting…" : !headset?.stream?.live
    ? "Waiting for the headset. Check its power and Bluetooth connection."
    : !calibration.clean ? "Adjust the forehead sensor and ear clip. Keep still." : "Clean headset signal.";
  const proceed = async () => {
    setBusy(true); setError("");
    try {
      if (saved) await api.continueCalibration(sessionId);
      else await api.beginCalibration(sessionId);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  return <section className="quick-start" aria-labelledby="calibration-title">
    <p className="small muted">Personal focus calibration</p>
    <h1 id="calibration-title">{saved ? "Calibration saved." : collecting ? "Keep counting silently." : calibration.status === "failed" ? "Let’s try that again." : "30 seconds to find your baseline."}</h1>
    <p>{saved ? "Your focused baseline is ready. Start the lecture when you are ready to record." : "Look at the dot with your eyes open. Count backwards from 300 by threes, silently. Keep your head still."}</p>
    <div aria-hidden="true" style={{ width: 18, height: 18, borderRadius: "50%", background: "currentColor", margin: "48px auto" }} />
    {collecting && <p className="t-title1 mono" aria-label="Seconds remaining">{Math.ceil(calibration.remaining_seconds)}s</p>}
    {!saved && <p role="status" className={calibration.clean && connected ? "ok-text" : "muted"}>{signal}</p>}
    {calibration.status === "failed" && <p role="alert">{calibration.error}. Your previous baseline has not been changed.</p>}
    {error && <p role="alert" className="error-text">{error}</p>}
    {!collecting && <button className="btn btn-primary btn-lg" disabled={busy || ending || !connected || (!saved && !calibration.clean)} onClick={() => void proceed()}>{busy ? "Please wait…" : saved ? "Start lecture" : calibration.status === "failed" ? "Retry 30-second calibration" : "Begin 30-second calibration"}</button>}
    <p className="small muted">The microphone and lecture start after calibration. No lesson or quiz here.</p>
    <button className="btn btn-plain" disabled={ending || busy} onClick={onEnd}>{ending ? "Ending…" : "Cancel session"}</button>
  </section>;
}
