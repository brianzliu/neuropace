import time

from fastapi.testclient import TestClient


def _read_until(ws, want: str, limit: int = 300):
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == want:
            return m
    raise AssertionError(f"no {want} message within {limit} messages")


def test_health_doctor_learners_lectures(app):
    with TestClient(app) as c:
        assert c.get("/api/health").json()["ok"] is True
        d = c.get("/api/doctor").json()
        assert d["keys"] == {"deepgram": False, "openai": False, "openrouter": False, "gemini": False}
        assert d["headset"]["kind"] == "simulated"
        assert d["totem"]["kind"] == "keyboard"
        lr = c.post("/api/learners", json={"name": "Judge"}).json()
        assert lr["id"].startswith("lrn_") and c.get("/api/learners").json()["learners"][0]["id"] == lr["id"]
        lecs = c.get("/api/lectures").json()["lectures"]
        assert lecs[0]["id"] == "lec_demo0001" and lecs[0]["word_count"] > 700 and len(lecs[0]["quiz"]) == 15
        full = c.get("/api/lectures/lec_demo0001?full=1").json()
        assert len(full["words"]) == lecs[0]["word_count"]
        assert c.get("/api/lectures/nope").status_code == 404
        t = c.get(f"/api/learners/{lr['id']}/tally").json()
        assert t["enough_data"] is False and t["pick"] in t["forms"]


def test_session_validation_errors(app):
    with TestClient(app) as c:
        lr = c.post("/api/learners", json={"name": "x"}).json()
        r = c.post("/api/sessions", json={"learner_id": lr["id"], "mode": "live"})
        assert r.status_code == 400 and "DEEPGRAM" in r.json()["detail"]
        assert c.post("/api/sessions", json={"learner_id": "lrn_nope", "mode": "live"}).status_code == 404
        assert (
            c.post(
                "/api/sessions", json={"learner_id": lr["id"], "lecture_id": "lec_demo0001", "mode": "weird"}
            ).status_code
            == 400
        )
        assert c.post("/api/sessions", json={"learner_id": lr["id"], "mode": "recorded"}).status_code == 400


def test_full_flow_over_http_and_ws_realtime(app):
    """Real-time: 20 s baseline replaced by 5 s, recaps every 5 s; the whole thing takes ~8 s."""
    with TestClient(app) as c:
        lr = c.post("/api/learners", json={"name": "Judge"}).json()
        r = c.post(
            "/api/sessions",
            json={
                "learner_id": lr["id"],
                "lecture_id": "lec_demo0001",
                "mode": "live",
                "baseline_seconds": 5,
                "headset": "sim",
                "totem": "sim",
                "seed": 5,
            },
        )
        assert r.status_code == 200, r.text
        sess = r.json()
        assert (
            sess["running"]
            and sess["transcript_kind"] == "scripted"
            and sess["headset"]["kind"] == "simulated"
        )
        with c.websocket_connect(f"/ws/session/{sess['id']}") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["sim"] == {
                "headset": True,
                "totem": False,
                "transcript": True,
            }
            assert hello["lecture"]["id"] == "lec_demo0001" and hello["config"]["baseline_seconds"] == 5
            assert hello["totem"]["kind"] == "keyboard" and "Space" in hello["totem"]["hint"]
            f = _read_until(ws, "focus")
            assert f["sim"] is True and f["quality"] == "good"
            time.sleep(6.5)  # baseline (5 s) + a few words
            ws.send_json({"type": "ping"})
            _read_until(ws, "pong")
            t0 = time.perf_counter()
            ws.send_json({"type": "tap"})
            cu = _read_until(ws, "catchup")
            latency = time.perf_counter() - t0
            assert latency < 1.0, f"tap -> catch-up took {latency:.2f}s"
            assert cu["auto_show"] and cu["reason"] == "tap" and cu["line"] and cu["ttl_s"] == 6
            ws.send_json({"type": "sim_headset", "state": "drifting"})
            h = _read_until(ws, "headset")
            assert h["state"] == "drifting"
            ws.send_json({"type": "force_flag"})
            chip = _read_until(ws, "chip")
            assert chip["flag_id"].startswith("flag_")
            ws.send_json({"type": "open_catchup", "flag_id": chip["flag_id"]})
            _read_until(ws, "catchup_opened")
        s2 = c.get(f"/api/sessions/{sess['id']}").json()
        assert len(s2["flags"]) == 2 and s2["catchups_shown"] == 2
        end = c.post(f"/api/sessions/{sess['id']}/end").json()
        assert end["session"]["status"] == "ended" and len(end["gaps"]) >= 1
        g = end["gaps"][0]
        assert "question" not in g and g["note"]["key_term"]  # the check stays server-side until review
        notes = c.get(f"/api/sessions/{sess['id']}/notes").json()
        assert len(notes["gaps"]) == len(end["gaps"]) and "words" not in notes
        manual = c.post(f"/api/sessions/{sess['id']}/review/start", json={"mode": "manual"}).json()
        assert manual["card"]["kind"] == "question" and manual["progress"]["mode"] == "manual"
        assert c.post(f"/api/sessions/{sess['id']}/review/start", json={"mode": "nope"}).status_code == 400
        # the same lesson, switched to private tutoring: the open check stays, the next moment is explained first
        st = c.post(f"/api/sessions/{sess['id']}/review/start", json={"mode": "tutor"}).json()
        card0 = st["card"]
        assert card0["kind"] == "question" and st["progress"]["mode"] == "tutor"
        ans0 = c.post(
            f"/api/sessions/{sess['id']}/review/answer", json={"card_id": card0["id"], "choice": 0}
        ).json()
        assert ans0["credited_form"] is None
        st = c.get(f"/api/sessions/{sess['id']}/review").json()
        first = st["card"]
        if first is None or first["kind"] != "reteach":
            first = ans0["next"]
        assert first["kind"] == "reteach" and st["progress"]["gaps_total"] == len(end["gaps"])
        assert first["reteach"]["why"] and first["reteach"]["said"]
        adv = c.post(f"/api/sessions/{sess['id']}/review/advance", json={"card_id": first["id"]}).json()
        card = adv["next"]
        assert card["kind"] == "question"
        ans = c.post(
            f"/api/sessions/{sess['id']}/review/answer", json={"card_id": card["id"], "choice": 0}
        ).json()
        assert ans["outcome"] in ("hit", "miss") and 0 <= ans["correct_index"] < 4
        assert ans["credited_form"] == first["form"]
        if ans["next"] and ans["next"]["kind"] == "reteach":
            drop = c.post(
                f"/api/sessions/{sess['id']}/review/drop", json={"card_id": ans["next"]["id"]}
            ).json()
            assert drop["outcome"] == "drop"
        assert (
            c.post(
                f"/api/sessions/{sess['id']}/review/answer", json={"card_id": card["id"], "choice": 0}
            ).status_code
            == 400
        )
        tally = c.get(f"/api/learners/{lr['id']}/tally").json()
        assert tally["total_attempts"] >= 1
        ev = c.get(f"/api/sessions/{sess['id']}/events").json()["events"]
        assert ev[-1]["type"] == "session_ended" and any(e["type"] == "catchup" for e in ev)
        lm = c.get("/api/lectures/lec_demo0001/lossmap").json()
        assert lm["ready"] is False and lm["n"] == 1
        quiz = c.get(f"/api/sessions/{sess['id']}/quiz").json()
        assert len(quiz["items"]) == 15 and "correct_index" not in quiz["items"][0]
        qr = c.post(
            f"/api/sessions/{sess['id']}/quiz",
            json={"phase": "before", "answers": {q["id"]: 0 for q in quiz["items"]}},
        ).json()
        assert qr["score"] == 15 and qr["total"] == 15
        study = c.get("/api/lectures/lec_demo0001/study").json()
        assert study["sessions"] == 1
        assert c.get(f"/api/sessions/{sess['id']}/review").json()["progress"]["gaps_total"] >= 1
        ws_closed = c.websocket_connect(f"/ws/session/{sess['id']}")
        with ws_closed as ws:
            m = ws.receive_json()
            assert m["type"] == "error" and m["status"] in ("ended", "reviewed")


