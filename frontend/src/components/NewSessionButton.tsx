// Shared single-entry launcher contract (Agent A defines, Agent B adopts).
//
// Naming rule (plans/parallel-ui-cleanup/00-README.md): "New session" is the
// launcher (dashboard only); "Start session" is the Studio setup submit;
// "End lecture" is Live only. Do not reuse these labels elsewhere.
//
// Agent B: replace BOTH Home.tsx call sites (toolbar `New session` ~line 107
// and empty-state `Start a session` ~line 126) with <NewSessionButton/> and
// delete Home's local openStudio(). Empty-state copy becomes "New session"
// so exactly one launcher with one label remains.

export function openStudio() {
  const studio = window.open("/session/new", "reflow-studio", "popup,width=1320,height=900");
  if (studio) studio.focus();
  else window.location.assign("/session/new");
}

export default function NewSessionButton({ className = "primary new-session" }: { className?: string }) {
  return (
    <button className={className} onClick={openStudio}>
      <span aria-hidden="true">＋</span> New session <small>Opens your live studio</small>
    </button>
  );
}
