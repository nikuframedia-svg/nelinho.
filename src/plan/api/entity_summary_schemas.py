"""ProdPlan ONE — schemas (DTOs Pydantic) da Entity Summary API.

Extraido de entity_summary.py (saneamento 2026-06-04). Self-contained
(so pydantic/typing/uuid); importado por entity_summary.py. Q.116.A.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Schemas ─────────────────────────────────────────────────────────────────


class PhaseInTemplate(BaseModel):
    # Q.116.BD fix: row id (UUID) exposto para que o frontend ModeloSheet
    # possa usar nos endpoints PATCH /routing-templates/{id}/sequence e
    # /phases/{phase_row_id}/flexible. Sem isto os botoes "Guardar
    # ordem" e modal "Posicao alternativa" ficam desactivados.
    id: UUID
    seq: int
    phase_id: str
    phase_name: Optional[str]
    duration_p50_h: Optional[float]
    can_skip: bool
    # Q.116.B fix: estado is_flexible + allowed_predecessors para o
    # frontend mostrar badge e modal pre-populado.
    is_flexible: bool = False
    allowed_predecessors: Optional[List[str]] = None


class RoutingTemplateOut(BaseModel):
    id: UUID
    code: str
    name: str
    phase_count: int
    phases: List[PhaseInTemplate]


class BoatInProduction(BaseModel):
    """Q.116.G — linha resumo de um barco actualmente em produção do modelo."""

    legacy_id: int
    current_phase_name: str
    customer_name: Optional[str] = None
    transport_date: Optional[str] = None
    effective_boost: int = 0


class ModeloSummary(BaseModel):
    # `model_` é um namespace protegido em Pydantic v2; silenciamos o
    # warning porque o domínio NELO usa "modelo" para barco (não LLM).
    model_config = {"protected_namespaces": ()}

    model_id: str
    model_name: str
    product_type: Optional[str]
    routing_template: Optional[RoutingTemplateOut]
    active_orders_count: int
    in_production_count: int
    # Q.116.G — lista (até 20) de barcos do modelo actualmente em
    # produção, ordenados por `created_date DESC`. effective_boost vem
    # do mesmo stack do EncomendaSummary (cliente + encomenda + barco).
    # Q.172.F4E (fecha o TODO Q.117.X): o truncamento deixou de ser
    # silencioso — `in_production_truncated=True` quando a lista é
    # parcial; o total REAL está em `in_production_count`.
    in_production_boats: List[BoatInProduction] = Field(default_factory=list)
    in_production_truncated: bool = False
    # Q.116.C — lista (até 20) de encomendas activas do modelo. Reutiliza
    # o shape OrderInList (mesmo do ClienteSummary). Forward-ref resolvido
    # via model_rebuild() no fim do bloco de schemas.
    orders: List["OrderInList"] = Field(default_factory=list)
    # Q.116.E — drill-down por fase da rota com top operadores (afinidade).
    phase_drilldown: List["PhaseDrilldown"] = Field(default_factory=list)


class OperatorScore(BaseModel):
    operator_id: str
    operator_name: str
    score: float
    sample_count: int


class PhaseDrilldown(BaseModel):
    """Q.116.E — uma fase da rota do modelo + os seus top operadores."""

    phase_id: str
    phase_name: Optional[str]
    seq: int
    top_operators: List[OperatorScore] = Field(default_factory=list)


class BoatScore(BaseModel):
    boat_id: str
    score: float
    sample_count: int


class CuringGap(BaseModel):
    from_phase: str
    to_phase: str
    hours: float


class FaseSummary(BaseModel):
    phase_id: str
    phase_name: str
    top_operators: List[OperatorScore]
    difficult_boats: List[BoatScore]
    curing_gaps_in: List[CuringGap]
    curing_gaps_out: List[CuringGap]
    # Q.160 — mediana REAL da fila inter-fase ANTES desta fase (horas), de
    # factory_raw.of_fp. Diagnóstico de WIP/gargalo (qual fase acumula espera).
    # None quando a fase não tem >=5 observações (honesto, zero-mocks).
    fila_mediana_h: Optional[float] = None


class OrderInList(BaseModel):
    legacy_id: int
    product_name: str
    current_phase_name: str
    transport_date: Optional[str]
    status: str


class LeadTimeEntry(BaseModel):
    """Q.116.D — lead-time de uma encomenda concluída do cliente."""

    legacy_id: int
    days: float


class ClienteHistory(BaseModel):
    """Q.116.D — histórico do cliente: lead-time + revenue.

    Cada secção é independente e honesta: `avg_lead_time_days`/`lead_times`
    ficam vazios sem encomendas concluídas; `revenue_eur` fica None quando o
    mart de facturação não existe (dev) ou o nome do cliente não casa.
    """

    completed_orders_count: int = 0
    avg_lead_time_days: Optional[float] = None
    lead_times: List[LeadTimeEntry] = Field(default_factory=list)
    revenue_eur: Optional[float] = None
    revenue_note: Optional[str] = None


class ClienteSummary(BaseModel):
    customer_id: str
    customer_name: str
    priority: Optional[int]
    active_orders_count: int
    orders: List[OrderInList]
    # Q.116.D — secção Histórico (lead-time + revenue).
    history: Optional[ClienteHistory] = None


class PhaseHistoryEntry(BaseModel):
    phase_name: str
    start_at: Optional[str]
    end_at: Optional[str]


class EncomendaSummary(BaseModel):
    legacy_id: int
    product_name: str
    product_type: Optional[str]
    customer_name: Optional[str]
    status: str
    current_phase_name: str
    created_date: Optional[str]
    transport_date: Optional[str]
    completed_date: Optional[str]
    phase_history: List[PhaseHistoryEntry]
    # Q.116.C — boost manual + override de data de transporte. As tabelas
    # plan.order_boost e plan.work_order_override estao a ser introduzidas
    # pelo Agent B em paralelo; ate ai (ou em dev sem migrate), os
    # endpoints devolvem defaults (0/None) em vez de falhar.
    boost: int = 0
    boost_reason: Optional[str] = None
    transport_date_override: Optional[str] = None
    transport_date_effective: Optional[str] = None
    # Q.116.G — breakdown completo do stack do boost. `client_boost` vem
    # de `ClientPriority` do cliente associado mapeado via
    # `client_boost_from_priority` (5 escalões 100/80/60/40/20).
    # `boat_boost` é o BoatBoost (PK = product_name string).
    # `effective_boost` é a soma capped a 200 via
    # `boost_service.compute_effective_boost`. Defaults 0 quando alguma
    # query falha (defesa em profundidade — endpoint robusto).
    client_boost: int = 0
    boat_boost: int = 0
    effective_boost: int = 0


# Q.116.E — Operador sheet ────────────────────────────────────────────────────


class TopPhaseForOperator(BaseModel):
    phase_id: str
    phase_name: str
    score: float
    sample_count: int


class OperatorTask(BaseModel):
    """Q.116.F — tarefa do operador no plano de hoje (último ScheduleCommit)."""

    operation_id: str
    order_legacy_id: Optional[int]
    phase_name: str
    start_time: Optional[str]
    end_time: Optional[str]


class OperatorPhaseHistory(BaseModel):
    """Q.116.F — fase trabalhada no histórico real (factory_raw.of_fp)."""

    of_legacy_id: Optional[int]
    phase_id: str
    phase_name: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    hours: Optional[float]


class OperadorSummary(BaseModel):
    operator_id: str
    operator_name: str
    role: Optional[str]
    active: bool
    top_phases: List[TopPhaseForOperator]
    total_phases_with_data: int
    # Q.116.F — tarefas de hoje (plano) + histórico de fases (ERP).
    today_tasks: List[OperatorTask] = Field(default_factory=list)
    phase_history: List[OperatorPhaseHistory] = Field(default_factory=list)


# Resolve forward-refs: ModeloSummary referencia OrderInList/PhaseDrilldown
# que são definidos mais abaixo (from __future__ annotations → lazy).
ModeloSummary.model_rebuild()
