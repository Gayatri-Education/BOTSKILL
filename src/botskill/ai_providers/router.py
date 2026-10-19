"""BOTSKILL — AI Provider Router and Circuit Breakers."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
    ProviderStatus,
    RoutingProfile,
)

logger = logging.getLogger("botskill.ai_providers.router")


class CircuitBreaker:
    """Tracks consecutive failures and prevents storming an unavailable provider."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout_seconds
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self.state = ProviderStatus.HEALTHY

    def is_available(self) -> bool:
        if self.state == ProviderStatus.CIRCUIT_OPEN:
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = ProviderStatus.DEGRADED  # Half-open trial
                return True
            return False
        return True

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.state = ProviderStatus.HEALTHY

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.failure_threshold:
            self.state = ProviderStatus.CIRCUIT_OPEN
            logger.warning(
                "Circuit breaker OPEN after %d failures. Cooling off for %0.1fs",
                self.consecutive_failures,
                self.reset_timeout,
            )


class ModelRouter:
    """Selects and sequences providers according to profile, health, and privacy."""

    def __init__(self, default_profile: RoutingProfile = RoutingProfile.LOCAL_ONLY):
        self.profile = default_profile
        self.adapters: Dict[str, Any] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.is_cloud: Dict[str, bool] = {}

    def register_adapter(self, provider_id: str, adapter: Any, is_cloud: bool = False) -> None:
        self.adapters[provider_id] = adapter
        self.circuit_breakers[provider_id] = CircuitBreaker()
        self.is_cloud[provider_id] = is_cloud

    def get_routing_plan(self, request: AIExecutionRequest) -> List[str]:
        """Produce eligible provider IDs ordered by profile and privacy."""
        plan: List[str] = []

        local_adapters = [pid for pid, is_c in self.is_cloud.items() if not is_c]
        cloud_adapters = [pid for pid, is_c in self.is_cloud.items() if is_c]

        if self.profile == RoutingProfile.LOCAL_ONLY or not request.allow_cloud_egress:
            # Privacy invariant: zero cloud endpoints
            plan = [pid for pid in local_adapters if self.circuit_breakers[pid].is_available()]
        elif self.profile == RoutingProfile.LOCAL_FIRST:
            plan = (
                [pid for pid in local_adapters if self.circuit_breakers[pid].is_available()]
                + [pid for pid in cloud_adapters if self.circuit_breakers[pid].is_available()]
            )
        elif self.profile == RoutingProfile.CLOUD_PREFERRED:
            plan = (
                [pid for pid in cloud_adapters if self.circuit_breakers[pid].is_available()]
                + [pid for pid in local_adapters if self.circuit_breakers[pid].is_available()]
            )

        return plan
