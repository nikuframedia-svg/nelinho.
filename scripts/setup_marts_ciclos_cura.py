"""Q.100 Medida 1 — view `marts.v_ciclos_cura`.

Medida registada: `ambiental.cura_horas` (TEMPO em horas).

**Fonte**: `factory_raw.iot_sensor_data` (Q.98 espelhamento, 3.2M rows).
Sensores cura (Estufa 60 = 12, Estufa 30 = 14, Estufa Peças = 17) com
amostragem ~300s (5 min). Q.82 validou cura química em 68-71 °C
durante ~13-15 h.

**Definição de ciclo de cura** (decisão de negócio Q.100):
  - Threshold: `SD_TEMPERATURE >= 65 °C` (separa standby ~30 °C de
    cura activa observada 73-77 °C; `IOT_SENSOR_ALARM.SA_MIN=45` é
    o limite NELO documentado mas usamos 65 porque é onde os
    ciclos reais aparecem na distribuição).
  - Gap separador: gap entre leituras T≥65 maior que 60 min separa
    ciclos distintos. Validado empiricamente Q.100 Fase 0: dentro de
    um ciclo noturno real há thermo-cycling à 03h (queda <65 °C
    durante ~45 min antes de retomar), por isso 30 min era agressivo
    demais e dividia 1 ciclo em 2. 60 min mantém o ciclo nocturno
    de 12-13 h unido.
  - Duração mínima: ≥1 h (filtra picos transitórios não-cura).
  - Duração do ciclo: `MAX(ts) - MIN(ts)` dentro do ciclo (não
    "n_leituras × 5min" — esse subestima porque o intervalo
    nominal de amostragem não inclui o fim).

**Anchor Q.100 (validado Fase 0)**:
  - Estufa 60 (sensor 12) Abril 2026: **13 ciclos, ~165 h**.
    Padrão noturno (~19h→07h), 12.7 h médio, pico 79.4 °C.
  - Estufa 60 ano: ~570 h em 2026-03→2026-04 representam 63 %
    (sazonalidade forte; Dez/Fev praticamente zero).

**Granularidade da view**: 1 row por (sensor, ciclo). Cube agrega
por mês via timeDimension. `SUM(duracao_h)` é aditivo entre
estufas e meses (TEMPO).

Idempotente. Falha cedo se `factory_raw.iot_sensor_data` não existir.

Uso::

    .\\.venv\\Scripts\\python.exe scripts/setup_marts_ciclos_cura.py
"""
from __future__ import annotations

import asyncio
import sys

import asyncpg

from src.shared.config import settings


VIEW_SQL = """
CREATE OR REPLACE VIEW marts.v_ciclos_cura AS
-- Q.100 Medida 1 — ciclos de cura por sensor de estufa.
-- 1 row por ciclo (não por leitura). Janela contínua T>=65, gap entre
-- leituras T>=65 acima de 30 min separa ciclos.
WITH leituras AS (
    SELECT
        d."SD_SENSOR_ID"             AS sensor_id,
        s."SENSOR_NAME"              AS estufa,
        s."SENSOR_LOCATION"          AS estufa_local,
        d."SD_DATE"::timestamp       AS ts,
        d."SD_TEMPERATURE"::numeric  AS temp
    FROM factory_raw.iot_sensor_data d
    JOIN factory_raw.iot_sensor s
      ON s."SENSOR_ID" = d."SD_SENSOR_ID"
    WHERE s."SENSOR_TEMP" = TRUE
      AND (s."SENSOR_NAME" ILIKE '%estufa%' OR s."SENSOR_LOCATION" ILIKE '%estufa%')
      AND d."SD_TEMPERATURE" IS NOT NULL
      AND d."SD_TEMPERATURE"::numeric >= 65
),
-- Detectar inicio de novo ciclo: gap >30 min vs leitura T>=65 anterior do MESMO sensor.
flagged AS (
    SELECT
        sensor_id, estufa, estufa_local, ts, temp,
        CASE
            WHEN LAG(ts) OVER (PARTITION BY sensor_id ORDER BY ts) IS NULL
              OR (ts - LAG(ts) OVER (PARTITION BY sensor_id ORDER BY ts)) > INTERVAL '60 minutes'
            THEN 1 ELSE 0
        END AS new_cycle
    FROM leituras
),
numbered AS (
    SELECT
        sensor_id, estufa, estufa_local, ts, temp,
        SUM(new_cycle) OVER (PARTITION BY sensor_id ORDER BY ts) AS cycle_local_id
    FROM flagged
),
agregados AS (
    SELECT
        sensor_id,
        estufa,
        estufa_local,
        cycle_local_id,
        MIN(ts)                                                  AS ts_inicio,
        MAX(ts)                                                  AS ts_fim,
        EXTRACT(EPOCH FROM (MAX(ts) - MIN(ts))) / 3600.0         AS duracao_h,
        MAX(temp)                                                AS temp_max,
        AVG(temp)                                                AS temp_avg,
        COUNT(*)                                                 AS n_leituras
    FROM numbered
    GROUP BY 1, 2, 3, 4
)
SELECT
    -- Granularidade time = primeiro dia do mês de início (Cube timeDimension)
    DATE_TRUNC('month', ts_inicio)::date AS data,
    -- Identificador estável do ciclo
    sensor_id,
    estufa,
    estufa_local,
    ts_inicio,
    ts_fim,
    ROUND(duracao_h::numeric, 4)         AS duracao_h,
    ROUND(temp_max::numeric, 2)          AS temp_max,
    ROUND(temp_avg::numeric, 2)          AS temp_avg,
    n_leituras
FROM agregados
WHERE duracao_h >= 1.0
"""


