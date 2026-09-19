"""Review state machine (TDD §8.3, FR-R1..R6). Persisted in cards/gaps; rebuilt from the DB when needed."""

from __future__ import annotations

import time

import numpy as np

from ..config import FORMS, Settings
from ..ids import new_id
from ..store.db import DB
from . import tally as tallymod


class ReviewEngine:
    def __init__(self, db: DB, s: Settings, session_id: str, learner_id: str, seed: int = 0) -> None:
        self.db = db
        self.s = s
        self.session_id = session_id
        self.learner_id = learner_id
        self.rng = np.random.default_rng(seed)
        self.gaps = self.db.get_gaps(session_id)
        self.flags = self.db.get_flags(session_id)
        self.streak = 0
        self.done = False
        self.cards_answered = 0
        self._ord = 0
        self._forms_used: dict[str, list[str]] = {g["id"]: [] for g in self.gaps}
        self._form_before: dict[str, str | None] = {g["id"]: self._catchup_form(g) for g in self.gaps}
        self.current: dict | None = None
        self._rebuild()

    # ---- helpers ----
    def _catchup_form(self, gap: dict) -> str | None:
        forms = [
            f["catchup_form"]
            for f in self.flags
            if f["id"] in gap.get("flag_ids", []) and f.get("catchup_shown") and f.get("catchup_form")
        ]
        return forms[-1] if forms else None

    def _tally_rank(self) -> list[str]:
        summ = tallymod.summary(
            self.db.get_tally(self.learner_id), self.db.population_tally(), self.s, self.rng
        )
        return summ["rank"]

    def _rebuild(self) -> None:
        cards = self.db.get_cards(self.session_id)
        streak = 0
        for c in cards:
            self._ord = max(self._ord, c["ord"] + 1)
            if c["kind"] == "reteach":
                self._forms_used.setdefault(c["gap_id"], []).append(c["form"])
                self._form_before[c["gap_id"]] = c["form"]
            if c["kind"] == "question" and c["outcome"] in ("hit", "miss", "drop"):
                self.cards_answered += 1
                streak = streak + 1 if c["outcome"] == "hit" else 0
        self.streak = streak
        pending = [c for c in cards if c["outcome"] is None]
        if pending:
            self.current = pending[-1]
        gaps_open = [g for g in self.gaps if g["status"] == "open"]
        if self.streak >= self.s.review_stop_streak or not gaps_open:
            self.done = not pending

    def _gap(self, gid: str) -> dict:
        return next(g for g in self.gaps if g["id"] == gid)

    def _next_open_gap(self) -> dict | None:
        for g in self.gaps:
            if g["status"] == "open":
                return g
        return None

    def _new_card(self, gap: dict, kind: str, form: str | None) -> dict:
        card = {
            "id": new_id("card"),
            "session_id": self.session_id,
            "gap_id": gap["id"],
            "ord": self._ord,
            "kind": kind,
            "form": form,
            "shown_at": time.time(),
            "outcome": None,
            "choice": None,
            "option_order": None,
        }
        self._ord += 1
        if kind == "question":
            card["option_order"] = [int(i) for i in self.rng.permutation(4)]
        self.db.add_card(card)
        self.current = card
        return card

    def _present(self, card: dict | None) -> dict | None:
        if card is None:
            return None
        gap = self._gap(card["gap_id"])
        pkg = gap.get("package") or {}
        out = {
            "id": card["id"],
            "kind": card["kind"],
            "gap_id": gap["id"],
            "gap_ord": gap["ord"],
            "form": card["form"],
            "t_start": gap["t_start"],
            "t_end": gap["t_end"],
            "package_source": gap.get("package_source"),
            "forms_used": list(self._forms_used.get(gap["id"], [])),
        }
        if card["kind"] == "question":
            q = pkg.get("question", {})
            order = card.get("option_order") or [0, 1, 2, 3]
            opts = q.get("options", ["", "", "", ""])
            out["question"] = {"question": q.get("question", ""), "options": [opts[i] for i in order]}
        else:
            forms = pkg.get("forms", {})
            out["reteach"] = {
                "form": card["form"],
                "content": forms.get(card["form"]),
                "key_term": pkg.get("note", {}).get("key_term"),
            }
        return out

    def progress(self) -> dict:
        return {
            "gaps_total": len(self.gaps),
            "gaps_closed": sum(1 for g in self.gaps if g["status"] == "closed"),
            "gaps_exhausted": sum(1 for g in self.gaps if g["status"] == "exhausted"),
            "streak": self.streak,
            "stop_streak": self.s.review_stop_streak,
            "cards_answered": self.cards_answered,
            "done": self.done,
        }

    def tally_summary(self) -> dict:
        return tallymod.summary(
            self.db.get_tally(self.learner_id), self.db.population_tally(), self.s, self.rng
        )

    # ---- API ----
    def start(self) -> dict:
        if self.current is None and not self.done:
            gap = self._next_open_gap()
            if gap is None:
                self.done = True
            else:
                self._new_card(gap, "question", None)
        return {
            "card": self._present(self.current),
            "progress": self.progress(),
            "tally": self.tally_summary(),
        }

    def _finish_if_needed(self) -> None:
        if self.streak >= self.s.review_stop_streak or self._next_open_gap() is None:
            self.done = True
            self.current = None

    def _switch_form(self, gap: dict) -> dict | None:
        used = self._forms_used.setdefault(gap["id"], [])
        for f in self._tally_rank():
            if f not in used:
                used.append(f)
                self._form_before[gap["id"]] = f
                return self._new_card(gap, "reteach", f)
        gap["status"] = "exhausted"
        self.db.set_gap_status(gap["id"], "exhausted")
        return None

    def answer(self, card_id: str, choice: int) -> dict:
        card = self.db.get_card(card_id)
        if card is None or card["kind"] != "question" or card["outcome"] is not None:
            raise ValueError("card is not an open question")
        gap = self._gap(card["gap_id"])
        q = (gap.get("package") or {}).get("question", {})
        order = card.get("option_order") or [0, 1, 2, 3]
        correct_orig = int(q.get("correct_index", 0))
        correct_shown = order.index(correct_orig)
        hit = int(choice) == correct_shown
        outcome = "hit" if hit else "miss"
        self.db.update_card(card_id, outcome=outcome, choice=int(choice))
        self.cards_answered += 1
        form_before = self._form_before.get(gap["id"])
        if form_before in FORMS:
            self.db.tally_add(self.learner_id, form_before, rescue=hit)
        nxt: dict | None
        if hit:
            self.streak += 1
            gap["status"] = "closed"
            self.db.set_gap_status(gap["id"], "closed")
            self.current = None
            self._finish_if_needed()
            nxt = None if self.done else self._new_card(self._next_open_gap(), "question", None)  # type: ignore[arg-type]
        else:
            self.streak = 0
            nxt = self._switch_form(gap)
            if nxt is None:
                self.current = None
                self._finish_if_needed()
                g2 = self._next_open_gap()
                nxt = None if (self.done or g2 is None) else self._new_card(g2, "question", None)
        return {
            "outcome": outcome,
            "correct_index": correct_shown,
            "explanation": q.get("explanation", ""),
            "credited_form": form_before,
            "next": self._present(nxt),
            "done": self.done,
            "progress": self.progress(),
            "tally": self.tally_summary(),
        }

    def drop(self, card_id: str) -> dict:
        """Focus drop while a card is open: switch form, no tally change."""
        card = self.db.get_card(card_id)
        if card is None or card["outcome"] is not None:
            raise ValueError("card is not open")
        self.db.update_card(card_id, outcome="drop")
        gap = self._gap(card["gap_id"])
        if card["kind"] == "question":
            self.cards_answered += 1
            self.streak = 0
        nxt = self._switch_form(gap)
        if nxt is None:
            self.current = None
            self._finish_if_needed()
            g2 = self._next_open_gap()
            nxt = None if (self.done or g2 is None) else self._new_card(g2, "question", None)
        return {
            "outcome": "drop",
            "next": self._present(nxt),
            "done": self.done,
            "progress": self.progress(),
            "tally": self.tally_summary(),
        }

    def advance(self, card_id: str) -> dict:
        """After reading a reteach card, ask the question again."""
        card = self.db.get_card(card_id)
        if card is None or card["kind"] != "reteach" or card["outcome"] is not None:
            raise ValueError("card is not an open reteach card")
        self.db.update_card(card_id, outcome="read")
        gap = self._gap(card["gap_id"])
        nxt = self._new_card(gap, "question", None)
        return {
            "next": self._present(nxt),
            "done": self.done,
            "progress": self.progress(),
            "tally": self.tally_summary(),
        }

    def state(self) -> dict:
        return {
            "card": self._present(self.current),
            "progress": self.progress(),
            "tally": self.tally_summary(),
        }
