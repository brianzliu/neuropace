interface Props {
  count: number;
  onOpen: () => void;
}

/** "catch-up ready" at the screen edge; an EEG flag only offers a catch-up (PRD P4). */
export default function Chip({ count, onOpen }: Props) {
  if (count <= 0) return null;
  return (
    <button className="chip" onClick={onOpen} title="Open the catch-up for the moment the headset flagged">
      catch-up ready{count > 1 ? ` (${count})` : ""}
      <small>tap to open, or ignore</small>
    </button>
  );
}
