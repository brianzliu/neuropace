"""Study analysis (TDD §8.5, FR-S4): the four numbers of spec §6, each with its interval."""

from __future__ import annotations

from ..config import Settings
from ..eval.neuropace_eval import paired_outcome
from ..store.db import DB
from .lossmap import compute_lossmap


def _overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return a0 < b1 and b0 < a1


def _flag_span(f: dict, s: Settings) -> tuple[float, float]:
    t0 = float(f["t_start"])
    t1 = float(f["t_end"]) if f.get("t_end") is not None else float(f["t_trigger"]) + s.lead_in_seconds
    return t0, t1


def lossmap_inputs(db: DB, sessions: list[dict], s: Settings) -> list[dict]:
    out = []
    for sess in sessions:
        flags = db.get_flags(sess["id"])
        out.append(
            {
                "id": sess["id"],
                "samples": db.get_focus_samples(sess["id"]),
                "taps": [f["t_trigger"] for f in flags if f["source"] in ("tap", "key", "sim_tap")],
                "eeg_flags": [_flag_span(f, s) for f in flags if f["source"] in ("eeg", "forced")],
            }
        )
    return out


def analyze(db: DB, s: Settings, lecture_id: str) -> dict:
    lecture = db.get_lecture(lecture_id)
    if not lecture:
        raise ValueError(f"unknown lecture {lecture_id}")
    quiz = lecture.get("quiz") or []
    items = {q["id"]: q for q in quiz}
    sessions = [x for x in db.list_sessions(lecture_id=lecture_id) if x["status"] in ("ended", "reviewed")]
    # ---- 1. flagged vs unflagged recall, before review ----
    unfl, fl = [], []
    per_participant = []
    for sess in sessions:
        flags = db.get_flags(sess["id"])
        spans = [_flag_span(f, s) for f in flags]
        answers = {a["item_id"]: a for a in db.get_quiz_answers(sess["id"], "before")}
        if not answers:
            continue
        f_c, f_n, u_c, u_n = 0, 0, 0, 0
        for iid, a in answers.items():
            q = items.get(iid)
            if not q:
                continue
            flagged = any(_overlaps(q["t_start"], q["t_end"], t0, t1) for t0, t1 in spans)
            if flagged:
                f_n += 1
                f_c += int(bool(a["correct"]))
            else:
                u_n += 1
                u_c += int(bool(a["correct"]))
        if f_n and u_n:
            fl.append(f_c / f_n)
            unfl.append(u_c / u_n)
            per_participant.append(
                {
                    "session_id": sess["id"],
                    "flagged": round(f_c / f_n, 3),
                    "unflagged": round(u_c / u_n, 3),
                    "n_flagged_items": f_n,
                }
            )
    n1 = (
        paired_outcome(unfl, fl)
        if len(fl) >= 2
        else {"n": len(fl), "note": "needs 2 or more participants with both flagged and unflagged items"}
    )
    # ---- 2. loss map ranks the planted segment? ----
    lm = compute_lossmap(
        lossmap_inputs(db, sessions, s), lecture.get("duration") or 0.0, lecture.get("segments"), s
    )
    planted = [seg for seg in (lecture.get("segments") or []) if seg.get("planted_bad")]
    planted_id = planted[0]["id"] if planted else None
    planted_rank = None
    if lm.get("ready") and planted_id:
        for seg in lm["segments"]:
            if seg["id"] == planted_id:
                planted_rank = seg.get("rank")
    n2 = {
        "ready": lm.get("ready", False),
        "n": lm.get("n"),
        "planted_segment": planted_id,
        "planted_rank": planted_rank,
        "ranking": lm.get("ranking"),
        "peak": lm.get("peak"),
    }
    # ---- 3. catch-up benefit and cost (randomized policy only) ----
    ben_shown, ben_with, cost_shown, cost_with = [], [], [], []
    for sess in sessions:
        if sess.get("catchup_policy") != "randomized":
            continue
        answers = {a["item_id"]: a for a in db.get_quiz_answers(sess["id"], "before")}
        if not answers:
            continue
        acc = {"ben": {True: [], False: []}, "cost": {True: [], False: []}}
        for f in db.get_flags(sess["id"]):
            if f.get("catchup_shown") is None:
                continue
            t0, t1 = _flag_span(f, s)
            for iid, a in answers.items():
                q = items.get(iid)
                if not q:
                    continue
                if _overlaps(q["t_start"], q["t_end"], t0, t1):
                    acc["ben"][bool(f["catchup_shown"])].append(int(bool(a["correct"])))
                elif _overlaps(q["t_start"], q["t_end"], t1, t1 + 20.0):
                    acc["cost"][bool(f["catchup_shown"])].append(int(bool(a["correct"])))
        if acc["ben"][True] and acc["ben"][False]:
            ben_shown.append(sum(acc["ben"][True]) / len(acc["ben"][True]))
            ben_with.append(sum(acc["ben"][False]) / len(acc["ben"][False]))
        if acc["cost"][True] and acc["cost"][False]:
            cost_shown.append(sum(acc["cost"][True]) / len(acc["cost"][True]))
            cost_with.append(sum(acc["cost"][False]) / len(acc["cost"][False]))
    n3 = {
        "benefit_on_missed_span": paired_outcome(ben_shown, ben_with)
        if len(ben_shown) >= 2
        else {"n": len(ben_shown), "note": "needs 2+ participants with shown and withheld lapses"},
        "cost_on_next_20s": paired_outcome(cost_shown, cost_with)
        if len(cost_shown) >= 2
        else {"n": len(cost_shown), "note": "needs 2+ participants with shown and withheld lapses"},
        "note": "positive mean_diff = catch-up shown scored higher; intervals will be wide at ~5 lapses per person",
    }
    # ---- 4. rescues per form ----
    pooled = db.population_tally()
    per_learner = {}
    for sess in sessions:
        lid = sess["learner_id"]
        if lid not in per_learner:
            per_learner[lid] = db.get_tally(lid)
    n4 = {"pooled": pooled, "per_learner": per_learner, "note": "descriptive only at this n"}
    return {
        "lecture": {"id": lecture["id"], "title": lecture["title"]},
        "sessions": len(sessions),
        "flagged_vs_unflagged_before_review": {
            **n1,
            "per_participant": per_participant,
            "note": "mean_diff = unflagged minus flagged proportion correct",
        },
        "lossmap": n2,
        "catchup": n3,
        "rescues_per_form": n4,
    }
