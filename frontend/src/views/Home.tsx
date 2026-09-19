import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, Learner, SessionPublic } from "../lib/types";
import { mmss } from "../lib/format";
import { Badge, StatusDot } from "../components/Badges";
import { Group, Row } from "../components/Inspector";

const LS_KEY = "reflow.learner";
type HeadsetChoice = "auto" | "sim" | "fake" | "custom";
type TotemChoice = "auto" | "keyboard" | "custom";

export default function Home() {
  const nav = useNavigate();
  const [learners, setLearners] = useState<Learner[]>([]);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [sessions, setSessions] = useState<SessionPublic[]>([]);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [newName, setNewName] = useState("");
  const [headsetChoice, setHeadsetChoice] = useState<HeadsetChoice>("auto");
  const [customHeadset, setCustomHeadset] = useState("");
  const [totemChoice, setTotemChoice] = useState<TotemChoice>("auto");
  const [customTotem, setCustomTotem] = useState("");
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
    try {
      const [l, lec, s] = await Promise.all([api.learners(), api.lectures(), api.sessions()]);
      setLearners(l.learners);
      setLectures(lec.lectures);
      setSessions(s.sessions.slice(0, 10));
      setForm((f) => ({
        ...f,
        learner_id: f.learner_id && l.learners.some((x) => x.id === f.learner_id) ? f.learner_id : (l.learners[0]?.id ?? ""),
        lecture_id: f.lecture_id ?? lec.lectures[0]?.id ?? null,
      }));
    } catch (e) {
      setErr(errorText(e));
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
      setErr(errorText(e));
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
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const learner = learners.find((l) => l.id === form.learner_id);
  const liveMic = form.mode === "live" && !form.lecture_id;
  const lectureById = (id: string | null) => lectures.find((l) => l.id === id);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="t-large">Reflow</h1>
          <div className="sub">It notices the moment a lecture loses you, catches you up in one glance, and re-teaches what you missed until it lands.</div>
        </div>
      </div>
      {err ? <div className="card error-text" style={{ marginBottom: 16 }}>{err}</div> : null}
      <div className="home-grid">
        <div className="stack-lg">
          <Group title="Learner">
            <Row label="learner">
              <select className="select" value={form.learner_id} onChange={(e) => setForm({ ...form, learner_id: e.target.value })}>
                {learners.length === 0 ? <option value="">create one first</option> : null}
                {learners.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                    {l.baseline_mu !== null ? " (stored baseline)" : ""}
                  </option>
                ))}
              </select>
            </Row>
            <Row label="new learner">
              <input className="field" value={newName} placeholder="name" onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void addLearner()} />
              <button className="btn" onClick={() => void addLearner()}>
                Add
              </button>
            </Row>
          </Group>
          <Group
            title="Lecture"
            note={
              liveMic && doctor && !doctor.keys.deepgram
                ? "Live microphone needs DEEPGRAM_API_KEY. Pick a scripted lecture to rehearse without it."
                : form.lecture_id && form.mode === "live"
                  ? "Scripted lecture: the transcript is replayed in real time and labelled as such. Space taps, L forces a flag, 1/2/3 drive a simulated headset, E ends."
                  : undefined
            }
          >
            <Row label="lecture">
              <select className="select" style={{ maxWidth: 360 }} value={form.lecture_id ?? ""} onChange={(e) => setForm({ ...form, lecture_id: e.target.value || null })}>
                <option value="">Live microphone (Deepgram)</option>
                {lectures.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.title} · {mmss(l.duration)} · {l.segments?.length ?? 0} segments
                  </option>
                ))}
              </select>
            </Row>
          </Group>
          <Group title="Session">
            <Row label="mode">
              <div className="segmented sm">
                <button className={form.mode === "live" ? "is-active" : ""} onClick={() => setForm({ ...form, mode: "live" })}>
                  live
                </button>
                <button className={form.mode === "recorded" ? "is-active" : ""} onClick={() => setForm({ ...form, mode: "recorded" })}>
                  recorded
                </button>
              </div>
            </Row>
            <Row label="catch-ups">
              <div className="segmented sm">
                <button className={form.catchup_policy === "always" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "always" })}>
                  always show
                </button>
                <button className={form.catchup_policy === "randomized" ? "is-active" : ""} onClick={() => setForm({ ...form, catchup_policy: "randomized" })}>
                  randomized (study)
                </button>
              </div>
            </Row>
            <Row label="baseline">
              <input className="field field-num" type="number" min={5} value={form.baseline_seconds} onChange={(e) => setForm({ ...form, baseline_seconds: Number(e.target.value) })} />
              <span className="t-footnote label-2">s</span>
              <div className="segmented sm">
                <button className={form.baseline_seconds === 30 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 30 })}>
                  30 rehearsal
                </button>
                <button className={form.baseline_seconds === 180 ? "is-active" : ""} onClick={() => setForm({ ...form, baseline_seconds: 180 })}>
                  180 spec
                </button>
              </div>
            </Row>
            <Row label={<span>stored baseline<div className="t-footnote label-2">{learner && learner.baseline_mu !== null ? "use this learner's calibrated baseline" : "none stored for this learner yet"}</div></span>}>
              <input type="checkbox" className="switch" checked={!!form.use_stored_baseline} disabled={!learner || learner.baseline_mu === null} onChange={(e) => setForm({ ...form, use_stored_baseline: e.target.checked })} />
            </Row>
            <Row label="headset">
              <select className="select" value={headsetChoice} onChange={(e) => onHeadsetChoice(e.target.value)}>
                <option value="auto">auto (MindWave if paired, else simulated)</option>
                <option value="sim">simulated EEG</option>
                <option value="fake">pipeline synthetic EEG</option>
                <option value="custom">custom port or replay</option>
              </select>
            </Row>
            {headsetChoice === "custom" ? (
              <Row label="headset port">
                <input
                  className="field"
                  style={{ width: 300 }}
                  value={customHeadset}
                  placeholder="COM3, /dev/cu.MindWave…, replay:sessions/…"
                  onChange={(e) => {
                    setCustomHeadset(e.target.value);
                    setForm({ ...form, headset: e.target.value || "auto" });
                  }}
                />
              </Row>
            ) : null}
            <Row label="totem">
              <select className="select" value={totemChoice} onChange={(e) => onTotemChoice(e.target.value)}>
                <option value="auto">auto (Arduino if plugged in, else keyboard)</option>
                <option value="keyboard">keyboard</option>
                <option value="custom">custom port</option>
              </select>
            </Row>
            {totemChoice === "custom" ? (
              <Row label="totem port">
                <input
                  className="field"
                  style={{ width: 300 }}
                  value={customTotem}
                  placeholder="COM5 or /dev/cu.usbmodem…"
                  onChange={(e) => {
                    setCustomTotem(e.target.value);
                    setForm({ ...form, totem: e.target.value || "auto" });
                  }}
                />
              </Row>
            ) : null}
            {form.mode === "recorded" ? (
              <Row label={<span>auto-pause<div className="t-footnote label-2">pause the video and show the card on an EEG flag</div></span>}>
                <input type="checkbox" className="switch" checked={!!form.auto_pause} onChange={(e) => setForm({ ...form, auto_pause: e.target.checked })} />
              </Row>
            ) : null}
          </Group>
          <div className="row">
            <button className="btn btn-primary btn-lg" disabled={!form.learner_id || busy} onClick={() => void start()}>
              {busy ? "Starting…" : "Start session"}
            </button>
            {learner ? <Link className="t-subhead" to={`/tally/${learner.id}`}>Tally for {learner.name}</Link> : null}
            {form.lecture_id ? <Link className="t-subhead" to={`/lossmap/${form.lecture_id}`}>Loss map</Link> : null}
          </div>
        </div>
        <div className="stack-lg">
          <SystemGroup d={doctor} />
          <Group title="Recent sessions">
            {sessions.length === 0 ? <div className="group-row label-2">none yet</div> : null}
            {sessions.map((s) => (
              <div key={s.id} className="session-row">
                <div>
                  <div className="t-subhead">
                    {lectureById(s.lecture_id)?.title ?? (s.transcript_kind === "deepgram" ? "Live microphone" : "Session")}
                    <span className="label-2"> · {learners.find((l) => l.id === s.learner_id)?.name ?? s.learner_id}</span>
                  </div>
                  <div className="meta">
                    <span className="mono">{s.id}</span>
                    <span>{s.flags.length} flags · {s.gaps} gaps</span>
                  </div>
                </div>
                <Badge tone={s.status === "running" ? "success" : s.status === "reviewed" ? "accent" : "neutral"}>{s.status}</Badge>
                <div className="links">
                  {s.status === "running" ? <Link to={`/live/${s.id}`}>live</Link> : null}
                  <Link to={`/notes/${s.id}`}>notes</Link>
                  <Link to={`/review/${s.id}`}>review</Link>
                  <Link to={`/replay/${s.id}`}>replay</Link>
                  {s.lecture_id ? <Link to={`/quiz/${s.id}`}>quiz</Link> : null}
                </div>
              </div>
            ))}
          </Group>
        </div>
      </div>
    </div>
  );
}

