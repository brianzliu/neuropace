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


def test_model_provider_can_save_and_switch_keys_without_returning_them(app, settings):
    with TestClient(app) as client:
        status = client.get("/api/settings/model").json()
        assert status == {
            "provider": "openai",
            "model": "gpt-5-mini",
            "models": {
                "openai": "gpt-5-mini",
                "openrouter": "openai/gpt-4o-mini",
                "gemini": "gemini-2.5-flash",
            },
            "configured": {"openai": False, "openrouter": False, "gemini": False},
        }
        response = client.put(
            "/api/settings/model",
            json={
                "provider": "openrouter",
                "api_key": "router-secret",
                "model": "openai/gpt-4o-mini",
            },
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "openrouter"
        assert "router-secret" not in response.text
        assert settings.openrouter_api_key == "router-secret"
        assert app.state.llm.provider == "openrouter"

        response = client.put(
            "/api/settings/model",
            json={
                "provider": "openai",
                "api_key": "openai-secret",
                "model": "gpt-5-mini",
            },
        )
        assert response.status_code == 200
        assert app.state.llm.provider == "openai"
        assert settings.openrouter_api_key == "router-secret"

        response = client.put(
            "/api/settings/model",
            json={
                "provider": "openrouter",
                "model": "anthropic/claude-sonnet-4.5",
            },
        )
        assert response.status_code == 200
        assert settings.openrouter_model == "anthropic/claude-sonnet-4.5"
        assert app.state.llm.provider == "openrouter"


def test_model_provider_rejects_missing_or_invalid_settings(app):
    with TestClient(app) as client:
        assert client.put("/api/settings/model", json={"provider": "other", "model": "x"}).status_code == 400
        assert (
            client.put("/api/settings/model", json={"provider": "openrouter", "model": "x"}).status_code
            == 400
        )
        assert (
            client.put(
                "/api/settings/model",
                json={
                    "provider": "openrouter",
                    "api_key": "bad key",
                    "model": "x",
                },
            ).status_code
            == 400
        )
        assert (
            client.put(
                "/api/settings/model",
                json={
                    "provider": "openrouter",
                    "api_key": "key",
                    "model": "bad model",
                },
            ).status_code
            == 400
        )


def test_gemini_provider_switch_never_returns_secret(app, settings):
    with TestClient(app) as client:
        response = client.put(
            "/api/settings/model",
            json={"provider": "gemini", "model": "gemini-2.5-flash", "api_key": "gemini-test-secret"},
        )
        assert response.status_code == 200 and response.json()["configured"]["gemini"]
        assert settings.llm_provider == "gemini" and app.state.llm.model == "gemini-2.5-flash"
        assert "gemini-test-secret" not in response.text
        assert str(app.state.llm._client.base_url).startswith("https://generativelanguage.googleapis.com/")


def test_provider_change_repairs_running_session(app):
    with TestClient(app) as client:
        response = client.post(
            "/api/sessions", json={"mode": "review", "headset": "sim", "totem": "keyboard"}
        )
        assert response.status_code == 200
        runtime = app.state.runtimes[response.json()["id"]]
        original = runtime.llm
        response = client.put(
            "/api/settings/model",
            json={
                "provider": "openrouter",
                "model": "openai/gpt-4.1-mini",
                "api_key": "synthetic-key",
            },
        )
        assert response.status_code == 200
        assert runtime.llm is app.state.llm and runtime.llm is not original
        assert runtime.recaps.llm is runtime.llm
