import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../lib/api";

// Persistent main-window tab bar (Agent A). Studio popup (/session/new),
// live (/live/*) and replay (legacy /replay/* + /library/:id/replay) hide
// this bar — see App.tsx `showTabs`.
export default function TopTabs() {
  const { pathname } = useLocation();
  const [latestSessionId, setLatestSessionId] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.sessions()
      .then(({ sessions }) => { if (live) setLatestSessionId(sessions[0]?.id ?? null); })
      .catch(() => { /* Offline or unreachable: tab falls back to the picker. */ });
    return () => { live = false; };
  }, []);

  const isLibraryPath =
    pathname === "/library" ||
    pathname.startsWith("/library/") ||
    pathname.startsWith("/notes/") ||
    pathname.startsWith("/review/") ||
    pathname.startsWith("/replay/") ||
    pathname.startsWith("/quiz/");
  const isInsightsPath =
    pathname === "/insights" ||
    pathname.startsWith("/insights/") ||
    pathname.startsWith("/tally/") ||
    pathname.startsWith("/lossmap/");
  const isDashboard = pathname === "/";

  return (
    <nav className="toptabs" aria-label="Primary">
      <Link to="/" aria-current={isDashboard ? "page" : undefined}>
        Dashboard
      </Link>
      <Link
        to={latestSessionId ? `/library/${latestSessionId}` : "/library"}
        aria-current={isLibraryPath ? "page" : undefined}
      >
        Library
      </Link>
      <Link to="/insights" aria-current={isInsightsPath ? "page" : undefined}>
        Insights
      </Link>
    </nav>
  );
}
