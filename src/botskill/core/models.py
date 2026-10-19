"""BOTSKILL — Core Domain Models, Enums, and State Lifecycle Entities."""

from __future__ import annotations

import enum
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AutonomyLevel(str, enum.Enum):
    """Progressive autonomy tier enforcement."""
    DISABLED = "LEVEL_0_DISABLED"
    DRAFT_ONLY = "LEVEL_1_DRAFT_ONLY"          # Default safe mode: stages drafts in Outlook
    SUPERVISED = "LEVEL_2_SUPERVISED"          # Requires human click before live send
    LIMITED_AUTO_SEND = "LEVEL_3_LIMITED_AUTO"  # Only explicitly whitelisted low-risk categories


class MessageState(str, enum.Enum):
    """Deterministic message lifecycle states."""
    DISCOVERED = "DISCOVERED"
    CLAIMED = "CLAIMED"
    PARSED = "PARSED"
    CLASSIFIED = "CLASSIFIED"
    KNOWLEDGE_RETRIEVED = "KNOWLEDGE_RETRIEVED"
    DRAFTED = "DRAFTED"
    POLICY_CHECKED = "POLICY_CHECKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED_TO_STAGE = "APPROVED_TO_STAGE"
    STAGED_TO_DRAFTS = "STAGED_TO_DRAFTS"
    APPROVED_TO_SEND = "APPROVED_TO_SEND"
    SEND_PENDING = "SEND_PENDING"
    SENT_CONFIRMED = "SENT_CONFIRMED"
    SEND_OUTCOME_UNKNOWN = "SEND_OUTCOME_UNKNOWN"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"
    QUARANTINED = "QUARANTINED"
    IGNORED = "IGNORED"


class PolicyDecision(str, enum.Enum):
    """Outcome of deterministic policy evaluation."""
    PASS = "PASS"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    BLOCK = "BLOCK"
    POLICY_CONFLICT = "POLICY_CONFLICT"
    PROHIBITED_CLAIM = "PROHIBITED_CLAIM"


class RuleType(str, enum.Enum):
    """Typed category of policy obligation."""
    MANDATORY_POLICY = "mandatory_policy"
    GUARDRAIL = "guardrail"
    PROHIBITION = "prohibition"
    APPROVAL_REQUIRED = "approval_required"
    SOP = "sop"
    FAQ = "faq"
    STYLE_GUIDE = "style_guide"


class SeverityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def generate_idempotency_key(account_id: str, provider_message_id: str, thread_id: str) -> str:
    """Compute a deterministic hash for deduplication and duplicate prevention."""
    raw = f"{account_id}:{provider_message_id}:{thread_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class PolicyCitation(BaseModel):
    """Citation trace pointing to supporting business document evidence."""
    rule_id: str
    document_id: str
    document_title: str
    source_location: str  # e.g. "Section 3.2, Page 4"
    source_quote: str
    confidence: float = 1.0


class PolicyRule(BaseModel):
    """Normalized, typed enterprise policy rule."""
    rule_id: str
    title: str
    rule_type: RuleType = RuleType.MANDATORY_POLICY
    severity: SeverityLevel = SeverityLevel.HIGH
    condition: str
    required_action: Optional[str] = None
    prohibited_actions: List[str] = Field(default_factory=list)
    source_document_id: str
    source_location: str
    source_quote: str
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EmailMessage(BaseModel):
    """Normalized email message metadata and payload."""
    message_id: str
    provider_id: str
    thread_id: str
    account_id: str
    sender: str
    sender_name: Optional[str] = None
    recipients: List[str]
    cc: List[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: Optional[str] = None
    received_at: str
    state: MessageState = MessageState.DISCOVERED
    idempotency_key: str
    is_read: bool = False
    inbound_intent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DraftReply(BaseModel):
    """AI or rule-generated proposed reply staged for review."""
    draft_id: str
    message_id: str
    thread_id: str
    account_id: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    citations: List[PolicyCitation] = Field(default_factory=list)
    policy_decision: PolicyDecision = PolicyDecision.NEEDS_HUMAN_REVIEW
    decision_reason: Optional[str] = None
    model_provenance: str = "local-slm-qwen2.5-0.5b"
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    staged_to_provider: bool = False
    is_approved: bool = False


class AuditEvent(BaseModel):
    """Immutable audit trail record."""
    event_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str
    account_id: Optional[str] = None
    message_id: Optional[str] = None
    severity: SeverityLevel = SeverityLevel.LOW
    details: Dict[str, Any] = Field(default_factory=dict)
