import { Link, useLocation } from "react-router-dom";

/** The one back affordance for session views: same icon, same top-left spot, same label.
 *  Library tabs already get this from LibraryFrame; standalone session views render
 *  SessionBack so Notes, Review, Quiz, Replay, and Office Hours always show a back control. */
export function BackLink({ to, label, className }: { to: string; label: string; className?: string }) {
  return (
    <Link
      className={"icon-button back-link" + (className ? " " + className : "")}
      to={to}
      aria-label={label}
      title={label}
    >
      <span aria-hidden="true">←</span>
    </Link>
  );
}

/** Standalone session view (no library shell): learners go to the Dashboard, the team to Team. */
export default function SessionBack({ className }: { className?: string }) {
  const { pathname } = useLocation();
  const team = pathname.startsWith("/team");
  return (
    <BackLink
      className={className}
      to={team ? "/team" : "/"}
      label={team ? "Back to Team" : "Back to Dashboard"}
    />
  );
}
