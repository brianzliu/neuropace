import { useEffect, useMemo, useState } from "react";
import Whiteboard from "./Whiteboard";
import type {
  AnalogyContent,
  AnimationContent,
  ArtifactKind,
  ChartContent,
  CompareContent,
  ExampleContent,
  PlotContent,
  ReteachContent,
  SceneGraph,
  StepsContent,
  TimelineContent,
  WordsContent,
} from "../lib/types";

/** Renders one explanation artifact (docs/PRODUCT.md §4). Every template is a fixed rendering; the model only
 * filled its data. Progressive reveal is the presentation mode for every multi-part artifact: `step` counts the
 * parts shown so far; `onSteps` reports how many parts there are. */
export default function ArtifactView({ kind, content, step, onSteps }: { kind: ArtifactKind; content: ReteachContent; step: number; onSteps?: (n: number) => void }) {
  useEffect(() => {
    onSteps?.(stepsOf(kind, content));
  }, [kind, content, onSteps]);
  if (content === null || content === undefined || content === "") return <div className="label-2">Nothing to show for this one.</div>;
  switch (kind) {
    case "words":
      return <WordsView c={content as WordsContent} />;
    case "analogy":
      return <AnalogyView c={content as AnalogyContent | string} step={step} />;
    case "diagram":
      return <Whiteboard graph={content as SceneGraph} step={step} />;
    case "chart":
      return <ChartView c={content as ChartContent} step={step} />;
    case "plot":
      return <PlotView c={content as PlotContent} step={step} />;
    case "timeline":
      return <TimelineView c={content as TimelineContent} step={step} />;
    case "compare":
      return <CompareView c={content as CompareContent} step={step} />;
    case "animation":
      return <AnimationView c={content as AnimationContent} />;
    case "steps":
      return <StepsView c={content as StepsContent} step={step} />;
    case "example":
      return <ExampleView c={content as ExampleContent} step={step} />;
  }
}

