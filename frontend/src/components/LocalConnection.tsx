import { useState, type ReactNode } from "react";
import { backendFetch, backendOrigin, needsPairing, pairingToken } from "../lib/backend";
import { writeSessionSetting } from "../lib/storage";

export default function LocalConnection({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(!needsPairing);
  const [token, setToken] = useState(pairingToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const connect = async () => {
    setBusy(true); setError("");
    try {
      writeSessionSetting("pairing", token.trim());
      const response = await backendFetch("/api/bridge/check", { signal: AbortSignal.timeout(10000) });
      if (response.status === 401) throw new Error("The pairing code has changed. Copy the code from the running NeuroPace service.");
      if (!response.ok) throw new Error("Connection refused. Check the allowed website address in your local service settings.");
      const result = await response.json();
      if (result.ok !== true) throw new Error("This is not a NeuroPace service. Check the backend address.");
      setConnected(true);
    } catch (e) {
      setError(e instanceof TypeError || (e instanceof DOMException && e.name === "TimeoutError")
        ? "Could not reach NeuroPace on this computer. Start the service, allow local network access in your browser, then try again."
        : String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); }
  };
  if (connected) return children;
  return <section className="panel" style={{maxWidth: 620, margin: "3rem auto"}}>
    <h1>Connect this computer</h1>
    <p>NeuroPace's headset, button, and session data stay with the service on your laptop. Start it before opening your workspace.</p>
    <p>Run this in the NeuroPace project folder:</p>
    <pre style={{overflowX: "auto"}}>uv run neuropace serve</pre>
    <p>Paste the pairing code printed in the terminal. Allow local network access if your browser asks.</p>
    <form onSubmit={e => { e.preventDefault(); void connect(); }}>
      <label htmlFor="pairing-code">Pairing code</label>
      <input id="pairing-code" type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} required style={{display: "block", width: "100%", margin: "12px 0"}} />
      <button type="submit" disabled={busy || !token.trim()}>{busy ? "Connecting…" : "Connect to NeuroPace"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    <p className="small muted">Service address: {backendOrigin}. Keep the service running during your session. A phone or another laptop needs its own connection setup.</p>
    <a href={backendOrigin}>Open the local interface</a>
  </section>;
}
