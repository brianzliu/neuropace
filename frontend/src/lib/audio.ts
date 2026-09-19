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

/** Captures the microphone and streams PCM16 frames over the session socket (Deepgram live mode). */
export async function startMicStream(socket: SessionSocket): Promise<MicStream> {
  const media = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const ctx = new AudioContext({ sampleRate: 16000 });
  await ctx.resume();
  const url = URL.createObjectURL(new Blob([WORKLET_SRC], { type: "application/javascript" }));
  await ctx.audioWorklet.addModule(url);
  URL.revokeObjectURL(url);
  const src = ctx.createMediaStreamSource(media);
  const node = new AudioWorkletNode(ctx, "pcm-capture", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1 });
  socket.send({ type: "audio_start", sample_rate: ctx.sampleRate });
  node.port.onmessage = (ev: MessageEvent<Float32Array>) => {
    socket.sendBinary(floatToInt16(ev.data));
  };
  src.connect(node);
  return {
    sampleRate: ctx.sampleRate,
    stop: async () => {
      socket.send({ type: "audio_stop" });
      node.port.onmessage = null;
      src.disconnect();
      node.disconnect();
      media.getTracks().forEach((t) => t.stop());
      await ctx.close();
    },
  };
}
