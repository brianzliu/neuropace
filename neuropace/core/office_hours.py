"""Office Hours (docs/PRODUCT.md §5a): an open conversation about a lecture, agent-drawn board.

Unlike ReviewEngine's scripted teach/check loop, this is agent-driven: the student sends a message, the
model replies and optionally adds/updates/removes elements on a shared board (the same template catalogue
as §4, plus small shape/arrow/label annotations). State is event-sourced in oh_messages/oh_board_ops
(store/db.py) so the engine, like ReviewEngine, is always rebuildable from the DB after a restart, and a
"scrub to time T" is just replaying the op log up to that ord.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from pydantic import ValidationError

from ..config import Settings
from ..llm.client import LLMClient
from ..llm.schemas import BOARD_CONTENT_KINDS, AddElement, RemoveElement, UpdateElement
from ..store.db import DB

log = logging.getLogger(__name__)

MAX_LIVE_ELEMENTS = 24
MAX_TRANSCRIPT_CHARS = 12000


def replay_board(ops: list[dict]) -> dict[str, dict]:
    """Fold an ord-ordered slice of oh_board_ops into {element_id: element}. Pure so it can serve both
    "current board" (all ops) and "board at time T" (ops filtered to ord<=T) identically."""
    board: dict[str, dict] = {}
    for row in ops:
        eid = row["element_id"]
        if row["op"] == "add":
            board[eid] = {"id": eid, **(row["payload"] or {})}
        elif row["op"] == "update":
            if eid in board:
                cur = dict(board[eid])
                patch = row["payload"] or {}
                if "envelope" in patch:
                    cur["envelope"] = {**cur.get("envelope", {}), **patch["envelope"]}
                if "content" in patch:
                    cur["content"] = {**cur.get("content", {}), **patch["content"]}
                board[eid] = cur
        elif row["op"] == "remove":
            board.pop(eid, None)
    return board


def _validate_content(kind: str, content_json: str | None) -> dict | None:
    if content_json is None:
        return None
    model_cls = BOARD_CONTENT_KINDS.get(kind)
    if model_cls is None:
        log.warning("office hours: unknown board element kind %r, dropping op", kind)
        return None
    try:
        return model_cls.model_validate_json(content_json).model_dump()
    except (ValidationError, ValueError) as e:
        log.warning("office hours: %s content rejected, dropping op: %s", kind, str(e)[:200])
        return None


class OfficeHoursEngine:
    def __init__(
        self,
        db: DB,
        s: Settings,
        llm: LLMClient,
        session_id: str,
        learner_id: str,
        lecture: dict | None,
    ) -> None:
        self.db = db
        self.s = s
        self.llm = llm
        self.session_id = session_id
        self.learner_id = learner_id
        self.lecture = lecture
        self.messages: list[dict] = []
        self.board: dict[str, dict] = {}
        self._ord = 0
        self._transcript = self._lecture_transcript()
        self._rebuild()

    def _lecture_transcript(self) -> str:
        """What the agent is grounded in (GROUNDING, llm/prompts.py): the lecture's own words, not summaries
        the model would have to trust blindly. Empty when there is no lecture or no transcript yet."""
        if not self.lecture:
            return ""
        words = self.lecture.get("words") or []
        text = " ".join(w.get("w", "") for w in words).strip()
        return text[:MAX_TRANSCRIPT_CHARS]

    def _rebuild(self) -> None:
        self.messages = self.db.oh_get_messages(self.session_id)
        self.board = replay_board(self.db.oh_get_board_ops(self.session_id))
        self._ord = self.db.oh_next_ord(self.session_id)

    # ---- reads ----
    def snapshot(self, upto_ord: int | None = None) -> dict:
        """The board and chat as of upto_ord (None = now). Scrubbing the timeline is this same call at an
        earlier ord: there is no separate "history" representation to keep in sync."""
        messages = self.db.oh_get_messages(self.session_id, upto_ord=upto_ord)
        board = replay_board(self.db.oh_get_board_ops(self.session_id, upto_ord=upto_ord))
        return {"messages": messages, "board": list(board.values()), "ord": self._ord - 1}

    # ---- writes ----
    async def send_message(self, text: str) -> dict:
        text = " ".join((text or "").split())
        if not text:
            raise ValueError("empty message")
        self._append_message("user", text)
        history = [{"role": m["role"], "text": m["text"]} for m in self.messages]
        board_summary = [
            {"id": eid, "kind": el.get("kind"), "envelope": el.get("envelope")}
            for eid, el in self.board.items()
        ]
        turn, source = await self.llm.office_hours_turn(history, board_summary, text, self._transcript)
        if turn is None:
            return self._append_message(
                "agent",
                "Sorry, I couldn't reach the model just now. Try asking again in a moment.",
                source="failed",
            )
        applied_ids = self._apply_ops(turn.board_ops)
        return self._append_message("agent", turn.reply_text, related_element_ids=applied_ids, source=source)

    async def send_message_stream(self, text: str) -> AsyncIterator[dict]:
        """Same turn as send_message, but applies (and persists) each board op the moment the model finishes
        it instead of waiting for the whole reply — the whiteboard fills in live instead of popping in all at
        once. Yields {"type": "reply", "text": ...} once, {"type": "board", "board": [...]} after each applied
        op, and finally {"type": "done", "message": ...} with the same persisted agent message send_message
        would have produced."""
        text = " ".join((text or "").split())
        if not text:
            raise ValueError("empty message")
        self._append_message("user", text)
        history = [{"role": m["role"], "text": m["text"]} for m in self.messages]
        board_summary = [
            {"id": eid, "kind": el.get("kind"), "envelope": el.get("envelope")}
            for eid, el in self.board.items()
        ]
        reply_text = ""
        source = "offline"
        applied_ids: list[str] = []
        async for event in self.llm.office_hours_turn_stream(history, board_summary, text, self._transcript):
            if event["type"] == "reply":
                reply_text = " ".join(event["text"].split())
                if len(reply_text.split()) < 2:
                    reply_text = ""
                    continue
                source = "llm"
                yield {"type": "reply", "text": reply_text}
            elif event["type"] == "op":
                applied_ids.extend(self._apply_ops([event["op"]]))
                yield {"type": "board", "board": list(self.board.values())}
        if not reply_text:
            msg = self._append_message(
                "agent",
                "Sorry, I couldn't reach the model just now. Try asking again in a moment.",
                source="failed",
            )
        else:
            msg = self._append_message("agent", reply_text, related_element_ids=applied_ids, source=source)
        yield {"type": "done", "message": msg}

    async def expand_element(self, element_id: str) -> dict:
        """Click-to-expand: synthesizes a user turn asking about this element, then runs the normal turn path
        so an elaboration is indistinguishable from any other reply once it lands in the chat."""
        el = self.board.get(element_id)
        if el is None:
            raise ValueError("unknown board element")
        prompt = f"Can you say more about the board element you just showed me ({el.get('kind')}, id {element_id})?"
        return await self.send_message(prompt)

    def _apply_ops(self, ops: list[AddElement | UpdateElement | RemoveElement]) -> list[str]:
        ids: list[str] = []
        for op in ops:
            if isinstance(op, AddElement):
                content = _validate_content(op.kind, op.content_json)
                if content is None:
                    continue
                payload = {"kind": op.kind, "envelope": op.envelope.model_dump(), "content": content}
                self._ord += 1
                self.db.oh_add_board_op(self.session_id, self._ord, "add", op.element_id, payload)
                self.board[op.element_id] = {"id": op.element_id, **payload}
            elif isinstance(op, UpdateElement):
                if op.element_id not in self.board:
                    continue
                patch: dict = {}
                if op.envelope is not None:
                    patch["envelope"] = op.envelope.model_dump()
                if op.content_json is not None:
                    kind = self.board[op.element_id].get("kind", "")
                    content = _validate_content(kind, op.content_json)
                    if content is not None:
                        patch["content"] = content
                if not patch:
                    continue
                self._ord += 1
                self.db.oh_add_board_op(self.session_id, self._ord, "update", op.element_id, patch)
                cur = dict(self.board[op.element_id])
                if "envelope" in patch:
                    cur["envelope"] = {**cur.get("envelope", {}), **patch["envelope"]}
                if "content" in patch:
                    cur["content"] = {**cur.get("content", {}), **patch["content"]}
                self.board[op.element_id] = cur
            elif isinstance(op, RemoveElement):
                if op.element_id not in self.board:
                    continue
                self._ord += 1
                self.db.oh_add_board_op(self.session_id, self._ord, "remove", op.element_id, None)
                self.board.pop(op.element_id, None)
            ids.append(op.element_id)
        self._evict_if_crowded()
        return ids

    def _evict_if_crowded(self) -> None:
        """A long conversation can't grow the board without bound: drop the oldest element past the cap."""
        while len(self.board) > MAX_LIVE_ELEMENTS:
            oldest = next(iter(self.board))
            self._ord += 1
            self.db.oh_add_board_op(self.session_id, self._ord, "remove", oldest, None)
            self.board.pop(oldest, None)

    def _append_message(
        self, role: str, text: str, related_element_ids: list[str] | None = None, source: str | None = None
    ) -> dict:
        self._ord += 1
        msg = self.db.oh_add_message(self.session_id, self._ord, role, text, related_element_ids, source)
        self.messages.append(msg)
        return msg
