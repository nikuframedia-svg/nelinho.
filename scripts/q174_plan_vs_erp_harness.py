"""Q.174.F9 — harness plano-nosso vs planeador canónico do ERP (Z_PrevisaoPlano).

O ERP corre o planeador de laminação dele e persiste a previsão na tabela
`Z_PrevisaoPlano` (barco-a-barco: OF, Dt_Lam, turno, molde, Dt_Trans). Este
harness compara essa previsão com o NOSSO último plano saudável — detector
permanente de fórmula-errada: se divergirmos em bloco do planeador que a
fábrica usa há anos, ou os dados ou o modelo estão tortos.

Métricas:
  * cobertura — % dos barcos do plano ERP que existem no nosso commit;
  * Δ laminação — distribuição (mediana, |média|, % dentro de ±2/±5 dias)
    entre o nosso início de Laminagem (fases 1/54/67) e o Dt_Lam do ERP;
  * acordo de molde — % das OFs em que escolhemos o MESMO molde;
  * top divergências com detalhe (para investigar uma a uma).

Read-only nos dois lados (SELECT no ERP; commit já gravado no Postgres).
Cron-able: exit 0 por defeito; `--fail-median-days N` torna-o um gate.

Uso::

    $env:PYTHONPATH = "."
    .\\.venv\\Scripts\\python.exe scripts/q174_plan_vs_erp_harness.py
    .\\.venv\\Scripts\\python.exe scripts/q174_plan_vs_erp_harness.py --json out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")

# Fases de laminação de BARCO no catálogo canónico (factory_raw.fases_producao):
# 1=Laminagem, 54=Laminagem Double Dutch, 67=Laminagem Infusão. A 36 é de
# PEÇAS (fluxo próprio) e a 11 ("Não Laminado") é estado, não fase.
LAMINATION_PHASE_IDS = {"1", "54", "67"}

ERP_DSN = os.environ.get(
    "MAR_KAYAKS_DSN",
    "DRIVER={SQL Server};SERVER=fabrica.nelo.eu,1039;DATABASE=MAR-KAYAKS;"
    "UID=nikufra;PWD=arfukin2026",
)


def _load_erp_plan() -> List[Dict[str, Any]]:
    """Lê a previsão canónica do ERP (tabela viva, reescrita a cada run)."""
    import pyodbc

    cn = pyodbc.connect(ERP_DSN, timeout=20)
    try:
        cur = cn.cursor()
        cur.execute(
            "SELECT [OF], Modelo, Turno, Molde, Dt_Trans, Dt_Lam, Dif "
            "FROM Z_PrevisaoPlano ORDER BY Dt_Lam, Turno"
        )
        rows = [
            {
                "of_id": str(r[0]),
                "modelo": str(r[1] or ""),
                "turno": int(r[2] or 0),
                "molde": str(r[3]) if r[3] is not None else None,
                "dt_trans": r[4].date() if r[4] else None,
                "dt_lam": r[5].date() if r[5] else None,
            }
            for r in cur.fetchall()
        ]
    finally:
        cn.close()
    return rows


async def _load_our_plan() -> Dict[str, Any]:
    """Último commit SAUDÁVEL: início de laminação + molde por order_id."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from src.plan.cpo.commits import CommitsService
    from src.shared.config import settings

    eng = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(eng) as session:
            commits = CommitsService(session, DEV_TENANT)
            rows = await commits.list_commits(limit=1, healthy_only=True)
            if not rows:
                return {"commit": None, "lam": {}, "orders": set()}
            commit = await commits.get_by_sha(rows[0].commit_sha256)
            ops = list(commit.operations or [])
    finally:
        await eng.dispose()

    lam: Dict[str, Dict[str, Any]] = {}
    orders: set = set()
    for o in ops:
        oid = str(o.get("order_id") or "")
        if not oid:
            continue
        orders.add(oid)
        if str(o.get("phase_id") or "") not in LAMINATION_PHASE_IDS:
            continue
        try:
            start = datetime.fromisoformat(str(o.get("start_time") or ""))
        except ValueError:
            continue
        cur = lam.get(oid)
        if cur is None or start < cur["start"]:
            lam[oid] = {
                "start": start,
                "mold_id": str(o.get("mold_id")) if o.get("mold_id") else None,
            }
    return {
        "commit": {
            "sha": commit.commit_sha256,
            "status": commit.status,
            "created_at": commit.created_at.isoformat(),
            "operations": len(ops),
        },
        "lam": lam,
        "orders": orders,
    }


