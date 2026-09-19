import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { FORM_LABEL, FORMS, type Learner, type TallySummary } from "../lib/types";
import { pct } from "../lib/format";
import { Badge } from "../components/Badges";
import { Group, Row } from "../components/Inspector";

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
  if (err) return <div className="page narrow"><div className="card error-text">{err}</div></div>;
  if (!tally) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <h1 className="t-title1">{learner?.name ?? "Learner"}: which form lands</h1>
          <div className="sub">We don't believe in learning styles. We test it on you, and show you the data.</div>
        </div>
        {tally.enough_data ? <Badge tone="success">enough data</Badge> : <Badge>not enough data yet · {tally.total_attempts}/{tally.needed_attempts} scored cards</Badge>}
      </div>
      <div className="stack-lg">
        <div className="card" style={{ padding: 0 }}>
          <table className="table">
            <thead>
              <tr>
                <th>form</th>
                <th className="num">rescues</th>
                <th className="num">attempts</th>
                <th className="num">rate</th>
                <th>posterior mean</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {FORMS.map((f) => {
                const st = tally.forms[f];
                return (
                  <tr key={f}>
                    <td>{FORM_LABEL[f]}</td>
                    <td className="num">{st.rescues}</td>
                    <td className="num">{st.attempts}</td>
                    <td className="num">{st.rate === null ? "n/a" : pct(st.rate)}</td>
                    <td>
                      <span className="row" style={{ flexWrap: "nowrap" }}>
                        <span className="progress" style={{ width: 140 }}>
                          <i style={{ width: `${Math.round(st.posterior_mean * 100)}%` }} />
                        </span>
                        <span className="mono t-footnote label-2">{st.posterior_mean.toFixed(2)}</span>
                      </span>
                    </td>
                    <td>{tally.pick === f ? <Badge tone="accent">pick</Badge> : null}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="t-footnote label-2">
          A rescue is a form shown right before a correct answer. Scored by quiz answers only; the headset never updates this. The pick is a Thompson sample over the posteriors, so untried forms keep getting explored.
        </div>
        <Group title="Population prior" note="New learners start from the average across all learners (pseudo-count 2).">
          {FORMS.map((f) => (
            <Row key={f} label={FORM_LABEL[f]}>
              <span className="mono">
                {tally.population[f].rescues}/{tally.population[f].attempts} pooled
              </span>
              <span className="mono label-3">
                Beta({tally.forms[f].prior_a}, {tally.forms[f].prior_b})
              </span>
            </Row>
          ))}
        </Group>
      </div>
    </div>
  );
}
