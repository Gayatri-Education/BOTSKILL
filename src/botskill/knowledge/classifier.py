"""BOTSKILL — Document Taxonomy Classification & Metadata Extraction (Phase 6B)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from botskill.core.models import RuleType
from botskill.knowledge.parsers import DocumentParseResult


class DocumentMetadata:
    """Classified metadata and authority scope for an enterprise document."""

    def __init__(
        self,
        document_id: str,
        title: str,
        primary_type: RuleType,
        department: str,
        effective_from: Optional[str] = None,
        confidence: float = 1.0,
        status: str = "NEEDS_REVIEW",
    ):
        self.document_id = document_id
        self.title = title
        self.primary_type = primary_type
        self.department = department
        self.effective_from = effective_from
        self.confidence = confidence
        self.status = status  # NEEDS_REVIEW, APPROVED, REJECTED, SUPERSEDED


class DocumentClassifier:
    """Infers document type and extracts scope without blind filename assumptions."""

    def classify(self, parse_result: DocumentParseResult) -> DocumentMetadata:
        text_sample = parse_result.text_content[:2000].lower()
        filename_lower = parse_result.filename.lower()

        # Department detection
        department = "general"
        if "hr" in filename_lower or "human resources" in text_sample or "recruitment" in text_sample or "intern" in text_sample:
            department = "hr"
        elif "support" in filename_lower or "customer service" in text_sample or "sla" in text_sample:
            department = "customer_support"
        elif "sales" in filename_lower or "pricing" in text_sample or "quotation" in text_sample:
            department = "sales"

        # Type detection
        if "policy" in filename_lower or "code of conduct" in text_sample or "mandatory" in text_sample:
            primary_type = RuleType.MANDATORY_POLICY
            confidence = 0.92
        elif "guardrail" in filename_lower or "prohibited" in text_sample:
            primary_type = RuleType.GUARDRAIL
            confidence = 0.90
        elif "sop" in filename_lower or "operating procedure" in text_sample:
            primary_type = RuleType.SOP
            confidence = 0.88
        elif "faq" in filename_lower or "frequently asked" in text_sample:
            primary_type = RuleType.FAQ
            confidence = 0.85
        else:
            primary_type = RuleType.MANDATORY_POLICY
            confidence = 0.65

        # Effective date extraction
        date_match = re.search(r"effective(?:\s+date)?[:\s]+(\d{4}[-/]\d{2}[-/]\d{2})", text_sample)
        effective_from = date_match.group(1) if date_match else None

        title = parse_result.filename.rsplit(".", 1)[0].replace("_", " ").title()

        return DocumentMetadata(
            document_id=parse_result.document_id,
            title=title,
            primary_type=primary_type,
            department=department,
            effective_from=effective_from,
            confidence=confidence,
            status="NEEDS_REVIEW",  # Mandatory human approval required
        )
