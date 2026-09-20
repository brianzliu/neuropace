import { useMemo } from "react";

/** Text that dissolves character by character (random delays over ~500 ms, 300 ms each) when `active`.
 * Characters are grouped per word so the browser only wraps between words, never inside one. */
export default function Dissolve({ text, active, className }: { text: string; active: boolean; className?: string }) {
  const words = useMemo(() => text.split(/(\s+)/).filter((w) => w.length > 0), [text]);
  const delays = useMemo(() => words.map((w) => Array.from(w).map(() => Math.random() * 0.45)), [words]);
  return (
    <span className={"dissolve" + (active ? " active" : "") + (className ? " " + className : "")}>
      {words.map((w, wi) =>
        /^\s+$/.test(w) ? (
          <span key={wi}>{w}</span>
        ) : (
          <span key={wi} className="dissolve-word">
            {Array.from(w).map((c, i) => (
              <span key={i} style={{ ["--d" as string]: `${delays[wi][i].toFixed(3)}s` }}>
                {c}
              </span>
            ))}
          </span>
        ),
      )}
    </span>
  );
}
