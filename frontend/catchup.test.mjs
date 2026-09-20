import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";

const require = createRequire(import.meta.url);
function load(path, overrides = {}, cache = new Map()) {
  const url = new URL(path, import.meta.url);
  if (cache.has(url.href)) return cache.get(url.href);
  const context = {
    exports: {},
    require(name) {
      if (name in overrides) return overrides[name];
      if (name.endsWith(".css")) return {};
      if (!name.startsWith(".")) return require(name);
      const resolved = new URL(name, url);
      let extension = ".ts";
      try { readFileSync(new URL(resolved.href + extension)); }
      catch { extension = ".tsx"; }
      return load(resolved.href + extension, overrides, cache);
    },
    ...overrides.globals,
  };
  const source = ts.transpileModule(readFileSync(url, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  vm.runInNewContext(source, context);
  cache.set(url.href, context.exports);
  return context.exports;
}

const session = load("./src/lib/sessionState.ts");
const recap = (flag_id = "first", extra = {}) => ({
  type: "catchup", flag_id, rich: true, auto_show: true, reason: "tap", t: 30,
  form: "words", line: "The lecture recap stays readable.", now_text: "The next topic.",
  forms: { words: "The lecture recap stays readable." }, source: "transcript", ttl_s: 6,
  recap_window: [10, 30], ...extra,
});
const explanation = (flag_id = "first", extra = {}) => ({
  type: "catchup_explanation", flag_id, status: "ready", source: "llm",
  options: [
    { form: "visual", artifact: "diagram", content: {
      title: "Generated relationship", nodes: [{ id: "one", label: "Lecture concept" }], edges: [],
      steps: [{ highlight: ["one"], caption: "First insight" }, { highlight: ["one"], caption: "Second insight" }],
    } },
    { form: "doing", artifact: "steps", content: { title: "Try the idea", steps: ["First action", "Second action"] } },
  ], ...extra,
});
const hello = (catchup_explanations, id = "live") => ({
  type: "hello", session: { id }, words: [], flags: [], recaps: [], focus: [],
  totem: null, headset: null, notices: [], best_form: "words", catchup_explanations,
});

const overlay = load("./src/components/CatchupOverlay.tsx").default;
const props = card => ({ card, onExpire() {}, onDismiss() {}, cycleToken: 0, onRetry() {} });
const markup = p => renderToStaticMarkup(createElement(overlay, p));

test("explanations are flag-scoped and late results cannot replace the current recap", () => {
  let state = session.reduce(session.initialState, recap());
  state = session.reduce(state, recap("second"));
  const card = state.catchup;
  state = session.reduce(state, explanation());
  assert.equal(state.catchup, card);
  assert.equal(state.catchupExplanations.first.status, "ready");
  assert.equal(state.catchupExplanations.second, undefined);
  state = session.clearCatchup(state);
  state = session.reduce(state, explanation("second"));
  assert.equal(state.catchup, null);
  assert.equal(state.catchupExplanations.second.status, "ready");
});

test("hello hydrates saved explanations without reopening dismissed cards", () => {
  let state = session.reduce(session.initialState, hello([explanation()]));
  assert.equal(state.catchupExplanations.first.status, "ready");
  assert.equal(state.catchup, null);
  state = session.reduce(state, recap());
  const card = state.catchup;
  state = session.reduce(state, hello([explanation()]));
  assert.equal(state.catchup, card);
  state = session.reduce(state, hello([], "another-session"));
  assert.equal(state.catchup, null);
  assert.equal(Object.keys(state.catchupExplanations).length, 0);
});

test("rich catch-up shows the recap and pending status in an explicit-close dialog", () => {
  const html = markup(props(recap()));
  assert.match(html, /role="dialog"/);
  assert.match(html, /The lecture recap stays readable/);
  assert.match(html, /Preparing/);
  assert.match(html, /Back to lecture/);
  assert.doesNotMatch(html, /hud fading/);
});

test("ready cards use generated visual content and only offer available formats", () => {
  const html = markup({ ...props(recap()), explanation: explanation() });
  assert.match(html, /Generated relationship/);
  assert.match(html, /Lecture concept/);
  assert.match(html, /role="tabpanel"/);
  assert.match(html, /First insight/);
  assert.match(html, /Next step/);
  const formats = html.match(/class="live-catchup-tabs"[\s\S]*?<\/div>/)?.[0] ?? "";
  assert.equal((formats.match(/role="tab"/g) ?? []).length, 2);
  assert.doesNotMatch(html, /Preparing|Retry explanation|by comparison/);
});

test("old-flag explanations and absent visual options never produce a made-up picture", () => {
  const stale = markup({ ...props(recap("second")), explanation: explanation() });
  assert.match(stale, /Preparing/);
  assert.doesNotMatch(stale, /Generated relationship|First insight/);
  const textOnly = markup({ ...props(recap()), explanation: explanation("first", { options: [
    { form: "words", artifact: "words", content: { summary: "Grounded text only", key_idea: { term: "Idea", definition: "Definition", example: "Example" } } },
  ] }) });
  assert.match(textOnly, /Grounded text only/);
  assert.equal((textOnly.match(/role="tab"/g) ?? []).length, 1);
  assert.doesNotMatch(textOnly, /<svg|<iframe|Next step|as a picture/);
});

test("generation failure and empty results keep the recap usable and offer retry", () => {
  for (const result of [explanation("first", { status: "failed", error: "Provider unavailable" }), explanation("first", { options: [] })]) {
    const html = markup({ ...props(recap()), explanation: result });
    assert.match(html, /The lecture recap stays readable/);
    assert.match(html, /role="alert"/);
    assert.match(html, /Retry explanation/);
    assert.doesNotMatch(html, /role="tabpanel"|Preparing/);
    if (result.error) assert.match(html, /Provider unavailable/);
  }
});

test("animations retain the existing scripts-only artifact sandbox", () => {
  const AnimationOverlay = load("./src/components/CatchupOverlay.tsx", { globals: {
    document: { documentElement: {} }, getComputedStyle: () => ({ getPropertyValue: () => "#123456" }),
  } }).default;
  const html = renderToStaticMarkup(createElement(AnimationOverlay, {
    ...props(recap()), explanation: explanation("first", { options: [{ form: "visual", artifact: "animation", content: {
      title: "Generated motion", caption: "Lecture-specific motion", html: "<svg></svg><script>window.frame = 1</script>",
    } }] }),
  }));
  assert.match(html, /sandbox="allow-scripts"/);
  assert.match(html, /Content-Security-Policy/);
  assert.match(html, /Generated motion/);
  assert.doesNotMatch(html, /allow-same-origin|<script>/);
});

test("EEG recaps stay behind their chip and telemetry continues with a rich panel open", () => {
  let state = session.reduce(session.initialState, recap("eeg", { auto_show: false, reason: "eeg" }));
  state = session.reduce(state, { type: "chip", flag_id: "eeg", t: 30 });
  assert.equal(state.catchup, null);
  assert.equal(Object.keys(state.catchupExplanations).length, 0);
  state = session.openChip(state, "eeg");
  assert.equal(state.catchup.flag_id, "eeg");
  assert.equal(state.catchup.rich, true);
  assert.equal(state.chipIds.length, 0);
  const card = state.catchup;
  state = session.reduce(state, { type: "catchup_explanation", flag_id: "eeg", status: "pending" });
  state = session.reduce(state, { type: "words", words: [{ w: "still recording", start: 31, end: 32 }], final: true, t: 32 });
  state = session.reduce(state, { type: "focus", t: 33, bands: { theta: 1, alpha: 2, beta: 3 } });
  state = session.reduce(state, explanation("eeg"));
  assert.equal(state.catchup, card);
  assert.equal(state.words[0].w, "still recording");
  assert.equal(state.focus.length, 1);
  assert.equal(state.catchupExplanations.eeg.status, "ready");
});

function hooks() {
  const slots = [], effects = [], cleanups = [];
  let cursor = 0;
  return {
    react: {
      useId: () => "catchup-test",
      useRef(initial) {
        const index = cursor++;
        return slots[index] ??= { current: initial };
      },
      useState(initial) {
        const index = cursor++;
        if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
        return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }];
      },
      useEffect(effect, deps) {
        const index = cursor++;
        if (!slots[index] || deps.some((value, i) => !Object.is(value, slots[index][i]))) {
          slots[index] = deps;
          effects.push(() => { cleanups[index]?.(); cleanups[index] = effect(); });
        }
      },
      useMemo: fn => fn(),
      useCallback: fn => fn,
    },
    render(fn) {
      cursor = 0;
      const result = fn();
      effects.splice(0).forEach(effect => effect());
      return result;
    },
    cleanup: () => cleanups.forEach(cleanup => cleanup?.()),
  };
}

