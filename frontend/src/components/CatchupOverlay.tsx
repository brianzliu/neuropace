import { useEffect, useState } from "react";
import { FORM_LABEL, FORMS, type Form } from "../lib/types";
import type { VisibleCatchup } from "../lib/sessionState";
import { Badge, SourceBadge } from "./Badges";
import { mmss } from "../lib/format";

interface Props {
  card: VisibleCatchup | null;
  onExpire: () => void;
  onDismiss: () => void;
  /** Bumps to cycle the form (the F key). */
  cycleToken: number;
  freeze?: boolean; // recorded mode: paused video, keep the card until resume
  /** Team detail: where the line came from (model, cache, verbatim transcript). Students see none of that. */
  details?: boolean;
}

/** One line, dim, static; fades over ttl_s (PRD P5). */
export default function CatchupOverlay({ card, onExpire, onDismiss, cycleToken, freeze, details }: Props) {
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
