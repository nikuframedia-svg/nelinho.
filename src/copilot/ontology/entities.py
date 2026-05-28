"""
ProdPlan ONE — Ontologia formal das entidades NELO (Q.115.I)
=============================================================

Lista canónica de entidades e relações do domínio fabril. Serve como
contrato semântico para o loop Claude remoto: enriquecer o grafo ao
longo dos dias seguintes sem perder consistência.

Fontes:
- MEASURE_REGISTRY / CANONICAL_DIMENSIONS (measure_contract.py)
- nelo_dag.py (22 CausalNodes)
- DB schemas: core, plan, quality, governance, supply, hr
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EntityCategory(str, Enum):
    PROCESS = "process"       # fases, operações, OFs
    RESOURCE = "resource"     # operadores, máquinas, moldes
    PRODUCT = "product"       # produtos, BOM, materiais
    EVENT = "event"           # defeitos, rework, decisões
    SEMANTIC = "semantic"     # KPIs, medidas, dimensões
    EXTERNAL = "external"     # clientes, fornecedores, encomendas


class RelationKind(str, Enum):
    HAS_A = "has_a"           # OF has phases
    REQUIRES = "requires"     # phase requires skill
    PRODUCES = "produces"     # operation produces defect
    DEPENDS_ON = "depends_on" # phase B depends_on phase A
    BELONGS_TO = "belongs_to" # operator belongs_to team
    MEASURES = "measures"     # measure_X measures phase_Y
    CAUSES = "causes"         # cura_inadequada causes defeito


@dataclass(frozen=True)
class Entity:
    name: str
    category: EntityCategory
    source_path: str          # caminho canónico (e.g. "core.products" ou "MEASURE_REGISTRY.throughput")
    description_pt: str       # 1 linha PT-PT


@dataclass(frozen=True)
class Relation:
    source: str               # Entity.name
    target: str               # Entity.name
    kind: RelationKind
    confidence: float         # [0, 1] — 1.0 canónico, <1 descoberto


# ─── Lista canónica ───────────────────────────────────────────────────────────
# Claude remoto enriquece com o tempo. ≥30 entidades obrigatório.

ENTITIES: list[Entity] = [
    # PROCESS
    Entity("of", EntityCategory.PROCESS, "plan.production_orders", "Ordem de fabrico"),
    Entity("phase", EntityCategory.PROCESS, "plan.routing_template_phases", "Fase de produção"),
    Entity("operation", EntityCategory.PROCESS, "core.operation", "Operação executada"),
    Entity("schedule_commit", EntityCategory.PROCESS, "plan.cpo.commits", "Plano aprovado pelo CPO"),
    Entity("routing_template", EntityCategory.PROCESS, "plan.routing_templates", "Template de routing (61 padrões)"),
    # RESOURCE
    Entity("operator", EntityCategory.RESOURCE, "core.employees", "Operador da fábrica"),
    Entity("machine", EntityCategory.RESOURCE, "core.machine", "Máquina de produção"),
    Entity("mold", EntityCategory.RESOURCE, "plan.molds", "Molde (510 na NELO)"),
    Entity("skill", EntityCategory.RESOURCE, "hr.skills", "Competência do operador"),
    Entity("operator_phase_affinity", EntityCategory.RESOURCE, "governance.phase_operator_affinity", "Afinidade operador-fase (score aprendido)"),
    Entity("shift", EntityCategory.RESOURCE, "plan.shifts", "Turno de trabalho"),
    # PRODUCT
    Entity("product", EntityCategory.PRODUCT, "core.products", "Produto/modelo de caiaque"),
    Entity("bom_item", EntityCategory.PRODUCT, "core.bom", "Componente do BOM"),
    Entity("material", EntityCategory.PRODUCT, "supply.supply_material_master", "Material / matéria-prima"),
    Entity("bom", EntityCategory.PRODUCT, "core.bom", "Bill of Materials completa"),
    # EVENT
    Entity("rework_entry", EntityCategory.EVENT, "quality.rework_entry", "Registo de retrabalho"),
    Entity("defect", EntityCategory.EVENT, "quality.error_catalog", "Tipo de defeito catalogado"),
    Entity("decision", EntityCategory.EVENT, "governance.decision_runs", "Decisão proposta ao CPO"),
    Entity("runbook", EntityCategory.EVENT, "quality.runbook", "Procedimento de remediação aprendido"),
    Entity("preference_rule", EntityCategory.EVENT, "governance.preference_rule", "Regra de preferência aprendida"),
    Entity("audit_entry", EntityCategory.EVENT, "governance.audit_log", "Entrada de auditoria (imutável)"),
    Entity("transport_event", EntityCategory.EVENT, "plan.transport_batch", "Evento de expedição/camião"),
    # SEMANTIC
    Entity("kpi_throughput", EntityCategory.SEMANTIC, "MEASURE_REGISTRY.throughput", "Throughput diário (barcos/dia)"),
    Entity("kpi_defect_rate", EntityCategory.SEMANTIC, "MEASURE_REGISTRY.defect_rate", "Taxa de defeitos (%)"),
    Entity("kpi_otd", EntityCategory.SEMANTIC, "MEASURE_REGISTRY.otd", "On-time delivery (%)"),
    Entity("kpi_oee", EntityCategory.SEMANTIC, "MEASURE_REGISTRY.oee", "Overall Equipment Effectiveness"),
    Entity("kpi_margin", EntityCategory.SEMANTIC, "MEASURE_REGISTRY.margin", "Margem € por barco"),
    Entity("dimension_phase", EntityCategory.SEMANTIC, "CANONICAL_DIMENSIONS.fase", "Dimensão fase (Cube)"),
    Entity("dimension_operator", EntityCategory.SEMANTIC, "CANONICAL_DIMENSIONS.operator_id", "Dimensão operador (Cube)"),
    Entity("dimension_mold", EntityCategory.SEMANTIC, "CANONICAL_DIMENSIONS.molde_id", "Dimensão molde (Cube)"),
    Entity("dimension_time", EntityCategory.SEMANTIC, "CANONICAL_DIMENSIONS.tempo", "Dimensão temporal (Cube)"),
    Entity("dimension_client", EntityCategory.SEMANTIC, "CANONICAL_DIMENSIONS.cliente", "Dimensão cliente (Cube)"),
    # EXTERNAL
    Entity("client", EntityCategory.EXTERNAL, "core.entities", "Cliente NELO"),
    Entity("supplier", EntityCategory.EXTERNAL, "core.entities", "Fornecedor"),
    Entity("encomenda", EntityCategory.EXTERNAL, "ERP.ENCOMENDA", "Encomenda do ERP MAR-KAYAKS"),
    Entity("transport_batch", EntityCategory.EXTERNAL, "plan.transport_batch", "Camião / lote de expedição"),
    # Adicional CPO / aprendizagem
    Entity("user_input", EntityCategory.EVENT, "core.user_input", "Input PT-PT do Luis (trigger decisão)"),
    Entity("cost_target", EntityCategory.SEMANTIC, "core.daily_revenue_target", "Alvo diário de receita €"),
]


RELATIONS: list[Relation] = [
    # OF / fases / operações
    Relation("of", "phase", RelationKind.HAS_A, 1.0),
    Relation("phase", "operation", RelationKind.HAS_A, 1.0),
    Relation("phase", "skill", RelationKind.REQUIRES, 1.0),
    Relation("phase", "phase", RelationKind.DEPENDS_ON, 1.0),      # B depends_on A
    Relation("of", "product", RelationKind.BELONGS_TO, 1.0),
    Relation("of", "client", RelationKind.BELONGS_TO, 1.0),
    Relation("of", "transport_batch", RelationKind.BELONGS_TO, 0.8),
    Relation("of", "routing_template", RelationKind.BELONGS_TO, 1.0),
    # Recursos
    Relation("operation", "operator", RelationKind.REQUIRES, 1.0),
    Relation("operation", "machine", RelationKind.REQUIRES, 1.0),
    Relation("operation", "mold", RelationKind.REQUIRES, 0.9),
    Relation("operator", "skill", RelationKind.HAS_A, 1.0),
    Relation("operator", "operator_phase_affinity", RelationKind.HAS_A, 1.0),
    Relation("operator", "shift", RelationKind.BELONGS_TO, 1.0),
    # Produto
    Relation("product", "bom_item", RelationKind.HAS_A, 1.0),
    Relation("bom_item", "material", RelationKind.HAS_A, 1.0),
    Relation("product", "bom", RelationKind.HAS_A, 1.0),
    # Eventos
    Relation("operation", "rework_entry", RelationKind.PRODUCES, 0.7),
    Relation("rework_entry", "defect", RelationKind.BELONGS_TO, 1.0),
    Relation("defect", "runbook", RelationKind.HAS_A, 0.8),
    Relation("decision", "schedule_commit", RelationKind.PRODUCES, 1.0),
    Relation("user_input", "decision", RelationKind.CAUSES, 0.6),
    Relation("rework_entry", "preference_rule", RelationKind.CAUSES, 0.5),
    Relation("decision", "audit_entry", RelationKind.PRODUCES, 1.0),
    # Semântico (KPIs → fontes)
    Relation("kpi_throughput", "operation", RelationKind.MEASURES, 1.0),
    Relation("kpi_defect_rate", "rework_entry", RelationKind.MEASURES, 1.0),
    Relation("kpi_otd", "of", RelationKind.MEASURES, 1.0),
    Relation("kpi_margin", "operation", RelationKind.MEASURES, 1.0),
    Relation("kpi_oee", "machine", RelationKind.MEASURES, 1.0),
    Relation("cost_target", "of", RelationKind.MEASURES, 0.9),
]


# ─── Lookups ──────────────────────────────────────────────────────────────────

def _build_index() -> dict[str, Entity]:
    idx: dict[str, Entity] = {}
    for e in ENTITIES:
        idx[e.name] = e
    return idx


_ENTITY_INDEX: dict[str, Entity] = _build_index()


def find_entity(name: str) -> Optional[Entity]:
    """Devolve a Entity com `name`, ou None."""
    return _ENTITY_INDEX.get(name)


def relations_from(entity: str) -> list[Relation]:
    """Todas as relações onde `entity` é source."""
    return [r for r in RELATIONS if r.source == entity]


def relations_to(entity: str) -> list[Relation]:
    """Todas as relações onde `entity` é target."""
    return [r for r in RELATIONS if r.target == entity]


def export_json() -> dict:
    """Graph dump para visualização / enriquecimento pelo Claude remoto."""
    return {
        "schema_version": "q115.i.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(ENTITIES),
        "relation_count": len(RELATIONS),
        "entities": [asdict(e) for e in ENTITIES],
        "relations": [asdict(r) for r in RELATIONS],
    }
