import { useEffect, useState } from "react";
import { api, errorText } from "../lib/api";

type Provider = "openai" | "openrouter" | "gemini";
const defaults: Record<Provider, string> = {
  openai: "gpt-5-mini",
  openrouter: "openai/gpt-4o-mini",
  gemini: "gemini-2.5-flash",
};

export default function ModelSettings() {
  const [provider, setProvider] = useState<Provider>("openai");
  const [configured, setConfigured] = useState<Record<Provider, boolean>>({ openai: false, openrouter: false, gemini: false });
  const [models, setModels] = useState<Record<Provider, string>>(defaults);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.modelSettings().then((settings) => {
      if (!active) return;
      setProvider(settings.provider);
      setConfigured(settings.configured);
      setModels(settings.models);
    }).catch((e) => { if (active) setError(errorText(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const choose = (next: Provider) => {
    setProvider(next); setKey(""); setMessage(""); setError("");
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await api.setModelSettings({
        provider,
        model: models[provider],
        ...(key.trim() ? { api_key: key.trim() } : {}),
      });
      setConfigured(result.configured); setKey("");
      setMessage(`${provider === "openai" ? "OpenAI" : provider === "gemini" ? "Gemini" : "OpenRouter"} is active for new sessions.`);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };

  return <div className="transcription-settings model-settings">
    <h2>Explanation model</h2>
    <p>Choose the service that writes catch-ups, notes, review cards, and whiteboard explanations.</p>
    {loading ? <p>Checking setup…</p> : <form onSubmit={(e) => void save(e)}>
      <div className="provider-switch" role="group" aria-label="Model provider">
        {(["openai", "openrouter", "gemini"] as Provider[]).map((item) => <button
          key={item} type="button" className={provider === item ? "is-active" : ""} onClick={() => choose(item)}
        >{item === "openai" ? "OpenAI" : item === "gemini" ? "Gemini" : "OpenRouter"}{configured[item] ? " · saved" : ""}</button>)}
      </div>
      <label htmlFor="model-name">Model</label>
      <input id="model-name" value={models[provider]} onChange={(e) => setModels({ ...models, [provider]: e.target.value })} spellCheck={false} required />
      <label htmlFor="model-api-key">{provider === "openai" ? "OpenAI" : provider === "gemini" ? "Gemini" : "OpenRouter"} API key</label>
      <input id="model-api-key" type="password" autoComplete="off" spellCheck={false} value={key} onChange={(e) => setKey(e.target.value)} placeholder={configured[provider] ? "Leave blank to keep saved key" : "Paste your key"} required={!configured[provider]} />
      <p>The key stays in this local server's memory until it restarts. Switching applies to new sessions.</p>
      {error && <p role="alert" className="error">{error}</p>}
      {message && <p role="status" className="success-copy">{message}</p>}
      <button className="btn btn-primary" disabled={busy || !models[provider].trim() || (!configured[provider] && !key.trim())}>{busy ? "Saving…" : `Use ${provider === "openai" ? "OpenAI" : provider === "gemini" ? "Gemini" : "OpenRouter"}`}</button>
    </form>}
  </div>;
}
