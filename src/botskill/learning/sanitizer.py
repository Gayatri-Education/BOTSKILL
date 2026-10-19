"""BOTSKILL — Privacy-Preserving PII & Secret Sanitizer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


class SecurityError(Exception):
    """Raised when an operation violates privacy or security invariants."""
    pass


class PIISanitizer:
    """Detects, redacts, and audits personally identifiable information and secrets."""

    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}\b")
    API_KEY_REGEX = re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,}|ghp_[A-Za-z0-9]{20,})\b")
    BEARER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE)
    CARD_REGEX = re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b")
    PASSWORD_REGEX = re.compile(r"(password|secret|apikey|token)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE)

    def sanitize(self, text: str) -> str:
        """Deterministically redacts all detected PII and secret patterns from text."""
        if not text:
            return ""

        redacted = self.BEARER_REGEX.sub(r"\1[REDACTED_TOKEN]", text)
        redacted = self.API_KEY_REGEX.sub("[REDACTED_API_KEY]", redacted)
        redacted = self.PASSWORD_REGEX.sub(r"\1=[REDACTED_SECRET]", redacted)
        redacted = self.CARD_REGEX.sub("[REDACTED_CARD]", redacted)
        redacted = self.EMAIL_REGEX.sub("[REDACTED_EMAIL]", redacted)
        redacted = self.PHONE_REGEX.sub("[REDACTED_PHONE]", redacted)

        return redacted

    def detect_violations(self, text: str) -> List[str]:
        """Detects remaining unredacted sensitive patterns."""
        violations = []
        if self.API_KEY_REGEX.search(text):
            violations.append("UNREDACTED_API_KEY")
        if self.BEARER_REGEX.search(text):
            violations.append("UNREDACTED_BEARER_TOKEN")
        if self.CARD_REGEX.search(text):
            violations.append("UNREDACTED_CREDIT_CARD")
        if self.PASSWORD_REGEX.search(text):
            violations.append("UNREDACTED_PASSWORD")
        if self.EMAIL_REGEX.search(text):
            violations.append("UNREDACTED_EMAIL")
        if self.PHONE_REGEX.search(text):
            violations.append("UNREDACTED_PHONE")
        return violations

    def validate_for_export(self, payload: List[Dict[str, Any]]) -> None:
        """Enforces that an export bundle contains zero unredacted PII or credentials."""
        for idx, record in enumerate(payload):
            text_corpus = " ".join(
                str(v) for k, v in record.items() if isinstance(v, (str, int, float))
            )
            violations = self.detect_violations(text_corpus)
            if violations:
                raise SecurityError(
                    f"Privacy violation at record #{idx}: Detected raw sensitive data ({', '.join(violations)}). "
                    "Export aborted to protect confidentiality."
                )
