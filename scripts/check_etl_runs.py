"""Audit dos mirrors ERP NELO — preenchimento das tabelas e frescura dos runs.

Dois modos:

* ``--mode fullness`` (default): conta linhas por tabela (legacy Q.68.A).
* ``--mode freshness``: lê ``core.etl_run`` e mostra, por mirror
  (``source``), quando correu pela última vez, com que estado, quantas
  linhas mexeu e há quantas horas — o sinal que faltava para saber se os
  mirrors continuam vivos em produção.

O modo ``freshness`` aceita ``--stale-hours N`` (default 24): o script
sai com exit code ``1`` se qualquer mirror tiver idade > N horas. Útil
para um job de CI que dispara alarme quando o sync nocturno morre.

``--json`` emite a saída como JSON em vez de texto — usado pelo teste
de integração ``tests/adapters/nelo/test_etl_freshness.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from src.shared.database import async_session_factory


# Mirrors que registamos via `register_mirror(...)` em
# `src.adapters.nelo.etl.sync._load_mirror_modules`. Mantido como hint
# para o relatório identificar mirrors em falta (registados mas nunca
# correram). NÃO usado para filtrar — qualquer `source` em
# `core.etl_run` é exibido tal como está.
_EXPECTED_MIRRORS = (
    "master",
    "molds",
    "skills",
    "quality",
    "time_mining",
    "stock",
    "calendar",
    "inventory_ledger",
    "material_master",
    "purchase_orders",
)


# ─── Modo: fullness ──────────────────────────────────────────────────


async def _run_fullness() -> dict[str, Any]:
    """Conta linhas em cada tabela de utilizador (não-system) e separa
    cheias de vazias. Replica o comportamento Q.68.A original.
    """
    async with async_session_factory() as s:
        r = await s.execute(text(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_type='BASE TABLE' "
            "AND table_schema NOT IN ('pg_catalog','information_schema','sandbox','public') "
            "ORDER BY table_schema, table_name"
        ))
        tables = list(r)
        cheias: list[tuple[str, str, int]] = []
        vazias: list[tuple[str, str]] = []
        for sch, t in tables:
            try:
                c = (await s.execute(text(f'SELECT COUNT(*) FROM "{sch}"."{t}"'))).scalar()
            except Exception:  # pragma: no cover - defensive
                continue
            if c and c > 0:
                cheias.append((sch, t, int(c)))
            else:
                vazias.append((sch, t))
    return {
        "cheias": [{"schema": s, "table": t, "rows": n} for s, t, n in cheias],
        "vazias": [{"schema": s, "table": t} for s, t in vazias],
    }


def _print_fullness(report: dict[str, Any]) -> None:
    cheias = report["cheias"]
    vazias = report["vazias"]
    print(f"CHEIAS: {len(cheias)}")
    for row in cheias:
        print(f"  {row['schema']}.{row['table']:<40} {row['rows']}")
    print(f"\nVAZIAS: {len(vazias)}")
    for row in vazias:
        print(f"  {row['schema']}.{row['table']}")


# ─── Modo: freshness ─────────────────────────────────────────────────


def _utcnow() -> datetime:
    """Now em UTC tz-aware — combina com `core.etl_run.started_at`."""
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """``core.etl_run.started_at`` é tz-aware (DateTime(timezone=True)),
    mas algumas migrações antigas escreveram valores naïve. Normaliza
    para UTC antes de fazer aritmética.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _run_freshness() -> list[dict[str, Any]]:
    """Lê o último run por ``source`` em ``core.etl_run``.

    SQL puro (não ORM) porque o script tem de correr standalone sem
    importar todos os modelos. Faz um ``DISTINCT ON`` por source, com
    ``ORDER BY started_at DESC`` — Postgres-only mas o projecto é
    Postgres-only.
    """
    sql = text(
        "SELECT DISTINCT ON (source) "
        "  source, status, started_at, finished_at, "
        "  rows_inserted, rows_updated, rows_read, rows_skipped, error "
        "FROM core.etl_run "
        "ORDER BY source, started_at DESC"
    )
    async with async_session_factory() as s:
        rows = (await s.execute(sql)).all()

    now = _utcnow()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        started = _ensure_aware(row.started_at)
        finished = _ensure_aware(row.finished_at)
        idade_horas = None
        if started is not None:
            idade_horas = round((now - started).total_seconds() / 3600.0, 2)
        out.append({
            "source": row.source,
            "last_status": row.status,
            "last_run_at": started.isoformat() if started else None,
            "last_finished_at": finished.isoformat() if finished else None,
            "rows_inserted": int(row.rows_inserted or 0),
            "rows_updated": int(row.rows_updated or 0),
            "rows_read": int(row.rows_read or 0),
            "rows_skipped": int(row.rows_skipped or 0),
            "idade_horas": idade_horas,
            "error": row.error,
        })
        seen.add(row.source)

    # Mirrors que esperamos mas nunca correram — marcador explícito.
    for name in _EXPECTED_MIRRORS:
        if name not in seen:
            out.append({
                "source": name,
                "last_status": "never_ran",
                "last_run_at": None,
                "last_finished_at": None,
                "rows_inserted": 0,
                "rows_updated": 0,
                "rows_read": 0,
                "rows_skipped": 0,
                "idade_horas": None,
                "error": None,
            })

    out.sort(key=lambda r: r["source"])
    return out


