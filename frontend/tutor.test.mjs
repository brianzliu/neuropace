import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(readFileSync(new URL("./src/lib/tutor.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function player(mode = "playing") {
  let audio, tick, now = 0, paused = false, revoked = false;
  const context = {
    exports: {}, require: () => ({}),
    Date: { now: () => now },
    window: { setInterval: fn => { tick = fn; return 1; }, clearInterval() {} },
    URL: { revokeObjectURL: () => { revoked = true; } },
    Audio: class {
      currentTime = 0;
      constructor() { audio = this; }
      play() { return mode === "blocked" ? Promise.reject(new Error("NotAllowedError")) : Promise.resolve(); }
      pause() { paused = true; }
    },
  };
  vm.runInNewContext(source, context);
  return {
    play: context.exports.playUrl,
    end: () => audio.onended(),
    advance: value => { now = value; tick(); },
    cleaned: () => paused && revoked,
  };
}

test("tutor audio finishes and releases its resources", async () => {
  const p = player();
  const result = p.play("blob:beat", () => true);
  p.end();
  assert.equal(await result, true);
  assert.ok(p.cleaned());
});

test("blocked playback reports failure instead of pretending to read", async () => {
  const p = player("blocked");
  assert.equal(await p.play("blob:beat", () => true), false);
  assert.ok(p.cleaned());
});

test("stalled playback is bounded and cancellable", async () => {
  const p = player();
  const result = p.play("blob:beat", () => true);
  p.advance(10001);
  assert.equal(await result, false);
  assert.ok(p.cleaned());
  const cancelled = player();
  assert.equal(await cancelled.play("blob:beat", () => false), false);
  assert.ok(cancelled.cleaned());
});
