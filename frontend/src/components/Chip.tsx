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
      <div className="title">Want a quick catch-up?{count > 1 ? ` (${count})` : ""}</div>
      <div className="subtitle">It looks like you drifted for a moment. One line, then back to the lecture.</div>
      <div className="actions">
        <button className="btn btn-plain btn-sm" onClick={onIgnore}>
          I'm fine
        </button>
        <button className="btn btn-primary btn-sm" onClick={onOpen}>
          Show me
        </button>
      </div>
    </div>
  );
}
