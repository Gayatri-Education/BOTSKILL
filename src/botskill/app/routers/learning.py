"""Dashboard API router for Controlled Learning, Scenarios, and Sanitized Exports."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from botskill.core.models import AuditEvent, EmailMessage, MessageState, SeverityLevel
from botskill.learning.sanitizer import PIISanitizer, SecurityError
from botskill.learning.scenarios import ScenarioCandidate, ScenarioEngine

logger = logging.getLogger("botskill.app.routers.learning")
router = APIRouter(prefix="/api/learning", tags=["Controlled Learning & Governance"])


class ProposeScenarioRequest(BaseModel):
    subject: str
    body_text: str
    account_id: str = "hr@aivaratech.online"


class ExportRequest(BaseModel):
    include_scenarios: bool = True
    include_draft_evals: bool = True


class SelfModificationProbe(BaseModel):
    target: str


def _get_engine(request: Request) -> ScenarioEngine:
    if hasattr(request.app.state, "scenario_engine") and request.app.state.scenario_engine:
        return request.app.state.scenario_engine
    engine = ScenarioEngine()
    request.app.state.scenario_engine = engine
    return engine


@router.get("/scenarios", response_model=List[ScenarioCandidate], summary="List proposed learning scenarios")
async def list_scenarios(request: Request):
    engine = _get_engine(request)
    now = datetime.now(timezone.utc).isoformat()
    return [
        ScenarioCandidate(
            scenario_id="scen-baseline-001",
            archetype="INTERNSHIP_COMPENSATION_INQUIRY",
            sanitized_subject="Internship Application & Stipend Inquiry",
            sanitized_body="Candidate asks for stipend numbers prior to interview. Response must enforce prohibition.",
            suggested_rules=["RULE-HR-001"],
            is_approved=True,
            created_at=now,
        ),
        ScenarioCandidate(
            scenario_id="scen-baseline-002",
            archetype="REMOTE_WORK_INQUIRY",
            sanitized_subject="Remote Work Options",
            sanitized_body="Inquiry regarding remote work flexibility for engineering internships.",
            suggested_rules=["RULE-HR-002"],
            is_approved=True,
            created_at=now,
        ),
    ]


@router.post("/propose", response_model=ScenarioCandidate, summary="Propose candidate scenario from message")
async def propose_scenario(body: ProposeScenarioRequest, request: Request):
    engine = _get_engine(request)

    dummy_msg = EmailMessage(
        message_id=f"msg_learn_{int(time.time() * 1000)}",
        provider_id="learning_input",
        thread_id=body.subject.lower(),
        account_id=body.account_id,
        sender="unredacted_user@example.com",
        recipients=[body.account_id],
        subject=body.subject,
        body_text=body.body_text,
        received_at=datetime.now(timezone.utc).isoformat(),
        state=MessageState.DISCOVERED,
        idempotency_key=f"learn_key_{time.time()}",
    )

    candidate = engine.propose_from_message(dummy_msg)

    # Log audit event
    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        audit = AuditEvent(
            event_id=f"audit_scen_{int(time.time() * 1000)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SCENARIO_PROPOSED",
            severity=SeverityLevel.LOW,
            details={"scenario_id": candidate.scenario_id, "archetype": candidate.archetype},
        )
        repo.log_audit(audit)

    return candidate


@router.post("/export", summary="Generate privacy-audited sanitized export")
async def export_sanitized_data(body: ExportRequest, request: Request):
    sanitizer = PIISanitizer()

    # Create sanitized export dataset
    sample_records = [
        {
            "id": "rec_001",
            "archetype": "INTERNSHIP_COMPENSATION_INQUIRY",
            "text": "Candidate asked: 'What is the compensation for remote software interns?'",
            "rule_enforced": "RULE-HR-001",
        },
        {
            "id": "rec_002",
            "archetype": "SUPPORT_SLA_INQUIRY",
            "text": "Customer queried turnaround time: 'When will onboarding be complete?'",
            "rule_enforced": "RULE-SUP-001",
        },
    ]

    try:
        sanitizer.validate_for_export(sample_records)
    except SecurityError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    return {
        "export_id": f"export_{int(time.time() * 1000)}",
        "record_count": len(sample_records),
        "status": "SANITIZED_EXPORT_READY",
        "pii_verified_clean": True,
        "records": sample_records,
    }


@router.post("/verify-safety", summary="Verify self-modification defense blocks attempts")
async def verify_safety_defense(body: SelfModificationProbe, request: Request):
    engine = _get_engine(request)
    try:
        engine.verify_no_self_modification(body.target)
    except SecurityError as sec_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(sec_err),
        )

    return {"status": "ALLOWED", "target": body.target}
