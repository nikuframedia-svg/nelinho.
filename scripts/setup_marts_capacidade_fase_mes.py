"""Q.167.C — view `marts.v_capacidade_fase_mes`.

Capacidade de produção por fase, com o impacto das ausências — o buraco de
"dados honestos" que a auditoria assinalou (não tínhamos visibilidade
nenhuma de capacidade vs absentismo).

Fórmula canónica (lida de `dbo.Report_ProducaoCapacidade_Sub_Capacidade`,
2026-06-08): por entidade ACTIVA (`E_ACTIVO`) cuja **fase principal**
`entidade.E_FP_ID` = a fase, capacidade teórica = `E_PRODUTIVIDADE`
(barcos/pessoa/dia); a entidade perde-a num dia em que está ausente
(ausência = `ent_mov` × `ent_mov_tipo` com `MET_MET_ID = 2` = grupo Faltas:
Injustificada / Justificada / Baixas / Férias; data = `MOVENT_DATA_I`).

Granularidade: 1 row por (mês, fase). Colunas:
  * `capacidade_dia_teorica` — barcos/dia da fase a 100% de presença.
  * `dias_ausencia`          — dias-pessoa perdidos a faltas nesse mês.
  * `capacidade_perdida`     — barcos-dia perdidos (Σ prod × dias-ausente).

Q.175.B — agora que `factory_raw.dias_trabalho` está espelhado (Q.174.I),
acrescenta `dias_uteis`, `capacidade_mes_teorica` e `capacidade_disponivel`
(a fórmula completa canónica = cap_dia × dias_úteis - perdida).

Granularidade: 1 row por (mês, fase). Colunas:
  * `capacidade_dia_teorica` — barcos/dia da fase a 100% de presença.
  * `dias_ausencia`          — dias-pessoa perdidos a faltas nesse mês.
  * `capacidade_perdida`     — barcos-dia perdidos (Σ prod × dias-ausente).
  * `dias_uteis`             — dias úteis do mês (de DIAS_TRABALHO canónico).
  * `capacidade_mes_teorica` — barcos totais disponíveis a 100% presença.
  * `capacidade_disponivel`  — capacidade efectiva = teorica - perdida.
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_capacidade_fase_mes AS
WITH phase_ops AS (
    -- operadores activos pela sua FASE PRINCIPAL (entidade.E_FP_ID)
    SELECT e."E_FP_ID"         AS fase_id,
           e."E_ID"            AS e_id,
           e."E_PRODUTIVIDADE" AS prod
    FROM factory_raw.entidade e
    WHERE e."E_ACTIVO" = true
      AND e."E_FP_ID" IS NOT NULL
      AND e."E_PRODUTIVIDADE" IS NOT NULL
      AND e."E_PRODUTIVIDADE" > 0
),
abs AS (
    -- dias de FALTA (MET_MET_ID=2) por (mês, operador)
    SELECT DATE_TRUNC('month', em."MOVENT_DATA_I"::timestamp)::date AS mes,
           em."MOVENT_E_ID"                                         AS e_id,
           COUNT(*)                                                 AS dias_ausente
    FROM factory_raw.ent_mov em
    JOIN factory_raw.ent_mov_tipo mt ON mt."MET_ID" = em."MOVENT_MET_ID"
    WHERE mt."MET_MET_ID" = 2
      AND NULLIF(em."MOVENT_DATA_I", '') IS NOT NULL
    GROUP BY 1, 2
),
meses AS (SELECT DISTINCT mes FROM abs),
-- Q.175.B — dias úteis por mês (canónico: DIAS_TRABALHO; DTRB_DATA = dias que a NELO trabalha)
dias_uteis_mes AS (
    SELECT DATE_TRUNC('month', "DTRB_DATA"::timestamp)::date AS mes,
           COUNT(*)                                           AS dias_uteis
    FROM factory_raw.dias_trabalho
    WHERE "DTRB_DATA" IS NOT NULL
    GROUP BY 1
)
SELECT
    m.mes                                                          AS data,
    po.fase_id                                                     AS fase_id,
    fp."FP_NOME"                                                   AS fase,
    COUNT(DISTINCT po.e_id)                                        AS operadores,
    ROUND(SUM(po.prod)::numeric, 2)                               AS capacidade_dia_teorica,
    COALESCE(SUM(a.dias_ausente), 0)                              AS dias_ausencia,
    ROUND(SUM(po.prod * COALESCE(a.dias_ausente, 0))::numeric, 2) AS capacidade_perdida,
    -- Q.175.B — fórmula canónica completa (Report_ProducaoCapacidade_Sub_Capacidade)
    COALESCE(du.dias_uteis, 0)                                     AS dias_uteis,
    ROUND((SUM(po.prod) * COALESCE(du.dias_uteis, 0))::numeric, 2) AS capacidade_mes_teorica,
    GREATEST(0,
        ROUND((SUM(po.prod) * COALESCE(du.dias_uteis, 0)
               - SUM(po.prod * COALESCE(a.dias_ausente, 0)))::numeric, 2)
    )                                                              AS capacidade_disponivel
FROM meses m
CROSS JOIN phase_ops po
JOIN factory_raw.fases_producao fp ON fp."FP_ID" = po.fase_id
LEFT JOIN abs a ON a.mes = m.mes AND a.e_id = po.e_id
LEFT JOIN dias_uteis_mes du ON du.mes = m.mes
GROUP BY m.mes, po.fase_id, fp."FP_NOME", du.dias_uteis
"""


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS marts")
        await conn.execute("DROP VIEW IF EXISTS marts.v_capacidade_fase_mes")
        await conn.execute(VIEW_SQL)

        n = await conn.fetchval("SELECT COUNT(*) FROM marts.v_capacidade_fase_mes")
        tot = await conn.fetchrow(
            "SELECT COUNT(DISTINCT fase_id) AS fases, COUNT(DISTINCT data) AS meses, "
            "SUM(capacidade_perdida)::float AS perda, "
            "MAX(dias_uteis) AS max_dias_uteis, "
            "SUM(capacidade_disponivel)::float AS disponivel "
            "FROM marts.v_capacidade_fase_mes"
        )
        print(f"  OK -- {n:,} rows (mes x fase). "
              f"{tot['fases']} fases, {tot['meses']} meses, "
              f"{tot['perda']:,.0f} barcos-dia perdidos. "
              f"Max dias_uteis/mes: {tot['max_dias_uteis']}. "
              f"Capacidade disponivel total: {tot['disponivel']:,.0f} barcos.")

        print("\n  Top 5 fases por capacidade disponivel (ultimo mes com dados):")
        rows = await conn.fetch(
            "SELECT fase, capacidade_dia_teorica::float AS cap_dia, "
            "dias_uteis, capacidade_mes_teorica::float AS cap_mes, "
            "capacidade_disponivel::float AS disponivel, operadores "
            "FROM marts.v_capacidade_fase_mes "
            "WHERE data = (SELECT MAX(data) FROM marts.v_capacidade_fase_mes) "
            "ORDER BY disponivel DESC LIMIT 5"
        )
        for r in rows:
            print(f"    {(r['fase'] or '?')[:28]:<28} "
                  f"{r['cap_dia']:>5.1f}/dia x {r['dias_uteis']:>2}d = "
                  f"{r['cap_mes']:>6.0f} teorico -> {r['disponivel']:>6.0f} disponivel "
                  f"({r['operadores']} ops)")

        # Sanity anchors (verificado live 2026-06-08: 62 486 faltas met_met_id=2).
        abs_n = await conn.fetchval(
            'SELECT COUNT(*) FROM factory_raw.ent_mov em '
            'JOIN factory_raw.ent_mov_tipo mt ON mt."MET_ID"=em."MOVENT_MET_ID" '
            'WHERE mt."MET_MET_ID"=2'
        )
        assert abs_n >= 50_000, f"Anchor falhou: {abs_n} faltas (esperado ~62k)"
        assert n > 0 and tot["fases"] >= 10, (
            f"Anchor falhou: {n} rows / {tot['fases']} fases (esperado >0 / >=10)"
        )
        print(f"\n  Anchor OK ({abs_n:,} faltas met_met_id=2; {tot['fases']} fases).")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
