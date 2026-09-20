import type { SessionSocket } from "./ws";

// Inline AudioWorklet: batches 128-frame blocks into ~100 ms mono Float32 chunks.
const WORKLET_SRC = `
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(Math.round(sampleRate / 10));
    this.n = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.buf[this.n++] = ch[i];
      if (this.n >= this.buf.length) {
        this.port.postMessage(this.buf.slice(0, this.n));
        this.n = 0;
      }
    }
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
`;

export interface MicStream {
  sampleRate: number;
  stop: () => Promise<void>;
}

function floatToInt16(f: Float32Array): ArrayBuffer {
  const out = new Int16Array(f.length);
  for (let i = 0; i < f.length; i++) {
    const v = Math.max(-1, Math.min(1, f[i]));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out.buffer;
}

async function waitForAudio<T>(operation: Promise<T>, signal?: AbortSignal, timeout = 10000): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let onAbort: (() => void) | undefined;
  try {
    return await Promise.race([
      operation,
      new Promise<never>((_, reject) => {
        onAbort = () => reject(new DOMException("Microphone startup cancelled", "AbortError"));
        if (signal?.aborted) { onAbort(); return; }
        signal?.addEventListener("abort", onAbort, { once: true });
        timer = setTimeout(() => reject(new Error("Microphone startup timed out. Check browser permission and try again.")), timeout);
      }),
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
    if (onAbort) signal?.removeEventListener("abort", onAbort);
  }
}

/** Captures the microphone and streams PCM16 frames over the session socket (Deepgram live mode). */
export async function startMicStream(socket: SessionSocket, signal?: AbortSignal): Promise<MicStream> {
  signal?.throwIfAborted();
  let media: MediaStream | null = null;
  let ctx: AudioContext | null = null;
  let url: string | null = null;
  let disposed = false;
  const release = () => {
    disposed = true;
    if (url) { URL.revokeObjectURL(url); url = null; }
    media?.getTracks().forEach((t) => t.stop());
    if (ctx && ctx.state !== "closed") void ctx.close().catch(() => {});
  };
  try {
    const stream = await waitForAudio(navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    }).then((stream) => {
      if (disposed) stream.getTracks().forEach((t) => t.stop());
      else media = stream;
      return stream;
    }), signal, 30000);
    signal?.throwIfAborted();
    ctx = new AudioContext({ sampleRate: 16000 });
    await waitForAudio(ctx.resume(), signal);
    signal?.throwIfAborted();
    url = URL.createObjectURL(new Blob([WORKLET_SRC], { type: "application/javascript" }));
    await waitForAudio(ctx.audioWorklet.addModule(url), signal);
    signal?.throwIfAborted();
    URL.revokeObjectURL(url);
    url = null;
    const src = ctx.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(ctx, "pcm-capture", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1 });
    if (!socket.send({ type: "audio_start", sample_rate: ctx.sampleRate })) {
      throw new Error("The lecture connection is unavailable. Reconnect and try again.");
    }
    node.port.onmessage = (ev: MessageEvent<Float32Array>) => {
      socket.sendBinary(floatToInt16(ev.data));
    };
    src.connect(node);
    return {
      sampleRate: ctx.sampleRate,
      stop: async () => {
        if (disposed) return;
        socket.send({ type: "audio_stop" });
        node.port.onmessage = null;
        src.disconnect();
        node.disconnect();
        release();
      },
    };
  } catch (error) {
    release();
    throw error;
  }
}
