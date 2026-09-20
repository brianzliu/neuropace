import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";

/** Backend fallback reasons (dashboard_data) — never shown as if model-written. */
const FALLBACK_REASONS = new Set(["Not reviewed yet", "Try another explanation"]);

interface ConceptBoxProps {
  concept: Concept;
  index: number;
  /** True only when the queue itself came back ordered by the model (llm/cache). */
  organized: boolean;
  /** Session calendar date (e.g. "Sep 19"), resolved by the parent. Absent when unknown. */
  dateLabel?: string;
}

/**
 * One tactile box per saved concept. Title and body come from the stored note;
 * when the model ordered the queue, its short per-concept reason is shown as a
 * labelled suggestion. Nothing here is inferred by the frontend.
 *
 * Gentle severity: an `exhausted` concept (all re-teach forms tried, still
 * open) gets a warmer honey tint plus warm copy — never red, never alarming.
 */
export default function ConceptBox({ concept, index, organized, dateLabel }: ConceptBoxProps) {
  const suggested = organized && !!concept.reason && !FALLBACK_REASONS.has(concept.reason);
  const needsExtraTime = concept.status === "exhausted";
  return (
    <article className={"concept-box" + (needsExtraTime ? " is-warm" : "")}>
      <div className="concept-box-top">
        {organized ? (
          <span className="concept-box-index" aria-hidden="true" title="Suggested order">{index + 1}</span>
        ) : (
          <span className="concept-box-dot" aria-hidden="true" />
        )}
        <div>
          <h3>{concept.title}</h3>
          {concept.description ? <p className="concept-box-description">{concept.description}</p> : null}
          {suggested ? <p className="concept-box-note is-suggested">Suggested order — {concept.reason}</p> : null}
          {needsExtraTime && !suggested ? <p className="concept-box-note is-warm-note">Could use a little extra time — try a different explanation.</p> : null}
        </div>
      </div>
      <div className="concept-box-footer">
        <Link
          className="concept-source"
          to={`/notes/${concept.session_id}`}
          aria-label={`Open notes for ${concept.title}`}
        >
          {concept.lecture}
          {dateLabel ? <span>{dateLabel}</span> : null}
        </Link>
        <Link
          className="concept-review"
          to={`/review/${concept.session_id}`}
          aria-label={`Review session: ${concept.title}`}
        >
          Review
        </Link>
      </div>
    </article>
  );
}
