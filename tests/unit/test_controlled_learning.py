"""Unit tests for Phase 11 — Controlled Learning, Sanitized Export, and Governance."""

import pytest
from fastapi.testclient import TestClient

from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.core.models import EmailMessage, MessageState
from botskill.learning.sanitizer import PIISanitizer, SecurityError
from botskill.learning.scenarios import ScenarioEngine
from botskill.storage.database import DatabaseManager


def test_pii_sanitizer_redacts_sensitive_data():
    sanitizer = PIISanitizer()

    raw_text = (
        "Applicant John Doe (john.doe@gmail.com, +91 98765 43210) applied for engineering. "
        "Credentials: password: SuperSecretPassword123, api_key: sk-1234567890abcdef12345, "
        "auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.card: 4111 2222 3333 4444."
    )

    clean_text = sanitizer.sanitize(raw_text)

    assert "john.doe@gmail.com" not in clean_text
    assert "[REDACTED_EMAIL]" in clean_text
    assert "98765" not in clean_text
    assert "[REDACTED_PHONE]" in clean_text
    assert "SuperSecretPassword123" not in clean_text
    assert "[REDACTED_SECRET]" in clean_text
    assert "sk-1234567890abcdef12345" not in clean_text
    assert "[REDACTED_API_KEY]" in clean_text
    assert "4111 2222 3333 4444" not in clean_text
    assert "[REDACTED_CARD]" in clean_text


def test_export_validation_strictly_rejects_raw_pii():
    sanitizer = PIISanitizer()

    dirty_payload = [
        {"id": "1", "text": "Contact candidate at candidate.real@corp.com for offer."},
    ]

    with pytest.raises(SecurityError, match="Detected raw sensitive data"):
        sanitizer.validate_for_export(dirty_payload)

    clean_payload = [
        {"id": "1", "text": "Contact candidate at [REDACTED_EMAIL] for offer."},
    ]
    # Passes without raising error
    sanitizer.validate_for_export(clean_payload)


def test_scenario_proposal_and_synthetic_test_synthesis():
    engine = ScenarioEngine()

    msg = EmailMessage(
        message_id="msg_real_001",
        provider_id="outlook",
        thread_id="inquiry about compensation",
        account_id="hr@aivaratech.online",
        sender="intern.candidate@university.edu",
        recipients=["hr@aivaratech.online"],
        subject="Internship Application & Stipend Inquiry",
        body_text="Dear HR, can you share the stipend for the remote python role? My phone is +1-555-123-4567.",
        received_at="2026-10-20T00:00:00Z",
        state=MessageState.DISCOVERED,
        idempotency_key="key_001",
    )

    candidate = engine.propose_from_message(msg)

    assert candidate.archetype == "INTERNSHIP_COMPENSATION_INQUIRY"
    assert "RULE-HR-001" in candidate.suggested_rules
    assert "+1-555-123-4567" not in candidate.sanitized_body
    assert "[REDACTED_PHONE]" in candidate.sanitized_body
    assert candidate.is_approved is False  # Must require supervisor approval

    # Generate synthetic regression test fixture
    synth = engine.generate_synthetic_test(candidate)
    assert synth["test_id"].startswith("test_scen_")
    assert synth["expected_policy_enforcement"]["must_block_unauthorized_numbers"] is True
    assert synth["expected_policy_enforcement"]["mode"] == "DRAFT_ONLY"


def test_code_self_modification_prevention():
    engine = ScenarioEngine()

    with pytest.raises(SecurityError, match="Attempted write or self-modification to executable"):
        engine.verify_no_self_modification("src/botskill/app/server.py")

    with pytest.raises(SecurityError, match="Attempted write or self-modification to executable"):
        engine.verify_no_self_modification("run_botskill.bat")

    with pytest.raises(SecurityError, match="Dynamic code execution"):
        engine.verify_no_self_modification("eval('import os; os.system(\"rm -rf\")')")


def test_learning_api_endpoints():
    session_mgr = SessionManager()
    db_mgr = DatabaseManager(":memory:")
    app = create_app(db_manager=db_mgr, session_manager=session_mgr)
    client = TestClient(app)

    # 1. List scenarios
    scen_res = client.get("/api/learning/scenarios")
    assert scen_res.status_code == 200
    assert len(scen_res.json()) >= 1

    # 2. Propose candidate requires CSRF
    res_no_csrf = client.post(
        "/api/learning/propose",
        json={"subject": "Stipend question", "body_text": "What is the pay?"},
    )
    assert res_no_csrf.status_code == 403

    res_ok = client.post(
        "/api/learning/propose",
        json={"subject": "Stipend question", "body_text": "What is the pay?"},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["archetype"] == "INTERNSHIP_COMPENSATION_INQUIRY"

    # 3. Export sanitized dataset
    exp_res = client.post(
        "/api/learning/export",
        json={"include_scenarios": True},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert exp_res.status_code == 200
    assert exp_res.json()["pii_verified_clean"] is True

    # 4. Verify safety endpoint blocks dangerous modifications
    blocked_res = client.post(
        "/api/learning/verify-safety",
        json={"target": "malicious_script.py"},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert blocked_res.status_code == 403
    assert "Attempted write or self-modification" in blocked_res.json()["detail"]
