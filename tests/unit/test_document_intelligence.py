"""Unit tests for Document Intelligence, Classification, Rule Extraction, and Policy Guardrails."""

import os
import tempfile
import pytest
from botskill.core.models import (
    DraftReply,
    EmailMessage,
    MessageState,
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
from botskill.storage.database import DatabaseManager, StorageRepository


@pytest.fixture
def parser():
    return SafeDocumentParser()


@pytest.fixture
def classifier():
    return DocumentClassifier()


@pytest.fixture
def extractor():
    return RuleExtractor()


@pytest.fixture
def policy_engine():
    db_mgr = DatabaseManager(":memory:")
    repo = StorageRepository(db_mgr)
    return PolicyEngine(repo)


def test_safe_document_parser_text(parser):
    """Test text/markdown parsing and section extraction."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# Aivara HR Policy\n\nEffective date: 2026-01-01\n\nSection 1: Stipend details cannot be promised prior to technical evaluation.")
        tmp_name = f.name

    try:
        res = parser.parse_file(tmp_name)
        assert res.is_success is True
        assert res.file_type == "text"
        assert len(res.sections) >= 2
        assert len(res.content_hash) == 64
    finally:
        os.remove(tmp_name)


def test_document_classification_and_metadata(parser, classifier):
    """Verify document taxonomy detection and mandatory review status."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Company Mandatory Policy for Recruitment.\nEffective Date: 2026-01-01\nAll intern stipends must be approved.")
        tmp_name = f.name

    try:
        parse_res = parser.parse_file(tmp_name)
        meta = classifier.classify(parse_res)
        assert meta.department == "hr"
        assert meta.primary_type == RuleType.MANDATORY_POLICY
        assert meta.effective_from == "2026-01-01"
        assert meta.status == "NEEDS_REVIEW"  # Safety invariant: starts unapproved
    finally:
        os.remove(tmp_name)


def test_rule_extraction_with_provenance_locators(parser, classifier, extractor):
    """Verify candidate rule extraction includes exact section coordinates."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Section 1: Introduction\n\nSection 2: Candidate compensation and stipend policy dictates no upfront quotes.\n\nSection 3: Remote work is permitted.")
        tmp_name = f.name

    try:
        parse_res = parser.parse_file(tmp_name)
        meta = classifier.classify(parse_res)
        rules = extractor.extract_rules(parse_res, meta)

        assert len(rules) >= 2
        stipend_rule = next(r for r in rules if "STIPEND" in r.rule_id)
        assert stipend_rule.rule_type == RuleType.PROHIBITION
        assert "quote_unverified_stipend" in stipend_rule.prohibited_actions
        assert stipend_rule.is_active is False  # Candidate rule starts inactive
    finally:
        os.remove(tmp_name)


def test_policy_engine_blocks_unauthorized_numeric_stipend(policy_engine):
    """Deterministic Safeguard: Model cannot hallucinate numeric stipend amounts."""
    # Seed active approved HR rule into DB
    rule = PolicyRule(
        rule_id="HR-001",
        title="Prohibit Unapproved Stipend Promises",
        rule_type=RuleType.PROHIBITION,
        severity=SeverityLevel.HIGH,
        condition="A reply discusses stipend or compensation",
        required_action="Decline to quote numbers before interview",
        prohibited_actions=["quote_unverified_stipend"],
        source_document_id="doc_hr_2026",
        source_location="Section 3.2, Page 4",
        source_quote="No unapproved stipend promises.",
        is_active=True,
    )
    policy_engine.storage.insert_rule(rule)

    inbound = EmailMessage(
        message_id="msg_inbound",
        provider_id="outlook_com",
        thread_id="th_1",
        account_id="hr@aivaratech.online",
        sender="student@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Internship Stipend Query",
        body_text="What is the monthly stipend?",
        received_at="2026-10-20T01:00:00Z",
        idempotency_key="key_1",
    )

    # 1. Hallucinated draft with unapproved numeric promise ($1,500 per month)
    bad_draft = DraftReply(
        draft_id="draft_bad",
        message_id="msg_inbound",
        thread_id="th_1",
        account_id="hr@aivaratech.online",
        subject="Re: Internship Stipend Query",
        body_text="The stipend is $1500 per month. Welcome aboard!",
    )
    evaluated_bad = policy_engine.evaluate_draft(bad_draft, inbound)
    assert evaluated_bad.policy_decision == PolicyDecision.BLOCK
    assert "Draft promises unapproved numeric compensation" in evaluated_bad.decision_reason

    # 2. Compliant grounded draft without numeric promise
    good_draft = DraftReply(
        draft_id="draft_good",
        message_id="msg_inbound",
        thread_id="th_1",
        account_id="hr@aivaratech.online",
        subject="Re: Internship Stipend Query",
        body_text="Stipend details are communicated post-interview in the formal offer letter.",
    )
    evaluated_good = policy_engine.evaluate_draft(good_draft, inbound)
    assert evaluated_good.policy_decision == PolicyDecision.PASS
    assert len(evaluated_good.citations) == 1
    assert evaluated_good.citations[0].rule_id == "HR-001"
