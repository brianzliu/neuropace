import { Link } from "react-router-dom";
import type { Dashboard } from "../../lib/dashboardTypes";

/**
 * Every lecture you listened to, newest first: the one history list in the app. Status is a tinted
 * wash on the card (word kept screen-reader-only); the summary line is the moment count.
 */
export default function SessionsSidebar({ sessions }: { sessions: Dashboard["sessions"] | undefined }) {
  return (
    <aside className="session-sidebar" aria-label="Your lectures">
      <div className="dashboard-section-heading">
        <h2>Your lectures</h2>
      </div>
      {sessions === undefined ? (
        <p className="small muted" role="status">Loading…</p>
      ) : sessions.length ? (
        <div className="session-list">
          {sessions.map((session) => {
            const statusClass = session.status === "running" ? "is-running"
              : session.status === "reviewed" ? "is-reviewed"
              : session.status === "ended" ? "is-ended" : "is-other";
            const statusLabel = session.status === "running" ? "In progress"
              : session.status === "reviewed" ? "Reviewed"
              : session.status === "ended" ? "Ended"
              : session.status === "created" ? "Created" : session.status;
            const when = new Date(session.started_at * 1000);
            return (
              <article className={`session-history-item ${statusClass}`} key={session.id}>
                <span className="session-date-tab" title={when.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}>
                  {when.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </span>
                <span className="visually-hidden">{statusLabel}</span>
                <h3>{session.title}</h3>
                {session.summary ? <p className="session-summary">{session.summary}</p> : null}
                {session.status === "running" ? (
                  <div className="row session-actions">
                    <Link className="live-open" to={`/live/${session.id}`}>
                      <span aria-hidden="true">▶</span> Open live session
                    </Link>
                  </div>
                ) : (
                  <div className="row session-links">
                    <Link to={`/library/${session.id}/notes`}>Notes</Link>
                    <Link className="btn btn-primary btn-sm" to={`/library/${session.id}/review`} aria-label={`Study ${session.title}`}>Study</Link>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="session-placeholder">
          <span aria-hidden="true">↶</span>
        </div>
      )}
    </aside>
  );
}
