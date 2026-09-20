import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";

/**
 * One tactile box per saved moment. Title and body come from the stored note.
 * Gentle severity: an `exhausted` moment (all re-teach forms tried, still open) gets a warmer
 * honey tint plus warm copy — never red, never alarming.
 */
export default function ConceptBox({ concept, index }: { concept: Concept; index: number }) {
  const needsExtraTime = concept.status === "exhausted";
  return (
    <article className={"concept-box" + (needsExtraTime ? " is-warm" : "")}>
      <div className="concept-box-top">
        <span className="concept-box-index" aria-hidden="true">{index + 1}</span>
        <div>
          <h3>{concept.title}</h3>
          {concept.description ? <p className="concept-box-description">{concept.description}</p> : null}
          {needsExtraTime ? <p className="concept-box-note is-warm-note">Could use a little extra time. Try a different explanation.</p> : null}
        </div>
      </div>
      <div className="concept-box-footer">
        <Link className="concept-source" to={`/library/${concept.session_id}/notes`} aria-label={`Open notes for ${concept.title}`}>
          {concept.lecture}
        </Link>
        <Link className="concept-review" to={`/library/${concept.session_id}/review`} aria-label={`Review ${concept.title}`}>
          Review
        </Link>
      </div>
    </article>
  );
}
