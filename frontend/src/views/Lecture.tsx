import { useGuidedStep } from "../lib/guide";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge } from "../components/Badges";
import { JargonSpans, ScholarStrip, ScholarTopicLine, useJargon, useScholar } from "../components/ScholarSources";

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
  const scholar = useScholar(sessionId, ended && data!.gaps.length > 0);
  const jargon = useJargon(sessionId, ended);

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

      {ended ? <JargonSpans data={jargon.data} /> : null}

      {data.gaps.length > 0 ? (
        <section className="stack">
          {!guide && <div className="eyebrow">What you missed</div>}
          <ScholarTopicLine data={scholar.data} />
          {data.gaps.filter(g => !guide?.decision.target_gap_id || g.id === guide.decision.target_gap_id).map((g) => (
            <details key={g.id} className="moment-row" open={guide ? true : undefined}>
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
                <ScholarStrip gap={scholar.byGap.get(g.id)} loading={scholar.loading} />
              </div>
            </details>
          ))}
        </section>
      ) : null}
    </div>
  );
}
