from fastapi.testclient import TestClient


def test_deepgram_key_is_runtime_only_and_never_returned(app, settings):
    with TestClient(app) as client:
        assert client.get("/api/settings/deepgram").json() == {"configured": False}
        response = client.put("/api/settings/deepgram", json={"api_key": " synthetic-key "})
        assert response.json() == {"configured": True}
        assert settings.deepgram_api_key == "synthetic-key"
        assert client.get("/api/settings/deepgram").json() == {"configured": True}
        assert "synthetic-key" not in response.text
        for path in settings.data_dir.rglob("*"):
            if path.is_file():
                assert b"synthetic-key" not in path.read_bytes()
        for value in ["", "   ", "bad key", "x" * 513, None, 42]:
            response = client.put("/api/settings/deepgram", json={"api_key": value})
            assert response.status_code == 400
            assert response.json() == {"detail": "Enter a valid Deepgram API key."}
        assert settings.deepgram_api_key == "synthetic-key"


def test_unpaired_website_cannot_set_key(app, settings):
    with TestClient(app) as client:
        response = client.put(
            "/api/settings/deepgram",
            headers={"origin": "https://untrusted.example"},
            json={"api_key": "synthetic-key"},
        )
        assert response.status_code == 403
        assert settings.deepgram_api_key is None
