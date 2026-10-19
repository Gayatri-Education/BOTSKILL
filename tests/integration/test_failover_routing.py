"""Integration tests for AI Provider Failover and Local SLM Fallback."""

import pytest
from botskill.ai_providers.gateway import AIGateway
from botskill.ai_providers.local_llama import LocalLlamaRuntime
from botskill.ai_providers.router import ModelRouter
from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
    RoutingProfile,
)


class FailingCloudAdapter:
    """Simulates a remote cloud provider outage (e.g. rate limit, 503, DNS timeout)."""

    def __init__(self, name: str = "cloud_api"):
        self.name = name
        self.attempts = 0

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        self.attempts += 1
        return AIExecutionResult(
            request_id=request.request_id,
            output_text="",
            provider_id=self.name,
            model_name="cloud-gpt-4o",
            latency_ms=120.0,
            is_success=False,
            error_message="HTTP 503 Service Unavailable: Remote upstream is overloaded.",
            failure_category=FailureCategory.PROVIDER_UNAVAILABLE,
        )


def test_cloud_outage_fails_over_to_real_local_slm():
    """Verify that a remote provider failure automatically falls back to native local Qwen2.5 SLM."""
    router = ModelRouter(default_profile=RoutingProfile.CLOUD_PREFERRED)

    failing_cloud = FailingCloudAdapter("primary_cloud")
    local_slm = LocalLlamaRuntime()

    router.register_adapter("primary_cloud", failing_cloud, is_cloud=True)
    router.register_adapter("local_slm", local_slm, is_cloud=False)

    gateway = AIGateway(router)

    # Request allows cloud egress so cloud is tried first
    req = AIExecutionRequest(
        request_id="req_failover_integration_01",
        system_instruction="You are BOTSKILL local agent. Answer in one short sentence.",
        prompt="Confirm if internship interviews are conducted online.",
        max_tokens=64,
        temperature=0.1,
        allow_cloud_egress=True,
    )

    result = gateway.execute(req)

    # 1. Cloud was attempted once and failed
    assert failing_cloud.attempts == 1

    # 2. Gateway gracefully fell back to local SLM
    assert result.is_success is True
    assert result.provider_id == "local_llama_cpp"
    assert result.model_name == "qwen2.5-0.5b-instruct-q4_k_m"
    assert len(result.output_text) > 0

    local_slm.unload()


def test_local_only_profile_strictly_ignores_cloud_even_when_allowed():
    """Verify privacy invariant: under LOCAL_ONLY, cloud adapters are never even called."""
    router = ModelRouter(default_profile=RoutingProfile.LOCAL_ONLY)
    cloud_adapter = FailingCloudAdapter("unwanted_cloud")
    local_slm = LocalLlamaRuntime()

    router.register_adapter("unwanted_cloud", cloud_adapter, is_cloud=True)
    router.register_adapter("local_slm", local_slm, is_cloud=False)

    gateway = AIGateway(router)

    req = AIExecutionRequest(
        request_id="req_privacy_invariant",
        system_instruction="Be concise.",
        prompt="Status check",
        max_tokens=32,
        allow_cloud_egress=True,  # Even if request permits egress, policy blocks it
    )

    result = gateway.execute(req)

    # Assert cloud was never touched (0 attempts)
    assert cloud_adapter.attempts == 0
    assert result.provider_id == "local_llama_cpp"
    assert result.is_success is True

    local_slm.unload()


def test_finite_chain_all_providers_down():
    """Verify that when all providers fail, a clean structured degraded result is returned."""
    router = ModelRouter(default_profile=RoutingProfile.LOCAL_ONLY)
    router.register_adapter("broken_1", FailingCloudAdapter("broken_1"), is_cloud=False)
    router.register_adapter("broken_2", FailingCloudAdapter("broken_2"), is_cloud=False)

    gateway = AIGateway(router)
    req = AIExecutionRequest(request_id="req_all_down", prompt="Test")

    result = gateway.execute(req)
    assert result.is_success is False
    assert result.provider_id == "failover_exhausted"
    assert result.failure_category == FailureCategory.PROVIDER_UNAVAILABLE
