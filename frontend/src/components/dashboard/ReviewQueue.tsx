import type { Concept } from "../../lib/dashboardTypes";
import BrainMascot from "./BrainMascot";
import ConceptBox from "./ConceptBox";

interface ReviewQueueProps {
  concepts: Concept[] | undefined;
  closed: number;
  /** Queue-level summary from GET /api/learners/:id/dashboard. Display only. */
  summary?: string;
  /** "llm" | "cache" when the model organized the queue; anything else is the rules fallback. */
  organizationSource?: string;
  /** True while the organize pass is in flight (the first response is deterministic). */
  organizing?: boolean;
}

export default function ReviewQueue({ concepts, closed, organizationSource }: ReviewQueueProps) {
  const organized = organizationSource === "llm" || organizationSource === "cache";
  return (
    <section className="concept-section" aria-label="Moments to review">
      <div className="dashboard-section-heading">
        <h2>{concepts?.length
          ? `${concepts.length} moment${concepts.length === 1 ? "" : "s"} worth another look`
          : "Your next discovery starts here."}</h2>
      </div>
      {!concepts ? <div className="mascot-row" role="status"><BrainMascot art="think" size={56} /><p className="muted">Loading…</p></div>
        : concepts.length ? (
          <>
            <div className="concept-list">
              {concepts.map((concept, i) => (
                <ConceptBox key={concept.id} concept={concept} index={i} organized={organized} />
              ))}
            </div>
          </>
        ) : (
          <div className="dashboard-empty">
            {closed ? <BrainMascot art="cheer" size={84} /> : <BrainMascot art="wave" size={84} />}
            <h3>{closed ? "You've cleared your saved moments." : "Nothing to untangle. Yet."}</h3>
          </div>
        )}
    </section>
  );
}
