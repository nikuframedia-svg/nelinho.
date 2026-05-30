"""Q.93.B — validar `Cube == view` (Fase 1 do plano CUBE).

Prova que o Cube Core (Docker) modela a medida `consumo_material.consumo`
sobre `marts.v_consumo_material_dia` SEM divergir da view. Reutiliza as
mesmas constantes/âncoras da Fase 0 (verdade conhecida = view = Cube).

O elo:  verdade  ==  view  (Fase 0, 9/9 ok)  ==  Cube  (esta fase).
Se o Cube divergir da view, é erro silencioso a entrar pela porta nova
— delta zero ou explicado até à origem.

Pré-requisitos:
    1. View criada e populada (`scripts/setup_marts_cube_fase0.py`).
    2. Cube container UP (`docker compose up -d cube`).
    3. Cube SQL API em :15432, REST API em :4000.

Exit 0 se tudo passa; 1 se qualquer check falhar.

Uso:
    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts/validate_cube_fase1.py
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import asyncpg
import httpx

from scripts.validate_marts_consumo_material import (
    ANCHOR_MATERIAL_EXACT,
    ANCHOR_PERIOD_END,
    ANCHOR_PERIOD_START,
    ANCHOR_UNIT_ID,
    ANCHOR_VALUE,
    CheckResult,
    MONTHLY_EXPECTED,
    TOL,
)
from src.shared.database import engine as pg_engine


# Cube endpoints (defaults do docker-compose.yml service `cube`)
CUBE_SQL_HOST = "localhost"
CUBE_SQL_PORT = 15432
CUBE_REST_BASE = "http://localhost:4000"
CUBE_DB_NAME = "prodplan_one"

# Em DEV_MODE qualquer user/password funciona. asyncpg direto (sem SQLAlchemy)
# porque o Cube SQL API anuncia OIDs de tipo (114=json) que o SQLAlchemy +
# asyncpg interpretam mal em prepared statements — mesmo com statement_cache
# desligado. asyncpg.connect() + conn.fetch() com SQL inlined contorna isso.
CUBE_PG_DSN = (
    f"postgresql://cube:cube@{CUBE_SQL_HOST}:{CUBE_SQL_PORT}/{CUBE_DB_NAME}"
)

# Threshold de perf para Cube (mais folga que a view nativa — Cube tem
# overhead de planning + transformação SQL).
CUBE_PERF_THRESHOLD_S = 10.0


# ────────────────────────────── Helpers ──────────────────────────────


def _format_dec(v: Any) -> str:
    if v is None:
        return "None"
    if isinstance(v, Decimal):
        return f"{v.normalize():f}"
    return str(v)


def _delta(a: Decimal, b: Decimal) -> Decimal:
    return (a - b).copy_abs()


def _inline(sql: str, **params: Any) -> str:
    """Substitui :nome por literal Python-escapado.

    Necessário para o Cube SQL API: o protocolo Postgres-wire dele anuncia
    OIDs de tipo (114=json) que o asyncpg interpreta mal em prepared
    statements. Os valores aqui vêm de constantes trusted no validador
    (datas, nomes de material) — sem input externo, sem risco real de SQL
    injection. Mantemos o escape de aspas como defesa-em-profundidade.
    """
    out = sql
    for k, v in params.items():
        if v is None:
            replacement = "NULL"
        elif isinstance(v, str):
            replacement = "'" + v.replace("'", "''") + "'"
        elif isinstance(v, _dt.date):
            replacement = f"'{v.isoformat()}'"
        elif isinstance(v, (int, float, Decimal)):
            replacement = str(v)
        else:
            raise ValueError(f"_inline: tipo não suportado {type(v).__name__} para {k}")
        out = out.replace(f":{k}", replacement)
    return out


async def _cube_scalar(sql: str, **params: Any) -> Decimal | None:
    inlined = _inline(sql, **params)
    conn = await asyncpg.connect(CUBE_PG_DSN)
    try:
        row = await conn.fetchrow(inlined)
    finally:
        await conn.close()
    if row is None or row[0] is None:
        return None
    return Decimal(str(row[0]))


async def _cube_rows(sql: str, **params: Any) -> list[tuple[Any, ...]]:
    inlined = _inline(sql, **params)
    conn = await asyncpg.connect(CUBE_PG_DSN)
    try:
        rows = await conn.fetch(inlined)
    finally:
        await conn.close()
    return [tuple(r) for r in rows]


async def _pg_scalar(sql: str, **params: Any) -> Decimal | None:
    from sqlalchemy import text
    async with pg_engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        row = result.first()
    if row is None or row[0] is None:
        return None
    return Decimal(str(row[0]))


async def _pg_rows(sql: str, **params: Any) -> list[tuple[Any, ...]]:
    from sqlalchemy import text
    async with pg_engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        return [tuple(r) for r in result]


# ────────────────────────────── Check 0 — REST smoke ──────────────────────────────


async def check_0_rest_smoke() -> CheckResult:
    """Cube REST API responde em :4000 e o cube `consumo_material` aparece no /meta."""
    try:
        async with httpx.AsyncClient(base_url=CUBE_REST_BASE, timeout=10.0) as cli:
            r_ready = await cli.get("/readyz")
            # DEV_MODE: /meta aceita qualquer header (ou nenhum); um token bogus chega.
            r_meta = await cli.get(
                "/cubejs-api/v1/meta",
                headers={"Authorization": "bogus-dev-mode-token"},
            )
        if r_ready.status_code != 200:
            return CheckResult(
                "0 REST smoke",
                ok=False,
                detail=f"readyz={r_ready.status_code} body={r_ready.text[:200]}",
            )
        if r_meta.status_code != 200:
            return CheckResult(
                "0 REST smoke",
                ok=False,
                detail=f"meta={r_meta.status_code} body={r_meta.text[:200]}",
            )
        cubes_meta = r_meta.json().get("cubes", [])
        names = [c.get("name") for c in cubes_meta]
        ok = "consumo_material" in names
        return CheckResult(
            "0 REST smoke",
            ok=ok,
            detail=(
                f"readyz=200  meta=200  cubes_in_catalog={names}  "
                f"consumo_material_present={ok}"
            ),
        )
    except Exception as exc:
        return CheckResult(
            "0 REST smoke",
            ok=False,
            detail=f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}",
        )


# ────────────────────────────── Checks 1.1–1.5 ──────────────────────────────


async def check_11_anchor() -> CheckResult:
    """Âncora: consumo_material(Resina Lavesan EN 720 × tambor, Abril 2026) = 4.724."""
    total = await _cube_scalar(
        """
        SELECT MEASURE(consumo) AS consumo
        FROM consumo_material
        WHERE material = :mat
          AND unidade_id = :uid
          AND data >= :ini
          AND data < :fim
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if total is None:
        return CheckResult(
            "1.1 anchor (Cube)",
            ok=False,
            detail="Cube devolveu NULL para a âncora",
        )
    delta = _delta(total, ANCHOR_VALUE)
    return CheckResult(
        "1.1 anchor (Cube)",
        ok=delta <= TOL,
        detail=(
            f"cube={_format_dec(total)}  ref={_format_dec(ANCHOR_VALUE)}  "
            f"delta={_format_dec(delta)}  tol={_format_dec(TOL)}"
        ),
    )


