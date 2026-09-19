import type { ReactNode } from "react";
import type { FocusMsg, HeadsetStatus, TotemStatus } from "../lib/types";
import { FORM_LABEL, type Form } from "../lib/types";
import { Badge, StatusDot } from "./Badges";
import { Group, Row } from "./Inspector";

interface Props {
  headset: HeadsetStatus | null;
  last: FocusMsg | null;
  totem: TotemStatus | null;
  transcriptKind: string | null;
  bestForm: Form;
  policy: string | null;
  withheld?: number;
  extraRows?: ReactNode;
}

function headsetLabel(kind: string): string {
  switch (kind) {
    case "real":
      return "MindWave";
    case "fake":
      return "pipeline synthetic";
    case "replay":
      return "recorded session";
    default:
      return "simulated";
  }
}

/** Right-hand groups on the live and replay stages: Signal, Totem, Transcript, Best form, Catch-ups. */
export default function SessionInspector({ headset, last, totem, transcriptKind, bestForm, policy, withheld, extraRows }: Props) {
  const hs = headset;
  const quality = last?.quality;
  const hsState: "ok" | "warn" | "bad" | "off" = !hs?.connected ? "off" : quality === "bad" ? "warn" : "ok";
  const cal = hs?.mw;
  const totemKeyboard = totem ? totem.kind !== "real" : false;
  return (
    <>
      <Group title="Signal">
        <Row label={<span className="row"><StatusDot state={hsState} />headset</span>}>
          <span>{hs ? headsetLabel(hs.kind) : "?"}</span>
          {hs && hs.kind !== "real" ? <Badge tone="warning">{hs.kind === "simulated" ? "simulated" : hs.kind}</Badge> : null}
        </Row>
        <Row label="quality">
          {last ? (
            <>
              <span>{last.state === "nosignal" ? "no signal" : quality === "bad" ? "poor contact" : "good"}</span>
              {last.state === "baseline" ? <Badge tone="accent">baseline {Math.round(last.baseline_progress * 100)}%</Badge> : null}
              {last.state === "drop" ? <Badge tone="danger">drop</Badge> : null}
            </>
          ) : (
            <span>waiting</span>
          )}
        </Row>
        {hs && hs.kind !== "simulated" ? (
          <Row label="calibration">
            {cal?.cal_phase ? (
              <Badge tone="accent">collecting: {cal.cal_phase.replace("_", " ")}</Badge>
            ) : cal?.calibrated ? (
              <Badge tone="success">calibrated{cal.calibration_weak ? " (weak)" : ""}</Badge>
            ) : (
              <span>not yet</span>
            )}
            {cal?.alpha_closed_open_ratio ? <span className="mono">alpha {cal.alpha_closed_open_ratio.toFixed(1)}x</span> : null}
          </Row>
        ) : null}
        <Row label="blinks">
          <span className="mono">{last?.blinks_total ?? 0}</span>
          {last?.mw?.blink_rate !== undefined && last?.mw?.blink_rate !== null ? <span className="mono">{Math.round(last.mw.blink_rate)}/min</span> : null}
        </Row>
        {last?.mw && last.mw.effort !== undefined && last.mw.effort !== null ? (
          <Row label="effort · engagement">
            <span className="mono">
              {last.mw.effort.toFixed(2)} · {(last.mw.engagement ?? 0).toFixed(2)}
            </span>
          </Row>
        ) : null}
      </Group>
      <Group title="Totem" note={totem?.hint ?? undefined}>
        <Row label={<span className="row"><StatusDot state={totem?.connected ? (totemKeyboard ? "accent" : "ok") : "off"} />pad</span>}>
          <span>{totem ? (totemKeyboard ? "keyboard" : "Arduino") : "?"}</span>
          {totemKeyboard ? <Badge>keyboard fallback (no Arduino)</Badge> : null}
        </Row>
        <Row label="saved spans">
          <span className="mono">{totem?.dots ?? 0}</span>
        </Row>
        <Row label="fit meter">
          <span className="progress" style={{ width: 90 }}>
            <i style={{ width: `${Math.round(((totem?.fit ?? 0) / 8) * 100)}%` }} />
          </span>
          <span className="mono">{totem?.fit ?? 0}/8</span>
        </Row>
      </Group>
      <Group title="Transcript">
        <Row label="source">
          <span>{transcriptKind === "deepgram" ? "Deepgram live" : transcriptKind === "recorded" ? "recorded lecture" : transcriptKind === "scripted" ? "scripted" : "?"}</span>
          {transcriptKind === "scripted" ? <Badge tone="warning">scripted</Badge> : null}
        </Row>
      </Group>
      <Group title="Catch-ups">
        <Row label="best form">
          <span>{FORM_LABEL[bestForm]}</span>
        </Row>
        {policy ? (
          <Row label="policy">
            <span>{policy === "randomized" ? "randomized per lapse" : "always shown"}</span>
          </Row>
        ) : null}
        {withheld ? (
          <Row label="withheld (study)">
            <span className="mono">{withheld}</span>
          </Row>
        ) : null}
        {extraRows}
      </Group>
    </>
  );
}
