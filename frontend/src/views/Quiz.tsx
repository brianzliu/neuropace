import { useGuidedStep } from "../lib/guide";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { QuizExplanation, QuizGet, QuizResult } from "../lib/types";
import SessionBack from "../components/BackLink";
import { useLibrary } from "./Library";

export default function Quiz() {
  const { sessionId = "" } = useParams();
  const library = useLibrary();
  const guide = useGuidedStep();
  const [data, setData] = useState<QuizGet | null>(null);
  const [phase, setPhase] = useState<"before" | "after">("before");
  const [prompt, setPrompt] = useState("");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [explanations, setExplanations] = useState<Record<string, QuizExplanation>>({});
  const [explanationLoading, setExplanationLoading] = useState<Record<string, boolean>>({});
  const [explanationErrors, setExplanationErrors] = useState<Record<string, string>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api.quiz(sessionId).then((quiz) => {
      if (!active) return;
      setData(quiz);
      setPhase(quiz.answers.some((answer) => answer.phase === "before") ? "after" : "before");
      const first = quiz.items[0];
      if (first) {
        void api.quizPrompt(sessionId, first.id).then((message) => {
          if (active) setPrompt(message.text);
        }).catch(() => {});
      }
    }).catch((e) => { if (active) setErr(String(e)); });
    return () => { active = false; };
  }, [sessionId]);
  const submit = async () => {
    setBusy(true);
    try {
      const scored = await api.submitQuiz(sessionId, phase, answers);
      setResult(scored);
      guide?.reportOutcome(scored.score === scored.total ? "hit" : "miss");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };
  const explain = async (itemId: string, choice: number) => {
    if (!result) return;
    const key = `${itemId}:${choice}`;
    if (explanations[key] || explanationLoading[key]) return;
    setExplanationLoading((current) => ({ ...current, [key]: true }));
    setExplanationErrors((current) => ({ ...current, [key]: "" }));
    try {
      const explanation = await api.quizExplanation(sessionId, itemId, choice);
      setExplanations((current) => ({ ...current, [key]: explanation }));
    } catch {
      setExplanationErrors((current) => ({ ...current, [key]: "Couldn't explain this choice. Try again." }));
    } finally {
      setExplanationLoading((current) => ({ ...current, [key]: false }));
    }
  };
  if (err) return <div className="page narrow">{!library ? <div className="page-back"><SessionBack /></div> : null}<div className="card error-text">{err}</div></div>;
  if (!data) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const answered = Object.keys(answers).length;
  return (
    <div className="page narrow">
      {!library ? <div className="page-back"><SessionBack /></div> : null}
      <div className="page-head quiz-head">
        <div>
          <h1 className="t-title1">Quiz</h1>
          {prompt ? <p className="quiz-prompt">{prompt}</p> : null}
        </div>
      </div>
      <div className="stack-lg">
        {data.items.length === 0 ? <div className="empty-state">This session's lecture has no quiz items.</div> : null}
        {data.items.map((it, n) => (
          <div key={it.id} className="card quiz-item">
            <div className="q">
              <span className="label-2 mono">{n + 1}.</span> {it.question}
            </div>
            <div className="options quiz-options">
              {it.options.map((o, i) => {
                const sel = answers[it.id] === i;
                const r = result?.per_item.find((p) => p.item_id === it.id);
                const key = `${it.id}:${i}`;
                const explanation = explanations[key];
                const judged = explanation?.correct ?? (r && sel ? r.correct : null);
                const cls = (sel ? " selected" : "") + (judged === true ? " correct" : judged === false ? " wrong" : "");
                return (
                  <div className={`quiz-choice${cls}`} key={i}>
                    <label className="group-row clickable" onClick={(event) => {
                      if (!result) return;
                      event.preventDefault();
                      void explain(it.id, i);
                    }}>
                      <span className="row">
                        <input type="radio" className="radio" name={it.id} checked={sel} disabled={!!result} onChange={() => setAnswers({ ...answers, [it.id]: i })} />
                        <span className="txt">{o}</span>
                      </span>
                    </label>
                    {explanationLoading[key] ? <p className="quiz-explanation muted" role="status">Writing an explanation…</p> : null}
                    {explanation ? <p className="quiz-explanation">{explanation.text}</p> : null}
                    {explanationErrors[key] ? <button className="quiz-explanation-error" onClick={() => void explain(it.id, i)}>{explanationErrors[key]}</button> : null}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        {data.items.length ? (
          <div className="card row">
            {!result ? (
              <button className="btn btn-primary btn-lg" disabled={answered < data.items.length || busy} onClick={() => void submit()}>
                Submit ({answered}/{data.items.length})
              </button>
            ) : (
              <p className="quiz-result" role="status">
                {result.score} of {result.total} correct. Select any answer to see why.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
