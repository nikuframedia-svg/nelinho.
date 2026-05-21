"""
ProdPlan ONE - COPILOT RAG Engine
==================================

RAG retrieval + embeddings para base de conhecimento.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, or_, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.models import CopilotRAGChunk, PGVECTOR_AVAILABLE
from src.copilot.ollama_client import get_ollama_client
from src.shared.config import settings

logger = logging.getLogger(__name__)


# Q.67.4.E — schemas servidos pelo nelinho (17 schemas de domínio).
# Excluímos sandbox/public/pg_catalog/information_schema. Ordem fixa para
# determinismo no chunking.
SCHEMA_DOCS_SOURCE_TYPE = "schema_docs"

NELINHO_SCHEMAS: tuple[str, ...] = (
    "plan",
    "core",
    "supply",
    "hr",
    "quality",
    "profit",
    "governance",
    "dqa",
    "twin",
    "factory_curated",
    "factory_meta",
    "factory_raw",
    "reports",
    "shared",
    "improve",
    "sandbox",
)


# Termos PT-PT do glossário do copilot — aplicáveis quando o nome de
# tabela/coluna bate em substrings conhecidas. Mirrored em
# agent_docs/copilot_glossary.md (single source of truth para o LLM).
GLOSSARY_TERM_HINTS: dict[str, str] = {
    "fase": "fase (production phase)",
    "molde": "molde (mold)",
    "of_": "OF (ordem de fabrico)",
    "_of": "OF (ordem de fabrico)",
    "production_order": "OF (ordem de fabrico)",
    "rework": "retrabalho",
    "retrabalho": "retrabalho",
    "cura": "cura (chemical curing)",
    "curing": "cura (chemical curing)",
    "operario": "operário",
    "operator": "operador",
    "operador": "operador",
    "routing": "rota (routing)",
    "rota": "rota (routing)",
    "coeficiente": "CoeficienteX (€ - dinheiro, src/profit/)",
    "margin": "margem",
    "margem": "margem",
    "truck": "camião (moda 26 barcos/viagem)",
    "camiao": "camião",
    "shipment": "expedição",
    "expedicao": "expedição",
    "trust": "trust_index (0-1)",
    "kill_switch": "kill switch (admin-SQL-only)",
    "tenant": "tenant_id (multi-tenant)",
}


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


# ─── Q.67.4.E — Schema docs (PT-PT) RAG indexing ─────────────────────
#
# Indexa um chunk por tabela das 17 schemas do nelinho. Cada chunk segue
# o template:
#
#     <schema>.<table> — <COMMENT_TABELA>. Colunas: <c1: tipo (comment)>,
#     <c2: tipo (comment)>, .... Termos: <termos do glossário aplicáveis>.
#
# Idempotente: `force=True` apaga primeiro os chunks com
# source_type='schema_docs' do tenant, depois reingere. Reusa o
# `ingest_document` existente (1 doc por tabela → 1 chunk).
#
# Lê column comments do pg_catalog (`col_description`) — funciona em
# Postgres real; em sessões fake (testes) os queries são interceptados.


def _matching_glossary_terms(haystack: str) -> List[str]:
    """Termos do glossário que aparecem em `haystack` (table+col names).

    Q.67.4.E — anota cada chunk com hints PT-PT para o retrieval do
    LLM. Match por substring case-insensitive, dedup ordenado.
    """
    text_lower = haystack.lower()
    seen: List[str] = []
    for key, label in GLOSSARY_TERM_HINTS.items():
        if key in text_lower and label not in seen:
            seen.append(label)
    return seen


def _build_schema_chunk_text(
    schema: str,
    table: str,
    table_comment: Optional[str],
    columns: List[Tuple[str, str, Optional[str]]],
) -> str:
    """Constrói o texto PT-PT de 1 chunk por tabela.

    `columns` é uma lista de (col_name, data_type, col_comment).
    """
    table_desc = (table_comment or "sem descrição registada").strip()
    col_parts: List[str] = []
    for name, dtype, comment in columns:
        if comment:
            col_parts.append(f"{name}: {dtype} ({comment.strip()})")
        else:
            col_parts.append(f"{name}: {dtype}")
    cols_blob = ", ".join(col_parts) if col_parts else "(sem colunas)"

    haystack = f"{schema} {table} {' '.join(c[0] for c in columns)}"
    terms = _matching_glossary_terms(haystack)
    terms_blob = ", ".join(terms) if terms else "n/a"

    return (
        f"{schema}.{table} — {table_desc}. "
        f"Colunas: {cols_blob}. "
        f"Termos: {terms_blob}."
    )


async def _list_schema_tables(
    session: AsyncSession,
    schemas: tuple[str, ...],
) -> List[Tuple[str, str, Optional[str]]]:
    """Lista (schema, table, table_comment) das tabelas das schemas dadas.

    Usa `information_schema.tables` + `pg_catalog.obj_description`.
    """
    stmt = text(
        """
        SELECT
            t.table_schema,
            t.table_name,
            obj_description(
                format('%I.%I', t.table_schema, t.table_name)::regclass,
                'pg_class'
            ) AS table_comment
        FROM information_schema.tables t
        WHERE t.table_type = 'BASE TABLE'
          AND t.table_schema = ANY(:schemas)
        ORDER BY t.table_schema, t.table_name
        """
    )
    result = await session.execute(stmt, {"schemas": list(schemas)})
    return [(row[0], row[1], row[2]) for row in result.all()]


async def _list_table_columns(
    session: AsyncSession,
    schema: str,
    table: str,
) -> List[Tuple[str, str, Optional[str]]]:
    """Lista (col_name, data_type, col_comment) de uma tabela."""
    stmt = text(
        """
        SELECT
            c.column_name,
            c.data_type,
            col_description(
                format('%I.%I', c.table_schema, c.table_name)::regclass,
                c.ordinal_position
            ) AS col_comment
        FROM information_schema.columns c
        WHERE c.table_schema = :schema
          AND c.table_name = :table
        ORDER BY c.ordinal_position
        """
    )
    result = await session.execute(stmt, {"schema": schema, "table": table})
    return [(row[0], row[1], row[2]) for row in result.all()]


async def ingest_schema_docs(
    session: AsyncSession,
    tenant_id: UUID,
    force: bool = False,
    schemas: tuple[str, ...] = NELINHO_SCHEMAS,
) -> int:
    """Indexa 1 chunk PT-PT por tabela das 17 schemas no RAG do copilot.

    Para cada tabela das schemas em `schemas`, gera 1 chunk no template
    `<schema>.<table> — <comment>. Colunas: ... . Termos: ...` e
    persiste via `ingest_document` (source_type='schema_docs').

    Idempotente: se `force=True`, apaga primeiro todos os chunks com
    source_type='schema_docs' do tenant antes de reingerir. Sem
    `force=True` acumula chunks novos (útil para incrementais; mas a
    forma canónica de refresh é force=True via cron nightly).

    Args:
        session: Sessão async DB.
        tenant_id: Tenant alvo.
        force: Se True, faz delete antes de reingerir.
        schemas: Schemas a indexar (default: todas as 17 nelinho).

    Returns:
        Número total de chunks indexados.
    """
    if force:
        del_stmt = delete(CopilotRAGChunk).where(
            and_(
                CopilotRAGChunk.tenant_id == tenant_id,
                CopilotRAGChunk.source_type == SCHEMA_DOCS_SOURCE_TYPE,
            )
        )
        await session.execute(del_stmt)
        logger.info(
            "ingest_schema_docs: apagados chunks existentes (tenant=%s)",
            tenant_id,
        )

    tables = await _list_schema_tables(session, schemas)
    if not tables:
        logger.warning(
            "ingest_schema_docs: nenhuma tabela encontrada nas schemas %s",
            schemas,
        )
        return 0

    total_chunks = 0
    for schema, table, table_comment in tables:
        columns = await _list_table_columns(session, schema, table)
        chunk_body = _build_schema_chunk_text(
            schema=schema,
            table=table,
            table_comment=table_comment,
            columns=columns,
        )
        # 1 chunk por tabela — bypassamos `chunk_text` (que assume docs
        # longos) porque o template PT-PT é curto e auto-contido. Reusa
        # o pipeline de embedding + add do `ingest_document` em forma
        # inline (mesmas invariantes: pgvector fallback, log de erro,
        # audit_coverage exemption no add).
        try:
            embedding_value = await get_embeddings(chunk_body)
            if not PGVECTOR_AVAILABLE:
                embedding_value = str(embedding_value)
        except Exception as exc:
            logger.warning(
                "ingest_schema_docs: embedding falhou para %s.%s: %s",
                schema, table, exc,
            )
            embedding_value = None

        chunk = CopilotRAGChunk(
            tenant_id=tenant_id,
            source_type=SCHEMA_DOCS_SOURCE_TYPE,
            source_id=f"{schema}.{table}",
            chunk_index=0,
            chunk_text=chunk_body,
            embedding=embedding_value,
            chunk_metadata={
                "schema": schema,
                "table": table,
                "column_count": len(columns),
            },
        )
        # Q.66.B.3 audit_coverage exemption: chunk RAG é cache derivada
        # de schema docs, não state autoritativo de governance.
        session.add(chunk)  # noqa: audit_coverage  # RAG cache chunk
        total_chunks += 1

    await session.flush()

    logger.info(
        "ingest_schema_docs: %d chunks indexados (%d tabelas, force=%s)",
        total_chunks,
        len(tables),
        force,
    )
    return total_chunks


