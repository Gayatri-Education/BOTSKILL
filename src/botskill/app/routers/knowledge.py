"""Dashboard API router for Document Ingestion, Intelligence, and Policy Rules Matrix."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from botskill.core.models import (
    AuditEvent,
    PolicyRule,
    RuleType,
    SeverityLevel,
)
from botskill.knowledge.classifier import DocumentClassifier
from botskill.knowledge.parsers import MAX_FILE_SIZE_BYTES, SafeDocumentParser
from botskill.knowledge.rules import RuleExtractor

logger = logging.getLogger("botskill.app.routers.knowledge")
router = APIRouter(prefix="/api/knowledge", tags=["Knowledge & Policies"])


class RuleResponse(BaseModel):
    rule_id: str
    title: str
    rule_type: str
    severity: str
    condition: str
    required_action: str
    prohibited_actions: List[str]
    source_document_id: str
    source_location: str
    source_quote: str
    is_active: bool
    created_at: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    content_hash: str
    page_count: int
    classification: Dict[str, Any]
    preview_text: str
    extracted_rules_count: int
    extracted_rules: List[RuleResponse]


def _get_default_rules() -> List[PolicyRule]:
    """Fallback baseline enterprise rules."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        PolicyRule(
            rule_id="RULE-HR-001",
            title="Internship Stipend Guardrail",
            rule_type=RuleType.PROHIBITION,
            severity=SeverityLevel.HIGH,
            condition="Candidate or applicant asks about compensation or stipend",
            required_action="Quote compensation only post-interview with approved offer letter",
            prohibited_actions=["quote_unverified_stipend", "promise_salary_amount"],
            source_document_id="doc_hr_handbook_v2",
            source_location="Page 4, Section 3.1",
            source_quote="Intern compensation is finalized strictly after technical evaluation.",
            is_active=True,
            created_at=now,
        ),
        PolicyRule(
            rule_id="RULE-HR-002",
            title="Remote Work Eligibility",
            rule_type=RuleType.MANDATORY_POLICY,
            severity=SeverityLevel.MEDIUM,
            condition="Applicant inquires about office location or remote options",
            required_action="Clarify that engineering internships are 100% remote",
            prohibited_actions=["require_office_attendance"],
            source_document_id="doc_hr_handbook_v2",
            source_location="Page 2, Section 1.4",
            source_quote="Engineering internships operate fully remotely across India.",
            is_active=True,
            created_at=now,
        ),
    ]


@router.post("/upload", response_model=DocumentUploadResponse, summary="Upload, parse and extract policy rules from document")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    # 1. Read bytes & check size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    # 2. Save to secure temporary file for parsing
    suffix = Path(file.filename or "upload.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = SafeDocumentParser()
        parse_result = parser.parse_file(tmp_path)
        parse_result.filename = file.filename or "uploaded_file"

        if not parse_result.is_success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document parsing failed: {parse_result.error_message}",
            )

        # 3. Classify and extract rules
        classifier = DocumentClassifier()
        metadata = classifier.classify(parse_result)

        extractor = RuleExtractor()
        rules = extractor.extract_rules(parse_result, metadata)

        # 4. Persist to SQLite if DB manager configured
        db_mgr = getattr(request.app.state, "db_manager", None)
        if db_mgr:
            repo = db_mgr.get_repository()
            for rule in rules:
                repo.insert_rule(rule)

            audit = AuditEvent(
                event_id=f"audit_upload_{int(time.time() * 1000)}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="DOCUMENT_UPLOADED",
                severity=SeverityLevel.LOW,
                details={
                    "filename": file.filename,
                    "document_id": parse_result.document_id,
                    "sha256": parse_result.content_hash,
                    "rules_extracted": len(rules),
                },
            )
            repo.log_audit(audit)

        rule_responses = [
            RuleResponse(
                rule_id=r.rule_id,
                title=r.title,
                rule_type=r.rule_type.value,
                severity=r.severity.value,
                condition=r.condition,
                required_action=r.required_action,
                prohibited_actions=r.prohibited_actions,
                source_document_id=r.source_document_id,
                source_location=r.source_location,
                source_quote=r.source_quote,
                is_active=r.is_active,
                created_at=r.created_at,
            )
            for r in rules
        ]

        return DocumentUploadResponse(
            document_id=parse_result.document_id,
            filename=parse_result.filename,
            file_type=parse_result.file_type,
            content_hash=parse_result.content_hash,
            page_count=parse_result.page_count,
            classification={
                "title": metadata.title,
                "department": metadata.department,
                "primary_type": metadata.primary_type.value,
                "confidence": metadata.confidence,
                "status": metadata.status,
            },
            preview_text=parse_result.text_content[:600],
            extracted_rules_count=len(rules),
            extracted_rules=rule_responses,
        )

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@router.get("/rules", response_model=List[RuleResponse], summary="List all policy rules")
async def list_rules(request: Request):
    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        rules = repo.list_all_rules()
        if rules:
            return [
                RuleResponse(
                    rule_id=r.rule_id,
                    title=r.title,
                    rule_type=r.rule_type.value,
                    severity=r.severity.value,
                    condition=r.condition,
                    required_action=r.required_action,
                    prohibited_actions=r.prohibited_actions,
                    source_document_id=r.source_document_id,
                    source_location=r.source_location,
                    source_quote=r.source_quote,
                    is_active=r.is_active,
                    created_at=r.created_at,
                )
                for r in rules
            ]

    # Return defaults if database is empty
    defaults = _get_default_rules()
    return [
        RuleResponse(
            rule_id=r.rule_id,
            title=r.title,
            rule_type=r.rule_type.value,
            severity=r.severity.value,
            condition=r.condition,
            required_action=r.required_action,
            prohibited_actions=r.prohibited_actions,
            source_document_id=r.source_document_id,
            source_location=r.source_location,
            source_quote=r.source_quote,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in defaults
    ]


@router.post("/rules/{rule_id}/approve", summary="Human approval to activate a policy rule")
async def approve_rule(rule_id: str, request: Request):
    db_mgr = getattr(request.app.state, "db_manager", None)
    if not db_mgr:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database manager not initialized.",
        )

    repo = db_mgr.get_repository()
    rule = repo.get_rule(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found.",
        )

    repo.set_rule_active_status(rule_id, is_active=True)

    # Log audit event
    audit = AuditEvent(
        event_id=f"audit_appr_{int(time.time() * 1000)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type="POLICY_RULE_APPROVED",
        severity=SeverityLevel.LOW,
        details={"rule_id": rule_id, "action": "human_approved"},
    )
    repo.log_audit(audit)

    return {"rule_id": rule_id, "status": "APPROVED", "is_active": True}


@router.post("/rules/{rule_id}/deactivate", summary="Deactivate an existing policy rule")
async def deactivate_rule(rule_id: str, request: Request):
    db_mgr = getattr(request.app.state, "db_manager", None)
    if not db_mgr:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database manager not initialized.",
        )

    repo = db_mgr.get_repository()
    rule = repo.get_rule(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' not found.",
        )

    repo.set_rule_active_status(rule_id, is_active=False)

    # Log audit event
    audit = AuditEvent(
        event_id=f"audit_deact_{int(time.time() * 1000)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type="POLICY_RULE_DEACTIVATED",
        severity=SeverityLevel.LOW,
        details={"rule_id": rule_id, "action": "human_deactivated"},
    )
    repo.log_audit(audit)

    return {"rule_id": rule_id, "status": "INACTIVE", "is_active": False}
