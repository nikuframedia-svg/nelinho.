"""
ProdPlan ONE - Ollama Backend (Sprint S.1 wrapper)
====================================================

Thin adapter that presents the existing `OllamaClient` singleton behind
the `LLMClient` protocol. Keeps the 5 legacy callers working without
modification while enabling the factory to select Ollama vs vLLM at
runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.copilot.ollama_client import get_ollama_client

from .base import LLMClient, LLMResponse


class OllamaBackend:
    """Implements `LLMClient` by delegating to the module-level singleton."""

    backend_name = "ollama"

    def __init__(self) -> None:
        self._client = get_ollama_client()

    async def chat(
        self,
        prompt: str,
        model: str,
        format: Optional[str] = "json",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        return await self._client.chat(
            prompt=prompt,
            model=model,
            format=format,
            history=history,
            system_prompt=system_prompt,
        )

    async def embeddings(self, text: str, model: str) -> List[float]:
        return await self._client.embeddings(text=text, model=model)

    async def health_check(self) -> bool:
        return await self._client.health_check()

    def reset_circuit_breaker(self) -> None:
        self._client.reset_circuit_breaker()


# Runtime check — enforce protocol compliance at import time.
_verify: LLMClient = OllamaBackend()  # type: ignore[assignment]
del _verify
