from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_demo_mode_is_isolated_seeded_and_persistent(app, settings):
    with TestClient(app) as client:
        assert client.get("/api/settings/demo").json() == {
            "enabled": False,
            "synthetic": True,
        }
        learner_id = client.get("/api/learners/me").json()["id"]
        real_before = client.get(f"/api/learners/{learner_id}/dashboard").json()

        enabled = client.put("/api/settings/demo", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True
        sample = client.get(f"/api/learners/{learner_id}/dashboard").json()
        assert len(sample["sessions"]) == 3
        assert len(sample["concepts"]) == 2
        assert sample["closed"] == 1
        assert all(concept["source"] == "demo" for concept in sample["concepts"])
        assert settings.data_dir.joinpath("neuropace-demo.db").exists()
        assert settings.data_dir.joinpath("demo-mode.json").read_text().strip()

        disabled = client.put("/api/settings/demo", json={"enabled": False})
        assert disabled.status_code == 200
        assert client.get(f"/api/learners/{learner_id}/dashboard").json() == real_before


def test_demo_mode_cannot_switch_during_a_live_session(app):
    app.state.runtimes["running"] = SimpleNamespace(status="running")
    with TestClient(app) as client:
        response = client.put("/api/settings/demo", json={"enabled": True})
        assert response.status_code == 409
        assert response.json()["detail"] == "End the live session before switching sample data."
        assert client.get("/api/settings/demo").json()["enabled"] is False
