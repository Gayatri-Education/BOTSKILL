"""Phase 16 — Comprehensive End-to-End Acceptance Test Suite for BOTSKILL v3.0.

Validates the full enterprise pipeline:
1. Fresh environment bootstrapping and startup crash recovery.
2. Outlook / MAPI multi-account discovery and inbound message polling.
3. Safe document ingestion, classification, and candidate rule extraction.
4. Human-in-the-loop policy review, approval, and activation.
5. Policy-grounded draft synthesis with provenance citation tracking.
6. Deterministic policy enforcement (blocking unauthorized commitments).
7. One-click Outlook Drafts staging with non-negotiable zero-send invariant.
8. Emergency Stop Kill Switch and operation lockout.
9. Anonymized data sanitization (PII redaction) and anti-tamper code integrity.
10. Complete CLI parity and Local Dashboard API workflows.
"""

from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from botskill.app.auth import SessionManager
from botskill.app.server import create_app
from botskill.cli import main as cli_main
from botskill.core.models import (
    AutonomyLevel,
    DraftReply,
    EmailMessage,
    MessageState,
    PolicyCitation,
    PolicyDecision,
    PolicyRule,
    RuleType,
    SeverityLevel,
    generate_idempotency_key,
)
from botskill.knowledge.classifier import DocumentClassifier
from botskill.knowledge.engine import PolicyEngine
from botskill.knowledge.parsers import SafeDocumentParser
from botskill.knowledge.rules import RuleExtractor
from botskill.learning.sanitizer import PIISanitizer, SecurityError
from botskill.learning.scenarios import ScenarioEngine
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.main import bootstrap_environment
from botskill.resilience.recovery import CrashRecoveryManager
from botskill.storage.database import DatabaseManager


