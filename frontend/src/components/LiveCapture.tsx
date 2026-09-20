import { backendFetch } from "../lib/backend";
import { useEffect, useRef, useState } from "react";

export interface CaptureStatus {
  capturing: boolean;
  frames: number;
}

export default function LiveCapture({ sessionId, active, onStatus }: { sessionId: string; active: boolean; onStatus?: (s: CaptureStatus) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const generation = useRef(0);
  const [capturing, setCapturing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [frames, setFrames] = useState(0);
  const clearBuffer = () => { void backendFetch(`/api/sessions/${sessionId}/board`, {method: "DELETE", keepalive: true}).catch(() => {}); };
  const halt = () => {
    generation.current++;
    stream.current?.getTracks().forEach(t => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setCapturing(false);
    setBusy(false);
  };
  const stop = () => { halt(); clearBuffer(); };
  // Media lifecycle: stop tracks and clear the server buffer when capture is
  // deactivated or the view goes away. The initial inactive mount must not
  // delete a buffer a reloading page is rejoining.
  useEffect(() => {
    if (!active) return;
    return () => { halt(); clearBuffer(); };
  }, [active]);
  useEffect(() => { onStatus?.({ capturing, frames }); }, [capturing, frames, onStatus]);
  const start = async () => {
    const run = ++generation.current;
    setBusy(true); setError("");
    try {
      const media = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 1280}, facingMode: "environment"}, audio: false});
      if (run !== generation.current) { media.getTracks().forEach(t => t.stop()); return; }
      stream.current = media;
      media.getVideoTracks()[0].onended = stop;
      if (video.current) { video.current.srcObject = media; await video.current.play(); }
      setCapturing(true);
    } catch (e) { stop(); setError(String(e)); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    if (!capturing) return;
    let sending = false;
    const controller = new AbortController();
    const interval = window.setInterval(async () => {
      if (sending || !video.current?.videoWidth) return;
      sending = true;
      try {
        const canvas = document.createElement("canvas");
        canvas.width = Math.min(960, video.current.videoWidth);
        canvas.height = Math.round(canvas.width * video.current.videoHeight / video.current.videoWidth);
        canvas.getContext("2d")!.drawImage(video.current, 0, 0, canvas.width, canvas.height);
        const response = await backendFetch(`/api/sessions/${sessionId}/board`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({image: canvas.toDataURL("image/jpeg", .65)}), signal: controller.signal});
        if (!response.ok) throw new Error("Board frame could not be saved. Pause capture and check the session connection.");
        setFrames(n => n + 1); setError("");
      } catch (e) { if (!controller.signal.aborted) setError(String(e)); }
      finally { sending = false; }
    }, 2000);
    return () => { window.clearInterval(interval); controller.abort(); };
  }, [capturing, sessionId]);
  return <section className="panel live-capture"><div className="row"><h2>Whiteboard</h2><span className={"badge " + (capturing ? "good" : "")}>{capturing ? "Camera live" : "Camera off"}</span></div>
    <video ref={video} muted playsInline hidden={!capturing} />
    {!capturing && <p className="small muted">Frame the board, not the audience. With everyone’s agreement, enable capture to include drawings in button-triggered explanations.</p>}
    <p className="small muted">Frames buffer locally for 90 seconds. Selected images and transcript are sent to the configured model when you request a catch-up. Raw video is not recorded.</p>
    <div className="row"><button onClick={() => capturing ? stop() : void start()} disabled={!active || busy}>{busy ? "Opening camera…" : capturing ? "Stop camera" : "Enable board capture"}</button>{capturing && <span className="small muted">{frames} frames received</span>}</div>
    {error && <p className="error small" role="alert">{error}</p>}
  </section>;
}
