"""BOTSKILL — Abstract Provider Protocols and Contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from botskill.core.models import DraftReply, EmailMessage, PolicyDecision, PolicyRule


@runtime_checkable
class EmailProvider(Protocol):
    """Protocol for interchangeable email transports (Outlook MAPI, IMAP/SMTP, Graph)."""

    def test_connection(self) -> Dict[str, Any]:
        """Verify transport connectivity without sending any messages."""
        ...

    def list_new_messages(self, account_id: str, limit: int = 50) -> List[EmailMessage]:
        """Fetch unread / new messages from the designated account."""
        ...

    def create_draft(self, draft: DraftReply) -> bool:
        """Stage proposed response in the account's local Drafts folder."""
        ...

    def send_reply(self, draft: DraftReply, idempotency_key: str) -> bool:
        """Transmits live email only when policy & operator approval explicitly allow."""
        ...


@runtime_checkable
class AIProvider(Protocol):
    """Protocol for AI generative backends (llama-cpp, Ollama, Cloud)."""

    def health_check(self) -> Dict[str, Any]:
        """Report runtime availability, loaded model, and latency."""
        ...

    def generate_reply(
        self,
        inbound_message: EmailMessage,
        applicable_rules: List[PolicyRule],
        tone_profile: str = "concise"
    ) -> Dict[str, Any]:
        """Generate structured draft response with source citations."""
        ...


@runtime_checkable
class SecretStore(Protocol):
    """Protocol for safe credential management."""

    def get_secret(self, secret_key: str) -> Optional[str]:
        ...

    def set_secret(self, secret_key: str, secret_value: str) -> None:
        ...
