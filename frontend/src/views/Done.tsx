import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { SessionPublic } from "../lib/types";

/** Lecture complete (docs/PRODUCT.md §6): the numbers, then restudy now or later. */
export default function Done() {
  const { sessionId = "" } = useParams();
  const [sess, setSess] = useState<SessionPublic | null>(null);
  const [title, setTitle] = useState("Lecture");
  useEffect(() => {
    api
      .session(sessionId)
      .then((s) => {
        setSess(s);
        if (s.lecture_id) api.lecture(s.lecture_id).then((l) => setTitle(l.title)).catch(() => undefined);
      })
      .catch(() => undefined);
  }, [sessionId]);
  if (!sess) return <div className="page narrow"><div className="loading">Wrapping up…</div></div>;
  const taps = sess.flags.filter((f) => f.source === "tap" || f.source === "key").length;
  // catch-ups the student actually saw: every tap card, plus the drift cards they chose to open
  const seen = sess.flags.filter((f) => f.catchup_shown && (f.source === "tap" || f.source === "key" || f.opened)).length;
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
            <div className="v">{seen}</div>
            <div className="k">catch-ups</div>
          </div>
        </div>
        <p className="sub">{sess.gaps ? "Each moment explained your way, then one quick question. About five minutes." : sess.words ? "No moments were saved for restudy this time." : "No transcript was captured. Check your microphone before starting another lecture."}</p>        {sess.gaps ? (
          <>
            <Link className="btn btn-primary btn-lg" to={`/restudy/${sessionId}?mode=tutor`}>
              Private tutoring
            </Link>
            <Link className="btn btn-blue" to={`/restudy/${sessionId}?mode=manual`}>
              Review on my own
            </Link>
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
