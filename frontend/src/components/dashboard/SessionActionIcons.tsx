import { Link } from "react-router-dom";
import { SESSION_ICONS, SessionIconArt } from "../../lib/sessionIcons";

/** Shared by Home's session sidebar and the Lectures history list. Links go straight to the
 *  canonical /library/:id/:tab paths so every entry lands inside the Library shell with its tab
 *  switcher. (The legacy /notes and /review paths redirect there, but /quiz and /replay render
 *  standalone — hence the switcher used to appear only sometimes.) */
const ACTIONS = (["notes", "review", "quiz", "replay"] as const).map((kind) => ({
  kind,
  to: (id: string) => `/library/${id}/${kind}`,
  ...SESSION_ICONS[kind],
}));

export default function SessionActionIcons({ sessionId, title, showQuiz = true }: { sessionId: string; title: string; showQuiz?: boolean }) {
  return (
    <div className="row session-actions">
      {ACTIONS.filter((a) => showQuiz || a.kind !== "quiz").map((action) => (
        <Link
          key={action.kind}
          className={`icon-button ${action.tone}`}
          to={action.to(sessionId)}
          aria-label={`${action.name} for ${title}`}
          title={`${action.name} for ${title}`}
        >
          <SessionIconArt kind={action.kind} />
        </Link>
      ))}
    </div>
  );
}
