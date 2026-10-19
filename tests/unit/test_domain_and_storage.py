"""Unit tests for BOTSKILL Core Domain Models and SQLite Storage Repository."""

import pytest
from botskill.core.models import (
    AuditEvent,
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
from botskill.storage.database import DatabaseManager, StorageRepository


@pytest.fixture
def repo():
    """Create a temporary in-memory database repository for testing."""
    db_mgr = DatabaseManager(":memory:")
    return StorageRepository(db_mgr)


def test_idempotency_key_generation():
    """Verify deterministic idempotency key computation."""
    key1 = generate_idempotency_key("acc_1", "msg_123", "th_abc")
    key2 = generate_idempotency_key("acc_1", "msg_123", "th_abc")
    key3 = generate_idempotency_key("acc_2", "msg_123", "th_abc")
    
    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 64  # SHA-256


def test_message_insertion_and_deduplication(repo):
    """Test inserting messages and asserting duplicate idempotency keys are rejected."""
    key = generate_idempotency_key("hr@aivaratech.online", "msg_001", "thread_001")
    msg1 = EmailMessage(
        message_id="msg_001",
        provider_id="outlook_com",
        thread_id="thread_001",
        account_id="hr@aivaratech.online",
        sender="candidate@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Internship Application",
        body_text="Here is my resume.",
        received_at="2026-10-20T01:00:00Z",
        state=MessageState.DISCOVERED,
        idempotency_key=key,
    )

    # First insert succeeds
    assert repo.insert_message(msg1) is True

    # Duplicate insert with identical idempotency key is rejected
    assert repo.insert_message(msg1) is False

    # Fetch and verify fields
    fetched = repo.get_message("msg_001")
    assert fetched is not None
    assert fetched.sender == "candidate@example.com"
    assert fetched.recipients == ["hr@aivaratech.online"]
    assert fetched.state == MessageState.DISCOVERED


def test_atomic_lease_claiming(repo):
    """Verify that multiple concurrent workers cannot claim the same message."""
    key = generate_idempotency_key("hr@aivaratech.online", "msg_lease", "thread_lease")
    msg = EmailMessage(
        message_id="msg_lease",
        provider_id="outlook_com",
        thread_id="thread_lease",
        account_id="hr@aivaratech.online",
        sender="worker@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Worker Test",
        body_text="Testing concurrency leases",
        received_at="2026-10-20T01:00:00Z",
        state=MessageState.DISCOVERED,
        idempotency_key=key,
    )
    repo.insert_message(msg)

    # Worker 1 claims lease for 60 seconds
    assert repo.claim_message_lease("msg_lease", lease_owner="worker_1", ttl_seconds=60) is True

    # Worker 2 attempts to claim active lease -> rejected
    assert repo.claim_message_lease("msg_lease", lease_owner="worker_2", ttl_seconds=60) is False

    # Worker 1 can refresh or re-claim when lease expired with 0 ttl
    assert repo.claim_message_lease("msg_lease", lease_owner="worker_1", ttl_seconds=-1) is True
    # Now that it's expired, worker 2 can claim it
    assert repo.claim_message_lease("msg_lease", lease_owner="worker_2", ttl_seconds=60) is True


def test_draft_saving_with_provenance_citations(repo):
    """Test saving and retrieving AI drafts with exact policy citations."""
    key = generate_idempotency_key("hr@aivaratech.online", "msg_draft", "th_draft")
    msg = EmailMessage(
        message_id="msg_draft",
        provider_id="outlook_com",
        thread_id="th_draft",
        account_id="hr@aivaratech.online",
        sender="user@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Internship Stipend Query",
        body_text="What is the stipend?",
        received_at="2026-10-20T01:00:00Z",
        state=MessageState.PARSED,
        idempotency_key=key,
    )
    repo.insert_message(msg)

    citation = PolicyCitation(
        rule_id="HR-001",
        document_id="doc_hr_2026",
        document_title="Aivara HR Policy 2026",
        source_location="Section 3.2, Page 4",
        source_quote="Stipends cannot be quoted prior to technical interview shortlisting.",
        confidence=0.98,
    )

    draft = DraftReply(
        draft_id="draft_001",
        message_id="msg_draft",
        thread_id="th_draft",
        account_id="hr@aivaratech.online",
        subject="Re: Internship Stipend Query",
        body_text="Stipend details are shared following technical evaluation.",
        citations=[citation],
        policy_decision=PolicyDecision.PASS,
        decision_reason="Grounded strictly in HR-001",
        model_provenance="local-slm-qwen2.5-0.5b",
        latency_ms=310.5,
    )

    repo.save_draft(draft)
    fetched = repo.get_draft("draft_001")
    assert fetched is not None
    assert fetched.subject == "Re: Internship Stipend Query"
    assert len(fetched.citations) == 1
    assert fetched.citations[0].rule_id == "HR-001"
    assert fetched.citations[0].source_location == "Section 3.2, Page 4"
    assert fetched.policy_decision == PolicyDecision.PASS
    assert fetched.staged_to_provider is False


def test_policy_rules_repository(repo):
    """Test inserting and listing active policy rules."""
    rule1 = PolicyRule(
        rule_id="HR-001",
        title="Prohibit Unapproved Stipend Promises",
        rule_type=RuleType.PROHIBITION,
        severity=SeverityLevel.HIGH,
        condition="Response mentions compensation or stipend",
        required_action="Decline to quote numbers before interview",
        prohibited_actions=["quote_unverified_stipend"],
        source_document_id="doc_hr_2026",
        source_location="Section 3.2, Page 4",
        source_quote="No unapproved stipend promises.",
        is_active=True,
    )
    rule2 = PolicyRule(
        rule_id="HR-OLD",
        title="Deprecated Policy",
        rule_type=RuleType.MANDATORY_POLICY,
        severity=SeverityLevel.LOW,
        condition="Old rule",
        source_document_id="doc_old",
        source_location="Page 1",
        source_quote="Old policy",
        is_active=False,  # Inactive
    )

    repo.insert_rule(rule1)
    repo.insert_rule(rule2)

    active_rules = repo.list_active_rules()
    assert len(active_rules) == 1
    assert active_rules[0].rule_id == "HR-001"
    assert active_rules[0].prohibited_actions == ["quote_unverified_stipend"]


def test_audit_event_logging(repo):
    """Test structured audit event persistence."""
    event = AuditEvent(
        event_id="ev_001",
        event_type="MESSAGE_DISCOVERED",
        account_id="hr@aivaratech.online",
        message_id="msg_001",
        severity=SeverityLevel.LOW,
        details={"source": "outlook_mapi", "count": 1},
    )
    repo.log_audit(event)

    with repo.db.transaction() as cur:
        cur.execute("SELECT * FROM audit_events WHERE event_id = 'ev_001';")
        row = cur.fetchone()
        assert row is not None
        assert row["event_type"] == "MESSAGE_DISCOVERED"
        assert row["severity"] == "low"


def test_no_send_called_by_default(repo):
    """Safety Invariant: Proves that creating, parsing, and drafting does NOT transmit email."""
    key = generate_idempotency_key("hr@aivaratech.online", "msg_safe", "th_safe")
    msg = EmailMessage(
        message_id="msg_safe",
        provider_id="outlook_com",
        thread_id="th_safe",
        account_id="hr@aivaratech.online",
        sender="inbound@example.com",
        recipients=["hr@aivaratech.online"],
        subject="Inbound Subject",
        body_text="Inbound content",
        received_at="2026-10-20T01:00:00Z",
        state=MessageState.DISCOVERED,
        idempotency_key=key,
    )
    repo.insert_message(msg)

    # Draft created in PENDING_APPROVAL state
    draft = DraftReply(
        draft_id="draft_safe",
        message_id="msg_safe",
        thread_id="th_safe",
        account_id="hr@aivaratech.online",
        subject="Re: Inbound Subject",
        body_text="Safe draft response",
        policy_decision=PolicyDecision.NEEDS_HUMAN_REVIEW,
    )
    repo.save_draft(draft)

    # Assert that staged_to_provider and is_approved remain False by default
    saved_draft = repo.get_draft("draft_safe")
    assert saved_draft.is_approved is False
    assert saved_draft.staged_to_provider is False

    # Assert that the send_ledger has ZERO entries
    with repo.db.transaction() as cur:
        cur.execute("SELECT count(*) as count FROM send_ledger;")
        count = cur.fetchone()["count"]
        assert count == 0


def test_transaction_rollback_on_error(repo):
    """Verify ACID transactional rollback on unhandled failure."""
    try:
        with repo.db.transaction() as cur:
            cur.execute(
                "INSERT INTO audit_events (event_id, timestamp, event_type, severity, details_json) VALUES (?, ?, ?, ?, ?);",
                ("ev_fail", "2026-10-20T01:00:00Z", "TEST", "low", "{}")
            )
            # Intentionally raise an error to trigger rollback
            raise RuntimeError("Forced transaction failure")
    except RuntimeError:
        pass

    with repo.db.transaction() as cur:
        cur.execute("SELECT * FROM audit_events WHERE event_id = 'ev_fail';")
        assert cur.fetchone() is None

