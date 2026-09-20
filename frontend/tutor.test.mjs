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

test("an ended event after cancellation is not natural completion", async () => {
  const p = player();
  let active = true;
  const result = p.play("blob:beat", () => active);
  active = false;
  p.end();
  assert.equal(await result, false);
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

const settle = () => new Promise(resolve => setImmediate(resolve));

function hooks() {
  const slots = [];
  let index, effects, component, value, dirty;
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const memo = (fn, deps) => {
    const i = index++;
    if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
    return slots[i].value;
  };
  const react = {
    useState(initial) {
      const i = index++;
      slots[i] ??= { state: typeof initial === "function" ? initial() : initial };
      return [slots[i].state, next => {
        const result = typeof next === "function" ? next(slots[i].state) : next;
        if (!Object.is(slots[i].state, result)) { slots[i].state = result; dirty = true; }
      }];
    },
    useRef: initial => memo(() => ({ current: initial }), []),
    useMemo: memo,
    useCallback: (fn, deps) => memo(() => fn, deps),
    useEffect(fn, deps) {
      const i = index++;
      if (!slots[i] || !same(slots[i].deps, deps)) {
        const old = slots[i];
        slots[i] = { deps };
        effects.push(() => { old?.cleanup?.(); slots[i].cleanup = fn(); });
      }
    },
  };
  const render = (fn = component) => {
    component = fn;
    let renders = 0;
    do {
      assert.ok(++renders < 30, "render must settle");
      index = 0; effects = []; dirty = false;
      value = component();
      effects.forEach(fn => fn());
    } while (dirty);
    return value;
  };
  return { react, render, unmount: () => slots.forEach(slot => slot.cleanup?.()), replaceState(previous, next) {
    const slot = slots.find(slot => slot.state === previous);
    assert.ok(slot, "state to replace exists");
    slot.state = next;
    render();
  } };
}

function clock() {
  let now = 0, sequence = 0;
  const timers = new Map();
  const add = (fn, delay, repeat = false) => {
    const id = ++sequence;
    timers.set(id, { fn, delay, repeat, at: now + delay });
    return id;
  };
  return {
    Date: { now: () => now },
    window: {
      setTimeout: (fn, delay) => add(fn, delay), clearTimeout: id => timers.delete(id),
      setInterval: (fn, delay) => add(fn, delay, true), clearInterval: id => timers.delete(id),
    },
    advance(ms) {
      const target = now + ms;
      while (true) {
        const next = [...timers].filter(([, t]) => t.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        const [id, timer] = next;
        now = timer.at;
        if (timer.repeat) timer.at += timer.delay;
        else timers.delete(id);
        timer.fn();
      }
      now = target;
    },
    pending: () => timers.size,
  };
}

function tutorHarness(options = {}) {
  const h = hooks(), time = clock(), audio = [], revoked = [], requests = [];
  let blob = 0;
  const context = {
    exports: {}, ...time, AbortSignal,
    localStorage: { getItem: () => options.disabled ? "0" : "1", setItem() {} },
    URL: { createObjectURL: () => `blob:${++blob}`, revokeObjectURL: url => revoked.push(url) },
    require: name => name === "react" ? h.react : { backendFetch: async (_, init) => {
      requests.push(JSON.parse(init.body).text);
      if (options.fetch) return options.fetch(requests.length);
      return { ok: !options.failFetch, blob: async () => ({}) };
    } },
    Audio: class {
      currentTime = 1;
      constructor() { audio.push(this); }
      play() { return options.blocked ? Promise.reject(new Error("blocked")) : Promise.resolve(); }
      pause() { this.paused = true; }
    },
  };
  vm.runInNewContext(source, context);
  return { ...h, time, audio, revoked, requests, narration: context.exports.narrationForCard,
    tutor: () => h.render(() => context.exports.useTutor(options.supported !== false)) };
}

const beats = [{ text: "First", step: 0 }, { text: "Second", step: 1 }];

test("full narration completes only after every beat ends naturally", async () => {
  const h = tutorHarness(), revealed = [];
  let resolved = false;
  const result = h.tutor().play(beats, (_, beat) => revealed.push(beat.step)).then(value => { resolved = true; return value; });
  await settle();
  assert.deepEqual(revealed, [0]);
  h.audio[0].onended();
  await settle();
  assert.equal(resolved, false);
  assert.deepEqual(revealed, [0, 1]);
  h.audio[1].onended();
  assert.equal(await result, true);
  assert.equal(h.tutor().speaking, false);
  assert.equal(h.tutor().beat, -1);
  assert.equal(h.revoked.length, 2);
  assert.equal(h.time.pending(), 0);
});

for (const cancel of ["stop", "disable", "unmount"]) {
  test(`${cancel} cancels a full narration and cleans prefetched audio`, async () => {
    const h = tutorHarness(), tutor = h.tutor();
    const result = tutor.play(beats);
    await settle();
    if (cancel === "unmount") h.unmount();
    else if (cancel === "disable") tutor.setEnabled(false);
    else tutor.stop();
    h.audio[0].onended();
    assert.equal(await result, false);
    await settle();
    assert.equal(h.revoked.length, 2);
    assert.equal(h.audio.length, 1);
    assert.equal(h.time.pending(), 0);
  });
}

for (const options of [{ blocked: true }, { failFetch: true }]) {
  test(`full narration returns false on ${options.blocked ? "playback" : "TTS"} failure`, async () => {
    const h = tutorHarness(options);
    const result = h.tutor().play(beats);
    await settle();
    h.time.advance(1200);
    assert.equal(await result, false);
    assert.match(h.tutor().error, /could not play/);
    assert.equal(h.tutor().speaking, false);
    assert.equal(h.time.pending(), 0);
  });
}

test("a later failed beat makes the whole narration incomplete", async () => {
  const h = tutorHarness({ fetch: async index => ({ ok: index === 1, blob: async () => ({}) }) });
  const result = h.tutor().play(beats);
  await settle();
  h.audio[0].onended();
  await settle();
  h.time.advance(1200);
  assert.equal(await result, false);
  assert.equal(h.audio.length, 1);
  assert.equal(h.revoked.length, 1);
});

test("empty narration is not a successful reading", async () => {
  const h = tutorHarness();
  assert.equal(await h.tutor().play([]), false);
  assert.equal(h.requests.length, 0);
});

for (const options of [{ disabled: true }, { supported: false }]) {
  test(`unavailable narration does not start (${JSON.stringify(options)})`, async () => {
    const h = tutorHarness(options);
    assert.equal(await h.tutor().play(beats), false);
    assert.equal(h.requests.length, 0);
  });
}

test("cancellation releases audio fetched after stopping", async () => {
  let respond;
  const h = tutorHarness({ fetch: () => new Promise(resolve => { respond = resolve; }) });
  const tutor = h.tutor(), result = tutor.play(beats);
  tutor.stop();
  respond({ ok: true, blob: async () => ({}) });
  assert.equal(await result, false);
  assert.equal(h.revoked.length, 1);
  assert.equal(h.audio.length, 0);
});

test("a replacement narration cancels the old one without stopping the new one", async () => {
  const h = tutorHarness(), tutor = h.tutor();
  const old = tutor.play(beats);
  await settle();
  const fresh = tutor.play([beats[1]]);
  await settle();
  h.audio[0].onended();
  assert.equal(await old, false);
  assert.equal(h.tutor().speaking, true);
  h.audio[1].onended();
  assert.equal(await fresh, true);
  assert.equal(h.revoked.length, 3);
});

test("plan reason replaces the generic intro without repeating identical context", () => {
  const h = tutorHarness();
  const narration = h.narration({ reteach: { plan_reason: "Show the flow.", why: "Generic intro.", context: "Show the flow.", artifact: "animation", content: { title: "Flow", caption: "Follow it." } } });
  assert.deepEqual(Array.from(narration, beat => beat.text), ["Show the flow.", "Flow", "Follow it."]);
});

const restudySource = ts.transpileModule(readFileSync(new URL("./src/views/Restudy.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== "object") return [];
  return [tree, ...nodes(tree.props?.children)];
}

function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join("");
  if (tree && typeof tree === "object") return text(tree.props?.children);
  return tree == null || typeof tree === "boolean" ? "" : String(tree);
}

async function restudyHarness(options = {}) {
  const h = hooks(), time = clock(), calls = [], advances = [], keys = new Map();
  const route = { mode: options.mode ?? "tutor", sessionId: "session" };
  const card = { id: "card", kind: "reteach", reteach: { form: "visual", artifact: options.artifact ?? "animation", content: {}, why: "Generic intro.", plan_reason: "Watch the flow.", ...options.reteach } };
  const question = { id: "check", kind: "question", question: { question: "Which way?", options: ["Left", "Right"] } };
  const progress = { gaps_total: 1, gaps_closed: 0, gaps_exhausted: 0, streak: 0, stop_streak: 3 };
  let enabled = !options.disabled, active;
  const tutor = {
    supported: true, enabled, speaking: false, error: null,
    stop() { tutor.speaking = false; active = undefined; },
    setEnabled(on) { enabled = on; tutor.enabled = on; },
    play(beats, onBeat) {
      tutor.speaking = true; tutor.error = null;
      active = calls.length;
      return new Promise(resolve => calls.push({ beats, onBeat, resolve }));
    },
  };
  const focus = { driftSeq: 0, startCard() {}, endCard: () => ({}) };
  const context = {
    exports: {}, Date: time.Date,
    window: { ...time.window, addEventListener: (name, fn) => keys.set(name, fn), removeEventListener: name => keys.delete(name) },
    require(name) {
      if (name === "react") return h.react;
      if (name === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
      if (name === "react-router-dom") return { useParams: () => ({ sessionId: route.sessionId }), useSearchParams: () => [{ get: () => route.mode }], Link: "a" };
      if (name === "./Library") return { useLibrary: () => false };
      if (name === "../lib/focusSession") return { useFocusSession: () => focus };
      if (name === "../lib/tutor") return {
        narrationForCard: () => beats,
        useTutor: supported => { tutor.supported = supported; tutor.enabled = supported && enabled; return tutor; },
      };
      if (name === "../lib/types") return { FORM_ICON: { visual: "" }, FORM_LABEL: { visual: "Visual" }, ARTIFACT_LABEL: { animation: "Animation", diagram: "Diagram", words: "Words" } };
      if (name === "../components/ArtifactView") return { default: "ArtifactView" };
      if (name === "../lib/flash") return { flash() {} };
      if (name === "../lib/api") return { errorText: String, api: {
        health: async () => ({ voice: !options.unsupported }),
        session: async () => ({ id: route.sessionId, learner_id: "learner" }),
        reviewStart: async () => ({ card, progress, tally: {} }),
        reviewAdvance: async (...args) => { advances.push(args); return options.advance ? options.advance() : { next: question, progress, tally: {} }; },
        reviewDrop: async () => ({ next: { ...card, id: "replacement" }, progress, tally: {} }),
        reviewAnswer: async () => ({ outcome: "miss", correct_index: 1, explanation: "Try the flow.", next: card, progress, tally: {} }),
      } };
      return {};
    },
  };
  vm.runInNewContext(restudySource, context);
  const render = () => h.render(() => context.exports.default());
  render();
  await settle();
  render();
  return { ...h, render, time, calls, advances, tutor, card, route, question,
    button(label) {
      const button = nodes(render()).find(node => node.type === "button" && text(node).startsWith(label));
      assert.ok(button, `button exists: ${label}`);
      button.props.onClick();
      render();
    },
    artifact: () => nodes(render()).find(node => node.type === "ArtifactView"),
    key(key, tagName = "DIV") { keys.get("keydown")({ key, target: { tagName }, preventDefault() {} }); render(); },
    async finish(completed = true, index = calls.length - 1) {
      if (active === index) { tutor.speaking = false; if (!completed) tutor.error = "Voice could not play."; }
      calls[index].resolve(completed);
      await settle();
      render();
    },
  };
}

test("Restudy reveals beats, then waits eight seconds before the animation check", async () => {
  const h = await restudyHarness();
  assert.equal(h.calls.length, 1);
  h.calls[0].onBeat(1, beats[1]);
  assert.equal(h.artifact().props.step, 1);
  h.time.advance(1000);
  await h.finish();
  assert.match(text(h.render()), /A quick check is next/);
  h.time.advance(6999);
  assert.equal(h.advances.length, 0);
  h.time.advance(1);
  await settle();
  assert.equal(h.advances.length, 1);
  assert.deepEqual(h.advances[0].slice(0, 2), ["session", "card"]);
  h.time.advance(20000);
  assert.equal(h.advances.length, 1);
});

test("diagrams remain readable for three seconds after successful narration", async () => {
  const h = await restudyHarness({ artifact: "diagram" });
  h.time.advance(20000);
  await h.finish();
  h.time.advance(2999);
  assert.equal(h.advances.length, 0);
  h.time.advance(1);
  assert.equal(h.advances.length, 1);
});

for (const action of ["Pause tutor", "Skip the reading", "voice", "keyboard skip", "unmount", "replace", "mode", "session"]) {
  test(`${action} prevents stale narration completion from auto-advancing`, async () => {
    const h = await restudyHarness();
    const initialStep = h.artifact().props.step;
    if (action === "voice") h.key("v");
    else if (action === "keyboard skip") h.key(" ");
    else if (action === "unmount") h.unmount();
    else if (action === "replace") h.replaceState(h.card, { ...h.card });
    else if (action === "mode") { h.route.mode = "manual"; h.render(); }
    else if (action === "session") { h.route.sessionId = "other"; h.render(); }
    else h.button(action);
    h.calls[0].onBeat(9, { step: 9 });
    if (action !== "unmount") assert.notEqual(h.artifact()?.props.step, 9);
    if (action === "Pause tutor") assert.equal(h.artifact().props.step, initialStep);
    h.calls[0].resolve(true);
    await settle();
    h.time.advance(20000);
    assert.equal(h.advances.length, 0);
    h.unmount();
  });
}

for (const action of ["Pause tutor", "voice", "unmount", "replace"]) {
  test(`${action} cancels the pending visual viewing delay`, async () => {
    const h = await restudyHarness();
    await h.finish();
    if (action === "voice") h.key("v");
    else if (action === "unmount") h.unmount();
    else if (action === "replace") h.replaceState(h.card, { ...h.card, id: "new" });
    else h.button(action);
    h.time.advance(20000);
    assert.equal(h.advances.length, 0);
    assert.equal(h.time.pending(), 0);
    h.unmount();
  });
}

test("failed voice never advances, but retry completion can advance", async () => {
  const h = await restudyHarness();
  await h.finish(false);
  h.time.advance(20000);
  assert.equal(h.advances.length, 0);
  h.button("Retry voice");
  assert.equal(h.calls.length, 2);
  await h.finish();
  h.time.advance(8000);
  assert.equal(h.advances.length, 1);
});

for (const options of [{ mode: "manual" }, { disabled: true }, { unsupported: true }]) {
  test(`manual recovery remains available with no automatic playback (${JSON.stringify(options)})`, async () => {
    const h = await restudyHarness(options);
    assert.equal(h.calls.length, 0);
    h.artifact().props.onSteps(2);
    h.button("Next");
    assert.equal(h.artifact().props.step, 1);
    h.time.advance(20000);
    assert.equal(h.advances.length, 0);
    h.button("Got it, ask me");
    assert.equal(h.advances.length, 1);
  });
}

test("skip preserves Got it recovery and does not submit twice", async () => {
  const h = await restudyHarness();
  h.artifact().props.onSteps(3);
  h.button("Skip the reading");
  assert.equal(h.artifact().props.step, 2);
  await h.finish();
  h.time.advance(20000);
  assert.equal(h.advances.length, 0);
  h.button("Got it, ask me");
  h.key(" ");
  assert.equal(h.advances.length, 1);
});

test("an in-flight check response cannot replace a newer card", async () => {
  let respond;
  const h = await restudyHarness({ advance: () => new Promise(resolve => { respond = resolve; }) });
  await h.finish();
  h.time.advance(8000);
  assert.equal(h.advances.length, 1);
  const replacement = { ...h.card, id: "new", reteach: { ...h.card.reteach, plan_reason: "New explanation." } };
  h.replaceState(h.card, replacement);
  respond({ next: h.question, progress: {}, tally: {} });
  await settle();
  assert.match(text(h.render()), /New explanation/);
  assert.doesNotMatch(text(h.render()), /Which way/);
  h.unmount();
});

test("drift cancels the pending check and a late transition cannot replace a newer card", async () => {
  const h = await restudyHarness();
  await h.finish();
  h.key("d");
  await settle();
  h.render();
  const replacement = { ...h.card, id: "new", reteach: { ...h.card.reteach, plan_reason: "New explanation." } };
  h.replaceState(h.card, replacement);
  h.time.advance(20000);
  assert.equal(h.advances.length, 0);
  assert.match(text(h.render()), /New explanation/);
  h.unmount();
});

test("a missed check still transitions to another explanation", async () => {
  const h = await restudyHarness();
  await h.finish();
  h.time.advance(8000);
  await settle();
  h.render();
  h.key("1");
  await settle();
  assert.match(text(h.render()), /Not yet/);
  h.time.advance(1700);
  h.render();
  h.time.advance(750);
  h.render();
  assert.equal(h.calls.length, 2);
  h.unmount();
});

test("focused buttons keep their own Space action instead of also advancing", async () => {
  const h = await restudyHarness();
  h.key(" ", "BUTTON");
  assert.equal(h.tutor.speaking, true);
  assert.equal(h.advances.length, 0);
  h.unmount();
});

test("text fallback is visible and the generic reason is not duplicated", async () => {
  const h = await restudyHarness({ artifact: "words", reteach: { visual_unavailable: true } });
  const copy = text(h.render());
  assert.match(copy, /Text fallback: the planned visual is unavailable/);
  assert.match(copy, /Watch the flow/);
  assert.doesNotMatch(copy, /Generic intro/);
  h.unmount();
});
