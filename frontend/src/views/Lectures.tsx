import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { activeLearnerId } from "../lib/activeLearner";
import { api } from "../lib/api";
import type { LectureFull, SessionPublic } from "../lib/types";
import { Badge } from "../components/Badges";
import SessionActionIcons from "../components/dashboard/SessionActionIcons";

/** Lectures: the history, newest first. The only place it lives (docs/PRODUCT.md §6). */
export default function Lectures() {
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void activeLearnerId().then(learner_id => Promise.all([api.sessions({ learner_id }), api.lectures()]))
      .then(([s, l]) => {
        if (!active) return;
        setSessions(s.sessions.filter(x => x.mode !== "review" && x.mode !== "office_hours"));
        setLectures(l.lectures);
        setLoaded(true);
      }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, []);
  return (
    <div className="page narrow">
      <header className="hero">
        <h1 className="t-large">Lectures</h1>
        <p className="sub">Everything you listened to. Open one to restudy the moments you missed.</p>
      </header>
      {error && <div className="callout danger">{error}</div>}
      {loaded && sessions.length === 0 ? (
        <div className="empty-state">
          Nothing yet. <Link to="/">Start listening</Link> and your lectures will show up here.
        </div>
      ) : null}
      <div className="list">
        {sessions.map((s) => {
          const lec = lectures.find((l) => l.id === s.lecture_id);
          const title = lec?.title ?? (s.transcript_kind === "deepgram" ? "Live lecture" : "Lecture");
          const running = s.status === "running";
          const restudied = s.status === "reviewed";
          const badge = running ? { t: "Listening now", tone: "success" as const } : restudied ? { t: "Restudied", tone: "accent" as const } : s.gaps ? { t: `${s.gaps} to restudy`, tone: "warning" as const } : { t: "No saved moments", tone: "neutral" as const };
          return (
            <article key={s.id} className="list-row">
              <Link className="lr-main" to={running ? `/live/${s.id}` : `/lecture/${s.id}`}>
                <span className="lr-title">{title}</span>
                <span className="lr-meta">{new Date(s.started_at * 1000).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
              </Link>
              <Badge tone={badge.tone}>{badge.t}</Badge>
              {!running ? <SessionActionIcons sessionId={s.id} title={title} showQuiz={!!s.lecture_id} /> : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
