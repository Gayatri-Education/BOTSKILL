"""BOTSKILL — Native Local SLM Runtime using llama-cpp-python and GGUF."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from botskill.ai_providers.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    FailureCategory,
)

logger = logging.getLogger("botskill.ai_providers.local_llama")


def format_chatml_prompt(messages: List[Dict[str, str]]) -> str:
    """Format messages into ChatML prompt for Qwen2.5."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)


class LocalLlamaRuntime:
    """Local GGUF execution engine wrapping llama-cpp-python."""

    _instance = None
    _model = None
    _lock = threading.Lock()

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            # Default to bundled model in models/
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            model_path = str(base_dir / "models" / "qwen2.5-0.5b-instruct-q4_k_m.gguf")

        self.model_path = model_path
        self.model_name = "qwen2.5-0.5b-instruct-q4_k_m"

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                if not os.path.exists(self.model_path):
                    raise FileNotFoundError(f"Model artifact not found at {self.model_path}")
                import llama_cpp
                logger.info("Loading local GGUF model: %s", self.model_path)
                self._model = llama_cpp.Llama(
                    model_path=self.model_path,
                    n_ctx=4096,
                    n_threads=min(4, os.cpu_count() or 4),
                    verbose=False,
                )
            return self._model

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on local model runtime."""
        exists = os.path.exists(self.model_path)
        return {
            "status": "READY" if exists else "NOT_INSTALLED",
            "provider": "llama_cpp",
            "model_path": self.model_path,
            "artifact_exists": exists,
            "model_loaded": self._model is not None,
            "device": "CPU",
        }

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        """Execute inference locally on CPU with zero cloud network egress."""
        t0 = time.perf_counter()
        try:
            model = self._get_model()

            messages = []
            if request.system_instruction:
                messages.append({"role": "system", "content": request.system_instruction})
            messages.append({"role": "user", "content": request.prompt})

            prompt = format_chatml_prompt(messages)

            resp = model(
                prompt,
                max_tokens=request.max_tokens or 512,
                temperature=request.temperature or 0.2,
                stop=["<|im_end|>", "<|endoftext|>"],
            )

            latency_ms = (time.perf_counter() - t0) * 1000.0
            output_text = resp["choices"][0]["text"].strip()
            usage = resp.get("usage", {})

            return AIExecutionResult(
                request_id=request.request_id,
                output_text=output_text,
                provider_id="local_llama_cpp",
                model_name=self.model_name,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                is_success=True,
            )

        except Exception as ex:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.error("Local inference error: %s", ex)
            return AIExecutionResult(
                request_id=request.request_id,
                output_text="",
                provider_id="local_llama_cpp",
                model_name=self.model_name,
                latency_ms=latency_ms,
                is_success=False,
                error_message=str(ex),
                failure_category=FailureCategory.PROVIDER_UNAVAILABLE,
            )

    def unload(self) -> None:
        """Unload model to free system RAM."""
        with self._lock:
            if self._model is not None:
                del self._model
                self._model = None
                logger.info("Unloaded local GGUF model from memory.")
