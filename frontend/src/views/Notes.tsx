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
          <h1 className="t-title1">Gap notes</h1>
          <div className="sub">Only for the spans you missed: what was said, the key term, and how it connects to what you did hear.</div>
        </div>
        <span className="mono t-footnote label-2">{sessionId}</span>
      </div>
      <div className="stack-lg">
        {running ? (
          <div className="card row between">
            <span>This session is still running.</span>
            <span className="row">
              <Link className="btn btn-plain" to={`/live/${sessionId}`}>
                Back to live
              </Link>
              <button className="btn btn-primary" onClick={() => void endNow()} disabled={ending}>
                {ending ? "Building notes…" : "End it and build notes"}
              </button>
            </span>
          </div>
        ) : null}
        {!running && data.gaps.length === 0 ? <div className="empty-state">Nothing flagged, nothing to review.</div> : null}
        {data.gaps.map((g) => (
          <div key={g.id} className="card">
            <div className="card-header">
              <span className="card-title">
                Gap {g.ord + 1} <span className="label-2 mono">· {range(g.t_start, g.t_end)}</span>
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
                  <div className="k">Key term</div>
                  <div>
                    <span className="term">{g.note.key_term}</span>
                    <span className="label-2"> · </span>
                    {g.note.definition}
                  </div>
                </div>
                <div className="note-row">
                  <div className="k">Connection</div>
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
              Start review
            </button>
            <span className="t-footnote label-2">
              {failed.length ? "Disabled until every gap has its notes and question." : "One card per gap, check question first. A miss re-teaches it in another form."}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
