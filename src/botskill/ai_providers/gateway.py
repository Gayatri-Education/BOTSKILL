"""BOTSKILL — Unified AI Gateway Coordinator."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional
from botskill.ai_providers.router import ModelRouter
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
)

logger = logging.getLogger("botskill.ai_providers.gateway")


def sanitize_ai_error(err_msg: Optional[str]) -> str:
    """Sanitize sensitive credentials, API keys, and bearer tokens from error text."""
    if not err_msg:
        return ""
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}", r"\1[REDACTED]", err_msg, flags=re.IGNORECASE)
    sanitized = re.sub(r"(sk-[A-Za-z0-9_\-]{15,})", r"[REDACTED_API_KEY]", sanitized)
    sanitized = re.sub(r"([A-Fa-f0-9]{32,64})", r"[REDACTED_HASH]", sanitized)
    return sanitized


class AIGateway:
    """Dispatches execution requests through router failover chain with fallback."""

    def __init__(self, router: ModelRouter):
        self.router = router

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        plan = self.router.get_routing_plan(request)
        if not plan:
            return AIExecutionResult(
                request_id=request.request_id,
                output_text="",
                provider_id="none",
                model_name="none",
                latency_ms=0.0,
                is_success=False,
                error_message="No healthy AI providers available matching routing policy.",
                failure_category=FailureCategory.PROVIDER_UNAVAILABLE,
            )

        last_error = ""
        for provider_id in plan:
            adapter = self.router.adapters.get(provider_id)
            cb = self.router.circuit_breakers.get(provider_id)
            t0 = time.perf_counter()

            try:
                result = adapter.execute(request)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                if result.is_success:
                    if cb:
                        cb.record_success()
                    result.latency_ms = latency_ms
                    return result
                else:
                    if cb:
                        cb.record_failure()
                    last_error = result.error_message or "Execution failed"
                    logger.warning("Provider %s failed: %s", provider_id, last_error)
            except Exception as ex:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                if cb:
                    cb.record_failure()
                last_error = sanitize_ai_error(str(ex))
                logger.error("Exception in provider %s: %s", provider_id, last_error)

        return AIExecutionResult(
            request_id=request.request_id,
            output_text="",
            provider_id="failover_exhausted",
            model_name="none",
            latency_ms=0.0,
            is_success=False,
            error_message=f"All configured providers failed. Last error: {last_error}",
            failure_category=FailureCategory.PROVIDER_UNAVAILABLE,
        )
