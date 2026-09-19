import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, Learner, SessionPublic } from "../lib/types";
import { mmss } from "../lib/format";

const LS_KEY = "reflow.learner";

export default function Home() {
  const nav = useNavigate();
  const [learners, setLearners] = useState<Learner[]>([]);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [newName, setNewName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<SessionCreate>(() => ({
    learner_id: localStorage.getItem(LS_KEY) ?? "",
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

  const load = async () => {
    try {
      const [l, lec, s] = await Promise.all([api.learners(), api.lectures(), api.sessions()]);
      setLearners(l.learners);
      setLectures(lec.lectures);
      setSessions(s.sessions.slice(0, 12));
      setForm((f) => ({
        ...f,
        learner_id: f.learner_id && l.learners.some((x) => x.id === f.learner_id) ? f.learner_id : (l.learners[0]?.id ?? ""),
        lecture_id: f.lecture_id ?? lec.lectures[0]?.id ?? null,
      }));
    } catch (e) {
      setErr(String(e));
    }
  };
  useEffect(() => {
    void load();
    api.doctor().then(setDoctor).catch(() => setDoctor(null));
  }, []);

  const addLearner = async () => {
    if (!newName.trim()) return;
    try {
      const l = await api.createLearner(newName.trim());
      setNewName("");
      setLearners((xs) => xs.concat(l));
      setForm((f) => ({ ...f, learner_id: l.id }));
    } catch (e) {
      setErr(String(e));
    }
  };

  const start = async () => {
    setErr(null);
    setBusy(true);
    try {
      localStorage.setItem(LS_KEY, form.learner_id);
      const body: SessionCreate = { ...form, lecture_id: form.lecture_id || null };
      const s = await api.createSession(body);
      nav(`/live/${s.id}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const learner = learners.find((l) => l.id === form.learner_id);
  const liveMic = form.mode === "live" && !form.lecture_id;
  const lectureById = (id: string | null) => lectures.find((l) => l.id === id);

  return (
    <div className="col">
      <h1>Reflow</h1>
      <div className="muted" style={{ marginTop: "-0.5rem" }}>
        It notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.
      </div>
      <DoctorStrip d={doctor} />
      {err ? <div className="panel error">{err}</div> : null}
      <div className="home">
        <div className="panel col">
          <h2>Start a session</h2>
          <div className="form-grid">
            <label>
              learner
              <select value={form.learner_id} onChange={(e) => setForm({ ...form, learner_id: e.target.value })}>
                {learners.length === 0 ? <option value="">create one first</option> : null}
                {learners.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                    {l.baseline_mu !== null ? " (has stored baseline)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              new learner
              <div className="row" style={{ gap: "0.4rem" }}>
                <input value={newName} placeholder="name" onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void addLearner()} style={{ flex: 1 }} />
                <button onClick={() => void addLearner()}>add</button>
              </div>
            </label>
            <label className="full">
              lecture
              <select value={form.lecture_id ?? ""} onChange={(e) => setForm({ ...form, lecture_id: e.target.value || null })}>
                <option value="">Live microphone (Deepgram, needs a key)</option>
                {lectures.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.title} · {l.kind} · {mmss(l.duration)} · {l.segments?.length ?? 0} segments · {(l.quiz ?? []).length} quiz items
                  </option>
                ))}
              </select>
            </label>
            <label>
              mode
              <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value as "live" | "recorded" })}>
                <option value="live">live (transcript streams in real time)</option>
                <option value="recorded">recorded (player drives the clock, auto-pause on a flag)</option>
              </select>
            </label>
            <label>
              catch-up policy
              <select value={form.catchup_policy} onChange={(e) => setForm({ ...form, catchup_policy: e.target.value as "always" | "randomized" })}>
                <option value="always">always show</option>
                <option value="randomized">randomized per lapse (study)</option>
              </select>
            </label>
            <label>
              baseline seconds
              <div className="row" style={{ gap: "0.4rem" }}>
                <input type="number" min={5} value={form.baseline_seconds} onChange={(e) => setForm({ ...form, baseline_seconds: Number(e.target.value) })} style={{ width: 110 }} />
                <button className="ghost" onClick={() => setForm({ ...form, baseline_seconds: 30 })}>30 (rehearsal)</button>
                <button className="ghost" onClick={() => setForm({ ...form, baseline_seconds: 180 })}>180 (spec)</button>
              </div>
            </label>
            <label>
              stored baseline
              <div className="row">
                <input type="checkbox" checked={!!form.use_stored_baseline} disabled={!learner || learner.baseline_mu === null} onChange={(e) => setForm({ ...form, use_stored_baseline: e.target.checked })} style={{ minHeight: 0, width: 22, height: 22 }} />
                <span className="small muted">{learner?.baseline_mu !== null && learner ? "use this learner's calibrated baseline (labelled)" : "none stored yet for this learner"}</span>
              </div>
            </label>
            <label>
              headset
              <select value={form.headset} onChange={(e) => setForm({ ...form, headset: e.target.value as "auto" | "sim" })}>
                <option value="auto">auto-detect (simulate if none)</option>
                <option value="sim">simulated</option>
              </select>
            </label>
            <label>
              totem
              <select value={form.totem} onChange={(e) => setForm({ ...form, totem: e.target.value as "auto" | "sim" })}>
                <option value="auto">auto-detect (simulate if none)</option>
                <option value="sim">simulated</option>
              </select>
            </label>
            {form.mode === "recorded" ? (
              <label className="full">
                <div className="row">
                  <input type="checkbox" checked={!!form.auto_pause} onChange={(e) => setForm({ ...form, auto_pause: e.target.checked })} style={{ minHeight: 0, width: 22, height: 22 }} />
                  <span className="small muted">auto-pause the video and show the card on an EEG flag</span>
                </div>
              </label>
            ) : null}
          </div>
          {liveMic && doctor && !doctor.keys.deepgram ? <div className="small error">Live microphone needs DEEPGRAM_API_KEY. Pick a scripted lecture to rehearse without it.</div> : null}
          {form.lecture_id && form.mode === "live" ? <div className="small muted">Scripted lecture: the transcript is replayed in real time (labelled SCRIPTED TRANSCRIPT). Keys T / L / 1 / 2 / 3 / E drive the demo.</div> : null}
          <div className="row">
            <button className="primary" disabled={!form.learner_id || busy} onClick={() => void start()}>
              {busy ? "starting…" : "Start session"}
            </button>
            {learner ? <Link to={`/tally/${learner.id}`}>tally for {learner.name}</Link> : null}
            {form.lecture_id ? <Link to={`/lossmap/${form.lecture_id}`}>loss map: {lectureById(form.lecture_id)?.title}</Link> : null}
          </div>
        </div>
        <div className="panel">
          <h2>Recent sessions</h2>
          {sessions.length === 0 ? <div className="dim">none yet</div> : null}
          <div className="sessions-list">
            {sessions.map((s) => (
              <div key={s.id} className="s">
                <span className="mono">{s.id}</span>
                <span className="muted">{learners.find((l) => l.id === s.learner_id)?.name ?? s.learner_id}</span>
                <span className="muted">{lectureById(s.lecture_id)?.title ?? (s.transcript_kind === "deepgram" ? "microphone" : "")}</span>
                <span className={"badge " + (s.status === "running" ? "good" : "")}>{s.status}</span>
                <span className="muted">{s.flags.length} flags · {s.gaps} gaps</span>
                <span className="links">
                  {s.status === "running" ? <Link to={`/live/${s.id}`}>live</Link> : null}
                  <Link to={`/notes/${s.id}`}>notes</Link>
                  <Link to={`/review/${s.id}`}>review</Link>
                  <Link to={`/replay/${s.id}`}>replay</Link>
                  {s.lecture_id ? <Link to={`/quiz/${s.id}`}>quiz</Link> : null}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function DoctorStrip({ d }: { d: Doctor | null }) {
  if (!d) return <div className="strip"><span className="item muted">doctor: checking…</span></div>;
  return (
    <div className="strip">
      <span className="item">
        <span className={"dotled " + (d.keys.deepgram ? (d.deepgram.ok ? "on" : "warn") : "off")} />
        Deepgram <b>{d.keys.deepgram ? (d.deepgram.ok ? "ok" : d.deepgram.reason ?? "key set, not reachable") : "no key"}</b>
      </span>
      <span className="item">
        <span className={"dotled " + (d.keys.openai ? (d.openai.ok ? "on" : "warn") : "off")} />
        OpenAI <b>{d.keys.openai ? `${d.openai.model} ${d.openai.ok ? "ok" : "unavailable"}` : "no key (offline recaps)"}</b>
      </span>
      <span className="item">
        <span className={"dotled " + (d.headset.kind === "real" ? "on" : "warn")} />
        headset <b>{d.headset.kind}</b> <span className="muted mono small">{d.headset.port ?? ""}</span>
      </span>
      <span className="item">
        <span className={"dotled " + (d.totem.kind === "real" ? "on" : "warn")} />
        totem <b>{d.totem.kind}</b> <span className="muted mono small">{d.totem.port ?? ""}</span>
      </span>
      <span className="item">
        baseline <b>{d.baseline_seconds}s</b>
      </span>
    </div>
  );
}
