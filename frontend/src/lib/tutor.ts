import { useCallback, useEffect, useRef, useState } from "react";
import { backendFetch } from "./backend";
import type { AnalogyContent, AnimationContent, ArtifactKind, Card, ChartContent, CompareContent, ExampleContent, PlotContent, ReteachContent, SceneGraph, StepsContent, TimelineContent, WordsContent } from "./types";

/** One spoken beat of an explanation and the reveal step the template should be at while it is read. */
export interface Beat {
  text: string;
  step: number;
}

const sentences = (t: string): string[] =>
  (t ?? "")
    .split(/(?<=[.!?])\s+/)
    .map((x) => x.trim())
    .filter(Boolean);

/** What the tutor says for one template, in reveal order (docs/PRODUCT.md §5): the voice and the picture advance together. */
export function narrationOf(kind: ArtifactKind, content: ReteachContent): Beat[] {
  if (!content) return [];
  const out: Beat[] = [];
  switch (kind) {
    case "words": {
      const c = content as WordsContent;
      for (const s of sentences(c.summary)) out.push({ text: s, step: 0 });
      if (c.key_idea?.term) out.push({ text: `The key idea: ${c.key_idea.term}. ${c.key_idea.definition}`, step: 0 });
      if (c.key_idea?.example) out.push({ text: `For example, ${c.key_idea.example}`, step: 0 });
      return out;
    }
    case "analogy": {
      if (typeof content === "string") return sentences(content).map((s) => ({ text: s, step: 0 }));
      const c = content as AnalogyContent;
      for (const s of sentences(c.story)) out.push({ text: s, step: 0 });
      c.mapping.forEach((m, i) => out.push({ text: `${m.idea} is like ${m.everyday}.`, step: i + 1 }));
      if (c.caveat) out.push({ text: `Where it stops holding: ${c.caveat}`, step: c.mapping.length });
      return out;
    }
    case "diagram": {
      const g = content as SceneGraph;
      if (g.title) out.push({ text: g.title, step: 0 });
      g.steps.forEach((s, i) => out.push({ text: s.caption, step: i }));
      return out;
    }
    case "chart": {
      const c = content as ChartContent;
      out.push({ text: c.title, step: 0 });
      c.points.forEach((p, i) => out.push({ text: `${p.label}: ${p.value} ${c.unit}`.trim(), step: i }));
      if (c.takeaway) out.push({ text: c.takeaway, step: c.points.length - 1 });
      return out;
    }
    case "plot": {
      const c = content as PlotContent;
      out.push({ text: `${c.title}. ${c.y_label} against ${c.x_label}.`, step: 0 });
      c.series.forEach((s, i) => out.push({ text: `This curve is ${s.name}.`, step: i }));
      c.annotations.forEach((a) => out.push({ text: a.text, step: c.series.length - 1 }));
      if (c.takeaway) out.push({ text: c.takeaway, step: c.series.length - 1 });
      return out;
    }
    case "timeline": {
      const c = content as TimelineContent;
      out.push({ text: c.title, step: 0 });
      c.events.forEach((e, i) => out.push({ text: `${e.when}: ${e.label}. ${e.detail}`, step: i }));
      if (c.takeaway) out.push({ text: c.takeaway, step: c.events.length - 1 });
      return out;
    }
    case "compare": {
      const c = content as CompareContent;
      out.push({ text: `${c.left} versus ${c.right}.`, step: 0 });
      c.rows.forEach((r, i) => out.push({ text: `${r.aspect}. ${c.left}: ${r.left_value}. ${c.right}: ${r.right_value}.`, step: i + 1 }));
      if (c.verdict) out.push({ text: c.verdict, step: c.rows.length });
      return out;
    }
    case "animation": {
      const c = content as AnimationContent;
      out.push({ text: c.title, step: 0 });
      if (c.caption) out.push({ text: c.caption, step: 0 });
      return out;
    }
    case "steps": {
      const c = content as StepsContent;
      if (c.title) out.push({ text: c.title, step: 0 });
      c.steps.forEach((s, i) => out.push({ text: `Step ${i + 1}. ${s}`, step: i }));
      return out;
    }
    case "example": {
      const c = content as ExampleContent;
      if (c.title) out.push({ text: c.title, step: 0 });
      c.lines.forEach((l, i) => out.push({ text: l, step: i }));
      if (c.result) out.push({ text: `So: ${c.result}`, step: c.lines.length });
      return out;
    }
  }
}

/** The whole narration for a reteach card: why this family, where you were, then the template beat by beat. */
export function narrationForCard(card: Card): Beat[] {
  const r = card.reteach;
  if (!r) return [];
  const beats: Beat[] = [];
  if (r.why) beats.push({ text: r.why, step: 0 });
  if (r.context) beats.push({ text: `Where you were: ${r.context}`, step: 0 });
  return beats.concat(narrationOf(r.artifact, r.content));
}

