import { Link, useLocation } from "react-router-dom";

// Persistent main-window tab bar (Agent A). Studio popup (/session/new),
// live (/live/*) and replay (legacy /replay/* + /library/:id/replay) hide
// this bar — see App.tsx `showTabs`.
export default function TopTabs() {
  const { pathname } = useLocation();
  const isLecturesPath =
    pathname === "/lectures" ||
    pathname === "/library" ||
    pathname.startsWith("/library/") ||
    pathname.startsWith("/notes/") ||
    pathname.startsWith("/review/") ||
    pathname.startsWith("/replay/") ||
    pathname.startsWith("/quiz/") || pathname.startsWith("/lecture") || pathname.startsWith("/done/");
  const isInsightsPath =
    pathname === "/insights" ||
    pathname.startsWith("/insights/") ||
    pathname.startsWith("/tally/") ||
    pathname.startsWith("/lossmap/") ||
    pathname === "/you";
  const isDashboard = pathname === "/";

  return (
    <nav className="toptabs" aria-label="Primary">
      <Link to="/" aria-current={isDashboard ? "page" : undefined}>
        Dashboard
      </Link>
      <Link
        to="/lectures"
        aria-current={isLecturesPath ? "page" : undefined}
      >
        Lectures
      </Link>
      <Link to="/insights" aria-current={isInsightsPath ? "page" : undefined}>
        Insights
      </Link>
    </nav>
  );
}
