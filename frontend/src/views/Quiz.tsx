import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { QuizGet, QuizResult } from "../lib/types";
import { Badge } from "../components/Badges";

/** A stable shuffle of option positions per item and session, so the answer key's position never gives it away
 * (the lecture files list the correct option first) and the order stays the same across the two phases. */
function permutation(seed: string, n: number): number[] {
  let h = 2166136261;
  for (const ch of seed) {
    h ^= ch.charCodeAt(0);
    h = Math.imul(h, 16777619) >>> 0;
  }
  const idx = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    h ^= h << 13;
    h >>>= 0;
    h ^= h >>> 17;
    h ^= h << 5;
    h >>>= 0;
    const j = h % (i + 1);
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return idx;
}

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
  const orders = useMemo(() => Object.fromEntries((data?.items ?? []).map((it) => [it.id, permutation(sessionId + it.id, it.options.length)])), [data, sessionId]);
  if (err) return <div className="page narrow"><div className="card error-text">{err}</div></div>;
  if (!data) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const prior = data.answers.filter((a) => a.phase === phase);
  const answered = Object.keys(answers).length;
  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <h1 className="t-title1">Final quiz</h1>
          <div className="sub">
            {data.items.length} items. {prior.length ? `Already submitted for this phase: ${prior.filter((a) => a.correct).length}/${prior.length} correct (resubmitting replaces).` : "Not submitted yet for this phase."}
          </div>
        </div>
        <div className="segmented">
          {(["before", "after"] as const).map((p) => (
            <button
              key={p}
              className={phase === p ? "is-active" : ""}
              onClick={() => {
                setPhase(p);
                setResult(null);
                setAnswers({});
              }}
            >
              {p} review
            </button>
          ))}
        </div>
      </div>
      <div className="stack-lg">
        {data.items.length === 0 ? <div className="empty-state">This session's lecture has no quiz items.</div> : null}
        {data.items.map((it, n) => (
          <div key={it.id} className="card quiz-item">
            <div className="q">
              <span className="label-2 mono">{n + 1}.</span> {it.question}
            </div>
            <div className="options">
              {(orders[it.id] ?? it.options.map((_, i) => i)).map((orig, i) => {
                const o = it.options[orig];
                const sel = answers[it.id] === orig;
                const r = result?.per_item.find((p) => p.item_id === it.id);
                const cls = (sel ? " selected" : "") + (r && sel ? (r.correct ? " correct" : " wrong") : "");
                return (
                  <label key={i} className={"group-row clickable" + cls}>
                    <span className="row">
                      <input type="radio" className="radio" name={it.id} checked={sel} disabled={!!result} onChange={() => setAnswers({ ...answers, [it.id]: orig })} />
                      <span className="txt">{o}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
        {data.items.length ? (
          <div className="row">
            {!result ? (
              <button className="btn btn-primary btn-lg" disabled={answered < data.items.length || busy} onClick={() => void submit()}>
                Submit ({answered}/{data.items.length})
              </button>
            ) : (
              <>
                <Badge tone="success">
                  score {result.score}/{result.total} · {phase} review
                </Badge>
                <button
                  className="btn btn-plain"
                  onClick={() => {
                    setResult(null);
                    setAnswers({});
                  }}
                >
                  Answer again
                </button>
              </>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