def _print_freshness(rows: list[dict[str, Any]], stale_hours: float) -> None:
    print(f"{'SOURCE':<22} {'STATUS':<10} {'IDADE_H':>8} {'INS+UPD':>10}  LAST_RUN_AT")
    print("-" * 78)
    for r in rows:
        idade = r["idade_horas"]
        idade_str = f"{idade:>8.2f}" if idade is not None else f"{'—':>8}"
        ins_upd = (r["rows_inserted"] or 0) + (r["rows_updated"] or 0)
        last = r["last_run_at"] or "—"
        marker = ""
        if r["last_status"] == "never_ran":
            marker = "  [NUNCA CORREU]"
        elif idade is not None and idade > stale_hours:
            marker = f"  [STALE > {stale_hours}h]"
        elif r["last_status"] not in ("ok", "running"):
            marker = "  [FAIL]"
        print(
            f"{r['source']:<22} {r['last_status']:<10} "
            f"{idade_str} {ins_upd:>10}  {last}{marker}"
        )


def _is_stale(rows: list[dict[str, Any]], stale_hours: float) -> list[str]:
    """Retorna a lista de mirrors com idade > stale_hours ou nunca correu."""
    stale: list[str] = []
    for r in rows:
        if r["last_status"] == "never_ran":
            stale.append(r["source"])
            continue
        idade = r["idade_horas"]
        if idade is not None and idade > stale_hours:
            stale.append(r["source"])
    return stale


# ─── CLI ─────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode",
        choices=["fullness", "freshness"],
        default="fullness",
        help="fullness: conta linhas por tabela; freshness: audita core.etl_run.",
    )
    p.add_argument(
        "--stale-hours",
        type=float,
        default=24.0,
        help="(freshness) exit 1 se algum mirror tem idade > N horas. Default 24.",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emite o relatório em JSON (para integração CI).",
    )
    return p


async def _amain(args: argparse.Namespace) -> int:
    if args.mode == "fullness":
        report = await _run_fullness()
        if args.as_json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            _print_fullness(report)
        return 0

    # freshness
    rows = await _run_freshness()
    stale = _is_stale(rows, args.stale_hours)
    if args.as_json:
        print(json.dumps(
            {
                "stale_hours_threshold": args.stale_hours,
                "stale_mirrors": stale,
                "mirrors": rows,
            },
            indent=2,
            ensure_ascii=False,
        ))
    else:
        _print_freshness(rows, args.stale_hours)
        if stale:
            print(f"\nMIRRORS STALE (idade > {args.stale_hours}h ou never_ran): {stale}")
        else:
            print(f"\nTodos os mirrors dentro de {args.stale_hours}h.")
    return 1 if stale else 0


def main() -> int:
    args = _build_parser().parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
