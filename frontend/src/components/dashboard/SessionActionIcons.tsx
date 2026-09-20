import { Link } from "react-router-dom";

/** One entry into the guided study flow. The tutor chooses the activity after this point. */
export default function SessionActionIcons({ sessionId, title }: { sessionId: string; title: string; showQuiz?: boolean }) {
  return (
    <div className="row session-actions">
      <Link className="btn btn-primary" to={`/library/${sessionId}/review`} aria-label={`Study ${title}`}>
        Study
      </Link>
    </div>
  );
}
