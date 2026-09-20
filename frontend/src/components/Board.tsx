import { useState } from "react";
import ArtifactView, { stepsOf } from "./ArtifactView";
import ManimView from "./ManimView";
import type { ArrowContent, ArtifactKind, BoardElement, LabelContent, ManimContent, ReteachContent, ShapeContent } from "../lib/types";

const BOARD_W = 4000;
const BOARD_H = 3000;

/** The shared board (docs/PRODUCT.md §5a): the agent's elements laid out on a bounded canvas. Position/zoom is
 * the only freedom the model has beyond content — every element is one of the same validated templates used
 * elsewhere (§4) or one of three small annotation primitives (shape, arrow, label). */
export default function Board({ elements, onExpand }: { elements: BoardElement[]; onExpand: (id: string) => void }) {
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
            <defs>
              <marker id="oh-arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
                <path d="M0,0 L0,6 L9,3 z" fill="currentColor" />
              </marker>
            </defs>
            {arrows.map((a) => {
              const c = a.content as ArrowContent;
              const from = centerOf(c.from_id);
              const to = centerOf(c.to_id);
              if (!from || !to) return null;
              return (
                <g key={a.id} className="oh-arrow">
                  <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} markerEnd="url(#oh-arrowhead)" />
                  <text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 8}>
                    {c.label}
                  </text>
                </g>
              );
            })}
          </svg>
          {boxes.length === 0 ? <div className="oh-board-empty label-2">Ask a question to start filling the board.</div> : null}
          {boxes.map((el) => (
            <BoardElementWrapper key={el.id} el={el} onExpand={onExpand} />
          ))}
        </div>
      </div>
    </div>
  );
}

function BoardElementWrapper({ el, onExpand }: { el: BoardElement; onExpand: (id: string) => void }) {
  const { x, y, w, h, z } = el.envelope;
  return (
    <div
      className="oh-board-element"
      style={{ left: x, top: y, width: w, height: h, zIndex: z + 1 }}
      role="button"
      tabIndex={0}
      onClick={() => onExpand(el.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onExpand(el.id);
      }}
    >
      <BoardElementContent el={el} />
    </div>
  );
}

function BoardElementContent({ el }: { el: BoardElement }) {
  if (el.kind === "shape") {
    const c = el.content as ShapeContent;
    return <div className={`oh-shape oh-shape-${c.shape}`}>{c.label}</div>;
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
