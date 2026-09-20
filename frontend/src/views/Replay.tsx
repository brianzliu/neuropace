import { useGuidedStep } from "../lib/guide";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { HelloMsg, LectureFull, ServerMsg, SessionPublic } from "../lib/types";
import { clearCatchup, dismissChip, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import TranscriptPane from "../components/TranscriptPane";
import CatchupOverlay from "../components/CatchupOverlay";
import Chip from "../components/Chip";
import "../replay.css";
import SessionBack from "../components/BackLink";
import { useLibrary } from "./Library";
import { mmss } from "../lib/format";

const DEFAULT_CONFIG: HelloMsg["config"] = {
  baseline_seconds: 180, lead_in_seconds: 8, recap_period_seconds: 20, recap_window_seconds: 30, catchup_ttl_seconds: 6,
  drop_enter_z: -1.25, drop_exit_z: -0.6, window_seconds: 15, review_stop_streak: 3, tally_enough_attempts: 12,
  forms: ["words", "analogy", "visual", "doing"],
};

/** Plays a session's event log at speed through the same stage as the live view (FR-L14). */
export default function Replay() {
  const { sessionId = "" } = useParams();
  const library = useLibrary();
  const guide = useGuidedStep();
  const targetTime = guide?.decision.target_time;
  const guideRef = useRef(guide);
  guideRef.current = guide;
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState<ServerMsg[]>([]);
  const [state, setState] = useState<SessionState>(initialState);
  const [speed, setSpeed] = useState(4);
  const [playing, setPlaying] = useState(false);
  const [idx, setIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [cycleToken, setCycleToken] = useState(0);
  const timer = useRef<number | null>(null);
  const startWall = useRef(0);
  const startT = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [ev, sess] = await Promise.all([api.events(sessionId), api.session(sessionId)]);
        let lecture: LectureFull | null = null;
        if (sess.lecture_id) {
          try {
            lecture = await api.lecture(sess.lecture_id);
          } catch {
            lecture = null;
          }
        }
        if (cancelled) return;
        setEvents(ev.events);
        let snapshot = reduce(initialState, synthHello(sess, lecture));
        let startIndex = 0;
        if (targetTime != null) {
          while (startIndex < ev.events.length && ((ev.events[startIndex] as { t?: number }).t ?? 0) < targetTime) {
            snapshot = reduce(snapshot, ev.events[startIndex]); startIndex++;
          }
        }
        setIdx(startIndex);
        setState(snapshot);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, targetTime]);

  const stop = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    setPlaying(false);
  }, []);

  const play = useCallback(() => {
    if (!events.length) return;
    const first = idx < events.length ? idx : 0;
    if (first === 0) setState((s) => ({ ...initialState, hello: s.hello, bestForm: s.bestForm }));
    setIdx(first);
    startWall.current = performance.now();
    startT.current = (events[first] as { t?: number }).t ?? 0;
    setPlaying(true);
    let i = first;
    timer.current = window.setInterval(() => {
      const elapsed = ((performance.now() - startWall.current) / 1000) * speed + startT.current;
      let advanced = false;
      while (i < events.length && ((events[i] as { t?: number }).t ?? 0) <= elapsed) {
        const m = events[i];
        setState((s) => reduce(s, m));
        i += 1;
        advanced = true;
      }
      if (advanced) setIdx(i);
      if (i >= events.length || (guideRef.current && elapsed >= (targetTime ?? startT.current) + 45)) {
        guideRef.current?.reportOutcome("read");
        if (timer.current !== null) window.clearInterval(timer.current);
        timer.current = null;
        setPlaying(false);
      }
    }, 100);
  }, [events, idx, speed, targetTime]);

  useEffect(() => () => stop(), [stop]);
  useEffect(() => { if (guide?.paused) stop(); }, [guide?.paused, stop]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (ev.key.toLowerCase() === "f") {
        setCycleToken((x) => x + 1);
        ev.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onOpenChip = useCallback(() => {
    setState((s) => (s.chipIds[0] ? openChip(s, s.chipIds[0]) : s));
  }, []);
  const onIgnoreChip = useCallback(() => {
    setState((s) => s.chipIds.reduce((acc, id) => dismissChip(acc, id), s));
  }, []);

  if (error) {
    return (
      <div className="page narrow">
        {!library ? <div className="page-back"><SessionBack /></div> : null}
        <div className="card error-text">{error}</div>
      </div>
    );
  }
  const flags = state.flagOrder.map(id => state.flags[id]).filter(Boolean);
  const duration = events.reduce((last, event) => Math.max(last, (event as { t?: number }).t ?? 0), 0);
  const clipStart = targetTime ?? 0;
  const clipEnd = guide ? Math.min(duration, clipStart + 45) : duration;
  const elapsed = Math.max(0, Math.min(state.t, clipEnd) - clipStart);
  const length = Math.max(0, clipEnd - clipStart);
  return (
    <section className="lecture-replay" aria-label="Lecture replay">
      <header className="replay-heading">
        {!library && !guide ? <SessionBack /> : null}
        <div>
          <h2>{guide ? "Back to this moment" : "Replay the lecture"}</h2>
          <p>{state.hello?.lecture?.title ?? "Recorded session"}{guide && targetTime != null ? ` · from ${mmss(targetTime)}` : ""}</p>
        </div>
      </header>
      <div className="replay-player">
        <div className="replay-controls">
          <button className="replay-play" onClick={playing ? stop : play} disabled={loading || !events.length || guide?.paused}>
            <svg viewBox="0 0 20 20" aria-hidden="true">{playing
              ? <path d="M6 4v12M14 4v12" stroke="currentColor" strokeWidth="3" />
              : <path d="M6 3.5 16 10 6 16.5Z" fill="currentColor" />}</svg>
            {playing ? "Pause" : idx > 0 && idx < events.length ? "Resume" : "Play"}
          </button>
          <div className="replay-position">
            <progress value={elapsed} max={length || 1} aria-label="Replay progress" />
            <span>{mmss(elapsed)} <span aria-hidden="true">/</span> {mmss(length)}</span>
          </div>
          <div className="replay-speed" role="group" aria-label="Playback speed">
            {[1, 4, 8].map(value => <button key={value} aria-pressed={speed === value} disabled={playing}
              onClick={() => setSpeed(value)} aria-label={`${value} times speed`}>{value}×</button>)}
          </div>
        </div>
        {loading ? <p className="replay-empty" role="status">Loading the lecture…</p>
          : !events.length ? <p className="replay-empty">There is no saved playback for this session.</p>
          : <div className="replay-transcript">{state.words.length || state.interim.length ? <TranscriptPane words={state.words} interim={state.interim} flags={flags} now={state.t} /> : <p className="replay-empty">{playing ? "The transcript will appear as the lecture plays." : "Press Play to follow the lecture transcript."}</p>}</div>}
      </div>
      {state.hello?.sim.transcript && <p className="replay-note">Practice lecture · scripted transcript</p>}
      <CatchupOverlay card={state.catchup} onExpire={() => setState(s => clearCatchup(s))}
        onDismiss={() => setState(s => clearCatchup(s))} cycleToken={cycleToken} details={false} />
      <Chip count={state.chipIds.length} onOpen={onOpenChip} onIgnore={onIgnoreChip} />
    </section>
  );
}

function synthHello(sess: SessionPublic, lecture: LectureFull | null): HelloMsg {
  return {
    type: "hello",
    session: sess,
    learner: { id: sess.learner_id, name: "learner", created_at: 0, baseline_mu: null, baseline_sigma: null, baseline_at: null },
    lecture: lecture
      ? { id: lecture.id, title: lecture.title, kind: lecture.kind, duration: lecture.duration, segments: lecture.segments, keyterms: lecture.keyterms, has_media: !!lecture.media_path, quiz_count: (lecture.quiz ?? []).length }
      : null,
    config: DEFAULT_CONFIG,
    best_form: sess.best_form ?? "words",
    // Office Hours sessions have no runtime/event log and are filtered out of every list that links here;
    // this fallback only avoids widening HelloMsg's mode (an unrelated, /ws/session-only type) for a case
    // that shouldn't reach Replay in practice.
    mode: sess.mode === "office_hours" ? "live" : sess.mode,
    policy: sess.catchup_policy,
    auto_pause: sess.auto_pause,
    transcript_kind: sess.transcript_kind ?? "scripted",
    words: [],
    flags: [],
    recaps: [],
    focus: [],
    headset: { connected: true, kind: sess.headset_kind === "real" ? "real" : sess.headset_kind === "fake" ? "fake" : sess.headset_kind === "replay" ? "replay" : "simulated", port: null, state: null },
    totem: { connected: true, kind: sess.totem_kind === "real" ? "real" : "keyboard", port: null, dots: 0, fit: 0 },
    notices: [],
    sim: { headset: sess.headset_kind !== "real", totem: false, transcript: sess.transcript_kind === "scripted" },
  };
}