export function stepsOf(kind: ArtifactKind, content: ReteachContent): number {
  if (!content || typeof content === "string") return 1;
  if (kind === "analogy") return Math.max(1, ((content as AnalogyContent).mapping?.length ?? 0) + 1);
  if (kind === "diagram") return Math.max(1, (content as SceneGraph).steps?.length ?? 1);
  if (kind === "chart") return Math.max(1, (content as ChartContent).points?.length ?? 1);
  if (kind === "plot") return Math.max(1, (content as PlotContent).series?.length ?? 1);
  if (kind === "timeline") return Math.max(1, (content as TimelineContent).events?.length ?? 1);
  if (kind === "compare") return Math.max(1, ((content as CompareContent).rows?.length ?? 0) + 1);
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

/** The story first, then each mapping pair on its own beat, then where the comparison breaks. */
function AnalogyView({ c, step }: { c: AnalogyContent | string; step: number }) {
  if (typeof c === "string") return <p className="artifact-prose analogy">{c}</p>;
  const shown = Math.min(c.mapping.length, step);
  return (
    <div className="stack">
      <p className="artifact-prose analogy">{c.story}</p>
      {shown > 0 ? (
        <div className="mapping">
          {c.mapping.slice(0, shown).map((m, i) => (
            <div key={i} className="map-row">
              <span className="map-idea">{m.idea}</span>
              <span className="map-arrow">is like</span>
              <span className="map-everyday">{m.everyday}</span>
            </div>
          ))}
        </div>
      ) : null}
      {step >= c.mapping.length && c.caveat ? <div className="caption">Where it stops holding: {c.caveat}</div> : null}
    </div>
  );
}

function StepsView({ c, step }: { c: StepsContent; step: number }) {
  return (
    <div className="stack">
      {c.title ? <div className="artifact-title">{c.title}</div> : null}
      <ol className="steps">
        {c.steps.slice(0, step + 1).map((s, i) => (
          <li key={i} className="step-item">
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

const SERIES_CLASS = ["s0", "s1", "s2"];

/** Numeric axes, up to three series drawn one per step, annotations at the end. */
function PlotView({ c, step }: { c: PlotContent; step: number }) {
  const W = 640;
  const H = 260;
  const padL = 52;
  const padR = 18;
  const padT = 18;
  const padB = 44;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const { xs, ys } = useMemo(() => {
    const allX = c.series.flatMap((s) => s.points.map((p) => p.x)).concat(c.annotations.map((a) => a.x));
    const allY = c.series.flatMap((s) => s.points.map((p) => p.y)).concat(c.annotations.map((a) => a.y));
    const x0 = Math.min(...allX);
    const x1 = Math.max(...allX);
    const y0 = Math.min(0, ...allY);
    const y1 = Math.max(...allY);
    return { xs: [x0, x1 === x0 ? x0 + 1 : x1], ys: [y0, y1 === y0 ? y0 + 1 : y1] };
  }, [c]);
  const sx = (v: number) => padL + ((v - xs[0]) / (xs[1] - xs[0])) * innerW;
  const sy = (v: number) => padT + innerH - ((v - ys[0]) / (ys[1] - ys[0])) * innerH;
  const shown = Math.min(c.series.length, step + 1);
  const fmt = (v: number) => (Math.abs(v) >= 100 ? Math.round(v).toString() : Number(v.toFixed(2)).toString());
  return (
    <div className="stack">
      <div className="row between">
        <div className="artifact-title">{c.title}</div>
        {c.illustrative ? <span className="badge">shape only</span> : null}
      </div>
      <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={c.title}>
        <line x1={padL} y1={padT + innerH} x2={W - padR} y2={padT + innerH} className="axis-line" />
        <line x1={padL} y1={padT} x2={padL} y2={padT + innerH} className="axis-line" />
        <text x={W - padR} y={H - 10} textAnchor="end" className="lbl">
          {c.x_label}
        </text>
        <text x={12} y={padT + 6} className="lbl">
          {c.y_label}
        </text>
        {!c.illustrative ? (
          <>
            <text x={padL} y={padT + innerH + 16} textAnchor="middle" className="tick">
              {fmt(xs[0])}
            </text>
            <text x={W - padR} y={padT + innerH + 16} textAnchor="middle" className="tick">
              {fmt(xs[1])}
            </text>
            <text x={padL - 6} y={padT + 4} textAnchor="end" className="tick">
              {fmt(ys[1])}
            </text>
          </>
        ) : null}
        {c.series.slice(0, shown).map((s, i) => (
          <g key={i} className={"series " + SERIES_CLASS[i % 3]}>
            <polyline className="plot-line" points={s.points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} />
            <text x={sx(s.points[s.points.length - 1].x) - 4} y={sy(s.points[s.points.length - 1].y) - 8} textAnchor="end" className="series-name">
              {s.name}
            </text>
          </g>
        ))}
        {shown >= c.series.length
          ? c.annotations.map((a, i) => (
              <g key={i} className="annot">
                <circle cx={sx(a.x)} cy={sy(a.y)} r={5} />
                <text x={sx(a.x) + 8} y={sy(a.y) - 6} className="annot-text">
                  {a.text}
                </text>
              </g>
            ))
          : null}
      </svg>
      {shown >= c.series.length ? <div className="caption">{c.takeaway}</div> : null}
    </div>
  );
}

/** A line with one dot per event; events appear in order, the current one carries its detail. */
function TimelineView({ c, step }: { c: TimelineContent; step: number }) {
  const n = c.events.length;
  const shown = Math.min(n, step + 1);
  const cur = c.events[shown - 1];
  return (
    <div className="stack">
      <div className="artifact-title">{c.title}</div>
      <div className="timeline" style={{ ["--n" as string]: n }}>
        <div className="tl-line">
          <i style={{ width: `${n > 1 ? ((shown - 1) / (n - 1)) * 100 : 100}%` }} />
        </div>
        {c.events.map((e, i) => (
          <div key={i} className={"tl-event" + (i < shown ? " on" : "") + (i === shown - 1 ? " cur" : "")} style={{ left: n > 1 ? `calc(60px + (100% - 120px) * ${i / (n - 1)})` : "50%" }}>
            <span className="tl-when">{e.when}</span>
            <span className="tl-dot" />
            <span className="tl-label">{e.label}</span>
          </div>
        ))}
      </div>
      <div className="caption" key={shown}>
        {cur?.detail}
      </div>
      {shown >= n ? <div className="caption takeaway">{c.takeaway}</div> : null}
    </div>
  );
}

/** Two columns, one row per step, the verdict last. */
function CompareView({ c, step }: { c: CompareContent; step: number }) {
  const shown = Math.min(c.rows.length, step + 1);
  return (
    <div className="stack">
      <div className="artifact-title">{c.title}</div>
      <table className="compare">
        <thead>
          <tr>
            <th />
            <th>{c.left}</th>
            <th>{c.right}</th>
          </tr>
        </thead>
        <tbody>
          {c.rows.slice(0, shown).map((r, i) => (
            <tr key={i} className="cmp-row">
              <th>{r.aspect}</th>
              <td>{r.left_value}</td>
              <td>{r.right_value}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {step >= c.rows.length ? <div className="caption">{c.verdict}</div> : null}
    </div>
  );
}

/** The model's animation runs in a sandboxed iframe (scripts only: no network, storage or access to Reflow). */
function AnimationView({ c }: { c: AnimationContent }) {
  const [gen, setGen] = useState(0);
  const doc = useMemo(() => {
    const ink = getComputedStyle(document.documentElement).getPropertyValue("--label").trim() || "#3c3c3c";
    return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'"><style>html,body{margin:0;background:transparent;color:${ink};font-family:system-ui,sans-serif;overflow:hidden}svg,canvas{display:block;width:100%;height:260px;object-fit:contain}</style></head><body>${c.html}</body></html>`;
  }, [c.html]);
  return (
    <div className="stack">
      <div className="row between">
        <div className="artifact-title">{c.title}</div>
        <button className="btn btn-sm" onClick={() => setGen((g) => g + 1)} title="Play the animation from the start">
          Replay
        </button>
      </div>
      <div className="animation-card">
        <iframe key={gen} className="animation-frame" title={c.title} sandbox="allow-scripts" srcDoc={doc} />
      </div>
      <div className="caption">{c.caption}</div>
    </div>
  );
}
