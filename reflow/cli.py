"""Command line (TDD §11)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from .config import load_settings


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    s = load_settings()
    host = args.host or s.host
    port = args.port or s.port
    print(f"NeuroPace on http://{host}:{port}  (data: {s.data_dir.resolve()})")
    if args.reload:
        uvicorn.run(
            "reflow.api.app:create_app", factory=True, host=host, port=port, reload=True, log_level="info"
        )
    else:
        from .api.app import create_app
        from .keys import start_key_listener

        app = create_app(s)
        print(f"Hosted UI pairing code: {app.state.pairing_token}", flush=True)
        print(f"Allowed websites: {', '.join(s.ui_origins)}", flush=True)

        def _on_loop(fn):
            loop = getattr(app.state, "loop", None)
            if loop is not None:
                loop.call_soon_threadsafe(fn)

        stop = start_key_listener(lambda: _on_loop(app.state.tap_all), lambda: _on_loop(app.state.force_all))
        if stop is not None:
            print(
                "terminal keys: SPACE or T = lost me (keyboard totem), L = force an EEG-style flag (simulated)"
            )
        try:
            uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
        finally:
            if stop is not None:
                stop.set()

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from .doctor import run_doctor

    s = load_settings()
    res = asyncio.run(run_doctor(s))
    print(json.dumps(res, indent=2))
    ok = res["frontend_built"]
    print()
    print(
        "keys        :",
        "deepgram" if res["keys"]["deepgram"] else "no DEEPGRAM_API_KEY",
        "|",
        "openai" if res["keys"]["openai"] else "no OPENAI_API_KEY",
        "|",
        "openrouter" if res["keys"]["openrouter"] else "no OPENROUTER_API_KEY",
    )
    print(
        "deepgram    :", "ok" if res["deepgram"].get("ok") else res["deepgram"].get("reason", res["deepgram"])
    )
    oa = res["openai"]
    print(
        "openai model:",
        oa.get("model"),
        "ok" if oa.get("ok") else ("REQUIRED, " if oa.get("required") else "") + str(oa.get("reason", "")),
    )
    router = res["openrouter"]
    print(
        "router model:",
        router.get("model"),
        "ok" if router.get("ok") else str(router.get("reason", "")),
        "(active)" if res["llm_provider"] == "openrouter" else "",
    )
    if res["openai"].get("alternatives"):
        print("   available:", ", ".join(res["openai"]["alternatives"]))
    print("headset     :", res["headset"]["kind"], res["headset"]["port"] or "(none found -> simulated)")
    print("totem       :", res["totem"]["kind"], res["totem"]["port"] or "(none found -> keyboard fallback)")
    print("frontend    :", "built" if ok else "NOT built: cd frontend && pnpm install && pnpm build")
    return 0


def cmd_ingest_script(args: argparse.Namespace) -> int:
    from .store.db import DB
    from .transcribe.scripted import load_script

    s = load_settings()
    s.ensure_dirs()
    db = DB(s.db_path)
    data = load_script(args.script)
    lec = db.create_lecture(
        title=args.title or data.get("title", Path(args.script).stem),
        kind="scripted",
        words=data["words"],
        segments=data.get("segments"),
        quiz=data.get("quiz"),
        keyterms=data.get("keyterms"),
        duration=data.get("duration"),
        lecture_id=data.get("id") if args.keep_id else None,
    )
    print(lec["id"], lec["title"], f"{lec['word_count']} words")
    return 0


def cmd_ingest_lecture(args: argparse.Namespace) -> int:
    from .store.db import DB
    from .transcribe.deepgram_prerecorded import transcribe_file

    s = load_settings()
    if not s.deepgram_api_key:
        print("DEEPGRAM_API_KEY is required for media ingestion", file=sys.stderr)
        return 2
    s.ensure_dirs()
    db = DB(s.db_path)
    extra = json.loads(Path(args.meta).read_text()) if args.meta else {}
    words = asyncio.run(
        transcribe_file(args.file, s.deepgram_api_key, s.deepgram_model, extra.get("keyterms"))
    )
    lec = db.create_lecture(
        title=args.title,
        kind="media",
        words=[w.to_dict() for w in words],
        segments=extra.get("segments"),
        quiz=extra.get("quiz"),
        keyterms=extra.get("keyterms"),
        media_path=str(Path(args.file).resolve()),
    )
    print(lec["id"], lec["title"], f"{lec['word_count']} words, {lec['duration']:.0f} s")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    s = load_settings()
    path = s.sessions_dir / f"{args.session_id}.jsonl"
    if not path.exists():
        print(f"no event log at {path}", file=sys.stderr)
        return 2
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    t0 = None
    start = time.monotonic()
    for ev in events:
        if ev.get("type") in ("focus",) and not args.verbose:
            continue
        t = ev.get("t", 0.0)
        if t0 is None:
            t0 = t
        target = (t - t0) / args.speed
        delay = target - (time.monotonic() - start)
        if delay > 0 and args.speed > 0:
            time.sleep(min(delay, 5.0))
        summary = {k: v for k, v in ev.items() if k not in ("wall",)}
        print(json.dumps(summary, ensure_ascii=False)[: args.width])
    return 0


def cmd_study_analyze(args: argparse.Namespace) -> int:
    from .core.study import analyze
    from .store.db import DB

    s = load_settings()
    db = DB(s.db_path)
    res = analyze(db, s, args.lecture)
    print(json.dumps(res, indent=2))
    n1 = res["flagged_vs_unflagged_before_review"]
    print()
    print(f"Sessions analysed: {res['sessions']}")
    if "mean_diff" in n1:
        print(
            f"1. Flagged vs unflagged recall (before review): n={n1['n']}, unflagged minus flagged = {n1['mean_diff']:+.3f}, 95% CI {n1['ci95']}, p={n1['p_perm']}"
        )
    else:
        print("1. Flagged vs unflagged recall:", n1.get("note"))
    lm = res["lossmap"]
    print(
        f"2. Loss map: ready={lm['ready']} n={lm['n']} planted={lm['planted_segment']} rank={lm['planted_rank']} ranking={lm['ranking']}"
    )
    print(
        "3. Catch-up benefit:",
        res["catchup"]["benefit_on_missed_span"],
        "| cost:",
        res["catchup"]["cost_on_next_20s"],
    )
    print("4. Rescues per form (pooled):", res["rescues_per_form"]["pooled"])
    return 0


def cmd_sim(args: argparse.Namespace) -> int:
    if args.which == "selftest":
        from .eval.reflow_eval import selftest

        return selftest()
    if args.which == "bandit":
        from .eval import bandit_sim

        p = [0.75, 0.55, 0.55, 0.55]
        print("P(pick best variant) | mean success rate   [uniform random play = 0.25 | 0.60]")
        for n in (12, 24, 60, 150):
            print(
                f"cards={n:4d}",
                {
                    sg: tuple(round(v, 2) for v in bandit_sim.run(p, n, sg, sims=args.sims))
                    for sg in ("quiz", "eeg", "both")
                },
            )
        return 0
    if args.which == "lossmap":
        from .eval import lossmap_sim

        print("P(planted-bad segment ranked #1, top-2) of 5 segments; chance = 0.20, 0.40")
        for dp, label in ((0.545, "AUC .65 sensor"), (1.0, "AUC .76 fused (ASSUMPTION)")):
            print(label)
            for N in (6, 10, 12, 20):
                print(
                    f"  N={N:3d}  q=0.6:{lossmap_sim.sim(N, S=5, dprime=dp, sims=args.sims)}  q=0.9:{lossmap_sim.sim(N, S=5, q=0.9, dprime=dp, sims=args.sims)}"
                )
        return 0
    return 2


def cmd_kaggle(args: argparse.Namespace) -> int:
    from .eval.kaggle_check import main as kmain

    return kmain([args.path])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="neuropace", description="NeuroPace: catch-ups, gap notes and adaptive review for lectures."
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("serve", help="start the API and the built frontend")
    sp.add_argument("--host")
    sp.add_argument("--port", type=int)
    sp.add_argument("--reload", action="store_true")
    sp.set_defaults(fn=cmd_serve)
    sp = sub.add_parser("doctor", help="check keys, services, ports, frontend build")
    sp.set_defaults(fn=cmd_doctor)
    sp = sub.add_parser("ingest-script", help="add a scripted lecture from a JSON file (words or text)")
    sp.add_argument("script")
    sp.add_argument("--title")
    sp.add_argument("--keep-id", action="store_true")
    sp.set_defaults(fn=cmd_ingest_script)
    sp = sub.add_parser(
        "ingest-lecture", help="transcribe a media file with Deepgram and add it as a lecture"
    )
    sp.add_argument("--title", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--meta", help="JSON with segments/quiz/keyterms")
    sp.set_defaults(fn=cmd_ingest_lecture)
    sp = sub.add_parser("replay", help="print a session's event log at speed")
    sp.add_argument("session_id")
    sp.add_argument("--speed", type=float, default=4.0)
    sp.add_argument("--verbose", action="store_true", help="include focus samples")
    sp.add_argument("--width", type=int, default=200)
    sp.set_defaults(fn=cmd_replay)
    sp = sub.add_parser("study-analyze", help="the four study numbers for a lecture")
    sp.add_argument("--lecture", required=True)
    sp.set_defaults(fn=cmd_study_analyze)
    sp = sub.add_parser("sim", help="run the spec's simulations")
    sp.add_argument("which", choices=["selftest", "bandit", "lossmap"])
    sp.add_argument("--sims", type=int, default=1000)
    sp.set_defaults(fn=cmd_sim)
    sp = sub.add_parser("kaggle-check", help="hour-0 feature check on the Wang et al. EEG confusion CSV")
    sp.add_argument("path")
    sp.set_defaults(fn=cmd_kaggle)
    args = p.parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
