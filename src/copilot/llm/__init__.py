"""
ProdPlan ONE - LLM package (Sprint S)
======================================

Blueprint v2.0 §4.1 prescribes vLLM as the LLM serving layer, but Sprint K
shipped with Ollama. This package introduces a backend-agnostic
`LLMClient` protocol so callers can swap implementations via
`llm.backend` config without code changes.

Exports:
    LLMClient      — Protocol (duck-typed, works with existing OllamaClient)
    LLMResponse    — dict-like response envelope
    get_llm_client — factory reading TenantConfig.llm.backend
    OllamaBackend  — concrete wrapper around src.copilot.ollama_client
    VLLMBackend    — concrete wrapper around httpx for vLLM's OpenAI API
    structured_call — Pydantic-validated LLM call (Sprint S.3)
"""

from .base import LLMClient, LLMResponse, BackendUnavailableError
from .factory import get_llm_client
from .ollama import OllamaBackend
from .vllm import VLLMBackend

__all__ = [
    "LLMClient",
    "LLMResponse",
    "BackendUnavailableError",
    "get_llm_client",
    "OllamaBackend",
    "VLLMBackend",
]
