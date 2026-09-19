import Appearance from "./components/Appearance";
import LocalConnection from "./components/LocalConnection";
import TopTabs from "./components/TopTabs";
import { useLayoutEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import Home from "./views/Home";
import Setup from "./views/Setup";
import Live from "./views/Live";
import Notes from "./views/Notes";
import Review from "./views/Review";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import Library from "./views/Library";
import Insights from "./views/Insights";

// Legacy deep links redirect into the new shells (Agent A decision,
// documented here): /notes|review|replay|quiz/:id -> /library/:id/<tab>
// (nested route, same component instance), /tally/:learnerId ->
// /insights?learner=<id>, /lossmap/:lectureId -> /insights?lecture=<id>
// (Agent E's Insights reads ?learner= / ?lecture=). /live/:id stays in the
// Studio popup and is NOT moved into Library.
function RedirectToLibraryTab({ tab }: { tab: string }) {
  const { sessionId = "" } = useParams();
  return <Navigate to={`/library/${sessionId}/${tab}`} replace />;
}

function RedirectToInsights({ param }: { param: "learner" | "lecture" }) {
  const params = useParams();
  const id = param === "learner" ? params.learnerId ?? "" : params.lectureId ?? "";
  return <Navigate to={`/insights?${param}=${encodeURIComponent(id)}`} replace />;
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    try { const saved = localStorage.getItem("reflow.theme"); return saved && ["pocket", "paper", "orbit"].includes(saved) ? saved : "pocket"; }
    catch { return "pocket"; }
  });
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("reflow.theme", theme); } catch { /* Theme still works without storage. */ }
  }, [theme]);
  const loc = useLocation();
  const pathname = loc.pathname;
  const isStudio = pathname === "/session/new" || pathname.startsWith("/session/new/");
  const isLive = pathname.startsWith("/live");
  const isReplay = pathname.startsWith("/replay") || /^\/library\/[^/]+\/replay\/?$/.test(pathname);
  // Main window shows tabs; Studio popup (/session/new), live, and replay
  // (immersive playback, legacy or nested) do not. Compact slim header
  // follows the same split.
  const showTabs = !(isStudio || isLive || isReplay);
  const compact = !showTabs;
  return (
    <div className={"app" + (compact ? " app-compact" : "")}>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-dot" /> Neurospace
        </Link>
        <nav className="topnav" aria-label="Main navigation">
          <Appearance theme={theme} onChange={setTheme} />
          <Link to="/">Dashboard</Link>
        </nav>
      </header>
      {showTabs && <TopTabs />}
      <main className="main">
        <LocalConnection><Routes>
          <Route path="/" element={<Home />} />
          <Route path="/session/new" element={<Setup />} />
          <Route path="/live/:sessionId" element={<Live />} />
          <Route path="/library" element={<Library />} />
          <Route path="/library/:sessionId" element={<Library />}>
            <Route path="notes" element={<Notes />} />
            <Route path="review" element={<Review />} />
            <Route path="replay" element={<Replay />} />
            <Route path="quiz" element={<Quiz />} />
          </Route>
          <Route path="/notes/:sessionId" element={<RedirectToLibraryTab tab="notes" />} />
          <Route path="/review/:sessionId" element={<RedirectToLibraryTab tab="review" />} />
          <Route path="/replay/:sessionId" element={<RedirectToLibraryTab tab="replay" />} />
          <Route path="/quiz/:sessionId" element={<RedirectToLibraryTab tab="quiz" />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/tally/:learnerId" element={<RedirectToInsights param="learner" />} />
          <Route path="/lossmap/:lectureId" element={<RedirectToInsights param="lecture" />} />
          <Route path="*" element={<div className="panel">Unknown page. <Link to="/">Back to Dashboard</Link></div>} />
        </Routes></LocalConnection>
      </main>
    </div>
  );
}
