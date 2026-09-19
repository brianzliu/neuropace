import { useEffect, useState } from "react";
import { FORM_LABEL, FORMS, type Form } from "../lib/types";
import type { VisibleCatchup } from "../lib/sessionState";
import { SourceBadge } from "./Badges";

interface Props {
  card: VisibleCatchup | null;
  onExpire: () => void;
  onDismiss: () => void;
  /** Bumps to cycle the form (the F key). */
  cycleToken: number;
  freeze?: boolean; // recorded mode: paused video, keep the card until resume
}

/** One line, dim, static; fades over ttl_s (PRD P5). */
export default function CatchupOverlay({ card, onExpire, onDismiss, cycleToken, freeze }: Props) {
  const [form, setForm] = useState<Form | null>(null);
  useEffect(() => {
    setForm(null);
  }, [card?.key]);
  useEffect(() => {
    if (!card || cycleToken === 0) return;
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
  return (
    <div className={"catchup" + (freeze ? "" : " fading")} style={{ ["--ttl" as string]: `${card.ttl_s}s` }} onClick={onDismiss}>
      <div>
        <span className="lbl">You missed</span>
        {line}
        {card.now_text ? (
          <>
            <span className="sep">·</span>
            <span className="lbl">Now</span>
            <span className="muted">{card.now_text}</span>
          </>
        ) : null}
      </div>
      <div className="meta">
        <span>form: {FORM_LABEL[f]}{f !== card.form ? " (F to cycle)" : " (best for this learner)"}</span>
        <SourceBadge source={card.source} />
        {card.reason === "video_pause" ? <span className="badge accent">video paused</span> : null}
        {card.reason === "eeg" ? <span className="badge">eeg flag</span> : null}
      </div>
    </div>
  );
}
