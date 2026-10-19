"""Dashboard API router for Autonomy Controls and Emergency Kill Switch."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from botskill.core.models import AuditEvent, AutonomyLevel, SeverityLevel

logger = logging.getLogger("botskill.app.routers.autonomy")
router = APIRouter(prefix="/api/autonomy", tags=["Autonomy & Controls"])


class AutonomyStatusResponse(BaseModel):
    is_halted: bool
    autonomy_level: str
    live_send_permitted: bool
    safety_mode: str


class KillSwitchResponse(BaseModel):
    status: str
    is_halted: bool
    message: str


@router.get("/status", response_model=AutonomyStatusResponse, summary="Check autonomy state and emergency kill switch")
async def get_autonomy_status(request: Request):
    is_halted = getattr(request.app.state, "is_halted", False)
    return AutonomyStatusResponse(
        is_halted=is_halted,
        autonomy_level=AutonomyLevel.DRAFT_ONLY.value,
        live_send_permitted=False,
        safety_mode="DRAFT_ONLY_STAGED_IN_OUTLOOK",
    )


@router.post("/kill", response_model=KillSwitchResponse, summary="Emergency Stop: Halt all processing immediately")
async def emergency_kill(request: Request):
    request.app.state.is_halted = True
    logger.critical("EMERGENCY KILL SWITCH ACTIVATED! All background sync and staging halted.")

    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        audit = AuditEvent(
            event_id=f"audit_kill_{int(time.time() * 1000)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="EMERGENCY_STOP_HALTED",
            severity=SeverityLevel.CRITICAL,
            details={"trigger": "manual_kill_switch", "status": "ALL_OPERATIONS_HALTED"},
        )
        repo.log_audit(audit)

    return KillSwitchResponse(
        status="HALTED",
        is_halted=True,
        message="Emergency Stop activated. All Outlook background sync and draft staging halted immediately.",
    )


@router.post("/resume", response_model=KillSwitchResponse, summary="Resume normal operations after emergency stop")
async def resume_processing(request: Request):
    request.app.state.is_halted = False
    logger.info("Operations resumed from emergency stop.")

    db_mgr = getattr(request.app.state, "db_manager", None)
    if db_mgr:
        repo = db_mgr.get_repository()
        audit = AuditEvent(
            event_id=f"audit_resume_{int(time.time() * 1000)}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="PROCESSING_RESUMED",
            severity=SeverityLevel.LOW,
            details={"trigger": "supervisor_resume", "status": "OPERATIONS_RESUMED"},
        )
        repo.log_audit(audit)

    return KillSwitchResponse(
        status="ACTIVE",
        is_halted=False,
        message="System operations resumed safely in DRAFT_ONLY mode.",
    )
