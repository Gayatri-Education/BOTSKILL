"""Unit tests for Phase 15 — CLI Parity and Agent Skill Integration."""

import io
from datetime import datetime, timezone
from pathlib import Path
import pytest

from botskill.cli import main
from botskill.core.models import (
    DraftReply,
    EmailMessage,
    MessageState,
    PolicyCitation,
    PolicyDecision,
    PolicyRule,
    RuleType,
    SeverityLevel,
)
from botskill.storage.database import DatabaseManager


def test_cli_accounts_list(capsys):
    code = main(["accounts", "list", "--mock"])
    assert code == 0
    captured = capsys.readouterr()
    assert "CONNECTED MAILBOXES" in captured.out
    assert "LEVEL_1_DRAFT_ONLY" in captured.out


def test_cli_drafts_list_and_staging(tmp_path: Path, capsys):
    db_file = tmp_path / "cli_test.db"
    db_mgr = DatabaseManager(str(db_file))
    repo = db_mgr.get_repository()

    now = datetime.now(timezone.utc).isoformat()
    parent_msg = EmailMessage(
        message_id="msg_cli_01",
        provider_id="fake",
        thread_id="th_cli",
        account_id="hr@aivaratech.online",
        sender="intern@corp.com",
        recipients=["hr@aivaratech.online"],
        subject="Intern inquiry",
        body_text="Is it remote?",
        received_at=now,
        state=MessageState.DISCOVERED,
        idempotency_key="key_cli_01",
    )
    repo.insert_message(parent_msg)

    draft = DraftReply(
        draft_id="draft_cli_001",
        message_id="msg_cli_01",
        thread_id="th_cli",
        account_id="hr@aivaratech.online",
        subject="Re: Intern inquiry",
        body_text="Yes, fully remote.",
        citations=[
            PolicyCitation(
                rule_id="RULE-HR-002",
                document_id="doc_hr",
                document_title="HR Guide",
                source_location="Page 1",
                source_quote="Fully remote work across India.",
            )
        ],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Verified against remote policy.",
        model_provenance="Qwen2.5-0.5B-Instruct",
        latency_ms=180.0,
        staged_to_provider=False,
        is_approved=True,
        created_at=now,
    )
    repo.save_draft(draft)

    # 1. Test listing
    code_list = main(["--db", str(db_file), "--mock", "drafts", "list"])
    assert code_list == 0
    out_list = capsys.readouterr().out
    assert "draft_cli_001" in out_list
    assert "[PENDING REVIEW]" in out_list

    # 2. Test staging
    code_stage = main(["--db", str(db_file), "--mock", "drafts", "stage", "draft_cli_001"])
    assert code_stage == 0
    out_stage = capsys.readouterr().out
    assert "SUCCESS: Draft 'draft_cli_001' safely staged" in out_stage
    assert "DRAFT_ONLY invariant enforced" in out_stage

    # Verify marked staged in database
    updated = repo.get_draft("draft_cli_001")
    assert updated.staged_to_provider is True


def test_cli_policy_management(tmp_path: Path, capsys):
    db_file = tmp_path / "policy_cli.db"
    db_mgr = DatabaseManager(str(db_file))
    repo = db_mgr.get_repository()

    now = datetime.now(timezone.utc).isoformat()
    rule = PolicyRule(
        rule_id="RULE-SEC-099",
        title="Password Protection",
        rule_type=RuleType.PROHIBITION,
        severity=SeverityLevel.CRITICAL,
        condition="Customer asks for credentials",
        required_action="Never disclose passwords or tokens",
        prohibited_actions=["share_password"],
        source_document_id="doc_sec",
        source_location="Page 1",
        source_quote="Never share passwords under any circumstances.",
        is_active=False,
        created_at=now,
    )
    repo.insert_rule(rule)

    # List rules
    code_list = main(["--db", str(db_file), "policy", "list"])
    assert code_list == 0
    out_list = capsys.readouterr().out
    assert "RULE-SEC-099" in out_list
    assert "[PENDING APPROVAL]" in out_list

    # Approve rule
    code_appr = main(["--db", str(db_file), "policy", "approve", "RULE-SEC-099"])
    assert code_appr == 0
    out_appr = capsys.readouterr().out
    assert "is now ACTIVE" in out_appr

    # Verify active in database
    active_rule = repo.get_rule("RULE-SEC-099")
    assert active_rule.is_active is True


def test_cli_ai_status(capsys):
    code = main(["ai", "status"])
    assert code == 0
    captured = capsys.readouterr()
    assert "LOCAL SLM INTELLIGENCE STATUS" in captured.out
    assert "ZERO CLOUD EGRESS" in captured.out


def test_agent_skill_file_integrity():
    root_dir = Path(__file__).resolve().parent.parent.parent
    skill_file = root_dir / "skill" / "email-responder" / "SKILL.md"

    assert skill_file.exists(), "skill/email-responder/SKILL.md must exist"
    content = skill_file.read_text(encoding="utf-8")

    assert "name: autonomous-email-responder" in content
    assert "Safety Invariant — DRAFT_ONLY by Default" in content
    assert "botskill accounts list" in content
    assert "botskill drafts stage" in content
