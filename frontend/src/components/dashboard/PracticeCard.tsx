import { Link } from "react-router-dom";
import type { Concept } from "../../lib/dashboardTypes";

interface PracticeCardProps {
  concepts: Concept[] | undefined;
  closed: number;
}

/**
 * Sidebar practice card. Replaces the old static quote block with real,
 * honest counts: open concepts link into review, cleared queues link to
 * the library. No mastery percentages, no streaks — counts only.
 */
export default function PracticeCard({ concepts, closed }: PracticeCardProps) {
  if (concepts === undefined) {
    return (
      <div className="practice-card" aria-label="Practice">
        <h3>Practice</h3>
        <p role="status">Loading…</p>
      </div>
    );
  }
  if (concepts.length > 0) {
    const first = concepts[0];
    return (
      <div className="practice-card" aria-label="Practice">
        <h3>
          {concepts.length} concept{concepts.length === 1 ? "" : "s"} ready
        </h3>
        <p>Start with “{first.title}”.</p>
        <Link className="practice-go" to={`/library/${first.session_id}/review`}>
          Practice now
        </Link>
      </div>
    );
  }
  return (
    <div className="practice-card" aria-label="Practice">
      <h3>{closed ? "All caught up." : "Nothing saved yet."}</h3>
      <Link className="practice-go" to="/library">
        Open library
      </Link>
    </div>
  );
}
