import { useEffect, useRef } from "react";
import type { Flag, FocusMsg } from "../lib/types";

interface Props {
  focus: FocusMsg[];
  flags: Flag[];
  now: number;
  enterZ: number;
  exitZ: number;
  windowSeconds?: number;
}

/** Focus trace: z(E) over the last 180 s with thresholds, drop bands, tap marks and blink ticks. */
export default function FocusTrace({ focus, flags, now, enterZ, exitZ, windowSeconds = 180 }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const last = focus.length ? focus[focus.length - 1] : null;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const padL = 34;
    const padR = 8;
    const padT = 22;
    const padB = 22;
    const zMin = -4;
    const zMax = 3;
    const t1 = Math.max(now, windowSeconds);
    const t0 = t1 - windowSeconds;
    const x = (t: number) => padL + ((t - t0) / windowSeconds) * (W - padL - padR);
    const y = (z: number) => padT + ((zMax - Math.max(zMin, Math.min(zMax, z))) / (zMax - zMin)) * (H - padT - padB);

    // drop bands (from focus state) and bad-quality shading
    let bandStart: number | null = null;
    let badStart: number | null = null;
    const flush = (kind: "drop" | "bad", from: number, to: number) => {
      ctx.fillStyle = kind === "drop" ? "rgba(248,113,113,0.18)" : "rgba(139,149,167,0.10)";
      ctx.fillRect(x(from), padT, Math.max(1, x(to) - x(from)), H - padT - padB);
    };
    for (const f of focus) {
      if (f.t < t0 - 1) continue;
      if (f.state === "drop") {
        if (bandStart === null) bandStart = f.t;
      } else if (bandStart !== null) {
        flush("drop", bandStart, f.t);
        bandStart = null;
      }
      if (f.quality === "bad" || f.state === "nosignal") {
        if (badStart === null) badStart = f.t;
      } else if (badStart !== null) {
        flush("bad", badStart, f.t);
        badStart = null;
      }
    }
    if (bandStart !== null) flush("drop", bandStart, t1);
    if (badStart !== null) flush("bad", badStart, t1);

    // grid + thresholds
    ctx.strokeStyle = "#273041";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, y(0));
    ctx.lineTo(W - padR, y(0));
    ctx.stroke();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "#f87171";
    ctx.beginPath();
    ctx.moveTo(padL, y(enterZ));
    ctx.lineTo(W - padR, y(enterZ));
    ctx.stroke();
    ctx.strokeStyle = "#fbbf24";
    ctx.beginPath();
    ctx.moveTo(padL, y(exitZ));
    ctx.lineTo(W - padR, y(exitZ));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#8b95a7";
    ctx.font = "11px ui-monospace, Menlo, monospace";
    ctx.textAlign = "right";
    for (const z of [2, 0, -2, enterZ]) {
      ctx.fillText(z.toFixed(0), padL - 6, y(z) + 4);
    }
    ctx.textAlign = "left";
    // time ticks
    for (let t = Math.ceil(t0 / 30) * 30; t <= t1; t += 30) {
      ctx.fillText(`${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`, x(t) + 2, H - 6);
      ctx.fillStyle = "#273041";
      ctx.fillRect(x(t), padT, 1, H - padT - padB);
      ctx.fillStyle = "#8b95a7";
    }

    // z line
    ctx.strokeStyle = "#60a5fa";
    ctx.lineWidth = 2;
    ctx.beginPath();
    let pen = false;
    for (const f of focus) {
      if (f.t < t0 - 1) continue;
      if (f.z === null || f.paused) {
        pen = false;
        continue;
      }
      const px = x(f.t);
      const py = y(f.z);
      if (!pen) {
        ctx.moveTo(px, py);
        pen = true;
      } else ctx.lineTo(px, py);
    }
    ctx.stroke();
    // w15 (window mean) as a thin line
    ctx.strokeStyle = "rgba(167,139,250,0.8)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    pen = false;
    for (const f of focus) {
      if (f.t < t0 - 1) continue;
      if (f.w15 === null || f.paused) {
        pen = false;
        continue;
      }
      const px = x(f.t);
      const py = y(f.w15);
      if (!pen) {
        ctx.moveTo(px, py);
        pen = true;
      } else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // blink ticks and artifacts
    for (const f of focus) {
      if (f.t < t0) continue;
      if (f.blink) {
        ctx.fillStyle = "#34d399";
        ctx.fillRect(x(f.t) - 1, padT - 8, 2, 6);
      }
      if (f.artifact) {
        ctx.fillStyle = "#8b95a7";
        ctx.fillRect(x(f.t) - 1, padT - 14, 2, 4);
      }
    }
    // tap marks and flag spans
    for (const fl of flags) {
      if (fl.t_trigger < t0 - 5) continue;
      const isTap = fl.source === "tap" || fl.source === "sim_tap";
      ctx.strokeStyle = isTap ? "#fbbf24" : "#f87171";
      ctx.lineWidth = isTap ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x(fl.t_trigger), padT);
      ctx.lineTo(x(fl.t_trigger), H - padB);
      ctx.stroke();
      if (fl.t_start !== null) {
        ctx.fillStyle = isTap ? "rgba(251,191,36,0.12)" : "rgba(248,113,113,0.10)";
        const end = fl.t_end ?? t1;
        ctx.fillRect(x(fl.t_start), H - padB - 6, Math.max(2, x(end) - x(fl.t_start)), 6);
      }
      if (isTap) {
        ctx.fillStyle = "#fbbf24";
        ctx.font = "bold 10px sans-serif";
        ctx.fillText("tap", x(fl.t_trigger) + 3, padT + 10);
      }
    }
    // now marker
    ctx.fillStyle = "#e8ecf2";
    ctx.fillRect(x(now) - 1, padT, 1, H - padT - padB);
  }, [focus, flags, now, enterZ, exitZ, windowSeconds]);

  return (
    <div className="trace-wrap">
      <canvas ref={ref} className="trace" />
      <div className="trace-legend">
        <span style={{ color: "#60a5fa" }}>z(E)</span>
        <span style={{ color: "#a78bfa" }}>15 s mean</span>
        <span style={{ color: "#f87171" }}>drop {enterZ}</span>
        <span style={{ color: "#fbbf24" }}>recover {exitZ}</span>
        <span style={{ color: "#34d399" }}>blink</span>
        {last ? <span className="mono">blinks {last.blinks_total ?? 0}</span> : null}
      </div>
      {last && !last.baseline_ready ? (
        <>
          <div className="baseline-bar">
            <i style={{ width: `${Math.round(last.baseline_progress * 100)}%` }} />
          </div>
          <div className="baseline-label">
            {last.state === "nosignal" ? "waiting for headset" : last.quality === "bad" ? "poor signal, fix the fit" : `baseline ${Math.round(last.baseline_progress * 100)}%`}
          </div>
        </>
      ) : null}
    </div>
  );
}
