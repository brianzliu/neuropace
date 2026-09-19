"""Allow an explicitly trusted hosted UI to pair with the loopback service."""

from __future__ import annotations

import secrets

from starlette.datastructures import Headers, QueryParams
from starlette.responses import JSONResponse


class LocalBridgeGuard:
    def __init__(self, app, *, origins: tuple[str, ...], token: str):
        self.app = app
        self.origins = origins
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        scheme = "https" if scope["scheme"] in {"https", "wss"} else "http"
        same_origin = origin == f"{scheme}://{headers.get('host', '')}"
        cross_origin = (origin is not None and not same_origin) or (
            headers.get("sec-fetch-site") == "cross-site"
        )
        if not cross_origin:
            return await self.app(scope, receive, send)

        # Media elements may omit Origin; their URL must still carry the pairing token.
        media_request = scope["type"] == "http" and scope["path"].startswith("/media/")
        allowed = origin in self.origins or (origin is None and media_request)
        token = headers.get("x-reflow-token", "")
        if scope["type"] == "websocket" or media_request:
            token = QueryParams(scope.get("query_string", b"")).get("pairing_token", token)
        if not allowed or not secrets.compare_digest(token.encode(), self.token.encode()):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 4401})
            else:
                response = JSONResponse(
                    {"detail": "Website not allowed" if not allowed else "Pairing code required"},
                    status_code=403 if not allowed else 401,
                )
                await response(scope, receive, send)
            return
        return await self.app(scope, receive, send)