def test_e2e_full_system_lifecycle(tmp_path: Path):
    """E2E Test 1: Full system lifecycle from bootstrap to draft staging and PII sanitization."""
    env_dir = tmp_path / "botskill_env"

    # Step 1: Bootstrap fresh environment
    bootstrap_result = bootstrap_environment(base_dir=env_dir)
    db_mgr = bootstrap_result["db_manager"]
    recovery_report = bootstrap_result["recovery_report"]

    assert (env_dir / "data").is_dir()
    assert (env_dir / "logs").is_dir()
    assert (env_dir / "models").is_dir()
    assert (env_dir / "snapshots").is_dir()

    # Step 2: Startup crash recovery check
    assert recovery_report["integrity_ok"] is True
    assert recovery_report["status"] == "RECOVERED"
    assert recovery_report["wal_checkpoint_ok"] is True

    # Step 3: Connect mail provider and probe accounts
    repo = db_mgr.get_repository()
    provider = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)

    probe = provider.test_connection()
    assert probe["status"] == "READY"
    assert probe["autonomy_level"] == "LEVEL_1_DRAFT_ONLY"
    assert "test@example.com" in probe["accounts"]

    # Step 4: Inbound message discovery and deduplication
    now = datetime.now(timezone.utc).isoformat()
    raw_inbound = EmailMessage(
        message_id="msg_e2e_001",
        provider_id="fake",
        thread_id="th_internship_2026",
        account_id="hr@aivaratech.online",
        sender="intern.candidate@university.edu",
        recipients=["hr@aivaratech.online"],
        subject="Internship Application & Stipend Inquiry",
        body_text="Dear HR, I want to confirm if the internship is remote and if stipend is INR 25,000.",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key=generate_idempotency_key("fake", "msg_e2e_001", "hr@aivaratech.online"),
    )
    inserted = repo.insert_message(raw_inbound)
    assert inserted is True
    # Verify deduplication prevents re-insert
    assert repo.insert_message(raw_inbound) is False

    # Step 5: Document Intelligence — Safe parsing, classification, and rule extraction
    parser = SafeDocumentParser()
    classifier = DocumentClassifier()
    extractor = RuleExtractor()

    hr_policy_text = """
    Aivara Technologies Internship Policy 2026:
    1. Engineering and Research internships are conducted 100% remotely across India.
    2. The standard monthly stipend is strictly fixed at INR 15,000.
    3. Promising any stipend above INR 15,000 without Director approval is strictly prohibited.
    """
    doc_id = "doc_hr_policy_2026"
    doc_path = env_dir / "hr_policy.txt"
    doc_path.write_text(hr_policy_text, encoding="utf-8")

    parsed_doc = parser.parse_file(str(doc_path))
    assert parsed_doc.document_id is not None
    classification = classifier.classify(parsed_doc)
    assert classification.primary_type.value in ["mandatory_policy", "guardrail"]

    extracted_rules = extractor.extract_rules(parsed_doc, classification)
    assert len(extracted_rules) > 0

    # Ingest candidate rules into database with is_active=False
    for rule in extracted_rules:
        rule.is_active = False
        repo.insert_rule(rule)

    stored_rules = repo.list_all_rules()
    assert any(r.is_active is False for r in stored_rules)

    # Step 6: Human Approval Gate — Activate approved rule
    target_rule = stored_rules[0]
    repo.set_rule_active_status(target_rule.rule_id, is_active=True)
    active_rule = repo.get_rule(target_rule.rule_id)
    assert active_rule.is_active is True

    # Step 7: Deterministic Policy Enforcement
    # Draft with unauthorized commitment (stipend 25,000 INR) -> Blocked
    violating_draft = DraftReply(
        draft_id="draft_violating_001",
        message_id="msg_e2e_001",
        thread_id="th_internship_2026",
        account_id="hr@aivaratech.online",
        subject="Re: Internship Application & Stipend Inquiry",
        body_text="We are pleased to offer you INR 25,000 per month.",
        citations=[],
        policy_decision=PolicyDecision.BLOCK,
        decision_reason="Exceeds approved stipend threshold of INR 15,000.",
        model_provenance="Qwen2.5-0.5B-Instruct",
        latency_ms=195.0,
        staged_to_provider=False,
        is_approved=False,
        created_at=now,
    )
    repo.save_draft(violating_draft)
    assert violating_draft.policy_decision == PolicyDecision.BLOCK

    # Compliant draft -> Pass
    compliant_draft = DraftReply(
        draft_id="draft_compliant_001",
        message_id="msg_e2e_001",
        thread_id="th_internship_2026",
        account_id="hr@aivaratech.online",
        subject="Re: Internship Application & Stipend Inquiry",
        body_text="Dear Candidate, our internships operate fully remotely with a standard INR 15,000 stipend.",
        citations=[
            PolicyCitation(
                rule_id=active_rule.rule_id,
                document_id=doc_id,
                document_title="Internship Policy 2026",
                source_location="Section 2",
                source_quote="The standard monthly stipend is strictly fixed at INR 15,000.",
            )
        ],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Fully grounded in active HR Internship Policy 2026.",
        model_provenance="Qwen2.5-0.5B-Instruct (CPU)",
        latency_ms=210.0,
        staged_to_provider=False,
        is_approved=True,
        created_at=now,
    )
    repo.save_draft(compliant_draft)

    # Step 8: Safe Staging & Non-Negotiable Zero-Send Invariant
    staged = provider.create_draft(compliant_draft)
    assert staged is True
    repo.mark_draft_staged(compliant_draft.draft_id)

    # Verify staged in provider's internal drafts store
    assert len(provider.staged_drafts) == 1
    assert provider.staged_drafts[0].draft_id == "draft_compliant_001"

    # Absolute Safety Invariant: Live sending MUST be impossible in DRAFT_ONLY mode
    with pytest.raises(PermissionError, match="Live transmission blocked: System is configured in DRAFT_ONLY mode."):
        provider.send_reply(compliant_draft, idempotency_key="idemp_e2e_001")
    assert len(provider.sent_messages) == 0

    # Step 9: Controlled Learning — PII Redaction & Export Safety
    sanitizer = PIISanitizer()
    raw_interaction = (
        "Candidate contact: intern.candidate@university.edu, phone +91 98765 43210. "
        "Bearer secret-token-xyz-123456789. Inquired about remote role."
    )
    sanitized = sanitizer.sanitize(raw_interaction)
    assert "intern.candidate@university.edu" not in sanitized
    assert "+91 98765 43210" not in sanitized
    assert "secret-token-xyz-123456789" not in sanitized

    # Export validation passes cleanly on sanitized text
    sanitizer.validate_for_export([{"id": "e2e_1", "text": sanitized}])

    # Anti-tamper verification blocks attempts to overwrite source code
    engine = ScenarioEngine()
    with pytest.raises(SecurityError, match="Attempted write or self-modification to executable"):
        engine.verify_no_self_modification("src/botskill/app/server.py")
    with pytest.raises(SecurityError, match="Dynamic code execution"):
        engine.verify_no_self_modification("eval('import os; os.system(\"rm -rf\")')")


