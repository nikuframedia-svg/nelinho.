"""Q.140.B — SectorPreferenceService: nível por (pessoa × sector) + ranking.

O Luis quer um **nível independente por sector** para cada colaborador (uma
pessoa multi-funcional é 3.0 na Pintura e 1.5 na Laminagem) e uma **ordem de
preferência por sector** (quem é melhor em cada área).

Fonte dos sinais: **`factory_raw` (ERP vivo)** — `offp_eq ⋈ of_fp ⋈
fases_producao` — porque é onde estão os dados reais (a camada
`factory_curated.*` e `phase_operator_affinity` estão vazias neste deployment).
Por (worker E_ID, fase): nº de ops, defeitos (`OFFP_RETURN` = devolvido para
retrabalho) e recência (`OFFP_DATAFIM`). Agregado por **grupo de área** via
`area_group_for_phase`, o score Laplace vira nível 1.0–3.0 com `quality_to_level`
(mesma escala da UI). NUNCA lê `OFFP_COEFICIENTE_X` (€ — CoeficienteX).

Precedência do nível efectivo por sector:
    override manual (PreferenceRule field=sector_level) > derivado (histórico
    real) > semente ERP `E_NIVEL` (só quando ∈ {1,2,3}) > nada (None → "—").

Tudo read-only. O serviço expõe:
* `per_employee_sector_levels(employee_id)` — os 7 sectores de uma pessoa.
* `sector_ranking(area_group, limit)` — vista inversa: colaboradores aptos ao
  sector, ordenados por (effective_level, ops, recência).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee
from src.workforce.employee_extras_service import SMOOTHING_ALPHA, SMOOTHING_BETA
from src.workforce.levels import (
    AREA_GROUPS,
    area_group_for_phase,
    clamp_level,
    public_level_from_cpo,
    quality_to_level,
)

logger = logging.getLogger(__name__)

# Convenção pública (3=melhor) — devolvida nos payloads para a UI não adivinhar.
LEVEL_SCALE = {"min": 1.0, "max": 3.0, "best": 3.0, "step": 0.5, "convention": "3=melhor, 1=pior"}

# Campo do predicate da PreferenceRule(workforce_override) que guarda o override
# de nível por sector (Q.140.D escreve-o; aqui só lemos).
_SECTOR_LEVEL_FIELD = "sector_level"


@dataclass
class _PhaseStat:
    """Agregado bruto por (worker, fase) vindo do factory_raw."""

    fase_id: str
    fase_nome: Optional[str]
    ops: int
    defects: int
    last_fim: Optional[datetime]


@dataclass
class SectorLevel:
    """Nível de UM colaborador em UM sector (grupo de área)."""

    area_group: str
    apt: bool
    derived_level: Optional[float]      # do histórico real (None = sem histórico)
    erp_level: Optional[float]          # semente E_NIVEL (None quando 0/ausente)
    override_level: Optional[float]     # override manual (None = nenhum)
    effective_level: Optional[float]    # override > derived > erp_seed
    source: str                         # 'override' | 'derived' | 'erp_seed' | 'none'
    ops_total: int
    defects: int
    recency_days: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area_group": self.area_group,
            "apt": self.apt,
            "derived_level": self.derived_level,
            "erp_level": self.erp_level,
            "override_level": self.override_level,
            "effective_level": self.effective_level,
            "source": self.source,
            "ops_total": self.ops_total,
            "defects": self.defects,
            "recency_days": self.recency_days,
        }


def _laplace_level(ops: int, defects: int) -> Optional[float]:
    """Score Laplace [1,10] → nível [1.0,3.0]. None quando não há ops."""
    if ops <= 0 and defects <= 0:
        return None
    rate = (defects + SMOOTHING_ALPHA) / (ops + SMOOTHING_BETA)
    score = max(1.0, min(10.0, 10.0 - 10.0 * rate))
    return quality_to_level(score)


def _recency_days(last_fim: Any, today: Optional[date] = None) -> Optional[int]:
    """Dias desde a última op. `last_fim` pode ser datetime, date ou str ISO
    (no factory_raw, OFFP_DATAFIM é TEXT tipo '2024-09-19T08:16:00')."""
    if not last_fim:
        return None
    ref = today or datetime.now().date()
    if isinstance(last_fim, str):
        try:
            d = datetime.fromisoformat(last_fim.strip()).date()
        except ValueError:
            return None
    elif isinstance(last_fim, datetime):
        d = last_fim.date()
    elif isinstance(last_fim, date):
        d = last_fim
    else:  # pragma: no cover — tipo inesperado
        return None
    return max(0, (ref - d).days)


def build_sector_levels(
    phase_stats: List[_PhaseStat],
    *,
    erp_level: Optional[float] = None,
    overrides: Optional[Dict[str, float]] = None,
    today: Optional[date] = None,
) -> List[SectorLevel]:
    """Pure: agrega `phase_stats` (de UM worker) nos 7 grupos de área.

    `overrides` mapeia area_group → nível manual. Devolve sempre os 7 grupos
    (apt=False quando sem histórico nesse grupo). Precedência do effective:
    override > derived > erp_seed > None.
    """
    overrides = overrides or {}
    by_area: Dict[str, Dict[str, Any]] = {
        g: {"ops": 0, "defects": 0, "last_fim": None} for g in AREA_GROUPS
    }
    for st in phase_stats:
        group = area_group_for_phase(st.fase_nome, st.fase_id)
        agg = by_area[group]
        agg["ops"] += int(st.ops or 0)
        agg["defects"] += int(st.defects or 0)
        if st.last_fim is not None and (
            agg["last_fim"] is None or st.last_fim > agg["last_fim"]
        ):
            agg["last_fim"] = st.last_fim

    out: List[SectorLevel] = []
    for group in AREA_GROUPS:
        agg = by_area[group]
        ops = agg["ops"]
        defects = agg["defects"]
        derived = _laplace_level(ops, defects)
        override = overrides.get(group)
        override = clamp_level(override) if override is not None else None
        # Precedência: override > derived > erp_seed.
        if override is not None:
            effective, source = override, "override"
        elif derived is not None:
            effective, source = derived, "derived"
        elif erp_level is not None:
            effective, source = erp_level, "erp_seed"
        else:
            effective, source = None, "none"
        out.append(
            SectorLevel(
                area_group=group,
                apt=ops > 0,
                derived_level=derived,
                erp_level=erp_level,
                override_level=override,
                effective_level=effective,
                source=source,
                ops_total=ops,
                defects=defects,
                recency_days=_recency_days(agg["last_fim"], today),
            )
        )
    return out


class SectorPreferenceService:
    """Níveis por sector + ranking por sector. Read-only."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ── Fetch helpers (SQL isolado — testes fazem monkeypatch) ──────────────

    async def _fetch_phase_history(
        self, employee_code: Optional[str] = None,
    ) -> Dict[str, List[_PhaseStat]]:
        """Histórico real por (worker E_ID → employee_code, fase) do factory_raw.

        ``employee_code`` filtra a um worker; None = todos. Devolve
        {employee_code: [_PhaseStat, ...]}. Best-effort: tabela ausente → {}.
        """
        if self.session is None:
            return {}
        where_worker = 'AND eq."OFFPEQ_E_ID"::text = :code' if employee_code else ""
        sql = text(
            f"""
            SELECT eq."OFFPEQ_E_ID"::text       AS worker_code,
                   f."FP_ID"::text              AS fase_id,
                   f."FP_NOME"                  AS fase_nome,
                   COUNT(*)                     AS ops,
                   COUNT(*) FILTER (WHERE o."OFFP_RETURN") AS defects,
                   MAX(o."OFFP_DATAFIM")        AS last_fim
            FROM factory_raw.offp_eq eq
            JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
            JOIN factory_raw.fases_producao f ON f."FP_ID" = o."OFFP_FP_ID"
            WHERE eq."OFFPEQ_E_ID" IS NOT NULL
              {where_worker}
            GROUP BY eq."OFFPEQ_E_ID", f."FP_ID", f."FP_NOME"
            """
        )
        params = {"code": employee_code} if employee_code else {}
        try:
            rows = (await self.session.execute(sql, params)).mappings().all()
        except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente/dev
            logger.warning("sector history fetch failed: %s", exc)
            return {}
        out: Dict[str, List[_PhaseStat]] = {}
        for r in rows:
            out.setdefault(r["worker_code"], []).append(
                _PhaseStat(
                    fase_id=str(r["fase_id"]),
                    fase_nome=r["fase_nome"],
                    ops=int(r["ops"] or 0),
                    defects=int(r["defects"] or 0),
                    last_fim=r["last_fim"],
                )
            )
        return out

    async def _fetch_erp_levels(self) -> Dict[str, float]:
        """Semente E_NIVEL por employee_code (factory_raw.entidade).

        Só níveis ∈ {1,2,3} contam (mapeados p/ escala invertida). E_NIVEL=0
        (o caso comum no espelho actual) → ausente, sem semente falsa.
        """
        if self.session is None:
            return {}
        sql = text(
            'SELECT "E_ID"::text AS code, "E_NIVEL" AS nivel '
            'FROM factory_raw.entidade WHERE "E_NIVEL" IN (1,2,3)'
        )
        try:
            rows = (await self.session.execute(sql)).mappings().all()
        except SQLAlchemyError as exc:  # pragma: no cover
            logger.warning("erp levels fetch failed: %s", exc)
            return {}
        return {r["code"]: public_level_from_cpo(int(r["nivel"])) for r in rows}

    async def _fetch_overrides(self) -> Dict[Tuple[str, str], float]:
        """Overrides manuais por (employee_id_str, area_group) das PreferenceRule.

        Lê PreferenceRule(type=workforce_override) cujo predicate.field ==
        'sector_level'. Best-effort: schema ausente → {}.
        """
        if self.session is None:
            return {}
        try:
            from src.governance.models import PreferenceRule, PreferenceRuleType

            stmt = select(PreferenceRule).where(
                PreferenceRule.tenant_id == self.tenant_id,
                PreferenceRule.type == PreferenceRuleType.WORKFORCE_OVERRIDE.value,
                PreferenceRule.predicate.contains({"field": _SECTOR_LEVEL_FIELD}),
            )
            rules = (await self.session.execute(stmt)).scalars().all()
        except (SQLAlchemyError, ImportError) as exc:  # pragma: no cover
            logger.warning("sector overrides fetch failed: %s", exc)
            return {}
        out: Dict[Tuple[str, str], float] = {}
        for rule in rules:
            pred = rule.predicate or {}
            emp = pred.get("employee_id")
            area = pred.get("area_group")
            nivel = pred.get("nivel")
            if emp and area and nivel is not None:
                out[(str(emp), str(area))] = clamp_level(float(nivel))
        return out

    async def _fetch_employee_dim(
        self, codes: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[UUID, str]]:
        """employee_code → (id UUID, employee_name) de core.employees (tenant).

        Só workers com linha em core.employees são editáveis (têm UUID p/ o
        override). `codes` opcional restringe a query.
        """
        if self.session is None:
            return {}
        stmt = select(
            Employee.employee_code, Employee.id, Employee.employee_name
        ).where(Employee.tenant_id == self.tenant_id)
        if codes:
            stmt = stmt.where(Employee.employee_code.in_(codes))
        try:
            rows = (await self.session.execute(stmt)).all()
        except SQLAlchemyError as exc:  # pragma: no cover
            logger.warning("employee dim fetch failed: %s", exc)
            return {}
        return {r[0]: (r[1], r[2]) for r in rows if r[0]}

    # ── Public API ──────────────────────────────────────────────────────────

    async def per_employee_sector_levels(
        self, employee_id: UUID,
    ) -> Dict[str, Any]:
        """Os 7 sectores de um colaborador, com nível efectivo independente."""
        dim_stmt = select(
            Employee.employee_code, Employee.employee_name
        ).where(Employee.id == employee_id, Employee.tenant_id == self.tenant_id)
        row = (await self.session.execute(dim_stmt)).first()
        code = row[0] if row else None
        name = row[1] if row else None

        history = await self._fetch_phase_history(code) if code else {}
        stats = history.get(code, []) if code else []
        erp_levels = await self._fetch_erp_levels()
        overrides_all = await self._fetch_overrides()
        overrides = {
            area: lvl
            for (emp, area), lvl in overrides_all.items()
            if emp == str(employee_id)
        }

        levels = build_sector_levels(
            stats,
            erp_level=erp_levels.get(code) if code else None,
            overrides=overrides,
        )
        return {
            "employee_id": str(employee_id),
            "employee_name": name,
            "employee_code": code,
            "level_scale": LEVEL_SCALE,
            "sectors": [lvl.to_dict() for lvl in levels],
        }

    async def sector_ranking(
        self, area_group: str, *, limit: int = 100,
    ) -> Dict[str, Any]:
        """Vista inversa: colaboradores APTOS ao sector, ordenados por preferência.

        Apto = tem ≥1 op histórica numa fase do grupo (axioma 5 — nunca alarga
        além de quem já trabalhou no sector). Ordem determinística:
        (effective_level desc, ops desc, recency asc, employee_id asc).
        """
        history = await self._fetch_phase_history()
        erp_levels = await self._fetch_erp_levels()
        overrides_all = await self._fetch_overrides()
        dim = await self._fetch_employee_dim(list(history.keys()) or None)

        ranking: List[Dict[str, Any]] = []
        for code, stats in history.items():
            ident = dim.get(code)
            if ident is None:
                # Sem linha em core.employees → não editável (sem UUID). Salta.
                continue
            emp_id, emp_name = ident
            emp_overrides = {
                a: lvl for (e, a), lvl in overrides_all.items() if e == str(emp_id)
            }
            levels = build_sector_levels(
                stats, erp_level=erp_levels.get(code), overrides=emp_overrides,
            )
            sl = next((x for x in levels if x.area_group == area_group), None)
            if sl is None or not sl.apt:
                continue
            ranking.append(
                {
                    "employee_id": str(emp_id),
                    "employee_name": emp_name,
                    "employee_code": code,
                    "effective_level": sl.effective_level,
                    "derived_level": sl.derived_level,
                    "erp_level": sl.erp_level,
                    "override_level": sl.override_level,
                    "source": sl.source,
                    "ops_total": sl.ops_total,
                    "defects": sl.defects,
                    "recency_days": sl.recency_days,
                }
            )

        ranking.sort(
            key=lambda r: (
                -(r["effective_level"] if r["effective_level"] is not None else -1.0),
                -r["ops_total"],
                r["recency_days"] if r["recency_days"] is not None else 10**9,
                r["employee_id"],
            )
        )
        for i, r in enumerate(ranking[:limit], start=1):
            r["rank"] = i
        return {
            "area_group": area_group,
            "level_scale": LEVEL_SCALE,
            "ranking": ranking[:limit],
            "total": len(ranking),
        }
