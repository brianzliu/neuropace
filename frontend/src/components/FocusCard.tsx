import type { FocusMsg, HeadsetStatus } from "../lib/types";

/** The student-facing focus indicator: one calm ring and one sentence. The z-score trace lives in Details. */
export default function FocusCard({ last, headset, flags }: { last: FocusMsg | null; headset: HeadsetStatus | null; flags: number }) {
  const practice = headset?.kind === "simulated" || headset?.kind === "fake";
  const replay = headset?.kind === "replay";
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
          ? "Check the headset fit and signal quality."
          : "Connect a headset to measure focus."
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
        <div className="focus-title">{practice ? `Simulated · ${title}` : replay ? `Replay · ${title}` : title}</div>
        <div className="focus-body">{practice ? "Practice signal, not a measurement of your attention." : replay ? "Previously recorded signal, not your current attention." : body}</div>
      </div>
    </div>
  );
}
