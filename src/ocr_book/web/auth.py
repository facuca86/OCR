"""Autenticación mínima por token: pensada para una instancia de uso
personal/reducido detrás de un `--token`, no para multi-usuario. Un único
token (variable de entorno `OCRBOOK_WEB_TOKEN`) protege todo salvo
`/login` y los archivos estáticos. Las páginas HTML lo guardan en una
cookie tras el login; la API acepta además `Authorization: Bearer <token>`
para scripts/tests."""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp

COOKIE_NAME = "ocrbook_token"

_EXEMPT_PREFIXES = ("/login", "/static", "/health", "/favicon.ico")


def _is_valid_token(request: Request, expected_token: str) -> bool:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        candidate = auth_header[7:].strip()
        if secrets.compare_digest(candidate, expected_token):
            return True

    cookie_token = request.cookies.get(COOKIE_NAME, "")
    return secrets.compare_digest(cookie_token, expected_token)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, token: str):
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        if not _is_valid_token(request, self._token):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "No autorizado. Falta o es inválido el token de acceso."}, status_code=401)
            next_url = request.url.path
            return RedirectResponse(url=f"/login?next={next_url}", status_code=303)

        return await call_next(request)
