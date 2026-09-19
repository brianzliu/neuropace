import type { FocusMsg, HeadsetStatus } from "../lib/types";

/** The student-facing focus indicator: one calm ring and one sentence. The z-score trace lives in Details. */
export default function FocusCard({ last, headset, flags }: { last: FocusMsg | null; headset: HeadsetStatus | null; flags: number }) {
  const state = !headset?.connected ? "off" : !last ? "off" : last.state;
  const settling = state === "baseline";
  const pct = settling ? Math.round((last?.baseline_progress ?? 0) * 100) : 100;
  const tone = state === "drop" ? "drop" : state === "bad" || state === "nosignal" || state === "off" ? "off" : settling ? "settle" : "steady";
  const title =
    tone === "drop" ? "You may have drifted" : tone === "off" ? (headset?.connected ? "Adjust the headset" : "No headset yet") : settling ? "Getting to know you" : "Steady";
  const body =
    tone === "drop"
      ? "Tap Lost me for a one-line catch-up, or keep listening."
      : tone === "off"
        ? headset?.connected
          ? "The pad is not touching your forehead. Nothing is recorded until it does."
          : "Focus is simulated for this session."
        : settling
          ? `Learning your normal focus during the first minutes · ${pct}%`
          : flags
            ? `${flags} moment${flags === 1 ? "" : "s"} saved for your notes.`
            : "Listening along with you. Nothing saved yet.";
  const r = 22;
  const c = 2 * Math.PI * r;
  return (
    <div className={"focus-card " + tone}>
      <svg className="focus-ring" width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
        <circle cx="28" cy="28" r={r} className="track" />
        <circle cx="28" cy="28" r={r} className="arc" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
        <circle cx="28" cy="28" r="6" className="core" />
      </svg>
      <div className="focus-text">
        <div className="focus-title">{title}</div>
        <div className="focus-body">{body}</div>
      </div>
    </div>
  );
}
