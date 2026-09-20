import type { Concept } from "../../lib/dashboardTypes";
import BrainMascot from "./BrainMascot";
import ConceptBox from "./ConceptBox";

/** Every open moment across the learner's lectures, tricky ones first (server order). */
export default function ReviewQueue({ concepts, closed }: { concepts: Concept[] | undefined; closed: number }) {
  return (
    <section className="concept-section" aria-label="Moments to review">
      <div className="dashboard-section-heading">
        <h2>{concepts?.length
          ? `${concepts.length} moment${concepts.length === 1 ? "" : "s"} worth another look`
          : "Your next discovery starts here."}</h2>
        {closed ? <span>{closed} cleared</span> : null}
      </div>
      {!concepts ? <div className="mascot-row" role="status"><BrainMascot art="think" size={56} /><p className="muted">Loading…</p></div>
        : concepts.length ? (
          <div className="concept-list">
            {concepts.map((concept, i) => (
              <ConceptBox key={concept.id} concept={concept} index={i} />
            ))}
          </div>
        ) : (
          <div className="dashboard-empty">
            {closed ? <BrainMascot art="cheer" size={84} /> : <BrainMascot art="wave" size={84} />}
            <h3>{closed ? "You've cleared your saved moments." : "Nothing to untangle. Yet."}</h3>
          </div>
        )}
    </section>
  );
}
