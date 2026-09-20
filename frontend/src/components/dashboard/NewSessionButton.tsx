export function openStudio() {
  const studio = window.open("/session/new", "neuropace-studio", "popup,width=1320,height=900");
  if (studio) studio.focus();
  else window.location.assign("/session/new");
}

export default function NewSessionButton() {
  return (
    <button className="primary new-session" onClick={openStudio}>
      <span aria-hidden="true">＋</span> Start session
    </button>
  );
}
