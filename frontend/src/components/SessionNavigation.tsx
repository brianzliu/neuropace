import type { SessionPublic } from "../lib/types";
import { BackLink } from "./BackLink";
import SessionSwitcher from "./SessionSwitcher";

export type SessionTab = "notes" | "review" | "quiz" | "replay" | "artifacts";


export function sessionHref(sessionId: string, tab: SessionTab) {
  return `/library/${encodeURIComponent(sessionId)}/${tab}`;
}

/** Every lecture view shares the same navigation, including standalone and team links. */
export default function SessionNavigation({ sessionId, title, sessions, titles, onSelect }: {
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

  </header>;
}
