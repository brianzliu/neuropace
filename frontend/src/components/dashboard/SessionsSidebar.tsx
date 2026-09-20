import type { Concept, Dashboard } from "../../lib/dashboardTypes";
import PracticeCard from "./PracticeCard";
import SessionActionIcons from "./SessionActionIcons";

interface SessionsSidebarProps {
  sessions: Dashboard["sessions"] | undefined;
  concepts: Concept[] | undefined;
  closed: number;
}

/**
 * Dashboard compartment 2: every lecture you listened to, newest first. This is the one history
 * list in the app (the separate Lectures page was the same rows under another name).
 * No status pills (user request): a running session shows an
 * "Open live session" link instead of the icon row, so state is still
 * communicated without a tag in the corner.
 */
export default function SessionsSidebar({ sessions, concepts, closed }: SessionsSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="Your lectures">
      <div className="dashboard-section-heading">
        <h2>Your lectures</h2>
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
            <span className="session-date-tab" title={new Date(session.started_at * 1000).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}>
              {new Date(session.started_at * 1000).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
            </span>
            <span className="visually-hidden">{statusLabel}</span>
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
