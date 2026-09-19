import { useMemo } from "react";

/** Text that dissolves character by character (random delays over ~500 ms, 300 ms each) when `active`. */
export default function Dissolve({ text, active, className }: { text: string; active: boolean; className?: string }) {
  const chars = useMemo(() => Array.from(text), [text]);
  const delays = useMemo(() => chars.map(() => Math.random() * 0.45), [chars]);
  return (
    <span className={"dissolve" + (active ? " active" : "") + (className ? " " + className : "")}>
      {chars.map((c, i) => (
        <span key={i} style={{ ["--d" as string]: `${delays[i].toFixed(3)}s` }}>
          {c}
        </span>
      ))}
    </span>
  );
}
