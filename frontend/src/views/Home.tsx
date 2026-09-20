import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../lib/api";
import type { Devices, Doctor, LectureFull, SessionPublic } from "../lib/types";

/** Listen (docs/PRODUCT.md §6): one button. A practice lecture is a fallback, not a peer choice.
 * "Next up" shows at most one lecture with moments left to restudy; the history lives on Lectures. */
export default function Home() {
  const nav = useNavigate();
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [practice, setPractice] = useState<LectureFull | null>(null);
  const [lectures, setLectures] = useState<LectureFull[]>([]);
  const [nextUp, setNextUp] = useState<SessionPublic | null>(null);
  const [running, setRunning] = useState<SessionPublic | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [devices, setDevices] = useState<Devices | null>(null);

  // the headset is often switched on after this screen opens: ask every few seconds, cheaply
  useEffect(() => {
    let alive = true;
    const load = () => api.devices().then((d) => alive && setDevices(d)).catch(() => undefined);
    void load();
    const id = window.setInterval(load, 4000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    (async () => {
      const [lec, s, d] = await Promise.allSettled([api.lectures(), api.sessions(), api.doctor()]);
      if (lec.status === "fulfilled") {
        setLectures(lec.value.lectures);
        setPractice(lec.value.lectures.find((l) => l.kind === "scripted") ?? lec.value.lectures[0] ?? null);
      }
      if (s.status === "fulfilled") {
        const all = s.value.sessions.filter((x) => x.mode !== "review");
        setRunning(all.find((x) => x.status === "running") ?? null);
        setNextUp(all.find((x) => x.status === "ended" && x.gaps > 0) ?? null);
      }
      if (d.status === "fulfilled") setDoctor(d.value);
    })();
  }, []);

  const liveOk = !!doctor && doctor.keys.deepgram && doctor.deepgram.ok;
  const notesOk = !!doctor && doctor.keys.openai && doctor.openai.ok;

  const start = async (lectureId: string | null) => {
    setErr(null);
    setBusy(true);
    try {
      const s = await api.createSession({ lecture_id: lectureId, mode: "live", headset: "auto", totem: "auto" });
      nav(`/live/${s.id}`);
    } catch (e) {
      setErr(friendly(errorText(e)));
    } finally {
      setBusy(false);
    }
  };

  const dev = devices ?? doctor;
  const statusLine = !dev
    ? ""
    : [
        dev.headset.kind === "real" ? "Headset connected." : "Turn your headset on before you start; without one, focus is simulated for practice.",
        dev.totem.kind === "real" ? "Pad connected." : "Press Space whenever you want a catch-up.",
      ].join(" ");

  return (
    <div className="page narrow">
      <header className="hero center-hero">
        <h1 className="t-large">Ready when you are.</h1>
        <p className="sub">Put the headset on and start the lecture. If you drift, Reflow catches you up in one line and, afterwards, teaches you only what you missed.</p>
      </header>

      {err ? <div className="callout danger">{err}</div> : null}
      {doctor && !notesOk ? <div className="callout warning">Reflow can't write notes right now. Ask the team to check the setup before you start.</div> : null}

      <div className="start">
        {running ? (
          <Link className="btn btn-primary btn-lg btn-block" to={`/live/${running.id}`}>
            Back to the lecture
          </Link>
        ) : liveOk ? (
          <button className="btn btn-primary btn-lg btn-block" disabled={busy} onClick={() => void start(null)}>
            {busy ? "Starting…" : "Start listening"}
          </button>
        ) : practice ? (
          <button className="btn btn-primary btn-lg btn-block" disabled={busy} onClick={() => void start(practice.id)}>
            {busy ? "Starting…" : "Try a practice lecture"}
          </button>
        ) : (
          <button className="btn btn-primary btn-lg btn-block" disabled>
            Nothing to listen to yet
          </button>
        )}
        <div className={"start-note" + (dev && dev.headset.kind === "real" ? " ok" : "")}>{statusLine}</div>
        {liveOk && practice && !running ? (
          <div className="start-alt">
            No lecture right now?{" "}
            <button className="linklike" disabled={busy} onClick={() => void start(practice.id)}>
              Try a practice lecture
            </button>
          </div>
        ) : null}
        {!liveOk && doctor ? <div className="start-alt">Live lectures aren't available on this laptop right now.</div> : null}
      </div>

      {nextUp ? (
        <section className="next-up">
          <div className="eyebrow">Next up</div>
          <Link className="list-row" to={`/lecture/${nextUp.id}`}>
            <span className="lr-main">
              <span className="lr-title">{lectures.find((l) => l.id === nextUp.lecture_id)?.title ?? "Live lecture"}</span>
              <span className="lr-meta">
                {nextUp.gaps} moment{nextUp.gaps === 1 ? "" : "s"} to restudy · {new Date(nextUp.started_at * 1000).toLocaleDateString(undefined, { weekday: "long" })}
              </span>
            </span>
            <span className="btn btn-blue btn-sm">Restudy</span>
          </Link>
        </section>
      ) : null}
    </div>
  );
}

function friendly(detail: string): string {
  if (/OPENAI_API_KEY/i.test(detail)) return "Reflow can't write notes right now. Ask the team to check the setup.";
  if (/DEEPGRAM/i.test(detail)) return "Live lectures aren't available right now. Try a practice lecture, or ask the team.";
  return detail;
}
