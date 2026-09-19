import csv

from reflow.config import Settings
from reflow.core.study import analyze
from reflow.eval import kaggle_check, reflow_eval
from reflow.store.db import DB


def test_selftest_passes():
    assert reflow_eval.selftest() == 0


def test_kaggle_check_on_synthetic_csv(tmp_path):
    path = tmp_path / "EEG_data.csv"
    cols = [
        "SubjectID",
        "VideoID",
        "Attention",
        "Mediation",
        "Raw",
        "Delta",
        "Theta",
        "Alpha1",
        "Alpha2",
        "Beta1",
        "Beta2",
        "Gamma1",
        "Gamma2",
        "predefinedlabel",
        "user-definedlabeln",
    ]
    import random

    rng = random.Random(1)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for subj in range(5):
            for vid in range(10):
                confused = 1 if vid % 2 else 0
                for _ in range(20):
                    beta = 100 * (0.6 if confused else 1.0) * rng.uniform(0.7, 1.3)
                    theta = 100 * (1.4 if confused else 1.0) * rng.uniform(0.7, 1.3)
                    w.writerow(
                        [subj, vid, 50, 50, 0, 100, theta, 100, 100, beta, beta, 10, 10, confused, confused]
                    )
    res = kaggle_check.run(str(path))
    assert res["subject_videos"] == 50 and res["auc_user_label"] > 0.75


def _seed_session(db, s, lecture, learner, flagged_items, correct_items, policy="always", coin=None):
    sess = db.create_session(
        learner_id=learner["id"], lecture_id=lecture["id"], mode="live", catchup_policy=policy, seed=1
    )
    quiz = {q["id"]: q for q in lecture["quiz"]}
    for i, iid in enumerate(flagged_items):
        q = quiz[iid]
        db.upsert_flag(
            {
                "id": f"flag_{sess['id']}_{i}",
                "session_id": sess["id"],
                "source": "key",
                "t_trigger": q["t_end"] - 1,
                "t_start": q["t_start"],
                "t_end": q["t_end"],
                "catchup_shown": (coin[i] if coin else True),
                "catchup_form": "plain",
            }
        )
    db.add_focus_samples(
        sess["id"],
        [
            {
                "t": float(t),
                "z": (
                    -2.0 if any(quiz[i]["t_start"] <= t <= quiz[i]["t_end"] for i in flagged_items) else 0.0
                ),
                "quality": "good",
                "state": "ok",
                "artifact": False,
                "blink": False,
                "paused": False,
            }
            for t in range(int(lecture["duration"]))
        ],
    )
    db.set_quiz_answers(
        sess["id"], "before", [{"item_id": iid, "choice": 0, "correct": iid in correct_items} for iid in quiz]
    )
    db.update_session(sess["id"], status="ended")
    return sess


def test_study_analysis_four_numbers_on_synthetic_sessions(tmp_path):
    s = Settings(data_dir=tmp_path)
    db = DB(s.db_path)
    from reflow.api.app import ensure_demo_lecture

    ensure_demo_lecture(db)
    lec = db.get_lecture("lec_demo0001")
    seg3 = [q["id"] for q in lec["quiz"] if q["segment"] == "seg3"]
    others = [q["id"] for q in lec["quiz"] if q["segment"] != "seg3"]
    for k in range(6):
        lr = db.create_learner(f"p{k}")
        # flagged (segment 3) items are missed, the rest are correct: a 100-point gap
        _seed_session(
            db,
            s,
            lec,
            lr,
            flagged_items=seg3,
            correct_items=set(others),
            policy="randomized",
            coin=[True, False, True],
        )
    res = analyze(db, s, "lec_demo0001")
    n1 = res["flagged_vs_unflagged_before_review"]
    # quiz spans overlap across segment borders, so a few unflagged-segment items count as flagged; the gap stays large
    assert n1["n"] == 6 and 0.6 <= n1["mean_diff"] <= 1.0 and n1["p_perm"] < 0.1
    assert all(pp["flagged"] < pp["unflagged"] for pp in n1["per_participant"])
    assert (
        res["lossmap"]["ready"]
        and res["lossmap"]["planted_segment"] == "seg3"
        and res["lossmap"]["planted_rank"] == 1
    )
    assert (
        "mean_diff" in res["catchup"]["benefit_on_missed_span"]
        or "note" in res["catchup"]["benefit_on_missed_span"]
    )
    assert set(res["rescues_per_form"]["pooled"]) == {"words", "analogy", "visual", "doing"}
