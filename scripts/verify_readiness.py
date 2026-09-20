from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Optional running verification server for the live-provider smoke")
    args = parser.parse_args()
    commands = [
        (ROOT, ["uv", "run", "pytest", "-q"]),
        (ROOT, ["uv", "run", "ruff", "check", "neuropace", "tests", "scripts"]),
        (ROOT, ["uv", "run", "ruff", "format", "--check", "neuropace", "tests", "scripts"]),
        (ROOT / "frontend", ["pnpm", "test"]),
        (ROOT / "frontend", ["node", "audio.mutations.mjs"]),
        (ROOT, ["uv", "run", "python", "scripts/verify_personal_calibration.py"]),
        (ROOT / "frontend", ["pnpm", "build"]),
        (ROOT, ["uv", "run", "neuropace", "sim", "selftest"]),
        (ROOT, ["uv", "build", "--wheel"]),
        (
            ROOT,
            [
                "uv",
                "run",
                "python",
                "scripts/verify_distribution.py",
                "dist/neuropace-0.1.0-py3-none-any.whl",
            ],
        ),
        (ROOT, ["git", "diff", "--check"]),
    ]
    if args.base:
        commands.append((ROOT, ["uv", "run", "python", "scripts/smoke_e2e.py", "--base", args.base]))
    failures = []
    for cwd, command in commands:
        print("RUN", " ".join(command), flush=True)
        try:
            subprocess.run(command, cwd=cwd, check=True, timeout=180)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            failures.append(" ".join(command))
            print("FAILED", error, flush=True)
    if failures:
        raise SystemExit("READINESS FAILED: " + "; ".join(failures))
    print("READINESS CHECKS PASS (browser and physical-device checks are separate)")


if __name__ == "__main__":
    main()