function nodes(node) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(nodes);
  return [node, ...nodes(node.props?.children)];
}
const button = (tree, text) => nodes(tree).find(node => node.type === "button" && node.props.children === text);
const artifact = tree => nodes(tree).find(node => node.props?.kind && "step" in node.props);

function liveHarness(request) {
  const h = hooks();
  let receive;
  const sent = [], requests = [];
  const initial = session.reduce(session.reduce(session.initialState, {
    ...hello([explanation("first", { status: "failed" })]), mode: "live", transcript_kind: "scripted", sim: {},
  }), recap());
  const Component = load("./src/views/Live.tsx", {
    react: h.react,
    "react-router-dom": { useParams: () => ({ sessionId: "live" }), useNavigate: () => () => { throw new Error("Unexpected navigation"); }, useBlocker: () => ({ state: "unblocked" }) },
    "../lib/sessionState": { ...session, initialState: initial },
    "../lib/api": { api: { catchupExplanation: (id, flag) => { requests.push([id, flag]); return request(id, flag); } }, errorText: error => error.message },
    "../lib/ws": { SessionSocket: class {
      constructor(_id, onMessage) { receive = onMessage; }
      connect() {}
      close() {}
      send(message) { sent.push(message); return true; }
    } },
    "../lib/backend": { backendFetch: () => { throw new Error("Unexpected capture change"); } },
    "../lib/audio": { startMicStream: () => { throw new Error("Unexpected audio startup"); } },
    "../lib/flash": { flash() {} },
    "../lib/storage": { readLocalSetting: () => null, writeLocalSetting() {} },
    "../components/LiveCapture": { default: "live-capture" },
    "../components/PersonalCalibration": { default: "calibration" },
    "../components/StudioChrome": { ConnectionPills: "connection-pills" },
    "../components/LiveStage": { default: "live-stage" },
    "../components/SessionPlayer": { default: "session-player" },
    globals: { URLSearchParams, window: { location: { search: "" }, addEventListener() {}, removeEventListener() {} } },
  }).default;
  return {
    requests, sent, emit: message => receive(message),
    render: () => nodes(h.render(Component)).find(node => node.type === "live-stage").props,
    cleanup: h.cleanup,
  };
}

