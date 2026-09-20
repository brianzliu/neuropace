/** Drag back through an Office Hours conversation (docs/PRODUCT.md §5a): scrubbing is read-only time travel —
 * the board and chat are shown as of that ord, nothing is edited or branched. */
export default function OHScrubber({
  maxOrd,
  ord,
  live,
  onChange,
}: {
  maxOrd: number;
  ord: number;
  live: boolean;
  onChange: (ord: number | null) => void;
}) {
  const max = Math.max(0, maxOrd);
  return (
    <div className={"oh-scrubber row" + (live ? "" : " oh-scrubber-past")}>
      <input
        type="range"
        min={0}
        max={max}
        value={Math.min(Math.max(0, ord), max)}
        disabled={max === 0}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Scrub the conversation"
      />
      {live ? (
        <span className="label-3">Now</span>
      ) : (
        <button type="button" className="btn btn-sm" onClick={() => onChange(null)}>
          Return to now
        </button>
      )}
    </div>
  );
}
