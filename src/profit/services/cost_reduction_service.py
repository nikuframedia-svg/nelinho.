"""
ProdPlan ONE - Cost Reduction Suggestions Service (Sprint Q.54.H)
==================================================================

Powers `POST /v1/profit/cost-reduction-suggestions`. The Custos page
shows a "Poupado por sugestões" KPI (`ObjectivesService._pp1_impact`),
but until now nothing actually *generated* the suggestions — the KPI
could only ever read €0.

This service closes that loop:

1. **Analyse** the persisted `CostCalculation` rows (the same data the
   `cost-ledger` consolidates). For each product type (K1/K2/K4…) it
   builds a per-component baseline — the **median** cost of material,
   labour, machine, setup, overhead and scrap across that type's boats.

2. **Find outliers.** A boat whose component cost exceeds its type's
   median by a configurable factor (default ≥ 1.25×, and at least
   €50 of absolute slack) is an outlier — money is leaking on that
   boat / cost centre.

3. **Explain.** For each outlier a suggestion is built. Every number —
   the boat's cost, the type median, the € overspend — comes from the
   deterministic analysis. The LLM (Ollama, same pattern as
   `nl_translator.py`) only writes the human-readable PT-PT prose. If
   the LLM is offline the suggestion still ships with a deterministic
   fallback sentence — the numbers are never invented.

4. **Action.** A suggestion can be promoted to a `DecisionRun` via
   `create_decision_from_suggestion`. It lands in the governance Inbox
   with `requires_human_approval` semantics (the `cost_reduction`
   policy keeps `requires_approval=True`); the `expected_impact`
   carries `eur_saved`, so once executed it counts towards the PP1
   figure `ObjectivesService._pp1_impact` already reads.

CoeficienteX is DINHEIRO but is a *different* figure — it is not a COGS
component and is deliberately absent here, exactly as in the cost-ledger.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.models.order import ProductionOrder
from src.profit.models.cost import CostCalculation

logger = logging.getLogger(__name__)

# The COGS components we hunt for outliers in — same six as the ledger.
_COST_COMPONENTS = (
    "material",
    "labor",
    "machine",
    "setup",
    "overhead",
    "scrap",
)

# Human-friendly PT-PT label per component, for prompts + fallback text.
_COMPONENT_LABEL = {
    "material": "material",
    "labor": "mão de obra",
    "machine": "máquina",
    "setup": "preparação (setup)",
    "overhead": "estrutura (overhead)",
    "scrap": "desperdício",
}

# An outlier must exceed the type median by this factor…
_OUTLIER_FACTOR = Decimal("1.25")
# …and overspend at least this many euros in absolute terms (kills noise
# on tiny cost centres where 1.25× is only a couple of euros).
_MIN_ABS_SLACK_EUR = Decimal("50")
# A type needs this many calculated boats before a median is meaningful.
_MIN_SAMPLE = 3

# Governance decision_type for a promoted suggestion. Has no entry in
# DEFAULT_POLICIES → GovernanceService falls back to the L2 default
# policy (requires_approval=True) — so it lands in the human Inbox.
COST_REDUCTION_DECISION_TYPE = "cost_reduction"


@dataclass
class _Outlier:
    """One deterministic over-spend finding before the LLM writes prose."""

    order_id: str
    product_type: str
    product_name: Optional[str]
    component: str
    boat_cost: Decimal
    baseline_cost: Decimal
    sample_size: int

    @property
    def overspend_eur(self) -> Decimal:
        return self.boat_cost - self.baseline_cost

    @property
    def overspend_ratio(self) -> float:
        if self.baseline_cost <= 0:
            return 0.0
        return float(
            (self.boat_cost / self.baseline_cost).quantize(Decimal("0.01"))
        )


@dataclass
class _Bucket:
    """Per-(product_type, component) cost samples for the baseline."""

    samples: list[Decimal] = field(default_factory=list)


class CostReductionService:
    """Turns the cost ledger into actionable € reduction suggestions."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── public API ────────────────────────────────────────────────────────

    async def suggestions(
        self,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 20,
        llm_client: Any = None,
    ) -> dict[str, Any]:
        """Build cost-reduction suggestions from the persisted COGS.

        Args:
            date_from / date_to: optional `ProductionOrder.created_date`
                window — scopes which boats are analysed.
            limit: max suggestions returned (highest € overspend first).
            llm_client: optional pre-built LLM client (tests pass an
                `AsyncMock`); when None one is created lazily.

        Returns a 200-shaped dict always. When there is not enough data
        to compute a baseline, `suggestions` is empty with a clear
        `reason` — never a fabricated finding.
        """
        orders = await self._load_orders(date_from, date_to)
        if not orders:
            return _empty("Não há ordens de produção na janela analisada.")

        keys = [str(o.legacy_id) for o in orders]
        cost_by_order = await self._load_costs(keys)
        order_by_key = {str(o.legacy_id): o for o in orders}

        if not cost_by_order:
            return _empty(
                "Nenhuma ordem na janela tem COGS calculado — sem "
                "base para detetar desvios de custo."
            )

        baselines = self._build_baselines(order_by_key, cost_by_order)
        outliers = self._find_outliers(
            order_by_key, cost_by_order, baselines
        )
        # Biggest money leak first.
        outliers.sort(key=lambda o: o.overspend_eur, reverse=True)
        outliers = outliers[:limit]

        if not outliers:
            return _empty(
                "Os custos por barco estão dentro do esperado — nenhum "
                "desvio acima do limiar foi encontrado."
            )

        client = llm_client or await self._llm_client()
        suggestions = []
        for o in outliers:
            text = await self._explain(o, client)
            suggestions.append(self._suggestion_dict(o, text))

        total_opportunity = sum(
            (o.overspend_eur for o in outliers), Decimal("0")
        )
        return {
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "count": len(suggestions),
            "total_opportunity_eur": _money(total_opportunity),
            "suggestions": suggestions,
            "reason": None,
            "currency": "EUR",
            "source": "profit.cost_calculations",
        }

    async def create_decision_from_suggestion(
        self,
        suggestion: dict[str, Any],
        *,
        proposed_by: str,
    ) -> dict[str, Any]:
        """Promote a suggestion into a governance `DecisionRun`.

        The decision lands in the Inbox for human approval (the
        `cost_reduction` type has no auto-approve policy, so
        `GovernanceService` keeps `requires_approval=True`). Its
        `expected_impact.eur_saved` is the deterministic overspend — so
        once executed it counts towards the PP1-impact KPI that
        `ObjectivesService._pp1_impact` reads.
        """
        from src.governance.service import GovernanceService

        eur_saved = float(suggestion["overspend_eur"])
        gov = GovernanceService(self.session, self.tenant_id)
        decision = await gov.propose_decision(
            decision_type=COST_REDUCTION_DECISION_TYPE,
            title=suggestion["title"],
            description=suggestion["explanation"],
            action_data={
                "kind": "cost_reduction_suggestion",
                "order_id": suggestion["order_id"],
                "product_type": suggestion["product_type"],
                "cost_center": suggestion["cost_center"],
                "boat_cost_eur": suggestion["boat_cost_eur"],
                "baseline_cost_eur": suggestion["baseline_cost_eur"],
            },
            proposed_by=proposed_by,
            expected_impact={
                "eur_saved": eur_saved,
                "kpi": "cogs_eur",
                "basis": "median_baseline_by_product_type",
            },
            risk_level="low",
            evidence_refs=[
                f"cost_calculation:order_id={suggestion['order_id']}",
            ],
        )
        return decision

    # ─── loaders ───────────────────────────────────────────────────────────

    async def _load_orders(
        self,
        date_from: Optional[date],
        date_to: Optional[date],
        limit: int = 5000,
    ) -> list[ProductionOrder]:
        stmt = select(ProductionOrder).where(
            ProductionOrder.tenant_id == self.tenant_id
        )
        if date_from is not None:
            stmt = stmt.where(ProductionOrder.created_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(ProductionOrder.created_date <= date_to)
        stmt = stmt.order_by(
            ProductionOrder.created_date.desc().nullslast()
        ).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def _load_costs(
        self, keys: list[str]
    ) -> dict[str, CostCalculation]:
        """Latest `CostCalculation` per order_id (highest version wins)."""
        by_order: dict[str, CostCalculation] = {}
        stmt = (
            select(CostCalculation)
            .where(
                and_(
                    CostCalculation.tenant_id == self.tenant_id,
                    CostCalculation.order_id.in_(keys),
                )
            )
            .order_by(CostCalculation.calculation_version)
        )
        for cc in (await self.session.execute(stmt)).scalars().all():
            by_order[cc.order_id] = cc
        return by_order

    async def _llm_client(self) -> Any:
        """Lazily build the configured LLM client (Ollama by default)."""
        from src.copilot.llm.factory import get_llm_client

        return await get_llm_client(
            session=self.session, tenant_id=self.tenant_id
        )

    # ─── analysis (pure / deterministic) ───────────────────────────────────

    def _build_baselines(
        self,
        order_by_key: dict[str, ProductionOrder],
        cost_by_order: dict[str, CostCalculation],
    ) -> dict[tuple[str, str], Decimal]:
        """Median cost per (product_type, component).

        Only types with `>= _MIN_SAMPLE` calculated boats get a baseline
        — a median of two boats is not a baseline, it is a guess.
        """
        buckets: dict[tuple[str, str], _Bucket] = {}
        for order_id, cc in cost_by_order.items():
            order = order_by_key.get(order_id)
            ptype = (order.product_type if order else None) or "Outro"
            for comp in _COST_COMPONENTS:
                value = Decimal(str(getattr(cc, f"{comp}_cost")))
                buckets.setdefault((ptype, comp), _Bucket()).samples.append(
                    value
                )

        baselines: dict[tuple[str, str], Decimal] = {}
        for key, bucket in buckets.items():
            if len(bucket.samples) < _MIN_SAMPLE:
                continue
            baselines[key] = _median(bucket.samples)
        return baselines

    def _find_outliers(
        self,
        order_by_key: dict[str, ProductionOrder],
        cost_by_order: dict[str, CostCalculation],
        baselines: dict[tuple[str, str], Decimal],
    ) -> list[_Outlier]:
        """Flag boats whose component cost exceeds its type baseline."""
        # Sample size per (type, component) for the explanation context.
        sample_size: dict[tuple[str, str], int] = {}
        for order_id, cc in cost_by_order.items():
            order = order_by_key.get(order_id)
            ptype = (order.product_type if order else None) or "Outro"
            for comp in _COST_COMPONENTS:
                k = (ptype, comp)
                sample_size[k] = sample_size.get(k, 0) + 1

        outliers: list[_Outlier] = []
        for order_id, cc in cost_by_order.items():
            order = order_by_key.get(order_id)
            ptype = (order.product_type if order else None) or "Outro"
            for comp in _COST_COMPONENTS:
                baseline = baselines.get((ptype, comp))
                if baseline is None or baseline <= 0:
                    continue
                boat_cost = Decimal(str(getattr(cc, f"{comp}_cost")))
                slack = boat_cost - baseline
                if (
                    boat_cost >= baseline * _OUTLIER_FACTOR
                    and slack >= _MIN_ABS_SLACK_EUR
                ):
                    outliers.append(
                        _Outlier(
                            order_id=order_id,
                            product_type=ptype,
                            product_name=(
                                order.product_name if order else None
                            ),
                            component=comp,
                            boat_cost=boat_cost,
                            baseline_cost=baseline,
                            sample_size=sample_size.get((ptype, comp), 0),
                        )
                    )
        return outliers

    # ─── explanation (LLM writes prose, never numbers) ─────────────────────

    async def _explain(self, outlier: _Outlier, client: Any) -> str:
        """Ask the LLM for a PT-PT explanation; fall back deterministically.

        The LLM gets the figures already computed and is told to *only*
        phrase them — it must not invent or alter any number. If the
        call fails (Ollama offline in dev) we ship a templated sentence
        built from the same figures.
        """
        if client is None:
            return self._fallback_text(outlier)

        prompt = self._build_prompt(outlier)
        system = (
            "És um analista de custos da fábrica de caiaques NELO. "
            "Recebes números já calculados sobre um desvio de custo e "
            "escreves uma explicação curta em português de Portugal "
            "(informal, 1-2 frases). NUNCA inventes nem alteres números "
            "— usa apenas os que recebes. Responde só com a frase, sem "
            "markdown nem prefácios."
        )
        try:
            response = await client.chat(
                prompt=prompt,
                model=self._model_id(),
                format=None,
                system_prompt=system,
            )
        except Exception as exc:  # noqa: BLE001 — degrade, never crash
            logger.warning(
                "cost-reduction: LLM indisponível, uso texto determinístico: %s",
                exc,
            )
            return self._fallback_text(outlier)

        text = _response_text(response)
        if not text:
            return self._fallback_text(outlier)
        return text.strip()

    def _build_prompt(self, o: _Outlier) -> str:
        label = _COMPONENT_LABEL.get(o.component, o.component)
        return (
            "Escreve uma explicação curta para esta sugestão de redução "
            "de custo.\n"
            f"- Barco: {o.product_name or o.order_id} "
            f"(ordem {o.order_id}, tipo {o.product_type})\n"
            f"- Centro de custo: {label}\n"
            f"- Custo deste barco: {_money(o.boat_cost):.0f} EUR\n"
            f"- Mediana do tipo {o.product_type} "
            f"({o.sample_size} barcos): {_money(o.baseline_cost):.0f} EUR\n"
            f"- Excesso: {_money(o.overspend_eur):.0f} EUR "
            f"({o.overspend_ratio:.2f}x acima da mediana)\n"
            "Diz porque é que isto merece atenção e o que poupa se for "
            "corrigido para a mediana."
        )

    @staticmethod
    def _fallback_text(o: _Outlier) -> str:
        label = _COMPONENT_LABEL.get(o.component, o.component)
        return (
            f"O barco {o.product_name or o.order_id} gastou "
            f"{_money(o.boat_cost):.0f} EUR em {label}, contra uma mediana "
            f"de {_money(o.baseline_cost):.0f} EUR para os {o.product_type} "
            f"({o.sample_size} barcos). Alinhar com a mediana poupa "
            f"{_money(o.overspend_eur):.0f} EUR neste barco."
        )

    @staticmethod
    def _model_id() -> str:
        from src.shared.config import settings

        return getattr(settings, "ollama_model", "gemma4:e4b")

    # ─── shaping ───────────────────────────────────────────────────────────

    @staticmethod
    def _suggestion_dict(o: _Outlier, explanation: str) -> dict[str, Any]:
        label = _COMPONENT_LABEL.get(o.component, o.component)
        return {
            "order_id": o.order_id,
            "hull": o.order_id,
            "product_type": o.product_type,
            "product_name": o.product_name,
            "cost_center": o.component,
            "cost_center_label": label,
            "boat_cost_eur": _money(o.boat_cost),
            "baseline_cost_eur": _money(o.baseline_cost),
            "overspend_eur": _money(o.overspend_eur),
            "overspend_ratio": o.overspend_ratio,
            "sample_size": o.sample_size,
            "title": (
                f"Barco {o.product_name or o.order_id}: {label} "
                f"+{_money(o.overspend_eur):.0f} EUR vs mediana {o.product_type}"
            ),
            "explanation": explanation,
            "decision_type": COST_REDUCTION_DECISION_TYPE,
        }


# ─── helpers ───────────────────────────────────────────────────────────────


def _median(values: list[Decimal]) -> Decimal:
    """Median of a non-empty list of Decimals."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _money(value: Any) -> float:
    """Decimal/None-safe euro rounding to cents."""
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _response_text(response: Any) -> Optional[str]:
    """Pull plain text out of an LLM response envelope.

    Handles the two shapes the Ollama backend returns — `{"message":
    {"content": ...}}` (chat) and `{"response": ...}` (generate).
    """
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        msg = response.get("message")
        if isinstance(msg, dict) and msg.get("content"):
            return str(msg["content"])
        if response.get("response"):
            return str(response["response"])
        # Some callers JSON-encode a {"text": ...} blob.
        if response.get("text"):
            return str(response["text"])
    return None


def _empty(reason: str) -> dict[str, Any]:
    return {
        "date_from": None,
        "date_to": None,
        "count": 0,
        "total_opportunity_eur": 0.0,
        "suggestions": [],
        "reason": reason,
        "currency": "EUR",
        "source": "profit.cost_calculations",
    }
