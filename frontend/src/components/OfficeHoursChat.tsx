import { useEffect, useRef, useState } from "react";
import { api, errorText } from "../lib/api";
import { speak } from "../lib/tutor";
import type { OHMessage } from "../lib/types";

/** Push-to-talk (docs/PRODUCT.md §5a): hold to record one bounded clip, release to send. No streaming, no
 * barge-in — releasing the button ends the clip and it goes through the same turn path as typed text. */
function usePushToTalk(onClip: (blob: Blob) => void) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    if (recorderRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported(t));
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        if (blob.size > 0) onClip(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setError(null);
      setRecording(true);
    } catch {
      setError("Microphone unavailable; type your question instead.");
    }
  };
  const stop = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  };
  return { recording, error, start, stop };
}

export default function OfficeHoursChat({
  sessionId,
  messages,
  voiceOn,
  disabled,
  onSent,
}: {
  sessionId: string;
  messages: OHMessage[];
  voiceOn: boolean;
  disabled: boolean;
  onSent: () => void;
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  const afterReply = (replyText: string) => {
    onSent();
    if (voiceOn) void speak(replyText);
  };

  const send = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed || sending) return;
    setSending(true);
    setErr(null);
    setText("");
    try {
      const reply = await api.officeHoursSend(sessionId, trimmed);
      afterReply(reply.text);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setSending(false);
    }
  };

  const ptt = usePushToTalk(async (blob) => {
    setSending(true);
    setErr(null);
    try {
      const { reply } = await api.officeHoursVoice(sessionId, blob);
      afterReply(reply.text);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setSending(false);
    }
  });

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
      </div>
      {err ? <div className="callout danger label-3">{err}</div> : null}
      {ptt.error ? <div className="label-3">{ptt.error}</div> : null}
      {disabled ? <div className="label-3">Looking back — return to now to keep talking.</div> : null}
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
        <button className="btn btn-sm btn-primary" type="submit" disabled={locked || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
