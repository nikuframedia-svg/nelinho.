"""
ProdPlan ONE - LLM Protocol (Sprint S.1)
=========================================

The `LLMClient` protocol. Structured so that the existing
`src.copilot.ollama_client.OllamaClient` satisfies it by duck-typing —
no forced subclass, no breaking changes to the 5 existing callers.
Sprint S.2 adds a vLLM adapter that also implements the protocol.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class BackendUnavailableError(Exception):
    """Raised when the circuit breaker is open or the backend refuses."""


# Response envelope the protocol consumes. Kept dict-based because the
# existing callers (service.py, rag.py, tool_executor.py) already parse
# this shape directly and changing it to a Pydantic model would force a
# cross-module migration beyond the Sprint S scope.
LLMResponse = Dict[str, Any]


@runtime_checkable
class LLMClient(Protocol):
    """Minimum surface both Ollama and vLLM backends expose.

    Notes on parameter naming — we mirror `OllamaClient.chat` so legacy
    callers that already pass positional args keep working when they
    switch to `get_llm_client()`.
    """

    async def chat(
        self,
        prompt: str,
        model: str,
        format: Optional[str] = "json",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        ...

    async def embeddings(self, text: str, model: str) -> List[float]:
        ...

    async def health_check(self) -> bool:
        ...

    def reset_circuit_breaker(self) -> None:
        ...
