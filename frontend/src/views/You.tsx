import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";
import { FORM_ICON, FORM_LABEL, FORMS, type Profile } from "../lib/types";
import { Badge } from "../components/Badges";

/** You (docs/PRODUCT.md §6): your numbers, how you learn best, and one line about this device. */
export default function You() {
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const load = () => api.profile().then(setP).catch((e) => setErr(errorText(e)));
  useEffect(() => {
    void load();
  }, []);
  if (err) return <div className="page narrow"><div className="callout danger">{err}</div></div>;
  if (!p) return <div className="page narrow"><div className="loading">Loading…</div></div>;
  const t = p.tally;
  const maxRescues = Math.max(1, ...FORMS.map((f) => t.forms[f].rescues));
  const order = t.rank && t.rank.length ? t.rank : [...FORMS].sort((a, b) => t.forms[b].posterior_mean - t.forms[a].posterior_mean);
  const best = t.preferred ?? order[0];
  return (
    <div className="page narrow">
      <header className="hero">
        <h1 className="t-large">You</h1>
        <p className="sub">Reflow does not assume a learning style. It tests explanations on you and keeps what lands.</p>
      </header>
      <div className="stats">
        <div className="stat orange">
          <div className="v">{p.stats.streak_days}</div>
          <div className="k">day streak</div>
        </div>
        <div className="stat">
          <div className="v">{p.stats.lectures}</div>
          <div className="k">lectures</div>
        </div>
        <div className="stat green">
          <div className="v">{p.stats.moments_restudied}</div>
          <div className="k">moments landed</div>
        </div>
      </div>

      <section className="stack" style={{ marginTop: 28 }}>
        <div className="row between">
          <div className="eyebrow">How you learn best</div>
          {t.enough_data ? <Badge tone="success">{FORM_LABEL[best]} is your preferred way</Badge> : <Badge>still learning · {t.total_attempts}/{t.needed_attempts} explanations scored</Badge>}
        </div>
        <div className="prefs">
          {order.map((f, i) => {
            const st = t.forms[f];
            const focusPct = st.focus?.mean_focus != null ? Math.round(st.focus.mean_focus * 100) : null;
            return (
              <div key={f} className={"pref" + (i === 0 && t.enough_data ? " top" : "")}>
                <span className="f-icon">{FORM_ICON[f]}</span>
                <div>
                  <div className="p-name">
                    <span className="rank-num">{i + 1}</span>
                    {FORM_LABEL[f]}
                    {t.pick === f ? <Badge tone="accent">next time</Badge> : null}
                  </div>
                  <div className="p-bars">
                    <div className="p-bar">
                      <span>rescued you</span>
                      <span className="progress thin">
                        <i style={{ width: `${Math.round((st.rescues / maxRescues) * 100)}%` }} />
                      </span>
                      <span className="mono">{st.attempts ? `${st.rescues}/${st.attempts}` : "–"}</span>
                    </div>
                    <div className="p-bar">
                      <span>held your attention</span>
                      <span className="progress thin blue">
                        <i style={{ width: `${focusPct ?? 0}%` }} />
                      </span>
                      <span className="mono">{focusPct != null ? `${focusPct}%` : "–"}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="t-footnote label-2">Ranked by what works: whether the explanation came right before a correct answer counts most, how much of it held your attention (measured with the headset while you read) counts too. A drift while reading switches the explanation on the spot.</div>
      </section>

      <footer className="you-foot">
        <span>{p.calibrated ? "Focus calibration saved from your last lecture." : "Focus calibration is learned during your next lecture."} Your data stays on this laptop.</span>
        {!confirm ? (
          <button className="linklike" onClick={() => setConfirm(true)}>
            Not you? Start fresh
          </button>
        ) : (
          <span className="row">
            <span className="t-footnote">Forget the preferences and calibration on this device. Lectures stay.</span>
            <button
              className="btn btn-sm btn-danger"
              onClick={() => {
                api.resetProfile().then(() => {
                  setConfirm(false);
                  void load();
                });
              }}
            >
              Start fresh
            </button>
            <button className="btn btn-sm btn-plain" onClick={() => setConfirm(false)}>
              Keep
            </button>
          </span>
        )}
      </footer>
    </div>
  );
}
