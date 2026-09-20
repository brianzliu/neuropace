import { useEffect, useState } from "react";
import { api, errorText } from "../../lib/api";

export default function DemoModeToggle() {
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.demoMode()
      .then((result) => setEnabled(result.enabled))
      .catch((cause) => setError(errorText(cause)))
      .finally(() => setReady(true));
  }, []);

  const toggle = async () => {
    if (!ready || saving) return;
    setSaving(true);
    setError("");
    try {
      const result = await api.setDemoMode(!enabled);
      setEnabled(result.enabled);
      window.location.reload();
    } catch (cause) {
      setError(errorText(cause));
      setSaving(false);
    }
  };

  return (
    <div className="demo-toggle-wrap">
      <button
        type="button"
        className={`demo-toggle${enabled ? " is-on" : ""}`}
        role="switch"
        aria-checked={enabled}
        aria-label="Show synthetic sample data"
        disabled={!ready || saving}
        onClick={toggle}
      >
        <span className="demo-toggle-track" aria-hidden="true"><span /></span>
        <span>Sample data</span>
      </button>
      {enabled ? <span className="demo-data-note">Synthetic</span> : null}
      {error ? <span className="demo-toggle-error" role="alert">{error}</span> : null}
    </div>
  );
}
