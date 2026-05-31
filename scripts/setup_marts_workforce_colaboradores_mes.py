"""Q.106.1 — view `marts.v_workforce_colaboradores_mes`.

Colaboradores NELO activos no período. Granularidade 1 row por
(mês, colaborador, departamento). View NÃO filtra k-anonymity —
decisão Luís: cliente NELO quer transparência total, dim `colaborador`
normal igual a `cliente` em comercial.

Definição canónica (Q.82):
- colaborador NELO = entidade.E_ACTIVO=1 AND E_ENT_ID em sub-tipos
  de ENT_ID=19 Empregado.
- "Activo num período" = teve ≥1 evento em ENT_MOV no período.
- Anchor 158 colaboradores activos totais (view FuncionariosActivos).

Departamento = cargo canónico ENTIDADE_TIPO.ENT_NOME (Laminador,
Pintor, Acabador, …).
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_workforce_colaboradores_mes AS
SELECT
    DATE_TRUNC('month', CAST(em."MOVENT_DATA_I" AS timestamp))::date AS data,
    em."MOVENT_E_ID"                                                  AS colaborador_id,
    e."E_NOME"                                                        AS colaborador,
    COALESCE(et."ENT_NOME", 'Sem cargo')                              AS departamento,
    COUNT(*)                                                          AS n_eventos
FROM factory_raw.ent_mov em
JOIN factory_raw.entidade e ON e."E_ID" = em."MOVENT_E_ID"
LEFT JOIN factory_raw.entidade_tipo et ON et."ENT_ID" = e."E_ENT_ID"
WHERE e."E_ACTIVO" = TRUE
  AND e."E_ENT_ID" IN (
      SELECT "ENT_ID" FROM factory_raw.entidade_tipo WHERE "ENT_ENT_ID" = 19
  )
  AND em."MOVENT_DATA_I" IS NOT NULL
  AND NULLIF(em."MOVENT_DATA_I", '') IS NOT NULL
GROUP BY 1, 2, 3, 4
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        # Pre-req: tabelas Q.106-A
        for table in ("ent_mov", "entidade_tipo", "entidade"):
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='factory_raw' AND table_name=$1)",
                table,
            )
            if not exists:
                raise SystemExit(
                    f"factory_raw.{table} nao existe -- corre primeiro "
                    "`python scripts/q106_a_setup_workforce_mirror.py`."
                )

        await conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        await conn.execute("DROP VIEW IF EXISTS marts.v_workforce_colaboradores_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval(
            "SELECT COUNT(*) FROM marts.v_workforce_colaboradores_mes"
        )
        n_distintos = await conn.fetchval(
            "SELECT COUNT(DISTINCT colaborador_id) "
            "FROM marts.v_workforce_colaboradores_mes"
        )
        n_2024 = await conn.fetchval(
            "SELECT COUNT(DISTINCT colaborador_id) "
            "FROM marts.v_workforce_colaboradores_mes "
            "WHERE EXTRACT(YEAR FROM data) = 2024"
        )
        print(f"  OK -- {n:,} rows (mes x colaborador x departamento).")
        print(f"  Colaboradores distintos historico (activos): {n_distintos}")
        print(f"  Colaboradores activos 2024: {n_2024}")

        # Top 5 departamentos
        print("\n  Top 5 departamentos por n colaboradores distintos:")
        rows = await conn.fetch(
            "SELECT departamento, COUNT(DISTINCT colaborador_id) AS n "
            "FROM marts.v_workforce_colaboradores_mes "
            "GROUP BY departamento ORDER BY 2 DESC LIMIT 5"
        )
        for r in rows:
            print(f"    {r['departamento'][:30]:<30}  {r['n']:>4}")

        # Anchor sanity: total distintos historico deve estar perto de 158
        # (alguns dos 158 actuais podem nao ter eventos em ENT_MOV).
        assert n_distintos > 100, f"Anchor falhou: {n_distintos} colaboradores"
        print("\n  Anchor OK.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
