"""BOTSKILL — Policy Engine & Grounded Draft Evaluation (Phase 6D & 6E)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from botskill.core.models import (
    DraftReply,
    EmailMessage,
    PolicyCitation,
    PolicyDecision,
    PolicyRule,
    SeverityLevel,
)
from botskill.storage.database import StorageRepository


class PolicyEngine:
    """Evaluates drafts against active policy rules with deterministic guardrails."""

    def __init__(self, storage: StorageRepository):
        self.storage = storage

    def get_applicable_rules(self, message: EmailMessage) -> List[PolicyRule]:
        """Query active rules in database matching inbound message intent/scope."""
        all_rules = self.storage.list_active_rules()
        text_lower = (message.subject + " " + message.body_text).lower()

        applicable = []
        for rule in all_rules:
            # Check condition triggers
            if "stipend" in text_lower or "salary" in text_lower or "compensation" in text_lower:
                if "stipend" in rule.condition.lower() or "compensation" in rule.condition.lower():
                    applicable.append(rule)
            elif "remote" in text_lower or "location" in text_lower or "work from home" in text_lower:
                if "remote" in rule.condition.lower() or "location" in rule.condition.lower():
                    applicable.append(rule)
            elif "password" in text_lower or "credential" in text_lower or "login" in text_lower:
                if "credential" in rule.condition.lower() or "password" in rule.condition.lower():
                    applicable.append(rule)

        return applicable

    def evaluate_draft(self, draft: DraftReply, message: EmailMessage) -> DraftReply:
        """Evaluate a generated draft against applicable active rules."""
        rules = self.get_applicable_rules(message)
        citations: List[PolicyCitation] = []
        draft_text = draft.body_text.lower()

        # Deterministic check 1: Disallow unapproved monetary stipend amounts in draft
        if any("stipend" in r.condition.lower() for r in rules):
            # Check if draft contains numeric amount promises (e.g. "$1000", "₹15000", "15,000 INR", "20000 per month")
            numeric_money = re.search(r"(\$|₹|rs\.?|inr|usd)\s*\d+[\d,]*|\b\d{4,6}\s*(per\s*month|stipend|pm)\b", draft_text)
            if numeric_money:
                draft.policy_decision = PolicyDecision.BLOCK
                draft.decision_reason = (
                    f"Violation of Rule HR-001: Draft promises unapproved numeric compensation amount ({numeric_money.group(0)})."
                )
                return draft

        # Deterministic check 2: Disallow credential requests
        if any("credential" in r.condition.lower() for r in rules):
            if "send your password" in draft_text or "provide your password" in draft_text:
                draft.policy_decision = PolicyDecision.BLOCK
                draft.decision_reason = "Violation of Rule SUP-001: Prohibits requesting user credentials."
                return draft

        # Build verified citations for applicable rules
        for rule in rules:
            citations.append(PolicyCitation(
                rule_id=rule.rule_id,
                document_id=rule.source_document_id,
                document_title=rule.title,
                source_location=rule.source_location,
                source_quote=rule.source_quote,
                confidence=1.0,
            ))

        draft.citations = citations
        draft.policy_decision = PolicyDecision.PASS
        draft.decision_reason = "All deterministic policy guardrails verified successfully."
        return draft