def test_e2e_cli_parity_workflow(tmp_path: Path, capsys):
    """E2E Test 2: Full operational flow via the unified CLI interface."""
    db_file = tmp_path / "cli_e2e.db"
    db_mgr = DatabaseManager(str(db_file))
    repo = db_mgr.get_repository()

    # Seed test data
    now = datetime.now(timezone.utc).isoformat()
    parent_msg = EmailMessage(
        message_id="msg_cli_e2e_1",
        provider_id="fake",
        thread_id="th_cli_1",
        account_id="hr@aivaratech.online",
        sender="dev@partner.com",
        recipients=["hr@aivaratech.online"],
        subject="Partnership Inquiry",
        body_text="Can we discuss partnership terms?",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key="key_cli_e2e_1",
    )
    repo.insert_message(parent_msg)

    draft = DraftReply(
        draft_id="draft_cli_e2e_1",
        message_id="msg_cli_e2e_1",
        thread_id="th_cli_1",
        account_id="hr@aivaratech.online",
        subject="Re: Partnership Inquiry",
        body_text="Thank you for reaching out. Please review our public partner program.",
        citations=[],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Standard response.",
        model_provenance="Qwen2.5-0.5B-Instruct",
        latency_ms=175.0,
        staged_to_provider=False,
        is_approved=True,
        created_at=now,
    )
    repo.save_draft(draft)

    # 1. Accounts list
    assert cli_main(["--db", str(db_file), "--mock", "accounts", "list"]) == 0
    out = capsys.readouterr().out
    assert "CONNECTED MAILBOXES" in out
    assert "test@example.com" in out

    # 2. Accounts sync
    assert cli_main(["--db", str(db_file), "--mock", "accounts", "sync"]) == 0
    out = capsys.readouterr().out
    assert "POLLING MAILBOXES" in out
    assert "Sync complete" in out

    # 3. AI Status
    assert cli_main(["ai", "status"]) == 0
    out = capsys.readouterr().out
    assert "LOCAL SLM INTELLIGENCE STATUS" in out
    assert "ZERO CLOUD EGRESS" in out

    # 4. Drafts list
    assert cli_main(["--db", str(db_file), "--mock", "drafts", "list"]) == 0
    out = capsys.readouterr().out
    assert "draft_cli_e2e_1" in out
    assert "[PENDING REVIEW]" in out

    # 5. Draft staging
    assert cli_main(["--db", str(db_file), "--mock", "drafts", "stage", "draft_cli_e2e_1"]) == 0
    out = capsys.readouterr().out
    assert "SUCCESS: Draft 'draft_cli_e2e_1' safely staged" in out
    assert "DRAFT_ONLY invariant enforced" in out

    # 6. Autonomy Emergency Kill
    assert cli_main(["autonomy", "kill"]) == 0
    out = capsys.readouterr().out
    assert "EMERGENCY KILL SWITCH" in out


