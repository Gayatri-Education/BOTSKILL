"""BOTSKILL — AI Gateway & Router Schemas and Enums."""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RoutingProfile(str, enum.Enum):
    LOCAL_ONLY = "LOCAL_ONLY"          # Zero network egress, only local models & deterministic templates
    LOCAL_FIRST = "LOCAL_FIRST"        # Local models first, cloud fallback only if permitted
    CLOUD_PREFERRED = "CLOUD_PREFERRED"# Remote cloud first, local model as final generative fallback


class ProviderStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"


class FailureCategory(str, enum.Enum):
    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA = "QUOTA"
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    UNKNOWN = "UNKNOWN"


class AIExecutionRequest(BaseModel):
    request_id: str
    prompt: str
    system_instruction: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1024
    allow_cloud_egress: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIExecutionResult(BaseModel):
    request_id: str
    output_text: str
    provider_id: str
    model_name: str
    latency_ms: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    is_success: bool = True
    error_message: Optional[str] = None
    failure_category: Optional[FailureCategory] = None
