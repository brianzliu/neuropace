import { useState } from "react";
import type { Form, TallySummary } from "../lib/types";
import { FORMS } from "../lib/types";

export const EXPLANATION_LABEL: Record<Form, string> = {
  words: "Plain language",
  analogy: "Analogies",
  visual: "Visuals",
  doing: "Practice examples",
};

/** Which explanation formats led to correct review answers. Always shown; when the tally is still
 * thin it says so plainly rather than hiding, so a demo never wonders where the card went. */
export function TallyCard({ tally, onReset }: { tally: TallySummary; onReset?: () => void }) {
  const [confirmReset, setConfirmReset] = useState(false);
  const scored = FORMS.map(form => {
    const { rescues: correct, attempts } = tally.forms[form];
    return { form, correct, attempts, rate: attempts > 0 ? correct / attempts : null };
  });
  const best = tally.enough_data
    ? scored.find(item => item.form === tally.preferred) ?? null
    : null;
  const answered = scored.reduce((sum, item) => sum + item.attempts, 0);

  return (
    <section className="panel explanation-results" aria-labelledby="explanation-results-title">
      <div className="dashboard-section-heading">
        <h2 id="explanation-results-title">What helps you understand</h2>
        {!tally.enough_data ? <span className="rescue-tag" role="status">Not enough data yet · {answered} review answer{answered === 1 ? "" : "s"}</span> : null}
      </div>
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
      {!tally.enough_data ? <p className="small muted result-note">Your strongest format is picked once a few more review questions have been answered; until then the tutor rotates formats.</p> : null}
      {onReset ? (
        <div className="preference-actions">
          {!confirmReset ? <button className="linklike" onClick={() => setConfirmReset(true)}>Reset learning patterns</button> : (
            <div className="reset-confirmation">
              <span>Clear your explanation and headset preferences?</span>
              <button className="btn btn-sm btn-danger" onClick={() => { setConfirmReset(false); onReset(); }}>Clear</button>
              <button className="btn btn-sm btn-plain" onClick={() => setConfirmReset(false)}>Cancel</button>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
