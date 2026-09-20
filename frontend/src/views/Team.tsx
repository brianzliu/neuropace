import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, SessionPublic } from "../lib/types";
import { Badge, StatusDot } from "../components/Badges";
import DeepgramSettings from "../components/DeepgramSettings";
import ModelSettings from "../components/ModelSettings";
import { useNavigate } from "react-router-dom";

/** For the team (docs/PRODUCT.md §3): setup readiness, a technical session start, replay, loss map, study quiz. */
export default function Team() {
  const nav = useNavigate();
  const [d, setD] = useState<Doctor | null>(null);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [participant, setParticipant] = useState("");
  const [form, setForm] = useState<SessionCreate>({ lecture_id: null, mode: "live", catchup_policy: "always", baseline_seconds: 180, use_stored_baseline: false, auto_pause: true, headset: "auto", totem: "auto", transcript: "auto" });
  useEffect(() => {
    api.doctor().then(setD).catch(() => setD(null));
    api.lectures().then((l) => {
      setLectures(l.lectures);
      setForm((f) => ({ ...f, lecture_id: f.lecture_id ?? l.lectures[0]?.id ?? null }));
    });
    api.sessions().then((s) => setSessions(s.sessions.slice(0, 12)));
  }, []);
  const start = async () => {
    setErr(null);
    try {
      const s = await api.createSession({ ...form, learner_name: participant.trim() || null });
      nav(`/live/${s.id}?details=1`);
    } catch (e) {
      setErr(String(e));
    }
  };
  return (
    <div className="page">
      <header className="hero">
        <div className="eyebrow">For the team</div>
        <h1 className="t-title1">Setup, signals and the study</h1>
        <p className="sub">Nothing on this page is for a student. Readiness in plain words plus the technical detail, and the tools behind the demo and the study.</p>
      </header>
      <div className="two-col">
        <div className="stack-lg">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Readiness</span>
              {d ? <span className="label-2 t-footnote mono">{d.platform}</span> : null}
            </div>
            {!d ? (
              <div className="label-2">checking…</div>
            ) : (
              <div className="status-list">
                <Line ok={d.keys.deepgram && d.deepgram.ok} label="Deepgram (transcription)" value={d.keys.deepgram ? (d.deepgram.ok ? "reachable" : d.deepgram.reason ?? "unreachable") : "no key: set DEEPGRAM_API_KEY in .env"} />
                <Line
                  ok={d.keys[d.llm_provider] && d[d.llm_provider].ok}
                  label={`${d.llm_provider === "gemini" ? "Gemini" : d.llm_provider === "openrouter" ? "OpenRouter" : "OpenAI"} (recaps, notes, artifacts)`}
                  value={d.keys[d.llm_provider] ? (d[d.llm_provider].ok ? d[d.llm_provider].model : `${d[d.llm_provider].model} unavailable`) : "no model key"}
                />
                <Line ok={d.headset.kind === "real"} warn label="Headset" value={d.headset.kind === "real" ? `MindWave on ${d.headset.port}` : "none found: sessions simulate one"} />
                <Line ok={d.totem.kind === "real"} accent label="Totem" value={d.totem.kind === "real" ? `Arduino on ${d.totem.port}` : "none found: keyboard fallback (Space/T, terminal keys)"} />
                <Line ok={d.frontend_built} label="Frontend build" value={d.frontend_built ? "built" : "run pnpm build"} />
              </div>
            )}
            {d && d.serial_ports.length ? (
              <details className="disclosure" style={{ marginTop: 12 }}>
                <summary>Serial ports</summary>
                <div className="body">
                  {d.serial_ports.map((p) => (
                    <div key={p.device} className="mono">
                      {p.device} {p.description} {p.hwid ? `[${p.hwid}]` : ""}
                    </div>
                  ))}
                </div>
              </details>
            ) : null}
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Keys and model</span>
            </div>
            <div className="label-2 t-footnote">Students never see this. Keys live in this backend process only.</div>
            <DeepgramSettings />
            <ModelSettings />
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Start a technical session</span>
            </div>
            {err ? <div className="callout danger">{err}</div> : null}
            <div className="adv">
              <label className="opt">
                <span className="opt-k">Lecture</span>
                <select className="select" value={form.lecture_id ?? ""} onChange={(e) => setForm({ ...form, lecture_id: e.target.value || null })}>
                  <option value="">Live microphone (Deepgram)</option>
                  {lectures.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.title}
                    </option>
                  ))}
                </select>
              </label>
              <div className="row">
                <label className="opt">
                  <span className="opt-k">Mode</span>
                  <span className="segmented sm">
                    <button className={form.mode === "live" ? "is-active" : ""} onClick={() => setForm({ ...form, mode: "live" })}>live</button>
                    <button className={form.mode === "recorded" ? "is-active" : ""} disabled={!form.lecture_id} onClick={() => setForm({ ...form, mode: "recorded" })}>recorded</button>
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Catch-ups</span>
                  <span className="segmented sm">
                    <button className={form.catchup_policy === "always" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "always" })}>always</button>
                    <button className={form.catchup_policy === "randomized" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "randomized" })}>randomized (study)</button>
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Baseline</span>
                  <span className="row">
                    <span className="segmented sm">
                      <button className={form.baseline_seconds === 30 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 30 })}>30 s</button>
                      <button className={form.baseline_seconds === 180 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 180 })}>3 min</button>
                    </span>
                    <input className="field field-num" type="number" min={5} value={form.baseline_seconds} onChange={(e) => setForm({ ...form, baseline_seconds: Number(e.target.value) })} />
                  </span>
                </label>
              </div>
              <div className="row">
                <label className="opt">
                  <span className="opt-k">Headset</span>
                  <input className="field" value={form.headset} onChange={(e) => setForm({ ...form, headset: e.target.value })} placeholder="auto | sim | fake | replay:<dir> | port" />
                </label>
                <label className="opt">
                  <span className="opt-k">Totem</span>
                  <input className="field" value={form.totem} onChange={(e) => setForm({ ...form, totem: e.target.value })} placeholder="auto | keyboard | port" />
                </label>
                <label className="opt">
                  <span className="opt-k">Study participant</span>
                  <input className="field" value={participant} onChange={(e) => setParticipant(e.target.value)} placeholder="optional, e.g. P07" />
                </label>
              </div>
              <div className="row">
                <button className="btn btn-blue" onClick={() => void start()}>
                  Start with details on
                </button>
                <span className="t-footnote label-2">Opens the live screen with the signal trace, the rolling recaps and the demo keys visible.</span>
              </div>
            </div>
          </div>
        </div>

        <aside className="stack-lg">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Explanation templates</span>
              <Link className="btn btn-sm" to="/team/artifacts/sample">
                Sample data
              </Link>
            </div>
            <div className="label-2 t-footnote">The ten renderings (words, comparison, picture, numbers, curve, in order, side by side, in motion, steps, worked example) with built-in data, to check each one without a session.</div>
          </div>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Lecture tools</span>
            </div>
            <div className="stack">
              {lectures.map((l) => (
                <div key={l.id} className="row between">
                  <span className="t-subhead">{l.title}</span>
                  <Link className="btn btn-sm" to={`/team/lossmap/${l.id}`}>
                    Loss map
                  </Link>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Sessions</span>
            </div>
            <div className="session-list">
              {sessions.map((s) => (
                <div key={s.id} className="session-item">
                  <div className="si-main">
                    <div className="si-title mono">{s.id}</div>
                    <div className="si-meta">
                      {s.mode} · {s.learner_id} · {s.flags.length} flags · {s.gaps} gaps
                    </div>
                  </div>
                  <Badge tone={s.status === "running" ? "success" : "neutral"}>{s.status}</Badge>
                  <span className="row" style={{ gap: 6 }}>
                    <Link className="btn btn-sm" to={`/team/replay/${s.id}`}>
                      Replay
                    </Link>
                    {s.gaps ? (
                      <Link className="btn btn-sm" to={`/team/artifacts/${s.id}`}>
                        Explanations
                      </Link>
                    ) : null}
                    {s.lecture_id ? (
                      <Link className="btn btn-sm" to={`/team/quiz/${s.id}`}>
                        Quiz
                      </Link>
                    ) : null}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Line({ ok, warn, accent, label, value }: { ok: boolean; warn?: boolean; accent?: boolean; label: string; value: string }) {
  return (
    <div className="status-line">
      <StatusDot state={ok ? "ok" : accent ? "accent" : warn ? "warn" : "bad"} />
      <span>{label}</span>
      <span className={"sl-value" + (!ok && !warn && !accent ? " error-text" : "")}>{value}</span>
    </div>
  );
}
