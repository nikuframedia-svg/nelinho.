"""Q.159 — Criar/substituir view factory_raw.v_active_operators.

Define a regra EXATA de "operador ativo" da fábrica, verificada na BD real
(2026-06-03): um colaborador com `E_ACTIVO = true` **E** que registou trabalho
(`offp_eq`) numa operação iniciada nos **últimos 2 meses (60 dias)**.

Porquê 60 dias: o Luis pediu "últimos 2 meses". Medido como estável — a
contagem mal varia com a janela (60d=107 · 75d=108 · 90d=109), por isso 60 dias
não é frágil. Fonte de verdade = `factory_raw.entidade.E_ACTIVO` (não
`core.employees`, que tem ~2 de drift do mirror).

Esta é a fonte única consumida por:
  - `/v1/core/employees?active_only=true` (dropdowns de atribuição)
  - `/v1/workforce/operators/summary` (contagem + quebra por área no display)
  - `src/plan/cpo/state.py:_load_skills_db` (pool da CPO, com fallback não-vazio)

Contagem-alvo (2026-06-03): ~107 operadores ativos.

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .venv\\Scripts\\python.exe scripts/q159_setup_active_operators_view.py

Não requer SQL Server — opera só no Postgres local sobre factory_raw (entidade /
offp_eq / of_fp já espelhados pelo q75).
"""

from __future__ import annotations

import asyncio
import sys

import asyncpg

sys.path.insert(0, "C:/Users/User/nelinho")
from src.shared.config import settings  # noqa: E402

# ── DDL da view ──────────────────────────────────────────────────────────────
#
# CREATE OR REPLACE VIEW → idempotente, sem DROP, sem quebrar dependências.
#   - INNER JOIN entidade (E_ACTIVO=true) ⋈ offp_eq (quem trabalhou) ⋈ of_fp.
#   - As datas em of_fp são TEXT no mirror → NULLIF('')::timestamp (vazio→NULL).
#   - Janela de 60 dias sobre OFFP_DATAINICIO (operação iniciada).
#   - GROUP BY → 1 linha por operador, com a data do último trabalho.
#
_VIEW_DDL = """\
CREATE OR REPLACE VIEW factory_raw.v_active_operators AS
SELECT e."E_ID"                                            AS e_id,
       e."E_NOME"                                          AS e_nome,
       max(NULLIF(o."OFFP_DATAINICIO", '')::timestamp)     AS last_worked
FROM factory_raw.entidade e
JOIN factory_raw.offp_eq eq ON eq."OFFPEQ_E_ID" = e."E_ID"
JOIN factory_raw.of_fp   o  ON o."OFFP_ID"      = eq."OFFPEQ_OFFP_ID"
WHERE e."E_ACTIVO" = true
  AND NULLIF(o."OFFP_DATAINICIO", '')::timestamp >= now() - interval '60 days'
GROUP BY e."E_ID", e."E_NOME"
"""


async def setup() -> dict:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(_VIEW_DDL)
        count = await conn.fetchval(
            "SELECT count(*) FROM factory_raw.v_active_operators"
        )
        # Quebra por área (só fases de produção, últimos 60d) — verificação.
        areas = await conn.fetch(
            """
            SELECT f."FP_NOME"                     AS area,
                   count(DISTINCT eq."OFFPEQ_E_ID") AS ops
            FROM factory_raw.v_active_operators ao
            JOIN factory_raw.offp_eq eq ON eq."OFFPEQ_E_ID" = ao.e_id
            JOIN factory_raw.of_fp   o  ON o."OFFP_ID"      = eq."OFFPEQ_OFFP_ID"
            JOIN factory_raw.fases_producao f ON f."FP_ID" = o."OFFP_FP_ID"
            WHERE f."FP_PRODUCAO" = true
              AND NULLIF(o."OFFP_DATAINICIO", '')::timestamp >= now() - interval '60 days'
            GROUP BY f."FP_NOME"
            ORDER BY ops DESC
            """
        )
        return {
            "status": "ok",
            "view": "factory_raw.v_active_operators",
            "count": int(count),
            "by_area": [{"area": r["area"], "ops": int(r["ops"])} for r in areas],
        }
    finally:
        await conn.close()


def main() -> int:
    r = asyncio.run(setup())
    print(f"[q159] view={r['view']} operadores_ativos={r['count']}")
    if r["count"] == 0:
        print(
            "ERRO: 0 operadores ativos — factory_raw vazio/stale? "
            "Correr o sync (q75) antes.",
            file=sys.stderr,
        )
        return 1
    print("  por área (últimos 60d, só FP_PRODUCAO):")
    for a in r["by_area"]:
        print(f"    {a['ops']:>3}  {a['area']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
