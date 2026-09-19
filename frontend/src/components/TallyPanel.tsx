import { FORM_LABEL, FORMS, type TallySummary } from "../lib/types";
import { pct } from "../lib/format";

export default function TallyPanel({ tally, compact }: { tally: TallySummary; compact?: boolean }) {
  return (
    <div className="panel">
      <h2>Your tally</h2>
      {!tally.enough_data ? (
        <div className="muted small" style={{ marginBottom: "0.5rem" }}>
          not enough data yet ({tally.total_attempts}/{tally.needed_attempts} scored cards)
        </div>
      ) : (
        <div className="small" style={{ marginBottom: "0.5rem" }}>
          best form so far: <b>{FORM_LABEL[tally.rank[0]]}</b>
        </div>
      )}
      {FORMS.map((f) => {
        const st = tally.forms[f];
        return (
          <div key={f} className={"tally-row" + (tally.pick === f ? " pick" : "")}>
            <div className="name">
              {FORM_LABEL[f]}
              {tally.pick === f ? <span className="badge accent" style={{ marginLeft: 6 }}>pick</span> : null}
            </div>
            <div className="bar" title={`posterior mean ${st.posterior_mean}`}>
              <i style={{ width: `${Math.round(st.posterior_mean * 100)}%` }} />
            </div>
            <div className="mono small muted">
              {st.rescues}/{st.attempts}{st.rate !== null ? ` · ${pct(st.rate)}` : ""}
            </div>
          </div>
        );
      })}
      {!compact ? (
        <div className="dim small" style={{ marginTop: "0.6rem" }}>
          A rescue is a form shown right before a correct answer. Scored by quiz answers only; the headset never updates this.
          New learners start from the average across learners.
        </div>
      ) : null}
    </div>
  );
}
