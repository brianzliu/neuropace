import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

let implementation = readFileSync(new URL("./src/lib/audio.ts", import.meta.url), "utf8");
const mutations = {
  timeout: ['timer = setTimeout(() => reject(new Error("Microphone startup timed out. Check browser permission and try again.")), timeout);', "timer = undefined;"],
  cancellation: ['signal?.addEventListener("abort", onAbort, { once: true });', ""],
  cleanup: ["media?.getTracks().forEach((t) => t.stop());", ""],
  pcm: ["v * 0x8000", "v * 0x7fff"],
  idempotence: ["if (disposed) return;", ""],
};
if (process.env.NEUROPACE_AUDIO_MUTANT) {
  const [before, after] = mutations[process.env.NEUROPACE_AUDIO_MUTANT];
  assert.ok(implementation.includes(before), "mutation must match the implementation");
  implementation = implementation.replace(before, after);
}
const source = ts.transpileModule(implementation, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness(options = {}) {
  const state = { stopped: 0, closed: 0, revoked: 0, messages: [], binary: [], disconnected: 0 };
  const media = { getTracks: () => [{ stop: () => state.stopped++ }] };
  const pending = () => new Promise(() => {});
  const context = {
    exports: {}, Float32Array, Int16Array, Blob, DOMException,
    setTimeout: (fn) => setTimeout(fn, 20), clearTimeout,
    navigator: { mediaDevices: { getUserMedia: options.getUserMedia ?? (() => Promise.resolve(media)) } },
    URL: { createObjectURL: () => "blob:test", revokeObjectURL: () => state.revoked++ },
    AudioContext: class {
      state = "running";
      sampleRate = 16000;
      audioWorklet = { addModule: () => options.hang === "module" ? pending() : options.failModule ? Promise.reject(new Error("module failed")) : Promise.resolve() };
      resume() { return options.hang === "resume" ? pending() : Promise.resolve(); }
      close() { state.closed++; this.state = "closed"; return options.hangClose ? pending() : Promise.resolve(); }
      createMediaStreamSource() { return { connect() {}, disconnect() { state.disconnected++; } }; }
    },
    AudioWorkletNode: class {
      port = { onmessage: null };
      constructor() { state.node = this; }
      disconnect() { state.disconnected++; }
    },
  };
  vm.runInNewContext(source, context);
  const socket = {
    send(message) { state.messages.push(message); return options.connected !== false; },
    sendBinary(buffer) { state.binary.push(buffer); return true; },
  };
  return { state, media, start: (signal) => context.exports.startMicStream(socket, signal) };
}

async function settles(promise) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error("startup never settled")), 250);
    })]);
  } finally { clearTimeout(timer); }
}

for (const stage of ["resume", "module"]) {
  test(`hung ${stage} rejects and releases microphone even if context close hangs`, async () => {
    const h = harness({ hang: stage, hangClose: true });
    await assert.rejects(settles(h.start()), /timed out/i);
    assert.equal(h.state.stopped, 1);
    assert.equal(h.state.closed, 1);
    assert.equal(h.state.revoked, stage === "module" ? 1 : 0);
  });
}

test("cancelled permission request releases a microphone granted after cancellation", async () => {
  let grant;
  const h = harness({ getUserMedia: () => new Promise(resolve => { grant = resolve; }) });
  const controller = new AbortController();
  const started = h.start(controller.signal);
  controller.abort();
  await assert.rejects(settles(started), { name: "AbortError" });
  grant(h.media);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.messages.length, 0);
});

test("already cancelled start never requests permission", async () => {
  let requests = 0;
  const h = harness({ getUserMedia: () => { requests++; return new Promise(() => {}); } });
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(settles(h.start(controller.signal)), { name: "AbortError" });
  assert.equal(requests, 0);
});

test("cancellation during worklet startup stops tracks and releases the blob", async () => {
  const h = harness({ hang: "module" });
  const controller = new AbortController();
  const started = h.start(controller.signal);
  await new Promise(resolve => setImmediate(resolve));
  controller.abort();
  await assert.rejects(settles(started), { name: "AbortError" });
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.revoked, 1);
  assert.equal(h.state.messages.length, 0);
});

test("working capture sends mono PCM16 and stop is idempotent", async () => {
  const h = harness();
  const mic = await h.start();
  assert.equal(mic.sampleRate, 16000);
  assert.equal(h.state.messages[0].type, "audio_start");
  h.state.node.port.onmessage({ data: new Float32Array([-2, -1, 0, 0.5, 1, 2]) });
  assert.deepEqual([...new Int16Array(h.state.binary[0])], [-32768, -32768, 0, 16383, 32767, 32767]);
  await mic.stop();
  await mic.stop();
  assert.equal(h.state.messages.filter(m => m.type === "audio_stop").length, 1);
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.closed, 1);
  assert.equal(h.state.node.port.onmessage, null);
  assert.equal(h.state.disconnected, 2);
});

test("worklet rejection cleans up before surfacing the error", async () => {
  const h = harness({ failModule: true });
  await assert.rejects(h.start(), /module failed/);
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.closed, 1);
  assert.equal(h.state.revoked, 1);
});

test("socket unavailable during start releases all capture resources", async () => {
  const h = harness({ connected: false });
  await assert.rejects(h.start(), /connection is unavailable/);
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.closed, 1);
});

test("permission timeout releases a stream that arrives late", async () => {
  let grant;
  const h = harness({ getUserMedia: () => new Promise(resolve => { grant = resolve; }) });
  await assert.rejects(settles(h.start()), /timed out/i);
  grant(h.media);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.messages.length, 0);
});

test("stopping capture does not wait forever for the browser to close its context", async () => {
  const h = harness({ hangClose: true });
  const mic = await h.start();
  await settles(mic.stop());
  assert.equal(h.state.stopped, 1);
  assert.equal(h.state.closed, 1);
});

test("PCM conversion stays bounded and monotonic across the full input range", async () => {
  const h = harness();
  const mic = await h.start();
  const samples = Float32Array.from({ length: 2049 }, (_, i) => (i - 1024) / 256);
  h.state.node.port.onmessage({ data: samples });
  const result = new Int16Array(h.state.binary[0]);
  for (let i = 0; i < samples.length; i++) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    assert.equal(result[i], Math.trunc(value * (value < 0 ? 32768 : 32767)));
    if (i > 0) assert.ok(result[i] >= result[i - 1]);
  }
  await mic.stop();
});

test("denied permission preserves the browser error and starts no stream", async () => {
  const h = harness({ getUserMedia: () => Promise.reject(new DOMException("denied", "NotAllowedError")) });
  await assert.rejects(h.start(), { name: "NotAllowedError" });
  assert.equal(h.state.messages.length, 0);
});
