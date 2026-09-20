import sqlite3

from neuropace.config import FOCUS_METRIC, FORMS
from neuropace.store.db import DB


def test_legacy_baselines_migrate_without_assigning_metric(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_rows = [
        ("legacy_auto", "Automatic", 1.0, -0.8, 0.2, 2.0, "automatic"),
        ("legacy_personal", "Personal", 3.0, -0.6, 0.1, 4.0, "personal"),
    ]
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE learners(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL, "
            "baseline_mu REAL, baseline_sigma REAL, baseline_at REAL, baseline_source TEXT)"
        )
        conn.executemany("INSERT INTO learners VALUES(?,?,?,?,?,?,?)", legacy_rows)

    for _ in range(2):
        db = DB(path)
        try:
            for row in legacy_rows:
                learner = db.get_learner(row[0])
                assert learner == dict(
                    zip(
                        (
                            "id",
                            "name",
                            "created_at",
                            "baseline_mu",
                            "baseline_sigma",
                            "baseline_at",
                            "baseline_source",
                            "baseline_metric",
                        ),
                        (*row, None),
                        strict=True,
                    )
                )
        finally:
            db.close()


def test_new_baseline_save_stamps_current_metric(db):
    learner = db.create_learner("Synthetic listener")
    assert learner["baseline_metric"] is None

    db.set_learner_baseline(learner["id"], 0.8, 0.15)

    saved = db.get_learner(learner["id"])
    assert saved["baseline_mu"] == 0.8
    assert saved["baseline_sigma"] == 0.15
    assert saved["baseline_at"] is not None
    assert saved["baseline_source"] == "automatic"
    assert saved["baseline_metric"] == FOCUS_METRIC
    reader = DB(db.path)
    try:
        assert reader.get_learner(learner["id"]) == saved
    finally:
        reader.close()


def test_baseline_cas_preserves_newer_metadata_and_reset_clears_metric(db, monkeypatch):
    learner = db.create_learner("Synthetic calibration")
    other = db.create_learner("Synthetic other listener")
    db.set_learner_baseline(other["id"], 1.0, 0.2)
    other_saved = db.get_learner(other["id"])
    session = db.create_session(learner_id=learner["id"], mode="review")
    db.tally_add(learner["id"], FORMS[0], True)

    monkeypatch.setattr("neuropace.store.db.time.time", lambda: 100.0)
    assert db.compare_and_set_learner_baseline(learner["id"], 0.8, 0.15, None)
    initial = db.get_learner(learner["id"])
    assert initial["baseline_source"] == "personal"
    assert initial["baseline_metric"] == FOCUS_METRIC
    assert initial["baseline_at"] == 100.0

    monkeypatch.setattr("neuropace.store.db.time.time", lambda: 200.0)
    db.set_learner_baseline(learner["id"], 1.2, 0.3, metric="future_metric")
    newer = db.get_learner(learner["id"])
    assert newer["baseline_metric"] == "future_metric"
    assert newer["baseline_at"] == 200.0
    assert not db.compare_and_set_learner_baseline(learner["id"], 9.0, 9.0, initial["baseline_at"])
    assert not db.compare_and_set_learner_baseline(learner["id"], 9.0, 9.0, None)
    assert db.get_learner(learner["id"]) == newer

    assert db.compare_and_set_learner_baseline(learner["id"], 0.9, 0.2, newer["baseline_at"])
    personal = db.get_learner(learner["id"])
    assert personal["baseline_mu"] == 0.9
    assert personal["baseline_sigma"] == 0.2
    assert personal["baseline_source"] == "personal"
    assert personal["baseline_metric"] == FOCUS_METRIC

    db.reset_profile(learner["id"])
    assert db.get_learner(learner["id"]) == learner
    assert db.get_learner(other["id"]) == other_saved
    assert db.get_session(session["id"]) == session
    assert db.get_tally(learner["id"])[FORMS[0]] == {"rescues": 0, "attempts": 0}