def test_lossmap_ready_with_two_sessions(app):
    with TestClient(app) as c:
        ids = []
        for name in ("a", "b"):
            lr = c.post("/api/learners", json={"name": name}).json()
            r = c.post(
                "/api/sessions",
                json={
                    "learner_id": lr["id"],
                    "lecture_id": "lec_demo0001",
                    "mode": "live",
                    "baseline_seconds": 5,
                    "headset": "sim",
                    "totem": "sim",
                },
            )
            ids.append(r.json()["id"])
        time.sleep(3.0)
        for sid in ids:
            c.post(f"/api/sessions/{sid}/tap")
        for sid in ids:
            c.post(f"/api/sessions/{sid}/end")
        lm = c.get("/api/lectures/lec_demo0001/lossmap").json()
        assert lm["ready"] is True and lm["n"] == 2 and lm["peak"]["t_end"] - lm["peak"]["t_start"] <= 40
        assert lm["segments"] and lm["ranking"]


def test_sessions_default_to_the_single_device_learner(app):
    with TestClient(app) as c:
        r = c.post(
            "/api/sessions",
            json={
                "lecture_id": "lec_demo0001",
                "mode": "live",
                "baseline_seconds": 5,
                "headset": "sim",
                "totem": "keyboard",
            },
        )
        assert r.status_code == 200, r.text
        sess = r.json()
        assert sess["learner_id"] == "lrn_me"
        me = c.get("/api/learners/me").json()
        assert me["id"] == "lrn_me" and me["name"] == "you"
        assert c.get("/api/learners/me/tally").json()["total_attempts"] == 0
        # the study can still name a participant, created on first use and reused after
        r2 = c.post(
            "/api/sessions",
            json={
                "lecture_id": "lec_demo0001",
                "mode": "live",
                "baseline_seconds": 5,
                "headset": "sim",
                "totem": "keyboard",
                "learner_name": "P07",
            },
        )
        r3 = c.post(
            "/api/sessions",
            json={
                "lecture_id": "lec_demo0001",
                "mode": "live",
                "baseline_seconds": 5,
                "headset": "sim",
                "totem": "keyboard",
                "learner_name": "p07",
            },
        )
        assert r2.json()["learner_id"] == r3.json()["learner_id"] != "lrn_me"
        for sid in (sess["id"], r2.json()["id"], r3.json()["id"]):
            c.post(f"/api/sessions/{sid}/end")
