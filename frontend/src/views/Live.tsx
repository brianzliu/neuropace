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
  return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || !!el?.isContentEditable;
}

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
      if (mic) await mic.stop();
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
  const hsKind = state.headset?.kind;
  const showSim = hsKind === "simulated" || hsKind === "fake";
  const showCal = !!state.headset && hsKind !== "simulated";
  const totemKeyboard = state.totem ? state.totem.kind !== "real" : true;

  const controls = useMemo(
    () => (
      <>
        <button className="btn btn-primary btn-lg pad-btn" onClick={doTap} title={totemKeyboard ? "No pad connected: Space works the same" : "Same as the pad"}>
          I'm lost <span className="kbd">space</span>
        </button>
        {hello?.transcript_kind === "deepgram" ? (
          <div className="grp">
            {mic ? (
              <button className="btn" onClick={() => void stopMic()}>
                Stop microphone
              </button>
            ) : (
              <button className="btn btn-primary" onClick={() => void startMic()}>
                Start microphone
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
    [doTap, doForce, doSim, doCal, state.catchup, showSim, showCal, simState, calPhase, hello?.transcript_kind, mic, ending, micError, doEnd, totemKeyboard, details],
  );

  const listening = status === "open" && !state.ended;
  const head = (
    <div className="stage-head">
      <div className="row">
        <span className="t-title2">{hello?.lecture?.title ?? (hello?.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</span>
        <span className={"pill " + (listening ? "live" : "")}>
          <span className="dot" /> {state.ended ? "ended" : listening ? "listening" : status}
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
      onCatchupExpire={onExpire}
      onCatchupDismiss={onDismiss}
      onOpenChip={onOpenChip}
      onIgnoreChip={onIgnoreChip}
      cycleToken={cycleToken}
      freezeCatchup={freeze}
      controls={controls}
      head={head}
      details={details}
    />
  );
}
