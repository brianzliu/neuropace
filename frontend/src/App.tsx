import { useLayoutEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import Home from "./views/Home";
import Live from "./views/Live";
import Notes from "./views/Notes";
import Review from "./views/Review";
import Tally from "./views/Tally";
import LossMapView from "./views/LossMap";
import Replay from "./views/Replay";
import Quiz from "./views/Quiz";

export default function App() {
  const [theme, setTheme] = useState(() => {
    try { const saved = localStorage.getItem("reflow.theme"); return saved && ["fieldnotes", "studio", "afterhours"].includes(saved) ? saved : "fieldnotes"; }
    catch { return "fieldnotes"; }
  });
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("reflow.theme", theme); } catch { /* Theme still works without storage. */ }
  }, [theme]);
  const loc = useLocation();
  const compact = loc.pathname.startsWith("/live") || loc.pathname.startsWith("/replay");
  return (
    <div className={"app" + (compact ? " app-compact" : "")}>
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-dot" /> Reflow
        </Link>
        <nav className="topnav" aria-label="Main navigation">
          <label className="theme-picker">Appearance
            <select aria-label="Design theme" value={theme} onChange={e => setTheme(e.target.value)}>
              <option value="fieldnotes">Fieldnotes</option>
              <option value="studio">Studio</option>
              <option value="afterhours">Afterhours</option>
            </select>
          </label>
          <Link to="/">Home</Link>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/live/:sessionId" element={<Live />} />
          <Route path="/notes/:sessionId" element={<Notes />} />
          <Route path="/review/:sessionId" element={<Review />} />
          <Route path="/tally/:learnerId" element={<Tally />} />
          <Route path="/lossmap/:lectureId" element={<LossMapView />} />
          <Route path="/replay/:sessionId" element={<Replay />} />
          <Route path="/quiz/:sessionId" element={<Quiz />} />
          <Route path="*" element={<div className="panel">Unknown page. <Link to="/">Home</Link></div>} />
        </Routes>
      </main>
    </div>
  );
}
