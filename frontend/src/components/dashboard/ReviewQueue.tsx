import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";
import { mmss } from "../../lib/format";

interface ReviewQueueProps {
  concepts: Concept[] | undefined;
  closed: number;
  summary: string | undefined;
  organizationSource: string | undefined;
  organizing: boolean;
  hasLearner: boolean;
}

/**
 * Dashboard compartment 1: review overview + up-next concept list.
 * LLM summary/order is display-only; it never edits completion.
 * Empty state points at the toolbar NewSessionButton — no second launcher.
 */
export default function ReviewQueue({
  concepts,
  closed,
  summary,
  organizationSource,
  organizing,
  hasLearner,
}: ReviewQueueProps) {
  const loaded = concepts !== undefined;
  return (
    <>
      <section className="review-overview" aria-label="Review overview">
        <div className="overview-copy">
          <span className="section-kicker">A good place to start</span>
          <h2>
            {loaded && concepts.length
              ? `${concepts.length} concepts worth another look`
              : "Make room for the tricky bits."}
          </h2>
          <p>
            {summary ??
              (hasLearner
                ? "Loading your saved moments…"
                : "Capture a lecture, then come back here for notes and a focused review.")}
          </p>
          <span className="summary-source">
            {organizing
              ? "Organizing your review…"
              : organizationSource === "llm" || organizationSource === "cache"
                ? "Suggested order · based on your saved notes"
                : "Review queue · unfinished concepts first"}
          </span>
        </div>
        <div className="idea-sculpture" aria-hidden="true">
          <i />
          <i />
          <i />
          <span>✳</span>
        </div>
      </section>
      <section className="concept-section" aria-label="Up next">
        <div className="dashboard-section-heading">
          <h2>Up next</h2>
          <span>{closed} cleared in review</span>
        </div>
        {!loaded ? (
          <p className="muted" role="status">
            Loading your saved moments…
          </p>
        ) : concepts.length ? (
          <div className="concept-list">
            {concepts.map((concept, i) => (
              <article className="concept-row" key={concept.id}>
                <span className="concept-index" aria-hidden="true">
                  {i + 1}
                </span>
                <div>
                  <span className="small muted">
                    {concept.lecture} · {mmss(concept.t_start)}
                  </span>
                  <h3>{concept.title}</h3>
                  <p>{concept.description}</p>
                  <span className="concept-reason">{concept.reason}</span>
                </div>
                <div className="concept-actions">
                  <Link className="review-link" to={`/review/${concept.session_id}`}>
                    Review session
                  </Link>
                  <Link to={`/notes/${concept.session_id}`}>Source notes</Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="dashboard-empty">
            <div className="empty-stack" aria-hidden="true">
              <i />
              <i />
              <i>
                <span>✳</span>
              </i>
            </div>
            <h3>
              {closed ? "You’ve cleared your saved concepts." : "Nothing to untangle. Yet."}
            </h3>
            <p>
              {closed
                ? "Your next lecture can start whenever you’re ready."
                : "Moments you save during a lecture become your review list here."}
            </p>
            <p className="small muted">
              Use <strong>New session</strong> above to capture your first lecture.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
