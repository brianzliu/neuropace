import { useId, useState } from "react";
import type { SceneGraph } from "../lib/types";
import Diagram from "./Diagram";

/** Alternate readings of the same tutor explanation, with no generated markup or scripts. */
export default function Whiteboard({ graph, step }: { graph: SceneGraph; step: number }) {
  const [tab, setTab] = useState<"Board" | "Steps" | "Text">("Board");
  const id = useId();
  const caption = graph.steps[Math.min(step, graph.steps.length - 1)]?.caption;
  const labels = new Map(graph.nodes.map(node => [node.id, node.label]));
  return <section className="concept-whiteboard" aria-label={graph.title}>
    <div className="whiteboard-toolbar">
      <h3>{graph.title}</h3>
      <div className="whiteboard-tabs" role="tablist" aria-label="Explanation view">
        {(["Board", "Steps", "Text"] as const).map((name, index, tabs) => <button
          key={name} id={`${id}-${name}`} role="tab" aria-selected={tab === name}
          aria-controls={`${id}-panel`} tabIndex={tab === name ? 0 : -1}
          onClick={() => setTab(name)} onKeyDown={event => {
            const next = event.key === "ArrowRight" ? tabs[(index + 1) % tabs.length]
              : event.key === "ArrowLeft" ? tabs[(index + tabs.length - 1) % tabs.length]
              : event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[tabs.length - 1] : null;
            if (next) { event.preventDefault(); setTab(next); document.getElementById(`${id}-${next}`)?.focus(); }
          }}>{name}</button>)}
      </div>
    </div>
    <div className="whiteboard-content" id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${tab}`} tabIndex={0}>
      {tab === "Board" ? <><Diagram graph={graph} step={step} />{caption && <p className="whiteboard-caption" aria-live="polite">{caption}</p>}</>
        : tab === "Steps" ? <ol className="whiteboard-steps">{graph.steps.map((item, index) => <li key={index} aria-current={index === step ? "step" : undefined}>{item.caption}</li>)}</ol>
        : <div className="whiteboard-text">
            {graph.steps.map((item, index) => <p key={index}>{item.caption}</p>)}
            {graph.edges.length > 0 && <ul>{graph.edges.map((edge, index) => <li key={index}>{labels.get(edge.from_id) ?? edge.from_id} → {edge.label} → {labels.get(edge.to_id) ?? edge.to_id}</li>)}</ul>}
          </div>}
    </div>
  </section>;
}
