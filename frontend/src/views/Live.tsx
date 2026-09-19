import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { SessionSocket, type SocketStatus } from "../lib/ws";
import { startMicStream, type MicStream } from "../lib/audio";
import { clearCatchup, dismissChip, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import { useSimBadge } from "../lib/useSimBadge";
import { SimFlash } from "../components/Badges";
import LiveStage from "../components/LiveStage";
import SessionPlayer from "../components/SessionPlayer";
import { mmss } from "../lib/format";

export default function Live() {
  const { sessionId = "" } = useParams();
  const nav = useNavigate();
  const [state, setState] = useState<SessionState>(initialState);
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [wsError, setWsError] = useState<string | null>(null);
  const [cycleToken, setCycleToken] = useState(0);
  const [ending, setEnding] = useState(false);
  const [mic, setMic] = useState<MicStream | null>(null);
  const [micError, setMicError] = useState<string | null>(null);
  const sockRef = useRef<SessionSocket | null>(null);
  const sim = useSimBadge();
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const sock = new SessionSocket(
      sessionId,
      (m) => {
        if (m.type === "error") {
          setWsError(m.text + (m.status ? ` (status: ${m.status})` : ""));
          return;
        }
        setState((s) => reduce(s, m));
      },
      setStatus,
    );
    sockRef.current = sock;
    sock.connect();
    return () => {
      sock.close();
      sockRef.current = null;
    };
  }, [sessionId]);

  const send = useCallback((obj: Record<string, unknown>) => sockRef.current?.send(obj) ?? false, []);

  const doTap = useCallback(() => {
    send({ type: "tap" });
    sim.flash("SIMULATED TAP");
  }, [send, sim]);
  const doForce = useCallback(() => {
    send({ type: "force_flag" });
    sim.flash("SIMULATED FLAG");
  }, [send, sim]);
  const doSim = useCallback(
    (st: "focused" | "drifting" | "poor") => {
      send({ type: "sim_headset", state: st });
      sim.flash(`SIMULATED HEADSET: ${st.toUpperCase()}`);
    },
    [send, sim],
  );
  const doEnd = useCallback(async () => {
    if (ending) return;
    setEnding(true);
    try {
      if (mic) await mic.stop();
      await api.endSession(sessionId);
      nav(`/notes/${sessionId}`);
    } catch (e) {
      setWsError(String(e));
      setEnding(false);
    }
  }, [ending, mic, nav, sessionId]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const k = ev.key.toLowerCase();
      if (k === "t") doTap();
      else if (k === "l") doForce();
      else if (k === "f") setCycleToken((x) => x + 1);
      else if (k === "1") doSim("focused");
      else if (k === "2") doSim("drifting");
      else if (k === "3") doSim("poor");
      else if (k === "e") void doEnd();
      else return;
      ev.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [doTap, doForce, doSim, doEnd]);

  const onExpire = useCallback(() => setState((s) => clearCatchup(s)), []);
  const onDismiss = useCallback(() => {
    const c = stateRef.current.catchup;
    if (c) send({ type: "dismiss_catchup", flag_id: c.flag_id });
    setState((s) => clearCatchup(s));
  }, [send]);
  const onOpenChip = useCallback(() => {
    const id = stateRef.current.chipIds[0];
    if (!id) return;
    send({ type: "open_catchup", flag_id: id });
    setState((s) => openChip(s, id));
  }, [send]);
  const onIgnoreChips = useCallback(() => {
    for (const id of stateRef.current.chipIds) setState((s) => dismissChip(s, id));
  }, []);

  const onTime = useCallback((t: number, playing: boolean) => send({ type: "media_time", t, playing }), [send]);

  const startMic = async () => {
    setMicError(null);
    try {
      const sock = sockRef.current;
      if (!sock) return;
      const m = await startMicStream(sock);
      setMic(m);
    } catch (e) {
      setMicError(String(e));
    }
  };
  const stopMic = async () => {
    if (mic) await mic.stop();
    setMic(null);
  };

  const hello = state.hello;
  const recorded = hello?.mode === "recorded";
  const freeze = recorded && !!state.catchup && state.catchup.reason === "video_pause";
  const controls = useMemo(
    () => (
      <div className="panel">
        <div className="controls">
          <button onClick={doTap} title="Simulated pad tap">
            <kbd>T</kbd>tap: lost me
          </button>
          <button onClick={doForce} title="Simulated EEG flag">
            <kbd>L</kbd>force flag
          </button>
          <button onClick={() => setCycleToken((x) => x + 1)} disabled={!state.catchup}>
            <kbd>F</kbd>other form
          </button>
          {state.headset?.kind === "simulated" ? (
            <>
              <button onClick={() => doSim("focused")}>
                <kbd>1</kbd>focused
              </button>
              <button onClick={() => doSim("drifting")}>
                <kbd>2</kbd>drifting
              </button>
              <button onClick={() => doSim("poor")}>
                <kbd>3</kbd>poor signal
              </button>
            </>
          ) : null}
          {state.chipIds.length ? (
            <button className="ghost" onClick={onIgnoreChips}>
              ignore chips
            </button>
          ) : null}
          {hello?.transcript_kind === "deepgram" ? (
            mic ? (
              <button onClick={() => void stopMic()}>stop mic ({mic.sampleRate} Hz)</button>
            ) : (
              <button className="primary" onClick={() => void startMic()}>
                start microphone
              </button>
            )
          ) : null}
          <button className="danger" onClick={() => void doEnd()} disabled={ending}>
            <kbd>E</kbd>{ending ? "ending…" : "end lecture"}
          </button>
        </div>
        {micError ? <div className="error small">{micError}</div> : null}
      </div>
    ),
    [doTap, doForce, doSim, state.catchup, state.headset?.kind, state.chipIds.length, hello?.transcript_kind, mic, ending, micError, onIgnoreChips, doEnd],
  );

  const above = (
    <div className="row" style={{ justifyContent: "space-between" }}>
      <div className="row">
        <b>{hello?.lecture?.title ?? (hello?.transcript_kind === "deepgram" ? "Live microphone" : "Session")}</b>
        <span className="muted small">
          {hello?.learner.name} · {hello?.mode} · <span className="mono">{mmss(state.t)}</span>
        </span>
        <span className={"badge " + (status === "open" ? "good" : status === "failed" || status === "closed" ? "bad" : "")}>{status}</span>
        {state.ended ? <span className="badge accent">ended: {state.ended.gaps} gaps</span> : null}
      </div>
      {recorded && hello ? (
        <SessionPlayer
          lectureId={hello.lecture?.id ?? null}
          hasMedia={!!hello.lecture?.has_media}
          duration={hello.lecture?.duration ?? null}
          onTime={onTime}
          pauseSeq={state.pauseRequest?.seq ?? 0}
          onResume={() => setState((s) => clearCatchup(s))}
        />
      ) : null}
    </div>
  );

  if (wsError) {
    return (
      <div className="panel">
        <div className="error">{wsError}</div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <button onClick={() => nav(`/notes/${sessionId}`)}>Go to notes</button>
          <button onClick={() => nav(`/replay/${sessionId}`)}>Replay</button>
          <button className="ghost" onClick={() => nav("/")}>Home</button>
        </div>
      </div>
    );
  }

  return (
    <>
      <SimFlash visible={sim.visible} label={sim.label} />
      <LiveStage
        state={state}
        onCatchupExpire={onExpire}
        onCatchupDismiss={onDismiss}
        onOpenChip={onOpenChip}
        cycleToken={cycleToken}
        freezeCatchup={freeze}
        controls={controls}
        above={above}
      />
    </>
  );
}
