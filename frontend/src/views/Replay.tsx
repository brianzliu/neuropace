import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { HelloMsg, LectureFull, ServerMsg, SessionPublic } from "../lib/types";
import { clearCatchup, dismissChip, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import LiveStage from "../components/LiveStage";
import { Badge } from "../components/Badges";
import { mmss } from "../lib/format";

const DEFAULT_CONFIG: HelloMsg["config"] = {
  baseline_seconds: 180, lead_in_seconds: 8, recap_period_seconds: 20, recap_window_seconds: 30, catchup_ttl_seconds: 6,
  drop_enter_z: -1.25, drop_exit_z: -0.6, window_seconds: 15, review_stop_streak: 3, tally_enough_attempts: 12,
  forms: ["words", "analogy", "visual", "doing"],
};

/** Plays a session's event log at speed through the same stage as the live view (FR-L14). */
export default function Replay() {
  const { sessionId = "" } = useParams();
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
        <div className="card error-text">{error}</div>
      </div>
    );
  }
  const head = (
    <div className="transport">
      <Badge tone="purple">replay</Badge>
      <span className="t-title3">{state.hello?.lecture?.title ?? "Session"}</span>
      <span className="mono t-subhead label-2">{mmss(state.t)}</span>
      <span className="t-footnote label-2">
        {idx}/{events.length} events
      </span>
      <div className="right row">
        <div className="segmented sm">
          {[1, 4, 8].map((s) => (
            <button key={s} className={speed === s ? "is-active" : ""} disabled={playing} onClick={() => setSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
        <button className="btn" onClick={() => setCycleToken((x) => x + 1)} disabled={!state.catchup}>
          Other form <span className="kbd">F</span>
        </button>
        {playing ? (
          <button className="btn" onClick={stop}>
            Pause
          </button>
        ) : (
          <button className="btn btn-primary" onClick={play}>
            {idx > 0 && idx < events.length ? "Resume" : "Play"}
          </button>
        )}
      </div>
    </div>
  );
  return (
    <LiveStage
      details={true}
      state={state}
      onCatchupExpire={() => setState((s) => clearCatchup(s))}
      onCatchupDismiss={() => setState((s) => clearCatchup(s))}
      onOpenChip={onOpenChip}
      onIgnoreChip={onIgnoreChip}
      cycleToken={cycleToken}
      head={head}
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
