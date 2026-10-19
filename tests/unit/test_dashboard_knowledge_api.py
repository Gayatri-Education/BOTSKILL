"""Unit tests for Phase 9 — Knowledge Ingestion & Policy Matrix Management."""

import io
import pytest
from fastapi.testclient import TestClient

from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.knowledge.parsers import MAX_FILE_SIZE_BYTES
from botskill.storage.database import DatabaseManager


@pytest.fixture
def knowledge_setup():
    session_mgr = SessionManager()
    db_mgr = DatabaseManager(":memory:")
    app = create_app(
        db_manager=db_mgr,
        session_manager=session_mgr,
    )
    client = TestClient(app)
    return client, session_mgr, db_mgr


def test_document_upload_and_rule_extraction(knowledge_setup):
    client, session_mgr, db_mgr = knowledge_setup

    sample_policy_content = (
        "# Aivara Technologies Human Resources Policy\n\n"
        "## Section 1: Working Environment\n"
        "All engineering internships are conducted in a 100% remote format across India.\n\n"
        "## Section 2: Compensation Guidelines\n"
        "Internship stipend numbers and salary figures must never be quoted prior to the technical interview. "
        "Compensation is strictly formalized in approved offer letters.\n"
    )

    file_bytes = io.BytesIO(sample_policy_content.encode("utf-8"))

    # Upload requires CSRF token because it is a POST mutating operation
    res_no_csrf = client.post(
        "/api/knowledge/upload",
        files={"file": ("hr_policy.md", file_bytes, "text/markdown")},
    )
    assert res_no_csrf.status_code == 403

    file_bytes.seek(0)
    upload_res = client.post(
        "/api/knowledge/upload",
        files={"file": ("hr_policy.md", file_bytes, "text/markdown")},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert upload_res.status_code == 200
    data = upload_res.json()

    assert data["filename"] == "hr_policy.md"
    assert len(data["content_hash"]) == 64
    assert data["classification"]["department"] == "hr"
    assert data["extracted_rules_count"] >= 1
    assert any("STIPEND" in r["rule_id"] for r in data["extracted_rules"])

    # Invariant: Extracted rules must be inactive until human approval
    for rule in data["extracted_rules"]:
        assert rule["is_active"] is False

    # Check database persistence
    repo = db_mgr.get_repository()
    db_rules = repo.list_all_rules()
    assert len(db_rules) >= 1


def test_rules_listing(knowledge_setup):
    client, session_mgr, db_mgr = knowledge_setup

    response = client.get("/api/knowledge/rules")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) >= 1
    assert any("RULE-" in r["rule_id"] for r in rules)


def test_human_rule_approval_and_deactivation_transition(knowledge_setup):
    client, session_mgr, db_mgr = knowledge_setup

    # 1. Upload document to generate candidate rules
    content = "## HR Stipend Policy\nInternship stipend compensation must never be promised in advance."
    file_bytes = io.BytesIO(content.encode("utf-8"))

    upload_res = client.post(
        "/api/knowledge/upload",
        files={"file": ("policy.txt", file_bytes, "text/plain")},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert upload_res.status_code == 200
    candidate_rules = upload_res.json()["extracted_rules"]
    assert len(candidate_rules) > 0

    target_rule_id = candidate_rules[0]["rule_id"]
    repo = db_mgr.get_repository()
    initial_rule = repo.get_rule(target_rule_id)
    assert initial_rule.is_active is False

    # 2. Human approval to activate rule
    appr_res = client.post(
        f"/api/knowledge/rules/{target_rule_id}/approve",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
    assert appr_res.json()["is_active"] is True

    # Check database reflected transition
    updated_rule = repo.get_rule(target_rule_id)
    assert updated_rule.is_active is True

    # 3. Deactivate rule
    deact_res = client.post(
        f"/api/knowledge/rules/{target_rule_id}/deactivate",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["status"] == "INACTIVE"
    assert deact_res.json()["is_active"] is False

    deactivated_rule = repo.get_rule(target_rule_id)
    assert deactivated_rule.is_active is False


def test_oversized_file_rejection(knowledge_setup):
    client, session_mgr, _ = knowledge_setup

    # Simulate file exceeding 25MB bound
    oversized_data = b"0" * (MAX_FILE_SIZE_BYTES + 1024)
    file_bytes = io.BytesIO(oversized_data)

    res = client.post(
        "/api/knowledge/upload",
        files={"file": ("huge_file.txt", file_bytes, "text/plain")},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert res.status_code == 413
