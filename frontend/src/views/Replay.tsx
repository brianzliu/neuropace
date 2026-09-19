import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { HelloMsg, LectureFull, ServerMsg, SessionPublic } from "../lib/types";
import { clearCatchup, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import LiveStage from "../components/LiveStage";
import { mmss } from "../lib/format";
import { LibraryFrame, useLibrary } from "./Library";

const DEFAULT_CONFIG: HelloMsg["config"] = {
  baseline_seconds: 180, lead_in_seconds: 8, recap_period_seconds: 20, recap_window_seconds: 30, catchup_ttl_seconds: 6,
  drop_enter_z: -1, drop_exit_z: -0.5, window_seconds: 15, review_stop_streak: 3, tally_enough_attempts: 12,
  forms: ["plain", "keyterm", "analogy", "sketch"],
};

export default function Replay() {
  const { sessionId = "" } = useParams();
  const library = useLibrary();
  if (library) return <ReplaySession sessionId={library.sessionId} />;
  return (
    <LibraryFrame sessionId={sessionId} tab="replay">
      <ReplaySession sessionId={sessionId} />
    </LibraryFrame>
  );
}

/** Plays a session's event log at speed through the same stage as the live view (FR-L14). */
function ReplaySession({ sessionId }: { sessionId: string }) {
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
        setState(reduce(initialState, synthHello(sess, lecture)));
      } catch (e) {
        setError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

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
      if (i >= events.length) {
        if (timer.current !== null) window.clearInterval(timer.current);
        timer.current = null;
        setPlaying(false);
      }
    }, 100);
  }, [events, idx, speed]);

  useEffect(() => () => stop(), [stop]);

  const onOpenChip = useCallback(() => {
    setState((s) => (s.chipIds[0] ? openChip(s, s.chipIds[0]) : s));
  }, []);

  if (error) return <div className="panel error">{error}</div>;
  const above = (
    <div className="row" style={{ justifyContent: "space-between" }}>
      <div className="row">
        <span className="replay-badge">REPLAY {speed}×</span>
        <b>{state.hello?.lecture?.title ?? "Session"}</b>
        <span className="muted small mono">{mmss(state.t)}</span>
        <span className="muted small">
          {idx}/{events.length} events
        </span>
      </div>
      <div className="row">
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={playing}>
          <option value={1}>1×</option>
          <option value={4}>4×</option>
          <option value={8}>8×</option>
        </select>
        {playing ? <button onClick={stop}>Pause</button> : <button className="primary" onClick={play}>{idx > 0 && idx < events.length ? "Resume" : "Play"}</button>}
        <button className="ghost" onClick={() => setCycleToken((x) => x + 1)} disabled={!state.catchup}>
          other form (F)
        </button>
      </div>
    </div>
  );
  return (
    <LiveStage
      state={state}
      onCatchupExpire={() => setState((s) => clearCatchup(s))}
      onCatchupDismiss={() => setState((s) => clearCatchup(s))}
      onOpenChip={onOpenChip}
      cycleToken={cycleToken}
      above={above}
      stripExtra={<span className="item">replay of {state.hello?.session.id}</span>}
    />
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
    best_form: sess.best_form ?? "plain",
    mode: sess.mode,
    policy: sess.catchup_policy,
    auto_pause: sess.auto_pause,
    transcript_kind: sess.transcript_kind ?? "scripted",
    words: [],
    flags: [],
    recaps: [],
    focus: [],
    headset: { connected: true, kind: sess.headset_kind === "real" ? "real" : "simulated", port: null, state: null },
    totem: { connected: true, kind: sess.totem_kind === "real" ? "real" : "simulated", port: null, dots: 0, fit: 0 },
    notices: [],
    sim: { headset: sess.headset_kind !== "real", totem: sess.totem_kind !== "real", transcript: sess.transcript_kind === "scripted" },
  };
}
