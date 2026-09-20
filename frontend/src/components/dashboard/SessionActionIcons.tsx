import { Link } from "react-router-dom";
import type { ReactNode } from "react";

/** Stroke-consistent action icons (24-grid, round caps, 2px stroke), shared by Home's session
 *  sidebar and the Lectures history list. Links go straight to the canonical /library/:id/:tab
 *  paths so every entry lands inside the Library shell with its tab switcher. (The legacy
 *  /notes and /review paths redirect there, but /quiz and /replay render standalone — hence
 *  the switcher used to appear only sometimes.) */
function ActionIcon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

const ACTIONS = [
  { to: (id: string) => `/library/${id}/notes`, name: "Notes", tone: "tone-notes", img: "/icon-notes.png", paths: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>) },
  { to: (id: string) => `/library/${id}/review`, name: "Review", tone: "tone-review", img: "/icon-review.png", paths: (<><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></>) },
  { to: (id: string) => `/library/${id}/quiz`, name: "Quiz", tone: "tone-quiz", img: "/icon-quiz.png", paths: (<><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="m9 14 2 2 4-4" /></>) },
  { to: (id: string) => `/library/${id}/replay`, name: "Replay", tone: "tone-replay", img: "/icon-replay.png", paths: (<><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>) },
] as const;

export default function SessionActionIcons({ sessionId, title, showQuiz = true }: { sessionId: string; title: string; showQuiz?: boolean }) {
  return (
    <div className="row session-actions">
      {ACTIONS.filter((a) => showQuiz || a.name !== "Quiz").map((action) => (
        <Link
          key={action.name}
          className={`icon-button ${action.tone}`}
          to={action.to(sessionId)}
          aria-label={`${action.name} for ${title}`}
          title={`${action.name} for ${title}`}
        >
            <span className="action-art" aria-hidden="true"><ActionIcon>{action.paths}</ActionIcon><img src={action.img} alt="" onError={(e) => { e.currentTarget.remove(); }} /></span>
        </Link>
      ))}
    </div>
  );
}
