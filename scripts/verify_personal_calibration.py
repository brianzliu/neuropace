from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    "coverage": ("MIN_VALID_SECONDS = 24", "MIN_VALID_SECONDS = 1"),
    "simulation": ('and sample.get("sim") is False', "and True"),
    "diagnostic": ('and (sample.get("mw") or {}).get("cal_phase") is None', "and True"),
    "sigma_floor": ("max(statistics.stdev(values), settings.sigma_floor)", "statistics.stdev(values)"),
}


def main() -> None:
    bootstrap = """
import inspect, sys
import pytest
import neuropace.signal.personal_calibration as module
source = inspect.getsource(module)
assert source.count(sys.argv[1]) == 1
exec(compile(source.replace(sys.argv[1], sys.argv[2]), module.__file__, 'exec'), module.__dict__)
raise SystemExit(pytest.main(['-q', 'tests/test_personal_calibration.py']))
"""
    for name, (before, after) in MUTATIONS.items():
        result = subprocess.run(
            [sys.executable, "-c", bootstrap, before, after],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 1 or " failed" not in result.stdout:
            raise SystemExit(
                f"Mutation {name} was not killed by a test failure\n{result.stdout}\n{result.stderr}"
            )
        print("KILLED", name, flush=True)
    print("PERSONAL CALIBRATION MUTATIONS PASS: 4/4; source files untouched")


if __name__ == "__main__":
    main()
