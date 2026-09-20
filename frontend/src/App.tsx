import { useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import Home from "./views/Home";
import Live from "./views/Live";
import Done from "./views/Done";
import Lectures from "./views/Lectures";
import Lecture from "./views/Lecture";
import Restudy from "./views/Restudy";
import You from "./views/You";
import Team from "./views/Team";
import LossMapView from "./views/LossMap";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import Artifacts from "./views/Artifacts";
import Sidebar from "./components/Sidebar";
import { useFlash } from "./lib/flash";
import { api } from "./lib/api";

/** Window shell: sidebar + content. Live and replay collapse the sidebar to an icon rail. */
export default function App() {
  const loc = useLocation();
  const fl = useFlash();
  const m = loc.pathname.match(/^\/(?:team\/)?(live|lecture|restudy|done|replay|quiz|artifacts)\/([^/]+)/);
  const sessionId = m && m[2] !== "sample" ? m[2] : null;
  const rail = !!m && (m[1] === "live" || m[1] === "replay" || m[1] === "restudy");
  const [running, setRunning] = useState(false);
  useEffect(() => {
    if (!sessionId) return;
    let alive = true;
    api
      .session(sessionId)
      .then((s) => alive && setRunning(!!s.running))
      .catch(() => alive && setRunning(false));
    return () => {
      alive = false;
    };
  }, [sessionId, loc.pathname]);

  return (
    <div className={"shell" + (rail ? " shell-rail" : "")}>
      <Sidebar sessionId={sessionId} sessionRunning={running || m?.[1] === "live"} rail={rail} />
      <main className="content">
        {fl ? (
          <div className="flash-host">
            <span key={fl.seq} className={"flash" + (fl.tone === "neutral" ? " neutral" : "")}>
              {fl.label}
            </span>
          </div>
        ) : null}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/live/:sessionId" element={<Live />} />
          <Route path="/done/:sessionId" element={<Done />} />
          <Route path="/lectures" element={<Lectures />} />
          <Route path="/lecture/:sessionId" element={<Lecture />} />
          <Route path="/restudy/:sessionId" element={<Restudy />} />
          <Route path="/you" element={<You />} />
          <Route path="/team" element={<Team />} />
          <Route path="/team/replay/:sessionId" element={<Replay />} />
          <Route path="/team/lossmap/:lectureId" element={<LossMapView />} />
          <Route path="/team/quiz/:sessionId" element={<Quiz />} />
          <Route path="/team/artifacts/:sessionId" element={<Artifacts />} />
          {/* old links */}
          <Route path="/notes/:sessionId" element={<Lecture />} />
          <Route path="/review/:sessionId" element={<Restudy />} />
          <Route path="/replay/:sessionId" element={<Replay />} />
          <Route path="/quiz/:sessionId" element={<Quiz />} />
          <Route path="/lossmap/:lectureId" element={<LossMapView />} />
          <Route path="/tally/:learnerId" element={<You />} />
          <Route
            path="*"
            element={
              <div className="page narrow">
                <div className="empty-state">
                  That page does not exist. <Link to="/">Back to listening</Link>
                </div>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
