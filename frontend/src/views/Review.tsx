import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../lib/api";
import { FORM_ICON, FORM_LABEL, type Card, type Progress, type SessionPublic, type TallySummary } from "../lib/types";
import { flash } from "../lib/flash";
import { useFocusSession } from "../lib/focusSession";
import { usePushToTalk } from "../lib/pushToTalk";
import { readSessionSetting, writeSessionSetting } from "../lib/storage";
import ArtifactView from "../components/ArtifactView";
import BrainWaves from "../components/BrainWaves";
import OfficeHours from "./OfficeHours";
import { libraryHref } from "./Library";

type Mode = "explain" | "whiteboard";

/** The Review tab: two ways through the same lecture. Explain is a deck of cards, one per missed moment,
 * with the headset watching (docs/PRODUCT.md §5); Whiteboard is the voice-agent conversation with a shared
 * board (§5a). The choice sticks for the tab session. */
export default function Review() {
  const { sessionId = "" } = useParams();
  const key = `review-mode:${sessionId}`;
  const [mode, setMode] = useState<Mode>(() => (readSessionSetting(key) === "whiteboard" ? "whiteboard" : "explain"));
  const pick = (m: Mode) => {
    setMode(m);
    writeSessionSetting(key, m);
  };
  return (
    <div className="page review-page">
      <div className="review-mode-bar">
        <div className="segmented" role="tablist" aria-label="How to review">
          <button role="tab" aria-selected={mode === "explain"} className={mode === "explain" ? "is-active" : ""} onClick={() => pick("explain")}>
            Explain
          </button>
          <button role="tab" aria-selected={mode === "whiteboard"} className={mode === "whiteboard" ? "is-active" : ""} onClick={() => pick("whiteboard")}>
            Whiteboard
          </button>
        </div>
        <span className="label-3 t-footnote">{mode === "explain" ? "One moment at a time, your headset watching." : "Talk it through; the tutor draws as it goes."}</span>
      </div>
      {mode === "explain" ? <ExplainDeck sessionId={sessionId} /> : <Whiteboard sessionId={sessionId} />}
    </div>
  );
}

/** The lecture's one whiteboard conversation, opened once and reused. */
function Whiteboard({ sessionId }: { sessionId: string }) {
  const [oh, setOh] = useState<SessionPublic | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setOh(null);
    setErr(null);
    api
      .officeHoursOpen(sessionId)
      .then((s) => !cancelled && setOh(s))
      .catch((e) => !cancelled && setErr(errorText(e)));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);
  if (err) return <div className="callout danger">{err}</div>;
  if (!oh) return <div className="loading">Opening the whiteboard…</div>;
  return <OfficeHours sessionId={oh.id} original={sessionId} />;
}

type Phase = "idle" | "answering" | "feedback" | "reteach" | "done" | "blocked";

