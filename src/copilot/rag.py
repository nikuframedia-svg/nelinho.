"""
ProdPlan ONE - COPILOT RAG Engine
==================================

RAG retrieval + embeddings para base de conhecimento.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.models import CopilotRAGChunk, PGVECTOR_AVAILABLE
from src.copilot.ollama_client import get_ollama_client
from src.shared.config import settings

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> List[str]:
    """
    Chunking de texto.
    
    Args:
        text: Texto completo
        chunk_size: Tamanho do chunk (tokens aproximados)
        overlap: Overlap entre chunks (tokens)
    
    Returns:
        Lista de chunks
    """
    # Aproximação: 4 chars = 1 token
    char_size = chunk_size * 4
    char_overlap = overlap * 4

    # Sprint Q.12 Onda 4.3 — never split mid-word. The previous
    # implementation looked for a sentence break in the chunk window
    # but, when none existed, copied ``char_size`` characters
    # verbatim — which routinely cut entities like part numbers and
    # operator names in half (one half landed in chunk N, the other
    # in chunk N+1, and neither matched a query for the full token).
    # We now prefer a sentence break, then fall back to a word
    # boundary, and only as a last resort do we hard-cut.
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + char_size, len(text))
        chunk = text[start:end]

        if end < len(text):
            # Prefer a sentence boundary (period / newline / exclamation
            # / question mark) in the back half of the window.
            soft_break = -1
            for marker in (". ", ".\n", "\n\n", "?\n", "!\n", "\n"):
                idx = chunk.rfind(marker)
                if idx > char_size * 0.5:
                    soft_break = idx + len(marker)
                    break
            if soft_break == -1:
                # No sentence break — fall back to the last whitespace
                # in the back half of the window so we never cut a word.
                idx = chunk.rfind(" ", int(char_size * 0.5))
                if idx > 0:
                    soft_break = idx + 1
            if soft_break > 0:
                chunk = chunk[:soft_break]
                end = start + soft_break

        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        # Advance with overlap, but never go backwards (would happen
        # if a tiny chunk + large overlap made ``end - char_overlap``
        # less than ``start``).
        start = max(start + 1, end - char_overlap)

    return chunks


async def get_embeddings(
    text: str,
    model: Optional[str] = None,
) -> List[float]:
    """
    Obter embeddings via Ollama.
    
    Args:
        text: Texto para embed
        model: Modelo de embeddings (default: settings.copilot_embeddings_model)
    
    Returns:
        Lista de floats (embedding vector)
    """
    model = model or settings.copilot_embeddings_model
    client = get_ollama_client()
    
    try:
        embedding = await client.embeddings(text, model)
        return embedding
    except Exception as e:
        logger.error(f"Erro ao obter embeddings: {e}")
        raise


async def retrieve_rag_chunks(
    session: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int = 8,
) -> List[Dict[str, Any]]:
    """
    Retrieval de chunks RAG.
    
    Se PostgreSQL: vector search com pgvector
    Se SQLite: busca lexical (LIKE + scoring simples)
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        query: Query do utilizador
        top_k: Número de chunks a retornar
    
    Returns:
        Lista de chunks com score
    """
    # Obter embedding da query
    try:
        query_embedding = await get_embeddings(query)
    except Exception:
        logger.warning("Não foi possível obter embeddings - usando busca lexical")
        return await _lexical_search(session, tenant_id, query, top_k)
    
    # Use pgvector if available, otherwise lexical fallback
    if PGVECTOR_AVAILABLE:
        results = await _vector_search(session, tenant_id, query_embedding, top_k)
        if results:
            return results
        # Empty results from vector search — fall through to lexical
        logger.info("Vector search returned no results — trying lexical fallback")

    return await _lexical_search(session, tenant_id, query, top_k)


async def _vector_search(
    session: AsyncSession,
    tenant_id: UUID,
    query_embedding: List[float],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Vector search com pgvector (PostgreSQL).

    Uses cosine distance operator (<=>): 0 = identical, 2 = opposite.
    Score is converted to similarity: 1 - distance.
    """
    if not PGVECTOR_AVAILABLE:
        logger.warning("pgvector not installed — falling back to lexical search")
        return []

    # Cosine distance via pgvector: embedding <=> query_vector
    distance = CopilotRAGChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(CopilotRAGChunk, distance.label("distance"))
        .where(
            and_(
                CopilotRAGChunk.tenant_id == tenant_id,
                CopilotRAGChunk.embedding.isnot(None),
            )
        )
        .order_by(distance)
        .limit(top_k)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "id": str(chunk.id),
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "score": round(1.0 - dist, 4),
            "metadata": chunk.chunk_metadata or {},
        }
        for chunk, dist in rows
    ]


async def _lexical_search(
    session: AsyncSession,
    tenant_id: UUID,
    query: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Busca lexical simples (SQLite ou fallback).
    
    Usa LIKE + scoring básico.
    """
    # Extrair palavras-chave da query
    keywords = re.findall(r"\w+", query.lower())
    
    if not keywords:
        return []
    
    # Query com LIKE
    conditions = []
    for keyword in keywords[:5]:  # Limitar a 5 keywords
        conditions.append(CopilotRAGChunk.chunk_text.ilike(f"%{keyword}%"))
    
    query = select(CopilotRAGChunk).where(
        and_(
            CopilotRAGChunk.tenant_id == tenant_id,
            or_(*conditions),
        )
    ).limit(top_k * 2)  # Buscar mais para depois filtrar
    
    result = await session.execute(query)
    chunks = result.scalars().all()
    
    # Scoring simples: contar matches de keywords
    scored_chunks = []
    for chunk in chunks:
        text_lower = chunk.chunk_text.lower()
        matches = sum(1 for kw in keywords if kw in text_lower)
        score = matches / len(keywords) if keywords else 0.0
        
        scored_chunks.append({
            "id": str(chunk.id),
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "score": score,
            "metadata": chunk.chunk_metadata or {},
        })
    
    # Ordenar por score e retornar top_k
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:top_k]


async def ingest_document(
    session: AsyncSession,
    tenant_id: UUID,
    source_type: str,
    source_id: str,
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Ingestão de documento para RAG.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        source_type: Tipo de fonte (ex: "sop", "doc", "policy")
        source_id: ID da fonte
        text: Texto completo
        metadata: Metadados (url, title, etc.)
    
    Returns:
        Número de chunks criados
    """
    # Chunking
    chunks = chunk_text(text, chunk_size=600, overlap=100)
    
    created_count = 0

    for idx, chunk_text_content in enumerate(chunks):
        # Obter embedding (list[float] when pgvector is active, string fallback otherwise)
        try:
            embedding_value = await get_embeddings(chunk_text_content)
            if not PGVECTOR_AVAILABLE:
                embedding_value = str(embedding_value)
        except Exception as e:
            logger.warning(f"Erro ao obter embedding para chunk {idx}: {e}")
            embedding_value = None

        chunk = CopilotRAGChunk(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            chunk_index=idx,
            chunk_text=chunk_text_content,
            embedding=embedding_value,
            chunk_metadata=metadata,
        )
        
        # Q.66.B.3: chunk RAG (pgvector cache para retrieval do copiloto),
        # nao state autoritativo de governance — cache derivada de documentos.
        session.add(chunk)  # noqa: audit_coverage  # RAG cache chunk, not gov state
        created_count += 1
    
    await session.flush()
    
    logger.info(f"Ingestão concluída: {created_count} chunks criados para {source_type}:{source_id}")
    
    return created_count