def _compare(erp: List[Dict[str, Any]], ours: Dict[str, Any]) -> Dict[str, Any]:
    lam = ours["lam"]
    orders = ours["orders"]

    in_plan = [b for b in erp if b["of_id"] in orders]
    with_lam = [b for b in in_plan if b["of_id"] in lam and b["dt_lam"]]

    diffs: List[int] = []
    mold_both = 0
    mold_match = 0
    detail: List[Dict[str, Any]] = []
    for b in with_lam:
        our = lam[b["of_id"]]
        d = (our["start"].date() - b["dt_lam"]).days
        diffs.append(d)
        if b["molde"] and our["mold_id"]:
            mold_both += 1
            if b["molde"] == our["mold_id"]:
                mold_match += 1
        detail.append({
            "of_id": b["of_id"],
            "modelo": b["modelo"],
            "erp_dt_lam": b["dt_lam"].isoformat(),
            "nosso_lam": our["start"].date().isoformat(),
            "delta_dias": d,
            "erp_molde": b["molde"],
            "nosso_molde": our["mold_id"],
        })

    abs_diffs = [abs(d) for d in diffs]
    return {
        "erp_boats": len(erp),
        "coverage_any_op": len(in_plan),
        "coverage_lamination": len(with_lam),
        "delta": {
            "median_days": statistics.median(diffs) if diffs else None,
            "mean_abs_days": (
                round(statistics.fmean(abs_diffs), 2) if abs_diffs else None
            ),
            "within_2d_pct": (
                round(100 * sum(1 for d in abs_diffs if d <= 2) / len(abs_diffs), 1)
                if abs_diffs else None
            ),
            "within_5d_pct": (
                round(100 * sum(1 for d in abs_diffs if d <= 5) / len(abs_diffs), 1)
                if abs_diffs else None
            ),
        },
        "mold": {
            "both_assigned": mold_both,
            "same_mold": mold_match,
            "agreement_pct": (
                round(100 * mold_match / mold_both, 1) if mold_both else None
            ),
        },
        "top_divergences": sorted(
            detail, key=lambda x: -abs(x["delta_dias"])
        )[:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", type=str, default=None,
                        help="grava o relatório completo em JSON")
    parser.add_argument("--fail-median-days", type=float, default=None,
                        help="exit 1 se |mediana Delta| exceder este valor (gate)")
    args = parser.parse_args()

    print("-- Q.174.F9: plano nosso vs Z_PrevisaoPlano (ERP) --")
    erp = _load_erp_plan()
    print(f"ERP: {len(erp)} barcos no plano de laminação "
          f"(Dt_Lam {erp[0]['dt_lam']} -> {erp[-1]['dt_lam']})" if erp
          else "ERP: Z_PrevisaoPlano VAZIA -- o planeador deles não correu?")
    if not erp:
        return 0

    ours = asyncio.run(_load_our_plan())
    if ours["commit"] is None:
        print("NOSSO: sem commit saudável -- SKIP (corre o robo/POST /schedule primeiro).")
        return 0
    c = ours["commit"]
    print(f"NOSSO: commit {c['sha'][:8]} ({c['status']}, {c['operations']} ops, "
          f"{c['created_at'][:10]}); laminações no plano: {len(ours['lam'])}")

    rep = _compare(erp, ours)
    cov = rep["coverage_any_op"]
    lamc = rep["coverage_lamination"]
    print(f"\ncobertura: {cov}/{rep['erp_boats']} barcos do ERP no nosso plano "
          f"({100 * cov / rep['erp_boats']:.0f}%); com laminação planeada: {lamc}")
    d = rep["delta"]
    if d["median_days"] is not None:
        print(f"Delta laminação (nosso - ERP): mediana {d['median_days']:+.0f}d | "
              f"|média| {d['mean_abs_days']}d | +-2d {d['within_2d_pct']}% | "
              f"+-5d {d['within_5d_pct']}%")
    m = rep["mold"]
    if m["agreement_pct"] is not None:
        print(f"molde igual: {m['same_mold']}/{m['both_assigned']} "
              f"({m['agreement_pct']}%)")
    print("\ntop divergências:")
    for t in rep["top_divergences"][:5]:
        print(f"  OF {t['of_id']:<8} {t['modelo'][:28]:<28} "
              f"ERP {t['erp_dt_lam']} vs nosso {t['nosso_lam']} "
              f"({t['delta_dias']:+d}d)")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nrelatório JSON: {args.json}")

    if (args.fail_median_days is not None
            and d["median_days"] is not None
            and abs(d["median_days"]) > args.fail_median_days):
        print(f"\nGATE FALHOU: |mediana| {abs(d['median_days'])}d > "
              f"{args.fail_median_days}d")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