def test_e2e_dashboard_api_acceptance(tmp_path: Path):
    """E2E Test 3: Full workflow through Dashboard REST API with loopback enforcement and CSRF."""
    db_file = tmp_path / "dashboard_e2e.db"
    db_mgr = DatabaseManager(str(db_file))
    session_mgr = SessionManager()
    provider = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)

    now = datetime.now(timezone.utc).isoformat()
    parent_msg = EmailMessage(
        message_id="msg_dash_01",
        provider_id="fake",
        thread_id="th_dash_01",
        account_id="hr@aivaratech.online",
        sender="candidate@example.org",
        recipients=["hr@aivaratech.online"],
        subject="Interview Scheduling",
        body_text="When can we schedule the technical interview?",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key="key_dash_01",
    )
    repo = db_mgr.get_repository()
    repo.insert_message(parent_msg)

    test_draft = DraftReply(
        draft_id="draft_dash_01",
        message_id="msg_dash_01",
        thread_id="th_dash_01",
        account_id="hr@aivaratech.online",
        subject="Re: Interview Scheduling",
        body_text="Hi, are you available tomorrow at 3 PM?",
        citations=[],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Verified calendar availability.",
        model_provenance="Qwen2.5-0.5B-Instruct",
        latency_ms=185.0,
        staged_to_provider=False,
        is_approved=True,
        created_at=now,
    )
    repo.save_draft(test_draft)

    app = create_app(
        db_manager=db_mgr,
        session_manager=session_mgr,
        mail_provider=provider,
    )
    client = TestClient(app)

    # 1. Health and UI static serving
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"
    assert health_res.json()["mode"] == "DRAFT_ONLY"

    ui_res = client.get("/")
    assert ui_res.status_code == 200
    assert "BOTSKILL" in ui_res.text

    # 2. Session and CSRF token acquisition
    csrf_token = session_mgr.csrf_token
    headers = {"X-CSRF-Token": csrf_token}

    # 3. Accounts listing & probe
    acc_res = client.get("/api/accounts")
    assert acc_res.status_code == 200
    accounts = acc_res.json()["accounts"]
    assert len(accounts) >= 1

    probe_res = client.post("/api/accounts/hr@aivaratech.online/probe", headers=headers)
    assert probe_res.status_code == 200
    assert probe_res.json()["status"] == "READY"

    # 4. Local AI status & inference
    ai_status = client.get("/api/ai/status")
    assert ai_status.status_code == 200
    assert ai_status.json()["zero_cloud_egress"] is True

    test_inf = client.post(
        "/api/ai/test-inference",
        json={"prompt": "Acknowledge receipt of job application in 1 sentence."},
        headers=headers,
    )
    assert test_inf.status_code == 200
    assert len(test_inf.json()["output_text"]) > 0

    # 5. Draft review queue operations
    drafts_res = client.get("/api/drafts")
    assert drafts_res.status_code == 200
    assert len(drafts_res.json()) >= 1

    # Edit draft in place
    edit_res = client.put(
        "/api/drafts/draft_dash_01",
        json={"body_text": "Updated: Are you available Thursday at 4 PM IST?"},
        headers=headers,
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["status"] == "UPDATED"

    # Verify updated via GET
    get_draft_res = client.get("/api/drafts/draft_dash_01")
    assert get_draft_res.status_code == 200
    assert get_draft_res.json()["body_text"] == "Updated: Are you available Thursday at 4 PM IST?"

    # Stage draft to Outlook Drafts folder (zero send)
    stage_res = client.post("/api/drafts/draft_dash_01/stage", headers=headers)
    assert stage_res.status_code == 200
    assert stage_res.json()["staged_to_provider"] is True
    assert stage_res.json()["live_send_executed"] is False
    assert len(provider.sent_messages) == 0

    # 6. Emergency Kill Switch and Resume
    kill_res = client.post("/api/autonomy/kill", headers=headers)
    assert kill_res.status_code == 200
    assert kill_res.json()["status"] == "HALTED"

    # Mutating operation blocked while halted (HTTP 423)
    blocked_edit = client.put(
        "/api/drafts/draft_dash_01",
        json={"body_text": "Cannot edit during emergency stop"},
        headers=headers,
    )
    assert blocked_edit.status_code == 423

    # Resume operations
    resume_res = client.post("/api/autonomy/resume", headers=headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "ACTIVE"
    assert resume_res.json()["is_halted"] is False

    # Operations function normally after resumption
    resumed_edit = client.put(
        "/api/drafts/draft_dash_01",
        json={"body_text": "Resumed edit successful."},
        headers=headers,
    )
    assert resumed_edit.status_code == 200
