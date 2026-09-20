import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

for (const mutant of ["timeout", "cancellation", "cleanup", "pcm", "idempotence"]) {
  const result = spawnSync(process.execPath, ["--test", "audio.test.mjs"], {
    cwd: new URL(".", import.meta.url),
    env: { ...process.env, NEUROPACE_AUDIO_MUTANT: mutant },
    encoding: "utf8",
    timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1, `${mutant} survived\n${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /AssertionError/, `${mutant} must fail a behavioral assertion`);
  console.log(`KILLED ${mutant}`);
}
console.log("MUTATION PASS: 5/5 in-memory mutants killed; working tree untouched");
