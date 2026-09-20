import { useLibrary } from "./Library";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { NotesResponse } from "../lib/types";
import { range } from "../lib/format";
import { Badge } from "../components/Badges";
import SessionBack from "../components/BackLink";
import TranscriptPane from "../components/TranscriptPane";
import type { Flag } from "../lib/types";

/** One lecture: the transcript and the moments you missed. Starting a review happens from the Review tab
 * (ReviewEntry, which goes straight to Office Hours) when this page is inside the library shell; standalone
 * (no shell, e.g. right after a lecture ends) it offers that same entry point itself. */
export default function Lecture() {
  const { sessionId = "" } = useParams();
  const library = useLibrary();
  const nav = useNavigate();
  const [data, setData] = useState<NotesResponse | null>(null);
  const [title, setTitle] = useState("Lecture");
  const [err, setErr] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [startingOfficeHours, setStartingOfficeHours] = useState(false);

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
  const startOfficeHours = async () => {
    if (!data) return;
    setStartingOfficeHours(true);
    try {
      const sess = await api.createSession({
        mode: "office_hours",
        lecture_id: data.session.lecture_id ?? undefined,
        learner_id: data.session.learner_id,
      });
      nav(`/office-hours/${sess.id}?original=${sessionId}`);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setStartingOfficeHours(false);
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

  if (err) return <div className="page narrow">{!library ? <div className="page-back"><SessionBack /></div> : null}<div className="callout danger">{err}</div></div>;
  if (!data) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const running = data.session.status === "running";
  const failed = data.gaps.filter((g) => g.package_source === "failed");
  const total = data.gaps.length;
  return (
    <div className="page narrow">
      {!library ? (
        <div className="page-back">
          <SessionBack />
        </div>
      ) : null}
      {!library ? (
        <header className="hero">
          <h1 className="t-large">{title}</h1>
        </header>
      ) : null}

      {running ? (
        <div className="start">
          <Link className="btn btn-primary btn-lg btn-block" to={`/live/${sessionId}`}>
            Back to the lecture
          </Link>
          <button className="linklike" onClick={() => void endNow()} disabled={ending}>
            {ending ? "Writing your notes…" : "Or end it now and write my notes"}
          </button>
        </div>
      ) : null}

      {!running && !library ? (
        <div className="start">
          <button className="btn btn-primary btn-lg btn-block" onClick={() => void startOfficeHours()} disabled={startingOfficeHours || failed.length > 0}>
            {startingOfficeHours ? "Opening…" : "Review"}
          </button>
          {failed.length ? (
            <button className="linklike" onClick={() => void regenerate()} disabled={regenerating}>
              {regenerating ? "Writing…" : "Some notes aren't written yet — try again"}
            </button>
          ) : null}
        </div>
      ) : null}
      {!running && library && failed.length ? (
        <button className="linklike" onClick={() => void regenerate()} disabled={regenerating}>
          {regenerating ? "Writing…" : "Some notes aren't written yet — try again"}
        </button>
      ) : null}

      {data.words.length ? (
        <details className="moment-row whole" open={total === 0}>
          <summary>
            <span className="m-body">
              <span className="m-summary">The whole lecture</span>
              <span className="m-meta">{data.words.length} words{total ? ` · the ${total} moment${total === 1 ? "" : "s"} you missed are highlighted` : ""}</span>
            </span>
          </summary>
          <div className="m-detail">
            <TranscriptPane
              words={data.words}
              interim={[]}
              now={-1}
              autoScroll={false}
              className="reading"
              flags={data.gaps.map((g): Flag => ({ id: g.id, source: "eeg", t_trigger: g.t_end, t_start: g.t_start, t_end: g.t_end, catchup_shown: null, catchup_form: null, opened: false }))}
            />
          </div>
        </details>
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
