import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { SourceBadge } from "../components/Badges";

export default function Notes() {
  const { sessionId = "" } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<NotesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);

  const load = () => api.notes(sessionId).then(setData).catch((e) => setErr(String(e)));
  useEffect(() => {
    void load();
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const endNow = async () => {
    setEnding(true);
    try {
      await api.endSession(sessionId);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setEnding(false);
    }
  };

  if (err) return <div className="panel error">{err}</div>;
  if (!data) return <div className="panel muted">loading notes…</div>;
  const running = data.session.status === "running";
  return (
    <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>Gap notes</h1>
        <div className="row">
          <span className="muted small mono">{sessionId}</span>
          <Link to={`/replay/${sessionId}`}>replay</Link>
          {data.session.lecture_id ? <Link to={`/quiz/${sessionId}`}>quiz</Link> : null}
          <Link to="/">home</Link>
        </div>
      </div>
      <div className="muted">Notes only for the spans you missed: what was said, the key term, and how it connects to what you did hear.</div>
      {running ? (
        <div className="panel row">
          <span>This session is still running.</span>
          <button className="primary" onClick={() => void endNow()} disabled={ending}>
            {ending ? "building notes…" : "End it and build notes"}
          </button>
          <Link to={`/live/${sessionId}`}>back to live</Link>
        </div>
      ) : null}
      {!running && data.gaps.length === 0 ? <div className="panel">nothing flagged; nothing to review</div> : null}
      {data.gaps.map((g) => (
        <div key={g.id} className="panel gap-card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              Gap {g.ord + 1} · <span className="mono">{range(g.t_start, g.t_end)}</span>
            </b>
            <span className="row">
              <SourceBadge source={g.package_source} />
              <span className={"badge " + (g.status === "closed" ? "good" : "")}>{g.status}</span>
            </span>
          </div>
          {g.note ? (
            <>
              <div>{g.note.what_was_said}</div>
              <div>
                <span className="term">{g.note.key_term}</span>
                <span className="muted"> · </span>
                {g.note.definition}
              </div>
              <div className="muted">{g.note.connection}</div>
            </>
          ) : (
            <div className="dim">note not generated</div>
          )}
          <details>
            <summary className="muted small">transcript of the span</summary>
            <div className="span">{g.span_text}</div>
          </details>
        </div>
      ))}
      {!running && data.gaps.length > 0 ? (
        <div className="row">
          <button className="primary" onClick={() => nav(`/review/${sessionId}`)}>
            Start review
          </button>
          <span className="muted small">one card per gap, check question first; a miss re-teaches it in another form</span>
        </div>
      ) : null}
    </div>
  );
}
