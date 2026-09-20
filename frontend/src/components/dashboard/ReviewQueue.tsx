import type { Concept } from "../../lib/dashboardTypes";
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
    <section className="concept-section" aria-label="Concepts to review">
      <div className="dashboard-section-heading">
        <h2>{concepts?.length
          ? `${concepts.length} concept${concepts.length === 1 ? "" : "s"} worth another look`
          : "Your next discovery starts here."}</h2>
      </div>
      {!concepts ? <p className="muted" role="status">Loading…</p>
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
            <div className="empty-stack" aria-hidden="true"><i /><i /><i><span>✳</span></i></div>
            <h3>{closed ? "You've cleared your saved concepts." : "Nothing to untangle. Yet."}</h3>
          </div>
        )}
    </section>
  );
}
