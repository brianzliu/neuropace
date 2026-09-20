import { Link } from "react-router-dom";
import type { SessionPublic } from "../lib/types";
import { BackLink } from "./BackLink";
import SessionSwitcher from "./SessionSwitcher";

export type SessionTab = "notes" | "review" | "quiz" | "replay" | "artifacts";
const sections: { id: SessionTab; label: string }[] = [
  { id: "notes", label: "Notes" },
  { id: "review", label: "Review" },
  { id: "quiz", label: "Quiz" },
  { id: "replay", label: "Replay" },
  { id: "artifacts", label: "Explanations" },
];

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
      <BackLink to="/lectures" label="Back to Lectures" />
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
    <nav className="library-tabs" aria-label="Session sections">
      {sections.map(section => <Link key={section.id}
        to={sessionHref(sessionId, section.id)}
        className={`library-tab${tab === section.id ? " active" : ""}`}
        aria-current={tab === section.id ? "page" : undefined}
      >{section.label}</Link>)}
    </nav>
  </header>;
}