test("Live retry merges API and websocket results without navigation or audio startup", async () => {
  let resolve;
  const live = liveHarness(() => new Promise(done => { resolve = done; }));
  let stage = live.render();
  const waiting = stage.onCatchupRetry("first");
  stage = live.render();
  assert.equal(stage.state.catchupExplanations.first.status, "pending");
  await stage.onCatchupRetry("first");
  assert.deepEqual(live.requests, [["live", "first"]]);
  live.emit(explanation());
  resolve({ flag_id: "first", status: "pending" });
  await waiting;
  stage = live.render();
  assert.equal(stage.state.catchupExplanations.first.status, "ready");
  assert.equal(stage.state.catchup.flag_id, "first");
  stage.onCatchupExpire();
  assert.equal(live.render().state.catchup.flag_id, "first");
  live.cleanup();
});

test("Live retry returns provider failures to the card and ignores another flag's response", async () => {
  for (const request of [() => Promise.reject(new Error("Provider unavailable")), () => Promise.resolve(explanation("wrong"))]) {
    const live = liveHarness(request);
    const stage = live.render();
    await stage.onCatchupRetry("first");
    const state = live.render().state;
    assert.equal(state.catchupExplanations.first.status, "failed");
    assert.ok(state.catchupExplanations.first.error);
    assert.equal(state.catchupExplanations.wrong, undefined);
    assert.equal(state.catchup.line, recap().line);
    live.cleanup();
  }
});

test("Live waits for the EEG chip to be opened before requesting its explanation", () => {
  const live = liveHarness(() => { throw new Error("Unexpected eager generation"); });
  live.render();
  live.emit(recap("eeg", { auto_show: false, reason: "eeg" }));
  live.emit({ type: "chip", flag_id: "eeg", t: 30 });
  let stage = live.render();
  assert.equal(live.requests.length, 0);
  assert.equal(live.sent.length, 0);
  assert.equal(stage.state.catchup.flag_id, "first");
  stage.onOpenChip();
  stage = live.render();
  assert.equal(live.sent[0].type, "open_catchup");
  assert.equal(live.sent[0].flag_id, "eeg");
  assert.equal(stage.state.catchup.flag_id, "eeg");
  live.emit(explanation("eeg"));
  assert.equal(live.render().state.catchupExplanations.eeg.status, "ready");
  live.cleanup();
});

