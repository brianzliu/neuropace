import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";

export default function DeepgramSettings() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    api.deepgramKeyStatus().then(s => { if (active) setConfigured(s.configured); })
      .catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, []);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await api.setDeepgramKey(key.trim());
      setKey(""); setConfigured(true); setEditing(false); setSaved(true);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  return <div className="transcription-settings">
    <h2>Lecture transcription</h2>
    {error && <p role="alert" className="error">{error}</p>}
    {configured === null && !error && <p>Checking setup…</p>}
    {configured && !editing ? <>
      <p role="status">{saved ? "Key saved for this server run. Start a new session to use it." : "Deepgram key is configured."}</p>
      <button type="button" className="linklike" onClick={() => setEditing(true)}>Change API key</button>
    </> : configured !== null || error ? <form onSubmit={e => void save(e)}>
      <label htmlFor="deepgram-api-key">Deepgram API key</label>
      <input id="deepgram-api-key" type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} placeholder="Paste your key" required disabled={busy} aria-describedby="deepgram-key-help" />
      <p id="deepgram-key-help">Kept in your local server’s memory until it restarts. Used by Deepgram to transcribe your lecture audio.</p>
      <button className="btn btn-primary" disabled={busy || !key.trim()}>{busy ? "Saving…" : "Save key"}</button>
      {configured && <button type="button" className="btn btn-plain" disabled={busy} onClick={() => { setKey(""); setEditing(false); }}>Cancel</button>}
    </form> : null}
  </div>;
}
