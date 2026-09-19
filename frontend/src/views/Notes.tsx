import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge, SourceBadge } from "../components/Badges";

export default function Notes() {
  const { sessionId = "" } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState<NotesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const load = () => api.notes(sessionId).then(setData).catch((e) => setErr(errorText(e)));

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
  useEffect(() => {
    void load();
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

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

  if (err) return <div className="page narrow"><div className="card error-text">{err}</div></div>;
  if (!data) return <div className="page narrow"><div className="loading">Loading notes…</div></div>;
  const running = data.session.status === "running";
  const failed = data.gaps.filter((g) => g.package_source === "failed");
  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <h1 className="t-title1">What you missed</h1>
          <div className="sub">Only the moments you drifted, taken from the lecture itself: what was said, the key idea, and how it connects to what you did hear.</div>
        </div>
        
      </div>
      <div className="stack-lg">
        {running ? (
          <div className="card row between">
            <span>This lecture is still going.</span>
            <span className="row">
              <Link className="btn btn-plain" to={`/live/${sessionId}`}>
                Back to the lecture
              </Link>
              <button className="btn btn-primary" onClick={() => void endNow()} disabled={ending}>
                {ending ? "Writing your notes…" : "End it and write my notes"}
              </button>
            </span>
          </div>
        ) : null}
        {!running && data.gaps.length === 0 ? <div className="empty-state">You stayed with it the whole way. Nothing to review.</div> : null}
        {data.gaps.map((g) => (
          <div key={g.id} className="card">
            <div className="card-header">
              <span className="card-title">
                Moment {g.ord + 1} <span className="label-2 mono">· {range(g.t_start, g.t_end)}</span>
              </span>
              <span className="row">
                <SourceBadge source={g.package_source} />
                <Badge tone={g.status === "closed" ? "success" : g.status === "exhausted" ? "warning" : "neutral"}>{g.status}</Badge>
              </span>
            </div>
            {g.package_source === "failed" ? (
              <div className="stack">
                <div className="t-subhead warning-text">Notes could not be generated: {g.error ?? "unknown error"}</div>
                <div className="disclosure">
                  <div className="body">{g.span_text}</div>
                </div>
              </div>
            ) : g.note ? (
              <>
                <div className="note-row">
                  <div className="k">What was said</div>
                  <div>{g.note.what_was_said}</div>
                </div>
                <div className="note-row">
                  <div className="k">Key idea</div>
                  <div>
                    <span className="term">{g.note.key_term}</span>
                    <span className="label-2"> · </span>
                    {g.note.definition}
                  </div>
                </div>
                <div className="note-row">
                  <div className="k">How it connects</div>
                  <div className="label-2">{g.note.connection}</div>
                </div>
              </>
            ) : (
              <div className="label-2">note not generated</div>
            )}
            <details className="disclosure" style={{ marginTop: 10 }}>
              <summary>Transcript of the span</summary>
              <div className="body">{g.span_text}</div>
            </details>
          </div>
        ))}
        {!running && failed.length > 0 ? (
          <div className="card row between">
            <span className="t-subhead">
              {failed.length} gap{failed.length === 1 ? "" : "s"} without notes. Review needs every gap generated.
            </span>
            <button className="btn btn-primary" onClick={() => void regenerate()} disabled={regenerating}>
              {regenerating ? "Generating…" : "Retry generation"}
            </button>
          </div>
        ) : null}
        {!running && data.gaps.length > 0 ? (
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={() => nav(`/review/${sessionId}`)} disabled={failed.length > 0} title={failed.length ? "Retry generation first" : ""}>
              Make it stick
            </button>
            <span className="t-footnote label-2">
              {failed.length ? "Waiting for every moment to have its notes." : "One quick question per moment. Miss one and it gets explained a different way."}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
