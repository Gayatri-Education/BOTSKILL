"""Unit tests for BOTSKILL AI Gateway, Router, and Circuit Breakers."""

import pytest
from botskill.ai_providers.gateway import AIGateway, sanitize_ai_error
from botskill.ai_providers.router import CircuitBreaker, ModelRouter
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
    ProviderStatus,
    RoutingProfile,
)


class MockAdapter:
    """Mock adapter for deterministic testing of gateway failover."""

    def __init__(self, name: str, should_fail: bool = False, output_text: str = "Mock response"):
        self.name = name
        self.should_fail = should_fail
        self.output_text = output_text
        self.calls = 0

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        self.calls += 1
        if self.should_fail:
            return AIExecutionResult(
                request_id=request.request_id,
                output_text="",
                provider_id=self.name,
                model_name=f"{self.name}-model",
                latency_ms=10.0,
                is_success=False,
                error_message=f"Simulated failure in {self.name}",
                failure_category=FailureCategory.PROVIDER_UNAVAILABLE,
            )
        return AIExecutionResult(
            request_id=request.request_id,
            output_text=self.output_text,
            provider_id=self.name,
            model_name=f"{self.name}-model",
            latency_ms=15.0,
            is_success=True,
        )


def test_routing_profile_privacy_boundaries():
    """Verify that LOCAL_ONLY and egress restriction strictly eliminate cloud adapters."""
    router = ModelRouter(default_profile=RoutingProfile.LOCAL_ONLY)
    router.register_adapter("local_slm", MockAdapter("local_slm"), is_cloud=False)
    router.register_adapter("cloud_openai", MockAdapter("cloud_openai"), is_cloud=True)

    # 1. LOCAL_ONLY profile with egress=False
    req_local = AIExecutionRequest(request_id="r1", prompt="test", allow_cloud_egress=False)
    plan = router.get_routing_plan(req_local)
    assert plan == ["local_slm"]

    # 2. LOCAL_ONLY profile even if request requested egress=True
    req_egress = AIExecutionRequest(request_id="r2", prompt="test", allow_cloud_egress=True)
    plan = router.get_routing_plan(req_egress)
    assert plan == ["local_slm"]

    # 3. LOCAL_FIRST profile with egress=True allows cloud fallback
    router.profile = RoutingProfile.LOCAL_FIRST
    plan = router.get_routing_plan(req_egress)
    assert plan == ["local_slm", "cloud_openai"]

    # 4. CLOUD_PREFERRED profile with egress=True prefers cloud first
    router.profile = RoutingProfile.CLOUD_PREFERRED
    plan = router.get_routing_plan(req_egress)
    assert plan == ["cloud_openai", "local_slm"]


def test_circuit_breaker_tripping_and_recovery():
    """Verify that repeated failures open the circuit breaker and exclude the provider."""
    cb = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=0.1)
    assert cb.is_available() is True

    cb.record_failure()
    cb.record_failure()
    assert cb.state == ProviderStatus.HEALTHY
    assert cb.is_available() is True

    # Third failure trips circuit
    cb.record_failure()
    assert cb.state == ProviderStatus.CIRCUIT_OPEN
    assert cb.is_available() is False

    # Success resets consecutive failures
    cb.record_success()
    assert cb.state == ProviderStatus.HEALTHY
    assert cb.consecutive_failures == 0


def test_ai_gateway_failover_execution():
    """Test that gateway gracefully falls back from a failing adapter to a healthy adapter."""
    router = ModelRouter(default_profile=RoutingProfile.LOCAL_FIRST)
    failing_adapter = MockAdapter("primary_local", should_fail=True)
    healthy_adapter = MockAdapter("fallback_local", should_fail=False, output_text="Fallback response")

    router.register_adapter("primary_local", failing_adapter, is_cloud=False)
    router.register_adapter("fallback_local", healthy_adapter, is_cloud=False)

    gateway = AIGateway(router)
    req = AIExecutionRequest(request_id="req_failover", prompt="Hello", allow_cloud_egress=False)

    result = gateway.execute(req)

    assert result.is_success is True
    assert result.provider_id == "fallback_local"
    assert result.output_text == "Fallback response"
    assert failing_adapter.calls == 1
    assert healthy_adapter.calls == 1


def test_error_sanitization():
    """Verify that credentials and tokens are redacted from error strings."""
    raw_error = "Authentication failed with Bearer sk-ant-api03-abcdef1234567890 for hash 4f91e3a28b104928"
    sanitized = sanitize_ai_error(raw_error)
    assert "sk-ant-api03" not in sanitized
    assert "[REDACTED" in sanitized
