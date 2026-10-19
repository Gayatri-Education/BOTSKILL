"""Unit tests for Phase 10 — Draft Review Queue, 1-Click Outlook Staging, and Emergency Kill Switch."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.core.models import (
    AutonomyLevel,
    DraftReply,
    EmailMessage,
    MessageState,
    PolicyCitation,
    PolicyDecision,
)
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.storage.database import DatabaseManager


@pytest.fixture
def queue_setup():
    session_mgr = SessionManager()
    db_mgr = DatabaseManager(":memory:")
    fake_mail = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)

    # Seed test draft into database
    now = datetime.now(timezone.utc).isoformat()
    test_draft = DraftReply(
        draft_id="draft-test-101",
        message_id="msg-101",
        thread_id="thread-remote-policy",
        account_id="hr@aivaratech.online",
        subject="Re: Remote Python Role Application",
        body_text="Dear Candidate, our engineering internships are conducted 100% remotely.",
        citations=[
            PolicyCitation(
                rule_id="RULE-HR-002",
                document_id="doc_hr_handbook",
                document_title="HR Handbook",
                source_location="Page 2, Section 1",
                source_quote="Engineering internships operate fully remotely across India.",
            )
        ],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Fully verified against remote work policy.",
        model_provenance="Qwen2.5-0.5B-Instruct-Q4_K_M (Local CPU)",
        latency_ms=210.0,
        staged_to_provider=False,
        is_approved=True,
        created_at=now,
    )
    repo = db_mgr.get_repository()
    parent_msg = EmailMessage(
        message_id="msg-101",
        provider_id="fake",
        thread_id="thread-remote-policy",
        account_id="hr@aivaratech.online",
        sender="candidate@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Remote Python Role Application",
        body_text="Hi, is this position remote?",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key="key_test_101",
    )
    repo.insert_message(parent_msg)
    repo.save_draft(test_draft)

    app = create_app(
        db_manager=db_mgr,
        session_manager=session_mgr,
        mail_provider=fake_mail,
    )
    client = TestClient(app)
    return client, session_mgr, db_mgr, fake_mail, test_draft


def test_draft_review_queue_listing(queue_setup):
    client, session_mgr, db_mgr, _, test_draft = queue_setup

    response = client.get("/api/drafts")
    assert response.status_code == 200
    drafts = response.json()
    assert len(drafts) >= 1

    item = drafts[0]
    assert item["draft_id"] == "draft-test-101"
    assert item["account_id"] == "hr@aivaratech.online"
    assert len(item["citations"]) == 1
    assert item["citations"][0]["rule_id"] == "RULE-HR-002"
    assert item["policy_decision"] == "PASS"


def test_draft_retrieval_by_id(queue_setup):
    client, _, _, _, _ = queue_setup

    response = client.get("/api/drafts/draft-test-101")
    assert response.status_code == 200
    data = response.json()
    assert data["draft_id"] == "draft-test-101"
    assert "100% remotely" in data["body_text"]


def test_in_place_draft_edit(queue_setup):
    client, session_mgr, db_mgr, _, _ = queue_setup

    new_text = "Dear Candidate, Thank you for reaching out. The role is 100% remote across India."

    # Without CSRF -> 403
    res_no_csrf = client.put(
        "/api/drafts/draft-test-101",
        json={"body_text": new_text},
    )
    assert res_no_csrf.status_code == 403

    # With CSRF -> 200
    res_edit = client.put(
        "/api/drafts/draft-test-101",
        json={"body_text": new_text},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["status"] == "UPDATED"

    # Verify updated in database
    repo = db_mgr.get_repository()
    updated = repo.get_draft("draft-test-101")
    assert updated.body_text == new_text


def test_one_click_outlook_staging_preserves_no_send_invariant(queue_setup):
    client, session_mgr, db_mgr, fake_mail, test_draft = queue_setup

    # Stage draft into provider
    stage_res = client.post(
        "/api/drafts/draft-test-101/stage",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert stage_res.status_code == 200
    res_data = stage_res.json()

    assert res_data["staged_to_provider"] is True
    assert res_data["target_folder"] == "Drafts"
    assert res_data["status"] == "STAGED"
    assert res_data["live_send_executed"] is False

    # Invariant Verification: Staged in mail provider drafts list
    assert len(fake_mail.staged_drafts) == 1
    assert fake_mail.staged_drafts[0].draft_id == "draft-test-101"

    # Absolute Safety Invariant: Zero live emails transmitted
    assert len(fake_mail.sent_messages) == 0


def test_emergency_kill_switch_and_locked_operations(queue_setup):
    client, session_mgr, db_mgr, fake_mail, _ = queue_setup

    # 1. Verify initially running
    stat_res = client.get("/api/autonomy/status")
    assert stat_res.status_code == 200
    assert stat_res.json()["is_halted"] is False

    # 2. Trigger Emergency Stop
    kill_res = client.post(
        "/api/autonomy/kill",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert kill_res.status_code == 200
    assert kill_res.json()["status"] == "HALTED"
    assert kill_res.json()["is_halted"] is True

    # 3. Verify mutating operations are locked while halted (HTTP 423)
    locked_edit = client.put(
        "/api/drafts/draft-test-101",
        json={"body_text": "Halted test edit"},
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert locked_edit.status_code == 423
    assert "System is halted by Emergency Stop" in locked_edit.json()["detail"]

    locked_stage = client.post(
        "/api/drafts/draft-test-101/stage",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert locked_stage.status_code == 423

    # 4. Resume operations
    resume_res = client.post(
        "/api/autonomy/resume",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["is_halted"] is False

    # 5. Staging now succeeds again
    ok_stage = client.post(
        "/api/drafts/draft-test-101/stage",
        headers={"X-CSRF-Token": session_mgr.csrf_token},
    )
    assert ok_stage.status_code == 200
    assert ok_stage.json()["staged_to_provider"] is True
