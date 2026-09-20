import { useEffect, useState } from "react";
import type { FocusMsg, HeadsetStatus } from "../lib/types";

/** The student-facing focus indicator: one calm ring and one sentence. The z-score trace lives in Details.
 * "Headset lost" follows the same arrival-time test as the brain waves, so the two never disagree. */
export default function FocusCard({ last, headset, flags, rawAt }: { last: FocusMsg | null; headset: HeadsetStatus | null; flags: number; rawAt?: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, []);
  const focusDisabled = headset?.focus_enabled === false || last?.focus_enabled === false;
  const real = headset?.kind === "real";
  const practice = headset?.kind === "simulated" || headset?.kind === "fake";
  const replay = headset?.kind === "replay";
  const streamLive = rawAt !== undefined ? rawAt > 0 && now - rawAt < 2000 : headset?.stream ? headset.stream.live : true;
  const lost = real && !streamLive;
  const state = focusDisabled || !headset ? "off" : lost ? "lost" : !last ? "off" : last.state;  const settling = state === "baseline";
  const pct = focusDisabled ? 0 : settling ? Math.round((last?.baseline_progress ?? 0) * 100) : 100;
  const tone = state === "drop" ? "drop" : state === "lost" ? "lost" : state === "bad" || state === "nosignal" || state === "off" ? "off" : settling ? "settle" : "steady";
  const title = focusDisabled ? "Button-only mode" :
    tone === "drop"
      ? "You may have drifted"
      : tone === "lost"
        ? "Headset lost"
        : tone === "off"
          ? headset && headset.kind !== "real"
            ? "Practice focus"
            : "Adjust the headset"
          : settling
            ? "Getting to know you"
            : "Steady";
  const body = focusDisabled ? "Automatic focus detection is off for this session. Tap Catch me up whenever you need a recap." :
    tone === "drop"
      ? "Tap Catch me up for a one-line recap, or keep listening."
      : tone === "lost"
        ? "Reconnecting to your headset. Focus pauses until it is back; the lecture keeps recording."
        : tone === "off"
          ? headset && headset.kind !== "real"
            ? "No headset today, so focus is simulated. Catch me up still works."
            : last?.artifact
              ? "Movement is obscuring the signal. Keep still for a moment; the lecture keeps recording."
              : "Check the forehead sensor and ear clip. Focus pauses until contact improves; the lecture keeps recording."
          : settling
            ? `Learning your normal focus during the first minutes · ${pct}%`
            : flags
              ? `${flags} moment${flags === 1 ? "" : "s"} saved for your notes.`
              : "Listening along with you. Nothing saved yet.";  const r = 22;
  const c = 2 * Math.PI * r;
  return (
    <div className={"focus-card " + tone}>
      <svg className="focus-ring" width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
        <circle cx="28" cy="28" r={r} className="track" />
        <circle cx="28" cy="28" r={r} className="arc" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
        <circle cx="28" cy="28" r="6" className="core" />
      </svg>
      <div className="focus-text">
        <div className="focus-title">{focusDisabled ? title : practice ? `Simulated · ${title}` : replay ? `Replay · ${title}` : title}</div>
        <div className="focus-body">{focusDisabled ? body : practice ? "Practice signal, not a measurement of your attention." : replay ? "Previously recorded signal, not your current attention." : body}</div>
      </div>
    </div>
  );
}
