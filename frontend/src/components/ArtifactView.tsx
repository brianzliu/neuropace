import { useEffect, useState } from "react";
import Diagram from "./Diagram";
import type { ArtifactKind, ChartContent, ExampleContent, ReteachContent, SceneGraph, StepsContent, WordsContent } from "../lib/types";

/** Renders one explanation artifact (docs/PRODUCT.md §4). Progressive reveal is the presentation mode for every
 * multi-part artifact: `step` counts the parts shown so far; `onSteps` reports how many parts there are. */
export default function ArtifactView({ kind, content, step, onSteps }: { kind: ArtifactKind; content: ReteachContent; step: number; onSteps?: (n: number) => void }) {
  useEffect(() => {
    onSteps?.(stepsOf(kind, content));
  }, [kind, content, onSteps]);
  if (content === null || content === undefined) return <div className="label-2">Nothing to show for this one.</div>;
  switch (kind) {
    case "words":
      return <WordsView c={content as WordsContent} />;
    case "analogy":
      return <p className="artifact-prose analogy">{String(content)}</p>;
    case "diagram": {
      const g = content as SceneGraph;
      const cap = g.steps[Math.min(step, g.steps.length - 1)]?.caption ?? "";
      return (
        <div className="stack">
          <div className="diagram-card">
            <Diagram graph={g} step={step} />
          </div>
          <div className="caption" key={step}>
            {cap}
          </div>
        </div>
      );
    }
    case "chart":
      return <ChartView c={content as ChartContent} step={step} />;
    case "steps":
      return <StepsView c={content as StepsContent} step={step} />;
    case "example":
      return <ExampleView c={content as ExampleContent} step={step} />;
  }
}

export function stepsOf(kind: ArtifactKind, content: ReteachContent): number {
  if (!content || typeof content === "string") return 1;
  if (kind === "diagram") return Math.max(1, (content as SceneGraph).steps?.length ?? 1);
  if (kind === "chart") return Math.max(1, (content as ChartContent).points?.length ?? 1);
  if (kind === "steps") return Math.max(1, (content as StepsContent).steps?.length ?? 1);
  if (kind === "example") return Math.max(1, ((content as ExampleContent).lines?.length ?? 0) + 1);
  return 1;
}

function WordsView({ c }: { c: WordsContent }) {
  return (
    <div className="stack">
      <p className="artifact-prose">{c.summary}</p>
      <div className="key-idea">
        <div className="ki-term">{c.key_idea?.term}</div>
        <div className="ki-def">{c.key_idea?.definition}</div>
        {c.key_idea?.example ? <div className="ki-ex">For example: {c.key_idea.example}</div> : null}
      </div>
    </div>
  );
}

function StepsView({ c, step }: { c: StepsContent; step: number }) {
  return (
    <div className="stack">
      {c.title ? <div className="artifact-title">{c.title}</div> : null}
      <ol className="steps">
        {c.steps.slice(0, step + 1).map((s, i) => (
          <li key={i} className="step-item" style={{ animationDelay: "0ms" }}>
            <span className="step-num">{i + 1}</span>
            <span>{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ExampleView({ c, step }: { c: ExampleContent; step: number }) {
  const shown = c.lines.slice(0, Math.min(step + 1, c.lines.length));
  const showResult = step >= c.lines.length;
  return (
    <div className="stack">
      {c.title ? <div className="artifact-title">{c.title}</div> : null}
      <div className="example">
        {shown.map((l, i) => (
          <div key={i} className="ex-line">
            {l}
          </div>
        ))}
        {showResult ? <div className="ex-result">{c.result}</div> : null}
      </div>
    </div>
  );
}

function ChartView({ c, step }: { c: ChartContent; step: number }) {
  const [anim, setAnim] = useState(0);
  useEffect(() => {
    const id = window.requestAnimationFrame(() => setAnim(1));
    return () => window.cancelAnimationFrame(id);
  }, [step]);
  const pts = c.points ?? [];
  const max = Math.max(1e-9, ...pts.map((p) => Math.abs(p.value)));
  const shown = Math.min(pts.length, step + 1);
  const W = 640;
  const H = 240;
  const padL = 44;
  const padB = 36;
  const padT = 18;
  const innerW = W - padL - 16;
  const innerH = H - padB - padT;
  const x = (i: number) => padL + (innerW / Math.max(1, pts.length)) * (i + 0.5);
  const y = (v: number) => padT + innerH - (Math.abs(v) / max) * innerH;
  return (
    <div className="stack">
      <div className="artifact-title">{c.title}</div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={c.title}>
        <line x1={padL} y1={padT + innerH} x2={W - 16} y2={padT + innerH} className="axis-line" />
        <text x={8} y={padT + 10} className="unit">
          {c.unit}
        </text>
        {c.kind === "line" ? (
          <polyline
            className="chart-line"
            points={pts
              .slice(0, shown)
              .map((p, i) => `${x(i)},${y(p.value)}`)
              .join(" ")}
          />
        ) : null}
        {pts.map((p, i) => {
          const on = i < shown;
          const bw = Math.min(64, (innerW / pts.length) * 0.6);
          const top = y(p.value);
          return (
            <g key={i} className={"chart-pt" + (on ? " on" : "")}>
              {c.kind === "bar" ? (
                <rect x={x(i) - bw / 2} y={on ? top : padT + innerH} width={bw} height={on ? padT + innerH - top : 0} rx={6} style={{ transition: "all .5s cubic-bezier(.2,0,0,1)", opacity: anim }} />
              ) : (
                <circle cx={x(i)} cy={top} r={on ? 6 : 0} />
              )}
              <text x={x(i)} y={padT + innerH + 18} textAnchor="middle" className="lbl">
                {p.label}
              </text>
              {on ? (
                <text x={x(i)} y={top - 8} textAnchor="middle" className="val">
                  {p.value}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
      {shown >= pts.length ? <div className="caption">{c.takeaway}</div> : null}
    </div>
  );
}
