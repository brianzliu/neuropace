import { Link } from "react-router-dom";
import type { Concept, Dashboard } from "../../lib/dashboardTypes";
import PracticeCard from "./PracticeCard";

interface SessionsSidebarProps {
  sessions: Dashboard["sessions"] | undefined;
  concepts: Concept[] | undefined;
  closed: number;
}

/**
 * Dashboard compartment 2: recent sessions sidebar.
 * Deep links stay on their current paths; Agent D's Library shell will
 * re-home them (redirect) without changing what this component renders.
 * Status is always dot + word, never color-alone; dots are static (no
 * pulsing) so reduced-motion is respected by construction.
 */

type SessionStatus = "running" | "ended" | "reviewed" | "created" | string;

function statusMeta(status: SessionStatus): { modifier: string; label: string } {
  if (status === "running") return { modifier: "is-running", label: "In progress" };
  if (status === "ended") return { modifier: "is-ended", label: "Ended" };
  if (status === "reviewed") return { modifier: "is-ended", label: "Reviewed" };
  if (status === "created") return { modifier: "is-other", label: "Created" };
  return { modifier: "is-other", label: status };
}

const ACTIONS = [
  { to: (id: string) => `/notes/${id}`, glyph: "✎", name: "Notes" },
  { to: (id: string) => `/review/${id}`, glyph: "✓", name: "Review" },
  { to: (id: string) => `/quiz/${id}`, glyph: "?", name: "Quiz" },
  { to: (id: string) => `/replay/${id}`, glyph: "↶", name: "Replay" },
] as const;
export default function SessionsSidebar({ sessions, concepts, closed }: SessionsSidebarProps) {
  return (
    <aside className="session-sidebar" aria-label="Sessions">
      <div className="dashboard-section-heading">
        <h2>Sessions</h2>
      </div>
      {sessions === undefined ? (
        <p className="small muted" role="status">
          Loading your saved moments…
        </p>
      ) : sessions.length ? (
        sessions.map((session) => {
          const meta = statusMeta(session.status);
          return (
          <article className="session-history-item" key={session.id}>
            <span className="session-date">
              {new Date(session.started_at * 1000).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
              <span className={`pill session-status ${meta.modifier}`}>
                <i aria-hidden="true" />
                {meta.label}
              </span>
            </span>
            <h3>{session.title}</h3>
            <div className="row session-actions">
              {session.status === "running" ? (
                <a className="live-open" href={`/live/${session.id}`} target="neuropace-studio">
                  <span aria-hidden="true">▶</span> Open live session
                </a>
              ) : (
                ACTIONS.map(action => (
                  <Link
                    key={action.name}
                    className="icon-button"
                    to={action.to(session.id)}
                    aria-label={`${action.name} for ${session.title}`}
                    title={`${action.name} for ${session.title}`}
                  >
                    <span aria-hidden="true">{action.glyph}</span>
                  </Link>
                ))
              )}
            </div>
          </article>
          );
        })
      ) : (
        <div className="session-placeholder">
          <span aria-hidden="true">↶</span>
          <p>Your first lecture starts a new thread.</p>
        </div>
      )}
      <PracticeCard concepts={concepts} closed={closed} />
    </aside>
  );
}
