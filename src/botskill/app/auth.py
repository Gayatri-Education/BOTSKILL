"""Session security, CSRF protection, and loopback enforcement for BOTSKILL dashboard."""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class SessionManager:
    """Manages local cryptographically secure sessions and CSRF tokens."""

    def __init__(self, token_file: Optional[Path] = None):
        self.token_file = token_file
        self.session_id: str = secrets.token_hex(32)
        self.csrf_token: str = secrets.token_hex(32)
        self.created_at: float = time.time()

        if self.token_file:
            self.persist_session()

    def persist_session(self) -> None:
        """Saves session token securely to disk for CLI/agent access."""
        if not self.token_file:
            return
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(
            f"SESSION_ID={self.session_id}\nCSRF_TOKEN={self.csrf_token}\n",
            encoding="utf-8",
        )

    def validate_session(self, token: Optional[str]) -> bool:
        if not token:
            return False
        return secrets.compare_digest(token, self.session_id)

    def validate_csrf(self, token: Optional[str]) -> bool:
        if not token:
            return False
        return secrets.compare_digest(token, self.csrf_token)


class LoopbackEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforces that requests to the server originate strictly from loopback interfaces."""

    ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}

    async def dispatch(self, request: Request, call_next) -> Response:
        client_host = request.client.host if request.client else None

        # Always permit in-memory TestClient or loopback interfaces
        if client_host and client_host not in self.ALLOWED_HOSTS:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Forbidden",
                    "detail": f"Access denied. Requests are restricted to loopback interfaces. Received: {client_host}",
                },
            )

        response = await call_next(request)
        # Apply defense-in-depth security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response


csrf_header_scheme = APIKeyHeader(name="X-CSRF-Token", auto_error=False)


def get_csrf_verifier(session_manager: SessionManager):
    """Factory creating a FastAPI dependency that verifies the X-CSRF-Token header."""

    async def verify_csrf_token(
        request: Request,
        token: Optional[str] = Security(csrf_header_scheme),
    ) -> str:
        # Safe methods do not require CSRF token
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return ""

        if not token or not session_manager.validate_csrf(token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed. Missing or invalid X-CSRF-Token header.",
            )
        return token

    return verify_csrf_token
