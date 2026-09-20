/**
 * Decorative side blobs (user-directed polish). Pure decoration flanking the
 * content in wide-screen margins: aria-hidden, pointer-events none, hidden
 * in compact (Studio/live/replay) chrome and below 1250px so 390px layouts
 * and reading surfaces stay clean. Theme tokens only.
 */
export default function SideBlobs() {
  return (
    <div className="side-blobs" aria-hidden="true">
      <i className="side-blob left-a" />
      <i className="side-blob left-b" />
      <i className="side-blob right-a" />
      <i className="side-blob right-b" />
    </div>
  );
}
