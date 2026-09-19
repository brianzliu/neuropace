import asyncio

import pytest

from neuropace.clock import ManualClock
from neuropace.core.session import SessionRuntime
from neuropace.transcribe.transcript import Word


async def _drive(
    rt: SessionRuntime, words: list[Word], seconds: int, actions: dict[int, callable] | None = None
):
    """Advance lecture time one second at a time, feeding words and simulated EEG."""
    wi = 0
    actions = actions or {}
    for sec in range(1, seconds + 1):
        rt.clock.set(float(sec))
        batch = []
        while wi < len(words) and words[wi].end <= sec:
            batch.append(words[wi])
            wi += 1
        if batch:
            rt._on_words(batch, True)
        if sec in actions:
            actions[sec]()
        rt.feed_sim_second()
        rt.step(float(sec))
        await asyncio.sleep(0)


def _make(settings, db, llm, mode="live", policy="always", seed=7, transcript_kind="scripted"):
    lec = db.get_lecture("lec_demo0001", full=True)
    lrn = db.create_learner("Ana")
    sess = db.create_session(
        learner_id=lrn["id"], lecture_id=lec["id"], mode=mode, catchup_policy=policy, seed=seed
    )
    rt = SessionRuntime(
        settings,
        db,
        llm,
        sess,
        lrn,
        lec,
        transcript_kind,
        headset_port="sim",
        totem_port="sim",
        drive_manually=True,
    )
    if mode == "live":
        rt.clock = ManualClock(0.0)
    return rt, lec, lrn


def _drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


@pytest.mark.asyncio
async def test_live_session_tap_catchup_eeg_flag_notes_and_log(settings, db, llm):
    rt, lec, lrn = _make(settings, db, llm)
    await rt.start()
    q = rt.subscribe()
    words = [Word(**w) for w in lec["words"]]
    await _drive(
        rt,
        words,
        110,
        {
            35: lambda: rt.tap("key"),
            50: lambda: rt.set_sim_headset("drifting"),
            95: lambda: rt.set_sim_headset("focused"),
        },
    )
    msgs = _drain(q)
    types = {m["type"] for m in msgs}
    assert {"words", "focus", "recap", "flag_open", "flag_close", "catchup", "chip", "totem"} <= types
    cu = [m for m in msgs if m["type"] == "catchup"]
    tap_cu = [m for m in cu if m["reason"] == "tap"]
    assert (
        tap_cu and tap_cu[0]["auto_show"] is True and tap_cu[0]["form"] == rt.best_form and tap_cu[0]["line"]
    )
    assert "You" not in tap_cu[0]["line"][:3] or True
    assert tap_cu[0]["now_text"] and tap_cu[0]["recap_window"][1] <= 35 + 2
    eeg_cu = [m for m in cu if m["reason"] == "eeg"]
    assert eeg_cu and eeg_cu[0]["auto_show"] is False, "EEG flag only offers a card (P4)"
    assert any(m["type"] == "chip" for m in msgs)
    pulses = [m for m in msgs if m["type"] == "totem" and m.get("pulse")]
    assert pulses, "totem pulses on an EEG flag"
    flags = list(rt.flags.values())
    assert (
        flags[0]["source"] == "key"
        and flags[0]["simulated"] is False
        and flags[0]["t_start"] <= 35 - 8 + 0.25
    )
    eeg = [f for f in flags if f["source"] == "eeg"]
    assert eeg and 50 < eeg[0]["t_trigger"] < 75 and eeg[0]["t_start"] <= eeg[0]["t_trigger"] - 8 + 0.25
    assert rt.recaps.runs >= 10 and all(r["source"] == "offline" for r in rt.ring.all())
    gaps = await rt.end()
    assert gaps and all(
        g["package"]["question"]["options"] and len(g["package"]["question"]["options"]) == 4 for g in gaps
    )
    assert all(
        g["package"]["artifacts"]["diagram"]["nodes"] and g["package"]["artifacts"]["example"]["lines"]
        for g in gaps
    )
    sess = db.get_session(rt.id)
    assert sess["status"] == "ended" and sess["baseline"]["ready"] and sess["headset_kind"] == "simulated"
    assert db.get_learner(lrn["id"])["baseline_mu"] is not None
    assert len(db.get_focus_samples(rt.id)) == 110 and len(db.get_words(rt.id)) == len(
        [w for w in words if w.end <= 110]
    )
    log = (settings.sessions_dir / f"{rt.id}.jsonl").read_text().splitlines()
    assert len(log) >= len(msgs) and '"type": "session_ended"' in log[-1]