/** One card per missed moment: explain, watch, (drift → another way), one question. */
function ExplainDeck({ sessionId }: { sessionId: string }) {
  const [card, setCard] = useState<Card | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [tally, setTally] = useState<TallySummary | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [err, setErr] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [correctIdx, setCorrectIdx] = useState<number | null>(null);
  const [explanation, setExplanation] = useState("");
  const [outcome, setOutcome] = useState<"hit" | "miss" | "drop" | null>(null);
  const [drift, setDrift] = useState<{ at: number; simulated: boolean } | null>(null); // shown on the card that follows a drop
  const [step, setStep] = useState(0);
  const [nSteps, setNSteps] = useState(1);
  const [hits, setHits] = useState(0);
  const cardShownAt = useRef(0);
  const busy = useRef(false);
  const [learnerId, setLearnerId] = useState<string>();
  const focus = useFocusSession(!!learnerId, learnerId);
  const focusRef = useRef(focus);
  focusRef.current = focus;

  const applyNext = useCallback((next: Card | null, done: boolean) => {
    setChosen(null);
    setCorrectIdx(null);
    setOutcome(null);
    setStep(0);
    setNSteps(1);
    if (done || !next) {
      setCard(null);
      setPhase("done");
      return;
    }
    setCard(next);
    setPhase(next.kind === "question" ? "answering" : "reteach");
    cardShownAt.current = Date.now();
    focusRef.current.startCard();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const sess = await api.session(sessionId);
        if (cancelled) return;
        setLearnerId(sess.learner_id);
        const st = await api.reviewStart(sessionId);
        if (cancelled) return;
        setProgress(st.progress);
        setTally(st.tally);
        applyNext(st.card, st.progress.done);
      } catch (e) {
        const text = errorText(e);
        if (/not ready|no generated notes|end the session/i.test(text)) {
          setBlocked(text);
          setPhase("blocked");
        } else setErr(text);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId, applyNext]);

  const answer = useCallback(
    async (choice: number) => {
      if (!card || card.kind !== "question" || phase !== "answering" || busy.current) return;
      busy.current = true;
      setChosen(choice);
      try {
        const r = await api.reviewAnswer(sessionId, card.id, choice, focusRef.current.endCard());
        setCorrectIdx(r.correct_index);
        setExplanation(r.explanation);
        setOutcome(r.outcome);
        setProgress(r.progress);
        setTally(r.tally);
        setDrift(null);
        if (r.outcome === "hit") setHits((h) => h + 1);
        setPhase("feedback");
        window.setTimeout(() => applyNext(r.next, r.done), r.outcome === "hit" ? 1300 : 2200);
      } catch (e) {
        setErr(errorText(e));
      } finally {
        busy.current = false;
      }
    },
    [card, phase, sessionId, applyNext],
  );

  const drop = useCallback(
    async (simulated: boolean) => {
      if (!card || busy.current || (phase !== "answering" && phase !== "reteach")) return;
      busy.current = true;
      if (simulated) flash("SIMULATED DRIFT");
      try {
        const r = await api.reviewDrop(sessionId, card.id, focusRef.current.endCard());
        setDrift({ at: Math.round((Date.now() - cardShownAt.current) / 1000), simulated });
        setProgress(r.progress);
        setTally(r.tally);
        applyNext(r.next, r.done);
      } catch (e) {
        setErr(errorText(e));
      } finally {
        busy.current = false;
      }
    },
    [card, phase, sessionId, applyNext],
  );

  // a real drift while an explanation is up switches it early
  const driftSeen = useRef(0);
  useEffect(() => {
    if (focus.driftSeq === driftSeen.current) return;
    driftSeen.current = focus.driftSeq;
    if (phase === "reteach" && card) void drop(false);
  }, [focus.driftSeq, phase, card, drop]);

  const advance = useCallback(async () => {
    if (!card || card.kind !== "reteach" || busy.current) return;
    busy.current = true;
    try {
      const r = await api.reviewAdvance(sessionId, card.id, focusRef.current.endCard());
      setDrift(null);
      setProgress(r.progress);
      setTally(r.tally);
      applyNext(r.next, r.done);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      busy.current = false;
    }
  }, [card, sessionId, applyNext]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const tag = (ev.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      const k = ev.key;
      if (phase === "answering" && ["1", "2", "3", "4"].includes(k)) void answer(Number(k) - 1);
      else if (k.toLowerCase() === "d") void drop(true);
      else if (phase === "reteach" && (k === " " || k === "ArrowRight" || k === "Enter")) {
        if (step < nSteps - 1) setStep((s) => s + 1);
        else void advance();
      } else return;
      ev.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, answer, drop, advance, step, nSteps]);

  const onSteps = useCallback((n: number) => setNSteps(Math.max(1, n)), []);
  const headsetOn = !!focus.headset?.connected;

  if (err) return <div className="callout danger">{err}</div>;
  if (phase === "blocked") {
    return (
      <div className="complete">
        <div className="t-title1">Not quite ready</div>
        <p className="sub">{blocked}</p>
        <Link className="btn btn-blue" to={libraryHref(sessionId, "notes")}>
          Back to the notes
        </Link>
      </div>
    );
  }
  if (!progress || !tally) return <div className="loading">Getting your moments ready…</div>;

  const doneCount = progress.gaps_closed + progress.gaps_exhausted;
  const nowOrd = card ? card.gap_ord : progress.gaps_total;

  return (
    <div className="lesson">
      <div className="stack">
        <div className="moment-rail" aria-label={`${doneCount} of ${progress.gaps_total} moments done`}>
          {Array.from({ length: progress.gaps_total }, (_, i) => (
            <span key={i} className={"rail-dot" + (i < nowOrd || phase === "done" ? " done" : i === nowOrd ? " now" : "")}>
              {i + 1}
            </span>
          ))}
          <span className="label-3 t-footnote">
            {phase === "done" ? `All ${progress.gaps_total} moments reviewed` : card ? `Moment ${card.gap_ord + 1} of ${progress.gaps_total}` : ""}
          </span>
        </div>

        {drift && card ? (
          <div className="drift-banner" role="status">
            <b>You drifted{drift.at > 0 ? ` after ${drift.at}s` : ""}.</b> Trying it {card.reteach ? FORM_LABEL[card.reteach.form] : "another way"}.
            {drift.simulated ? <span className="sim-tag">SIMULATED</span> : null}
          </div>
        ) : null}

        <div className="lesson-card">
          {phase === "done" || !card ? (
            <DoneSummary sessionId={sessionId} progress={progress} tally={tally} hits={hits} />
          ) : card.kind === "question" && card.question ? (
            <>
              <div className="question">{card.question.question}</div>
              <div className="options">
                {card.question.options.map((o, i) => {
                  let cls = "option";
                  if (correctIdx !== null) {
                    if (i === correctIdx) cls += " correct";
                    else if (i === chosen) cls += " wrong";
                  }
                  return (
                    <button key={i} className={cls} disabled={phase !== "answering"} onClick={() => void answer(i)}>
                      <span className="k">{i + 1}</span>
                      {o}
                    </button>
                  );
                })}
              </div>
              {outcome ? (
                <div className={"feedback " + outcome}>
                  <div>
                    <div className="fb-title">{outcome === "hit" ? "That's it." : "Not yet. Let's try it another way."}</div>
                    {explanation ? <div className="fb-body">{explanation}</div> : null}
                  </div>
                </div>
              ) : (
                <div className="label-2 t-footnote">
                  Press <kbd className="kbd">1</kbd> to <kbd className="kbd">4</kbd>
                </div>
              )}
            </>
          ) : card.kind === "reteach" && card.reteach ? (
            <div className="reteach">
              <span className="artifact-kind">
                <span className="family-icon">{FORM_ICON[card.reteach.form]}</span>
                {FORM_LABEL[card.reteach.form]}
                {card.package_source === "offline" ? <span className="sim-tag">OFFLINE</span> : null}
              </span>
              {card.reteach.why && !drift ? <p className="why-line">{card.reteach.why}</p> : null}
              {card.reteach.context ? <p className="context-line">{card.reteach.context}</p> : null}
              <ArtifactView kind={card.reteach.artifact} content={card.reteach.content} step={step} onSteps={onSteps} />
              {card.reteach.said ? (
                <details className="said">
                  <summary>What the lecturer said</summary>
                  <p>{card.reteach.said}</p>
                </details>
              ) : null}
              <div className="row">
                {step < nSteps - 1 ? (
                  <button className="btn btn-blue" onClick={() => setStep((s) => s + 1)}>
                    Next ({step + 1}/{nSteps}) <span className="kbd">space</span>
                  </button>
                ) : (
                  <button className="btn btn-primary" onClick={() => void advance()}>
                    Got it, check me <span className="kbd">space</span>
                  </button>
                )}
                <button className="btn btn-plain" onClick={() => void drop(true)} title="Skip this explanation and see the moment another way">
                  Show it another way
                </button>
              </div>
              <AskMoment key={card.id} sessionId={sessionId} cardId={card.id} />
            </div>
          ) : null}
        </div>
      </div>

      <div className="lesson-side">
        <BrainWaves samples={focus.raw} rawAt={focus.rawAt} bands={focus.bands} headset={focus.headset} compact label="Your brain while you read" />
        <div className="focus-note label-3 t-footnote">
          {headsetOn
            ? "A drop switches the explanation. Only the question decides whether it landed."
            : "No headset: nothing switches on its own. Use “Show it another way”."}
        </div>
      </div>
    </div>
  );
}