async def _ensure_prereqs(pg_conn: asyncpg.Connection) -> None:
    """Confirma que iot_sensor_data + iot_sensor existem (Q.98)."""
    for table in ("iot_sensor_data", "iot_sensor"):
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
                "`python scripts/q98_setup_iot_mirror.py` para espelhar "
                "IoT, depois volta a correr este script."
            )

    await pg_conn.execute("CREATE SCHEMA IF NOT EXISTS marts")


async def setup() -> int:
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await _ensure_prereqs(conn)
        await conn.execute("DROP VIEW IF EXISTS marts.v_ciclos_cura")
        await conn.execute(VIEW_SQL)

        # Sanity 1: total rows + range temporal.
        n_rows = await conn.fetchval("SELECT COUNT(*) FROM marts.v_ciclos_cura")
        rng = await conn.fetchrow(
            """
            SELECT MIN(data) AS min_m, MAX(data) AS max_m,
                   MIN(ts_inicio) AS min_ts, MAX(ts_fim) AS max_ts
            FROM marts.v_ciclos_cura
            """
        )
        print(
            f"  OK view criada -- {n_rows:,} ciclos. "
            f"Range mes {rng['min_m']} a {rng['max_m']}."
        )

        # Sanity 2: duracao positiva + temp ≥65 em todas as rows.
        guard = await conn.fetchrow(
            """
            SELECT
                MIN(duracao_h)::numeric AS min_h,
                MAX(duracao_h)::numeric AS max_h,
                BOOL_AND(duracao_h >= 1.0) AS dur_min,
                BOOL_AND(temp_max >= 65.0) AS temp_ok
            FROM marts.v_ciclos_cura
            """
        )
        print(
            f"  Range guard: min_h={guard['min_h']}  max_h={guard['max_h']}  "
            f"dur_min1h={guard['dur_min']}  temp_max>=65={guard['temp_ok']}"
        )
        assert guard["dur_min"], "Filtro duracao>=1h violado"
        assert guard["temp_ok"], "Filtro T>=65 violado"

        # Anchor Q.100 / Estufa 60 Abril 2026: 13 ciclos, ~165h.
        anchor = await conn.fetchrow(
            """
            SELECT
                COUNT(*)::int                 AS n_ciclos,
                ROUND(SUM(duracao_h)::numeric, 1) AS horas_total,
                ROUND(AVG(duracao_h)::numeric, 2) AS duracao_avg,
                ROUND(MAX(temp_max)::numeric, 1)  AS temp_pico
            FROM marts.v_ciclos_cura
            WHERE sensor_id = 12
              AND data = '2026-04-01'
            """
        )
        print(
            f"  ANCHOR Estufa 60 Abril 2026: "
            f"{anchor['n_ciclos']} ciclos, {anchor['horas_total']} h, "
            f"medio {anchor['duracao_avg']} h, pico {anchor['temp_pico']} C."
        )
        # Aceitar 11-15 ciclos, 140-180 h (margem 10 % ambos os lados).
        assert 11 <= anchor["n_ciclos"] <= 15, (
            f"Anchor n_ciclos={anchor['n_ciclos']} fora do range 11-15"
        )
        assert 140 <= float(anchor["horas_total"]) <= 180, (
            f"Anchor horas={anchor['horas_total']} fora do range 140-180"
        )

        # Por estufa: quantos ciclos cada uma teve no espelho 1 ano.
        por_estufa = await conn.fetch(
            """
            SELECT sensor_id, estufa, estufa_local,
                   COUNT(*)::int AS n_ciclos,
                   ROUND(SUM(duracao_h)::numeric, 1) AS h_total
            FROM marts.v_ciclos_cura
            GROUP BY 1, 2, 3
            ORDER BY 4 DESC
            """
        )
        print("\n  Por estufa (ano espelho):")
        for r in por_estufa:
            print(
                f"    sensor {r['sensor_id']:>3}  "
                f"{(r['estufa'] or '?'):<25}  "
                f"{(r['estufa_local'] or '?'):<25}  "
                f"n_ciclos={r['n_ciclos']:>4}  total_h={r['h_total']}"
            )

        # Distribuicao mensal Estufa 60 (validar 145h Abril como pico).
        meses = await conn.fetch(
            """
            SELECT TO_CHAR(data, 'YYYY-MM') AS mes,
                   COUNT(*)::int                 AS n_ciclos,
                   ROUND(SUM(duracao_h)::numeric, 1) AS h
            FROM marts.v_ciclos_cura
            WHERE sensor_id = 12
            GROUP BY 1 ORDER BY 1 DESC LIMIT 14
            """
        )
        print("\n  Estufa 60 mensal (ultimos 14 meses):")
        for r in meses:
            print(f"    {r['mes']}  n={r['n_ciclos']:>3}  h={r['h']}")

        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(setup()))
