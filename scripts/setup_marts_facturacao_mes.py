"""Q.102.B — view `marts.v_facturacao_mes`.

Medida registada: `comercial_facturacao.total` (DINHEIRO €).

**Fonte**: `factory_raw.entidade_phc_fact` (Q.102.A espelhamento). 100 625
rows de PHC ERP NELO 2009-2026. Anchor histórico Q.82 confirmado:
**€125 372 058 acumulado, Canoe Sprint TP_ID=6 = €73 018 963 (58.24 %)**.

**Decisões de negócio** (em `business_decision` do MeasureSpec):
  - **HIPÓTESE FORTE — base sem IVA**: a tabela tem apenas uma coluna
    `EPHCF_FACTURADO`, sem coluna IVA separada. PHC ERP armazena
    tipicamente a base para reporting fiscal. Confirmação CFO pendente.
  - **Facturação líquida**: 3 797 rows com `EPHCF_FACTURADO < 0` são
    notas de crédito / devoluções. SUM já é líquido. Não há coluna
    tipo de documento — o sinal negativo é o marcador.
  - **Zeros**: 4 237 rows com €0 (cortesia / cancelados). Mantidos em
    `n_facturas`; SUM=0.
  - **EPOCA vs ANO**: `EPHCF_EPOCA` é ano desportivo (Out-Set ≠ ano
    calendário). Esta view usa ANO calendário (alinhado com perguntas
    do gestor).
  - **JOIN cliente correcto** (Q.102.A descoberta — Q.82 errou): o JOIN
    canónico é `EPHCF_EPHC_ID = ENTIDADE_PHC.EPHC_ID` (PK local), NÃO
    `= ENTIDADE_PHC.EPHC_PHC_ID` (referência externa PHC). Validado
    contra Q.82 top 5 clientes 2024 (Gusser KanuSport €488 898, etc.).
  - **NULL handling**: 14 % rows com `EPHCF_EPHC_ID=NULL` (vendas
    balcão/loja sem cliente registado) → 'Sem cliente registado'.
    60 % rows com `EPHCF_TP_ID=NULL` → 'Não categorizado'.

**Granularidade view**: 1 row por `(data_mes, cliente, disciplina)`.
Cube agrega por mês via timeDimension. `SUM(facturado_eur)` é aditivo
entre clientes/disciplinas/meses (DINHEIRO mesma base).

Idempotente. Falha cedo se `factory_raw.entidade_phc_fact` não existir.

Uso::

    PYTHONPATH=. .venv/Scripts/python.exe scripts/setup_marts_facturacao_mes.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_facturacao_mes AS
-- Q.102.B — facturação mensal agregada por cliente × disciplina.
-- Anchor: SUM(facturado_eur) = €125 372 058 (Q.82 ✓).
-- JOIN cliente canónico: EPHCF_EPHC_ID = ENTIDADE_PHC.EPHC_ID (PK local).
-- Q.108 Onda A: adiciona dim `pais` via entidade.E_PAIS (string livre);
-- NULL/'' → 'sem_pais'. Anchor 2024 Poland top-1 = €995 201.
SELECT
    MAKE_DATE(f."EPHCF_ANO", f."EPHCF_MES", 1)              AS data,
    f."EPHCF_ANO"                                           AS ano,
    f."EPHCF_MES"                                           AS mes,
    COALESCE(e."E_NOME", 'Sem cliente registado')           AS cliente,
    f."EPHCF_EPHC_ID"                                       AS cliente_id,
    COALESCE(pt."TP_NOME", 'Não categorizado')              AS disciplina,
    f."EPHCF_TP_ID"                                         AS disciplina_id,
    COALESCE(NULLIF(TRIM(e."E_PAIS"), ''), 'sem_pais')      AS pais,
    f."EPHCF_EPOCA"                                         AS epoca,
    SUM(f."EPHCF_FACTURADO"::numeric)                       AS facturado_eur,
    COUNT(*)                                                AS n_facturas,
    SUM(CASE WHEN f."EPHCF_FACTURADO" < 0 THEN 1 ELSE 0 END) AS n_creditos
FROM factory_raw.entidade_phc_fact f
LEFT JOIN factory_raw.entidade_phc ephc
       ON ephc."EPHC_ID" = f."EPHCF_EPHC_ID"
LEFT JOIN factory_raw.entidade e
       ON e."E_ID" = ephc."EPHC_E_ID"
LEFT JOIN factory_raw.produto_tipo pt
       ON pt."TP_ID" = f."EPHCF_TP_ID"
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que as 4 tabelas Q.102.A existem."""
    for table in ("entidade_phc_fact", "entidade_phc", "produto_tipo", "entidade"):
        exists = await pg_conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'factory_raw' AND table_name = $1
            )
            """,
            table,
        )
        if not exists:
            raise SystemExit(
                f"factory_raw.{table} nao existe -- corre primeiro "
                "`python scripts/q102_setup_comercial_mirror.py` para espelhar "
                "as tabelas PHC, depois volta a correr este script."
            )

    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_facturacao_mes")
        await conn.execute(VIEW_SQL)

        # Sanity 1: rows total + range
        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_facturacao_mes")
        rng = await conn.fetchrow(
            "SELECT MIN(data) AS min_d, MAX(data) AS max_d FROM marts.v_facturacao_mes"
        )
        print(f"  OK view criada -- {n:,} rows. Range {rng['min_d']} -> {rng['max_d']}.")

        # Anchor 1: SUM total tem de bater EPHC_FACT base.
        EXPECTED_TOTAL = 125_372_058
        total_view = await conn.fetchval(
            "SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint FROM marts.v_facturacao_mes"
        )
        diff_pct = 100.0 * abs(total_view - EXPECTED_TOTAL) / EXPECTED_TOTAL
        print(
            f"  ANCHOR total: {total_view:,} EUR  "
            f"(esperado {EXPECTED_TOTAL:,} EUR, delta {diff_pct:.4f} %)"
        )
        assert diff_pct < 0.01, f"Anchor falhou: delta {diff_pct} %"

        # Anchor 2: Canoe Sprint
        EXPECTED_CANOE = 73_018_963
        canoe = await conn.fetchval(
            """
            SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint
            FROM marts.v_facturacao_mes WHERE disciplina_id = 6
            """
        )
        diff_canoe = 100.0 * abs(canoe - EXPECTED_CANOE) / EXPECTED_CANOE
        print(
            f"  ANCHOR Canoe Sprint: {canoe:,} EUR  "
            f"(esperado {EXPECTED_CANOE:,} EUR, delta {diff_canoe:.4f} %)"
        )
        assert diff_canoe < 0.01, f"Canoe anchor falhou: delta {diff_canoe} %"

        # Anchor 3: top cliente 2024 = Gusser KanuSport €488 898
        gusser = await conn.fetchval(
            """
            SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint
            FROM marts.v_facturacao_mes
            WHERE ano = 2024 AND cliente_id = 737
            """
        )
        print(f"  ANCHOR Gusser KanuSport 2024: {gusser:,} EUR (esperado 488 898 EUR)")
        assert abs(gusser - 488_898) < 5, f"Gusser anchor falhou: {gusser}"

        # Anchor 4: facturação anual 2024
        EXPECTED_2024 = 9_538_482
        f2024 = await conn.fetchval(
            "SELECT ROUND(SUM(facturado_eur)::numeric, 0)::bigint "
            "FROM marts.v_facturacao_mes WHERE ano = 2024"
        )
        diff_2024 = 100.0 * abs(f2024 - EXPECTED_2024) / EXPECTED_2024
        print(
            f"  ANCHOR 2024: {f2024:,} EUR  "
            f"(esperado {EXPECTED_2024:,} EUR, delta {diff_2024:.4f} %)"
        )
        assert diff_2024 < 0.01, f"2024 anchor falhou: delta {diff_2024} %"

        # Distribuição: cobertura cliente / disciplina
        cov = await conn.fetchrow(
            """
            SELECT
              ROUND(100.0 * SUM(CASE WHEN cliente = 'Sem cliente registado'
                                     THEN n_facturas ELSE 0 END)
                          / SUM(n_facturas), 1) AS pct_sem_cliente,
              ROUND(100.0 * SUM(CASE WHEN disciplina = 'Não categorizado'
                                     THEN n_facturas ELSE 0 END)
                          / SUM(n_facturas), 1) AS pct_sem_disc,
              SUM(n_creditos) AS total_creditos
            FROM marts.v_facturacao_mes
            """
        )
        print(
            f"  Cobertura: {cov['pct_sem_cliente']} % rows sem cliente, "
            f"{cov['pct_sem_disc']} % rows sem disciplina, "
            f"{cov['total_creditos']} notas de crédito (negativos)"
        )

        # Top 5 disciplinas
        print("\n  Top 5 disciplinas (acumulado):")
        rows = await conn.fetch(
            """
            SELECT disciplina, COUNT(*)::int AS n_rows,
                   ROUND(SUM(facturado_eur)::numeric, 0)::bigint AS eur
            FROM marts.v_facturacao_mes
            GROUP BY disciplina ORDER BY 3 DESC LIMIT 5
            """
        )
        for r in rows:
            disc = (r['disciplina'] or '?')[:35]
            print(f"    {disc:<35} n={r['n_rows']:>5}  {r['eur']:>15,} EUR")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
