import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";
import { FORM_ICON, FORM_LABEL, FORMS, type Profile } from "../lib/types";
import { Badge } from "../components/Badges";

/** You (docs/PRODUCT.md §6): streak, moments, how you learn best, and "Not you? Start fresh". */
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
  const best = [...FORMS].sort((a, b) => t.forms[b].posterior_mean - t.forms[a].posterior_mean)[0];
  return (
    <div className="page">
      <header className="hero">
        <h1 className="t-large">How you learn</h1>
        <p className="sub">Reflow does not assume a learning style. Every explanation is scored by whether you answered the question after it, and the winner is what you see first next time.</p>
      </header>
      <div className="profile-grid">
        <div className="stack-lg">
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
          <div className="card">
            <div className="card-header">
              <span className="card-title">What works for you</span>
              {t.enough_data ? <Badge tone="success">{FORM_LABEL[best]} leads</Badge> : <Badge>still learning · {t.total_attempts}/{t.needed_attempts} answers</Badge>}
            </div>
            <div className="stack" style={{ gap: 0 }}>
              {FORMS.map((f) => {
                const st = t.forms[f];
                const focusPct = st.focus?.mean_focus != null ? Math.round(st.focus.mean_focus * 100) : null;
                return (
                  <div key={f} className="pref">
                    <span className="f-icon">{FORM_ICON[f]}</span>
                    <div>
                      <div className="p-name">
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
            <div className="t-footnote label-2" style={{ marginTop: 12 }}>
              Rescued means the explanation came right before a correct answer. Held your attention is measured with the headset while you read it; it switches an explanation early, it never picks the winner.
            </div>
          </div>
        </div>
        <aside className="stack-lg">
          <div className="card">
            <div className="card-header">
              <span className="card-title">This device</span>
            </div>
            <div className="status-list">
              <div className="status-line">
                <span className={"dot " + (p.calibrated ? "ok" : "warn")} />
                <span>Focus calibration</span>
                <span className="sl-value">{p.calibrated ? "saved from your last lecture" : "learned during your next lecture"}</span>
              </div>
              <div className="status-line">
                <span className="dot ok" />
                <span>Your data</span>
                <span className="sl-value">stays on this laptop</span>
              </div>
            </div>
            <div style={{ marginTop: 14 }}>
              {!confirm ? (
                <button className="btn btn-sm" onClick={() => setConfirm(true)}>
                  Not you? Start fresh
                </button>
              ) : (
                <div className="row">
                  <span className="t-footnote label-2">Forget the preferences and calibration on this device. Lectures and notes stay.</span>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => {
                      api.resetProfile().then(() => {
                        setConfirm(false);
                        void load();
                      });
                    }}
                  >
                    Yes, start fresh
                  </button>
                  <button className="btn btn-sm btn-plain" onClick={() => setConfirm(false)}>
                    Keep
                  </button>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
