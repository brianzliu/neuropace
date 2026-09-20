const PREFIX = "neuropace.";
const LEGACY_PREFIX = "reflow.";

export function readLocalSetting(name: string): string | null {
  try {
    const current = localStorage.getItem(PREFIX + name);
    if (current !== null) return current;
    const legacy = localStorage.getItem(LEGACY_PREFIX + name);
    if (legacy !== null) localStorage.setItem(PREFIX + name, legacy);
    return legacy;
  } catch { return null; }
}

export function writeLocalSetting(name: string, value: string): void {
  try { localStorage.setItem(PREFIX + name, value); } catch { /* Storage may be disabled. */ }
}

export function readSessionSetting(name: string): string | null {
  const current = sessionStorage.getItem(PREFIX + name);
  if (current !== null) return current;
  const legacy = sessionStorage.getItem(LEGACY_PREFIX + name);
  if (legacy !== null) sessionStorage.setItem(PREFIX + name, legacy);
  return legacy;
}

export function writeSessionSetting(name: string, value: string): void {
  sessionStorage.setItem(PREFIX + name, value);
}
