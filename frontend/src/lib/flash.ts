import { useEffect, useState } from "react";

/** A short capsule in the toolbar (2 s): "KEY TAP", "SIMULATED FLAG", ... Any view can flash; App renders it. */
export interface FlashMsg {
  label: string;
  tone: "warning" | "neutral";
  seq: number;
}

let seq = 0;
const listeners = new Set<(m: FlashMsg | null) => void>();
let timer: number | null = null;

export function flash(label: string, tone: "warning" | "neutral" = "warning"): void {
  seq += 1;
  const m: FlashMsg = { label, tone, seq };
  for (const l of listeners) l(m);
  if (timer !== null) window.clearTimeout(timer);
  timer = window.setTimeout(() => {
    timer = null;
    for (const l of listeners) l(null);
  }, 2000);
}

export function useFlash(): FlashMsg | null {
  const [m, setM] = useState<FlashMsg | null>(null);
  useEffect(() => {
    listeners.add(setM);
    return () => {
      listeners.delete(setM);
    };
  }, []);
  return m;
}
