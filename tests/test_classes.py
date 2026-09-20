"""Multiple classes per learner: CRUD, activation, dashboard isolation, legacy compat."""

from fastapi.testclient import TestClient


def test_classes_crud_and_activation(app, db):
    learner = db.create_learner("Synthetic Classes")
    with TestClient(app) as client:
        base = f"/api/learners/{learner['id']}/classes"
        # Legacy syllabus migrates into the first class.
        assert client.put(
            f"/api/learners/{learner['id']}/curriculum",
            json={"title": "Physics", "topics": [{"title": "Orbits", "completed": False}]},
        ).status_code == 200
        first = client.get(base).json()["classes"]
        assert len(first) == 1 and first[0]["title"] == "Physics" and first[0]["is_active"]

        created = client.post(base, json={"title": "Chemistry"}).json()
        assert created["title"] == "Chemistry" and not created["is_active"]
        assert client.post(base, json={"title": "x" * 201}).status_code == 422

        listing = client.get(base).json()["classes"]
        assert [c["title"] for c in listing] == ["Physics", "Chemistry"]

        # Saving topics to the second class does not touch the first.
        saved = client.put(
            f"{base}/{created['id']}",
            json={"title": "Chemistry", "topics": [{"title": "Acids", "completed": False}]},
        ).json()
        assert [t["title"] for t in saved["topics"]] == ["Acids"]
        assert client.get(base).json()["classes"][0]["topic_count"] == 1

        # Dashboards are class-isolated.
        dash_chem = client.get(
            f"/api/learners/{learner['id']}/dashboard", params={"class_id": created["id"]}
        ).json()
        assert [t["title"] for t in dash_chem["curriculum"]["topics"]] == ["Acids"]
        assert dash_chem["active_class"]["id"] == created["id"]
        dash_default = client.get(f"/api/learners/{learner['id']}/dashboard").json()
        assert [t["title"] for t in dash_default["curriculum"]["topics"]] == ["Orbits"]

        # Activation switches the default dashboard.
        activated = client.post(f"{base}/{created['id']}/activate").json()
        assert activated["is_active"]
        assert client.get(f"/api/learners/{learner['id']}/dashboard").json()["curriculum"]["topics"][0]["title"] == "Acids"

        # Unknown class ids 404 everywhere.
        assert client.get(f"/api/learners/{learner['id']}/dashboard", params={"class_id": "cls_nope"}).status_code == 404
        assert client.post(f"{base}/cls_nope/activate").status_code == 404
        assert client.delete(f"{base}/cls_nope").status_code == 404

        # Deleting the active class falls back to the survivor; deleting the
        # last class recreates a fresh default instead of a dead end.
        remaining = client.delete(f"{base}/{created['id']}").json()["classes"]
        assert len(remaining) == 1 and remaining[0]["is_active"]
        remaining = client.delete(f"{base}/{remaining[0]['id']}").json()["classes"]
        assert len(remaining) == 1 and remaining[0]["title"] == "My curriculum"


def test_classes_are_learner_scoped(app, db):
    a, b = db.create_learner("A"), db.create_learner("B")
    with TestClient(app) as client:
        other = client.post(f"/api/learners/{b['id']}/classes", json={"title": "B class"}).json()
        assert client.put(
            f"/api/learners/{a['id']}/classes/{other['id']}",
            json={"title": "Hijack", "topics": []},
        ).status_code == 404
        assert client.post(f"/api/learners/{a['id']}/classes/{other['id']}/activate").status_code == 404
