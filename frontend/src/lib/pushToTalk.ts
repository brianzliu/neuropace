import { useEffect, useRef, useState } from "react";

/** Push-to-talk (docs/PRODUCT.md §5a): hold to record one bounded clip, release to send. Kept as a fallback
 * for browsers without continuous speech recognition, and for a noisy room where hands-free mishears. */
export function usePushToTalk(onClip: (blob: Blob) => void) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const generation = useRef(0);
  const starting = useRef(false);
  useEffect(() => () => {
    generation.current++;
    const rec = recorderRef.current;
    if (rec) { rec.onstop = null; if (rec.state !== "inactive") rec.stop(); rec.stream.getTracks().forEach(t => t.stop()); }
    recorderRef.current = null;
  }, []);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    if (recorderRef.current || starting.current) return;
    starting.current = true;
    const run = ++generation.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (run !== generation.current) { stream.getTracks().forEach(t => t.stop()); return; }
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
    } finally { starting.current = false; }
  };
  const stop = () => {
    generation.current++;
    if (recorderRef.current?.state !== "inactive") recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  };
  const cancel = () => {
    generation.current++;
    const rec = recorderRef.current;
    if (rec) { rec.onstop = null; if (rec.state !== "inactive") rec.stop(); rec.stream.getTracks().forEach(t => t.stop()); }
    recorderRef.current = null; setRecording(false);
  };
  return { recording, error, start, stop, cancel };
}
