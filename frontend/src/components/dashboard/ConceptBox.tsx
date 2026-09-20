import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";

/** Backend fallback reasons (dashboard_data) — never shown as if model-written. */
const FALLBACK_REASONS = new Set(["Not reviewed yet", "Try another explanation"]);

interface ConceptBoxProps {
  concept: Concept;
  index: number;
  /** True only when the queue itself came back ordered by the model (llm/cache). */
  organized: boolean;
}

/**
 * One tactile box per saved concept. Title and body come from the stored note. When the model
 * ordered the queue, its per-concept reason is available as a tooltip on the numbered badge and as
 * a colored left border — not as its own sentence, which read as filler next to the description.
 *
 * Gentle severity: an `exhausted` concept (all re-teach forms tried, still
 * open) gets a warmer honey tint plus warm copy — never red, never alarming.
 */
export default function ConceptBox({ concept, index, organized }: ConceptBoxProps) {
  const suggested = organized && !!concept.reason && !FALLBACK_REASONS.has(concept.reason);
  const needsExtraTime = concept.status === "exhausted";
  return (
    <article className={"concept-box" + (needsExtraTime ? " is-warm" : "") + (suggested ? " has-suggestion" : "")}>
      <div className="concept-box-top">
        {organized ? (
          <span className="concept-box-index" aria-hidden="true" title={suggested ? concept.reason : "Suggested order"}>{index + 1}</span>
        ) : (
          <span className="concept-box-dot" aria-hidden="true" />
        )}
        <div>
          <h3>{concept.title}</h3>
          {concept.description ? <p className="concept-box-description">{concept.description}</p> : null}
          {needsExtraTime ? <p className="concept-box-note is-warm-note">Could use a little extra time. Try a different explanation.</p> : null}
        </div>
      </div>
      <div className="concept-box-footer">
        <Link
          className="concept-source"
          to={`/notes/${concept.session_id}`}
          aria-label={`Open notes for ${concept.title}`}
        >
          {concept.lecture}
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
