"""Unit tests for Phase 7 — Local Dashboard Foundation & Loopback Server."""

import pytest
from fastapi.testclient import TestClient

from botskill.app.auth import SessionManager
from botskill.app.server import create_app


def test_loopback_binding_rejection():
    """Verify that attempting to bind to non-loopback address raises a ValueError."""
    with pytest.raises(ValueError, match="Security violation: BOTSKILL server must bind strictly to a loopback"):
        create_app(host="0.0.0.0")

    with pytest.raises(ValueError, match="Security violation"):
        create_app(host="192.168.1.50")


def test_health_endpoint():
    """Verify health endpoint reports correct metadata and DRAFT_ONLY mode."""
    app = create_app(host="127.0.0.1", port=8765)
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "BOTSKILL"
    assert data["version"] == "3.0.0"
    assert data["mode"] == "DRAFT_ONLY"
    assert data["loopback_only"] is True


def test_dashboard_html_serving():
    """Verify that root GET / serves the approved dashboard HTML."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "BOTSKILL" in response.text
    assert "Autonomous Local Email Workstation" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_security_headers_present():
    """Verify defense-in-depth security headers are attached to responses."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "same-origin"


def test_csrf_protection_and_session():
    """Verify CSRF token generation and enforcement on mutating requests."""
    session_manager = SessionManager()
    app = create_app(session_manager=session_manager)
    client = TestClient(app)

    # 1. Retrieve session
    sess_res = client.get("/api/auth/session")
    assert sess_res.status_code == 200
    sess_data = sess_res.json()
    assert sess_data["csrf_token"] == session_manager.csrf_token

    # 2. Mutating request without CSRF token -> 403 Forbidden
    res_no_csrf = client.post("/api/auth/verify")
    assert res_no_csrf.status_code == 403
    assert "CSRF validation failed" in res_no_csrf.json()["detail"]

    # 3. Mutating request with invalid CSRF token -> 403 Forbidden
    res_bad_csrf = client.post(
        "/api/auth/verify",
        headers={"X-CSRF-Token": "invalid_forged_token_12345"},
    )
    assert res_bad_csrf.status_code == 403

    # 4. Mutating request with valid CSRF token -> 200 OK
    res_valid = client.post(
        "/api/auth/verify",
        headers={"X-CSRF-Token": session_manager.csrf_token},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["csrf_valid"] is True


def test_external_ip_rejected():
    """Verify that requests simulated from external non-loopback IP are blocked."""
    app = create_app()
    client = TestClient(app, client=("192.168.1.100", 54321))

    response = client.get("/api/health")
    assert response.status_code == 403
    assert "Access denied. Requests are restricted to loopback" in response.json()["detail"]
