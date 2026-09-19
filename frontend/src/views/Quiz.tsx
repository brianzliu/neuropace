import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { QuizGet, QuizResult } from "../lib/types";

export default function Quiz() {
  const { sessionId = "" } = useParams();
  const [data, setData] = useState<QuizGet | null>(null);
  const [phase, setPhase] = useState<"before" | "after">("before");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.quiz(sessionId).then(setData).catch((e) => setErr(String(e)));
  }, [sessionId]);
  const submit = async () => {
    setBusy(true);
    try {
      setResult(await api.submitQuiz(sessionId, phase, answers));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };
  if (err) return <div className="panel error">{err}</div>;
  if (!data) return <div className="panel muted">loading…</div>;
  const prior = data.answers.filter((a) => a.phase === phase);
  const answered = Object.keys(answers).length;
  return (
    <div className="col" style={{ maxWidth: 900 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>Final quiz</h1>
        <div className="row">
          <label>
            phase
            <select value={phase} onChange={(e) => { setPhase(e.target.value as "before" | "after"); setResult(null); setAnswers({}); }}>
              <option value="before">before review</option>
              <option value="after">after review</option>
            </select>
          </label>
          <Link to={`/notes/${sessionId}`}>notes</Link>
          <Link to="/">home</Link>
        </div>
      </div>
      <div className="muted small">
        {data.items.length} items. {prior.length ? `Already submitted for this phase: ${prior.filter((a) => a.correct).length}/${prior.length} correct (resubmitting replaces).` : "Not submitted yet for this phase."}
      </div>
      {data.items.length === 0 ? <div className="panel">this session's lecture has no quiz items</div> : null}
      {data.items.map((it, n) => (
        <div key={it.id} className="quiz-item">
          <div>
            <span className="muted mono">{n + 1}.</span> {it.question}
          </div>
          <div className="options" style={{ marginTop: "0.4rem" }}>
            {it.options.map((o, i) => {
              const sel = answers[it.id] === i;
              const r = result?.per_item.find((p) => p.item_id === it.id);
              const cls = (sel ? "sel" : "") + (r && sel ? (r.correct ? " correct" : " wrong") : "");
              return (
                <button key={i} className={cls} onClick={() => setAnswers({ ...answers, [it.id]: i })} disabled={!!result}>
                  <span className="k">{i + 1}</span>
                  {o}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {data.items.length ? (
        <div className="row">
          {!result ? (
            <button className="primary" disabled={answered < data.items.length || busy} onClick={() => void submit()}>
              submit ({answered}/{data.items.length})
            </button>
          ) : (
            <>
              <span className="outcome hit">
                score {result.score}/{result.total} ({phase})
              </span>
              <button className="ghost" onClick={() => { setResult(null); setAnswers({}); }}>
                answer again
              </button>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
