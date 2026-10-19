"""BOTSKILL — Inbound Prompt Injection & Adversarial Attack Detector."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Tuple
from pydantic import BaseModel

from botskill.core.models import SeverityLevel


class InjectionCheckResult(BaseModel):
    is_injection: bool
    risk_score: float
    threat_level: str
    matched_patterns: List[str]
    recommended_action: str  # "ALLOW" or "QUARANTINE"


class PromptInjectionGuard:
    """Multi-layer adversarial defense scanner for inbound email payloads."""

    OVERRIDE_PATTERNS = [
        re.compile(r"\b(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|above|system)\s+(instructions|prompts|rules|commands)\b", re.IGNORECASE),
        re.compile(r"\b(you\s+are\s+now|act\s+as)\s+(an?\s+)?(unrestricted|unfiltered|jailbroken|dan|developer mode|godmode)\b", re.IGNORECASE),
        re.compile(r"<\|im_start\|>system|<\|im_end\|>|\[SYSTEM_PROMPT\]", re.IGNORECASE),
        re.compile(r"\b(jailbreak|system\s+override|prompt\s+leak)\b", re.IGNORECASE),
    ]

    EXFILTRATION_PATTERNS = [
        re.compile(r"(send|forward|exfiltrate|post|transmit)\s+(all\s+)?(emails?|passwords?|keys?|secrets?|tokens?|database)\s+to\b", re.IGNORECASE),
        re.compile(r"\b(curl|wget|fetch\(|http_post)\b", re.IGNORECASE),
        re.compile(r"https?://[^\s<>\"']*(?:webhook|sink|leak|collector|attacker|pastebin)", re.IGNORECASE),
    ]

    AUTHORITY_OVERRIDE_PATTERNS = [
        re.compile(r"\b(this\s+is\s+the\s+ceo|executive\s+override|from\s+management)\b.*\b(bypass|disable|send\s+immediately|skip\s+review)\b", re.IGNORECASE),
        re.compile(r"\b(bypass\s+all\s+approval|disable\s+draft_only|enable\s+live\s+send)\b", re.IGNORECASE),
    ]

    ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u00AD]")

    def normalize_text(self, text: str) -> str:
        """Strip zero-width obfuscation and normalize Unicode."""
        if not text:
            return ""
        # Remove zero-width spaces/joiners often used to break keyword regex
        cleaned = self.ZERO_WIDTH_CHARS.sub("", text)
        normalized = unicodedata.normalize("NFKD", cleaned)
        return normalized

    def scan(self, text: str) -> InjectionCheckResult:
        if not text:
            return InjectionCheckResult(
                is_injection=False,
                risk_score=0.0,
                threat_level=SeverityLevel.LOW.value,
                matched_patterns=[],
                recommended_action="ALLOW",
            )

        normalized = self.normalize_text(text)
        matches: List[str] = []

        # 1. Check prompt override jailbreaks
        for pat in self.OVERRIDE_PATTERNS:
            if pat.search(normalized):
                matches.append(f"INSTRUCTION_OVERRIDE: {pat.pattern[:40]}")

        # 2. Check data exfiltration commands
        for pat in self.EXFILTRATION_PATTERNS:
            if pat.search(normalized):
                matches.append(f"EXFILTRATION_DIRECTIVE: {pat.pattern[:40]}")

        # 3. Check authority bypass attacks
        for pat in self.AUTHORITY_OVERRIDE_PATTERNS:
            if pat.search(normalized):
                matches.append(f"AUTHORITY_OVERRIDE: {pat.pattern[:40]}")

        # Compute risk score
        count = len(matches)
        if count == 0:
            return InjectionCheckResult(
                is_injection=False,
                risk_score=0.0,
                threat_level=SeverityLevel.LOW.value,
                matched_patterns=[],
                recommended_action="ALLOW",
            )
        elif count == 1:
            return InjectionCheckResult(
                is_injection=True,
                risk_score=0.75,
                threat_level=SeverityLevel.HIGH.value,
                matched_patterns=matches,
                recommended_action="QUARANTINE",
            )
        else:
            return InjectionCheckResult(
                is_injection=True,
                risk_score=0.98,
                threat_level=SeverityLevel.CRITICAL.value,
                matched_patterns=matches,
                recommended_action="QUARANTINE",
            )