function SystemGroup({ d }: { d: Doctor | null }) {
  if (!d) {
    return (
      <Group title="System">
        <Row label="checking…" />
      </Group>
    );
  }
  const totemKeyboard = d.totem.kind !== "real";
  return (
    <Group title="System" note={d.platform ? `platform ${d.platform} · data ${d.data_dir}` : undefined}>
      <Row label={<span className="row"><StatusDot state={d.keys.deepgram ? (d.deepgram.ok ? "ok" : "warn") : "off"} />Deepgram</span>}>
        {d.keys.deepgram ? <Badge tone={d.deepgram.ok ? "success" : "warning"}>{d.deepgram.ok ? "reachable" : d.deepgram.reason ?? "not reachable"}</Badge> : <Badge>no key</Badge>}
      </Row>
      <Row
        label={
          <span>
            <span className="row"><StatusDot state={d.keys.openai && d.openai.ok ? "ok" : "bad"} />OpenAI</span>
            {!(d.keys.openai && d.openai.ok) && d.openai.required !== false ? (
              <div className="t-footnote error-text">required: recaps, notes and review cards need OPENAI_API_KEY</div>
            ) : null}
          </span>
        }
      >
        {d.keys.openai && d.openai.ok ? (
          <Badge tone="success">{d.openai.model}</Badge>
        ) : (
          <Badge tone="danger">{d.keys.openai ? `${d.openai.model} unavailable` : "no key"}</Badge>
        )}
      </Row>
      <Row label={<span className="row"><StatusDot state={d.headset.kind === "real" ? "ok" : "warn"} />headset</span>}>
        <span className="mono t-footnote">{d.headset.port ?? ""}</span>
        <Badge tone={d.headset.kind === "real" ? "success" : "warning"}>{d.headset.kind === "real" ? "MindWave" : "simulated"}</Badge>
      </Row>
      <Row label={<span className="row"><StatusDot state={totemKeyboard ? "accent" : "ok"} />totem</span>}>
        <span className="mono t-footnote">{d.totem.port ?? ""}</span>
        <Badge tone={totemKeyboard ? "neutral" : "success"}>{totemKeyboard ? "keyboard fallback" : "Arduino"}</Badge>
      </Row>
      <Row label={<span className="row"><StatusDot state={d.frontend_built ? "ok" : "bad"} />frontend</span>}>
        <Badge tone={d.frontend_built ? "success" : "danger"}>{d.frontend_built ? "built" : "not built"}</Badge>
      </Row>
      <Row label="baseline">
        <span className="mono">{d.baseline_seconds}s</span>
      </Row>
    </Group>
  );
}
