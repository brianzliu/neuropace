"""SessionRuntime (TDD §2): one asyncio-driven object per running session.

Inputs: headset events, totem taps, transcript words, client messages (tap, media time, audio, sim state).
Outputs: broadcast messages (also appended to data/sessions/<id>.jsonl) and rows in SQLite.
The 1 Hz `step(t)` is the heart; the tick loop only calls it on wall-clock seconds.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any

import numpy as np

from ..clock import LiveClock, MediaClock
from ..config import FORMS, Settings
from ..ids import new_id
from ..llm.client import LLMClient
from ..llm.fallback import recap_forms as offline_recap
from ..signal.features import DetectorEvent, FocusEngine
from ..signal.headset import make_headset
from ..signal.thinkgear import TGEvent
from ..store.db import DB
from ..totem.bridge import make_totem
from ..transcribe.deepgram_live import DeepgramLive
from ..transcribe.scripted import ScriptedTranscript
from ..transcribe.transcript import Transcript, Word
from . import tally as tallymod
from .board import BoardCapture
from .recaps import Recap, RecapRing, RecapScheduler
from .spans import eeg_span, merge_into_gaps, snap_end, tap_span

log = logging.getLogger(__name__)


class SessionRuntime:
    def __init__(
        self,
        s: Settings,
        db: DB,
        llm: LLMClient,
        session: dict,
        learner: dict,
        lecture: dict | None,
        transcript_kind: str,
        headset_port: str | None = None,
        totem_port: str | None = None,
        tick_interval: float = 1.0,
        drive_manually: bool = False,
    ) -> None:
        self.s = s
        self.db = db
        self.llm = llm
        self.session = session
        self.id: str = session["id"]
        self.learner = learner
        self.lecture = lecture
        self.mode: str = session["mode"]
        self.policy: str = session.get("catchup_policy", "always")
        self.auto_pause: bool = bool(session.get("auto_pause", True))
        self.transcript_kind = transcript_kind
        self.tick_interval = tick_interval
        self.drive_manually = (
            drive_manually  # tests: no tick loop, no real-time sources; call feed_sim_second/_on_words/step
        )
        self.seed = int(session.get("seed") or 0)
        self.rng = np.random.default_rng(self.seed)
        self.clock = LiveClock() if self.mode == "live" else MediaClock()
        self.transcript = Transcript()
        self.board = BoardCapture(self)
        stored = None
        if session.get("baseline") and session["baseline"].get("stored"):
            stored = (session["baseline"]["mu"], session["baseline"]["sigma"])
        self.engine = FocusEngine(s, stored_baseline=stored)
        self.ring = RecapRing()
        keyterms = (lecture or {}).get("keyterms") or []
        self.keyterms = keyterms
        self.recaps = RecapScheduler(s, llm, self.transcript, self.ring, self._on_recap, keyterms)
        self.flags: dict[str, dict] = {}
        self.open_eeg_flag: str | None = None
        self.best_form: str = session.get("best_form") or self._draw_best_form()
        self.subscribers: set[asyncio.Queue] = set()
        self.status = "created"
        self._focus_buf: list[dict] = []
        self._tick_task: asyncio.Task | None = None
        self._log_path = s.sessions_dir / f"{self.id}.jsonl"
        self._log_fh = None
        self.words_total = 0
        self._pending_words: list[Word] = []
        self.headset = make_headset(
            headset_port,
            self._on_headset_events,
            seed=self.seed + 1,
            on_frame=self._on_frame,
            log_dir=str(s.data_dir / "eeg"),
        )
        self.totem = make_totem(
            totem_port, self._on_totem_tap, exclude_port=getattr(self.headset, "port", None)
        )
        if headset_port and headset_port.startswith("uno-q:"):
            from ..totem.uno_q import UnoQRelay

            relay = UnoQRelay(headset_port.split(":", 1)[1], self._on_totem_tap, self._on_frame)
            self.headset = relay.headset
            self.totem = relay
        self.transcriber: Any = None
        self.audio_sample_rate = 16000
        self._last_tick_t = -1.0
        self.catchups_shown = 0
        self.notices: list[dict] = []
        self._focus_hist: list[dict] = []
        if transcript_kind == "scripted" and lecture and lecture.get("words"):
            self.transcriber = ScriptedTranscript(
                [Word(**w) for w in lecture["words"]], self._on_words, self.clock
            )
        elif transcript_kind == "recorded" and lecture and lecture.get("words"):
            self._pending_words = sorted((Word(**w) for w in lecture["words"]), key=lambda w: w.start)
        elif transcript_kind == "deepgram":
            self.transcriber = None  # created on audio_start (needs the sample rate)

    # ------------------------------------------------------------------ setup
    def _draw_best_form(self) -> str:
        summ = tallymod.summary(
            self.db.get_tally(self.learner["id"]), self.db.population_tally(), self.s, self.rng
        )
        return summ["pick"]

    async def start(self) -> None:
        self.s.ensure_dirs()
        self._log_fh = open(self._log_path, "a", encoding="utf-8")  # noqa: SIM115
        self.status = "running"
        if not self.drive_manually:
            await self.headset.start()
        await self.totem.start()
        self.totem.send("CLEAR")
        self.totem.send("FIT 0")
        if (
            self.transcriber is not None
            and hasattr(self.transcriber, "start")
            and self.transcript_kind == "scripted"
            and not self.drive_manually
        ):
            await self.transcriber.start()
        self.db.update_session(
            self.id,
            headset_kind=self.headset.kind,
            totem_kind=self.totem.kind,
            transcript_kind=self.transcript_kind,
            best_form=self.best_form,
            status="running",
        )
        self.broadcast({"type": "headset", **self.headset_status()})
        self.broadcast({"type": "totem", **self.totem.status(), "pulse": False})
        if self.tick_interval > 0 and not self.drive_manually:
            self._tick_task = asyncio.create_task(self._tick_loop(), name=f"tick-{self.id}")

    def headset_status(self) -> dict:
        d = {
            "connected": bool(getattr(self.headset, "connected", False)),
            "kind": self.headset.kind,
            "port": getattr(self.headset, "port", None),
            "state": getattr(self.headset, "state", None),
        }
        if hasattr(self.headset, "status"):
            d["mw"] = self.headset.status()
        return d

    def calibrate(self, phase: str) -> None:
        """Drive the mindwave pipeline's three-anchor calibration (eyes_closed | easy | hard | done | reset)."""
        if hasattr(self.headset, "calibrate"):
            try:
                self.headset.calibrate(phase)
            except ValueError as e:
                self.notice("warn", str(e))
                return
            self.notice("info", f"calibration: {phase}")
        else:
            self.notice("warn", "calibration needs the mindwave pipeline (real, fake or replay headset)")
        self.broadcast({"type": "headset", **self.headset_status()})

    # ------------------------------------------------------------------ broadcast + log
    def broadcast(self, msg: dict) -> None:
        msg.setdefault("t", round(self.clock.now(), 3))
        msg.setdefault("wall", round(time.time(), 3))
        if self._log_fh is not None:
            self._log_fh.write(json.dumps(msg, ensure_ascii=False) + "\n")
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def notice(self, level: str, text: str) -> None:
        self.notices.append({"level": level, "text": text})
        self.broadcast({"type": "notice", "level": level, "text": text})

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    def snapshot(self) -> dict:
        lec = None
        if self.lecture:
            lec = {
                k: self.lecture.get(k) for k in ("id", "title", "kind", "duration", "segments", "keyterms")
            }
            lec["has_media"] = bool(self.lecture.get("media_path"))
            lec["quiz_count"] = len(self.lecture.get("quiz") or [])
        return {
            "type": "hello",
            "session": {**self.db.get_session(self.id), "status": self.status},  # type: ignore[dict-item]
            "learner": self.learner,
            "lecture": lec,
            "config": self.s.public(),
            "best_form": self.best_form,
            "mode": self.mode,
            "policy": self.policy,
            "auto_pause": self.auto_pause,
            "transcript_kind": self.transcript_kind,
            "words": self.transcript.to_dicts(),
            "flags": [self._flag_public(f) for f in self.flags.values()],
            "recaps": self.ring.all(),
            "focus": self._focus_recent,
            "headset": self.headset_status(),
            "totem": self.totem.status(),
            "notices": self.notices[-5:],
            "sim": {
                "headset": self.headset.kind != "real",
                "totem": self.totem.kind == "simulated",
                "transcript": self.transcript_kind == "scripted",
            },
        }

    # ------------------------------------------------------------------ inputs
    def _on_headset_events(self, events: list[TGEvent]) -> None:
        raws = [e.value for e in events if e.kind == "raw"]
        if raws:
            self.engine.feed_raw(raws)
        for e in events:
            if e.kind == "poor_signal":
                self.engine.feed_poor_signal(int(e.value))
            elif e.kind == "attention":
                self.engine.feed_attention(int(e.value))
            elif e.kind == "eeg_power":
                self.engine.feed_eeg_power(e.value)  # type: ignore[arg-type]

    def _on_frame(self, frame) -> None:
        """One FeatureFrame per second from the mindwave pipeline (real headset, fake, or replay)."""
        if self.status != "running":
            return
        extra = {
            "effort": frame.effort,
            "engagement": frame.engagement,
            "alpha_ratio": frame.alpha_ratio,
            "blink_rate": frame.blink_rate,
            "z_effort_ema": frame.z_effort_ema,
            "z_engagement_ema": frame.z_engagement_ema,
            "artifact_coverage": frame.artifact_coverage,
            "calibrated": frame.calibrated,
            "cal_phase": frame.cal_phase,
            "attention": frame.attention,
        }
        self.engine.feed_frame(frame.engagement, frame.quality, frame.valid, frame.blink_count, extra=extra)
        if frame.attention is not None:
            self.engine.feed_attention(int(frame.attention))

    def feed_sim_second(self) -> None:
        """Tests: push one second of simulated EEG synchronously (simulated headset only)."""
        sim = getattr(self.headset, "sim", None)
        parser = getattr(self.headset, "parser", None)
        if sim is None or parser is None:
            return
        self._on_headset_events(parser.feed(sim.next_bytes(sim.fs, with_status=True)))

    def set_sim_headset(self, state: str) -> None:
        if hasattr(self.headset, "set_state"):
            self.headset.set_state(state)
        self.broadcast({"type": "headset", **self.headset_status()})

    def _on_totem_tap(self, _mono: float) -> None:
        self.tap(source="tap")

    def _on_words(self, words: list[Word], final: bool) -> None:
        if self.status != "running":
            return
        if final:
            added = self.transcript.append(words)
            if added:
                self.db.add_words(self.id, [w.to_dict() for w in added], self.words_total)
                self.words_total += len(added)
                self.broadcast({"type": "words", "words": [w.to_dict() for w in added], "final": True})
        else:
            self.transcript.set_interim(words)
            self.broadcast({"type": "words", "words": [w.to_dict() for w in words], "final": False})

    def _reveal_recorded_words(self, t: float) -> None:
        if not self._pending_words:
            return
        batch = []
        while self._pending_words and self._pending_words[0].end <= t:
            batch.append(self._pending_words.pop(0))
        if batch:
            self._on_words(batch, True)

    def set_media_time(self, t: float, playing: bool) -> None:
        if isinstance(self.clock, MediaClock):
            self.clock.set(t, playing)
            self._reveal_recorded_words(self.clock.now())

    async def audio_start(self, sample_rate: int) -> None:
        self.audio_sample_rate = int(sample_rate) or 16000
        if self.transcript_kind != "deepgram":
            return
        if not self.s.deepgram_api_key:
            self.notice("warn", "No DEEPGRAM_API_KEY: audio ignored, transcript is scripted or empty")
            return
        if self.transcriber is None:
            self.transcriber = DeepgramLive(
                self.s.deepgram_api_key,
                self._on_words,
                self.clock,
                sample_rate=self.audio_sample_rate,
                model=self.s.deepgram_model,
                keyterms=self.keyterms,
            )
            await self.transcriber.start()
            if getattr(self.transcriber, "error", None):
                self.notice("error", str(self.transcriber.error))
            else:
                self.notice(
                    "info", f"Deepgram live connected ({self.s.deepgram_model}, {self.audio_sample_rate} Hz)"
                )

    async def handle_audio(self, pcm: bytes) -> None:
        if isinstance(self.transcriber, DeepgramLive):
            await self.transcriber.send_audio(pcm)

    async def audio_stop(self) -> None:
        if isinstance(self.transcriber, DeepgramLive):
            await self.transcriber.stop()
            self.transcriber = None

    # ------------------------------------------------------------------ flags and catch-ups
    def _flag_public(self, f: dict) -> dict:
        return {
            k: f.get(k)
            for k in (
                "id",
                "source",
                "t_trigger",
                "t_start",
                "t_end",
                "catchup_shown",
                "catchup_form",
                "opened",
                "simulated",
                "linked_eeg",
            )
        }

    def _recent_eeg_flag(self, t: float) -> dict | None:
        """The open EEG-style flag, or the latest one that closed within tap_link_eeg_seconds of t."""
        if self.open_eeg_flag and self.open_eeg_flag in self.flags:
            return self.flags[self.open_eeg_flag]
        recent = [
            f
            for f in self.flags.values()
            if f["source"] in ("eeg", "forced")
            and f.get("t_end") is not None
            and t - float(f["t_end"]) <= self.s.tap_link_eeg_seconds
        ]
        return max(recent, key=lambda f: float(f["t_end"])) if recent else None

    def _persist_flag(self, f: dict) -> None:
        self.db.upsert_flag({**f, "session_id": self.id})

    def _coin(self) -> bool:
        if self.policy == "randomized":
            return bool(self.rng.random() < 0.5)
        return True

    def _now_text(self, t: float) -> str:
        ws = self.transcript.last_words(self.s.now_words, before=t + 0.5)
        return " ".join(w.w for w in ws)

    def _build_catchup(self, flag: dict, t: float) -> dict:
        recap = self.ring.lookup(t, flag["t_start"])
        if recap is None:
            span_text = self.transcript.text_between(flag["t_start"], t) or self._now_text(t)
            if span_text.strip():
                forms = offline_recap(span_text, self.transcript.text_between(0, t)).model_dump()
                source = "offline"
            else:
                forms = {f: "(nothing transcribed yet for this span)" for f in FORMS}
                source = "offline"
            recap = Recap(flag["t_start"], t, forms, source)
        return {
            "type": "catchup",
            "flag_id": flag["id"],
            "since": flag["t_start"],
            "span_seconds": round(max(0.0, t - flag["t_start"]), 1),
            "linked_eeg": flag.get("linked_eeg"),
            "form": self.best_form,
            "line": recap.forms.get(self.best_form) or recap.forms.get("plain", ""),
            "now_text": self._now_text(t),
            "forms": recap.forms,
            "source": recap.source,
            "recap_window": [recap.t_from, recap.t_to],
            "ttl_s": self.s.catchup_ttl_seconds,
        }

    def _open_flag(
        self, source: str, t_trigger: float, t_start: float, t_end: float | None, simulated: bool
    ) -> dict:
        f = {
            "id": new_id("flag"),
            "source": source,
            "t_trigger": round(t_trigger, 3),
            "t_start": round(t_start, 3),
            "t_end": (round(t_end, 3) if t_end is not None else None),
            "catchup_shown": None,
            "catchup_form": None,
            "opened": False,
            "simulated": simulated,
            "linked_eeg": None,
            "created_at": time.time(),
        }
        self.flags[f["id"]] = f
        self._persist_flag(f)
        self.broadcast({"type": "flag_open", "flag": self._flag_public(f)})
        self.totem.send(f"DOT {len(self.flags)}")
        self.broadcast({"type": "totem", **self.totem.status(), "pulse": False})
        return f

    def _close_flag(self, flag_id: str, t_end: float) -> None:
        f = self.flags.get(flag_id)
        if not f:
            return
        f["t_end"] = round(snap_end(self.transcript, t_end, self.s.tap_end_extend_max), 3)
        self._persist_flag(f)
        self.broadcast({"type": "flag_close", "flag": self._flag_public(f)})

    def _offer_catchup(self, f: dict, t: float, auto_show: bool, reason: str) -> None:
        shown = self._coin()
        f["catchup_shown"] = shown
        f["catchup_form"] = self.best_form if shown else None
        self._persist_flag(f)
        if not shown:
            self.broadcast({"type": "catchup_withheld", "flag_id": f["id"], "reason": "randomized policy"})
            return
        card = self._build_catchup(f, t)
        card["auto_show"] = auto_show
        card["reason"] = reason
        if auto_show:
            self.catchups_shown += 1
        else:
            self.totem.send("PULSE")
            self.broadcast({"type": "totem", **self.totem.status(), "pulse": True})
            self.broadcast({"type": "chip", "flag_id": f["id"]})
        self.broadcast(card)

    def tap(self, source: str = "sim_tap") -> dict:
        t = self.clock.now()
        t_start, t_end = tap_span(self.transcript, t, self.s)
        linked = self._recent_eeg_flag(t)
        if linked is not None:
            # the tap confirms a lapse the EEG already saw: the span starts where focus dropped (capped)
            t_start = max(min(t_start, float(linked["t_start"])), t - self.s.tap_link_max_back, 0.0)
        f = self._open_flag(source, t, t_start, t_end, simulated=(source != "tap"))
        if linked is not None:
            f["linked_eeg"] = linked["id"]
            self.broadcast({"type": "flag_open", "flag": self._flag_public(f)})
        self._offer_catchup(f, t, auto_show=True, reason="tap")
        self.board.on_tap(f)
        return f

    def force_flag(self) -> dict:
        t = self.clock.now()
        t_start, _ = eeg_span(self.transcript, t, None, self.s)
        f = self._open_flag("forced", t, t_start, t, simulated=True)
        self._offer_eeg_style(f, t)
        return f

    def _offer_eeg_style(self, f: dict, t: float) -> None:
        if self.mode == "recorded" and self.auto_pause:
            self.broadcast({"type": "pause_request", "flag_id": f["id"]})
            self._offer_catchup(f, t, auto_show=True, reason="video_pause")
        else:
            self._offer_catchup(f, t, auto_show=False, reason="eeg")

    def open_catchup(self, flag_id: str) -> None:
        f = self.flags.get(flag_id)
        if f:
            f["opened"] = True
            self.catchups_shown += 1
            self._persist_flag(f)
            self.broadcast({"type": "catchup_opened", "flag_id": flag_id})

    def dismiss_catchup(self, flag_id: str) -> None:
        self.broadcast({"type": "catchup_dismissed", "flag_id": flag_id})

    def _on_detector_events(self, events: list[DetectorEvent], t: float) -> None:
        for ev in events:
            if ev.kind == "enter":
                t_start, _ = eeg_span(self.transcript, ev.t, None, self.s)
                f = self._open_flag("eeg", ev.t, t_start, None, simulated=(self.headset.kind != "real"))
                self.open_eeg_flag = f["id"]
                self._offer_eeg_style(f, t)
            elif ev.kind == "exit" and self.open_eeg_flag:
                self._close_flag(self.open_eeg_flag, ev.t_end if ev.t_end is not None else t)
                self.open_eeg_flag = None

    def _on_recap(self, r: Recap) -> None:
        self.db.add_recap(self.id, r.t_from, r.t_to, r.forms, r.source)
        self.broadcast({"type": "recap", **r.to_dict(), "best_form": self.best_form})

    # ------------------------------------------------------------------ the 1 Hz step
    @property
    def _focus_recent(self) -> list[dict]:
        return self._focus_hist[-180:]

    def step(self, t: float | None = None) -> dict:
        """One lecture second. Returns the focus sample dict."""
        if self.status != "running":
            return {}
        t = self.clock.now() if t is None else t
        self.board.prune(t)
        paused = self.clock.paused
        if self.mode == "recorded":
            self._reveal_recorded_words(t)
        sample, events = self.engine.tick(t, paused=paused)
        d = sample.to_dict()
        d["sim"] = self.headset.kind != "real"
        d["blinks_total"] = self.engine.blinks.count
        if self.engine.external and self.engine.extra:
            d["mw"] = self.engine.extra
        if not self.engine.baseline.ready:
            fit = min(8, int(round(sample.baseline_progress * 8)))
            if self.totem.fit != fit:
                self.totem.send(f"FIT {fit}")
        elif self.totem.fit != 8:
            self.totem.send("FIT 8")
        self._on_detector_events(events, t)
        self.recaps.maybe_run(t)
        self._focus_hist.append(d)
        if len(self._focus_hist) > 4000:
            self._focus_hist = self._focus_hist[-2000:]
        self._focus_buf.append(d)
        if len(self._focus_buf) >= 5:
            self.db.add_focus_samples(self.id, self._focus_buf)
            self._focus_buf = []
        self.broadcast({"type": "focus", **d})
        self._last_tick_t = t
        return d

    async def _tick_loop(self) -> None:
        next_t = time.monotonic()
        try:
            while self.status == "running":
                self.step()
                next_t += self.tick_interval
                await asyncio.sleep(max(0.0, next_t - time.monotonic()))
        except asyncio.CancelledError:
            pass
        except Exception as e:  # noqa: BLE001
            log.exception("tick loop crashed: %s", e)
            self.notice("error", f"tick loop crashed: {e}")

    # ------------------------------------------------------------------ end of lecture
    async def end(self) -> list[dict]:
        await self.board.stop()
        if self.status != "running":
            return self.db.get_gaps(self.id)
        self.status = "ending"
        if self._tick_task:
            self._tick_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tick_task
        t_end = self.clock.now()
        if self.open_eeg_flag:
            self._close_flag(self.open_eeg_flag, t_end)
            self.open_eeg_flag = None
        for stopper in (self.transcriber, self.headset, self.totem):
            if stopper is not None and hasattr(stopper, "stop"):
                with contextlib.suppress(Exception):
                    await stopper.stop()
        await self.recaps.flush()
        if self._focus_buf:
            self.db.add_focus_samples(self.id, self._focus_buf)
            self._focus_buf = []
        if self.engine.baseline.ready and not self.engine.baseline.stored:
            self.db.set_learner_baseline(
                self.learner["id"], self.engine.baseline.mu, self.engine.baseline.sigma
            )  # type: ignore[arg-type]
        gaps = await self._build_gaps()
        self.db.update_session(
            self.id,
            status="ended",
            ended_at=time.time(),
            baseline={
                "mu": self.engine.baseline.mu,
                "sigma": self.engine.baseline.sigma,
                "stored": self.engine.baseline.stored,
                "ready": self.engine.baseline.ready,
            },
        )
        self.status = "ended"
        self.broadcast(
            {
                "type": "session_ended",
                "gaps": len(gaps),
                "flags": len(self.flags),
                "blinks": self.engine.blinks.count,
                "llm": self.llm.stats,
            }
        )
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None
        return gaps

    async def _build_gaps(self) -> list[dict]:
        lecture_end = max(self.transcript.end_time, self.clock.now())
        merged = merge_into_gaps(list(self.flags.values()), self.s, lecture_end=lecture_end)
        corpus = self.transcript.text_between(0, lecture_end + 1)
        rows: list[dict] = []
        for g in merged:
            span_text = self.transcript.text_between(g["t_start"], g["t_end"])
            if not span_text.strip():
                continue
            ctx = self.transcript.text_between(max(0.0, g["t_start"] - 60.0), g["t_start"])
            rows.append(
                {
                    "id": new_id("gap"),
                    "ord": len(rows),
                    "t_start": g["t_start"],
                    "t_end": g["t_end"],
                    "span_text": span_text,
                    "context_text": ctx,
                    "flag_ids": g["flag_ids"],
                    "package": None,
                    "package_source": None,
                    "status": "open",
                }
            )
        sem = asyncio.Semaphore(4)

        async def fill(row: dict, i: int) -> None:
            async with sem:
                pkg, source = await self.llm.gap_package(
                    row["span_text"], row["context_text"], corpus, self.keyterms, seed=self.seed + i
                )
                row["package"] = pkg.model_dump()
                row["package_source"] = source

        await asyncio.gather(*(fill(r, i) for i, r in enumerate(rows)))
        self.db.replace_gaps(self.id, rows)
        return rows

    async def abort(self) -> None:
        """Stop without building gaps (server shutdown)."""
        await self.board.stop()
        if self.status == "running":
            self.status = "ended"
            if self._tick_task:
                self._tick_task.cancel()
            for stopper in (self.transcriber, self.headset, self.totem):
                if stopper is not None and hasattr(stopper, "stop"):
                    with contextlib.suppress(Exception):
                        await stopper.stop()
            if self._log_fh:
                self._log_fh.close()
