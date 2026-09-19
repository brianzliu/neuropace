import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge } from "../components/Badges";

/** One lecture: what you missed, moment by moment, and the way into restudy (docs/PRODUCT.md §6). */
export default function Lecture() {
  const { sessionId = "" } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<NotesResponse | null>(null);
  const [title, setTitle] = useState("Lecture");
  const [err, setErr] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const load = () =>
    api
      .notes(sessionId)
      .then((d) => {
        setData(d);
        if (d.session.lecture_id) api.lecture(d.session.lecture_id).then((l) => setTitle(l.title)).catch(() => undefined);
        else setTitle("Live lecture");
      })
      .catch((e) => setErr(errorText(e)));
  useEffect(() => {
    void load();
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const regenerate = async () => {
    setRegenerating(true);
    try {
      const r = await api.regenerate(sessionId);
      setData((d) => (d ? { ...d, gaps: r.gaps } : d));
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setRegenerating(false);
    }
  };
  const endNow = async () => {
    setEnding(true);
    try {
      await api.endSession(sessionId);
      await load();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setEnding(false);
    }
  };

  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (!data) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const running = data.session.status === "running";
  const failed = data.gaps.filter((g) => g.package_source === "failed");
  const closed = data.gaps.filter((g) => g.status === "closed").length;
  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <div className="eyebrow">{new Date(data.session.started_at * 1000).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</div>
          <h1 className="t-title1">{title}</h1>
          <p className="sub">{data.gaps.length ? `${data.gaps.length} moment${data.gaps.length === 1 ? "" : "s"} you missed, taken from the lecture itself.` : "You stayed with it the whole way."}</p>
        </div>
        {data.gaps.length ? (
          <Badge tone={closed === data.gaps.length ? "success" : "warning"}>
            {closed}/{data.gaps.length} landed
          </Badge>
        ) : null}
      </div>
      <div className="stack-lg">
        {running ? (
          <div className="card row between">
            <span className="t-headline">This lecture is still going.</span>
            <span className="row">
              <Link className="btn btn-plain" to={`/live/${sessionId}`}>
                Back to it
              </Link>
              <button className="btn btn-primary" onClick={() => void endNow()} disabled={ending}>
                {ending ? "Writing your notes…" : "End and write my notes"}
              </button>
            </span>
          </div>
        ) : null}
        {!running && data.gaps.length > 0 ? (
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={() => nav(`/restudy/${sessionId}`)} disabled={failed.length > 0}>
              {closed === data.gaps.length ? "Restudy again" : "Restudy"}
            </button>
            <span className="t-subhead label-2">{failed.length ? "Waiting for every moment to have its notes." : "One quick question per moment. Miss it, and it gets explained a different way."}</span>
          </div>
        ) : null}
        {!running && failed.length > 0 ? (
          <div className="callout warning">
            <span className="grow">Some notes could not be written yet.</span>
            <button className="btn btn-sm" onClick={() => void regenerate()} disabled={regenerating}>
              {regenerating ? "Writing…" : "Try again"}
            </button>
          </div>
        ) : null}
        {data.gaps.map((g) => (
          <div key={g.id} className="moment">
            <div className="m-head">
              <span className="m-title">Moment {g.ord + 1}</span>
              <span className="row">
                <span className="m-time">{range(g.t_start, g.t_end)}</span>
                <Badge tone={g.status === "closed" ? "success" : g.status === "exhausted" ? "warning" : "neutral"}>{g.status === "closed" ? "landed" : g.status === "exhausted" ? "still tricky" : "to restudy"}</Badge>
              </span>
            </div>
            {g.package_source === "failed" ? (
              <div className="disclosure">
                <div className="body">{g.span_text}</div>
              </div>
            ) : g.note ? (
              <>
                <div className="m-summary">{g.summary ?? g.note.what_was_said}</div>
                <div className="note-row">
                  <div className="k">Key idea</div>
                  <div>
                    <span className="term">{g.note.key_term}</span> · {g.note.definition}
                  </div>
                </div>
                <div className="note-row">
                  <div className="k">Connects to</div>
                  <div className="label-2">{g.note.connection}</div>
                </div>
              </>
            ) : (
              <div className="label-2">Notes are on their way.</div>
            )}
            <details className="disclosure">
              <summary>What was said</summary>
              <div className="body">{g.span_text}</div>
            </details>
          </div>
        ))}
        {!running && data.gaps.length === 0 ? (
          <div className="empty-state">
            Nothing to restudy here. <Link to="/">Listen to another lecture</Link>
          </div>
        ) : null}
      </div>
    </div>
  );
}
