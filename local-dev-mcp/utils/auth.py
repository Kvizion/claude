"""Token authentication middleware for the network (HTTP/SSE) transports.

When a shared secret is configured, every HTTP request must present it as
``Authorization: Bearer <token>`` or ``X-API-Key: <token>``. This keeps the
endpoint from being an open "run anything on my machine" service when exposed
through a tunnel. The stdio transport is local-only and is never wrapped.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._token = token

    def _extract(self, request) -> str | None:
        api_key = request.headers.get("x-api-key")
        if api_key:
            return api_key
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            return header[7:]
        return None

    async def dispatch(self, request, call_next):
        provided = self._extract(request)
        # Constant-time comparison avoids leaking the token through timing.
        if provided is not None and hmac.compare_digest(provided, self._token):
            return await call_next(request)
        return JSONResponse(
            {"error": "unauthorized", "detail": "Missing or invalid API token."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


def wrap_with_auth(app, token: str):
    """Return ``app`` wrapped so all HTTP requests require the shared secret."""
    return TokenAuthMiddleware(app, token)
