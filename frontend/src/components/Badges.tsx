import type { HeadsetStatus, TotemStatus } from "../lib/types";

export function SimFlash({ visible, label }: { visible: boolean; label: string }) {
  if (!visible) return null;
  return <div className="sim-flash">{label}</div>;
}

export function SourceBadge({ source }: { source: string | null | undefined }) {
  if (!source) return null;
  if (source === "offline") return <span className="badge offline">offline</span>;
  if (source === "cache") return <span className="badge">cached</span>;
  return <span className="badge accent">llm</span>;
}

export function StatusStrip(props: {
  headset: HeadsetStatus | null;
  quality?: string;
  totem: TotemStatus | null;
  transcriptKind: string | null;
  bestForm: string;
  policy: string | null;
  extra?: React.ReactNode;
}) {
  const { headset, quality, totem, transcriptKind, bestForm, policy, extra } = props;
  const hs = headset;
  const hsOn = !!hs?.connected;
  return (
    <div className="strip">
      <span className="item">
        <span className={"dotled " + (hsOn ? (quality === "bad" ? "warn" : "on") : "off")} />
        headset <b>{hs ? hs.kind : "?"}</b>
        {quality ? <span className="muted">{quality === "bad" ? "poor signal" : "signal ok"}</span> : null}
        {hs && hs.kind !== "real" ? <span className="badge sim">{hs.kind} headset</span> : null}
        {hs?.mw?.cal_phase ? <span className="badge accent">calibrating: {hs.mw.cal_phase}</span> : hs?.mw?.calibrated ? <span className="badge good">calibrated{hs.mw.calibration_weak ? " (weak)" : ""}</span> : null}
      </span>
      <span className="item">
        <span className={"dotled " + (totem?.connected ? "on" : "off")} />
        totem <b>{totem ? totem.kind : "?"}</b>
        <span className="muted">dots {totem?.dots ?? 0} · fit {totem?.fit ?? 0}/8</span>
        {totem?.kind === "simulated" ? <span className="badge sim">simulated totem</span> : null}
      </span>
      <span className="item">
        transcript <b>{transcriptKind ?? "?"}</b>
        {transcriptKind === "scripted" ? <span className="badge sim">scripted transcript</span> : null}
      </span>
      <span className="item">
        best form <b>{bestForm}</b>
      </span>
      {policy ? (
        <span className="item">
          catch-ups <b>{policy}</b>
        </span>
      ) : null}
      {extra}
    </div>
  );
}
