"""Unit tests for Native Local SLM Runtime (llama-cpp-python & Qwen2.5-0.5B GGUF)."""

import os
import pytest
from botskill.ai_providers.local_llama import LocalLlamaRuntime, format_chatml_prompt
from botskill.ai_providers.schema import AIExecutionRequest


def test_chatml_prompt_formatting():
    """Verify ChatML prompt construction for Qwen2.5."""
    messages = [
        {"role": "system", "content": "You are a professional email assistant."},
        {"role": "user", "content": "Draft a short acknowledgement."},
    ]
    prompt = format_chatml_prompt(messages)
    assert "<|im_start|>system\nYou are a professional email assistant.<|im_end|>" in prompt
    assert "<|im_start|>user\nDraft a short acknowledgement.<|im_end|>" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


def test_local_model_health_check():
    """Verify health check reports model readiness."""
    runtime = LocalLlamaRuntime()
    health = runtime.health_check()
    assert health["provider"] == "llama_cpp"
    assert health["device"] == "CPU"
    assert os.path.exists(health["model_path"]) is True
    assert health["status"] == "READY"


def test_real_local_cpu_inference():
    """Execute real synthetic inference on CPU using Qwen2.5-0.5B GGUF."""
    runtime = LocalLlamaRuntime()
    req = AIExecutionRequest(
        request_id="test_req_slm_001",
        system_instruction="You are BOTSKILL local assistant. Answer in one concise sentence.",
        prompt="Confirm if internship applications are open.",
        max_tokens=64,
        temperature=0.1,
        allow_cloud_egress=False,
    )

    result = runtime.execute(req)

    assert result.is_success is True
    assert result.provider_id == "local_llama_cpp"
    assert result.model_name == "qwen2.5-0.5b-instruct-q4_k_m"
    assert len(result.output_text) > 0
    assert result.latency_ms > 0.0

    # Clean unload
    runtime.unload()
    assert runtime._model is None
