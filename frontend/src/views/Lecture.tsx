import { useGuidedStep } from "../lib/guide";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge } from "../components/Badges";
import { JargonSpans, ScholarStrip, ScholarTopicLine, useJargon, useScholar } from "../components/ScholarSources";

/** OpenAlex sources and jargon spans (neuropace/scholar sidecar) are kept out of the learner's notes for now:
 * research papers are the wrong altitude for a missed sentence. Flip this to show them again; nothing else
 * changes and the backend keeps serving /api/sessions/:id/scholar. */
const SHOW_SCHOLAR = false;

/** One lecture's notes: the moments you missed. Always rendered inside the library shell, which carries the
 * title, the session switcher and the Review tab (Explain deck or Whiteboard). */
export default function Lecture() {
  const { sessionId = "" } = useParams();
  const guide = useGuidedStep();
  const nav = useNavigate();
  const [data, setData] = useState<NotesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const ended = Boolean(data && data.session.status !== "running");
  // scholarly sources load after the notes and never block them (scholar sidecar)
  const scholar = useScholar(sessionId, SHOW_SCHOLAR && ended && data!.gaps.length > 0);
  const jargon = useJargon(sessionId, SHOW_SCHOLAR && ended);

  useEffect(() => {
    api.notes(sessionId).then(setData).catch((e) => setErr(errorText(e)));
  }, [sessionId]);

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
  const failed = data.gaps.some((g) => g.package_source === "failed");
  return (
    <div className="page narrow">
      {!ended ? (
        <div className="start">
          <Link className="btn btn-primary btn-lg btn-block" to={`/live/${sessionId}`}>
            Back to the lecture
          </Link>
          <button className="linklike" onClick={() => void endNow()} disabled={ending}>
            {ending ? "Writing your notes…" : "Or end it now and write my notes"}
          </button>
        </div>
      ) : null}
      {ended && failed ? (
        <button className="linklike" onClick={() => void regenerate()} disabled={regenerating}>
          {regenerating ? "Writing…" : "Some notes aren't written yet. Try again"}
        </button>
      ) : null}

      {SHOW_SCHOLAR && ended ? <JargonSpans data={jargon.data} /> : null}

      {data.gaps.length > 0 ? (
        <section className="stack">
          {!guide && <div className="eyebrow">What you missed</div>}
          {SHOW_SCHOLAR ? <ScholarTopicLine data={scholar.data} /> : null}
          {data.gaps.filter((g) => !guide?.decision.target_gap_id || g.id === guide.decision.target_gap_id).map((g) => {
            const failed = g.package_source === "failed";
            return (
              <article key={g.id} className={"moment-card" + (g.status === "closed" ? " is-landed" : "")}>
                <header className="moment-head">
                  <span className="m-num">{g.ord + 1}</span>
                  <div className="m-body">
                    <h3 className="m-term">{g.note?.key_term ?? (failed ? "Notes not written yet" : "Notes are on their way")}</h3>
                    <span className="m-meta">{range(g.t_start, g.t_end)}</span>
                  </div>
                  <Badge tone={g.status === "closed" ? "success" : g.status === "exhausted" ? "warning" : "neutral"}>{g.status === "closed" ? "landed" : g.status === "exhausted" ? "tricky" : "to do"}</Badge>
                </header>
                <div className="moment-text">
                  {g.summary ? <p className="m-said">{g.summary}</p> : null}
                  {g.note?.definition ? <p className="m-def"><span className="term">{g.note.key_term}</span> · {g.note.definition}</p> : null}
                  <details className="m-exact">
                    <summary>Exact words</summary>
                    <p>{g.span_text}</p>
                  </details>
                  {SHOW_SCHOLAR ? <ScholarStrip gap={scholar.byGap.get(g.id)} loading={scholar.loading} /> : null}
                </div>
                {!guide && (
                  <footer className="moment-foot">
                    <Link className="btn btn-primary btn-sm" to={`/library/${sessionId}/review`}>Review</Link>
                  </footer>
                )}
              </article>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
