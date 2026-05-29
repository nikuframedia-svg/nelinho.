"""Q.117.D — captura + leitura da série histórica de KPIs.

A página LLM › KPIs mostra o valor actual (calculado live em
``src/profit/api/kpis.py``). Esta camada acrescenta a tendência:

* :func:`capture_kpi_snapshot` — escreve um ponto por KPI para um dia
  (idempotente: re-correr no mesmo dia faz update, não duplica). Chamado
  pelo job diário ``_kpi_snapshot_job``.
* :func:`get_kpi_history` — devolve os pontos dos últimos ``days`` dias
  para o gráfico. Validado contra a whitelist (mesma da tab no frontend).

ZERO MOCKS também no backend: quando um KPI não tem dados num dia
gravamos ``value=None`` (NULL) — o gráfico salta o ponto, nunca inventa.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select

from src.profit.models.kpi_snapshot import KpiSnapshot

# Whitelist (nome → unidade) — espelha KPI_META no frontend (KPIsTab.tsx).
SNAPSHOT_KPIS: Dict[str, str] = {
    "quality_fpy": "%",
    "rework_rate": "%",
    "orders_total": "",
    "orders_in_progress": "",
    "orders_completed": "",
}


async def capture_kpi_snapshot(
    session,
    tenant_id: UUID,
    *,
    on_date: Optional[date] = None,
    kpis: Optional[Dict[str, Any]] = None,
) -> int:
    """Grava (ou actualiza) um ponto por KPI da whitelist para ``on_date``.

    ``kpis`` permite injectar o resultado de ``calculate_kpis`` nos testes;
    em produção é calculado aqui. Devolve o número de KPIs persistidos.
    """
    if on_date is None:
        on_date = datetime.now(timezone.utc).date()
    if kpis is None:
        from src.profit.api.kpis import calculate_kpis

        kpis = await calculate_kpis(session, tenant_id)

    written = 0
    for name, unit in SNAPSHOT_KPIS.items():
        metric = kpis.get(name)
        raw = getattr(metric, "value", None) if metric is not None else None
        value = float(raw) if raw is not None else None

        existing = (
            await session.execute(
                select(KpiSnapshot).where(
                    KpiSnapshot.tenant_id == tenant_id,
                    KpiSnapshot.kpi_name == name,
                    KpiSnapshot.captured_date == on_date,
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            existing.value = value
            existing.unit = unit
        else:
            session.add(
                KpiSnapshot(
                    tenant_id=tenant_id,
                    kpi_name=name,
                    captured_date=on_date,
                    value=value,
                    unit=unit,
                )
            )
        written += 1

    await session.commit()
    return written


async def get_kpi_history(
    session,
    tenant_id: UUID,
    kpi_name: str,
    *,
    days: int = 30,
) -> Optional[Dict[str, Any]]:
    """Pontos dos últimos ``days`` dias para um KPI da whitelist.

    Devolve ``None`` se ``kpi_name`` não está na whitelist (caller → 404).
    Pontos com ``value=None`` são incluídos (o frontend salta-os) para que
    a tendência mostre honestamente os dias sem dados.
    """
    if kpi_name not in SNAPSHOT_KPIS:
        return None

    days = max(1, min(int(days), 365))
    since = datetime.now(timezone.utc).date() - timedelta(days=days)

    rows = (
        await session.execute(
            select(KpiSnapshot)
            .where(
                KpiSnapshot.tenant_id == tenant_id,
                KpiSnapshot.kpi_name == kpi_name,
                KpiSnapshot.captured_date >= since,
            )
            .order_by(KpiSnapshot.captured_date)
        )
    ).scalars().all()

    points = [
        {"date": r.captured_date.isoformat(), "value": r.value}
        for r in rows
    ]
    return {
        "name": kpi_name,
        "unit": SNAPSHOT_KPIS[kpi_name],
        "days": days,
        "points": points,
    }
