"""FastAPI Local Loopback Server for BOTSKILL v3.0."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from botskill.app.auth import (
    LoopbackEnforcementMiddleware,
    SessionManager,
    get_csrf_verifier,
)
from botskill.storage.database import DatabaseManager


def create_app(
    db_manager: Optional[DatabaseManager] = None,
    session_manager: Optional[SessionManager] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    static_dir: Optional[Path] = None,
) -> FastAPI:
    """Creates and configures the FastAPI application bound for local loopback."""

    # Invariant: Host must be loopback only
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            f"Security violation: BOTSKILL server must bind strictly to a loopback address. Received: {host}"
        )

    if session_manager is None:
        session_manager = SessionManager()

    if static_dir is None:
        static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(
        title="BOTSKILL Autonomous Email Workstation",
        version="3.0.0",
        description="Local-First enterprise email co-pilot and policy automation runtime",
        docs_url="/docs" if os.environ.get("BOTSKILL_ENV") == "development" else None,
        redoc_url=None,
    )

    # Restrict CORS to local loopback origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    # Add loopback enforcement and security headers
    app.add_middleware(LoopbackEnforcementMiddleware)

    # Store shared services in application state
    app.state.db_manager = db_manager
    app.state.session_manager = session_manager
    app.state.host = host
    app.state.port = port
    app.state.draft_only = True

    csrf_verifier = get_csrf_verifier(session_manager)

    # Mount static assets if the folder exists
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", summary="Dashboard Root Interface")
    async def serve_dashboard():
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "Dashboard template not found"},
            )
        return FileResponse(str(index_file), media_type="text/html")

    @app.get("/api/health", summary="Health and Operational Status")
    async def get_health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "app": "BOTSKILL",
            "version": "3.0.0",
            "host": host,
            "port": port,
            "mode": "DRAFT_ONLY",
            "loopback_only": True,
            "safety_invariant": "OUTBOUND_SEND_DISABLED",
        }

    @app.get("/api/auth/session", summary="Retrieve active session credentials")
    async def get_session():
        return {
            "session_id": session_manager.session_id,
            "csrf_token": session_manager.csrf_token,
            "created_at": session_manager.created_at,
        }

    @app.post(
        "/api/auth/verify",
        summary="Verify CSRF validation",
        dependencies=[Depends(csrf_verifier)],
    )
    async def verify_csrf_endpoint():
        return {"status": "authenticated", "csrf_valid": True}

    return app
