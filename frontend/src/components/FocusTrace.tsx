import { useEffect, useRef } from "react";
import { isTapSource, type Flag, type FocusMsg } from "../lib/types";

interface Props {
  focus: FocusMsg[];
  flags: Flag[];
  now: number;
  enterZ: number;
  exitZ: number;
  windowSeconds?: number;
}

function cssVar(el: Element, name: string, fallback: string): string {
  const v = getComputedStyle(el).getPropertyValue(name).trim();
  return v || fallback;
}

/** Focus trace: z(E) over the last 180 s with thresholds, drop bands, tap marks and blink ticks. Colors follow the theme. */
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
    const C = {
      accent: cssVar(canvas, "--accent", "#007aff"),
      purple: cssVar(canvas, "--purple", "#af52de"),
      danger: cssVar(canvas, "--danger", "#ff3b30"),
      warning: cssVar(canvas, "--warning", "#ff9f0a"),
      success: cssVar(canvas, "--success", "#34c759"),
      sep: cssVar(canvas, "--separator", "rgba(60,60,67,0.12)"),
      label2: cssVar(canvas, "--label-2", "rgba(60,60,67,0.6)"),
      label3: cssVar(canvas, "--label-3", "rgba(60,60,67,0.3)"),
      label: cssVar(canvas, "--label", "#1d1d1f"),
    };
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const padL = 30;
    const padR = 6;
    const padT = 14;
    const padB = 18;
    const zMin = -4;
    const zMax = 3;
    const t1 = Math.max(now, windowSeconds);
    const t0 = t1 - windowSeconds;
    const x = (t: number) => padL + ((t - t0) / windowSeconds) * (W - padL - padR);
    const y = (z: number) => padT + ((zMax - Math.max(zMin, Math.min(zMax, z))) / (zMax - zMin)) * (H - padT - padB);

    let bandStart: number | null = null;
    let badStart: number | null = null;
    const flush = (kind: "drop" | "bad", from: number, to: number) => {
      ctx.globalAlpha = kind === "drop" ? 0.14 : 0.08;
      ctx.fillStyle = kind === "drop" ? C.danger : C.label2;
      ctx.fillRect(x(from), padT, Math.max(1, x(to) - x(from)), H - padT - padB);
      ctx.globalAlpha = 1;
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

    ctx.strokeStyle = C.sep;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, y(0));
    ctx.lineTo(W - padR, y(0));
    ctx.stroke();
    ctx.setLineDash([3, 4]);
    ctx.strokeStyle = C.danger;
    ctx.beginPath();
    ctx.moveTo(padL, y(enterZ));
    ctx.lineTo(W - padR, y(enterZ));
    ctx.stroke();
    ctx.strokeStyle = C.warning;
    ctx.beginPath();
    ctx.moveTo(padL, y(exitZ));
    ctx.lineTo(W - padR, y(exitZ));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = C.label2;
    ctx.font = "10px ui-monospace, Menlo, monospace";
    ctx.textAlign = "right";
    for (const z of [2, 0, -2]) ctx.fillText(z.toFixed(0), padL - 5, y(z) + 3);
    ctx.textAlign = "left";
    for (let t = Math.ceil(t0 / 30) * 30; t <= t1; t += 30) {
      ctx.fillStyle = C.sep;
      ctx.fillRect(x(t), padT, 1, H - padT - padB);
      ctx.fillStyle = C.label2;
      ctx.fillText(`${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, "0")}`, x(t) + 3, H - 5);
    }

    const drawLine = (get: (f: FocusMsg) => number | null, color: string, width: number, alpha: number) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      let pen = false;
      for (const f of focus) {
        if (f.t < t0 - 1) continue;
        const v = get(f);
        if (v === null || f.paused) {
          pen = false;
          continue;
        }
        const px = x(f.t);
        const py = y(v);
        if (!pen) {
          ctx.moveTo(px, py);
          pen = true;
        } else ctx.lineTo(px, py);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    };
    drawLine((f) => f.z, C.accent, 1.8, 1);
    drawLine((f) => f.w15, C.purple, 1.2, 0.85);

    for (const f of focus) {
      if (f.t < t0) continue;
      if (f.blink) {
        ctx.fillStyle = C.success;
        ctx.fillRect(x(f.t) - 1, padT - 6, 2, 5);
      }
      if (f.artifact) {
        ctx.fillStyle = C.label3;
        ctx.fillRect(x(f.t) - 1, padT - 11, 2, 3);
      }
    }
    for (const fl of flags) {
      if (fl.t_trigger < t0 - 5) continue;
      const isTap = isTapSource(fl.source);
      ctx.strokeStyle = isTap ? C.warning : C.danger;
      ctx.lineWidth = isTap ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(x(fl.t_trigger), padT);
      ctx.lineTo(x(fl.t_trigger), H - padB);
      ctx.stroke();
      if (fl.t_start !== null) {
        ctx.globalAlpha = 0.16;
        ctx.fillStyle = isTap ? C.warning : C.danger;
        const end = fl.t_end ?? t1;
        ctx.fillRect(x(fl.t_start), H - padB - 5, Math.max(2, x(end) - x(fl.t_start)), 5);
        ctx.globalAlpha = 1;
      }
      if (isTap) {
        ctx.fillStyle = C.warning;
        ctx.font = "600 9px -apple-system, BlinkMacSystemFont, sans-serif";
        ctx.fillText("tap", x(fl.t_trigger) + 3, padT + 9);
      }
    }
    ctx.fillStyle = C.label;
    ctx.globalAlpha = 0.7;
    ctx.fillRect(x(now) - 0.5, padT, 1, H - padT - padB);
    ctx.globalAlpha = 1;
  }, [focus, flags, now, enterZ, exitZ, windowSeconds]);

  return (
    <div className="card trace-card">
      <div className="trace-legend">
        <span><i className="sw" style={{ background: "var(--accent)" }} />z(E)</span>
        <span><i className="sw" style={{ background: "var(--purple)" }} />15 s mean</span>
        <span><i className="sw" style={{ background: "var(--danger)" }} />drop {enterZ}</span>
        <span><i className="sw" style={{ background: "var(--warning)" }} />recover {exitZ}</span>
        <span><i className="sw" style={{ background: "var(--success)" }} />blink</span>
      </div>
      <canvas ref={ref} />
      {last && !last.baseline_ready ? (
        <div className="trace-foot">
          <span className="progress">
            <i style={{ width: `${Math.round(last.baseline_progress * 100)}%` }} />
          </span>
          <span>{last.state === "nosignal" ? "waiting for the headset" : last.quality === "bad" ? "poor signal, fix the fit" : `baseline ${Math.round(last.baseline_progress * 100)}%`}</span>
        </div>
      ) : null}
    </div>
  );
}
