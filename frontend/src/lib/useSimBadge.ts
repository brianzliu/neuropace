import { useCallback, useEffect, useRef, useState } from "react";

/** Flashes a SIMULATED badge for 2 s whenever `flash()` is called (PRD P9). */
export function useSimBadge(): { visible: boolean; label: string; flash: (label?: string) => void } {
  const [visible, setVisible] = useState(false);
  const [label, setLabel] = useState("SIMULATED");
  const timer = useRef<number | null>(null);
  const flash = useCallback((l?: string) => {
    setLabel(l ?? "SIMULATED");
    setVisible(true);
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setVisible(false), 2000);
  }, []);
  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);
  return { visible, label, flash };
}
