import { useEffect, useRef, useState } from "react";
import type { HeadsetStatus } from "../lib/types";

/** How long without a chunk before the trace is "not live" (the backend uses the same 2 s). */
const STALE_MS = 2000;

/** The student's own brain waves: the last seconds of the 64 Hz microvolt trace, plus theta/alpha/beta shares.
 * "Live" means chunks are arriving right now, judged here from their arrival time, not from a flag: a headset that
 * is paired but silent shows "waiting for the headset" within two seconds. A practice (simulated) signal says so. */
export default function BrainWaves({
  samples,
  rawAt,
  bands,
  headset,
  label,
  compact,
}: {
  samples: number[];
  rawAt: number;
  bands: { theta: number; alpha: number; beta: number } | null;
  headset: HeadsetStatus | null;
  label?: string;
  compact?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);
  const live = rawAt > 0 && now - rawAt < STALE_MS;
  const simulated = !headset || headset.kind !== "real";
  const paired = !!headset && headset.kind === "real";
  const tone: "live" | "practice" | "waiting" | "off" = !headset ? "off" : live ? (simulated ? "practice" : "live") : paired ? "waiting" : "off";
  const sub =
    tone === "live" ? "live from your headset" : tone === "practice" ? "practice signal" : tone === "waiting" ? "waiting for the headset" : "no headset";

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const css = getComputedStyle(canvas);
    const stroke = css.getPropertyValue("--wave").trim() || "#1cb0f6";
    const muted = css.getPropertyValue("--label-3").trim() || "#999";
    const grid = css.getPropertyValue("--separator").trim() || "rgba(0,0,0,.1)";
    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    const n = samples.length;
    if (n < 8) return;
    const win = Math.min(n, 320); // 5 s at 64 Hz
    const seg = samples.slice(n - win);
    // a real electrode drifts: centre the visible window on its own mean so the trace stays on screen
    let mean = 0;
    for (const v of seg) mean += v;
    mean /= seg.length;
    let peak = 20;
    for (const v of seg) peak = Math.max(peak, Math.abs(v - mean));
    peak = Math.min(peak, 400);
    ctx.strokeStyle = live ? stroke : muted;
    ctx.globalAlpha = live ? 1 : 0.45;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i < seg.length; i++) {
      const x = (i / (win - 1)) * w;
      const y = h / 2 - (Math.max(-peak, Math.min(peak, seg[i] - mean)) / peak) * (h / 2 - 6);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }, [samples, live]);

  return (
    <div className={"waves " + tone + (compact ? " compact" : "")}>
      <div className="waves-head">
        <span className="waves-title">{label ?? "Your brain waves"}</span>
        <span className="waves-sub">
          <span className="waves-dot" /> {sub}
        </span>
      </div>
      <canvas ref={ref} className="waves-canvas" />
      {bands && live ? (
        <div className="bands">
          {(["theta", "alpha", "beta"] as const).map((k) => (
            <div key={k} className={"band " + k} title={`${k}: ${Math.round(bands[k] * 100)}%`}>
              <span className="band-name">{k}</span>
              <span className="band-bar">
                <i style={{ width: `${Math.round(bands[k] * 100)}%` }} />
              </span>
            </div>
          ))}
        </div>
      ) : tone === "waiting" ? (
        <div className="waves-note">Nothing is coming from the headset. Check it is on and charged; Reflow reconnects by itself.</div>
      ) : null}
    </div>
  );
}
