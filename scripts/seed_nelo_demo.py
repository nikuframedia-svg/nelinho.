"""seed_nelo_demo.py — Q.18.ZIP.S

Insere dados realistas estilo NELO directamente nas tabelas reais para o
frontend portado parecer com `design/nelo-zip/src/data.jsx`.

Idempotente: usa UPSERT por business key (legacy_id, employee_code,
mold_code, transport_date+code, title). Safe to re-run.

Run:
    PYTHONPATH=. ./.venv/Scripts/python.exe scripts/seed_nelo_demo.py

Verifica:
    curl http://127.0.0.1:8001/v1/plan/orders/active | jq length        # 12
    curl http://127.0.0.1:8001/v1/plan/molds/health-report | jq length  # 4
    curl http://127.0.0.1:8001/v1/decisions/?status_filter=PENDING_APPROVAL | jq .total  # 3
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee, EmploymentStatus, EmploymentType
from src.plan.models.mold import Mold, MoldHealth
from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.models.transport import TransportBatch
from src.quality.models.rework import ReworkEntry
from src.shared.database import async_session_factory
from src.shared.models.governance import DecisionStatus, SharedDecisionRun

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# ─── Fases canónicas (matching data.jsx PHASES) ─────────────────────────────
PHASE_BY_ID = {
    1: "Prep. Molde",
    2: "Pintura gelcoat",
    3: "Laminagem",
    4: "Cura",
    5: "Desmolde",
    6: "Corte",
    7: "Colagem Peças",
    8: "Pintura Acabam.",
    9: "Lixagem água",
    10: "Montagem",
    11: "CQ Final",
    12: "Armazém",
}

# ─── Boats (data.jsx BOATS) ────────────────────────────────────────────────
BOATS = [
    # legacy_id, model, short, phase_id, transport
    (4271, "K1 Vanquish L SCS", "K1", 3, date(2026, 5, 16)),
    (4272, "K1 Quattro L SCS", "K1", 8, date(2026, 5, 16)),
    (4273, "K1 Vanquish M", "K1", 10, date(2026, 5, 16)),
    (4274, "K1 Vanquish L", "K1", 3, date(2026, 5, 20)),
    (4275, "K1 Vanquish M", "K1", 9, date(2026, 5, 16)),
    (5103, "K2 Hybrid", "K2", 7, date(2026, 5, 20)),
    (5104, "K2 Pro", "K2", 3, date(2026, 5, 22)),
    (5105, "K2 Sprint", "K2", 8, date(2026, 5, 22)),
    (6001, "K4 Multisport", "K4", 4, date(2026, 5, 22)),
    (6002, "K4 Cluster", "K4", 8, date(2026, 5, 16)),
    (6003, "K4 Multisport", "K4", 5, date(2026, 5, 16)),
    (6004, "K4 Cluster", "K4", 7, date(2026, 5, 22)),
]

# ─── Employees (data.jsx WORKERS) ──────────────────────────────────────────
EMPLOYEES = [
    # code, name, hire_date, main skill
    ("W01", "Paulo Gomes Faria", date(2010, 3, 15), "Laminagem"),
    ("W02", "Maria Silva", date(2012, 6, 1), "Laminagem"),
    ("W03", "João Costa", date(2013, 9, 10), "Colagem Peças"),
    ("W04", "Ana Reis", date(2025, 6, 20), "Pintura Acabamento"),
    ("W05", "António Pereira", date(2026, 1, 5), "Laminagem"),
    ("W06", "Carlos Santos", date(2011, 4, 12), "Pintura Acabamento"),
    ("W07", "Helena Marques", date(2014, 11, 3), "Lixagem água"),
    ("W08", "Tiago Lopes", date(2015, 2, 18), "Montagem"),
]

# ─── Molds (data.jsx MOLDS) ────────────────────────────────────────────────
MOLDS = [
    # code, model, name, uses, max, err_week, err_normal, status
    ("M-K1-03", "K1", "K1 7 ML (03)", 847, 800, 0.23, 0.12, "red"),
    ("M-K2-02", "K2", "K2 7 L (02)", 642, 800, 0.14, 0.10, "yellow"),
    ("M-K4-01", "K4", "K4 7 L (01)", 312, 800, 0.08, 0.09, "green"),
    ("M-K1-02", "K1", "K1 7 ML (02)", 521, 800, 0.09, 0.10, "green"),
]

# ─── Recent errors (data.jsx RECENT_ERRORS) ────────────────────────────────
RECENT_ERRORS = [
    # of_id, error_code, description, phase, employee_code, severity, cost
    ("4270", "INTERIOR_ENRUGADO", "Interior enrugado", "Laminagem", "W01", "high", 250.0),
    ("5098", "PINTURA_FIOS", "Pintura com fios", "Pintura Acabam.", "W04", "medium", 120.0),
    ("4268", "BOLHA", "Bolha 3 mm pavilhão", "Laminagem", "W05", "medium", 180.0),
    ("5999", "COLA_INSUF", "Cola insuficiente", "Colagem Peças", "W03", "low", 60.0),
]

# ─── Shipments (data.jsx SHIPMENTS) ────────────────────────────────────────
SHIPMENTS = [
    # date, code, destination, capacity, priority
    (date(2026, 5, 16), "SHP-2026-05-16", "Fed. Francesa + Fed. Portuguesa", 50, 100),
    (date(2026, 5, 20), "SHP-2026-05-20", "Cliente Privado DE", 50, 100),
    (date(2026, 5, 22), "SHP-2026-05-22", "Fed. Italiana + Equipa Sueca", 50, 100),
]

# ─── Suggestions (data.jsx SUGGESTIONS) ────────────────────────────────────
SUGGESTIONS = [
    {
        "title": "Mover 3 barcos K2 de terça para quarta",
        "action_type": "RESCHEDULE_BATCH",
        "target": "K2-batch-tue",
        "before_state": {
            "boats": ["5103", "5104", "5105"],
            "scheduled_day": "2026-05-19",
        },
        "after_state": {
            "boats": ["5103", "5104", "5105"],
            "scheduled_day": "2026-05-20",
        },
        "sandbox_result": {
            "priority": "critical",
            "why": "Molde K2 7 L (02) em manutenção preventiva terça-feira "
                   "(847 usos, atinge ciclo de 800). Sem molde, 3 barcos ficam parados.",
            "if_accept": [
                "Barcos atrasam 1 dia (entregues quarta às 18h)",
                "Expedição sexta sem impacto — margem de 2 dias",
                "Throughput terça: −€7.200, quarta: +€7.200 (zero impacto líquido)",
            ],
            "if_reject": [
                "3 barcos parados terça-feira inteira (sem molde)",
                "2 laminadores idle 8h — custo €240 em mão-de-obra parada",
                "Molde força paragem na mesma terça à tarde — barcos acabam quarta",
            ],
            "alternative": {
                "label": "Usar molde K2 7 L (01) — versão de 2 poços",
                "detail": "+2h por barco (4 poços vs 2), sem atraso de "
                          "calendário. Custo: ~€80 em horas extra.",
            },
            "confidence": 91,
            "source": "CPO Scheduler · regra MOLD_PREVENTIVE",
        },
    },
    {
        "title": "Trocar Ana Reis por Carlos Santos no K1 #4272 Pintura",
        "action_type": "REASSIGN_OPERATOR",
        "target": "boat-4272",
        "before_state": {"order_id": "4272", "operator_id": "W04"},
        "after_state": {"order_id": "4272", "operator_id": "W06"},
        "sandbox_result": {
            "priority": "high",
            "why": "Ana tem score 6.2 em Pintura Acabamento (taxa erro 18% "
                   "nos últimos 90 dias). Carlos tem score 8.1 (taxa 4%). "
                   "#4272 é prioridade alta — Federação Portuguesa, expedição sexta.",
            "if_accept": [
                "Risco de erro desce de 18% para 4%",
                "Tempo estimado: +30min (Carlos é mais metódico)",
                "Ana fica livre 09:00–13:00 — pode ir para Lixagem (3 barcos em fila)",
            ],
            "if_reject": [
                "Risco de retrabalho sobe — 1 em 5 barcos K1 da Ana volta à Pintura",
                "Se #4272 vier para retrabalho, perde-se a expedição de sexta",
            ],
            "alternative": None,
            "confidence": 84,
            "source": "CPO Scheduler · skill matching",
        },
    },
    {
        "title": "Antecipar K1 #4271 para expedição de quinta",
        "action_type": "ADVANCE_SHIPMENT",
        "target": "boat-4271",
        "before_state": {"order_id": "4271", "transport_date": "2026-05-15"},
        "after_state": {"order_id": "4271", "transport_date": "2026-05-14"},
        "sandbox_result": {
            "priority": "medium",
            "why": "#4271 acaba quarta às 16h. Próxima expedição é sexta. "
                   "Há um camião de quinta com 4 lugares vazios para Federação Francesa.",
            "if_accept": [
                "Cliente FR recebe 1 dia mais cedo (boa relação comercial)",
                "Liberta espaço de armazém quinta-feira",
                "Custo: €0 (camião já agendado)",
            ],
            "if_reject": [
                "Sem impacto operacional — expedição sexta corre normal",
                "Barco fica 1 dia parado em armazém",
            ],
            "alternative": None,
            "confidence": 76,
            "source": "CPO Dispatcher · transport_optimizer",
        },
    },
]


async def upsert_employees(session: AsyncSession) -> dict[str, UUID]:
    """Insere/actualiza employees. Retorna {code: id}."""
    code_to_id: dict[str, UUID] = {}
    for code, name, hire, main_skill in EMPLOYEES:
        stmt = select(Employee).where(
            Employee.tenant_id == DEV_TENANT_ID,
            Employee.employee_code == code,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.employee_name = name
            existing.hire_date = hire
            existing.skill_codes = {"main": main_skill}
            existing.status = EmploymentStatus.ACTIVE
            code_to_id[code] = existing.id
        else:
            emp = Employee(
                tenant_id=DEV_TENANT_ID,
                employee_code=code,
                employee_name=name,
                status=EmploymentStatus.ACTIVE,
                employment_type=EmploymentType.FULL_TIME,
                hire_date=hire,
                department="Produção",
                job_title=main_skill,
                base_monthly_salary=Decimal("1850.00"),
                burden_rate=Decimal("0.32"),
                weekly_hours=Decimal("40"),
                skill_codes={"main": main_skill},
            )
            session.add(emp)
            await session.flush()
            code_to_id[code] = emp.id
    return code_to_id


async def upsert_orders(session: AsyncSession) -> None:
    today = date.today()
    for legacy_id, model, short, phase_id, transport in BOATS:
        stmt = select(ProductionOrder).where(
            ProductionOrder.tenant_id == DEV_TENANT_ID,
            ProductionOrder.legacy_id == legacy_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        phase_name = PHASE_BY_ID[phase_id]
        if existing:
            existing.product_name = model
            existing.product_type = short
            existing.current_phase_id = phase_id
            existing.current_phase_name = phase_name
            existing.transport_date = transport
            existing.status = OrderStatus.IN_PROGRESS
        else:
            session.add(ProductionOrder(
                tenant_id=DEV_TENANT_ID,
                legacy_id=legacy_id,
                product_id=legacy_id,
                product_name=model,
                product_type=short,
                current_phase_id=phase_id,
                current_phase_name=phase_name,
                created_date=today,
                transport_date=transport,
                status=OrderStatus.IN_PROGRESS,
            ))


async def upsert_molds(session: AsyncSession) -> None:
    """Mold + MoldHealth (latest snapshot)."""
    now = datetime.now(timezone.utc)
    for code, model_id, name, uses, max_uses, err_week, err_normal, status in MOLDS:
        # Mold
        stmt = select(Mold).where(
            Mold.tenant_id == DEV_TENANT_ID,
            Mold.mold_code == code,
        )
        mold = (await session.execute(stmt)).scalar_one_or_none()
        if mold is None:
            mold = Mold(
                tenant_id=DEV_TENANT_ID,
                mold_code=code,
                model_id=model_id,
                name=name,
                pocket_count=2,
                expected_life_cycles=max_uses,
                active=True,
            )
            session.add(mold)
            await session.flush()
        else:
            mold.model_id = model_id
            mold.name = name
            mold.expected_life_cycles = max_uses

        # MoldHealth — substitui sempre o snapshot mais recente.
        # Score deriva: cycles ratio + error rate. Aproximação simples.
        cycles_pct = uses / max_uses
        err_delta = err_week - err_normal
        score = max(0, min(100, int(100 * (1 - cycles_pct * 0.5 - err_delta * 2))))
        risk = (
            "red" if status == "red"
            else "yellow" if status == "yellow"
            else "green"
        )
        # Apaga health antigos (replace strategy)
        from sqlalchemy import delete
        await session.execute(
            delete(MoldHealth).where(MoldHealth.mold_id == mold.id)
        )
        session.add(MoldHealth(
            tenant_id=DEV_TENANT_ID,
            mold_id=mold.id,
            score_0_100=score,
            risk_category=risk,
            assessed_at=now,
            assessed_by="seed_nelo_demo",
            components={
                "cycles_used": uses,
                "cycles_max": max_uses,
                "cycles_pct": round(cycles_pct, 2),
                "err_rate_week": err_week,
                "err_rate_normal": err_normal,
                "err_delta": round(err_delta, 3),
            },
        ))


async def upsert_recent_errors(
    session: AsyncSession, code_to_id: dict[str, UUID]
) -> None:
    """4 ReworkEntries — recent errors page-quality.jsx."""
    now = datetime.now(timezone.utc)
    for of_id, error_code, desc_str, phase, emp_code, severity, cost in RECENT_ERRORS:
        # idempotência — chave (of_id, error_code, causer)
        causer_id = code_to_id.get(emp_code)
        stmt = select(ReworkEntry).where(
            ReworkEntry.tenant_id == DEV_TENANT_ID,
            ReworkEntry.of_id == of_id,
            ReworkEntry.error_code == error_code,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            session.add(ReworkEntry(
                tenant_id=DEV_TENANT_ID,
                of_id=of_id,
                error_code=error_code,
                error_description=desc_str,
                phase_id_causer=phase,
                phase_id_rework=phase,
                causer_employee_id=causer_id,
                detected_at=now,
                detected_by="seed_nelo_demo",
                cost_estimate_eur=Decimal(str(cost)),
                hours_lost=Decimal("0.5"),
                context={"severity": severity, "seeded": True},
            ))


async def upsert_shipments(session: AsyncSession) -> None:
    for transport_date, code, destination, cap, priority in SHIPMENTS:
        stmt = select(TransportBatch).where(
            TransportBatch.tenant_id == DEV_TENANT_ID,
            TransportBatch.code == code,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.transport_date = transport_date
            existing.destination = destination
            existing.truck_capacity_units = cap
            existing.priority = priority
            existing.status = "OPEN"
        else:
            session.add(TransportBatch(
                tenant_id=DEV_TENANT_ID,
                code=code,
                transport_date=transport_date,
                destination=destination,
                truck_capacity_units=cap,
                priority=priority,
                status="OPEN",
            ))


async def upsert_suggestions(session: AsyncSession) -> None:
    """3 SharedDecisionRuns com payload estilo zip SUGGESTIONS."""
    seed_user = DEV_TENANT_ID  # reutiliza tenant uuid como proxy de user
    for sug in SUGGESTIONS:
        # idempotência — busca por título
        stmt = select(SharedDecisionRun).where(
            SharedDecisionRun.tenant_id == DEV_TENANT_ID,
            SharedDecisionRun.title == sug["title"],
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.action_type = sug["action_type"]
            existing.target = sug["target"]
            existing.before_state = sug["before_state"]
            existing.after_state = sug["after_state"]
            existing.sandbox_result = sug["sandbox_result"]
            existing.status = DecisionStatus.PROPOSED.value
        else:
            session.add(SharedDecisionRun(
                tenant_id=DEV_TENANT_ID,
                title=sug["title"],
                action_type=sug["action_type"],
                target=sug["target"],
                status=DecisionStatus.PROPOSED.value,
                before_state=sug["before_state"],
                after_state=sug["after_state"],
                sandbox_result=sug["sandbox_result"],
                proposed_by=seed_user,
                proposed_at=datetime.now(timezone.utc),
            ))


async def main() -> None:
    print(">> seed_nelo_demo Q.18.ZIP.S — tenant", DEV_TENANT_ID)
    async with async_session_factory() as session:
        try:
            print("   [1/6] employees …", end=" ", flush=True)
            code_to_id = await upsert_employees(session)
            print(f"{len(code_to_id)} OK")

            print("   [2/6] production orders …", end=" ", flush=True)
            await upsert_orders(session)
            print(f"{len(BOATS)} OK")

            print("   [3/6] molds + health …", end=" ", flush=True)
            await upsert_molds(session)
            print(f"{len(MOLDS)} OK")

            print("   [4/6] rework / recent errors …", end=" ", flush=True)
            await upsert_recent_errors(session, code_to_id)
            print(f"{len(RECENT_ERRORS)} OK")

            print("   [5/6] transport batches …", end=" ", flush=True)
            await upsert_shipments(session)
            print(f"{len(SHIPMENTS)} OK")

            print("   [6/6] suggestions / decisions …", end=" ", flush=True)
            await upsert_suggestions(session)
            print(f"{len(SUGGESTIONS)} OK")

            await session.commit()
            print(">> commit ok. seed completo.")
        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
