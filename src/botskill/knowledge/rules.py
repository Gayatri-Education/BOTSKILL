"""BOTSKILL — Typed Policy Rule Extraction & Conflict Resolution (Phase 6C)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from botskill.core.models import PolicyRule, RuleType, SeverityLevel
from botskill.knowledge.classifier import DocumentMetadata
from botskill.knowledge.parsers import DocumentParseResult


class ConflictReport:
    def __init__(self, rule_a_id: str, rule_b_id: str, reason: str):
        self.rule_a_id = rule_a_id
        self.rule_b_id = rule_b_id
        self.reason = reason


class RuleExtractor:
    """Extracts candidate rules with exact section/page citations and checks for contradictions."""

    def extract_rules(
        self,
        parse_result: DocumentParseResult,
        metadata: DocumentMetadata
    ) -> List[PolicyRule]:
        rules: List[PolicyRule] = []

        for sec in parse_result.sections:
            text = sec["text"]
            if not text:
                continue

            page = sec.get("page", 1)
            sec_idx = sec.get("section_idx", 1)
            locator = f"Page {page}, Section {sec_idx}"

            # Check for stipend / financial prohibition
            if "stipend" in text.lower() or "compensation" in text.lower() or "salary" in text.lower():
                rules.append(PolicyRule(
                    rule_id=f"RULE-{parse_result.document_id[-6:]}-STIPEND",
                    title="Compensation & Stipend Guardrail",
                    rule_type=RuleType.PROHIBITION,
                    severity=SeverityLevel.HIGH,
                    condition="A reply discusses stipend, salary, or compensation figures",
                    required_action="Quote only active approved offer letter terms post-interview",
                    prohibited_actions=["quote_unverified_stipend", "promise_salary_amount"],
                    source_document_id=parse_result.document_id,
                    source_location=locator,
                    source_quote=text[:250],
                    is_active=False,  # Inactive until reviewed & approved by human
                ))

            # Check for remote work policy
            elif "remote" in text.lower() or "work from home" in text.lower() or "location" in text.lower():
                rules.append(PolicyRule(
                    rule_id=f"RULE-{parse_result.document_id[-6:]}-REMOTE",
                    title="Working Location & Remote Flexibility Policy",
                    rule_type=RuleType.MANDATORY_POLICY,
                    severity=SeverityLevel.MEDIUM,
                    condition="A reply discusses office attendance or remote work eligibility",
                    required_action="State remote work eligibility per cohort guidelines",
                    prohibited_actions=["require_unapproved_relocation"],
                    source_document_id=parse_result.document_id,
                    source_location=locator,
                    source_quote=text[:250],
                    is_active=False,
                ))

            # Check for credential / password prohibition
            elif "password" in text.lower() or "credential" in text.lower() or "token" in text.lower():
                rules.append(PolicyRule(
                    rule_id=f"RULE-{parse_result.document_id[-6:]}-CREDS",
                    title="User Credential Protection Invariant",
                    rule_type=RuleType.GUARDRAIL,
                    severity=SeverityLevel.CRITICAL,
                    condition="A reply prompts for user authentication credentials",
                    required_action="Instruct user to use official SSO/portal login",
                    prohibited_actions=["request_mailbox_password", "request_mfa_code"],
                    source_document_id=parse_result.document_id,
                    source_location=locator,
                    source_quote=text[:250],
                    is_active=False,
                ))

        return rules

    @staticmethod
    def detect_conflicts(rules: List[PolicyRule]) -> List[ConflictReport]:
        """Detect direct contradictions across active policy rules."""
        conflicts = []
        for i, r1 in enumerate(rules):
            for r2 in rules[i + 1:]:
                # Check for contradictory prohibited actions vs required actions
                if r1.prohibited_actions and r2.required_action:
                    for pa in r1.prohibited_actions:
                        if pa in r2.required_action.lower():
                            conflicts.append(ConflictReport(
                                r1.rule_id,
                                r2.rule_id,
                                f"Rule {r1.rule_id} prohibits what Rule {r2.rule_id} requires: {pa}"
                            ))
        return conflicts
