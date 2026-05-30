"""MeasureIndex — Q.105.A retrieval BM25+FAISS+RRF sobre as MEDIDAS do
contrato (não sobre materiais).

**Motivação Q.104**: com 11 cubes (15 medidas) no prompt, o `qwen3.5:9b`
perde disciplina e inventa nomes de cubes (`resina_lavesan_en_720.total`,
`quimica_consumo_catalisador.total`) em vez de usar `consumo_material.consumo`.
Resultado Q.104: consumo 18/18 abstain.

**Solução Q.105.A**: cada pergunta passa por retrieval BM25+FAISS+RRF sobre
o ÍNDICE DE MEDIDAS (built de `description + synonyms` de cada MeasureSpec).
Top-K=5 candidatas entram no prompt em vez de todas. Prompt deixa de crescer
com nº de medidas (independência do teto Q.104).

**Arquitetura**: paralela a `material_retrieval.py` (Q.93.E provada). Reutiliza
`normalize_tokens` e `rrf_fuse` directamente. Sem aliases (medidas não têm
problema de ortografia como materiais — o mismatch é semântico, resolvido
pelo conjunto BM25+embedding).

**Fluxo**:
1. Refresh: `scripts/refresh_cube_measure_index.py` lê o REGISTRY,
   constrói tokens (BM25) + embeddings (Ollama nomic-embed-text).
2. Persistência: `cube/data/measure_index.npz` + `.faiss` + `_bm25.pkl`.
3. Singleton lazy via `MeasureIndex.get()`. `interpret()` chama
   `top_k_hybrid(question, ollama, k=5)` antes do LLM.

Air-gapped (FAISS local, Ollama local).
"""
from __future__ import annotations

import logging
import pickle
import threading
from pathlib import Path

import faiss  # type: ignore[import-untyped]
import numpy as np

from src.copilot.cube.material_retrieval import (
    EMBED_MODEL_DEFAULT,
    RRF_K,
    normalize_tokens,
    rrf_fuse,
)
from src.copilot.llm.base import LLMClient


log = logging.getLogger(__name__)

# Caminhos do índice de medidas (paralelos aos de materiais).
CUBE_DATA_DIR = Path(__file__).resolve().parents[3] / "cube" / "data"
MEASURE_INDEX_NPZ_PATH = CUBE_DATA_DIR / "measure_index.npz"
MEASURE_INDEX_FAISS_PATH = CUBE_DATA_DIR / "measure_index.faiss"
MEASURE_INDEX_BM25_PATH = CUBE_DATA_DIR / "measure_index_bm25.pkl"


class MeasureIndexNotBuilt(RuntimeError):
    """Levantada quando o índice não existe ainda — correr o script de refresh."""


class MeasureIndex:
    """Índice BM25+FAISS+RRF para retrieval de medidas.

    Singleton process-wide, mas o `OllamaClient` é passado em cada chamada
    (httpx pool atado a event loop — não cachear).
    """

    _instance: "MeasureIndex | None" = None
    _lock = threading.Lock()

    def __init__(self, embed_model: str = EMBED_MODEL_DEFAULT) -> None:
        self.embed_model = embed_model
        self._measures: np.ndarray | None = None  # array[str] de nomes (e.g. consumo_material.consumo)
        self._index: faiss.Index | None = None
        self._hash: str | None = None
        self._loaded: bool = False
        self._bm25: object | None = None  # BM25Okapi

    @classmethod
    def get(cls, embed_model: str = EMBED_MODEL_DEFAULT) -> "MeasureIndex":
        """Singleton process-wide do índice."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = MeasureIndex(embed_model=embed_model)
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset para testes (re-load do disco). Não-thread-safe — só em pytest."""
        with cls._lock:
            cls._instance = None

    def load(self) -> None:
        """Carrega .npz + .faiss + .pkl do disco. Idempotente."""
        if self._loaded:
            return
        if not MEASURE_INDEX_NPZ_PATH.exists() or not MEASURE_INDEX_FAISS_PATH.exists():
            raise MeasureIndexNotBuilt(
                f"Índice de medidas não encontrado em {MEASURE_INDEX_NPZ_PATH} / "
                f"{MEASURE_INDEX_FAISS_PATH}. Corre primeiro:\n"
                f"    python scripts/refresh_cube_measure_index.py"
            )
        archive = np.load(MEASURE_INDEX_NPZ_PATH, allow_pickle=True)
        self._measures = archive["measures"]
        self._hash = str(archive["hash"])
        self._index = faiss.read_index(str(MEASURE_INDEX_FAISS_PATH))
        if MEASURE_INDEX_BM25_PATH.exists():
            with MEASURE_INDEX_BM25_PATH.open("rb") as fh:
                self._bm25 = pickle.load(fh)
        self._loaded = True
        log.info(
            "MeasureIndex loaded: %d medidas, hash=%s, bm25=%s",
            len(self._measures),
            self._hash[:12],
            "yes" if self._bm25 is not None else "no",
        )

    @property
    def hash(self) -> str:
        if not self._loaded:
            self.load()
        assert self._hash is not None
        return self._hash

    @property
    def n_measures(self) -> int:
        if not self._loaded:
            self.load()
        assert self._measures is not None
        return len(self._measures)

    async def top_k(
        self,
        query_text: str,
        ollama: LLMClient,
        k: int = 5,
    ) -> list[tuple[str, float]]:
        """Embed a pergunta e devolve top-k medidas mais próximas (cosine).

        Devolve `[(measure_name, score_cosine), ...]` ordenado desc.
        """
        if not self._loaded:
            self.load()
        assert self._measures is not None
        assert self._index is not None

        emb = await ollama.embeddings(query_text, model=self.embed_model)
        vec = np.asarray(emb, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        vec = vec / norm

        scores, indices = self._index.search(vec, k)
        out: list[tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue
            out.append((str(self._measures[int(idx)]), float(score)))
        return out

    def _bm25_top_k(self, query_text: str, k: int) -> list[tuple[str, float]]:
        """BM25 top-k sobre tokens normalizados de description+synonyms."""
        assert self._measures is not None
        if self._bm25 is None:
            return []
        query_tokens = normalize_tokens(query_text)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)  # type: ignore[attr-defined]
        order = np.argsort(scores)[::-1][:k]
        return [
            (str(self._measures[int(i)]), float(scores[int(i)]))
            for i in order
            if scores[int(i)] > 0.0
        ]

    async def top_k_hybrid(
        self,
        query_text: str,
        ollama: LLMClient,
        k: int = 5,
        k_each: int = 10,
    ) -> list[tuple[str, float]]:
        """Q.105.A — top-k híbrido FAISS + BM25 via RRF.

        - FAISS top-k_each: captura semântica (embedding nomic-embed-text).
        - BM25 top-k_each: palavra-chave PT-PT (custo/custou/gastámos…).
        - RRF (k=60): premia candidatas em ambas as listas.
        - Devolve top-k final ordenado por RRF score desc.

        Sem aliases (não aplicável a medidas — só a materiais com
        ortografia divergente catalizador↔catalisador).

        Graceful degrade: se BM25 não existe, cai para FAISS-only.

        Resultado contrato: `[(measure_name, rrf_score), ...]`.
        `measure_name` é "consumo_material.consumo" estilo — chave do
        MEASURE_REGISTRY.
        """
        if self._bm25 is None:
            return await self.top_k(query_text, ollama=ollama, k=k)

        faiss_results = await self.top_k(query_text, ollama=ollama, k=k_each)
        bm25_results = self._bm25_top_k(query_text, k=k_each)
        return rrf_fuse(faiss_results, bm25_results, k_const=RRF_K)[:k]
