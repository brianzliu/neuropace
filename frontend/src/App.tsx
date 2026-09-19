import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import Home from "./views/Home";
import Live from "./views/Live";
import Notes from "./views/Notes";
import Review from "./views/Review";
import Tally from "./views/Tally";
import LossMapView from "./views/LossMap";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";
import { useTheme, type Theme } from "./lib/theme";
import { useFlash } from "./lib/flash";

const SESSION_ROUTES = ["live", "notes", "review", "replay", "quiz"] as const;

export default function App() {
  const loc = useLocation();
  const [theme, setTheme] = useTheme();
  const fl = useFlash();
  const m = loc.pathname.match(/^\/(live|notes|review|replay|quiz)\/([^/]+)/);
  const sessionId = m ? m[2] : null;
  const section = m ? m[1] : loc.pathname.startsWith("/tally") ? "tally" : loc.pathname.startsWith("/lossmap") ? "loss map" : null;
  return (
    <div className="app">
      <header className="toolbar">
        <Link to="/" className="brand">
          <span className="mark" /> Reflow
          {section ? <span className="crumb">{section}</span> : null}
        </Link>
        <div>
          {sessionId ? (
            <nav className="segmented sm" aria-label="session">
              {SESSION_ROUTES.map((r) => (
                <NavLink key={r} to={`/${r}/${sessionId}`} className={({ isActive }) => (isActive ? "is-active" : "")}>
                  {r}
                </NavLink>
              ))}
            </nav>
          ) : null}
        </div>
        <div className="tb-right">
          {fl ? (
            <span key={fl.seq} className={"flash" + (fl.tone === "neutral" ? " neutral" : "")}>
              {fl.label}
            </span>
          ) : null}
          <div className="segmented sm" aria-label="appearance">
            {(["auto", "light", "dark"] as Theme[]).map((t) => (
              <button key={t} className={theme === t ? "is-active" : ""} onClick={() => setTheme(t)}>
                {t}
              </button>
            ))}
          </div>
        </div>
      </header>
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
                Unknown page. <Link to="/">Home</Link>
              </div>
            </div>
          }
        />
      </Routes>
    </div>
  );
}
