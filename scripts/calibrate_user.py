from __future__ import annotations

import argparse
import json
import time
from collections import deque
from pathlib import Path

import httpx
from websockets.sync.client import connect


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure a focused 30-second personal baseline without changing the EEG algorithm"
    )
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--learner-id", help="Defaults to the device learner")
    parser.add_argument(
        "--apply", action="store_true", help="Save only after the complete window passes quality checks"
    )
    args = parser.parse_args()
    base = args.base.rstrip("/")
    directory = Path("data/verification") / ("personal-calibration-" + time.strftime("%Y%m%d-%H%M%S"))
    print("Keep your eyes open and attend to the same kind of material you will use the app for.")
    print("Do not close your eyes, daydream, or deliberately move to influence the score.")
    print(
        "The measurement is 30 seconds after a clean-signal preflight; detection thresholds stay unchanged.",
        flush=True,
    )
    with httpx.Client(base_url=base, timeout=90) as client:
        response = client.post(
            "/api/sessions",
            json={
                "mode": "review",
                "headset": "auto",
                "totem": "keyboard",
                "baseline_seconds": 3600,
                "use_stored_baseline": False,
                **({"learner_id": args.learner_id} if args.learner_id else {}),
            },
        )
        response.raise_for_status()
        session = response.json()
        sid = session["id"]
        try:
            if session["headset"]["kind"] != "real":
                raise RuntimeError("Real headset required; no calibration was saved")
            with connect(base.replace("http", "ws", 1) + "/ws/session/" + sid) as ws:
                recent = deque(maxlen=10)
                raw_at = 0.0
                deadline = time.monotonic() + 120
                print("Waiting for clean contact. Stay focused.", flush=True)
                while time.monotonic() < deadline:
                    message = json.loads(ws.recv(timeout=5))
                    if message["type"] == "raw":
                        raw_at = time.monotonic()
                    elif message["type"] == "focus":
                        recent.append(
                            message.get("quality") == "good"
                            and not message.get("artifact", True)
                            and not (message.get("mw") or {}).get("cal_phase")
                        )
                    if len(recent) == 10 and sum(recent) >= 8 and time.monotonic() - raw_at < 2:
                        break
                else:
                    raise RuntimeError("Clean-contact preflight failed; previous calibration is unchanged")
                response = client.post(f"/api/sessions/{sid}/personal-calibration/start")
                response.raise_for_status()
                window = response.json()
                end = window["t_start"] + window["duration_seconds"]
                deadline = time.monotonic() + 40
                last_count = None
                print("Measuring now. Keep attending for the full 30 seconds.", flush=True)
                while time.monotonic() < deadline:
                    message = json.loads(ws.recv(timeout=5))
                    if message["type"] != "focus":
                        continue
                    remaining = max(0, int(end - message["t"] + 0.999))
                    if remaining % 5 == 0 and remaining != last_count:
                        print(f"{remaining} seconds remaining", flush=True)
                        last_count = remaining
                    if message["t"] >= end:
                        break
                else:
                    raise RuntimeError("Measurement timed out; previous calibration is unchanged")
            response = client.post(
                f"/api/sessions/{sid}/personal-calibration/finish", json={"apply": args.apply}
            )
            if not response.is_success:
                raise RuntimeError(response.json().get("detail", "Calibration failed"))
            result = response.json()
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "result.json").write_text(
                json.dumps({"session_id": sid, **result}, indent=2, allow_nan=False)
            )
            print(json.dumps(result, indent=2), flush=True)
            print("Saved." if result["saved"] else "Preview only. No learner baseline was changed.")
            if result["saved"]:
                print(
                    "New sessions use this personal baseline by default; use_stored_baseline=false requests a fresh baseline."
                )
        finally:
            ended = client.post(f"/api/sessions/{sid}/end")
            ended.raise_for_status()


if __name__ == "__main__":
    main()