test("Live stores a late API result without reopening a closed card", async () => {
  let resolve;
  const live = liveHarness(() => new Promise(done => { resolve = done; }));
  const stage = live.render();
  const waiting = stage.onCatchupRetry("first");
  stage.onCatchupDismiss();
  resolve(explanation());
  await waiting;
  const state = live.render().state;
  assert.equal(state.catchup, null);
  assert.equal(state.catchupExplanations.first.status, "ready");
  assert.equal(live.sent[0].type, "dismiss_catchup");
  live.cleanup();
});

function panelHarness(initialProps) {
  const h = hooks();
  const timers = new Map();
  let timerId = 0;
  const globals = {
    window: { setTimeout: (fn, ms) => { timers.set(++timerId, { fn, ms }); return timerId; }, clearTimeout: id => timers.delete(id) },
    document: { activeElement: null, getElementById: () => null }, HTMLElement: class {},
  };
  const Component = load("./src/components/CatchupOverlay.tsx", { react: h.react, globals }).default;
  return {
    timers,
    render(p = initialProps) {
      const child = Component(p);
      return h.render(() => child.type(child.props));
    },
    cleanup: h.cleanup,
  };
}

test("rich cards never schedule expiry or click-dismiss while loading, failed, or stepping", () => {
  let dismissed = 0, expired = 0;
  const p = { ...props(recap()), onDismiss: () => dismissed++, onExpire: () => expired++ };
  const panel = panelHarness(p);
  for (const result of [undefined, explanation("first", { status: "pending" }), explanation("first", { status: "failed" }), explanation()]) {
    const tree = panel.render({ ...p, explanation: result });
    assert.equal(tree.props.onClick, undefined);
    assert.equal(panel.timers.size, 0);
  }
  const ready = { ...p, explanation: explanation() };
  let tree = panel.render(ready);
  assert.equal(artifact(tree).props.step, 0);
  button(tree, "Next step").props.onClick();
  tree = panel.render(ready);
  assert.equal(artifact(tree).props.step, 1);
  assert.equal(button(tree, "Next step").props.disabled, true);
  assert.equal(panel.timers.size, 0);
  assert.equal(dismissed + expired, 0);
  button(tree, "Back to lecture").props.onClick();
  assert.equal(dismissed, 1);
  panel.cleanup();
});

test("available-format tabs and keyboard cycling reset the reveal step without dismissing", () => {
  const p = { ...props(recap()), explanation: explanation(), cycleToken: 5 };
  const panel = panelHarness(p);
  let tree = panel.render();
  assert.equal(artifact(tree).props.kind, "diagram");
  button(tree, "Next step").props.onClick();
  tree = panel.render();
  const doingTab = nodes(tree).find(node => node.props?.role === "tab" && node.props.children === "by doing");
  doingTab.props.onClick();
  tree = panel.render();
  assert.equal(artifact(tree).props.kind, "steps");
  assert.equal(artifact(tree).props.step, 0);
  assert.equal(nodes(tree).find(node => node.props?.role === "tab" && node.props["aria-selected"]).props.children, "by doing");
  tree.props.onKeyDown({ key: "f", preventDefault() {}, stopPropagation() {} });
  tree = panel.render();
  assert.equal(artifact(tree).props.kind, "diagram");
  assert.equal(artifact(tree).props.step, 0);
  panel.cleanup();
});

test("retry targets the visible flag and Escape explicitly closes the panel", () => {
  const retries = [];
  let closed = 0;
  const panel = panelHarness({ ...props(recap()), explanation: explanation("first", { status: "failed" }),
    onRetry: id => retries.push(id), onDismiss: () => closed++,
  });
  const tree = panel.render();
  button(tree, "Retry explanation").props.onClick();
  assert.deepEqual(retries, ["first"]);
  tree.props.onKeyDown({ key: "Escape", preventDefault() {}, stopPropagation() {} });
  assert.equal(closed, 1);
  panel.cleanup();
});

test("legacy replay cards retain six-second expiry, click dismissal and paused-video freeze", () => {
  let expired = 0, dismissed = 0;
  const p = { ...props(recap("legacy", { rich: undefined })), onExpire: () => expired++, onDismiss: () => dismissed++ };
  const panel = panelHarness(p);
  const tree = panel.render();
  assert.equal(tree.props.className, "hud fading");
  assert.equal(panel.timers.size, 1);
  const timer = [...panel.timers.values()][0];
  assert.equal(timer.ms, 6000);
  timer.fn();
  tree.props.onClick();
  assert.equal(expired, 1);
  assert.equal(dismissed, 1);
  panel.cleanup();
  const frozen = panelHarness({ ...p, freeze: true });
  assert.equal(frozen.render().props.className, "hud");
  assert.equal(frozen.timers.size, 0);
  frozen.cleanup();
});
