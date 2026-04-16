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
