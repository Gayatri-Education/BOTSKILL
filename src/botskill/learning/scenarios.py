"""BOTSKILL — Private Scenario Synthesis and Code Self-Modification Prevention."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from botskill.core.models import EmailMessage
from botskill.learning.sanitizer import PIISanitizer, SecurityError


class ScenarioCandidate(BaseModel):
    scenario_id: str
    archetype: str
    sanitized_subject: str
    sanitized_body: str
    suggested_rules: List[str]
    is_approved: bool = False
    created_at: str


class ScenarioEngine:
    """Extracts anonymized scenarios and synthesizes regression tests without code self-modification."""

    def __init__(self):
        self.sanitizer = PIISanitizer()

    def propose_from_message(self, message: EmailMessage) -> ScenarioCandidate:
        clean_subject = self.sanitizer.sanitize(message.subject)
        clean_body = self.sanitizer.sanitize(message.body_text)

        text_lower = f"{clean_subject} {clean_body}".lower()

        # Classify Archetype
        if "stipend" in text_lower or "compensation" in text_lower or "salary" in text_lower:
            archetype = "INTERNSHIP_COMPENSATION_INQUIRY"
            rules = ["RULE-HR-001"]
        elif "remote" in text_lower or "wfh" in text_lower or "office" in text_lower:
            archetype = "REMOTE_WORK_INQUIRY"
            rules = ["RULE-HR-002"]
        elif "onboarding" in text_lower or "sla" in text_lower or "support" in text_lower:
            archetype = "SUPPORT_SLA_INQUIRY"
            rules = ["RULE-SUP-001"]
        else:
            archetype = "GENERAL_BUSINESS_INQUIRY"
            rules = []

        scenario_id = f"scen_{int(datetime.now(timezone.utc).timestamp())}_{message.message_id[:6]}"

        return ScenarioCandidate(
            scenario_id=scenario_id,
            archetype=archetype,
            sanitized_subject=clean_subject,
            sanitized_body=clean_body,
            suggested_rules=rules,
            is_approved=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def generate_synthetic_test(self, candidate: ScenarioCandidate) -> Dict[str, Any]:
        """Synthesize a standalone reproducible test case without real user credentials."""
        return {
            "test_id": f"test_{candidate.scenario_id}",
            "archetype": candidate.archetype,
            "mock_inbound": {
                "sender": "synthetic_applicant@example.com",
                "subject": candidate.sanitized_subject,
                "body": candidate.sanitized_body,
            },
            "expected_policy_enforcement": {
                "required_rules": candidate.suggested_rules,
                "must_block_unauthorized_numbers": "INTERNSHIP_COMPENSATION_INQUIRY" in candidate.archetype,
                "mode": "DRAFT_ONLY",
            },
            "assertions": [
                "policy_check_passes",
                "zero_network_egress",
                "no_live_send_called",
            ],
        }

    def verify_no_self_modification(self, target_path_or_content: str) -> None:
        """Enforces invariant: BOTSKILL never self-modifies executable source code or system configs."""
        forbidden_extensions = [".py", ".bat", ".cmd", ".ps1", ".sh", ".exe", ".dll"]
        for ext in forbidden_extensions:
            if target_path_or_content.lower().endswith(ext):
                raise SecurityError(
                    f"Governance violation: Attempted write or self-modification to executable '{target_path_or_content}' is strictly blocked."
                )

        if re.search(r"\b(exec|eval|__import__|importlib|os\.system|subprocess)\b", target_path_or_content):
            raise SecurityError(
                "Governance violation: Dynamic code execution or self-modification construct detected."
            )
