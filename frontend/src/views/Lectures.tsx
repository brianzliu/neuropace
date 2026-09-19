import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { LectureFull, SessionPublic } from "../lib/types";
import { Badge } from "../components/Badges";

/** Every past lecture as a tile with restudy progress (docs/PRODUCT.md §6). */
export default function Lectures() {
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    Promise.allSettled([api.sessions(), api.lectures()]).then(([s, l]) => {
      if (s.status === "fulfilled") setSessions(s.value.sessions.filter((x) => x.mode !== "review" && x.status !== "running"));
      if (l.status === "fulfilled") setLectures(l.value.lectures);
      setLoaded(true);
    });
  }, []);
  return (
    <div className="page">
      <header className="hero">
        <h1 className="t-large">Your lectures</h1>
        <p className="sub">Every lecture you listened to, with the moments Reflow knows you missed. Restudy any of them.</p>
      </header>
      {loaded && sessions.length === 0 ? (
        <div className="empty-state">
          Nothing yet. <Link to="/">Start listening</Link> to a lecture and it will show up here.
        </div>
      ) : null}
      <div className="tiles">
        {sessions.map((s) => {
          const lec = lectures.find((l) => l.id === s.lecture_id);
          const restudied = s.status === "reviewed";
          const tone = restudied ? "accent" : s.gaps ? "warning" : "neutral";
          return (
            <Link key={s.id} className={"tile" + (restudied || !s.gaps ? " done" : "")} to={`/lecture/${s.id}`}>
              <div className="tile-title">{lec?.title ?? (s.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</div>
              <div className="tile-meta">{new Date(s.started_at * 1000).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</div>
              <div className="progress thin">
                <i style={{ width: restudied ? "100%" : s.gaps ? "0%" : "100%" }} />
              </div>
              <div className="tile-foot">
                <Badge tone={tone}>{restudied ? "Restudied" : s.gaps ? `${s.gaps} moment${s.gaps === 1 ? "" : "s"} to restudy` : "All clear"}</Badge>
                <span className="t-footnote label-2">{s.flags.length} flag{s.flags.length === 1 ? "" : "s"}</span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
