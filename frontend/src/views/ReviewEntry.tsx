import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";

/** The Review tab (docs/PRODUCT.md §5a): goes straight into Office Hours for this lecture, no picker
 * screen in between. Office Hours' corner toggle offers Review on my own (Restudy, manual mode) instead,
 * for a self-test with no agent conversation. */
export default function ReviewEntry() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const sess = await api.session(sessionId);
        const oh = await api.createSession({
          mode: "office_hours",
          lecture_id: sess.lecture_id ?? undefined,
          learner_id: sess.learner_id,
        });
        if (!cancelled) navigate(`/office-hours/${oh.id}?original=${sessionId}`, { replace: true });
      } catch (e) {
        if (!cancelled) setErr(errorText(e));
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  return <div className="page narrow"><div className="loading">Opening…</div></div>;
}
