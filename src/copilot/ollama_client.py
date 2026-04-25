"""
ProdPlan ONE - COPILOT Ollama Client
=====================================

Cliente robusto para Ollama com timeout, retry, circuit breaker.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import httpx

from src.shared.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Cliente async para Ollama com:
    - Timeout: 30s
    - Retry: 2 tentativas com backoff exponencial
    - Circuit breaker: após 3 falhas consecutivas → OFFLINE por 60s
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2,
    ):
        self.base_url = base_url or getattr(settings, "ollama_base_url", "http://localhost:11434")
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Circuit breaker state
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._circuit_open_until: Optional[datetime] = None
        self._circuit_breaker_window = timedelta(seconds=60)
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with keep-alive."""
        if self._client is None:
            # Configurar keep-alive para reduzir latência
            limits = httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=600,  # 10 minutos
            )
            # Usar timeout explícito
            timeout = httpx.Timeout(self.timeout, connect=5.0)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                limits=limits,
                http2=False,  # Desabilitar HTTP/2 para evitar problemas de compatibilidade
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _check_circuit_breaker(self) -> bool:
        """Verificar se circuit breaker está aberto."""
        if self._circuit_open_until is None:
            return True  # Circuit fechado
        
        if datetime.utcnow() < self._circuit_open_until:
            # Circuit ainda aberto, mas logar para debugging
            remaining = (self._circuit_open_until - datetime.utcnow()).total_seconds()
            logger.debug(f"Circuit breaker aberto. Fecha em {remaining:.1f}s")
            return False  # Circuit aberto
        
        # Circuit fechou - reset
        logger.info("Circuit breaker fechou automaticamente após timeout")
        self._circuit_open_until = None
        self._failure_count = 0
        return True
    
    def reset_circuit_breaker(self):
        """Reset manual do circuit breaker (útil para debugging)."""
        logger.info("Circuit breaker resetado manualmente")
        self._circuit_open_until = None
        self._failure_count = 0
        self._last_failure_time = None
    
    def _record_failure(self):
        """Registar falha e abrir circuit se necessário."""
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()
        
        if self._failure_count >= 3:
            self._circuit_open_until = datetime.utcnow() + self._circuit_breaker_window
            logger.warning(
                f"Circuit breaker aberto após {self._failure_count} falhas. "
                f"Fechado até {self._circuit_open_until}"
            )
    
    def _record_success(self):
        """Registar sucesso e reset circuit breaker."""
        self._failure_count = 0
        self._last_failure_time = None
        self._circuit_open_until = None
    
    async def chat(
        self,
        prompt: str,
        model: str,
        format: Optional[str] = "json",
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        num_ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chamar Ollama /api/chat.

        Args:
            prompt: Prompt do utilizador
            model: Nome do modelo (ex: "gemma4:e4b")
            format: "json" para resposta estruturada
            history: Previous conversation turns [{"role": "user"|"assistant", "content": "..."}]
            system_prompt: Optional system prompt prepended to messages
            num_ctx: Override context window for this call. ``None`` →
                uses ``settings.ollama_num_ctx``. Multi-turn callers
                should pass a larger value when prior history is long
                (see ``run_rlm_agent_continue``).
            num_predict: Override max tokens to generate for this call.
                ``None`` → uses ``settings.ollama_num_predict``.

        Returns:
            Dict com resposta do LLM

        Raises:
            Exception se circuit breaker aberto ou falha após retries
        """
        if not self._check_circuit_breaker():
            raise Exception("Circuit breaker aberto - Ollama temporariamente indisponível")

        client = await self._get_client()

        # Build messages array with optional system prompt and history
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        effective_num_ctx = num_ctx if num_ctx is not None else getattr(settings, "ollama_num_ctx", 4096)
        effective_num_predict = num_predict if num_predict is not None else getattr(settings, "ollama_num_predict", 512)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": getattr(settings, "ollama_keep_alive", "30m"),
            "options": {
                "temperature": getattr(settings, "ollama_temperature", 0.1),
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": effective_num_predict,
                "num_ctx": effective_num_ctx,
                "repeat_penalty": 1.1,
                "num_thread": 8,
            },
        }

        if format == "json":
            payload["format"] = "json"
        
        # Retry com backoff exponencial
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                
                data = response.json()
                self._record_success()
                
                # Extrair resposta do formato Ollama
                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    if format == "json":
                        import json
                        return json.loads(content)
                    return {"content": content}
                
                return data
                
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Ollama timeout (tentativa {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(f"Ollama HTTP error: {e}")
                self._record_failure()
                raise
                
            except Exception as e:
                last_error = e
                logger.error(f"Ollama error (tentativa {attempt + 1}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
        
        # Todas as tentativas falharam
        self._record_failure()
        raise Exception(f"Ollama falhou após {self.max_retries + 1} tentativas: {last_error}")
    
    async def embeddings(
        self,
        text: str,
        model: str,
    ) -> List[float]:
        """
        Obter embeddings via Ollama /api/embeddings.
        
        Args:
            text: Texto para embed
            model: Nome do modelo de embeddings
        
        Returns:
            Lista de floats (embedding vector)
        """
        if not self._check_circuit_breaker():
            raise Exception("Circuit breaker aberto - Ollama temporariamente indisponível")
        
        client = await self._get_client()
        
        payload = {
            "model": model,
            "prompt": text,
        }
        
        try:
            response = await client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            
            data = response.json()
            self._record_success()
            
            if "embedding" in data:
                return data["embedding"]
            
            raise ValueError("Resposta Ollama não contém 'embedding'")
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Erro ao obter embeddings: {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Verificar se Ollama está disponível.
        
        Returns:
            True se disponível, False caso contrário
        """
        # Se circuit breaker está aberto, logar mas ainda tentar (para não ficar preso)
        circuit_open = not self._check_circuit_breaker()
        if circuit_open:
            logger.warning("Ollama health check: circuit breaker aberto, mas tentando mesmo assim para verificar se já recuperou")
        
        try:
            # Criar cliente temporário para health check (evitar problemas com cliente global)
            # Não usar base_url no cliente, usar URL completa para evitar problemas
            timeout = httpx.Timeout(5.0, connect=3.0)
            async with httpx.AsyncClient(timeout=timeout, http2=False) as client:
                url = f"{self.base_url}/api/tags"
                response = await client.get(url)
                response.raise_for_status()
                
                # Verificar que a resposta tem modelos
                data = response.json()
                if "models" in data:
                    self._record_success()
                    logger.info(f"Ollama health check OK: {len(data.get('models', []))} modelos disponíveis")
                    return True
                else:
                    logger.warning("Ollama health check: resposta sem 'models'")
                    self._record_failure()
                    return False
                
        except httpx.TimeoutException as e:
            logger.warning(f"Ollama health check timeout: {e}")
            self._record_failure()
            return False
        except httpx.ConnectError as e:
            logger.warning(f"Ollama health check: não conseguiu conectar a {self.base_url}: {e}")
            self._record_failure()
            return False
        except Exception as e:
            logger.warning(f"Ollama health check falhou: {type(e).__name__}: {e}")
            self._record_failure()
            return False


# Instância global (lazy)
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
        _ollama_client = OllamaClient(base_url=base_url)
    return _ollama_client


