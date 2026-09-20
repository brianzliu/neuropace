import { useState } from "react";
import ArtifactView, { stepsOf } from "./ArtifactView";
import ManimView from "./ManimView";
import { RoughArrowhead, RoughEllipse, RoughLine, RoughRect } from "./Rough";
import type { ArrowContent, ArtifactKind, BoardElement, LabelContent, ManimContent, ReteachContent, ShapeContent } from "../lib/types";

const BOARD_W = 4000;
const BOARD_H = 3000;
const SKETCH = { stroke: "currentColor", strokeWidth: 2, roughness: 1.7 };

/** The shared whiteboard (docs/PRODUCT.md §5a): a blank surface until the agent draws on it. Position/zoom
 * is the only freedom the model has beyond content — every element is one of the same validated templates
 * used elsewhere (§4) or one of three small annotation primitives (shape, arrow, label), rendered sketchy
 * (roughjs) so it reads as marker-on-a-board rather than app UI. */
export default function Board({ elements, onExpand, caption }: { elements: BoardElement[]; onExpand: (id: string) => void; caption?: string | null }) {
  const [zoom, setZoom] = useState(0.55);
  const boxes = elements.filter((e) => e.kind !== "arrow");
  const arrows = elements.filter((e) => e.kind === "arrow");
  const centerOf = (id: string) => {
    const el = boxes.find((b) => b.id === id);
    return el ? { x: el.envelope.x + el.envelope.w / 2, y: el.envelope.y + el.envelope.h / 2 } : null;
  };
  return (
    <div className="oh-board">
      <div className="oh-board-toolbar row">
        <button type="button" className="btn btn-sm" onClick={() => setZoom((z) => Math.max(0.25, z - 0.1))} aria-label="Zoom out">
          −
        </button>
        <span className="label-3">{Math.round(zoom * 100)}%</span>
        <button type="button" className="btn btn-sm" onClick={() => setZoom((z) => Math.min(1.5, z + 0.1))} aria-label="Zoom in">
          +
        </button>
      </div>
      <div className="oh-board-viewport">
        <div className="oh-board-canvas" style={{ width: BOARD_W, height: BOARD_H, transform: `scale(${zoom})` }}>
          <svg className="oh-board-arrows" viewBox={`0 0 ${BOARD_W} ${BOARD_H}`} width={BOARD_W} height={BOARD_H}>
            {arrows.map((a) => {
              const c = a.content as ArrowContent;
              const from = centerOf(c.from_id);
              const to = centerOf(c.to_id);
              if (!from || !to) return null;
              const angle = Math.atan2(to.y - from.y, to.x - from.x);
              const trim = 22;
              const tipX = to.x - trim * Math.cos(angle);
              const tipY = to.y - trim * Math.sin(angle);
              return (
                <g key={a.id} className="oh-arrow">
                  <RoughLine x1={from.x} y1={from.y} x2={tipX} y2={tipY} options={SKETCH} />
                  <RoughArrowhead x={tipX} y={tipY} angle={angle} options={SKETCH} />
                  <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 10}>
                    {c.label}
                  </text>
                </g>
              );
            })}
          </svg>
          {boxes.map((el, i) => (
            <BoardElementWrapper key={el.id} el={el} onExpand={onExpand} order={i} />
          ))}
        </div>
      </div>
      {caption ? (
        <div className="oh-caption-bar" role="status">
          <span key={caption} className="oh-caption-text">{caption}</span>
        </div>
      ) : null}
    </div>
  );
}

const FRAMED_KINDS = new Set(["shape", "label", "manim"]);

function BoardElementWrapper({ el, onExpand, order }: { el: BoardElement; onExpand: (id: string) => void; order: number }) {
  const { x, y, w, h, z } = el.envelope;
  const framed = !FRAMED_KINDS.has(el.kind);
  return (
    <div
      className="oh-board-element oh-pop-in"
      style={{ left: x, top: y, width: w, height: h, zIndex: z + 1, animationDelay: `${Math.min(order, 8) * 90}ms` }}
      role="button"
      tabIndex={0}
      onClick={() => onExpand(el.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onExpand(el.id);
      }}
    >
      {framed ? (
        <svg className="oh-board-element-frame" width={w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
          <RoughRect x={3} y={3} w={Math.max(w - 6, 10)} h={Math.max(h - 6, 10)} options={{ ...SKETCH, fill: "white", fillStyle: "solid", fillWeight: 0.5 }} />
        </svg>
      ) : null}
      <div className="oh-board-element-content">
        <BoardElementContent el={el} />
      </div>
    </div>
  );
}

function BoardElementContent({ el }: { el: BoardElement }) {
  if (el.kind === "shape") {
    const c = el.content as ShapeContent;
    return (
      <div className="oh-shape-wrap">
        <svg className="oh-shape-svg" viewBox="0 0 200 200" preserveAspectRatio="none">
          {c.shape === "ellipse" ? (
            <RoughEllipse x={4} y={4} w={192} h={192} options={SKETCH} />
          ) : (
            <RoughRect x={4} y={4} w={192} h={192} options={SKETCH} />
          )}
        </svg>
        <div className="oh-shape-label">{c.label}</div>
      </div>
    );
  }
  if (el.kind === "label") {
    const c = el.content as LabelContent;
    return <div className="oh-label">{c.text}</div>;
  }
  if (el.kind === "manim") {
    return <ManimView c={el.content as ManimContent} />;
  }
  const kind = el.kind as ArtifactKind;
  const content = el.content as ReteachContent;
  return (
    <div className="oh-artifact-card">
      <ArtifactView kind={kind} content={content} step={stepsOf(kind, content)} />
    </div>
  );
}
