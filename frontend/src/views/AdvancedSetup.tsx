import { backendFetch } from "../lib/backend";
import DeskObject from "../components/DeskObject";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type SessionCreate } from "../lib/api";
import type { Doctor, LectureFull, Learner } from "../lib/types";
import { mmss } from "../lib/format";
import { readLocalSetting, writeLocalSetting } from "../lib/storage";
import { ConnectionPills, StudioBackLink, StudioSteps, type ConnectionPill } from "../components/StudioChrome";

/** Studio setup: the only session-setup surface. Two steps — devices, then lecture.
 *  Profile is read-only here (dashboard owns creation); "Start session" is the only
 *  start-language submit. No connection pill is green unless the state is verified. */
export default function Setup() {
  const nav = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [learners, setLearners] = useState<Learner[]>([]);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [headsetChoice, setHeadsetChoice] = useState<"auto" | "sim" | "fake" | "custom">("auto");
  const [relayDevices, setRelayDevices] = useState<{ name: string; address: string }[]>([]);
  const [relayAddress, setRelayAddress] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState("");
  const scanRelay = async () => {
    setScanning(true); setScanMessage("");
    try {
      const response = await backendFetch("/api/devices/uno-q");
      if (!response.ok) throw new Error("Bluetooth scan failed");
      const result = await response.json();
      setRelayDevices(result.devices);
      setScanMessage(result.error || (!result.devices.length ? "No NeuroPace UNO Q relay found. Start the relay service on your board, then scan again." : "Select your board. Connection is verified in the live session."));
    } catch (e) { setScanMessage(String(e)); }
    finally { setScanning(false); }
  };
  const [customHeadset, setCustomHeadset] = useState("");
  const onHeadsetChoice = (v: string) => {
    const choice = (["auto", "sim", "fake", "custom"].includes(v) ? v : "auto") as "auto" | "sim" | "fake" | "custom";
    setHeadsetChoice(choice);
    setForm((f) => ({ ...f, headset: choice === "custom" ? customHeadset || "auto" : choice }));
  };
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState<SessionCreate>(() => ({
    learner_id: readLocalSetting("learner") ?? "",
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
      const [l, lec] = await Promise.all([api.learners(), api.lectures()]);
      setLearners(l.learners);
      setLectures(lec.lectures);
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
    const refresh = window.setInterval(() => { void backendFetch("/api/devices/status").then(r => {if (!r.ok) throw new Error("Device refresh failed"); return r.json();}).then(devices => setDoctor(d => d ? {...d, ...devices} : d)).catch(() => {}); }, 15000);
    return () => window.clearInterval(refresh);
  }, []);

  const start = async () => {
    setErr(null);
    setBusy(true);
    try {
      if (form.learner_id) writeLocalSetting("learner", form.learner_id);
      const body: SessionCreate = { ...form, lecture_id: form.lecture_id || null, ...(relayAddress ? {headset: `uno-q:${relayAddress}`, totem: "sim" as const} : {}) };
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

  const pills: ConnectionPill[] = [
    relayAddress
      ? { key: "eeg", label: "EEG", state: "pending", detail: "UNO Q relay: connection pending, verified in live session" }
      : headsetChoice === "sim" || headsetChoice === "fake"
        ? { key: "eeg", label: "EEG", state: "simulated", detail: headsetChoice === "fake" ? "fake: mindwave pipeline synthetic EEG (labelled)" : "simulated: NeuroPace synthetic EEG (labelled)" }
        : headsetChoice === "custom"
          ? { key: "eeg", label: "EEG", state: "pending", detail: `custom source: ${customHeadset || "not set"}, connection pending and verified in live session` }
          : !doctor
            ? { key: "eeg", label: "EEG", state: "pending", detail: "checking connection…" }
            : doctor.headset.kind === "real"
              ? { key: "eeg", label: "EEG", state: "connected", detail: `real headset${doctor.headset.port ? ` · ${doctor.headset.port}` : ""}` }
              : { key: "eeg", label: "EEG", state: "simulated", detail: "no paired headset, simulation runs labelled" },
    relayAddress
      ? { key: "button", label: "Button", state: "pending", detail: "UNO Q relay: connection pending, verified in live session" }
      : form.totem === "sim"
        ? { key: "button", label: "Button", state: "simulated", detail: "simulated button (labelled in session)" }
        : !doctor
          ? { key: "button", label: "Button", state: "pending", detail: "checking connection…" }
          : doctor.totem.kind === "real"
            ? { key: "button", label: "Button", state: "connected", detail: `button device${doctor.totem.port ? ` · ${doctor.totem.port}` : ""}` }
            : { key: "button", label: "Button", state: "simulated", detail: "no button detected, simulated and labelled in session" },
    form.lecture_id
      ? { key: "transcription", label: "Transcription", state: "simulated", detail: "scripted lecture transcript (labelled in session)" }
      : !doctor
        ? { key: "transcription", label: "Transcription", state: "pending", detail: "checking transcription setup…" }
        : doctor.keys.deepgram
          ? { key: "transcription", label: "Transcription", state: "pending", detail: "microphone starts in the live session" }
          : { key: "transcription", label: "Transcription", state: "off", detail: "live microphone needs DEEPGRAM_API_KEY" },
    { key: "board", label: "Board camera", state: "off", detail: "camera is enabled inside the live session, never before" },
  ];

  return (
    <div className="col home-page">
      <section className="welcome">
        <div className="welcome-copy"><span className="workspace-label"><span aria-hidden="true">✳</span> Session studio</span>
          <h1>Ready when<br />you are.</h1>
          <p className="muted">Connect your devices and choose your lecture. This window is your live workspace.</p>
          <a className="setup-link" href="#session-setup">Let’s set up a session <span aria-hidden="true">↘</span></a>
        </div>
        <DeskObject />
      </section>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <StudioSteps current="setup" />
        <StudioBackLink />
      </div>
      <ConnectionPills pills={pills} />
      {err ? <div className="panel error">{err}</div> : null}
      <div className="home">
        <div className="panel col session-setup" id="session-setup">
          <div className="section-heading">
            <span className="section-icon" aria-hidden="true">{step}</span>
            <div>
              <h2>{step === 1 ? "Devices" : "Lecture"}</h2>
              <p className="muted small">{step === 1 ? "Connect what you have. Nothing is verified until the live session, and simulation is always labelled." : "Choose what you’re tuning into."}</p>
            </div>
          </div>

          {step === 1 ? (
            <>
              <section className="device-setup">
                <div className="row"><h3>Connect your UNO Q</h3><span className="badge">Experimental relay</span></div>
                <p className="small muted">The MindWave headset pairs to the UNO Q; the physical button connects to the board. The scan finds only the custom NeuroPace relay service. Selecting a board routes the headset and the physical button through its Bluetooth relay; the connection is verified in the live session, not here.</p>
                <div className="row"><button disabled={scanning} onClick={() => void scanRelay()}>{scanning ? "Scanning…" : "Find UNO Q over Bluetooth"}</button></div>
                <label>Connection route<select value={relayAddress} onChange={e => setRelayAddress(e.target.value)}><option value="">Direct computer connections / simulation</option>{relayDevices.map(d => <option key={d.address} value={d.address}>{d.name} · {d.address}</option>)}</select></label>
                {scanMessage && <p className="small muted" role="status">{scanMessage}</p>}
                <p className="small muted">Direct computer connections and simulated devices remain clearly labelled fallbacks.</p>
              </section>
              <DoctorStrip d={doctor} />
              <p className="small muted">Device discovery refreshes every 15 seconds. A detected port is verified when the session connects. Direct mode uses computer-paired EEG and a USB button. Selecting a UNO Q above routes both inputs through its Bluetooth relay.</p>
              <div className="form-grid">
                <label>
                  EEG connection
                  <select value={headsetChoice} onChange={(e) => onHeadsetChoice(e.target.value)}>
                    <option value="auto">auto-detect (real MindWave if paired, else simulated)</option>
                    <option value="sim">simulated (NeuroPace synthetic EEG)</option>
                    <option value="fake">fake (mindwave pipeline synthetic EEG)</option>
                    <option value="custom">custom: port, replay:&lt;dir&gt; or serial:&lt;port&gt;</option>
                  </select>
                  {headsetChoice === "custom" ? (
                    <input
                      value={customHeadset}
                      placeholder="COM3, /dev/cu.MindWaveMobile-SerialPo, replay:sessions/20260919-120000"
                      onChange={(e) => {
                        setCustomHeadset(e.target.value);
                        setForm({ ...form, headset: e.target.value || "auto" });
                      }}
                    />
                  ) : null}
                </label>
                <label>
                  Button
                  <select value={form.totem} onChange={(e) => setForm({ ...form, totem: e.target.value as "auto" | "sim" })}>
                    <option value="auto">auto-detect (simulate if none)</option>
                    <option value="sim">simulated</option>
                  </select>
                </label>
              </div>
              <p className="small muted">The physical button is still being built. Use the labelled on-screen substitute for now.</p>
              <div className="row" style={{ marginTop: "1rem" }}>
                <button className="primary" onClick={() => setStep(2)}>Continue to lecture</button>
              </div>
            </>
          ) : (
            <>
              <div className="form-grid">
                <label className="full">
                  Lecture
                  <select value={form.lecture_id ?? ""} onChange={(e) => setForm({ ...form, lecture_id: e.target.value || null })}>
                    <option value="">Live microphone (requires transcription setup)</option>
                    {lectures.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.title} · {l.kind} · {mmss(l.duration)} · {l.segments?.length ?? 0} segments · {(l.quiz ?? []).length} quiz items
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Listening mode
                  <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value as "live" | "recorded" })}>
                    <option value="live">Live · follow along</option>
                    <option value="recorded">Recorded · listen at your pace</option>
                  </select>
                </label>
              </div>
              <details className="session-settings">
                <summary>Session settings <span>Calibration & catch-ups</span></summary>
                <div className="form-grid">
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
                {form.mode === "recorded" ? (
                  <label className="full">
                    <div className="row">
                      <input type="checkbox" checked={!!form.auto_pause} onChange={(e) => setForm({ ...form, auto_pause: e.target.checked })} style={{ minHeight: 0, width: 22, height: 22 }} />
                      <span className="small muted">auto-pause the video and show the card on an EEG flag</span>
                    </div>
                  </label>
                ) : null}
                </div>
              </details>
              <div className="small muted device-summary">Headset: {relayAddress ? "UNO Q relay, verified in live session" : headsetChoice === "sim" || headsetChoice === "fake" ? "simulated" : headsetChoice === "custom" ? "custom source" : doctor ? (doctor.headset.kind === "real" ? "connected" : "simulated") : "checking connection"} · Button: {relayAddress ? "UNO Q relay, verified in live session" : form.totem === "sim" ? "simulated" : doctor ? (doctor.totem.kind === "real" ? "connected" : "simulated") : "checking connection"}</div>
              {liveMic && doctor && !doctor.keys.deepgram ? <div className="small error">Live microphone needs DEEPGRAM_API_KEY. Pick a scripted lecture to rehearse without it.</div> : null}
              {form.lecture_id && form.mode === "live" ? <div className="small muted">Scripted lecture: the transcript is replayed in real time (labelled SCRIPTED TRANSCRIPT). Keys T / L / 1 / 2 / 3 / E drive the demo.</div> : null}
              <div className="row">
                <button className="ghost" onClick={() => setStep(1)}>Back to devices</button>
                <button className="primary" disabled={!form.learner_id || busy} onClick={() => void start()}>
                  {busy ? "starting…" : "Start session"}
                </button>
                {learner ? <Link to={`/tally/${learner.id}`}>My review preferences</Link> : null}
                {form.lecture_id ? <Link to={`/lossmap/${form.lecture_id}`}>Lecture overview</Link> : null}
              </div>
            </>
          )}
        </div>
        <aside className="studio-guide">
          <h2>A place to focus.</h2>
          <p className="muted">This window stays with your lecture. Your dashboard keeps your notes and review queue.</p>
          <ol><li><b>Choose your connection.</b><p>Use the UNO Q relay, direct computer connections, or clearly labelled simulated devices.</p></li><li><b>Start listening.</b><p>Live microphone sessions stream the teacher’s voice into a transcript. Scripted lectures are labelled rehearsals.</p></li><li><b>Add the whiteboard.</b><p>Enable camera capture in the live workspace. A button press can use recent board frames and transcript together.</p></li><li><b>Save a tricky moment.</b><p>Press your physical button, or use the labelled on-screen substitute. Review the saved moments after the lecture.</p></li></ol>
        </aside>
      </div>
    </div>
  );
}

function DoctorStrip({ d }: { d: Doctor | null }) {
  if (!d) return <div className="strip"><span className="item muted">Checking connections…</span></div>;
  return (
    <div className="strip">
      <span className="item">
        <span className={"dotled " + (d.keys.deepgram ? (d.deepgram.ok ? "on" : "warn") : "off")} />
        Transcription <b>{d.keys.deepgram ? (d.deepgram.ok ? "ok" : d.deepgram.reason ?? "key set, not reachable") : "no key"}</b>
      </span>
      <span className="item">
        <span className={"dotled " + (d.keys[d.llm_provider] ? (d[d.llm_provider].ok ? "on" : "warn") : "off")} />
        Recaps <b>{d.keys[d.llm_provider] ? (d[d.llm_provider].ok ? "ready" : "unavailable") : "no model key"}</b>
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
