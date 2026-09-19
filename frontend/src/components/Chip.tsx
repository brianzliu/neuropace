interface Props {
  count: number;
  onOpen: () => void;
  onIgnore: () => void;
}

/** Notification banner: an EEG flag only offers a catch-up (PRD P4). */
export default function Chip({ count, onOpen, onIgnore }: Props) {
  if (count <= 0) return null;
  return (
    <div className="banner" role="status">
      <div className="title">Catch-up ready{count > 1 ? ` (${count})` : ""}</div>
      <div className="subtitle">The headset flagged a lapse. Tap to open, or ignore.</div>
      <div className="actions">
        <button className="btn btn-plain btn-sm" onClick={onIgnore}>
          Ignore
        </button>
        <button className="btn btn-primary btn-sm" onClick={onOpen}>
          Open
        </button>
      </div>
    </div>
  );
}
