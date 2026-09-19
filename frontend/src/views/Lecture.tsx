import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge } from "../components/Badges";

/** One lecture: the way into restudy first, then the moments as a list (docs/PRODUCT.md §6). */
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
      nav(`/done/${sessionId}`);
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
  const total = data.gaps.length;
  return (
    <div className="page narrow">
      <header className="hero">
        <div className="eyebrow">{new Date(data.session.started_at * 1000).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</div>
        <h1 className="t-large">{title}</h1>
        <p className="sub">
          {running ? "This lecture is still going." : total === 0 ? "You stayed with it the whole way. Nothing to restudy." : closed === total ? `All ${total} moments landed. Restudy again any time.` : `${total - closed} of ${total} moment${total === 1 ? "" : "s"} still to restudy.`}
        </p>
      </header>

      {running ? (
        <div className="start">
          <Link className="btn btn-primary btn-lg btn-block" to={`/live/${sessionId}`}>
            Back to the lecture
          </Link>
          <button className="linklike" onClick={() => void endNow()} disabled={ending}>
            {ending ? "Writing your notes…" : "Or end it now and write my notes"}
          </button>
        </div>
      ) : total > 0 ? (
        <div className="start">
          <button className="btn btn-primary btn-lg btn-block" onClick={() => nav(`/restudy/${sessionId}`)} disabled={failed.length > 0}>
            {closed === total ? "Restudy again" : "Restudy"}
          </button>
          <div className="start-note">{failed.length ? "Some notes aren't written yet." : "One quick question per moment. Miss it, and it's explained a different way."}</div>
          {failed.length ? (
            <button className="linklike" onClick={() => void regenerate()} disabled={regenerating}>
              {regenerating ? "Writing…" : "Try writing them again"}
            </button>
          ) : null}
        </div>
      ) : null}

      {total > 0 ? (
        <section className="stack">
          <div className="eyebrow">What you missed</div>
          {data.gaps.map((g) => (
            <details key={g.id} className="moment-row">
              <summary>
                <span className="m-num">{g.ord + 1}</span>
                <span className="m-body">
                  <span className="m-summary">{g.package_source === "failed" ? g.span_text.slice(0, 140) + "…" : (g.summary ?? g.note?.what_was_said ?? "Notes are on their way.")}</span>
                  <span className="m-meta">
                    {range(g.t_start, g.t_end)} {g.note?.key_term ? `· ${g.note.key_term}` : ""}
                  </span>
                </span>
                <Badge tone={g.status === "closed" ? "success" : g.status === "exhausted" ? "warning" : "neutral"}>{g.status === "closed" ? "landed" : g.status === "exhausted" ? "tricky" : "to do"}</Badge>
              </summary>
              <div className="m-detail">
                {g.note ? (
                  <>
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
                ) : null}
                <div className="note-row">
                  <div className="k">What was said</div>
                  <div className="label-2">{g.span_text}</div>
                </div>
              </div>
            </details>
          ))}
        </section>
      ) : null}
    </div>
  );
}
