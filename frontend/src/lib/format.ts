export function mmss(t: number | null | undefined): string {
  if (t === null || t === undefined || !isFinite(t)) return "--:--";
  const s = Math.max(0, Math.round(t));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function range(t0: number, t1: number | null | undefined): string {
  return `${mmss(t0)} to ${mmss(t1 ?? t0)}`;
}

export function pct(x: number | null | undefined): string {
  if (x === null || x === undefined) return "n/a";
  return `${Math.round(x * 100)}%`;
}