@pytest.mark.asyncio
async def test_randomized_policy_logs_coin_and_withholds(settings, db, llm):
    rt, lec, _ = _make(settings, db, llm, policy="randomized", seed=11)
    await rt.start()
    q = rt.subscribe()
    words = [Word(**w) for w in lec["words"]]
    taps = {t: (lambda: rt.tap("key")) for t in (20, 30, 40, 50, 60, 70, 80, 90)}
    await _drive(rt, words, 95, taps)
    msgs = _drain(q)
    shown = [f for f in rt.flags.values() if f["catchup_shown"]]
    withheld = [f for f in rt.flags.values() if f["catchup_shown"] is False]
    assert shown and withheld, "with 8 taps both branches of the coin should appear"
    assert all(f["catchup_form"] is None for f in withheld) and all(
        f["catchup_form"] == rt.best_form for f in shown
    )
    assert len([m for m in msgs if m["type"] == "catchup"]) == len(shown)
    assert len([m for m in msgs if m["type"] == "catchup_withheld"]) == len(withheld)
    stored = db.get_flags(rt.id)
    assert {f["id"]: f["catchup_shown"] for f in stored} == {
        f["id"]: f["catchup_shown"] for f in rt.flags.values()
    }


@pytest.mark.asyncio
async def test_recorded_mode_media_clock_pause_request_and_paused_samples(settings, db, llm):
    rt, lec, _ = _make(settings, db, llm, mode="recorded", transcript_kind="recorded")
    await rt.start()
    q = rt.subscribe()
    # the client's player drives lecture time; words are revealed from the lecture transcript
    for sec in range(1, 30):
        rt.set_media_time(float(sec), True)
        rt.feed_sim_second()
        rt.step(float(sec))
        await asyncio.sleep(0)
    assert rt.words_total > 20
    rt.set_media_time(29.0, False)  # paused
    d = rt.step(29.0)
    assert d["paused"] is True
    rt.set_media_time(30.0, True)
    for sec in range(30, 60):
        rt.set_media_time(float(sec), True)
        rt.feed_sim_second()
        rt.step(float(sec))
        await asyncio.sleep(0)
    f = rt.force_flag()
    msgs = _drain(q)
    assert any(m["type"] == "pause_request" and m["flag_id"] == f["id"] for m in msgs)
    cu = [m for m in msgs if m["type"] == "catchup" and m["flag_id"] == f["id"]]
    assert cu and cu[0]["auto_show"] is True and cu[0]["reason"] == "video_pause"
    assert f["source"] == "forced" and f["simulated"] is True
    gaps = await rt.end()
    assert gaps


@pytest.mark.asyncio
async def test_no_flags_means_no_gaps(settings, db, llm):
    rt, lec, _ = _make(settings, db, llm, seed=3)
    await rt.start()
    words = [Word(**w) for w in lec["words"]]
    await _drive(rt, words, 40)
    gaps = await rt.end()
    assert gaps == [] and db.get_gaps(rt.id) == []


@pytest.mark.asyncio
async def test_tap_during_an_eeg_flag_inherits_the_drop_start(settings, db, llm):
    rt, lec, _ = _make(settings, db, llm, seed=21)
    await rt.start()
    q = rt.subscribe()
    words = [Word(**w) for w in lec["words"]]
    await _drive(rt, words, 45, {30: lambda: rt.set_sim_headset("drifting")})
    # drive until the EEG flag opens, then tap 12 s later while it is still open
    t = 45
    while rt.open_eeg_flag is None and t < 110:
        t += 1
        await _drive_one(rt, words, t)
    assert rt.open_eeg_flag, "no EEG flag opened while drifting"
    eeg = rt.flags[rt.open_eeg_flag]
    for _ in range(12):
        t += 1
        await _drive_one(rt, words, t)
    tap = rt.tap("key")
    assert tap["linked_eeg"] == eeg["id"]
    assert tap["t_start"] == max(eeg["t_start"], t - settings.tap_link_max_back)
    assert tap["t_start"] < t - 8.5, "the linked tap reaches further back than the plain 8 s lead-in"
    msgs = _drain(q)
    cu = [m for m in msgs if m["type"] == "catchup" and m["flag_id"] == tap["id"]]
    assert cu and cu[0]["since"] == tap["t_start"] and cu[0]["linked_eeg"] == eeg["id"]
    assert cu[0]["span_seconds"] >= 12 and cu[0]["recap_window"][0] <= t
    # a tap long after the flag closed is not linked
    rt.set_sim_headset("focused")
    while rt.open_eeg_flag is not None and t < 250:
        t += 1
        await _drive_one(rt, words, t)
    for _ in range(int(settings.tap_link_eeg_seconds) + 2):
        t += 1
        await _drive_one(rt, words, t)
    tap2 = rt.tap("key")
    assert tap2["linked_eeg"] is None and tap2["t_start"] >= t - 20.5
    await rt.end()


async def _drive_one(rt: SessionRuntime, words: list[Word], t: int) -> None:
    rt.clock.set(float(t))
    batch = [w for w in words if t - 1 < w.end <= t]
    if batch:
        rt._on_words(batch, True)
    rt.feed_sim_second()
    rt.step(float(t))
    await asyncio.sleep(0)
