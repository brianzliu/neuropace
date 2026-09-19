import { useEffect, useRef } from "react";
import type { Flag, Word } from "../lib/types";

interface Props {
  words: Word[];
  interim: Word[];
  flags: Flag[];
  now: number;
}

export default function TranscriptPane({ words, interim, flags, now }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [words.length, interim.length]);
  const spans = flags.filter((f) => f.t_start !== null).map((f) => [f.t_start, f.t_end ?? f.t_trigger] as const);
  const inFlag = (w: Word) => spans.some(([a, b]) => w.end > a && w.start < b);
  return (
    <div ref={ref} className="panel transcript">
      {words.length === 0 && interim.length === 0 ? <span className="empty">Listening. Words appear here as they are spoken.</span> : null}
      {words.map((w, i) => (
        <span key={i} className={"w" + (inFlag(w) ? " flagged" : "") + (now - w.end < 2.5 && now - w.end >= 0 ? " now" : "")}>
          {w.w}{" "}
        </span>
      ))}
      {interim.map((w, i) => (
        <span key={"i" + i} className="w interim">
          {w.w}{" "}
        </span>
      ))}
    </div>
  );
}
