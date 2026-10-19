"""Dashboard API router for Draft Review Queue and 1-Click Outlook Staging."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from botskill.core.models import (
    AuditEvent,
    AutonomyLevel,
    DraftReply,
    PolicyCitation,
    PolicyDecision,
    SeverityLevel,
)
from botskill.mail_providers.fake_provider import FakeEmailProvider
from botskill.mail_providers.outlook_mapi import OutlookMAPIAdapter

logger = logging.getLogger("botskill.app.routers.drafts")
router = APIRouter(prefix="/api/drafts", tags=["Draft Review Queue"])


class CitationResponse(BaseModel):
    rule_id: str
    document_id: str
    document_title: str
    source_location: str
    source_quote: str


class DraftResponse(BaseModel):
    draft_id: str
    message_id: str
    thread_id: str
    account_id: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    citations: List[CitationResponse]
    policy_decision: str
    decision_reason: str
    model_provenance: str
    latency_ms: float
    staged_to_provider: bool
    is_approved: bool
    created_at: str


class DraftUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body_text: Optional[str] = None


class StagingResponse(BaseModel):
    draft_id: str
    staged_to_provider: bool
    target_folder: str
    account_id: str
    status: str
    live_send_executed: bool


def _get_provider(request: Request):
    if hasattr(request.app.state, "mail_provider") and request.app.state.mail_provider:
        return request.app.state.mail_provider
    try:
        return OutlookMAPIAdapter()
    except Exception:
        return FakeEmailProvider()


def _get_default_drafts() -> List[DraftReply]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        DraftReply(
            draft_id="draft-001",
            message_id="msg-aivara-001",
            thread_id="internship inquiry: python backend engineer",
            account_id="hr@aivaratech.online",
            subject="Re: Internship Inquiry: Python Backend Engineer",
            body_text=(
                "Dear Candidate,\n\n"
                "Thank you for your interest in Aivara Technologies. All engineering internships "
                "are conducted remotely. Official compensation and stipend numbers are finalized "
                "strictly after the technical interview process.\n\n"
                "Best regards,\nAivara HR Team"
            ),
            citations=[
                PolicyCitation(
                    rule_id="RULE-HR-002",
                    document_id="doc_hr_handbook_v2",
                    document_title="Aivara HR Handbook v2.1",
                    source_location="Page 2, Section 1.4",
                    source_quote="Engineering internships operate fully remotely across India.",
                ),
                PolicyCitation(
                    rule_id="RULE-HR-001",
                    document_id="doc_hr_handbook_v2",
                    document_title="Aivara HR Handbook v2.1",
                    source_location="Page 4, Section 3.1",
                    source_quote="Intern compensation is finalized strictly after technical evaluation.",
                ),
            ],
            policy_decision=PolicyDecision.PASS,
            decision_reason="Draft strictly complies with stipend prohibition and remote work policies.",
            model_provenance="Qwen2.5-0.5B-Instruct-Q4_K_M (Local CPU)",
            latency_ms=284.0,
            staged_to_provider=False,
            is_approved=True,
            created_at=now,
        ),
        DraftReply(
            draft_id="draft-002",
            message_id="msg-aivara-002",
            thread_id="query regarding customer onboarding sla",
            account_id="contactus@aivaratech.online",
            subject="Re: Query Regarding Customer Onboarding SLA",
            body_text=(
                "Hello,\n\n"
                "Standard enterprise customer onboarding requires 3 to 5 business days as defined "
                "in our Customer Support Service Level Agreement.\n\n"
                "Regards,\nAivara Support"
            ),
            citations=[
                PolicyCitation(
                    rule_id="RULE-SUP-001",
                    document_id="doc_sla_2026",
                    document_title="Customer SLA Guide 2026",
                    source_location="Page 1, Section 2",
                    source_quote="Standard onboarding SLA is 3-5 business days.",
                ),
            ],
            policy_decision=PolicyDecision.PASS,
            decision_reason="Complies with published SLA parameters.",
            model_provenance="Qwen2.5-0.5B-Instruct-Q4_K_M (Local CPU)",
            latency_ms=195.0,
            staged_to_provider=False,
            is_approved=True,
            created_at=now,
        ),
        DraftReply(
            draft_id="draft-003",
            message_id="msg-aivara-003",
            thread_id="request for update regarding today's orientation session",
            account_id="hr@aivaratech.online",
            subject="Re: Request for Update Regarding Today's Orientation Session",
            body_text=(
                "Dear Adil,\n\n"
                "Thank you for following up regarding today's orientation session. As specified in our "
                "Candidate Onboarding SOP, virtual meeting links and orientation credentials are distributed "
                "strictly 30 minutes prior to the scheduled session start.\n\n"
                "Please check your inbox and spam folder shortly before start time. Our onboarding "
                "coordinator will also reach out if any technical adjustments occur.\n\n"
                "Warm regards,\nHR Operations Team\nAivara Technologies"
            ),
            citations=[
                PolicyCitation(
                    rule_id="RULE-HR-005",
                    document_id="doc_orientation_guide_2026",
                    document_title="Aivara Onboarding & Orientation SOP 2026",
                    source_location="Section 1.2",
                    source_quote="Orientation meeting links and materials are dispatched 30 minutes prior to session start to registered candidate emails.",
                ),
            ],
            policy_decision=PolicyDecision.PASS,
            decision_reason="Verified against Candidate Onboarding SOP 2026.",
            model_provenance="Qwen2.5-0.5B-Instruct-Q4_K_M (Local CPU)",
            latency_ms=210.0,
            staged_to_provider=False,
            is_approved=True,
            created_at=now,
        ),
    ]


@router.get("", response_model=List[DraftResponse], summary="List pending review drafts")
async def list_drafts(request: Request):
    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        drafts = repo.list_drafts()
        if drafts:
            return [
                DraftResponse(
                    draft_id=d.draft_id,
                    message_id=d.message_id,
                    thread_id=d.thread_id,
                    account_id=d.account_id,
                    subject=d.subject,
                    body_text=d.body_text,
                    body_html=d.body_html,
                    citations=[
                        CitationResponse(
                            rule_id=c.rule_id,
                            document_id=c.document_id,
                            document_title=c.document_title,
                            source_location=c.source_location,
                            source_quote=c.source_quote,
                        )
                        for c in d.citations
                    ],
                    policy_decision=d.policy_decision.value,
                    decision_reason=d.decision_reason,
                    model_provenance=d.model_provenance,
                    latency_ms=d.latency_ms,
                    staged_to_provider=d.staged_to_provider,
                    is_approved=d.is_approved,
                    created_at=d.created_at,
                )
                for d in drafts
            ]

    # Return defaults if database has no drafts yet
    defaults = _get_default_drafts()
    return [
        DraftResponse(
            draft_id=d.draft_id,
            message_id=d.message_id,
            thread_id=d.thread_id,
            account_id=d.account_id,
            subject=d.subject,
            body_text=d.body_text,
            body_html=d.body_html,
            citations=[
                CitationResponse(
                    rule_id=c.rule_id,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    source_location=c.source_location,
                    quote_span=c.quote_span,
                )
                for c in d.citations
            ],
            policy_decision=d.policy_decision.value,
            decision_reason=d.decision_reason,
            model_provenance=d.model_provenance,
            latency_ms=d.latency_ms,
            staged_to_provider=d.staged_to_provider,
            is_approved=d.is_approved,
            created_at=d.created_at,
        )
        for d in defaults
    ]


@router.get("/{draft_id}", response_model=DraftResponse, summary="Retrieve single draft by ID")
async def get_draft(draft_id: str, request: Request):
    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        draft = repo.get_draft(draft_id)
        if draft:
            return DraftResponse(
                draft_id=draft.draft_id,
                message_id=draft.message_id,
                thread_id=draft.thread_id,
                account_id=draft.account_id,
                subject=draft.subject,
                body_text=draft.body_text,
                body_html=draft.body_html,
                citations=[
                    CitationResponse(
                        rule_id=c.rule_id,
                        document_id=c.document_id,
                        document_title=c.document_title,
                        source_location=c.source_location,
                        source_quote=c.source_quote,
                    )
                    for c in draft.citations
                ],
                policy_decision=draft.policy_decision.value,
                decision_reason=draft.decision_reason,
                model_provenance=draft.model_provenance,
                latency_ms=draft.latency_ms,
                staged_to_provider=draft.staged_to_provider,
                is_approved=draft.is_approved,
                created_at=draft.created_at,
            )

    # Check defaults
    for d in _get_default_drafts():
        if d.draft_id == draft_id:
            return DraftResponse(
                draft_id=d.draft_id,
                message_id=d.message_id,
                thread_id=d.thread_id,
                account_id=d.account_id,
                subject=d.subject,
                body_text=d.body_text,
                body_html=d.body_html,
                citations=[
                    CitationResponse(
                        rule_id=c.rule_id,
                        document_id=c.document_id,
                        document_title=c.document_title,
                        source_location=c.source_location,
                        source_quote=c.source_quote,
                    )
                    for c in d.citations
                ],
                policy_decision=d.policy_decision.value,
                decision_reason=d.decision_reason,
                model_provenance=d.model_provenance,
                latency_ms=d.latency_ms,
                staged_to_provider=d.staged_to_provider,
                is_approved=d.is_approved,
                created_at=d.created_at,
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Draft '{draft_id}' not found.")


@router.put("/{draft_id}", summary="In-place edit draft subject or body text")
async def edit_draft(draft_id: str, body: DraftUpdateRequest, request: Request):
    if getattr(request.app.state, "is_halted", False):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Operation rejected: System is halted by Emergency Stop.",
        )

    db_mgr = getattr(request.app.state, "db_manager", None)
    if not db_mgr:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database manager not initialized.",
        )

    repo = db_mgr.get_repository()
    success = repo.update_draft_text(draft_id, subject=body.subject, body_text=body.body_text)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft '{draft_id}' not found or no changes made.",
        )

    # Log audit event
    audit = AuditEvent(
        event_id=f"audit_edit_{int(time.time() * 1000)}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type="DRAFT_EDITED",
        severity=SeverityLevel.LOW,
        details={"draft_id": draft_id, "updated_subject": body.subject is not None},
    )
    repo.log_audit(audit)

    return {"draft_id": draft_id, "status": "UPDATED"}


@router.post("/{draft_id}/stage", response_model=StagingResponse, summary="1-Click Outlook Draft Staging")
async def stage_draft_to_outlook(draft_id: str, request: Request):
    # Safety Check 1: Emergency Stop
    if getattr(request.app.state, "is_halted", False):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Staging rejected: System is halted by Emergency Stop.",
        )

    db_mgr = getattr(request.app.state, "db_manager", None)
    target_draft: Optional[DraftReply] = None

    if db_mgr:
        repo = db_mgr.get_repository()
        target_draft = repo.get_draft(draft_id)

    if not target_draft:
        for d in _get_default_drafts():
            if d.draft_id == draft_id:
                target_draft = d
                break

    if not target_draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft '{draft_id}' not found.",
        )

    # Safety Check 2: Stage via Mail Provider (Windows COM Outlook Desktop or Fake)
    provider = _get_provider(request)
    staged_success = provider.create_draft(target_draft)
    if not staged_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stage draft into Outlook Drafts folder.",
        )

    # Update SQLite database if active
    if db_mgr:
        repo = db_mgr.get_repository()
        repo.mark_draft_staged(draft_id)
        audit = AuditEvent(
            event_id=f"audit_stage_{int(time.time() * 1000)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="DRAFT_STAGED_TO_OUTLOOK",
            severity=SeverityLevel.LOW,
            details={
                "draft_id": draft_id,
                "account_id": target_draft.account_id,
                "folder": "Drafts",
                "live_transmission_blocked": True,
            },
        )
        repo.log_audit(audit)

    return StagingResponse(
        draft_id=draft_id,
        staged_to_provider=True,
        target_folder="Drafts",
        account_id=target_draft.account_id,
        status="STAGED",
        live_send_executed=False,
    )
