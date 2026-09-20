"""Local-only synthetic workspace used to preview a populated NeuroPace dashboard."""

from __future__ import annotations

import json
import time

from .config import Settings
from .llm.fallback import gap_package
from .store.db import DB
from .transcribe.scripted import script_from_text


class DemoData:
    def __init__(self, settings: Settings) -> None:
        self.state_path = settings.data_dir / "demo-mode.json"
        self.db_path = settings.data_dir / "neuropace-demo.db"
        self.enabled = self._read_enabled()
        self._db: DB | None = None

    def _read_enabled(self) -> bool:
        try:
            return json.loads(self.state_path.read_text()).get("enabled") is True
        except (OSError, ValueError, AttributeError):
            return False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.state_path.write_text(json.dumps({"enabled": enabled}, indent=2) + "\n")

    def database(self) -> DB:
        if self._db is None:
            self._db = DB(self.db_path)
            seed_demo_database(self._db)
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None


LECTURES = [
    (
        "lec_demo_cells",
        "How cells turn food into energy",
        "Cells capture energy from glucose through cellular respiration. Glycolysis begins in the cytoplasm "
        "and splits glucose into pyruvate. The citric acid cycle then transfers energy to electron carriers. "
        "Along the inner mitochondrial membrane, the electron transport chain builds a proton gradient. "
        "ATP synthase uses that gradient like a tiny turbine to produce ATP for the cell.",
        "proton gradient",
    ),
    (
        "lec_demo_stats",
        "Confidence intervals without the mystery",
        "A confidence interval combines a sample estimate with a margin of error. The standard error describes "
        "how much an estimate would vary across repeated samples. Larger samples usually reduce standard error. "
        "A ninety five percent procedure captures the true parameter in about ninety five percent of repeated "
        "samples. It does not mean there is a ninety five percent probability that this fixed interval is correct.",
        "standard error",
    ),
    (
        "lec_demo_orbits",
        "Why satellites stay in orbit",
        "An orbit is continuous free fall. Gravity pulls the satellite toward Earth while its sideways velocity "
        "carries it forward. The surface curves away at nearly the same rate that the satellite falls. A higher "
        "orbit has a longer path and a slower orbital speed. Changing velocity changes the shape and altitude of "
        "the orbit rather than switching gravity off.",
        "continuous free fall",
    ),
]


def _quiz(term: str) -> list[dict]:
    return [{
        "id": f"q_{term.replace(' ', '_')}",
        "question": f"Which idea best describes {term}?",
        "options": [
            f"The lecture's explanation of {term}",
            "A deadline mentioned before class",
            "An unrelated historical date",
            "A measurement with no context",
        ],
        "correct_index": 0,
        "segment": None,
    }]


def seed_demo_database(db: DB) -> None:
    if db.get_lecture(LECTURES[0][0]):
        return
    learner = db.default_learner()
    now = time.time()
    db.set_curriculum(learner["id"], {
        "title": "Foundations of science and data",
        "topics": [
            {"title": "Cellular respiration", "completed": True},
            {"title": "Statistical inference", "completed": False},
            {"title": "Orbital mechanics", "completed": False},
            {"title": "Scientific communication", "completed": False},
        ],
    })
    for index, (lecture_id, title, text, term) in enumerate(LECTURES):
        words = [word.to_dict() for word in script_from_text(text, wpm=145)]
        duration = words[-1]["end"] if words else 0
        db.create_lecture(
            title=title,
            kind="scripted",
            words=words,
            segments=[{
                "id": "seg1",
                "title": title,
                "t_start": 0,
                "t_end": duration,
                "planted_bad": False,
            }],
            quiz=_quiz(term),
            keyterms=[term],
            duration=duration,
            lecture_id=lecture_id,
        )
        session_id = f"sess_demo_{index + 1}"
        session = db.create_session(
            id=session_id,
            learner_id=learner["id"],
            lecture_id=lecture_id,
            mode="live",
            headset_kind="simulated",
            totem_kind="keyboard",
            transcript_kind="scripted",
            best_form=("visual", "analogy", "doing")[index],
            seed=100 + index,
        )
        started = now - index * 86400 - 3600
        db.update_session(session["id"], status="ended", started_at=started, ended_at=started + duration)
        db.add_words(session["id"], words, 0)
        db.add_focus_samples(session["id"], [
            {"t": second, "e": 0.55, "x": 0.45, "z": -0.2, "w15": -0.1,
             "quality": "good", "state": "steady", "artifact": False, "blink": False, "paused": False}
            for second in range(1, max(2, int(duration)), 4)
        ])
        span = text.split(". ")[min(2, len(text.split(". ")) - 1)] + "."
        package = gap_package(span, text.split(". ")[0] + ".", text, seed=index)
        gaps = [{
            "id": f"gap_demo_{index + 1}",
            "ord": 0,
            "t_start": round(duration * 0.45, 2),
            "t_end": round(duration * 0.68, 2),
            "span_text": span,
            "context_text": text,
            "flag_ids": [f"flag_demo_{index + 1}"],
            "package": package,
            "package_source": "demo",
            "status": "closed" if index == 2 else "open",
        }]
        db.replace_gaps(session["id"], gaps)
    for form, outcomes in {"words": (1, 3), "analogy": (3, 4), "visual": (4, 5), "doing": (2, 3)}.items():
        rescues, attempts = outcomes
        for attempt in range(attempts):
            db.tally_add(learner["id"], form, attempt < rescues)