async def check_12_cube_view_parity() -> CheckResult:
    """Paridade Cube ↔ view (delta tem de ser < 1e-10)."""
    cube_total = await _cube_scalar(
        """
        SELECT MEASURE(consumo) FROM consumo_material
        WHERE material = :mat AND unidade_id = :uid
          AND data >= :ini AND data < :fim
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    view_total = await _pg_scalar(
        """
        SELECT SUM(quantidade) FROM marts.v_consumo_material_dia
        WHERE material = :mat AND unidade_id = :uid
          AND data >= :ini AND data < :fim
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    cube_total = cube_total or Decimal(0)
    view_total = view_total or Decimal(0)
    delta = _delta(cube_total, view_total)
    # Cube e view fazem o MESMO cálculo sobre as MESMAS rows — delta tem
    # de ser apenas arredondamento (≤ 1e-10).
    ok = delta <= Decimal("0.0000000001")
    return CheckResult(
        "1.2 cube vs view parity",
        ok=ok,
        detail=(
            f"cube={_format_dec(cube_total)}  view={_format_dec(view_total)}  "
            f"delta={_format_dec(delta)}"
        ),
    )


async def check_13_monthly() -> CheckResult:
    """Distribuição mensal 12 meses (mesmo dict da Fase 0)."""
    rows = await _cube_rows(
        """
        SELECT DATE_TRUNC('month', data) AS mes,
               MEASURE(consumo) AS total
        FROM consumo_material
        WHERE material = :mat AND unidade_id = :uid
          AND data >= :ini AND data < :fim
        GROUP BY DATE_TRUNC('month', data)
        ORDER BY 1
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=_dt.date(2025, 5, 1),
        fim=_dt.date(2026, 5, 1),
    )
    got: dict[str, Decimal] = {}
    for r in rows:
        mes_obj = r[0]
        if mes_obj is None:
            continue
        mes_key = mes_obj.strftime("%Y-%m") if hasattr(mes_obj, "strftime") else str(mes_obj)[:7]
        if r[1] is not None:
            got[mes_key] = Decimal(str(r[1]))

    deltas: list[str] = []
    n_pass = 0
    for mes, expected in MONTHLY_EXPECTED.items():
        actual = got.get(mes)
        if actual is None:
            deltas.append(f"  {mes}: cube=NULL  ref={_format_dec(expected)}  FAIL")
            continue
        d = _delta(actual, expected)
        status = "ok" if d <= TOL else "FAIL"
        if d <= TOL:
            n_pass += 1
        deltas.append(
            f"  {mes}: cube={_format_dec(actual)}  "
            f"ref={_format_dec(expected)}  delta={_format_dec(d)}  {status}"
        )
    return CheckResult(
        "1.3 monthly distribution (Cube)",
        ok=n_pass == len(MONTHLY_EXPECTED),
        detail=f"{n_pass}/{len(MONTHLY_EXPECTED)} meses dentro de TOL ({_format_dec(TOL)})",
        rows=deltas,
    )


async def check_14_ranking_parity() -> CheckResult:
    """Ranking (material, unidade_id) Abril 2026 — Cube vs view linha-a-linha."""
    cube_rows = await _cube_rows(
        """
        SELECT material, unidade_id, MEASURE(consumo) AS total
        FROM consumo_material
        WHERE data >= :ini AND data < :fim
        GROUP BY material, unidade_id
        ORDER BY material, unidade_id
        """,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    view_rows = await _pg_rows(
        """
        SELECT material, unidade_id, SUM(quantidade) AS total
        FROM marts.v_consumo_material_dia
        WHERE data >= :ini AND data < :fim
        GROUP BY material, unidade_id
        ORDER BY material, unidade_id
        """,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )

    cube_map = {(r[0], r[1]): Decimal(str(r[2])) for r in cube_rows if r[2] is not None}
    view_map = {(r[0], r[1]): Decimal(str(r[2])) for r in view_rows if r[2] is not None}

    all_keys = set(cube_map) | set(view_map)
    mismatched: list[str] = []
    n_match = 0
    for key in all_keys:
        cv = cube_map.get(key)
        vv = view_map.get(key)
        if cv is None or vv is None:
            mismatched.append(f"  {key}: cube={_format_dec(cv)} view={_format_dec(vv)}")
            continue
        d = _delta(cv, vv)
        if d <= Decimal("0.0000000001"):
            n_match += 1
        else:
            mismatched.append(
                f"  {key}: cube={_format_dec(cv)}  view={_format_dec(vv)}  delta={_format_dec(d)}"
            )
    ok = len(mismatched) == 0
    return CheckResult(
        "1.4 ranking parity (Cube vs view)",
        ok=ok,
        detail=(
            f"{n_match}/{len(all_keys)} (material,unidade) batem byte-a-byte. "
            f"Mismatched={len(mismatched)}"
        ),
        rows=mismatched[:10],  # top 10 only
    )


async def check_15_unit_separation() -> CheckResult:
    """Material com unidades múltiplas → Cube devolve linhas separadas, não soma cega.

    `Secante Lavesan L 33` existe em unidade_id=12 e =18. O Cube tem de devolver
    DUAS linhas (uma por unidade), nunca uma soma. Se devolver uma só linha, é bug:
    estamos a misturar kg/m/tambor.
    """
    rows = await _cube_rows(
        """
        SELECT unidade_id, MEASURE(consumo) AS total
        FROM consumo_material
        WHERE material = :mat
          AND data >= :ini AND data < :fim
        GROUP BY unidade_id
        ORDER BY unidade_id
        """,
        mat="Secante Lavesan L 33",
        ini=_dt.date(2025, 1, 1),  # janela larga, é raro
        fim=_dt.date(2026, 6, 1),
    )
    # Esperamos pelo menos 2 unidades distintas para este material (ou 0 se
    # não houve consumo na janela; mas a view tem 1.3M+ linhas, deve existir).
    units = {r[0] for r in rows if r[0] is not None}
    # Aceitar 0 (sem consumo na janela) OU >=2 (separação correcta).
    # Falhar SE tiver exactamente 1 row mas a view mostra >1 — provaria soma cega.
    view_units = await _pg_rows(
        """
        SELECT DISTINCT unidade_id FROM marts.v_consumo_material_dia
        WHERE material = :mat
          AND data >= :ini AND data < :fim
        """,
        mat="Secante Lavesan L 33",
        ini=_dt.date(2025, 1, 1),
        fim=_dt.date(2026, 6, 1),
    )
    view_unit_set = {r[0] for r in view_units}
    ok = units == view_unit_set
    return CheckResult(
        "1.5 unit separation",
        ok=ok,
        detail=(
            f"cube_units={sorted(units)}  view_units={sorted(view_unit_set)}  "
            f"match={ok}"
        ),
    )


# ────────────────────────────── Checks 2.1–2.4 ──────────────────────────────


async def check_21_no_consumption_day() -> CheckResult:
    rows = await _cube_rows(
        """
        SELECT material, MEASURE(consumo)
        FROM consumo_material
        WHERE data = :d
        GROUP BY material
        """,
        d=_dt.date(1900, 1, 1),
    )
    ok = len(rows) == 0
    return CheckResult(
        "2.1 day without consumption",
        ok=ok,
        detail=f"rows={len(rows)} (esperado 0)",
    )


async def check_22_inexistent_material() -> CheckResult:
    rows = await _cube_rows(
        """
        SELECT MEASURE(consumo)
        FROM consumo_material
        WHERE material = :mat
        """,
        mat="xyz_inexistente_zzzz",
    )
    # GROUP BY ausente → Cube devolve 1 row com SUM=NULL para 0 matches
    # (igual a Postgres). Ambos comportamentos aceitáveis; falhar só se erro.
    if len(rows) == 0:
        return CheckResult(
            "2.2 inexistent material",
            ok=True,
            detail="rows=0 (vazio honesto)",
        )
    val = rows[0][0] if rows else None
    ok = val is None or Decimal(str(val)) == Decimal(0)
    return CheckResult(
        "2.2 inexistent material",
        ok=ok,
        detail=f"rows={len(rows)} value={val} (esperado None ou 0)",
    )


async def check_23_month_boundary() -> CheckResult:
    rows = await _cube_rows(
        """
        SELECT data, MEASURE(consumo)
        FROM consumo_material
        WHERE data >= :ini AND data < :fim
        GROUP BY data
        ORDER BY data
        """,
        ini=_dt.date(2026, 3, 30),
        fim=_dt.date(2026, 4, 2),
    )
    distinct_days = {str(r[0])[:10] for r in rows if r[0] is not None}
    ok = bool(distinct_days)
    return CheckResult(
        "2.3 month boundary",
        ok=ok,
        detail=f"dias_distintos={sorted(distinct_days)}",
    )


async def check_24_perf() -> CheckResult:
    """SUM Cube sobre 13 meses < CUBE_PERF_THRESHOLD_S (10s)."""
    t0 = time.monotonic()
    rows = await _cube_rows(
        """
        SELECT DATE_TRUNC('month', data) AS mes, MEASURE(consumo) AS total
        FROM consumo_material
        WHERE data >= :ini
        GROUP BY DATE_TRUNC('month', data)
        """,
        ini=_dt.date(2025, 5, 1),
    )
    elapsed = time.monotonic() - t0
    ok = elapsed < CUBE_PERF_THRESHOLD_S
    return CheckResult(
        "2.4 volume perf",
        ok=ok,
        detail=f"rows={len(rows)}  elapsed={elapsed:.2f}s  limite={CUBE_PERF_THRESHOLD_S:.2f}s",
    )


# ────────────────────────────── Runner ──────────────────────────────


CHECKS = [
    check_0_rest_smoke,
    check_11_anchor,
    check_12_cube_view_parity,
    check_13_monthly,
    check_14_ranking_parity,
    check_15_unit_separation,
    check_21_no_consumption_day,
    check_22_inexistent_material,
    check_23_month_boundary,
    check_24_perf,
]


async def run_all() -> int:
    print("Cube Fase 1 — validacao Cube == view\n")
    results: list[CheckResult] = []
    for fn in CHECKS:
        try:
            res = await fn()
        except Exception as exc:
            res = CheckResult(
                fn.__name__,
                ok=False,
                detail=f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}",
            )
        results.append(res)
        mark = "OK  " if res.ok else "FAIL"
        print(f"  [{mark}] {res.name}: {res.detail}")
        for line in res.rows:
            print(line)

    n_fail = sum(1 for r in results if not r.ok)
    print()
    print(f"Resultado: {len(results) - n_fail}/{len(results)} checks ok.")
    return 0 if n_fail == 0 else 1


def main() -> int:
    return asyncio.run(run_all())


if __name__ == "__main__":
    sys.exit(main())
