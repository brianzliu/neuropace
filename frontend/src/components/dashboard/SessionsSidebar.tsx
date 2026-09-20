import { Link } from "react-router-dom";
import type { ReactNode } from "react";
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

/** Stroke-consistent action icons (24-grid, round caps, 2px stroke).
 *  Text glyphs varied wildly in weight and optical size; these match. */
function ActionIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

const ACTIONS = [
  { to: (id: string) => `/notes/${id}`, name: "Notes", paths: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>) },
  { to: (id: string) => `/review/${id}`, name: "Review", paths: (<><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></>) },
  { to: (id: string) => `/quiz/${id}`, name: "Quiz", paths: (<><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" /></>) },
  { to: (id: string) => `/replay/${id}`, name: "Replay", paths: (<><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>) },
] as const;
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
                    <span aria-hidden="true"><ActionIcon>{action.paths}</ActionIcon></span>
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
        </div>
      )}
      <PracticeCard concepts={concepts} closed={closed} />
    </aside>
  );
}