/** One question about the card on screen, one answer. Typed, or held-to-talk when Deepgram is set up. */
function AskMoment({ sessionId, cardId }: { sessionId: string; cardId: string }) {
  const [text, setText] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [reply, setReply] = useState<{ text: string; source: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [micOk, setMicOk] = useState(false);
  useEffect(() => {
    api.deepgramKeyStatus().then((r) => setMicOk(r.configured)).catch(() => setMicOk(false));
  }, []);

  const send = async (q: string) => {
    const t = q.trim();
    if (!t || busy) return;
    setBusy(true);
    setErr(null);
    setAsked(t);
    setReply(null);
    setText("");
    try {
      const r = await api.reviewAsk(sessionId, cardId, t);
      setReply({ text: r.reply, source: r.source });
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const ptt = usePushToTalk(async (blob) => {
    setBusy(true);
    setErr(null);
    try {
      const { text: heard } = await api.transcribe(blob);
      await send(heard);
    } catch (e) {
      setErr(errorText(e));
      setBusy(false);
    }
  });

  return (
    <div className="ask-moment">
      {asked ? (
        <div className="ask-thread">
          <div className="ask-bubble you">{asked}</div>
          {reply ? (
            <div className="ask-bubble tutor">
              {reply.text}
              {reply.source === "offline" ? <span className="sim-tag">OFFLINE</span> : null}
            </div>
          ) : busy ? (
            <div className="ask-bubble tutor label-3">Thinking…</div>
          ) : null}
        </div>
      ) : null}
      {err ? <div className="label-3 error-text">{err}</div> : null}
      {ptt.error ? <div className="label-3">{ptt.error}</div> : null}
      <form
        className="ask-row"
        onSubmit={(e) => {
          e.preventDefault();
          void send(text);
        }}
      >
        <input id={`ask-${cardId}`} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about this moment…" disabled={busy} />
        {micOk ? (
          <button
            type="button"
            className={"btn btn-sm" + (ptt.recording ? " is-recording" : "")}
            onMouseDown={() => void ptt.start()}
            onMouseUp={ptt.stop}
            onMouseLeave={() => ptt.recording && ptt.stop()}
            onTouchStart={(e) => {
              e.preventDefault();
              void ptt.start();
            }}
            onTouchEnd={(e) => {
              e.preventDefault();
              ptt.stop();
            }}
            disabled={busy}
            title="Hold to talk"
          >
            {ptt.recording ? "Release to send" : "Hold to talk"}
          </button>
        ) : null}
        <button className="btn btn-sm btn-primary" type="submit" disabled={busy || !text.trim()}>
          Ask
        </button>
      </form>
    </div>
  );
}

function DoneSummary({ sessionId, progress, tally, hits }: { sessionId: string; progress: Progress; tally: TallySummary; hits: number }) {
  const best = tally.preferred ?? (tally.rank && tally.rank[0]) ?? null;
  const st = best ? tally.forms[best] : null;
  return (
    <div className="complete">
      <div className="big-mark">✓</div>
      <h2 className="t-title1">Every moment covered.</h2>
      <div className="stats">
        <div className="stat green">
          <div className="v">{progress.gaps_closed}</div>
          <div className="k">landed</div>
        </div>
        <div className="stat">
          <div className="v">{hits}</div>
          <div className="k">right answers</div>
        </div>
        <div className="stat orange">
          <div className="v">{progress.gaps_exhausted}</div>
          <div className="k">still tricky</div>
        </div>
      </div>
      {st && st.attempts > 0 && best ? (
        <p className="sub">
          Explaining it {FORM_LABEL[best]} led to {st.rescues} of {st.attempts} right answers
          {st.focus?.mean_focus != null ? ` and held your focus ${Math.round(st.focus.mean_focus * 100)}% of the time` : ""}.
        </p>
      ) : (
        <p className="sub">NeuroPace is still learning which explanations help you most.</p>
      )}
      {progress.gaps_exhausted > 0 ? <p className="sub">The tricky ones stay open in Notes with their sources.</p> : null}
      <div className="row">
        <Link className="btn btn-primary btn-lg" to={libraryHref(sessionId, "quiz")}>
          Take the quiz
        </Link>
        <Link className="btn btn-plain" to={libraryHref(sessionId, "notes")}>
          Back to Notes
        </Link>
      </div>
    </div>
  );
}
