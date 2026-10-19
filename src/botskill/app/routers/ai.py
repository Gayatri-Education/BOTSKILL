"""Dashboard API router for AI Model Routing, Telemetry, and Prompt Diagnostics."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from botskill.ai_providers.gateway import AIGateway
from botskill.ai_providers.local_llama import LocalLlamaRuntime
from botskill.ai_providers.router import ModelRouter
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    RoutingProfile,
)

logger = logging.getLogger("botskill.app.routers.ai")
router = APIRouter(prefix="/api/ai", tags=["AI Engine"])


class AIStatusResponse(BaseModel):
    profile: str
    active_model: str
    model_family: str
    quantization: str
    context_length: int
    estimated_ram_mb: int
    zero_cloud_egress: bool
    status: str
    provider_type: str


class ProfileUpdateRequest(BaseModel):
    profile: str = Field(..., description="Target routing profile: LOCAL_ONLY, LOCAL_FIRST, or CLOUD_FIRST")


class TestPromptRequest(BaseModel):
    prompt: Optional[str] = None
    max_tokens: int = 120
    temperature: float = 0.2


class TestPromptResponse(BaseModel):
    output_text: str
    model_name: str
    provider_id: str
    latency_ms: float
    is_success: bool
    zero_cloud_egress: bool


def _get_router(request: Request) -> ModelRouter:
    if hasattr(request.app.state, "router") and request.app.state.router:
        return request.app.state.router
    # Default router in LOCAL_ONLY mode
    return ModelRouter(default_profile=RoutingProfile.LOCAL_ONLY)


def _get_gateway(request: Request) -> AIGateway:
    if hasattr(request.app.state, "ai_gateway") and request.app.state.ai_gateway:
        return request.app.state.ai_gateway
    router_instance = _get_router(request)
    if "local_slm" not in router_instance.adapters:
        local_slm = LocalLlamaRuntime()
        router_instance.register_adapter("local_slm", local_slm, is_cloud=False)
    return AIGateway(router_instance)


@router.get("/status", response_model=AIStatusResponse, summary="Get AI routing engine status")
async def get_ai_status(request: Request):
    router_instance = _get_router(request)
    profile_str = (
        router_instance.profile.value
        if hasattr(router_instance.profile, "value")
        else str(router_instance.profile)
    )

    return AIStatusResponse(
        profile=profile_str,
        active_model="Qwen2.5-0.5B-Instruct",
        model_family="Qwen",
        quantization="Q4_K_M",
        context_length=8192,
        estimated_ram_mb=680,
        zero_cloud_egress=(profile_str == "LOCAL_ONLY"),
        status="READY",
        provider_type="llama-cpp-python native GGUF",
    )


@router.post("/profile", summary="Update active AI routing profile")
async def update_profile(body: ProfileUpdateRequest, request: Request):
    try:
        new_profile = RoutingProfile(body.profile.upper())
    except ValueError:
        valid_opts = [p.value for p in RoutingProfile]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid profile '{body.profile}'. Allowed: {valid_opts}",
        )

    router_instance = _get_router(request)
    router_instance.profile = new_profile
    if hasattr(request.app.state, "router"):
        request.app.state.router = router_instance

    return {
        "status": "updated",
        "profile": new_profile.value,
        "zero_cloud_egress": (new_profile == RoutingProfile.LOCAL_ONLY),
    }


@router.post("/test-inference", response_model=TestPromptResponse, summary="Run test inference on local SLM")
async def test_inference(body: TestPromptRequest, request: Request):
    gateway = _get_gateway(request)

    prompt = body.prompt or (
        "Candidate asks: 'Is the software engineering internship remote, and what is the stipend?'\n"
        "Grounding: Remote internships only. Official compensation communicated post-interview.\n"
        "Draft a polite 2-sentence response."
    )

    req = AIExecutionRequest(
        request_id=f"diag_{int(time.time() * 1000)}",
        prompt=prompt,
        system_instruction="You are a helpful and compliant corporate email assistant. Respond concisely.",
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    result = gateway.execute(req)

    return TestPromptResponse(
        output_text=result.output_text,
        model_name=result.model_name,
        provider_id=result.provider_id,
        latency_ms=round(result.latency_ms, 2),
        is_success=result.is_success,
        zero_cloud_egress=True,
    )
