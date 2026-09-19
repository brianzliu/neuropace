import { useLayoutEffect } from "react";
import { Link, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import LocalConnection from "./components/LocalConnection";
import TopTabs from "./components/TopTabs";
import { useFlash } from "./lib/flash";
import Home from "./views/Home";
import Setup from "./views/Setup";
import AdvancedSetup from "./views/AdvancedSetup";
import Live from "./views/Live";
import Done from "./views/Done";
import Lecture from "./views/Lecture";
import Lectures from "./views/Lectures";
import Restudy from "./views/Restudy";
import You from "./views/You";
import Team from "./views/Team";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import Library from "./views/Library";
import Insights from "./views/Insights";
import LossMap from "./views/LossMap";

function LegacySession({ tab }: { tab: string }) {
  const { sessionId = "" } = useParams();
  return <Navigate to={`/library/${sessionId}/${tab}`} replace />;
}

export default function App() {
  useLayoutEffect(() => { document.documentElement.dataset.theme = "pocket"; }, []);
  const { pathname } = useLocation();
  const flash = useFlash();
  const compact = /^\/(session|live|restudy|replay)(\/|$)/.test(pathname) || pathname.includes("/replay/") || /^\/library\/[^/]+\/(review|replay)/.test(pathname);
  return <div className={"app" + (compact ? " app-compact" : "")}>
    <header className="topbar">
      <Link to="/" className="brand"><span className="brand-dot" />NeuroPace</Link>
      {compact ? <Link to="/">Dashboard</Link> : <TopTabs />}
    </header>
    <main className="main">
      {flash && <div className="flash-host"><span key={flash.seq} className={"flash" + (flash.tone === "neutral" ? " neutral" : "")}>{flash.label}</span></div>}
      <LocalConnection><Routes>
        <Route path="/" element={<Home />} />
        <Route path="/session/new" element={<Setup />} />
        <Route path="/session/advanced" element={<AdvancedSetup />} />
        <Route path="/live/:sessionId" element={<Live />} />
        <Route path="/done/:sessionId" element={<Done />} />
        <Route path="/lecture/:sessionId" element={<Lecture />} />
        <Route path="/restudy/:sessionId" element={<Restudy />} />
        <Route path="/lectures" element={<Lectures />} />
        <Route path="/library" element={<Library />} />
        <Route path="/library/:sessionId" element={<Library />}>
          <Route path="notes" element={<Lecture />} />
          <Route path="review" element={<Restudy />} />
          <Route path="replay" element={<Replay />} />
          <Route path="quiz" element={<Quiz />} />
        </Route>
        <Route path="/notes/:sessionId" element={<LegacySession tab="notes" />} />
        <Route path="/review/:sessionId" element={<LegacySession tab="review" />} />
        <Route path="/replay/:sessionId" element={<Replay />} />
        <Route path="/quiz/:sessionId" element={<Quiz />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/you" element={<You />} />
        <Route path="/tally/:learnerId" element={<Insights />} />
        <Route path="/lossmap/:lectureId" element={<LossMap />} />
        <Route path="/team" element={<Team />} />
        <Route path="/team/replay/:sessionId" element={<Replay />} />
        <Route path="/team/lossmap/:lectureId" element={<LossMap />} />
        <Route path="/team/quiz/:sessionId" element={<Quiz />} />
        <Route path="*" element={<div className="panel">Page not found. <Link to="/">Dashboard</Link></div>} />
      </Routes></LocalConnection>
    </main>
  </div>;
}