export interface Tutor {
  /** The server can speak (a Deepgram key is set). */
  supported: boolean;
  enabled: boolean;
  setEnabled: (on: boolean) => void;
  speaking: boolean;
  error: string | null;
  /** Index into the beats being read, or -1. */
  beat: number;
  /** Reads the beats in order; resolves when done or stopped. onBeat fires as each beat starts. */
  play: (beats: Beat[], onBeat?: (i: number, beat: Beat) => void) => Promise<void>;
  stop: () => void;
}

async function fetchBeat(text: string): Promise<string | null> {
  try {
    const res = await backendFetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal: AbortSignal.timeout(25000) });
    if (!res.ok) return null;
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

export function playUrl(url: string, gen: () => boolean): Promise<boolean> {
  return new Promise((resolve) => {
    const a = new Audio(url);
    let finished = false;
    const started = Date.now();
    const done = (played: boolean) => {
      if (finished) return;
      finished = true;
      window.clearInterval(tick);
      a.pause();
      URL.revokeObjectURL(url);
      resolve(played);
    };
    a.onended = () => done(true);
    a.onerror = () => done(false);
    const tick = window.setInterval(() => {
      const elapsed = Date.now() - started;
      if (!gen() || (a.currentTime === 0 && elapsed > 10000) || elapsed > 120000) done(false);
    }, 100);
    if (!gen()) { done(false); return; }
    void a.play().catch(() => done(false));
  });
}

/** One-off playback for Office Hours (docs/PRODUCT.md §5a): fetch and play a whole reply, no beat stepping. */
let activeAudio: HTMLAudioElement | null = null;
let activeResolve: (() => void) | null = null;

export async function speak(text: string): Promise<void> {
  const url = await fetchBeat(text);
  if (!url) return;
  await new Promise<void>((resolve) => {
    const a = new Audio(url);
    activeAudio = a;
    activeResolve = resolve;
    const done = () => {
      if (activeAudio === a) {
        activeAudio = null;
        activeResolve = null;
      }
      URL.revokeObjectURL(url);
      resolve();
    };
    a.onended = done;
    a.onerror = done;
    void a.play().catch(done);
  });
}

/** A crude stand-in for barge-in (docs/PRODUCT.md §5a): not interrupting by talking over the agent, just an
 * immediate "stop" a click can reach — halts playback now and resolves whatever `speak()` call is waiting. */
export function stopSpeaking(): void {
  const resolve = activeResolve;
  const audio = activeAudio;
  activeAudio = null;
  activeResolve = null;
  audio?.pause();
  resolve?.();
}

export function isSpeaking(): boolean {
  return activeAudio !== null;
}

/** The tutor voice for restudy: sentence-sized beats from /api/tts, one prefetched ahead, cancellable. */
export function useTutor(supported: boolean): Tutor {
  const [enabled, setEnabledState] = useState<boolean>(() => {
    try {
      return localStorage.getItem("reflow.voice") !== "0";
    } catch {
      return true;
    }
  });
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [beat, setBeat] = useState(-1);
  const gen = useRef(0);

  const setEnabled = useCallback((on: boolean) => {
    setEnabledState(on);
    try {
      localStorage.setItem("reflow.voice", on ? "1" : "0");
    } catch {
      // ignore
    }
    if (!on) {
      gen.current += 1;
      setSpeaking(false);
      setBeat(-1);
    }
  }, []);

  const stop = useCallback(() => {
    gen.current += 1;
    setSpeaking(false);
    setBeat(-1);
  }, []);

  const play = useCallback(
    async (beats: Beat[], onBeat?: (i: number, b: Beat) => void) => {
      if (!supported || !beats.length) return;
      const my = ++gen.current;
      const alive = () => gen.current === my;
      setSpeaking(true);
      setError(null);
      let next: Promise<string | null> = fetchBeat(beats[0].text);
      for (let i = 0; i < beats.length; i++) {
        const url = await next;
        if (!alive()) { if (url) URL.revokeObjectURL(url); break; }
        if (i + 1 < beats.length) next = fetchBeat(beats[i + 1].text);
        setBeat(i);
        onBeat?.(i, beats[i]);
        let played = false;
        if (url) played = await playUrl(url, alive);
        else await new Promise((r) => window.setTimeout(r, 1200)); // no audio for this beat: keep the pace
        if (!played && alive()) setError("Voice could not play. Retry the reading, or continue with the text.");
        if (!alive() || !played) {
          if (i + 1 < beats.length) { const unused = await next; if (unused) URL.revokeObjectURL(unused); }
          break;
        }
      }
      if (alive()) {
        setSpeaking(false);
        setBeat(-1);
      }
    },
    [supported],
  );

  useEffect(() => () => void (gen.current += 1), []);
  return { supported, enabled: supported && enabled, setEnabled, speaking, error, beat, play, stop };
}
