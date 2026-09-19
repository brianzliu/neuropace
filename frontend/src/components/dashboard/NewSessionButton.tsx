/** Single dashboard launcher for the Studio window (Agent B).
 *
 * Naming rule (see plans/parallel-ui-cleanup/00-README.md): "New session" is
 * the launcher (dashboard only); "Start session" is the Studio setup submit.
 * Never reuse either label elsewhere. Agent A may re-home this component
 * into the shared shell — keep the exported contract stable.
 */

export function openStudio() {
  const studio = window.open("/session/new", "reflow-studio", "popup,width=1320,height=900");
  if (studio) studio.focus();
  else window.location.assign("/session/new");
}

export default function NewSessionButton() {
  return (
    <button className="primary new-session" onClick={openStudio}>
      <span aria-hidden="true">＋</span> New session <small>Opens your live studio</small>
    </button>
  );
}
