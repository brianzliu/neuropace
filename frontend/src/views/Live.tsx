import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useBlocker, useNavigate, useParams } from "react-router-dom";
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

function micMessage(e: unknown): string {
  const name = (e as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError") return "Reflow needs the microphone to hear the lecture. Allow it in the browser, then try again.";
  if (name === "NotFoundError") return "No microphone found. Plug one in, then try again.";
  return "The microphone could not start. " + (e instanceof Error ? e.message : String(e));
}

/** Listening (docs/PRODUCT.md §6). While the lecture is being recorded, leaving this screen asks first:
 * in-app navigation is blocked with a question, closing the tab gets the browser's own prompt. */
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
  const micRef = useRef<MicStream | null>(null);
  micRef.current = mic;
  const leaving = useRef(false); // set once the lecture is ended here, so the guard lets the navigation through
  const micTried = useRef(false);

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

  const recording = status === "open" && !state.ended && !ending && !wsError;

  const endLecture = useCallback(async (): Promise<boolean> => {
    if (ending) return false;
    setEnding(true);
    try {
      if (micRef.current) await micRef.current.stop();
      await api.endSession(sessionId);
      leaving.current = true;
      return true;
    } catch (e) {
      setWsError(String(e));
      setEnding(false);
      return false;
    }
  }, [ending, sessionId]);
  const doEnd = useCallback(async () => {
    if (await endLecture()) nav(`/done/${sessionId}`);
  }, [endLecture, nav, sessionId]);

  // in-app navigation while recording: ask first
  const blocker = useBlocker(({ currentLocation, nextLocation }) => recording && !leaving.current && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (!recording) return;
    const onUnload = (ev: BeforeUnloadEvent) => {
      ev.preventDefault();
      ev.returnValue = "";
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [recording]);
  const stopAndLeave = useCallback(async () => {
    if (await endLecture()) {
      if (blocker.state === "blocked") blocker.reset();
      nav(`/done/${sessionId}`);
    }
  }, [blocker, endLecture, nav, sessionId]);

  // the lecture ended elsewhere (a teammate's terminal, another tab): move on to the summary
  useEffect(() => {
    if (state.ended && !ending) {
      leaving.current = true;
      nav(`/done/${sessionId}`, { replace: true });
    }
  }, [state.ended, ending, nav, sessionId]);

  const startMic = useCallback(async () => {
    setMicError(null);
    try {
      const sock = sockRef.current;
      if (!sock) return;
      const m = await startMicStream(sock);
      setMic(m);
    } catch (e) {
      setMicError(micMessage(e));
    }
  }, []);
  const stopMic = async () => {
    if (mic) await mic.stop();
    setMic(null);
  };
  // a live lecture listens by itself: the microphone starts as soon as the session is open
  useEffect(() => {
    if (status !== "open" || state.hello?.transcript_kind !== "deepgram" || micTried.current) return;
    micTried.current = true;
    void startMic();
  }, [status, state.hello?.transcript_kind, startMic]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (inField(ev) || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const k = ev.key.toLowerCase();
      if (blocker.state === "blocked") {
        if (k === "escape") blocker.reset();
        else return;
        ev.preventDefault();
        return;
      }
      if (k === " " || k === "t") doTap();
      else if (k === "l" && details) doForce();
      else if (k === "f") setCycleToken((x) => x + 1);
      else if (k === "1" && details) doSim("focused");
      else if (k === "2" && details) doSim("drifting");
      else if (k === "3" && details) doSim("poor");
      else if (k === "e") void doEnd();
      else return;
      ev.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [doTap, doForce, doSim, doEnd, details, blocker]);

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

  const hello = state.hello;
  const recorded = hello?.mode === "recorded";
  const freeze = recorded && !!state.catchup && state.catchup.reason === "video_pause";
  const hsKind = state.headset?.kind;
  const showSim = hsKind === "simulated" || hsKind === "fake";
  const showCal = !!state.headset && hsKind !== "simulated";
  const totemKeyboard = state.totem ? state.totem.kind !== "real" : true;
  const practice = (state.headset && state.headset.kind !== "real") || hello?.transcript_kind === "scripted";

  const controls = useMemo(
    () => (
      <>
        <button className="btn btn-primary btn-lg pad-btn" onClick={doTap} title={totemKeyboard ? "No pad connected: Space does the same" : "Same as the pad"}>
          Catch me up <span className="kbd">space</span>
        </button>
        {hello?.transcript_kind === "deepgram" ? (
          <div className="grp">
            {mic ? (
              <button className="btn" onClick={() => void stopMic()} title="Reflow stops hearing the lecture">
                <span className="dot ok" /> Microphone on
              </button>
            ) : (
              <button className="btn btn-blue" onClick={() => void startMic()}>
                Turn the microphone on
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
          {ending ? "Writing your notes…" : "End lecture"} <span className="kbd">E</span>
        </button>
      </>
    ),
    [doTap, doForce, doSim, doCal, state.catchup, showSim, showCal, simState, calPhase, hello?.transcript_kind, mic, ending, micError, doEnd, totemKeyboard, details, startMic],
  );

  const listening = status === "open" && !state.ended;
  const head = (
    <div className="stage-head">
      <div className="row">
        <span className="t-title2">{hello?.lecture?.title ?? (hello?.transcript_kind === "deepgram" ? "Live lecture" : "Lecture")}</span>
        <span className={"pill " + (listening ? "live" : "")}>
          <span className="dot" /> {state.ended ? "ended" : listening ? "recording" : status}
        </span>
        <span className="t-subhead label-2 mono">{mmss(state.t)}</span>
        {practice ? (
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
        <button className={"btn btn-sm" + (details ? " is-on" : "")} onClick={toggleDetails} title="Signal trace, headset and pad status, rolling recaps">
          {details ? "Hide details" : "Details"}
        </button>
      </div>
    </div>
  );

  if (wsError) {
    const gone = /not running|unknown session/i.test(wsError);
    return (
      <div className="page narrow">
        <div className="complete">
          <h1 className="t-title1">{gone ? "This lecture has ended." : "Reflow lost the lecture."}</h1>
          <p className="sub">{gone ? "Your notes are ready when you are." : "The connection to Reflow dropped. If it was restarted, the lecture so far is kept and its moments are on the lecture page."}</p>
          <div className="row">
            <button className="btn btn-primary btn-lg" onClick={() => nav(`/lecture/${sessionId}`)}>
              See what you missed
            </button>
            <button className="btn btn-plain" onClick={() => nav("/")}>
              Home
            </button>
          </div>
          {details ? <div className="t-footnote mono label-3">{wsError}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <>
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
      {blocker.state === "blocked" ? (
        <div className="modal-back" onClick={() => blocker.reset()} role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="quit-title" onClick={(e) => e.stopPropagation()}>
            <h2 id="quit-title" className="t-title2">
              Do you want to quit recording?
            </h2>
            <p className="sub">Reflow is still listening to this lecture. Leaving stops the recording and writes your notes from what it heard so far.</p>
            <div className="row">
              <button className="btn btn-primary" autoFocus onClick={() => blocker.reset()}>
                Keep listening <span className="kbd">esc</span>
              </button>
              <button className="btn btn-danger" onClick={() => void stopAndLeave()} disabled={ending}>
                {ending ? "Writing your notes…" : "Stop and leave"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
