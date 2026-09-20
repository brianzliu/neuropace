import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { SessionPublic } from "../lib/types";

/** Lecture complete (docs/PRODUCT.md §6): the numbers, then straight into Office Hours (or later). Review
 * on my own is a corner toggle once inside Office Hours, same entry point as the Review tab (ReviewEntry). */
export default function Done() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [sess, setSess] = useState<SessionPublic | null>(null);
  const [title, setTitle] = useState("Lecture");
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api
      .session(sessionId)
      .then((s) => {
        setSess(s);
        if (s.lecture_id) api.lecture(s.lecture_id).then((l) => setTitle(l.title)).catch(() => undefined);
      })
      .catch(() => undefined);
  }, [sessionId]);
  const startReview = async () => {
    if (!sess) return;
    setStarting(true);
    setErr(null);
    try {
      const oh = await api.createSession({
        mode: "office_hours",
        lecture_id: sess.lecture_id ?? undefined,
        learner_id: sess.learner_id,
      });
      navigate(`/office-hours/${oh.id}?original=${sessionId}`);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setStarting(false);
    }
  };
  if (!sess) return <div className="page narrow"><div className="loading">Wrapping up…</div></div>;
  const taps = sess.flags.filter((f) => f.source === "tap" || f.source === "key").length;
  return (
    <div className="page narrow">
      <div className="complete">
        <div className="big-mark">✓</div>
        <div>
          <div className="eyebrow">{title}</div>
          <h1 className="t-title1">Lecture done.</h1>
        </div>
        <div className="stats">
          <div className="stat orange">
            <div className="v">{sess.gaps}</div>
            <div className="k">moments to restudy</div>
          </div>
          <div className="stat">
            <div className="v">{taps}</div>
            <div className="k">times you asked to catch up</div>
          </div>
          <div className="stat green">
            <div className="v">{sess.catchups_shown}</div>
            <div className="k">catch-ups</div>
          </div>
        </div>
        <p className="sub">{sess.gaps ? "Each moment explained your way, then one quick question. About five minutes." : "You stayed with it the whole way. Nothing to restudy this time."}</p>        {sess.gaps ? (
          <>
            <button className="btn btn-primary btn-lg" onClick={() => void startReview()} disabled={starting}>
              {starting ? "Opening…" : "Review"}
            </button>
            {err ? <div className="callout danger label-3">{err}</div> : null}
            <Link className="linklike" to={`/lecture/${sessionId}`}>
              Later
            </Link>
          </>
        ) : (
          <Link className="btn btn-primary btn-lg" to="/">
            Done
          </Link>
        )}
      </div>
    </div>
  );
}
