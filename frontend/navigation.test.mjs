import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = ts.transpileModule(readFileSync(new URL("./src/components/dashboard/NewSessionButton.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

test("dashboard starts a session through the current router, never a popup", () => {
  const visits = [];
  const context = {
    exports: {},
    window: { open() { throw new Error("Unexpected popup"); } },
    require(name) {
      if (name === "react-router-dom") return { useNavigate: () => path => visits.push(path) };
      if (name === "react/jsx-runtime") return { jsx: (tag, props) => ({ tag, props }), jsxs: (tag, props) => ({ tag, props }) };
      throw new Error(name);
    },
  };
  vm.runInNewContext(source, context);
  context.exports.default().props.onClick();
  assert.deepEqual(visits, ["/session/new"]);
});
