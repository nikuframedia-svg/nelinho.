"""Enable pgvector extension and convert RAG embeddings to Vector(768) + HNSW index

Revision ID: 008_pgvector
Revises: 6a8943269014
Create Date: 2026-04-16

Enables vector similarity search for RAG:
- CREATE EXTENSION vector
- Alter copilot_rag_chunk.embedding from TEXT to vector(768)
- Add HNSW index for cosine distance queries

This migration is idempotent: safe to re-run.
If pgvector is not available on the server, the ALTER TYPE will fail and
the migration must be applied after installing the extension.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_pgvector'
down_revision = '6a8943269014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Q.18.BOOTSTRAP — pgvector é optional em dev. Em produção a extension
    # vem instalada (apt/yum/docker). Em dev local (scoop postgres) pode
    # não estar disponível — skip graceful para o resto do upgrade head
    # poder continuar. RAG search degrada para fallback text-search.
    #
    # Importante: NÃO usar try/except à volta de CREATE EXTENSION — assim que
    # falha, a transaction Alembic fica em failed state e o resto do upgrade
    # explode. Tem que ser pre-flight check via pg_available_extensions
    # (query SELECT que NÃO aborta transaction se vazia).
    bind = op.get_bind()
    available = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).first()
    if not available:
        import logging
        logging.getLogger("alembic.008_pgvector").warning(
            "pgvector extension not available on this PostgreSQL server. "
            "Skipping vector column conversion + HNSW index. "
            "RAG search will fall back to text matching. "
            "Install pgvector and re-run this migration to enable vector search."
        )
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Convert existing embedding column (TEXT holding JSON arrays) to vector(768).
    # Existing rows with non-parseable data will be set to NULL; re-ingest them afterwards.
    op.execute(
        """
        ALTER TABLE copilot_rag_chunk
        ALTER COLUMN embedding TYPE vector(768)
        USING CASE
            WHEN embedding IS NULL THEN NULL
            WHEN embedding ~ '^\\[.*\\]$' THEN embedding::vector(768)
            ELSE NULL
        END
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_copilot_rag_chunk_embedding_hnsw
        ON copilot_rag_chunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_copilot_rag_chunk_embedding_hnsw")
    op.execute("ALTER TABLE copilot_rag_chunk ALTER COLUMN embedding TYPE text USING embedding::text")
    # Do NOT drop the vector extension — other tables may use it.
