"""End-to-end smoke against a running server (default http://127.0.0.1:8765), with a simulated headset and scripted lecture.

Creates a learner and a scripted live session, connects the WebSocket, waits for the baseline, taps, measures tap-to-catch-up
latency, forces an EEG-style flag, ends the session, walks the review, and prints the timings. Exit code 1 on any failure.

    uv run neuropace serve            # in one terminal
    uv run python scripts/smoke_e2e.py [--base http://127.0.0.1:8765] [--baseline 8]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx
from websockets.sync.client import connect


def read_until(ws, want: str, limit: int = 400, timeout: float = 20.0):
    deadline = time.time() + timeout
    for _ in range(limit):
        raw = ws.recv(timeout=max(0.1, deadline - time.time()))
        m = json.loads(raw)
        if m.get("type") == want:
            return m
    raise RuntimeError(f"no {want}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--baseline", type=float, default=8.0)
    a = ap.parse_args()
    base = a.base.rstrip("/")
    ws_base = base.replace("http", "ws", 1)
    c = httpx.Client(base_url=base, timeout=60.0)
    ok = True

    def check(cond: bool, label: str) -> None:
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + label)
        ok = ok and cond

    h = c.get("/api/health").json()
    check(h.get("ok") is True, f"health {h.get('version')}")
    d = c.get("/api/doctor").json()
    selected = c.get("/api/settings/model").json()
    print(
        f"     provider={selected['provider']} model={selected['model']} deepgram={d['keys']['deepgram']} headset={d['headset']['kind']} frontend_built={d['frontend_built']}"
    )
    lecs = c.get("/api/lectures").json()["lectures"]
    check(bool(lecs), f"lectures: {[lr['title'] for lr in lecs]}")
    lrn = c.post("/api/learners", json={"name": f"smoke-{int(time.time())}"}).json()
    r = c.post(
        "/api/sessions",
        json={
            "learner_id": lrn["id"],
            "lecture_id": lecs[0]["id"],
            "mode": "live",
            "baseline_seconds": a.baseline,
            "headset": "sim",
            "totem": "sim",
        },
    )
    check(r.status_code == 200, f"create session: {r.status_code}")
    sess = r.json()
    print(
        f"     session {sess['id']} transcript={sess['transcript_kind']} headset={sess['headset']['kind']} totem={sess['totem']['kind']} best_form={sess['best_form']}"
    )
    with connect(f"{ws_base}/ws/session/{sess['id']}", max_size=None) as ws:
        hello = json.loads(ws.recv(timeout=5))
        check(hello["type"] == "hello", "hello snapshot")
        f = read_until(ws, "focus")
        check(f["quality"] == "good", "focus samples flowing")
        print(f"     waiting {a.baseline + 2:.0f}s for baseline + words")
        t_end = time.time() + a.baseline + 2
        ready = False
        while time.time() < t_end:
            m = json.loads(ws.recv(timeout=5))
            if m["type"] == "focus" and m.get("baseline_ready"):
                ready = True
        check(ready, "baseline ready")
        t0 = time.perf_counter()
        ws.send(json.dumps({"type": "tap"}))
        cu = read_until(ws, "catchup")
        lat = time.perf_counter() - t0
        check(lat < 1.0, f"tap -> catch-up in {lat * 1000:.0f} ms (form={cu['form']}, source={cu['source']})")
        print(f"     line: {cu['line'][:100]}")
        print(f"     now : {cu['now_text'][:80]}")
        ws.send(json.dumps({"type": "sim_headset", "state": "drifting"}))
        ws.send(json.dumps({"type": "force_flag"}))
        chip = read_until(ws, "chip")
        check(chip["flag_id"].startswith("flag_"), "forced flag -> chip (no auto-show)")
        rec = read_until(ws, "recap", timeout=30)
        check(bool(rec["forms"]["words"]), f"rolling recap arrived (source={rec['source']})")
    end = c.post(f"/api/sessions/{sess['id']}/end").json()
    check(
        len(end["gaps"]) >= 1,
        f"session ended with {len(end['gaps'])} gap(s), package_source={end['gaps'][0]['package_source'] if end['gaps'] else None}",
    )
    st = c.post(f"/api/sessions/{sess['id']}/review/start").json()
    card = st["card"]
    check(card is not None and card["kind"] == "reteach", "private tutoring starts with an explanation")
    steps = 0
    while card and steps < 12:
        steps += 1
        if card["kind"] == "question":
            r = c.post(
                f"/api/sessions/{sess['id']}/review/answer", json={"card_id": card["id"], "choice": 0}
            ).json()
            print(f"     q -> {r['outcome']} (credited {r['credited_form']})")
            card = r["next"]
        else:
            r = c.post(f"/api/sessions/{sess['id']}/review/advance", json={"card_id": card["id"]}).json()
            card = r["next"]
    tally = c.get(f"/api/learners/{lrn['id']}/tally").json()
    check(
        tally["total_attempts"] >= 1,
        f"tally updated: total_attempts={tally['total_attempts']} enough_data={tally['enough_data']}",
    )
    ev = c.get(f"/api/sessions/{sess['id']}/events").json()["events"]
    check(ev and ev[-1]["type"] == "session_ended", f"event log has {len(ev)} events")
    lm = c.get(f"/api/lectures/{lecs[0]['id']}/lossmap").json()
    print(f"     lossmap ready={lm.get('ready')} n={lm.get('n')}")
    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
