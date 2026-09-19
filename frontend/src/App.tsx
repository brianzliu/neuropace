import { useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import Home from "./views/Home";
import Live from "./views/Live";
import Notes from "./views/Notes";
import Review from "./views/Review";
import Tally from "./views/Tally";
import LossMapView from "./views/LossMap";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import Sidebar from "./components/Sidebar";
import { useFlash } from "./lib/flash";
import { api } from "./lib/api";

/** Window shell: sidebar + content. Live and replay collapse the sidebar to an icon rail. */
export default function App() {
  const loc = useLocation();
  const fl = useFlash();
  const m = loc.pathname.match(/^\/(live|notes|review|replay|quiz)\/([^/]+)/);
  const sessionId = m ? m[2] : null;
  const rail = !!m && (m[1] === "live" || m[1] === "replay");
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
      <Sidebar sessionId={sessionId} sessionRunning={running || (m?.[1] === "live")} rail={rail} />
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
          <Route path="/notes/:sessionId" element={<Notes />} />
          <Route path="/review/:sessionId" element={<Review />} />
          <Route path="/tally/:learnerId" element={<Tally />} />
          <Route path="/lossmap/:lectureId" element={<LossMapView />} />
          <Route path="/replay/:sessionId" element={<Replay />} />
          <Route path="/quiz/:sessionId" element={<Quiz />} />
          <Route
            path="*"
            element={
              <div className="page narrow">
                <div className="empty-state">
                  Unknown page. <Link to="/">Start a session</Link>
                </div>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
