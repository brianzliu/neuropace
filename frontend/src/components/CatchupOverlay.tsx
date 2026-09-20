import { useEffect, useId, useRef, useState } from "react";
import { ARTIFACT_LABEL, FORM_LABEL, FORMS, type CatchupExplanation, type Form } from "../lib/types";
import type { VisibleCatchup } from "../lib/sessionState";
import { Badge, SourceBadge } from "./Badges";
import { mmss } from "../lib/format";
import ArtifactView, { stepsOf } from "./ArtifactView";
import "./CatchupOverlay.css";

interface Props {
  card: VisibleCatchup | null;
  onExpire: () => void;
  onDismiss: () => void;
  explanation?: CatchupExplanation;
  onRetry?: (flagId: string) => void;
  /** Bumps to cycle the form (the F key). */
  cycleToken: number;
  freeze?: boolean; // recorded mode: paused video, keep the card until resume
  /** Team detail: where the line came from (model, cache, verbatim transcript). Students see none of that. */
  details?: boolean;
}

export default function CatchupOverlay(props: Props) {
  if (props.card?.rich) {
    return <RichCatchup key={`${props.card.flag_id}:${props.card.key}`} {...props} card={props.card} />;
  }
  return <RecapOverlay {...props} />;
}

function RichCatchup({ card, explanation, onDismiss, onRetry, cycleToken, details }: Props & { card: VisibleCatchup }) {
  const id = useId();
  const panel = useRef<HTMLElement>(null);
  const previousCycle = useRef(cycleToken);
  const [form, setForm] = useState<Form | null>(null);
  const [step, setStep] = useState(0);
  const current = explanation?.flag_id === card.flag_id ? explanation : undefined;
  const options = current?.status === "ready"
    ? (current.options ?? []).filter((option) => option.content !== null && option.content !== undefined && option.content !== "")
    : [];
  const selected = options.find((option) => option.form === form) ?? options.find((option) => option.form === "visual") ?? options[0];
  const total = selected ? stepsOf(selected.artifact, selected.content) : 1;
  const shownStep = Math.min(step, total - 1);
  const pending = !current || current.status === "pending";
  const failed = current?.status === "failed" || (!pending && !selected);
  const choose = (next: Form) => { setForm(next); setStep(0); };
  const cycle = () => {
    if (!selected || options.length < 2) return;
    choose(options[(options.indexOf(selected) + 1) % options.length].form);
  };

  useEffect(() => {
    const before = document.activeElement;
    const element = panel.current;
    element?.focus({ preventScroll: true });
    return () => {
      if (before instanceof HTMLElement && before.isConnected && (element?.contains(document.activeElement) || document.activeElement === document.body)) {
        before.focus({ preventScroll: true });
      }
    };
  }, []);
  useEffect(() => {
    if (previousCycle.current === cycleToken) return;
    previousCycle.current = cycleToken;
    cycle();
  }, [cycleToken, options, selected]);

  return (
    <section
      ref={panel}
      className="live-catchup"
      data-live-catchup
      role="dialog"
      aria-modal="false"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-note`}
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          onDismiss();
        } else if (event.key.toLowerCase() === "f" && !event.altKey && !event.ctrlKey && !event.metaKey) {
          event.preventDefault();
          event.stopPropagation();
          cycle();
        }
      }}
    >
      <header className="live-catchup-header">
        <div>
          <h2 id={`${id}-title`}>Catch up at your pace</h2>
          <p id={`${id}-note`}>This panel does not pause lecture recording or transcription.</p>
        </div>
        <button className="btn btn-sm" onClick={onDismiss}>Back to lecture</button>
      </header>
      <div className="live-catchup-body">
        <section className="live-catchup-recap" aria-label="Quick recap">
          <h3>{card.source === "transcript" ? "What was said" : "Quick recap"}{card.since !== undefined ? ` since ${mmss(card.since)}` : ""}</h3>
          <p>{card.line}</p>
          {card.now_text ? <p className="live-catchup-now"><strong>Now: </strong>{card.now_text}</p> : null}
          {card.linked_eeg ? <Badge tone="accent">from where you drifted · {Math.round(card.span_seconds ?? 0)} s</Badge> : null}
        </section>
        {pending ? <p className="live-catchup-status" role="status">Preparing an explanation from this lecture moment. You can read the recap while you wait.</p> : null}
        {failed ? (
          <div className="live-catchup-status">
            <p role="alert">{current?.error || "The explanation could not be generated for this moment."} The quick recap is still available.</p>
            {onRetry ? <button className="btn" onClick={() => onRetry(card.flag_id)}>Retry explanation</button> : null}
          </div>
        ) : null}
        {selected ? (
          <>
            <div className="live-catchup-tabs" role="tablist" aria-label="Explanation format">
              {options.map((option, index) => (
                <button
                  key={option.form}
                  id={`${id}-tab-${option.form}`}
                  className="btn btn-sm"
                  role="tab"
                  aria-selected={option === selected}
                  aria-controls={`${id}-artifact`}
                  tabIndex={option === selected ? 0 : -1}
                  onClick={() => choose(option.form)}
                  onKeyDown={(event) => {
                    let next = index;
                    if (event.key === "ArrowRight") next = (index + 1) % options.length;
                    else if (event.key === "ArrowLeft") next = (index - 1 + options.length) % options.length;
                    else if (event.key === "Home") next = 0;
                    else if (event.key === "End") next = options.length - 1;
                    else return;
                    event.preventDefault();
                    event.stopPropagation();
                    choose(options[next].form);
                    document.getElementById(`${id}-tab-${options[next].form}`)?.focus();
                  }}
                >
                  {FORM_LABEL[option.form]}
                </button>
              ))}
            </div>
            <div id={`${id}-artifact`} role="tabpanel" aria-labelledby={`${id}-tab-${selected.form}`} tabIndex={0} className="live-catchup-artifact">
              <div className="live-catchup-format">{ARTIFACT_LABEL[selected.artifact]}</div>
              <ArtifactView key={`${selected.form}:${selected.artifact}`} kind={selected.artifact} content={selected.content} step={shownStep} />
            </div>
            {total > 1 ? (
              <div className="live-catchup-steps" aria-label="Explanation steps">
                <button className="btn btn-sm" disabled={shownStep === 0} onClick={() => setStep(shownStep - 1)}>Previous step</button>
                <span role="status">Step {shownStep + 1} of {total}</span>
                <button className="btn btn-sm" disabled={shownStep >= total - 1} onClick={() => setStep(shownStep + 1)}>Next step</button>
              </div>
            ) : null}
          </>
        ) : null}
        {details ? <SourceBadge source={current?.source ?? card.source} /> : null}
      </div>
    </section>
  );
}

/** One line, dim, static; fades over ttl_s (PRD P5). */
function RecapOverlay({ card, onExpire, onDismiss, cycleToken, freeze, details }: Props) {
  const [form, setForm] = useState<Form | null>(null);
  useEffect(() => {
    setForm(null);
  }, [card?.key]);
  useEffect(() => {
    if (!card || card.source === "transcript" || cycleToken === 0) return;
    setForm((f) => {
      const cur = f ?? card.form;
      const i = FORMS.indexOf(cur);
      return FORMS[(i + 1) % FORMS.length];
    });
  }, [cycleToken, card]);
  useEffect(() => {
    if (!card || freeze) return;
    const ms = Math.max(1000, card.ttl_s * 1000);
    const id = window.setTimeout(onExpire, ms);
    return () => window.clearTimeout(id);
  }, [card, freeze, onExpire]);
  if (!card) return null;
  const f = form ?? card.form;
  const line = card.forms[f] ?? card.line;
  const since = card.since !== undefined && (card.linked_eeg || (card.span_seconds ?? 0) >= 15) ? ` since ${mmss(card.since)}` : "";
  const verbatim = card.source === "transcript";
  return (
    <div className={"hud" + (freeze ? "" : " fading")} style={{ ["--ttl" as string]: `${card.ttl_s}s` }} onClick={onDismiss} role="status">
      <div className="line">
        <span className="lbl">{verbatim ? "What was said" : "You missed"}{since}</span>
        {line}
        {card.now_text ? (
          <>
            <span className="sep">·</span>
            <span className="lbl">Now</span>
            <span className="now">{card.now_text}</span>
          </>
        ) : null}
      </div>
      <div className="meta">
        <span>
          {verbatim ? "Lecture transcript" : FORM_LABEL[f]}
          {!verbatim && (f !== card.form ? " · F for another way" : " · your best way")}
        </span>
        {card.reason === "video_pause" ? <Badge tone="accent">video paused</Badge> : null}
        {card.reason === "eeg" ? <Badge>you drifted</Badge> : null}
        {card.linked_eeg ? <Badge tone="accent">from where you drifted · {Math.round(card.span_seconds ?? 0)} s</Badge> : null}
        {details ? <SourceBadge source={card.source} /> : null}
      </div>
    </div>
  );
}
