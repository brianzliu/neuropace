import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, Learner, SessionPublic } from "../lib/types";
import { mmss } from "../lib/format";
import { Badge, StatusDot } from "../components/Badges";

type HeadsetChoice = "auto" | "sim" | "fake" | "custom";
type TotemChoice = "auto" | "keyboard" | "custom";

function statusLabel(s: SessionPublic): { text: string; tone: "success" | "accent" | "neutral" } {
  if (s.status === "running") return { text: "Listening now", tone: "success" };
  if (s.status === "reviewed") return { text: "Reviewed", tone: "accent" };
  return { text: s.gaps ? "Notes ready" : "Nothing missed", tone: "neutral" };
}

/** Student-facing start screen: two decisions and a button. Everything technical lives under Setup. */
export default function Home() {
  const nav = useNavigate();
  const [me, setMe] = useState<Learner | null>(null);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [participant, setParticipant] = useState("");
  const [headsetChoice, setHeadsetChoice] = useState<HeadsetChoice>("auto");
  const [customHeadset, setCustomHeadset] = useState("");
  const [totemChoice, setTotemChoice] = useState<TotemChoice>("auto");
  const [customTotem, setCustomTotem] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<SessionCreate>(() => ({
    lecture_id: null,
    mode: "live",
    catchup_policy: "always",
    baseline_seconds: 180,
    use_stored_baseline: false,
    auto_pause: true,
    headset: "auto",
    totem: "auto",
    transcript: "auto",
  }));

  const onHeadsetChoice = (v: string) => {
    const choice = (["auto", "sim", "fake", "custom"].includes(v) ? v : "auto") as HeadsetChoice;
    setHeadsetChoice(choice);
    setForm((f) => ({ ...f, headset: choice === "custom" ? customHeadset || "auto" : choice }));
  };
  const onTotemChoice = (v: string) => {
    const choice = (["auto", "keyboard", "custom"].includes(v) ? v : "auto") as TotemChoice;
    setTotemChoice(choice);
    setForm((f) => ({ ...f, totem: choice === "custom" ? customTotem || "auto" : choice }));
  };

  const load = async () => {
    // each call stands alone: a failing one must not blank the lecture list
    const [m, lec, s] = await Promise.allSettled([api.learner("me"), api.lectures(), api.sessions()]);
    if (m.status === "fulfilled") setMe(m.value);
    if (lec.status === "fulfilled") {
      setLectures(lec.value.lectures);
      setForm((f) => ({ ...f, lecture_id: f.lecture_id ?? lec.value.lectures[0]?.id ?? null }));
    } else {
      setErr(errorText(lec.reason));
    }
    if (s.status === "fulfilled") setSessions(s.value.sessions.slice(0, 6));
  };
  useEffect(() => {
    void load();
    api.doctor().then(setDoctor).catch(() => setDoctor(null));
  }, []);

  const start = async () => {
    setErr(null);
    setBusy(true);
    try {
      const body: SessionCreate = { ...form, lecture_id: form.lecture_id || null, learner_name: participant.trim() || null };
      const s = await api.createSession(body);
      nav(`/live/${s.id}`);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const learner = me;
  const liveMic = !form.lecture_id;
  const lectureById = (id: string | null) => lectures.find((l) => l.id === id);
  const openaiOk = !!doctor && doctor.keys.openai && doctor.openai.ok;
  const deepgramOk = !!doctor && doctor.keys.deepgram && doctor.deepgram.ok;

  return (
    <div className="page">
      <header className="hero">
        <h1 className="t-large">Ready when you are.</h1>
        <p className="sub">Put the headset on and start the lecture. If you drift, Reflow notices, catches you up in one line, and afterwards teaches you only what you missed.</p>
      </header>

      {err ? (
        <div className="callout danger">
          <b>Could not start.</b> {err}
        </div>
      ) : null}

      <div className="home-grid">
        <div className="stack-lg">
          <section className="sheet setup">
            <div className="setup-sec">
              <div className="setup-head">
                <h2 className="t-title3">What are you listening to?</h2>
              </div>
              <div className="lecture-cards">
                {lectures.map((l) => {
                  const selected = form.lecture_id === l.id;
                  return (
                    <button key={l.id} className={"lecture-card" + (selected ? " selected" : "")} onClick={() => setForm({ ...form, lecture_id: l.id })}>
                      <span className="lc-kind">{l.kind === "media" ? "Recorded lecture" : "Practice lecture"}</span>
                      <span className="lc-title">{l.title}</span>
                      <span className="lc-meta">
                        {mmss(l.duration)} · {l.segments?.length ?? 0} parts
                      </span>
                    </button>
                  );
                })}
                <button className={"lecture-card" + (liveMic ? " selected" : "")} onClick={() => setForm({ ...form, lecture_id: null, mode: "live" })}>
                  <span className="lc-kind">Live</span>
                  <span className="lc-title">A lecture happening now</span>
                  <span className="lc-meta">{deepgramOk ? "Uses your laptop microphone." : "Needs the transcription key first."}</span>
                </button>
              </div>
            </div>

            <footer className="setup-foot">
              <button className="btn btn-primary btn-lg" disabled={busy || (liveMic && !deepgramOk)} onClick={() => void start()}>
                {busy ? "Starting…" : "Start listening"}
              </button>
              <span className="label-2 t-subhead">
                Feel lost? Press <kbd className="kbd">space</kbd> or tap the pad. You get one line, then keep listening.
              </span>
            </footer>
          </section>

          {doctor && !openaiOk ? (
            <div className="callout warning">
              <b>Notes need a key.</b> Catch-ups, notes and review cards are written by OpenAI. Add <code>OPENAI_API_KEY</code> to <code>.env</code> and restart, then start listening.
            </div>
          ) : null}
        </div>

        <aside className="stack-lg">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Your lectures</span>
            </div>
            {sessions.length === 0 ? <div className="label-2 t-subhead">Nothing yet. Your first lecture shows up here.</div> : null}
            <div className="session-list">
              {sessions.map((s) => {
                const st = statusLabel(s);
                const primary = s.status === "running" ? `/live/${s.id}` : s.status === "ended" && s.gaps ? `/notes/${s.id}` : s.status === "reviewed" ? `/review/${s.id}` : `/notes/${s.id}`;
                return (
                  <div key={s.id} className="session-item">
                    <div className="si-main">
                      <div className="si-title">{lectureById(s.lecture_id)?.title ?? (s.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</div>
                      <div className="si-meta">
                        {s.gaps ? `${s.gaps} moment${s.gaps === 1 ? "" : "s"} missed` : `${s.flags.length} flag${s.flags.length === 1 ? "" : "s"}`}{s.learner_id !== "lrn_me" ? " · study participant" : ""}
                      </div>
                    </div>
                    <Badge tone={st.tone}>{st.text}</Badge>
                    <Link className="btn btn-sm" to={primary}>
                      Open
                    </Link>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Setup</span>
              {doctor ? <span className="label-2 t-footnote">{doctor.platform}</span> : null}
            </div>
            {!doctor ? (
              <div className="label-2 t-subhead">Checking…</div>
            ) : (
              <div className="status-list">
                <StatusLine ok={doctor.headset.kind === "real"} tone={doctor.headset.kind === "real" ? "ok" : "warn"} label="Headset" value={doctor.headset.kind === "real" ? "Connected" : "Not connected · simulated for now"} />
                <StatusLine ok={doctor.totem.kind === "real"} tone={doctor.totem.kind === "real" ? "ok" : "accent"} label="Pad" value={doctor.totem.kind === "real" ? "Connected" : "Not connected · press Space instead"} />
                <StatusLine ok={deepgramOk} tone={deepgramOk ? "ok" : "bad"} label="Transcription" value={deepgramOk ? "Ready" : "Needs DEEPGRAM_API_KEY"} />
                <StatusLine ok={openaiOk} tone={openaiOk ? "ok" : "bad"} label="Notes" value={openaiOk ? "Ready" : "Needs OPENAI_API_KEY"} />
              </div>
            )}
            <details className="disclosure" style={{ marginTop: 12 }}>
              <summary>Advanced options</summary>
              <div className="adv">
                <label className="opt">
                  <span className="opt-k">Mode</span>
                  <span className="segmented sm">
                    <button className={form.mode === "live" ? "is-active" : ""} onClick={() => setForm({ ...form, mode: "live" })}>
                      live
                    </button>
                    <button className={form.mode === "recorded" ? "is-active" : ""} disabled={!form.lecture_id} onClick={() => setForm({ ...form, mode: "recorded" })}>
                      recorded
                    </button>
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Baseline</span>
                  <span className="row">
                    <span className="segmented sm">
                      <button className={form.baseline_seconds === 30 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 30 })}>
                        30 s
                      </button>
                      <button className={form.baseline_seconds === 180 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 180 })}>
                        3 min
                      </button>
                    </span>
                    <input className="field field-num" type="number" min={5} value={form.baseline_seconds} onChange={(e) => setForm({ ...form, baseline_seconds: Number(e.target.value) })} />
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Catch-ups</span>
                  <span className="segmented sm">
                    <button className={form.catchup_policy === "always" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "always" })}>
                      always
                    </button>
                    <button className={form.catchup_policy === "randomized" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "randomized" })}>
                      randomized (study)
                    </button>
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Study participant</span>
                  <input className="field wide" value={participant} placeholder="optional, e.g. P07 (keeps their tally separate)" onChange={(e) => setParticipant(e.target.value)} />
                </label>
                <label className="opt">
                  <span className="opt-k">Stored baseline</span>
                  <span className="row">
                    <input type="checkbox" className="switch" checked={!!form.use_stored_baseline} disabled={!learner || learner.baseline_mu === null} onChange={(e) => setForm({ ...form, use_stored_baseline: e.target.checked })} />
                    <span className="label-2 t-footnote">{learner && learner.baseline_mu !== null ? "skip the first minutes" : "none stored yet"}</span>
                  </span>
                </label>
                <label className="opt">
                  <span className="opt-k">Headset</span>
                  <select className="select popup" value={headsetChoice} onChange={(e) => onHeadsetChoice(e.target.value)}>
                    <option value="auto">auto</option>
                    <option value="sim">simulated EEG</option>
                    <option value="fake">pipeline synthetic EEG</option>
                    <option value="custom">custom port or replay</option>
                  </select>
                </label>
                {headsetChoice === "custom" ? (
                  <label className="opt">
                    <span className="opt-k">Headset port</span>
                    <input
                      className="field wide"
                      value={customHeadset}
                      placeholder="COM3, /dev/cu.MindWave…, replay:sessions/…"
                      onChange={(e) => {
                        setCustomHeadset(e.target.value);
                        setForm({ ...form, headset: e.target.value || "auto" });
                      }}
                    />
                  </label>
                ) : null}
                <label className="opt">
                  <span className="opt-k">Pad</span>
                  <select className="select popup" value={totemChoice} onChange={(e) => onTotemChoice(e.target.value)}>
                    <option value="auto">auto</option>
                    <option value="keyboard">keyboard</option>
                    <option value="custom">custom port</option>
                  </select>
                </label>
                {totemChoice === "custom" ? (
                  <label className="opt">
                    <span className="opt-k">Pad port</span>
                    <input
                      className="field wide"
                      value={customTotem}
                      placeholder="COM5 or /dev/cu.usbmodem…"
                      onChange={(e) => {
                        setCustomTotem(e.target.value);
                        setForm({ ...form, totem: e.target.value || "auto" });
                      }}
                    />
                  </label>
                ) : null}
                {form.mode === "recorded" ? (
                  <label className="opt">
                    <span className="opt-k">Auto-pause</span>
                    <span className="row">
                      <input type="checkbox" className="switch" checked={!!form.auto_pause} onChange={(e) => setForm({ ...form, auto_pause: e.target.checked })} />
                      <span className="label-2 t-footnote">pause the video on a flag</span>
                    </span>
                  </label>
                ) : null}
                <Link className="t-footnote" to="/tally/me">
                  What works for you
                </Link>
                {form.lecture_id ? (
                  <Link className="t-footnote" to={`/lossmap/${form.lecture_id}`}>
                    Where the room drifted
                  </Link>
                ) : null}
              </div>
            </details>
          </div>
        </aside>
      </div>
    </div>
  );
}

function StatusLine({ ok, tone, label, value }: { ok: boolean; tone: "ok" | "warn" | "bad" | "accent"; label: string; value: string }) {
  return (
    <div className="status-line">
      <StatusDot state={tone} />
      <span className="sl-label">{label}</span>
      <span className={"sl-value" + (!ok && tone === "bad" ? " error-text" : "")}>{value}</span>
    </div>
  );
}
