"""BOTSKILL — Deterministic Fake Email Provider for Testing and CI."""

from __future__ import annotations

from typing import Any, Dict, List
from botskill.core.models import AutonomyLevel, DraftReply, EmailMessage


class FakeEmailProvider:
    """In-memory mock transport guaranteeing zero real email transmission."""

    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.DRAFT_ONLY):
        self.autonomy_level = autonomy_level
        self.inbox: List[EmailMessage] = []
        self.staged_drafts: List[DraftReply] = []
        self.sent_messages: List[DraftReply] = []

    def test_connection(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "connector": "FakeEmailProvider (In-Memory)",
            "accounts_count": 1,
            "accounts": ["test@example.com"],
            "autonomy_level": self.autonomy_level.value,
        }

    def list_new_messages(self, account_id: str, limit: int = 20) -> List[EmailMessage]:
        return [msg for msg in self.inbox if msg.account_id == account_id][:limit]

    def create_draft(self, draft: DraftReply) -> bool:
        self.staged_drafts.append(draft)
        return True

    def send_reply(self, draft: DraftReply, idempotency_key: str) -> bool:
        if self.autonomy_level == AutonomyLevel.DRAFT_ONLY:
            raise PermissionError("Live transmission blocked: System is configured in DRAFT_ONLY mode.")
        if not draft.is_approved:
            raise PermissionError("Live transmission blocked: Draft requires human supervisor approval.")
        self.sent_messages.append(draft)
        return True
