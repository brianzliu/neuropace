import type { Concept, Dashboard } from "../../lib/dashboardTypes";
import PracticeCard from "./PracticeCard";
import SessionActionIcons from "./SessionActionIcons";

interface SessionsSidebarProps {
  sessions: Dashboard["sessions"] | undefined;
  concepts: Concept[] | undefined;
  closed: number;
}

/**
 * Dashboard compartment 2: recent sessions sidebar.
 * Deep links stay on their current paths; Agent D's Library shell will
 * re-home them (redirect) without changing what this component renders.
 * No status pills (user request): a running session shows an
 * "Open live session" link instead of the icon row, so state is still
 * communicated without a tag in the corner.
 */
export default function SessionsSidebar({ sessions, concepts, closed }: SessionsSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="Sessions">
      <div className="dashboard-section-heading">
        <h2>Sessions</h2>
      </div>
      {sessions === undefined ? (
        <p className="small muted" role="status">
          Loading…
        </p>
      ) : sessions.length ? (
        <div className="session-list">
          {sessions.map((session) => {
          // Color speaks: status lives on the card as a class (tinted wash),
          // with the word kept screen-reader-only so color is never the sole
          // carrier for assistive tech.
          const statusClass = session.status === "running" ? "is-running"
            : session.status === "reviewed" ? "is-reviewed"
            : session.status === "ended" ? "is-ended" : "is-other";
          const statusLabel = session.status === "running" ? "In progress"
            : session.status === "reviewed" ? "Reviewed"
            : session.status === "ended" ? "Ended"
            : session.status === "created" ? "Created" : session.status;
          return (
          <article className={`session-history-item ${statusClass}`} key={session.id}>
            <span className="session-date">
              {new Date(session.started_at * 1000).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
              <span className="visually-hidden">, {statusLabel}</span>
            </span>
            <h3>{session.title}</h3>
            {session.summary ? <p className="session-summary">{session.summary}</p> : null}
            {session.status === "running" ? (
              <div className="row session-actions">
                <a className="live-open" href={`/live/${session.id}`} target="neuropace-studio">
                  <span aria-hidden="true">▶</span> Open live session
                </a>
              </div>
            ) : (
              <SessionActionIcons sessionId={session.id} title={session.title} />
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
      <PracticeCard concepts={concepts} closed={closed} />
    </aside>
  );
}
