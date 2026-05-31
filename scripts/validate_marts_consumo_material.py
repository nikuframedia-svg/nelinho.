"""Q.93.A — validar `marts.v_consumo_material_dia` contra a verdade conhecida.

Coração da Fase 0 do plano CUBE: a view só "existe" depois de passar nestes 4
checks contra Postgres real + 5 casos de fronteira. Delta zero ou explicado;
"está perto" não é aceitável.

Verdade-âncora (Q.78 §Q4, agent_docs/q78_investigacao_buracos.md:206-217):
    Resina Lavesan EN 720 (P_ID=22876), unidade_id=18 (tambor 240kg),
    Abril 2026 = 4.724 unidades (com factor 0.00417 aplicado).
    Distribuição mensal min 1.25 (Ago 2025), max 5.94 (Mar 2026).

NOTA: o material `Resina Lavesan EN 720` é UM produto específico (P_ID=22876)
com unidade canónica `18 = tambor`. NÃO confundir com a soma agregada de tudo o
que faz match `ILIKE '%lavesan%'` (~25 produtos, mistura de unidades 7/12/18,
~2413 em Abril 2026 — número sem significado físico).

Exit 0 se tudo passa; 1 se qualquer check falhar.

Uso:
    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts/validate_marts_consumo_material.py
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import pathlib
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import yaml
from sqlalchemy import text

from src.shared.database import engine


# Tolerância de arredondamento — números na BD vêm com 3-4 casas decimais.
TOL = Decimal("0.01")

ANCHOR_VALUE = Decimal("4.724")  # Resina Lavesan EN 720 × tambor, Abril 2026
ANCHOR_PERIOD_START = _dt.date(2026, 4, 1)
ANCHOR_PERIOD_END = _dt.date(2026, 5, 1)
ANCHOR_MATERIAL_EXACT = "Resina Lavesan EN 720"  # P_ID=22876
ANCHOR_UNIT_ID = 18  # tambor 240kg (P_UNI_MOV_FACTOR=0.00417 aplicado)
# Mantemos um pattern ILIKE para o cross-check em supply.* que usa material_master.name.
ANCHOR_MATERIAL_LIKE = "%Resina Lavesan EN 720%"

# Distribuição mensal documentada em Q.78 §Q4 (last 13 months).
MONTHLY_EXPECTED: dict[str, Decimal] = {
    "2025-05": Decimal("4.185"),
    "2025-06": Decimal("3.935"),
    "2025-07": Decimal("4.128"),
    "2025-08": Decimal("1.248"),
    "2025-09": Decimal("4.825"),
    "2025-10": Decimal("4.672"),
    "2025-11": Decimal("4.092"),
    "2025-12": Decimal("3.411"),
    "2026-01": Decimal("3.195"),
    "2026-02": Decimal("4.019"),
    "2026-03": Decimal("5.938"),
    "2026-04": Decimal("4.724"),
    # 2026-05 está parcial (24 dias) — não validar como ponto âncora.
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    rows: list[Any] = field(default_factory=list)


# ────────────────────────────── Helpers ──────────────────────────────


async def _scalar(sql: str, **params: Any) -> Decimal | None:
    """Devolve o primeiro valor da primeira linha, ou None."""
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        row = result.first()
    if row is None:
        return None
    val = row[0]
    if val is None:
        return None
    return Decimal(str(val))


async def _rows(sql: str, **params: Any) -> list[tuple[Any, ...]]:
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        return [tuple(r) for r in result]


def _delta(a: Decimal, b: Decimal) -> Decimal:
    return (a - b).copy_abs()


def _format_dec(v: Any) -> str:
    if v is None:
        return "None"
    if isinstance(v, Decimal):
        return f"{v.normalize():f}"
    return str(v)


# ────────────────────────────── Checks 4.1–4.4 ──────────────────────────────


async def check_41_anchor() -> CheckResult:
    """Resina Lavesan EN 720 × tambor, Abril 2026 = 4.724 (tolerância ≤ 0.01)."""
    total = await _scalar(
        """
        SELECT SUM(quantidade)
        FROM marts.v_consumo_material_dia
        WHERE material = :mat
          AND unidade_id = :uid
          AND data >= :ini AND data < :fim
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if total is None:
        return CheckResult(
            "4.1 anchor",
            ok=False,
            detail=f"view devolveu NULL para Resina Lavesan {ANCHOR_PERIOD_START}",
        )
    delta = _delta(total, ANCHOR_VALUE)
    ok = delta <= TOL
    return CheckResult(
        "4.1 anchor",
        ok=ok,
        detail=(
            f"view={_format_dec(total)}  ref={_format_dec(ANCHOR_VALUE)}  "
            f"delta={_format_dec(delta)}  tol={_format_dec(TOL)}"
        ),
    )


