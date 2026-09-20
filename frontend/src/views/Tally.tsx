import type { Form, TallySummary } from "../lib/types";
import { FORMS } from "../lib/types";

export const EXPLANATION_LABEL: Record<Form, string> = {
  words: "Plain language",
  analogy: "Analogies",
  visual: "Visuals",
  doing: "Practice examples",
};

/** Shows which explanation formats led to correct review answers. */
export function TallyCard({ tally }: { tally: TallySummary }) {
  const scored = FORMS.map(form => {
    const { rescues: correct, attempts } = tally.forms[form];
    return { form, correct, attempts, rate: attempts > 0 ? correct / attempts : null };
  });
  const best = tally.enough_data
    ? scored.filter(item => item.rate !== null).sort((a, b) => (b.rate as number) - (a.rate as number) || b.attempts - a.attempts)[0] ?? null
    : null;

  return (
    <section className="panel explanation-results" aria-labelledby="explanation-results-title">
      <h2 id="explanation-results-title">What helps you understand</h2>
      {scored.map(({ form, correct, attempts, rate }) => {
        const percent = rate === null ? 0 : Math.round(rate * 100);
        return (
          <div className={`rescue-row${best?.form === form ? " is-best" : ""}`} key={form}>
            <div className="rescue-head">
              <span>{EXPLANATION_LABEL[form]}</span>
              <span className="result-value">{rate === null ? "Not tried" : `${percent}%`}</span>
            </div>
            <div className="rescue-track" role="img" aria-label={`${EXPLANATION_LABEL[form]} led to ${correct} correct answers out of ${attempts}`}>
              <div className="rescue-fill" style={{ width: `${percent}%` }} />
            </div>
            <span className="small muted">
              {attempts ? `${correct} of ${attempts} review answers correct` : "No review answers yet"}
            </span>
          </div>
        );
      })}
      {!tally.enough_data ? <p className="small muted result-note">Your strongest format will appear after a few more review questions.</p> : null}
    </section>
  );
}
