import { useEffect, useRef } from "react";

/** The student's own brain waves: the last seconds of the 64 Hz microvolt trace, plus theta/alpha/beta shares. */
export default function BrainWaves({
  samples,
  bands,
  connected,
  label,
  compact,
}: {
  samples: number[];
  bands: { theta: number; alpha: number; beta: number } | null;
  connected: boolean;
  label?: string;
  compact?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
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
    const grid = css.getPropertyValue("--separator").trim() || "rgba(0,0,0,.1)";
    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    const n = samples.length;
    if (!connected || n < 8) return;
    const win = Math.min(n, 320); // 5 s at 64 Hz
    const seg = samples.slice(n - win);
    let peak = 20;
    for (const v of seg) peak = Math.max(peak, Math.abs(v));
    peak = Math.min(peak, 400);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i < seg.length; i++) {
      const x = (i / (win - 1)) * w;
      const y = h / 2 - (Math.max(-peak, Math.min(peak, seg[i])) / peak) * (h / 2 - 6);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [samples, connected]);
  return (
    <div className={"waves" + (compact ? " compact" : "")}>
      <div className="waves-head">
        <span className="waves-title">{label ?? "Your brain waves"}</span>
        <span className="waves-sub">{connected ? "live, microvolts" : "no headset"}</span>
      </div>
      <canvas ref={ref} className="waves-canvas" />
      {bands && connected ? (
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
      ) : null}
    </div>
  );
}