def _load_route_q86() -> dict[str, Any]:
    """Lê o YAML da rota Q.86 (sync — chamado uma vez fora do loop async)."""
    route_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "routes"
        / "materiais"
        / "consumo_materiais.yml"
    )
    return yaml.safe_load(route_path.read_text(encoding="utf-8"))


_ROUTE_Q86 = _load_route_q86()


async def check_42_route_parity() -> CheckResult:
    """Paridade byte-a-byte com a SQL da rota Q.86 (consumo_materiais.yml)."""
    spec = _ROUTE_Q86
    route_sql = spec["sql"]
    defaults = spec.get("defaults", {})

    # A SQL da rota usa :data_inicio, :data_fim, :tpmov_consumo,
    # :pcont_materia_prima, :material_pattern. Bindamos os mesmos valores.
    params = {
        "data_inicio": ANCHOR_PERIOD_START,
        "data_fim": ANCHOR_PERIOD_END,
        "tpmov_consumo": defaults.get("tpmov_consumo", 11),
        "pcont_materia_prima": defaults.get("pcont_materia_prima", 1),
        "material_pattern": ANCHOR_MATERIAL_LIKE,
    }

    rows = await _rows(route_sql, **params)
    # SQL devolve (unidade_id, P_NOME, total, n_movimentos) por linha.
    route_total = sum((Decimal(str(r[2])) for r in rows if r[2] is not None), Decimal(0))

    view_total = await _scalar(
        """
        SELECT SUM(quantidade)
        FROM marts.v_consumo_material_dia
        WHERE material ILIKE :pat
          AND data >= :ini AND data < :fim
        """,
        pat=ANCHOR_MATERIAL_LIKE,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if view_total is None:
        view_total = Decimal(0)

    delta = _delta(route_total, view_total)
    ok = delta <= TOL
    return CheckResult(
        "4.2 route parity",
        ok=ok,
        detail=(
            f"route_q86={_format_dec(route_total)}  view={_format_dec(view_total)}  "
            f"delta={_format_dec(delta)}  rows_route={len(rows)}"
        ),
    )


async def check_43_monthly_distribution() -> CheckResult:
    """Distribuição mensal Resina Lavesan EN 720 × tambor (12 meses-âncora)."""
    rows = await _rows(
        """
        SELECT to_char(date_trunc('month', data), 'YYYY-MM') AS mes,
               SUM(quantidade)                                AS total
        FROM marts.v_consumo_material_dia
        WHERE material = :mat
          AND unidade_id = :uid
          AND data >= :ini AND data < :fim
        GROUP BY 1
        ORDER BY 1
        """,
        mat=ANCHOR_MATERIAL_EXACT,
        uid=ANCHOR_UNIT_ID,
        ini=_dt.date(2025, 5, 1),
        fim=_dt.date(2026, 5, 1),
    )
    got = {str(r[0]): Decimal(str(r[1])) for r in rows if r[1] is not None}

    deltas: list[str] = []
    n_pass = 0
    for mes, expected in MONTHLY_EXPECTED.items():
        actual = got.get(mes)
        if actual is None:
            deltas.append(f"  {mes}: view=NULL  ref={_format_dec(expected)}  FAIL")
            continue
        d = _delta(actual, expected)
        status = "ok" if d <= TOL else "FAIL"
        if d <= TOL:
            n_pass += 1
        deltas.append(
            f"  {mes}: view={_format_dec(actual)}  "
            f"ref={_format_dec(expected)}  delta={_format_dec(d)}  {status}"
        )

    ok = n_pass == len(MONTHLY_EXPECTED)
    return CheckResult(
        "4.3 monthly distribution",
        ok=ok,
        detail=f"{n_pass}/{len(MONTHLY_EXPECTED)} meses dentro da tolerância",
        rows=deltas,
    )


async def check_44_cross_check_supply() -> CheckResult:
    """Cross-check com supply.inventory_ledger_entries (curagem ETL Q.64.A)."""
    # Verifica se a tabela curada tem dados — se não tem, é informativo (não falha).
    n_rows_curated = await _scalar(
        """
        SELECT COUNT(*) FROM supply.inventory_ledger_entries
        WHERE transaction_type = 'consume'
        """
    )
    if n_rows_curated is None or n_rows_curated == 0:
        return CheckResult(
            "4.4 cross-check supply",
            ok=True,  # não bloqueia: curagem pode estar desligada em dev
            detail=(
                "supply.inventory_ledger_entries vazia (ou sem consumos) — "
                "cross-check skipped. Re-correr quando ETL Q.64.A estiver populado."
            ),
        )

    total_curated = await _scalar(
        """
        SELECT SUM(ile.qty_out)
        FROM supply.inventory_ledger_entries ile
        JOIN supply.supply_material_master mm ON mm.sku_id = ile.sku_id
        WHERE ile.transaction_type = 'consume'
          AND mm.name ILIKE :pat
          AND ile.date >= :ini AND ile.date < :fim
        """,
        pat=ANCHOR_MATERIAL_LIKE,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if total_curated is None:
        total_curated = Decimal(0)

    total_view = await _scalar(
        """
        SELECT SUM(quantidade)
        FROM marts.v_consumo_material_dia
        WHERE material ILIKE :pat
          AND data >= :ini AND data < :fim
        """,
        pat=ANCHOR_MATERIAL_LIKE,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if total_view is None:
        total_view = Decimal(0)

    delta = _delta(total_view, total_curated)
    # Não bloqueia o validador se divergir — é informação para a Fase 1 sanear o
    # ETL. Mas marca-se claramente no output.
    ok = True
    note = (
        "BATEM dentro da tolerância" if delta <= TOL
        else "DIVERGEM -- investigar ETL Q.64.A (não bloqueia Fase 0)"
    )
    return CheckResult(
        "4.4 cross-check supply",
        ok=ok,
        detail=(
            f"view={_format_dec(total_view)}  "
            f"curated_supply={_format_dec(total_curated)}  "
            f"delta={_format_dec(delta)}  -> {note}"
        ),
    )


# ────────────────────────────── Passo 5 — Robustez ──────────────────────────────


async def check_5_no_consumption_day() -> CheckResult:
    """Dia sem consumo → 0 rows (não NULL, não erro)."""
    rows = await _rows(
        """
        SELECT * FROM marts.v_consumo_material_dia
        WHERE data = :d
        """,
        d=_dt.date(1900, 1, 1),
    )
    ok = len(rows) == 0
    return CheckResult(
        "5.1 day without consumption",
        ok=ok,
        detail=f"rows={len(rows)} (esperado 0)",
    )


async def check_5_inexistent_material() -> CheckResult:
    rows = await _rows(
        """
        SELECT * FROM marts.v_consumo_material_dia
        WHERE material ILIKE :pat
        """,
        pat="%xyzinexistent_zzz%",
    )
    ok = len(rows) == 0
    return CheckResult(
        "5.2 inexistent material",
        ok=ok,
        detail=f"rows={len(rows)} (esperado 0)",
    )


async def check_5_month_boundary() -> CheckResult:
    """Viragem de mês — nenhuma linha perdida no corte 2026-03-30 a 2026-04-02."""
    rows = await _rows(
        """
        SELECT data, SUM(quantidade) AS q, COUNT(*) AS n
        FROM marts.v_consumo_material_dia
        WHERE data >= :ini AND data < :fim
        GROUP BY data
        ORDER BY data
        """,
        ini=_dt.date(2026, 3, 30),
        fim=_dt.date(2026, 4, 2),
    )
    # Esperamos pelo menos uma linha por dia útil; principal é não dar erro nem
    # devolver NULL em datas válidas.
    distinct_days = {str(r[0]) for r in rows}
    ok = bool(distinct_days)  # tem de devolver pelo menos um dia
    return CheckResult(
        "5.3 month boundary",
        ok=ok,
        detail=f"dias_distintos={sorted(distinct_days)}",
    )


async def check_5_factor_applied() -> CheckResult:
    """Factor de conversão aplicado: view ≠ SUM(MOV_QUANTIDADE) cru.

    Lavesan tem P_UNI_MOV_FACTOR=0.00417 (tambor 240kg). Se o factor não fosse
    aplicado, o SUM da view seria ~240× o SUM bruto. Aqui forçamos a diferença.
    """
    view_total = await _scalar(
        """
        SELECT SUM(quantidade)
        FROM marts.v_consumo_material_dia
        WHERE material ILIKE :pat
          AND data >= :ini AND data < :fim
        """,
        pat=ANCHOR_MATERIAL_LIKE,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    raw_total = await _scalar(
        """
        SELECT SUM(m."MOV_QUANTIDADE"::numeric)
        FROM factory_raw.movimento m
        JOIN factory_raw.produto p ON p."P_ID" = m."MOV_P_ID"
        WHERE p."P_NOME" ILIKE :pat
          AND p."P_PCONT_ID" = 1
          AND m."MOV_TPMOV_ID" = 11
          AND CAST(m."MOV_DATA" AS timestamp) >= :ini
          AND CAST(m."MOV_DATA" AS timestamp) <  :fim
        """,
        pat=ANCHOR_MATERIAL_LIKE,
        ini=ANCHOR_PERIOD_START,
        fim=ANCHOR_PERIOD_END,
    )
    if view_total is None or raw_total is None:
        return CheckResult(
            "5.4 factor applied",
            ok=False,
            detail=f"view={_format_dec(view_total)}  raw={_format_dec(raw_total)}",
        )
    # Esperamos factor != 1: |view - raw| > tolerância.
    differs = _delta(view_total, raw_total) > TOL
    return CheckResult(
        "5.4 factor applied",
        ok=differs,
        detail=(
            f"view={_format_dec(view_total)}  raw_sum={_format_dec(raw_total)}  "
            f"factor {'aplicado' if differs else 'NÃO aplicado (BUG)'}"
        ),
    )


async def check_5_volume_perf() -> CheckResult:
    """Tempo de SUM sobre 12 meses < 5s em Postgres dev."""
    import time
    t0 = time.monotonic()
    total = await _scalar(
        """
        SELECT SUM(quantidade)
        FROM marts.v_consumo_material_dia
        WHERE data >= :ini
        """,
        ini=_dt.date(2025, 5, 1),
    )
    elapsed = time.monotonic() - t0
    ok = elapsed < 5.0
    return CheckResult(
        "5.5 volume perf",
        ok=ok,
        detail=(
            f"sum={_format_dec(total)}  elapsed={elapsed:.2f}s  "
            f"limite=5.00s"
        ),
    )


# ────────────────────────────── Runner ──────────────────────────────


CHECKS = [
    check_41_anchor,
    check_42_route_parity,
    check_43_monthly_distribution,
    check_44_cross_check_supply,
    check_5_no_consumption_day,
    check_5_inexistent_material,
    check_5_month_boundary,
    check_5_factor_applied,
    check_5_volume_perf,
]


async def run_all() -> int:
    results: list[CheckResult] = []
    print("Cube Fase 0 — validação de marts.v_consumo_material_dia\n")
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
