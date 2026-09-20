import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { SessionSocket } from "./ws";
import type { FocusMsg, HeadsetStatus, ServerMsg } from "./types";

/** A headset-only session for restudy (docs/PRODUCT.md §5): brain waves, focus state, drift flags, and a per-card
 * focus ratio (fraction of the card's seconds not spent in a drop). Ends the session on unmount. */
export interface FocusSession {
  ready: boolean;
  headset: HeadsetStatus | null;
  last: FocusMsg | null;
  raw: number[];
  rawAt: number;
  bands: { theta: number; alpha: number; beta: number } | null;
  /** Bumps when the headset flags a drop while a card is open. */
  driftSeq: number;
  startCard: () => void;
  /** Returns the focus ratio for the card just shown, or null without a usable headset. */
  endCard: () => number | null;
}

export function useFocusSession(enabled: boolean, learnerId?: string): FocusSession {
  const [headset, setHeadset] = useState<HeadsetStatus | null>(null);
  const [last, setLast] = useState<FocusMsg | null>(null);
  const [raw, setRaw] = useState<number[]>([]);
  const [rawAt, setRawAt] = useState(0);
  const [bands, setBands] = useState<FocusSession["bands"]>(null);
  const [ready, setReady] = useState(false);
  const [driftSeq, setDriftSeq] = useState(0);
  const sock = useRef<SessionSocket | null>(null);
  const sid = useRef<string | null>(null);
  const card = useRef<{ total: number; dropped: number; valid: number } | null>(null);
  const lastRef = useRef<FocusMsg | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    (async () => {
      try {
        // the lecture's own calibration carries over: focus counts from the first card instead of after a new baseline
        const s = await api.createSession({ mode: "review", learner_id: learnerId, headset: "auto", totem: "keyboard", use_stored_baseline: true });
        if (!alive) {
          await api.endSession(s.id).catch(() => undefined);
          return;
        }
        sid.current = s.id;
        const ws = new SessionSocket(
          s.id,
          (m: ServerMsg) => {
            if (m.type === "hello") {
              setHeadset(m.headset);
              setReady(true);
            } else if (m.type === "headset") {
              setHeadset({ connected: m.connected, kind: m.kind, simulated: m.simulated, port: m.port, state: m.state, stream: m.stream, mw: m.mw });
            } else if (m.type === "focus") {
              lastRef.current = m;
              setLast(m);
              if (m.bands) setBands(m.bands);
              const c = card.current;
              if (c) {
                c.total += 1;
                if (!m.sim && !m.artifact && !m.paused && m.x != null && m.quality === "good" && m.baseline_ready) {
                  c.valid += 1;
                  if (m.state === "drop") c.dropped += 1;
                }
              }
            } else if (m.type === "raw") {
              setRaw((r) => (r.length > 512 ? r.slice(-512 + m.uv.length).concat(m.uv) : r.concat(m.uv)));
              setRawAt(Date.now());
            } else if (m.type === "flag_open" && (m.flag.source === "eeg" || m.flag.source === "forced")) {
              if (card.current && !m.flag.simulated) setDriftSeq((n) => n + 1);
            }
          },
          () => undefined,
        );
        sock.current = ws;
        ws.connect();
      } catch {
        setReady(false);
      }
    })();
    return () => {
      alive = false;
      sock.current?.close();
      sock.current = null;
      const id = sid.current;
      sid.current = null;
      if (id) void api.endSession(id).catch(() => undefined);
    };
  }, [enabled, learnerId]);

  const startCard = useCallback(() => {
    card.current = { total: 0, dropped: 0, valid: 0 };
  }, []);
  const endCard = useCallback((): number | null => {
    const c = card.current;
    card.current = null;
    if (!c || c.valid < 3) return null;
    return Math.round((1 - c.dropped / c.valid) * 1000) / 1000;
  }, []);

  return { ready, headset, last, raw, rawAt, bands, driftSeq, startCard, endCard };
}
