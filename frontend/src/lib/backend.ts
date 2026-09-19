const localPage = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
export const backendOrigin = (import.meta.env.VITE_BACKEND_URL || (localPage ? location.origin : "http://127.0.0.1:8765")).replace(/\/$/, "");
export const needsPairing = backendOrigin !== location.origin && !import.meta.env.DEV;

export function pairingToken(): string {
  return readSessionSetting("pairing") || "";
}

export function backendUrl(path: string, authenticate = false): string {
  const url = new URL(path, backendOrigin);
  if (authenticate && needsPairing) url.searchParams.set("pairing_token", pairingToken());
  return url.toString();
}

export function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (needsPairing) headers.set("X-NeuroPace-Token", pairingToken());
  return fetch(backendUrl(path), { ...init, headers });
}
import { readSessionSetting } from "./storage";
