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
  const catchups = sess.catchups_shown;
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
            <div className="k">times you said lost me</div>
          </div>
          <div className="stat green">
            <div className="v">{catchups}</div>
            <div className="k">catch-ups shown</div>
          </div>
        </div>
        <p className="sub">{sess.gaps ? "Those moments are ready to restudy: one quick question each, explained a different way if you need it." : "You stayed with it the whole way. Nothing to restudy this time."}</p>
        <div className="row">
          {sess.gaps ? (
            <Link className="btn btn-primary btn-lg" to={`/restudy/${sessionId}`}>
              Restudy now
            </Link>
          ) : null}
          <Link className="btn" to={`/lecture/${sessionId}`}>
            {sess.gaps ? "Later, show me the notes" : "See the lecture"}
          </Link>
          <Link className="btn btn-plain" to="/">
            Home
          </Link>
        </div>
      </div>
    </div>
  );
}
