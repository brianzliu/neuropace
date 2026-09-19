import { useMemo } from "react";
import type { SceneGraph } from "../lib/types";

interface Props {
  graph: SceneGraph;
  step: number; // index into graph.steps; -1 = nothing revealed
}

interface Laid {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

const W = 720;
const NODE_H = 46;

function layout(graph: SceneGraph): { nodes: Laid[]; height: number } {
  const ids = graph.nodes.map((n) => n.id);
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  for (const id of ids) {
    incoming.set(id, []);
    outgoing.set(id, []);
  }
  for (const e of graph.edges) {
    if (!incoming.has(e.to_id) || !outgoing.has(e.from_id)) continue;
    incoming.get(e.to_id)!.push(e.from_id);
    outgoing.get(e.from_id)!.push(e.to_id);
  }
  // longest-path layering from sources, with a cycle guard
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  const depth = (id: string): number => {
    if (layer.has(id)) return layer.get(id)!;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const parents = incoming.get(id) ?? [];
    const d = parents.length ? Math.max(...parents.map((p) => depth(p) + 1)) : 0;
    visiting.delete(id);
    layer.set(id, d);
    return d;
  };
  for (const id of ids) depth(id);
  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const l = layer.get(id) ?? 0;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(id);
  }
  const nLayers = Math.max(1, byLayer.size);
  const maxPerLayer = Math.max(...[...byLayer.values()].map((v) => v.length));
  const height = Math.max(200, 60 + maxPerLayer * (NODE_H + 34));
  const colW = W / nLayers;
  const nodes: Laid[] = [];
  const labelOf = new Map(graph.nodes.map((n) => [n.id, n.label]));
  for (const [l, members] of [...byLayer.entries()].sort((a, b) => a[0] - b[0])) {
    const rowH = (height - 40) / members.length;
    members.forEach((id, i) => {
      const label = labelOf.get(id) ?? id;
      const w = Math.min(colW - 24, Math.max(90, label.length * 8.6 + 26));
      nodes.push({ id, label, x: colW * l + colW / 2 - w / 2, y: 30 + rowH * i + rowH / 2 - NODE_H / 2, w, h: NODE_H });
    });
  }
  return { nodes, height };
}

function trunc(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/** Animated scene graph: nodes fade in when first highlighted, edges draw once both ends are visible. */
export default function Diagram({ graph, step }: Props) {
  const { nodes, height } = useMemo(() => layout(graph), [graph]);
  const pos = new Map(nodes.map((n) => [n.id, n]));
  const revealed = new Set<string>();
  for (let i = 0; i <= step && i < graph.steps.length; i++) for (const id of graph.steps[i].highlight) revealed.add(id);
  const hot = new Set(step >= 0 && step < graph.steps.length ? graph.steps[step].highlight : []);
  // if the last step is reached, reveal everything so nothing is left hidden
  if (step >= graph.steps.length - 1) for (const n of nodes) revealed.add(n.id);
  return (
    <svg className="diagram" viewBox={`0 0 ${W} ${height}`} role="img" aria-label={graph.title}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#8b95a7" />
        </marker>
      </defs>
      <text className="title" x={12} y={18}>
        {trunc(graph.title, 60)}
      </text>
      {graph.edges.map((e, i) => {
        const a = pos.get(e.from_id);
        const b = pos.get(e.to_id);
        if (!a || !b) return null;
        const on = revealed.has(e.from_id) && revealed.has(e.to_id);
        const isHot = on && (hot.has(e.from_id) || hot.has(e.to_id));
        const x1 = a.x + a.w;
        const y1 = a.y + a.h / 2;
        const x2 = b.x;
        const y2 = b.y + b.h / 2;
        const leftToRight = x2 >= x1;
        const sx = leftToRight ? x1 : a.x;
        const ex = leftToRight ? x2 : b.x + b.w;
        const cx = (sx + ex) / 2;
        const d = `M ${sx} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${ex} ${y2}`;
        return (
          <g key={i} className={"edge" + (on ? " on" : "") + (isHot ? " hot" : "")}>
            <path d={d} pathLength={1} markerEnd="url(#arrow)" />
            {e.label ? (
              <text x={cx} y={(y1 + y2) / 2 - 6} textAnchor="middle">
                {trunc(e.label, 18)}
              </text>
            ) : null}
          </g>
        );
      })}
      {nodes.map((n) => (
        <g key={n.id} className={"node" + (revealed.has(n.id) ? " on" : "") + (hot.has(n.id) ? " hot" : "")}>
          <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={10} />
          <text x={n.x + n.w / 2} y={n.y + n.h / 2 + 5} textAnchor="middle">
            {trunc(n.label, Math.max(8, Math.floor((n.w - 20) / 8.6)))}
          </text>
        </g>
      ))}
    </svg>
  );
}
