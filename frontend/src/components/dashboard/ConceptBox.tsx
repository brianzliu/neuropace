import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";
import { mmss } from "../../lib/format";

/** Backend fallback reasons (dashboard_data) — never shown as if model-written. */
const FALLBACK_REASONS = new Set(["Not reviewed yet", "Try another explanation"]);

interface ConceptBoxProps {
  concept: Concept;
  index: number;
  /** True only when the queue itself came back ordered by the model (llm/cache). */
  organized: boolean;
}

/**
 * One tactile box per saved concept. Title and body come from the stored note;
 * when the model ordered the queue, its short per-concept reason is shown as a
 * labelled suggestion. Nothing here is inferred by the frontend.
 */
export default function ConceptBox({ concept, index, organized }: ConceptBoxProps) {
  const suggested = organized && !!concept.reason && !FALLBACK_REASONS.has(concept.reason);
  return (
    <article className="concept-box">
      <div className="concept-box-top">
        <span className="concept-box-index" aria-hidden="true">{index + 1}</span>
        <div>
          <h3>{concept.title}</h3>
          {concept.description ? <p className="concept-box-description">{concept.description}</p> : null}
          {suggested ? <p className="concept-box-note is-suggested">Suggested order — {concept.reason}</p> : null}
          {concept.status === "exhausted" && !suggested ? <p className="concept-box-note">Try a different explanation.</p> : null}
        </div>
      </div>
      <div className="concept-box-footer">
        <Link
          className="concept-source"
          to={`/notes/${concept.session_id}`}
          aria-label={`Open notes for ${concept.title}`}
        >
          {concept.lecture} · saved at {mmss(concept.t_start)}
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
