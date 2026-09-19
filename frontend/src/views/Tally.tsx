import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Learner, TallySummary } from "../lib/types";
import { FORM_LABEL, FORMS } from "../lib/types";

/** Card body shared by the Insights shell and the legacy /tally/:learnerId deep link.
 *  Learner-scoped: only ever renders the selected learner's own tally. */
export function TallyCard({ tally }: { tally: TallySummary }) {
  return (
    <>
      <section className="panel">
        {FORMS.map(form => <div className="tally-row" key={form}>
          <span>{FORM_LABEL[form]}</span><span className="small muted">{tally.forms[form].attempts} attempts</span>
          <span>{tally.forms[form].rescues} rescues</span>
        </div>)}
        {!tally.enough_data && <p className="small muted">More review answers are needed before comparing explanation formats.</p>}
      </section>
      <div className="panel">
        <h2>Population prior</h2>
        <div className="small muted">New learners start from the average across all learners (pseudo-count 2).</div>
        {FORMS.map((f) => (
          <div key={f} className="tally-row">
            <div className="name">{FORM_LABEL[f]}</div>
            <div className="mono small muted">
              {tally.population[f].rescues}/{tally.population[f].attempts} rescues pooled
            </div>
            <div className="mono small muted">prior Beta({tally.forms[f].prior_a}, {tally.forms[f].prior_b})</div>
          </div>
        ))}
      </div>
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
