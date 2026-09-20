import { useLayoutEffect } from "react";
import { Link, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import LocalConnection from "./components/LocalConnection";
import SideBlobs from "./components/SideBlobs";
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
import ReviewEntry from "./views/ReviewEntry";
import Team from "./views/Team";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import Library, { SessionRouteFrame } from "./views/Library";
import Insights from "./views/Insights";
import LossMap from "./views/LossMap";
import Artifacts from "./views/Artifacts";
import OfficeHours from "./views/OfficeHours";

function LegacySession({ tab }: { tab: string }) {
  const { sessionId = "" } = useParams();
  return <Navigate to={`/library/${sessionId}/${tab}`} replace />;
}

export default function App() {
  useLayoutEffect(() => { document.documentElement.dataset.theme = "pocket"; }, []);
  const { pathname } = useLocation();
  const flash = useFlash();
  const compact = /^\/(session|live|restudy|replay|office-hours)(\/|$)/.test(pathname) || pathname.includes("/replay/") || /^\/library\/[^/]+\/(review|replay)/.test(pathname);
  return <div className={"app" + (compact ? " app-compact" : "")}>
    <SideBlobs />
    <header className="topbar">
      <Link to="/" className="brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><g transform="rotate(-18 12 12)"><rect x="9.3" y="2.2" width="5.4" height="2.8" rx="1.2" fill="var(--accent-2)" /><rect x="9.3" y="5" width="5.4" height="1.7" fill="var(--surface-edge)" /><rect x="9.3" y="6.7" width="5.4" height="8.3" fill="var(--accent)" /><polygon points="9.3,15 14.7,15 12,19.2" fill="var(--object)" /><polygon points="11.1,17.3 12.9,17.3 12,19.2" fill="var(--text)" /></g></svg></span>NeuroPace</Link>
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
        <Route path="/lecture/:sessionId" element={<SessionRouteFrame tab="notes"><Lecture /></SessionRouteFrame>} />
        <Route path="/restudy/:sessionId" element={<SessionRouteFrame tab="review"><Restudy /></SessionRouteFrame>} />
        <Route path="/office-hours/:sessionId" element={<SessionRouteFrame tab="review" useOriginal><OfficeHours /></SessionRouteFrame>} />
        <Route path="/lectures" element={<Lectures />} />
        <Route path="/library" element={<Library />} />
        <Route path="/library/:sessionId" element={<Library />}>
          <Route path="notes" element={<Lecture />} />
          <Route path="review" element={<ReviewEntry />} />
          <Route path="replay" element={<Replay />} />
          <Route path="quiz" element={<Quiz />} />
          <Route path="artifacts" element={<Artifacts />} />
        </Route>
        <Route path="/notes/:sessionId" element={<LegacySession tab="notes" />} />
        <Route path="/review/:sessionId" element={<LegacySession tab="review" />} />
        <Route path="/replay/:sessionId" element={<LegacySession tab="replay" />} />
        <Route path="/quiz/:sessionId" element={<LegacySession tab="quiz" />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/you" element={<Navigate to="/insights" replace />} />
        <Route path="/tally/:learnerId" element={<Insights />} />
        <Route path="/lossmap/:lectureId" element={<Insights />} />
        <Route path="/team" element={<Team />} />
        <Route path="/team/replay/:sessionId" element={<SessionRouteFrame tab="replay"><Replay /></SessionRouteFrame>} />
        <Route path="/team/lossmap/:lectureId" element={<LossMap />} />
        <Route path="/team/quiz/:sessionId" element={<SessionRouteFrame tab="quiz"><Quiz /></SessionRouteFrame>} />
        <Route path="/team/artifacts/:sessionId" element={<SessionRouteFrame tab="artifacts"><Artifacts /></SessionRouteFrame>} />
        <Route path="*" element={<div className="panel">Page not found. <Link to="/">Dashboard</Link></div>} />
      </Routes></LocalConnection>
    </main>
  </div>;
}
