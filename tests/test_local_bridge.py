"""Hosted UI access must be paired; ordinary local use stays available."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ORIGIN = "https://neurospace-hackmit.vercel.app"


def test_hosted_rest_requires_origin_and_pairing(app):
    with TestClient(app) as client:
        path = "/api/learners"
        assert client.get(path).status_code == 200
        assert client.get(path, headers={"Origin": "http://testserver"}).status_code == 200
        assert client.get(path, headers={"Origin": ORIGIN}).status_code == 401
        headers = {"Origin": ORIGIN, "X-NeuroPace-Token": app.state.pairing_token}
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN
        headers["Origin"] = "https://untrusted.example"
        assert client.get(path, headers=headers).status_code == 403
        assert client.post(path, json={"name": "Blocked"}, headers={"Origin": "null"}).status_code == 403


def test_preflight_and_media(app):
    with TestClient(app) as client:
        response = client.options(
            "/api/learners",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-neuropace-token",
            },
        )
        assert response.status_code == 200
        headers = {"Sec-Fetch-Site": "cross-site"}
        assert client.get("/media/missing", headers=headers).status_code == 401
        response = client.get(
            "/media/missing", params={"pairing_token": app.state.pairing_token}, headers=headers
        )
        assert response.status_code == 404  # Authorized, but the media does not exist.


def test_legacy_pairing_header_remains_accepted_during_migration(app):
    with TestClient(app) as client:
        response = client.get(
            "/api/bridge/check",
            headers={"Origin": ORIGIN, "X-Reflow-Token": app.state.pairing_token},
        )
        assert response.status_code == 200


def test_hosted_websocket_requires_pairing(app):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/ws/session/missing", headers={"Origin": ORIGIN}):
                pass
        assert rejected.value.code == 4401
        token = app.state.pairing_token
        with client.websocket_connect(
            f"/ws/session/missing?pairing_token={token}", headers={"Origin": ORIGIN}
        ) as socket:
            assert socket.receive_json()["text"] == "unknown session"
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/ws/session/missing?pairing_token={token}",
                headers={"Origin": "https://untrusted.example"},
            ):
                pass
