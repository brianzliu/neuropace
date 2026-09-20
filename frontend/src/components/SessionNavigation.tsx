import { Link } from "react-router-dom";
import type { SessionPublic } from "../lib/types";
import { BackLink } from "./BackLink";
import SessionSwitcher from "./SessionSwitcher";

export type SessionTab = "notes" | "review" | "quiz" | "replay" | "artifacts";


export function sessionHref(sessionId: string, tab: SessionTab) {
  return `/library/${encodeURIComponent(sessionId)}/${tab}`;
}

/** Every lecture view shares the same navigation, including standalone and team links. */
export default function SessionNavigation({ sessionId, tab, title, sessions, titles, onSelect }: {
  sessionId: string;
  tab: SessionTab;
  title: string;
  sessions: SessionPublic[] | null;
  titles: Record<string, string>;
  onSelect: (id: string) => void;
}) {
  return <header className="session-navigation">
    <div className="library-head session-navigation-heading">
      <BackLink to="/" label="Back to Dashboard" />
      {sessions && sessions.length > 0 ? (
        <SessionSwitcher
          sessions={sessions} titles={titles} currentId={sessionId}
          currentTitle={title} onSelect={onSelect}
          asHeading
        />
      ) : (
        <h1 className="library-title">{title}</h1>
      )}
    </div>
    <nav className="library-tabs" aria-label="Lecture views">
      {(["notes", "review", "replay", "quiz"] as const).map(item => (
        <Link key={item} className={"library-tab btn btn-sm" + (tab === item ? " is-active" : "")} aria-current={tab === item ? "page" : undefined} to={sessionHref(sessionId, item)}>
          {{ notes: "Notes", review: "Study", replay: "Replay", quiz: "Quiz" }[item]}
        </Link>
      ))}
    </nav>
  </header>;
}
