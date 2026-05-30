"""Q.93.A — create `marts` schema (Cube Fase 0 foundation).

Schema dedicado a views curadas para a camada semântica (Cube.dev) e outros
consumidores agnósticos (relatórios, dashboards). Esta migração só cria o
schema — as views vivem em `scripts/setup_marts_*.py` porque dependem das
tabelas espelhadas via `q75_setup_raw_mirror.py` (factory_raw.*), que são
criadas fora do Alembic.

Primeira view a aterrar aqui: `marts.v_consumo_material_dia` (Fase 0 do plano
CUBE).

Q.R1.1 — restaurado de e7772d9 no ramo da campanha do painel. O
`down_revision` original (062_q69_b_il_updated_at) não existe neste ramo;
re-apontado para o head atual (`q118r_merge_heads`) para manter um único head.

Revision ID: 063_q93_a_marts_schema
Revises: q118r_merge_heads
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op


revision = "063_q93_a_marts_schema"
down_revision = "q118r_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS marts")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS marts CASCADE")
