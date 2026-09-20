import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Learner, TallySummary } from "../lib/types";
import { FORM_LABEL, FORMS } from "../lib/types";

/** Card body shared by the Insights shell and the legacy /tally/:learnerId deep link.
 *  Learner-scoped: only ever renders the selected learner's own tally.
 *  Playful rescue bars, not a stats table. The spotlight names the best form
 *  only from real rescue counts when there is enough data — never invented. */
export function TallyCard({ tally }: { tally: TallySummary }) {
  const scored = FORMS.map(form => {
    const { rescues, attempts } = tally.forms[form];
    return { form, rescues, attempts, rate: attempts > 0 ? rescues / attempts : null };
  });
  const best = tally.enough_data
    ? scored.filter(s => s.rate !== null).sort((a, b) => (b.rate as number) - (a.rate as number) || b.attempts - a.attempts)[0] ?? null
    : null;
  return (
    <>
      <section className="panel tally-spotlight" aria-live="polite">
        {best ? (
          <p>
            <strong>{FORM_LABEL[best.form]}</strong> rescue{best.rescues === 1 ? "s" : ""} you most — {best.rescues} of {best.attempts} tries.
          </p>
        ) : (
          <p>Answer a few more review questions and your standout format shows up here.</p>
        )}
      </section>
      <section className="panel" aria-label="Rescues by explanation format">
        {scored.map(({ form, rescues, attempts, rate }) => (
          <div className={"rescue-row" + (best?.form === form ? " is-best" : "")} key={form}>
            <div className="rescue-head">
              <span>{FORM_LABEL[form]}</span>
              {best?.form === form ? <span className="rescue-tag">your best bet</span> : null}
            </div>
            <div className="rescue-track" role="img" aria-label={`${FORM_LABEL[form]}: ${rescues} rescues in ${attempts} tries`}>
              <div className="rescue-fill" style={{ width: `${rate === null ? 0 : Math.round(rate * 100)}%` }} />
            </div>
            <span className="small muted">{rescues} rescues in {attempts} {attempts === 1 ? "try" : "tries"}</span>
          </div>
        ))}
        {!tally.enough_data && <p className="small muted">More review answers are needed before comparing explanation formats.</p>}
      </section>
      <details className="panel prior-details">
        <summary>How new learners start</summary>
        <p className="small muted">Everyone begins from the room's average, pooled across learners — no personal data in the mix.</p>
        {FORMS.map((f) => (
          <div key={f} className="tally-row">
            <div className="name">{FORM_LABEL[f]}</div>
            <div className="small muted">
              {tally.population[f].rescues}/{tally.population[f].attempts} rescues pooled
            </div>
          </div>
        ))}
      </details>
    </>
  );
}

export default function Tally() {
  const { learnerId = "" } = useParams();
  const [tally, setTally] = useState<TallySummary | null>(null);
  const [learner, setLearner] = useState<Learner | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([api.tally(learnerId), api.learner(learnerId)])
      .then(([t, l]) => {
        setTally(t);
        setLearner(l);
      })
      .catch((e) => setErr(String(e)));
  }, [learnerId]);
  if (err) return <div className="panel error">{err}</div>;
  if (!tally) return <div className="panel muted">loading…</div>;
  return (
    <div className="col" style={{ maxWidth: 820 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{learner?.name ?? "learner"}: which form lands</h1>
        <Link to="/">home</Link>
      </div>
      <div className="muted">We don't believe in learning styles. We test it on you, and show you the data.</div>
      <TallyCard tally={tally} />
    </div>
  );
}
