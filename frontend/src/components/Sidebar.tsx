import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../lib/api";
import type { Doctor } from "../lib/types";
import { useTheme, type Theme } from "../lib/theme";

/** macOS window sidebar: brand, navigation, and a status footer. `rail` collapses it to icons (live and replay). */

const LS_LEARNER = "reflow.learner";

type IconName = "start" | "live" | "notes" | "review" | "replay" | "quiz" | "tally" | "lossmap";

function Icon({ name }: { name: IconName }) {
  const common = { width: 16, height: 16, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "start":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6.25" />
          <path d="M6.6 5.6v4.8L10.4 8z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "live":
      return (
        <svg {...common}>
          <path d="M1.75 8h2l1.5-4 2 8 2-6 1.5 3.5h3.5" />
        </svg>
      );
    case "notes":
      return (
        <svg {...common}>
          <rect x="3" y="2" width="10" height="12" rx="1.5" />
          <path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3" />
        </svg>
      );
    case "review":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6.25" />
          <path d="M5.2 8.2l1.9 1.9 3.8-4.2" />
        </svg>
      );
    case "replay":
      return (
        <svg {...common}>
          <path d="M3.2 6.3A5 5 0 1 1 3 9.2" />
          <path d="M2.5 3v3.5H6" />
        </svg>
      );
    case "quiz":
      return (
        <svg {...common}>
          <path d="M5.5 4.5h8M5.5 8h8M5.5 11.5h8" />
          <circle cx="2.8" cy="4.5" r="0.9" fill="currentColor" stroke="none" />
          <circle cx="2.8" cy="8" r="0.9" fill="currentColor" stroke="none" />
          <circle cx="2.8" cy="11.5" r="0.9" fill="currentColor" stroke="none" />
        </svg>
      );
    case "tally":
      return (
        <svg {...common}>
          <path d="M2.5 13.5h11" />
          <rect x="3.5" y="7" width="2.4" height="5" rx="0.6" fill="currentColor" stroke="none" />
          <rect x="7" y="3.5" width="2.4" height="8.5" rx="0.6" fill="currentColor" stroke="none" />
          <rect x="10.5" y="9" width="2.4" height="3" rx="0.6" fill="currentColor" stroke="none" />
        </svg>
      );
    case "lossmap":
      return (
        <svg {...common}>
          <path d="M2 12.5c2-3.5 3-6 5-6s3 4.5 5 4.5 2-3.5 2-3.5" />
          <path d="M2 13.5h12" />
        </svg>
      );
  }
}

function Item({ to, icon, label, end, rail }: { to: string; icon: IconName; label: string; end?: boolean; rail: boolean }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => "sb-item" + (isActive ? " is-active" : "")} title={rail ? label : undefined}>
      <span className="sb-icon">
        <Icon name={icon} />
      </span>
      {rail ? null : <span className="sb-label">{label}</span>}
    </NavLink>
  );
}

export default function Sidebar({ sessionId, sessionRunning, rail }: { sessionId: string | null; sessionRunning: boolean; rail: boolean }) {
  const [theme, setTheme] = useTheme();
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [lectureId, setLectureId] = useState<string | null>(null);
  const learnerId = (() => {
    try {
      return localStorage.getItem(LS_LEARNER);
    } catch {
      return null;
    }
  })();

  useEffect(() => {
    let alive = true;
    const load = () => api.doctor().then((d) => alive && setDoctor(d)).catch(() => alive && setDoctor(null));
    void load();
    api.lectures().then((l) => alive && setLectureId(l.lectures[0]?.id ?? null)).catch(() => undefined);
    const id = window.setInterval(load, 30000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  const openaiOk = !!doctor && doctor.keys.openai && doctor.openai.ok;
  return (
    <aside className={"sidebar" + (rail ? " rail" : "")}>
      <NavLink to="/" className="sb-brand" title="Reflow">
        <span className="mark" />
        {rail ? null : <span>Reflow</span>}
      </NavLink>
      <nav className="sb-nav">
        {rail ? null : <div className="sb-section">Lecture</div>}
        <Item to="/" icon="start" label="Listen" end rail={rail} />
        {sessionId ? (
          <>
            {rail ? null : (
              <div className="sb-section">
                Session <span className="mono">{sessionId.replace("sess_", "")}</span>
              </div>
            )}
            {sessionRunning ? <Item to={`/live/${sessionId}`} icon="live" label="Now playing" rail={rail} /> : null}
            <Item to={`/notes/${sessionId}`} icon="notes" label="What you missed" rail={rail} />
            <Item to={`/review/${sessionId}`} icon="review" label="Make it stick" rail={rail} />
            <Item to={`/replay/${sessionId}`} icon="replay" label="Replay" rail={rail} />
            <Item to={`/quiz/${sessionId}`} icon="quiz" label="Quiz" rail={rail} />
          </>
        ) : null}
        {rail ? null : <div className="sb-section">You</div>}
        {learnerId ? <Item to={`/tally/${learnerId}`} icon="tally" label="What works for you" rail={rail} /> : null}
        {lectureId ? <Item to={`/lossmap/${lectureId}`} icon="lossmap" label="Where the room drifted" rail={rail} /> : null}
      </nav>
      <div className="sb-footer">
        <div className="sb-status" title="Deepgram · OpenAI · headset · totem">
          <span className={"dot " + (doctor?.deepgram.ok ? "ok" : "bad")} title={doctor?.deepgram.ok ? "Deepgram reachable" : "Deepgram: no key or unreachable"} />
          <span className={"dot " + (openaiOk ? "ok" : "bad")} title={openaiOk ? `OpenAI ${doctor?.openai.model}` : "OpenAI key required"} />
          <span className={"dot " + (doctor?.headset.kind === "real" ? "ok" : "warn")} title={doctor?.headset.kind === "real" ? "MindWave paired" : "headset simulated"} />
          <span className={"dot " + (doctor?.totem.kind === "real" ? "ok" : "accent")} title={doctor?.totem.kind === "real" ? "Arduino totem" : "keyboard totem"} />
          {rail ? null : <span className="sb-status-text">{openaiOk ? "all set" : "setup needed"}</span>}
        </div>
        {rail ? null : (
          <div className="segmented sm sb-theme" aria-label="appearance">
            {(["auto", "light", "dark"] as Theme[]).map((t) => (
              <button key={t} className={theme === t ? "is-active" : ""} onClick={() => setTheme(t)}>
                {t}
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
