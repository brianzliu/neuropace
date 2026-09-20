import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(readFileSync(new URL("./src/views/Done.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

function completionText(session) {
  let state = 0;
  const context = {
    exports: {},
    require(name) {
      if (name === "react") return { useEffect() {}, useState: () => [state++ === 0 ? session : "Lecture", () => {}] };
      if (name === "react-router-dom") return { useParams: () => ({ sessionId: "test" }), Link: "a" };
      if (name === "../components/SessionNavigation") return { sessionHref: (id, tab) => `/library/${id}/${tab}` };
      if (name === "react/jsx-runtime") return { jsx: (_, props) => props.children, jsxs: (_, props) => props.children };
      return {};
    },
  };
  vm.runInNewContext(source, context);
  return JSON.stringify(context.exports.default());
}

for (const words of [0, 42]) {
  test(`no saved moments with ${words} words does not claim the learner stayed focused`, () => {
    const text = completionText({ gaps: 0, words, flags: [], catchups_shown: 0 });
    assert.doesNotMatch(text, /You stayed with it the whole way/);
    assert.match(text, words ? /No moments were saved/ : /No transcript was captured/);
  });
}

test("saved moments lead into guided study", () => {
  const text = completionText({ gaps: 1, words: 42, flags: [], catchups_shown: 1 });
  assert.match(text, /Each moment explained your way/);
  assert.match(text, /Study this lecture/);
});
