import { Link } from "react-router-dom";
import type { Dashboard } from "../../lib/dashboardTypes";

interface SessionsSidebarProps {
  sessions: Dashboard["sessions"] | undefined;
}

/**
 * Dashboard compartment 2: recent sessions sidebar.
 * Deep links stay on their current paths; Agent D's Library shell will
 * re-home them (redirect) without changing what this component renders.
 */
export default function SessionsSidebar({ sessions }: SessionsSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="Your sessions">
      <div className="dashboard-section-heading">
        <h2>Your sessions</h2>
        <span>{sessions?.length ?? 0}</span>
      </div>
      <p className="small muted">Recent lectures and places to pick up.</p>
      {sessions === undefined ? (
        <p className="small muted" role="status">
          Loading your saved moments…
        </p>
      ) : sessions.length ? (
        sessions.map((session) => (
          <article className="session-history-item" key={session.id}>
            <span className="session-date">
              {new Date(session.started_at * 1000).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
              <span>{session.status === "running" ? "In progress" : session.status}</span>
            </span>
            <h3>{session.title}</h3>
            <div className="row">
              {session.status === "running" ? (
                <a href={`/live/${session.id}`} target="reflow-studio">
                  Open live session
                </a>
              ) : (
                <>
                  <Link to={`/notes/${session.id}`}>Notes</Link>
                  <Link to={`/review/${session.id}`}>Review</Link>
                  <Link to={`/replay/${session.id}`}>Replay</Link>
                </>
              )}
            </div>
          </article>
        ))
      ) : (
        <div className="session-placeholder">
          <span aria-hidden="true">↶</span>
          <p>Your first lecture starts a new thread.</p>
        </div>
      )}
      <div className="sidebar-note">
        <span aria-hidden="true">✳</span>
        <p>
          One moment at a time.
          <br />
          You don’t have to catch everything.
        </p>
      </div>
    </aside>
  );
}
