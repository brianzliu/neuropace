import LiveCapture, { type CaptureStatus } from "../components/LiveCapture";
import type { BoardExplanation } from "../lib/types";
import { backendFetch } from "../lib/backend";
import { ConnectionPills, type ConnectionPill } from "../components/StudioChrome";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { SessionSocket, type SocketStatus } from "../lib/ws";
import { startMicStream, type MicStream } from "../lib/audio";
import { clearCatchup, dismissChip, initialState, openChip, reduce, type SessionState } from "../lib/sessionState";
import { flash } from "../lib/flash";
import { Badge } from "../components/Badges";
import LiveStage from "../components/LiveStage";
import SessionPlayer from "../components/SessionPlayer";
import { mmss } from "../lib/format";

const BOARD_EXPLANATION_TIMEOUT_MS = 12000;

type SimState = "focused" | "drifting" | "poor";
type CalPhase = "eyes_closed" | "easy" | "hard" | "done" | "reset";
const CAL: { k: CalPhase; label: string }[] = [
  { k: "eyes_closed", label: "eyes closed" },
  { k: "easy", label: "easy" },
  { k: "hard", label: "hard" },
  { k: "done", label: "done" },
  { k: "reset", label: "reset" },
];

function inField(ev: KeyboardEvent): boolean {
  const el = ev.target as HTMLElement | null;
  const tag = el?.tagName;
  return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || tag === "BUTTON" || tag === "A" || !!el?.isContentEditable;
}

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
  const [simState, setSimState] = useState<SimState>("focused");
  const [calPhase, setCalPhase] = useState<CalPhase | null>(null);
  const [details, setDetails] = useState<boolean>(() => {
    try {
      return new URLSearchParams(window.location.search).get("details") === "1" || localStorage.getItem("reflow.details") === "1";
    } catch {
      return false;
    }
  });
  const toggleDetails = useCallback(() => {
    setDetails((v) => {
      try {
        localStorage.setItem("reflow.details", v ? "0" : "1");
      } catch {
        // ignore
      }
      return !v;
    });
  }, []);
  const sockRef = useRef<SessionSocket | null>(null);
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
          setBoardAwaiting((a) => (m.status !== "pending" && a && a.flagId === m.flag_id ? null : a));
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
    flash("Catching you up", "neutral");
  }, [send]);
  const doForce = useCallback(() => {
    send({ type: "force_flag" });
    flash("SIMULATED FLAG");
  }, [send]);
  const doSim = useCallback(
    (st: SimState) => {
      setSimState(st);
      send({ type: "sim_headset", state: st });
      const kind = (stateRef.current.headset?.kind ?? "simulated").toUpperCase();
      flash(`${kind} HEADSET: ${st.toUpperCase()}`);
    },
    [send],
  );
  const doCal = useCallback(
    (phase: CalPhase) => {
      setCalPhase(phase === "done" || phase === "reset" ? null : phase);
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
      nav(`/done/${sessionId}`);
    } catch (e) {
      setWsError(String(e));
      setEnding(false);
    }
  }, [ending, mic, nav, sessionId]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (inField(ev) || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const k = ev.key.toLowerCase();
      if (k === " " || k === "t") doTap();
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
  const onIgnoreChip = useCallback(() => {
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
  const hsKind = state.headset?.kind;
  const showSim = hsKind === "simulated" || hsKind === "fake";
  const showCal = !!state.headset && hsKind !== "simulated";
  const totemKeyboard = state.totem ? state.totem.kind !== "real" : true;

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
        ? { key: "button", label: "Button", state: "off", detail: "on-screen or keyboard button; no physical pad connected" }
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
      <>
        <button className="btn btn-primary btn-lg pad-btn" onClick={doTap} title={totemKeyboard ? "No pad connected: Space works the same" : "Same as the pad"}>
          I’m confused <span className="kbd">space</span>
        </button>
        {hello?.transcript_kind === "deepgram" ? (
          <div className="grp">
            {mic ? (
              <button className="btn" onClick={() => void stopMic()}>
                Stop microphone
              </button>
            ) : (
              <button className="btn btn-primary" disabled={micStarting || status !== "open"} onClick={() => void startMic()}>
                {micStarting ? "Starting microphone…" : "Start microphone"}
              </button>
            )}
            {micError ? <span className="t-footnote error-text">{micError}</span> : null}
          </div>
        ) : null}
        {details ? (
          <>
            <span className="sep" />
            <span className="cap">demo</span>
            <button className="btn btn-sm" onClick={doForce} title="Opens an EEG-style flag without the headset (labelled simulated)">
              Force flag <span className="kbd">L</span>
            </button>
            <button className="btn btn-sm" onClick={() => setCycleToken((x) => x + 1)} disabled={!state.catchup}>
              Other form <span className="kbd">F</span>
            </button>
            {showSim ? (
              <div className="segmented sm">
                {(["focused", "drifting", "poor"] as SimState[]).map((st, i) => (
                  <button key={st} className={simState === st ? "is-active" : ""} onClick={() => doSim(st)}>
                    {st} <span className="kbd">{i + 1}</span>
                  </button>
                ))}
              </div>
            ) : null}
            {showCal ? (
              <div className="segmented sm">
                {CAL.map((c) => (
                  <button key={c.k} className={calPhase === c.k ? "is-active" : ""} onClick={() => doCal(c.k)}>
                    {c.label}
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
        <button className="btn btn-danger right" onClick={() => void doEnd()} disabled={ending}>
          {ending ? "Ending…" : "End lecture"} <span className="kbd">E</span>
        </button>
      </>
    ),
    [doTap, doForce, doSim, doCal, state.catchup, showSim, showCal, simState, calPhase, hello?.transcript_kind, mic, micStarting, status, ending, micError, doEnd, totemKeyboard, details],
  );

  const listening = status === "open" && !state.ended && (hello?.transcript_kind !== "deepgram" || !!mic);
  const head = (
    <div className="stage-head">
      <div className="row">
        <span className="t-title2">{hello?.lecture?.title ?? (hello?.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</span>
        <span className={"pill " + (listening ? "live" : "")}>
          <span className="dot" /> {state.ended ? "ended" : listening ? "listening" : status === "open" ? "microphone off" : status}
        </span>
        <span className="t-subhead label-2 mono">{mmss(state.t)}</span>
        {(state.headset && state.headset.kind !== "real") || hello?.transcript_kind === "scripted" ? (
          <Badge tone="warning" title={[state.headset && state.headset.kind !== "real" ? "simulated headset" : "", hello?.transcript_kind === "scripted" ? "practice transcript" : ""].filter(Boolean).join(", ")}>
            practice
          </Badge>
        ) : null}
      </div>
      <div className="row">
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
        <button className={"btn btn-sm" + (details ? " is-on" : "")} onClick={toggleDetails} title="Signal trace, headset and totem status, rolling recaps">
          {details ? "Hide details" : "Details"}
        </button>
      </div>
    </div>
  );

  if (wsError) {
    return (
      <div className="page narrow">
        <div className="card">
          <div className="error-text">{wsError}</div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => nav(`/notes/${sessionId}`)}>
              Notes
            </button>
            <button className="btn" onClick={() => nav(`/team/replay/${sessionId}`)}>
              Replay
            </button>
            <button className="btn btn-plain" onClick={() => nav("/")}>
              Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
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
      onIgnoreChip={onIgnoreChip}
      cycleToken={cycleToken}
      freezeCatchup={freeze}
      controls={controls}
      head={<>{head}<ConnectionPills pills={pills} /></>}
      details={details}
    />
  );
}
