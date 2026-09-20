"""Seed the demo state on a running server (docs/DEMO-PLAN.md, preconditions step 3).

Runs real practice sessions over the API with the simulated headset (labelled practice on screen), so nothing is
written into the database by hand:

  1. The device learner ("you") takes four practice lectures with four catch-ups each and is tutored on them,
     answering right only after a picture: twelve or more scored explanations, pictures preferred.
  2. Two named learners take the practice lecture in recorded mode, drift in the planted segment 3 and press the
     button there: with the device learner's own session that makes the loss map ready (n >= 3) and ranks segment 3.
  3. One more device-learner session is ended with its notes generated and left unreviewed: the backup for the
     tutoring beat if generation is slow on the venue network.

    NEUROPACE_BASELINE_SECONDS=30 uv run neuropace serve
    uv run python scripts/demo_seed.py --base http://127.0.0.1:8765 --db data/neuropace.db

About six minutes, real model calls (a few cents). Safe to re-run: it adds sessions, it never deletes.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from e2e_cases import GPS, Check, Ctx, run_review  # noqa: E402


async def practice_with_taps(ctx: Ctx, learner_id: str, seed: int, taps: int = 4):
    s = await ctx.start("", GPS, seed=seed, learner_id=learner_id)
    async with s:
        await s.wait_baseline()
        for i in range(taps):
            await s.tap()
            if i < taps - 1:
                await asyncio.sleep(21)
        await asyncio.sleep(2)
    return s, await s.end()


async def recorded_in_segment_3(ctx: Ctx, name: str, seed: int):
    s = await ctx.start(name, GPS, mode="recorded", seed=seed, extra={"auto_pause": True})
    async with s:
        await s.send({"type": "media_time", "t": 0.0, "playing": True})
        await s.wait_baseline()
        await s.send({"type": "media_time", "t": 140.0, "playing": True})
        await asyncio.sleep(3)
        c = s.cursor()
        await s.sim("drifting")
        fl = await s.expect("flag_open", lambda m: m["flag"]["source"] == "eeg", timeout=70, since=c)
        await s.send({"type": "media_time", "t": fl["t"] + 1.0, "playing": True})
        await asyncio.sleep(12)
        await s.sim("focused")
        await s.tap()
        await asyncio.sleep(2)
        now = s.msgs[-1].get("t", 180.0)
        await s.send({"type": "media_time", "t": max(now, 216.0) + 4.0, "playing": True})
        await asyncio.sleep(25)
    return s, await s.end()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument(
        "--db", required=True, help="the server's SQLite file, read only (to answer the checks on purpose)"
    )
    ap.add_argument("--baseline", type=float, default=20.0, help="baseline seconds for the seeded sessions")
    ap.add_argument("--case-timeout", type=float, default=900.0)
    args = ap.parse_args()
    ctx = Ctx(args)
    chk = Check("SEED")
    me = await ctx.get("/api/learners/me")
    print(f"device learner {me['id']} ({me['name']})", flush=True)
    t0 = time.monotonic()
    runs = await asyncio.gather(*(practice_with_taps(ctx, me["id"], 300 + i) for i in range(4)))
    for s, end in runs:
        print(
            f"  {s.id}: {len(end['gaps'])} moments, notes {[g['package_source'] for g in end['gaps']]}",
            flush=True,
        )
        await run_review(ctx, chk, s.id, "tutor", lambda card, fb: fb == "visual")
    tally = await ctx.get(f"/api/learners/{me['id']}/tally")
    print(
        f"tally: {tally['total_attempts']} scored, preferred={tally['preferred']}, rank={tally['rank']}",
        flush=True,
    )
    others = await asyncio.gather(
        recorded_in_segment_3(ctx, "Demo learner B", 401), recorded_in_segment_3(ctx, "Demo learner C", 402)
    )
    for s, end in others:
        print(f"  {s.id}: recorded, {len(end['gaps'])} moments", flush=True)
    lm = await ctx.get(f"/api/lectures/{GPS}/lossmap")
    print(
        f"loss map: ready={lm.get('ready')} n={lm.get('n')} ranking={lm.get('ranking')} peak={lm.get('peak')}",
        flush=True,
    )
    backup_s, backup_end = await practice_with_taps(ctx, me["id"], 500, taps=2)
    print(
        f"backup session for the tutoring beat: {backup_s.id} ({len(backup_end['gaps'])} moments, notes {[g['package_source'] for g in backup_end['gaps']]})",
        flush=True,
    )
    print(
        f"seeded in {time.monotonic() - t0:.0f}s. Open /lecture/{backup_s.id} for the backup, /you for the preference, /insights for the loss map."
    )
    await ctx.http.aclose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
