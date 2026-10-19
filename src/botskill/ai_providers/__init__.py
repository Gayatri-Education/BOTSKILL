"""BOTSKILL AI Providers Package."""

from botskill.ai_providers.gateway import AIGateway, sanitize_ai_error
from botskill.ai_providers.local_llama import LocalLlamaRuntime, format_chatml_prompt
from botskill.ai_providers.router import CircuitBreaker, ModelRouter
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
    ProviderStatus,
    RoutingProfile,
)

__all__ = [
    "AIGateway",
    "CircuitBreaker",
    "LocalLlamaRuntime",
    "ModelRouter",
    "AIExecutionRequest",
    "AIExecutionResult",
    "FailureCategory",
    "ProviderStatus",
    "RoutingProfile",
    "format_chatml_prompt",
    "sanitize_ai_error",
]
