import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";
import { mmss } from "../../lib/format";

interface ReviewQueueProps {
  concepts: Concept[] | undefined;
  closed: number;
  hasLearner: boolean;
}

export default function ReviewQueue({ concepts, closed, hasLearner }: ReviewQueueProps) {
  return (
    <section className="concept-section" aria-label="Concepts to review">
      <div className="dashboard-section-heading">
        <h2>{concepts?.length
          ? `${concepts.length} concept${concepts.length === 1 ? "" : "s"} worth another look`
          : "Your next discovery starts here."}</h2>
      </div>
      {!hasLearner ? <p className="muted" role="status">Loading your saved moments…</p>
        : !concepts ? <p className="muted" role="status">Loading your saved moments…</p>
        : concepts.length ? (
          <div className="concept-list">
            {concepts.map((concept, i) => (
              <article className="concept-row" key={concept.id}>
                <span className="concept-index" aria-hidden="true">{i + 1}</span>
                <div>
                  <h3>{concept.title}</h3>
                  <p>{concept.description}</p>
                  <Link className="concept-source" to={`/notes/${concept.session_id}`}>
                    {concept.lecture} · saved at {mmss(concept.t_start)}
                  </Link>
                  {concept.status === "exhausted" && <p className="concept-reason">Try a different explanation.</p>}
                </div>
                <div className="concept-actions">
                  <Link className="review-link" to={`/review/${concept.session_id}`}>Review session</Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="dashboard-empty">
            <div className="empty-stack" aria-hidden="true"><i /><i /><i><span>✳</span></i></div>
            <h3>{closed ? "You've cleared your saved concepts." : "Nothing to untangle. Yet."}</h3>
            <p>{closed ? "Your next lecture can start whenever you're ready." : "Start a session. Moments you save become your review list here."}</p>
          </div>
        )}
    </section>
  );
}
