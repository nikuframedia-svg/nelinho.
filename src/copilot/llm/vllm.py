"""
ProdPlan ONE - vLLM Backend (Sprint S.2)
==========================================

vLLM serves the OpenAI-compatible Chat Completions API at
`POST {base_url}/v1/chat/completions` and embeddings at
`POST {base_url}/v1/embeddings`. This backend matches the `LLMClient`
protocol and replicates the circuit-breaker pattern used by the Ollama
backend so callers see consistent failure semantics.

When `format="json"`, we pass `response_format={"type": "json_object"}`
so compliant models return valid JSON; callers get a parsed dict back.

Configuration (read via TenantConfig category `llm`):
  - `vllm.base_url`  (default http://vllm:8000)
  - `vllm.model`     (default Qwen2.5-7B-Instruct-AWQ)
  - `vllm.timeout_s` (default 60)
  - `vllm.embedding_model` (falls back to `vllm.model`)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import BackendUnavailableError, LLMClient, LLMResponse

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = "http://vllm:8000"
DEFAULT_MODEL = "Qwen2.5-7B-Instruct-AWQ"
DEFAULT_TIMEOUT_S = 60.0
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_WINDOW_S = 60.0


class VLLMBackend:
    """OpenAI-compatible vLLM adapter with circuit breaker + JSON mode."""

    backend_name = "vllm"

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.default_model = model or DEFAULT_MODEL
        self.default_embedding_model = embedding_model or self.default_model
        self.timeout_s = timeout_s or DEFAULT_TIMEOUT_S
        self._failure_count = 0
        self._circuit_open_until: Optional[float] = None

    # ─── LLMClient protocol ────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        model: str,
        format: Optional[str] = "json",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        self._raise_if_breaker_open()

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": 0.1,
            "stream": False,
        }
        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            content = await self._post_chat(payload)
        except Exception as exc:
            self._register_failure()
            raise BackendUnavailableError(str(exc)) from exc

        self._register_success()

        if format == "json":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Some models wrap JSON in a code fence; tolerate it.
                stripped = content.strip().strip("`")
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise BackendUnavailableError(
                        f"vLLM returned invalid JSON: {exc}"
                    ) from exc
        return {"content": content}

    async def embeddings(self, text: str, model: str) -> List[float]:
        self._raise_if_breaker_open()
        payload = {
            "model": model or self.default_embedding_model,
            "input": text,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/embeddings", json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            self._register_failure()
            raise BackendUnavailableError(str(exc)) from exc
        self._register_success()
        try:
            return list(data["data"][0]["embedding"])
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendUnavailableError(
                f"vLLM embedding response malformed: {data!r}",
            ) from exc

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception as exc:
            logger.debug("vLLM health_check failed: %s", exc)
            return False

    def reset_circuit_breaker(self) -> None:
        self._failure_count = 0
        self._circuit_open_until = None

    # ─── internals ────────────────────────────────────────────────────────

    async def _post_chat(self, payload: Dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions", json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"vLLM chat response malformed: {data!r}") from exc

    def _raise_if_breaker_open(self) -> None:
        if self._circuit_open_until is None:
            return
        if time.monotonic() >= self._circuit_open_until:
            self.reset_circuit_breaker()
            return
        remaining = self._circuit_open_until - time.monotonic()
        raise BackendUnavailableError(
            f"vLLM circuit breaker open ({remaining:.1f}s remaining)",
        )

    def _register_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = time.monotonic() + CIRCUIT_BREAKER_WINDOW_S
            logger.warning(
                "vLLM circuit breaker tripped after %d failures",
                self._failure_count,
            )

    def _register_success(self) -> None:
        self._failure_count = 0
        self._circuit_open_until = None


# Protocol compliance check at import time.
_verify: LLMClient = VLLMBackend()  # type: ignore[assignment]
del _verify
