import type { CatchupMsg, Flag, FocusMsg, HeadsetStatus, HelloMsg, Notice, RecapMsg, ServerMsg, SessionEndedMsg, TotemStatus, Word, Form } from "./types";

export interface VisibleCatchup extends CatchupMsg {
  shownAt: number; // Date.now()
  key: number;
}

export interface SessionState {
  hello: HelloMsg | null;
  t: number;
  words: Word[];
  interim: Word[];
  focus: FocusMsg[];
  flags: Record<string, Flag>;
  flagOrder: string[];
  recaps: RecapMsg[];
  catchup: VisibleCatchup | null;
  pendingChips: Record<string, CatchupMsg>; // eeg catch-ups waiting behind a chip
  chipIds: string[];
  withheld: number;
  totem: TotemStatus | null;
  headset: HeadsetStatus | null;
  notices: Notice[];
  ended: SessionEndedMsg | null;
  pauseRequest: { flag_id: string; seq: number } | null;
  bestForm: Form;
  catchupSeq: number;
}

export const initialState: SessionState = {
  hello: null,
  t: 0,
  words: [],
  interim: [],
  focus: [],
  flags: {},
  flagOrder: [],
  recaps: [],
  catchup: null,
  pendingChips: {},
  chipIds: [],
  withheld: 0,
  totem: null,
  headset: null,
  notices: [],
  ended: null,
  pauseRequest: null,
  bestForm: "plain",
  catchupSeq: 0,
};

const MAX_FOCUS = 400;

export function reduce(s: SessionState, m: ServerMsg): SessionState {
  switch (m.type) {
    case "hello": {
      const flags: Record<string, Flag> = {};
      const order: string[] = [];
      for (const f of m.flags) {
        flags[f.id] = f;
        order.push(f.id);
      }
      return {
        ...s,
        hello: m,
        words: m.words,
        interim: [],
        focus: m.focus.slice(-MAX_FOCUS),
        flags,
        flagOrder: order,
        recaps: m.recaps,
        totem: m.totem,
        headset: m.headset,
        notices: m.notices ?? [],
        bestForm: m.best_form,
        t: m.focus.length ? m.focus[m.focus.length - 1].t : 0,
      };
    }
    case "words":
      if (m.final) return { ...s, words: s.words.concat(m.words), interim: [], t: Math.max(s.t, m.t ?? s.t) };
      return { ...s, interim: m.words };
    case "focus": {
      const focus = s.focus.length >= MAX_FOCUS ? s.focus.slice(-MAX_FOCUS + 1) : s.focus.slice();
      focus.push(m);
      return { ...s, focus, t: m.t };
    }
    case "flag_open":
    case "flag_close": {
      const flags = { ...s.flags, [m.flag.id]: m.flag };
      const flagOrder = s.flagOrder.includes(m.flag.id) ? s.flagOrder : s.flagOrder.concat(m.flag.id);
      return { ...s, flags, flagOrder };
    }
    case "catchup": {
      if (m.auto_show) {
        const seq = s.catchupSeq + 1;
        return { ...s, catchup: { ...m, shownAt: Date.now(), key: seq }, catchupSeq: seq };
      }
      return { ...s, pendingChips: { ...s.pendingChips, [m.flag_id]: m } };
    }
    case "chip":
      return { ...s, chipIds: s.chipIds.includes(m.flag_id) ? s.chipIds : s.chipIds.concat(m.flag_id) };
    case "catchup_withheld":
      return { ...s, withheld: s.withheld + 1 };
    case "catchup_opened":
    case "catchup_dismissed":
      return s;
    case "recap":
      return { ...s, recaps: s.recaps.concat(m).slice(-30), bestForm: m.best_form ?? s.bestForm };
    case "totem":
      return { ...s, totem: { connected: m.connected, kind: m.kind, port: m.port, dots: m.dots, fit: m.fit, pulse: m.pulse } };
    case "headset":
      return { ...s, headset: { connected: m.connected, kind: m.kind, port: m.port, state: m.state, mw: m.mw } };
    case "pause_request":
      return { ...s, pauseRequest: { flag_id: m.flag_id, seq: (s.pauseRequest?.seq ?? 0) + 1 } };
    case "session_ended":
      return { ...s, ended: m };
    case "notice":
      return { ...s, notices: s.notices.concat({ level: m.level, text: m.text }).slice(-6) };
    default:
      return s;
  }
}

/** Open a chip's pending catch-up as the visible card. */
export function openChip(s: SessionState, flagId: string): SessionState {
  const pending = s.pendingChips[flagId];
  const chipIds = s.chipIds.filter((id) => id !== flagId);
  if (!pending) return { ...s, chipIds };
  const seq = s.catchupSeq + 1;
  const rest = { ...s.pendingChips };
  delete rest[flagId];
  return { ...s, chipIds, pendingChips: rest, catchup: { ...pending, auto_show: true, shownAt: Date.now(), key: seq }, catchupSeq: seq };
}

export function dismissChip(s: SessionState, flagId: string): SessionState {
  const rest = { ...s.pendingChips };
  delete rest[flagId];
  return { ...s, chipIds: s.chipIds.filter((id) => id !== flagId), pendingChips: rest };
}

export function clearCatchup(s: SessionState): SessionState {
  return { ...s, catchup: null };
}
