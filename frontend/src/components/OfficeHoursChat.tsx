import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorText } from "../lib/api";
import { speak, stopSpeaking } from "../lib/tutor";
import { usePushToTalk } from "../lib/pushToTalk";
import type { OHMessage } from "../lib/types";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((ev: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: ((ev: { error: string }) => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function speechRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/** A live voice agent (docs/PRODUCT.md §5a): continuous browser speech recognition, not push-to-talk — say
 * something, it's sent the moment you pause, the reply is spoken back. Listening pauses while the agent is
 * speaking (so the mic doesn't hear its own reply) and resumes right after; there is no true barge-in
 * (interrupting the agent mid-sentence by talking over it), just hands-free turn-taking. Chrome/Edge only
 * (the Web Speech API isn't in Firefox/Safari); push-to-talk and typing remain as fallbacks everywhere. */
function useVoiceAgent(onFinal: (text: string) => void) {
  const supported = !!speechRecognitionCtor();
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const pausedRef = useRef(false);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;
  const [active, setActive] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    pausedRef.current = true;
    recRef.current?.stop();
    recRef.current = null;
    setActive(false);
    setInterim("");
  }, []);

  const start = useCallback(() => {
    const Ctor = speechRecognitionCtor();
    if (!Ctor) {
      setError("Voice agent needs Chrome or Edge; type or hold to talk instead.");
      return;
    }
    if (recRef.current) return;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.onresult = (ev) => {
      let finalText = "";
      let interimText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interimText += r[0].transcript;
      }
      setInterim(interimText);
      if (finalText.trim()) {
        setInterim("");
        onFinalRef.current(finalText.trim());
      }
    };
    rec.onerror = (ev) => {
      if (ev.error === "no-speech" || ev.error === "aborted") return;
      setError(`Mic error: ${ev.error}`);
    };
    rec.onend = () => {
      if (recRef.current === rec && !pausedRef.current) {
        try {
          rec.start();
        } catch {
          // already starting; the next onend will retry
        }
      }
    };
    try {
      rec.start();
      recRef.current = rec;
      pausedRef.current = false;
      setError(null);
      setActive(true);
    } catch {
      setError("Could not start the microphone.");
    }
  }, []);

  const pause = useCallback(() => {
    pausedRef.current = true;
    recRef.current?.stop();
  }, []);
  const resume = useCallback(() => {
    if (!recRef.current) return;
    pausedRef.current = false;
    try {
      recRef.current.start();
    } catch {
      // already listening
    }
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { supported, active, interim, error, start, stop, pause, resume };
}

export default function OfficeHoursChat({
  sessionId,
  messages,
  voiceOn,
  disabled,
  onSend,
  onVoiceClipSent,
  pendingUserText,
  pendingReplyText,
}: {
  sessionId: string;
  messages: OHMessage[];
  voiceOn: boolean;
  disabled: boolean;
  /** Sends one turn and streams the board in live; resolves with the reply text once it's known
   *  (well before the board finishes drawing) so voice playback can start right away. */
  onSend: (text: string) => Promise<string>;
  /** Push-to-talk still transcribes+replies in one non-streaming call server-side (deliberately —
   *  releasing the button ends the clip, so there's nothing to stream mid-clip); this just tells
   *  the parent to pull the resulting board/message once it lands. */
  onVoiceClipSent: () => void;
  /** The turn in flight, echoed back immediately (before the server confirms it) so the
   *  conversation never looks stalled while the board is still being drawn. */
  pendingUserText: string | null;
  pendingReplyText: string | null;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  const afterReply = async (replyText: string) => {
    if (voiceOn && replyText) {
      setSpeaking(true);
      try {
        await speak(replyText);
      } finally {
        setSpeaking(false);
      }
    }
  };

  const send = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setErr(null);
    setText("");
    try {
      const replyText = await onSend(trimmed);
      await afterReply(replyText);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setSending(false);
    }
  };

  const agent = useVoiceAgent(async (spokenText) => {
    agent.pause();
    setSending(true);
    setErr(null);
    try {
      const replyText = await onSend(spokenText);
      await afterReply(replyText);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setSending(false);
      agent.resume();
    }
  });

  const ptt = usePushToTalk(async (blob) => {
    setSending(true);
    setErr(null);
    try {
      const { reply } = await api.officeHoursVoice(sessionId, blob);
      onVoiceClipSent();
      await afterReply(reply.text);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setSending(false);
    }
  });

  useEffect(() => {
    if (disabled && agent.active) agent.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  const locked = disabled || sending;

  return (
    <div className="oh-chat">
      <div className="oh-chat-list" ref={listRef}>
        {messages.map((m) => (
          <div key={m.id} className={"oh-bubble oh-bubble-" + m.role}>
            <div className="oh-bubble-text">{m.text}</div>
            {m.source === "failed" ? <span className="badge">offline</span> : null}
          </div>
        ))}
        {pendingUserText ? (
          <div className="oh-bubble oh-bubble-user">
            <div className="oh-bubble-text">{pendingUserText}</div>
          </div>
        ) : null}
        {pendingUserText ? (
          <div className="oh-bubble oh-bubble-agent oh-bubble-pending">
            <div className="oh-bubble-text">{pendingReplyText || "Drawing it out…"}</div>
          </div>
        ) : null}
        {agent.active && agent.interim ? (
          <div className="oh-bubble oh-bubble-user oh-bubble-interim">
            <div className="oh-bubble-text">{agent.interim}…</div>
          </div>
        ) : null}
      </div>
      {err ? <div className="callout danger label-3">{err}</div> : null}
      {ptt.error ? <div className="label-3">{ptt.error}</div> : null}
      {agent.error ? <div className="label-3">{agent.error}</div> : null}
      {disabled ? <div className="label-3">Looking back. Return to now to keep talking.</div> : null}
      <div className="oh-chat-toolbar row">
        <button
          type="button"
          className={"btn btn-sm" + (agent.active ? " is-on is-recording" : "")}
          onClick={() => (agent.active ? agent.stop() : agent.start())}
          disabled={disabled || !agent.supported}
          title={agent.supported ? "Continuous listening: talk any time, no button to hold" : "Needs Chrome or Edge"}
        >
          {agent.active ? "Listening…" : "Voice agent"}
        </button>
        <button
          type="button"
          className={"btn btn-sm" + (ptt.recording ? " is-recording" : "")}
          onMouseDown={() => void ptt.start()}
          onMouseUp={ptt.stop}
          onMouseLeave={() => ptt.recording && ptt.stop()}
          onTouchStart={(e) => {
            e.preventDefault();
            void ptt.start();
          }}
          onTouchEnd={(e) => {
            e.preventDefault();
            ptt.stop();
          }}
          disabled={locked}
        >
          {ptt.recording ? "Release to send" : "Hold to talk"}
        </button>
        {speaking ? (
          <button
            type="button"
            className="btn btn-sm btn-blue"
            onClick={() => {
              stopSpeaking();
              agent.resume();
            }}
            title="Stop the tutor speaking. You cannot talk over it yet."
          >
            Stop
          </button>
        ) : null}
      </div>
      <form
        className="oh-chat-input row"
        onSubmit={(e) => {
          e.preventDefault();
          void send(text);
        }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about the lecture…"
          disabled={locked}
        />
        <button className="btn btn-sm btn-primary" type="submit" disabled={locked || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
