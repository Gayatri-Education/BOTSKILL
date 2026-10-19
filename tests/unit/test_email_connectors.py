"""Unit tests for BOTSKILL Email Connectors (Windows Outlook COM and Fake Provider)."""

import sys
import pytest
from botskill.core.models import (
    AutonomyLevel,
    DraftReply,
    EmailMessage,
    MessageState,
    PolicyDecision,
    generate_idempotency_key,
)
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.mail_providers.outlook_mapi import OutlookMAPIAdapter


def test_fake_provider_contracts():
    """Verify in-memory fake email provider operations."""
    provider = FakeEmailProvider(autonomy_level=AutonomyLevel.DRAFT_ONLY)
    status = provider.test_connection()
    assert status["status"] == "READY"
    assert status["autonomy_level"] == "LEVEL_1_DRAFT_ONLY"

    # Add mock message
    key = generate_idempotency_key("test@example.com", "msg_1", "th_1")
    msg = EmailMessage(
        message_id="msg_1",
        provider_id="fake",
        thread_id="th_1",
        account_id="test@example.com",
        sender="sender@example.com",
        recipients=["test@example.com"],
        subject="Test Inquiry",
        body_text="Hello support",
        received_at="2026-10-20T01:00:00Z",
        idempotency_key=key,
    )
    provider.inbox.append(msg)

    messages = provider.list_new_messages("test@example.com")
    assert len(messages) == 1
    assert messages[0].subject == "Test Inquiry"

    # Staging draft succeeds
    draft = DraftReply(
        draft_id="draft_fake",
        message_id="msg_1",
        thread_id="th_1",
        account_id="test@example.com",
        subject="Re: Test Inquiry",
        body_text="Here is our response",
        policy_decision=PolicyDecision.PASS,
    )
    assert provider.create_draft(draft) is True
    assert len(provider.staged_drafts) == 1

    # Live sending in DRAFT_ONLY mode MUST raise PermissionError
    with pytest.raises(PermissionError, match="DRAFT_ONLY"):
        provider.send_reply(draft, idempotency_key=key)


def test_outlook_mapi_quote_cleaner():
    """Verify that quote-stripping removes thread histories and false intent traps."""
    body_with_quotes = """Thank you for your reply. I am interested.

-----Original Message-----
From: hr@aivaratech.online
Sent: Monday, October 19, 2026 10:00 AM
To: candidate@example.com
Subject: Interview Follow-up
You are rejected."""

    cleaned = OutlookMAPIAdapter.clean_inbound_text(body_with_quotes)
    assert cleaned == "Thank you for your reply. I am interested."
    assert "You are rejected" not in cleaned


def test_outlook_mapi_send_blocked_in_draft_only():
    """Verify Outlook COM adapter strictly blocks live sending when in DRAFT_ONLY mode."""
    adapter = OutlookMAPIAdapter(autonomy_level=AutonomyLevel.DRAFT_ONLY)
    draft = DraftReply(
        draft_id="draft_safe",
        message_id="msg_safe",
        thread_id="th_safe",
        account_id="hr@aivaratech.online",
        subject="Re: Inquiry",
        body_text="Staged response",
    )
    with pytest.raises(PermissionError, match="LEVEL_1_DRAFT_ONLY"):
        adapter.send_reply(draft, idempotency_key="test_key")


@pytest.mark.skipif(sys.platform != "win32", reason="Outlook COM only available on Windows")
def test_outlook_mapi_local_connection_probe():
    """Probe real local Outlook COM session without sending email."""
    adapter = OutlookMAPIAdapter(autonomy_level=AutonomyLevel.DRAFT_ONLY)
    res = adapter.test_connection()
    assert res["status"] in ("READY", "UNAVAILABLE")
    if res["status"] == "READY":
        assert res["accounts_count"] >= 1
        assert "hr@aivaratech.online" in res["accounts"] or len(res["accounts"]) > 0
