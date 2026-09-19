import LiveCapture, { type CaptureStatus } from "../components/LiveCapture";
import type { BoardExplanation } from "../lib/types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { backendFetch } from "../lib/backend";
import { SessionSocket, type SocketStatus } from "../lib/ws";
import { startMicStream, type MicStream } from "../lib/audio";
import { clearCatchup, dismissChip, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import { useSimBadge } from "../lib/useSimBadge";
import { SimFlash } from "../components/Badges";
import LiveStage from "../components/LiveStage";
import SessionPlayer from "../components/SessionPlayer";
import { ConnectionPills, StudioBackLink, StudioSteps, type ConnectionPill } from "../components/StudioChrome";
import { mmss } from "../lib/format";

const BOARD_EXPLANATION_TIMEOUT_MS = 12000;

export default function Live() {
  const { sessionId = "" } = useParams();
  const nav = useNavigate();
  const [state, setState] = useState<SessionState>(initialState);
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [wsError, setWsError] = useState<string | null>(null);
  const [cycleToken, setCycleToken] = useState(0);
  const [board, setBoard] = useState<BoardExplanation | null>(null);
  const [boardAwaiting, setBoardAwaiting] = useState<{ flagId: string; since: number } | null>(null);
  const [boardUnavailable, setBoardUnavailable] = useState(false);
  const [capture, setCapture] = useState<CaptureStatus>({ capturing: false, frames: 0 });
  const [ending, setEnding] = useState(false);
  const [mic, setMic] = useState<MicStream | null>(null);
  const [micError, setMicError] = useState<string | null>(null);
  const micRef = useRef<MicStream | null>(null);
  const micGeneration = useRef(0);
  const [micStarting, setMicStarting] = useState(false);
  useEffect(() => () => { micGeneration.current++; void micRef.current?.stop(); micRef.current = null; }, []);
  const sockRef = useRef<SessionSocket | null>(null);
  const sim = useSimBadge();
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const sock = new SessionSocket(
      sessionId,
      (m) => {
        if (m.type === "board_explanation") {
          // Board explanations are async, labelled and never replace the transcript
          // catch-up. They can only arrive when randomized withholding allowed it.
          setBoard(m);
          setBoardUnavailable(false);
          setBoardAwaiting((a) => (a && a.flagId === m.flag_id ? null : a));
          return;
        }
        if (m.type === "catchup_withheld") {
          setBoardAwaiting((a) => (a && a.flagId === m.flag_id ? null : a));
          setState((s) => reduce(s, m));
          return;
        }
        if (m.type === "catchup") {
          if (m.reason === "tap") {
            setBoardUnavailable(false);
            setBoardAwaiting({ flagId: m.flag_id, since: Date.now() });
          }
          setState((s) => reduce(s, m));
          return;
        }
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

  // If the server never starts a board explanation (camera off / no buffered
  // frames), say so instead of leaving a loading panel forever.
  useEffect(() => {
    if (!boardAwaiting) return;
    const timer = window.setTimeout(() => {
      setBoardAwaiting(null);
      setBoard((b) => (b && b.status === "pending" ? null : b));
      setBoardUnavailable(true);
    }, BOARD_EXPLANATION_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [boardAwaiting]);

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
      sim.flash(`${(stateRef.current.headset?.kind ?? "simulated").toUpperCase()} HEADSET: ${st.toUpperCase()}`);
    },
    [send, sim],
  );
  const doCal = useCallback(
    (phase: "eyes_closed" | "easy" | "hard" | "done" | "reset") => {
      send({ type: "calibrate", phase });
    },
    [send],
  );
  const doEnd = useCallback(async () => {
    if (ending) return;
    setEnding(true);
    try {
      micGeneration.current++;
      if (micRef.current) await micRef.current.stop();
      micRef.current = null;
      setMic(null);
      // Clear the ephemeral board buffer at end, alongside LiveCapture's own stop/unmount cleanup.
      void backendFetch(`/api/sessions/${sessionId}/board`, { method: "DELETE", keepalive: true }).catch(() => {});
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
    if (micStarting || micRef.current) return;
    setMicStarting(true);
    const run = ++micGeneration.current;
    setMicError(null);
    try {
      const sock = sockRef.current;
      if (!sock) return;
      const m = await startMicStream(sock);
      if (run !== micGeneration.current) { await m.stop(); return; }
      micRef.current = m;
      setMic(m);
    } catch (e) {
      setMicError(String(e));
    } finally { setMicStarting(false); }
  };
  const stopMic = async () => {
    micGeneration.current++;
    if (micRef.current) await micRef.current.stop();
    micRef.current = null;
    setMic(null);
  };

  const hello = state.hello;
  const recorded = hello?.mode === "recorded";
  const freeze = recorded && !!state.catchup && state.catchup.reason === "video_pause";
  const hs = state.headset;
  const tot = state.totem;
  const pills: ConnectionPill[] = [
    !hs
      ? { key: "eeg", label: "EEG", state: "pending", detail: "waiting for the session snapshot" }
      : hs.kind !== "real" || hello?.sim.headset
        ? { key: "eeg", label: "EEG", state: "simulated", detail: `${hs.kind} EEG (labelled in session)` }
        : hs.connected
          ? { key: "eeg", label: "EEG", state: "connected", detail: `real headset${hs.port ? ` · ${hs.port}` : ""}` }
          : { key: "eeg", label: "EEG", state: "pending", detail: "headset detected, not connected yet" },
    !tot
      ? { key: "button", label: "Button", state: "pending", detail: "waiting for the session snapshot" }
      : tot.kind !== "real" || hello?.sim.totem
        ? { key: "button", label: "Button", state: "simulated", detail: "simulated button (labelled in session)" }
        : tot.connected
          ? { key: "button", label: "Button", state: "connected", detail: `button device${tot.port ? ` · ${tot.port}` : ""}` }
          : { key: "button", label: "Button", state: "pending", detail: "button detected, not connected yet" },
    !hello
      ? { key: "transcription", label: "Transcription", state: "pending", detail: "waiting for the session snapshot" }
      : hello.transcript_kind === "deepgram"
        ? mic
          ? { key: "transcription", label: "Transcription", state: "connected", detail: `microphone streaming at ${mic.sampleRate} Hz` }
          : { key: "transcription", label: "Transcription", state: "pending", detail: "press Start microphone to transcribe" }
        : { key: "transcription", label: "Transcription", state: "simulated", detail: hello.transcript_kind === "recorded" ? "pre-recorded transcript (labelled)" : "scripted transcript (labelled)" },
    capture.capturing
      ? { key: "board", label: "Board camera", state: "connected", detail: `camera live · ${capture.frames} frames buffered` }
      : { key: "board", label: "Board camera", state: "off", detail: "enable board capture in the whiteboard panel" },
  ];
  const boardPanel = board && board.status === "ready"
    ? "ready"
    : boardAwaiting || board?.status === "pending"
      ? "loading"
      : boardUnavailable
        ? "unavailable"
        : null;
  const controls = useMemo(
    () => (
      <div className="panel">
        <div className="controls">
          <button onClick={doTap} title="Simulated pad tap">
            <kbd>T</kbd>I’m confused · simulated button
          </button>
          <button onClick={doForce} title="Simulated EEG flag">
            <kbd>L</kbd>force flag
          </button>
          <button onClick={() => setCycleToken((x) => x + 1)} disabled={!state.catchup}>
            <kbd>F</kbd>other form
          </button>
          {state.headset?.kind === "simulated" || state.headset?.kind === "fake" ? (
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
          {state.headset && state.headset.kind !== "simulated" ? (
            <span className="row" style={{ gap: "0.3rem" }} title="mindwave pipeline three-anchor calibration">
              <span className="dim small">calibrate:</span>
              <button className="ghost" onClick={() => doCal("eyes_closed")}>eyes closed</button>
              <button className="ghost" onClick={() => doCal("easy")}>easy</button>
              <button className="ghost" onClick={() => doCal("hard")}>hard</button>
              <button className="ghost" onClick={() => doCal("done")}>done</button>
              <button className="ghost" onClick={() => doCal("reset")}>reset</button>
            </span>
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
              <button className="primary" disabled={micStarting || status !== "open"} onClick={() => void startMic()}>
                {micStarting ? "Starting microphone…" : "Start microphone"}
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
    [doTap, doForce, doSim, doCal, state.catchup, state.headset, state.chipIds.length, hello?.transcript_kind, mic, micStarting, status, ending, micError, onIgnoreChips, doEnd],
  );

  const above = (
    <div className="col" style={{ gap: "0.6rem" }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <StudioSteps current="live" />
        <StudioBackLink leaveNote="Leaves the studio; press “end lecture” to build notes" />
      </div>
      <ConnectionPills pills={pills} />
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
    </div>
  );

  if (wsError) {
    return (
      <div className="panel">
        <div className="error">{wsError}</div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <button onClick={() => nav(`/notes/${sessionId}`)}>Go to notes</button>
          <button onClick={() => nav(`/replay/${sessionId}`)}>Replay</button>
          <button className="ghost" onClick={() => nav("/")}>Back to dashboard</button>
        </div>
      </div>
    );
  }

  return (
    <>
      <SimFlash visible={sim.visible} label={sim.label} />
      <LiveStage
        state={state}
        capture={hello?.mode === "live" ? <>
          <LiveCapture sessionId={sessionId} active={status === "open" && !ending && !state.ended} onStatus={setCapture} />
          {boardPanel ? (
            <details className="panel">
              <summary>
                {boardPanel === "ready" ? (boardAwaiting ? "Open board explanation — preparing the latest moment…" : "Open board explanation") : boardPanel === "loading" ? "Preparing board explanation…" : "Board explanation unavailable — transcript only"}
              </summary>
              {boardPanel === "loading" ? <p>Transcript recap; board explanation loading</p> : null}
              {boardPanel === "unavailable" ? <p>Transcript only; board unavailable</p> : null}
              {boardPanel === "ready" && board ? (
                <>
                  <p>{board.text}</p>
                  <span className="small muted">{board.source === "offline" ? "Offline · board not interpreted" : "Generated from transcript and board"}</span>
                  <div className="small muted">{board.frames.map(f => mmss(f.t)).join(", ")}</div>
                </>
              ) : null}
            </details>
          ) : null}
        </> : undefined}
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
