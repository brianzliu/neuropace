import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, SessionPublic } from "../lib/types";
import { mmss } from "../lib/format";
import { Badge } from "../components/Badges";

/** Listen: one decision and one button (docs/PRODUCT.md §6). Everything technical lives on the team page. */
export default function Home() {
  const nav = useNavigate();
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [lectureId, setLectureId] = useState<string | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const [lec, s, d] = await Promise.allSettled([api.lectures(), api.sessions(), api.doctor()]);
      if (lec.status === "fulfilled") {
        setLectures(lec.value.lectures);
        setLectureId((cur) => (cur === undefined ? (lec.value.lectures[0]?.id ?? null) : cur));
      } else setErr(errorText(lec.reason));
      if (s.status === "fulfilled") setSessions(s.value.sessions.filter((x) => x.mode !== "review").slice(0, 4));
      if (d.status === "fulfilled") setDoctor(d.value);
    })();
  }, []);

  const deepgramOk = !!doctor && doctor.keys.deepgram && doctor.deepgram.ok;
  const notesOk = !!doctor && doctor.keys.openai && doctor.openai.ok;
  const liveMic = lectureId === null;

  const start = async () => {
    setErr(null);
    setBusy(true);
    try {
      const body: SessionCreate = { lecture_id: lectureId ?? null, mode: "live", headset: "auto", totem: "auto" };
      const s = await api.createSession(body);
      nav(`/live/${s.id}`);
    } catch (e) {
      setErr(friendly(errorText(e)));
    } finally {
      setBusy(false);
    }
  };

  const headsetLine = !doctor ? "Checking your headset…" : doctor.headset.kind === "real" ? "Headset connected." : "No headset today. The button still works, and focus is simulated for practice.";
  const padLine = !doctor ? "" : doctor.totem.kind === "real" ? "Pad connected." : "No pad today: press Space when you feel lost.";

  return (
    <div className="page">
      <header className="hero">
        <h1 className="t-large">Ready when you are.</h1>
        <p className="sub">Put the headset on and start the lecture. If you drift, Reflow catches you up in one line and, afterwards, teaches you only what you missed.</p>
      </header>

      {err ? <div className="callout danger">{err}</div> : null}
      {doctor && !notesOk ? <div className="callout warning">Reflow can't write notes right now. Ask the team to check the setup before you start.</div> : null}

      <div className="home-grid">
        <div className="stack-lg">
          <div className="start-card">
            <div className="eyebrow">What are you listening to?</div>
            <div className="lecture-cards">
              {lectures.map((l) => (
                <button key={l.id} className={"lecture-card" + (lectureId === l.id ? " selected" : "")} onClick={() => setLectureId(l.id)}>
                  <span className="lc-kind">{l.kind === "media" ? "Recorded lecture" : "Practice lecture"}</span>
                  <span className="lc-title">{l.title}</span>
                  <span className="lc-meta">
                    {mmss(l.duration)} · {l.segments?.length ?? 0} parts
                  </span>
                </button>
              ))}
              <button className={"lecture-card" + (liveMic ? " selected" : "")} onClick={() => setLectureId(null)}>
                <span className="lc-kind">Live</span>
                <span className="lc-title">A lecture happening now</span>
                <span className="lc-meta">{deepgramOk ? "Uses your laptop microphone." : "Not available right now."}</span>
              </button>
            </div>
            <div className="row">
              <button className="btn btn-primary btn-lg" disabled={busy || lectureId === undefined || (liveMic && !deepgramOk)} onClick={() => void start()}>
                {busy ? "Starting…" : "Start listening"}
              </button>
              <span className="label-2 t-subhead">
                Feel lost? Press <kbd className="kbd">space</kbd> or tap the pad.
              </span>
            </div>
            <div className="t-footnote label-2">
              {headsetLine} {padLine}
            </div>
          </div>
        </div>

        <aside className="stack-lg">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Pick up where you left off</span>
              <Link className="t-footnote" to="/lectures">
                all lectures
              </Link>
            </div>
            {sessions.length === 0 ? <div className="label-2 t-subhead">Your first lecture shows up here.</div> : null}
            <div className="session-list">
              {sessions.map((s) => {
                const lec = lectures.find((l) => l.id === s.lecture_id);
                const st = s.status === "running" ? { text: "Listening now", tone: "success" as const } : s.status === "reviewed" ? { text: "Restudied", tone: "accent" as const } : s.gaps ? { text: `${s.gaps} to restudy`, tone: "warning" as const } : { text: "All clear", tone: "neutral" as const };
                const to = s.status === "running" ? `/live/${s.id}` : `/lecture/${s.id}`;
                return (
                  <div key={s.id} className="session-item">
                    <div className="si-main">
                      <div className="si-title">{lec?.title ?? (s.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</div>
                      <div className="si-meta">{new Date(s.started_at * 1000).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</div>
                    </div>
                    <Badge tone={st.tone}>{st.text}</Badge>
                    <Link className="btn btn-sm" to={to}>
                      Open
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function friendly(detail: string): string {
  if (/OPENAI_API_KEY/i.test(detail)) return "Reflow can't write notes right now. Ask the team to check the setup.";
  if (/DEEPGRAM/i.test(detail)) return "Live transcription isn't available right now. Pick a practice lecture, or ask the team.";
  return detail;
}
