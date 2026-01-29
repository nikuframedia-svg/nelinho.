"""
SEMANTIC Views — Contrato 010
=============================

Factory Semantic Schema:
- v_lead_time_historico
- v_backlog_fase_teorico
- v_bottlenecks_teoricos
- v_mold_conflicts_potenciais
- v_quality_hotspots
- v_skill_risk
- v_cost_teorico_por_ordem (sensitive)

CRITICAL:
- All views filter by factory_meta.active_run.active_ingestion_id
- Views return empty if data unavailable (not error)
- Trust metadata included where applicable
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SemanticViewId(str, Enum):
    """Allowed semantic view identifiers."""
    LEAD_TIME_HISTORICO = "v_lead_time_historico"
    BACKLOG_FASE_TEORICO = "v_backlog_fase_teorico"
    BOTTLENECKS_TEORICOS = "v_bottlenecks_teoricos"
    MOLD_CONFLICTS_POTENCIAIS = "v_mold_conflicts_potenciais"
    QUALITY_HOTSPOTS = "v_quality_hotspots"
    SKILL_RISK = "v_skill_risk"
    COST_TEORICO_POR_ORDEM = "v_cost_teorico_por_ordem"  # Sensitive


@dataclass
class SemanticViewDefinition:
    """Definition of a semantic view."""
    
    view_id: SemanticViewId
    name: str
    description: str
    schema_name: str
    
    # Available fields
    fields: List[str]
    
    # Filterable fields
    filterable_fields: List[str]
    
    # Sortable fields
    sortable_fields: List[str]
    
    # Required permissions
    requires_permission: Optional[str] = None
    
    # Is sensitive (PII or cost)?
    is_sensitive: bool = False
    
    # Trust score (0.0-1.0, None if unknown)
    trust_score: Optional[float] = None
    
    # Disclaimers
    disclaimers: List[str] = None
    
    def __post_init__(self):
        if self.disclaimers is None:
            self.disclaimers = []


# ============================================================================
# VIEW DEFINITIONS
# ============================================================================

SEMANTIC_VIEW_DEFINITIONS: Dict[SemanticViewId, SemanticViewDefinition] = {
    
    SemanticViewId.LEAD_TIME_HISTORICO: SemanticViewDefinition(
        view_id=SemanticViewId.LEAD_TIME_HISTORICO,
        name="Lead Time Histórico",
        description="Lead time histórico por ordem de fabrico",
        schema_name="factory_semantic",
        fields=[
            "of_id", "produto_id", "modelo_id",
            "data_entrada", "data_conclusao",
            "lead_time_dias", "lead_time_horas_produtivas",
            "trust_score",
        ],
        filterable_fields=["produto_id", "modelo_id", "data_entrada", "data_conclusao"],
        sortable_fields=["of_id", "data_entrada", "lead_time_dias"],
        trust_score=0.7,
        disclaimers=[
            "Lead time calculado com base em datas de entrada e conclusão registadas",
            "Não inclui tempos de espera não registados",
        ],
    ),
    
    SemanticViewId.BACKLOG_FASE_TEORICO: SemanticViewDefinition(
        view_id=SemanticViewId.BACKLOG_FASE_TEORICO,
        name="Backlog Teórico por Fase",
        description="Backlog teórico estimado por fase de produção",
        schema_name="factory_semantic",
        fields=[
            "fase_id", "fase_nome",
            "backlog_horas_teoricas", "backlog_ofs_count",
            "capacidade_horas_diaria", "dias_para_limpar_teorico",
            "trust_score",
        ],
        filterable_fields=["fase_id", "fase_nome"],
        sortable_fields=["fase_nome", "backlog_horas_teoricas", "dias_para_limpar_teorico"],
        trust_score=0.5,
        disclaimers=[
            "Valores são ESTIMATIVAS TEÓRICAS baseadas em standards",
            "Não representa carga real — ausência de dados MES",
            "Dias para limpar assume capacidade constante",
        ],
    ),
    
    SemanticViewId.BOTTLENECKS_TEORICOS: SemanticViewDefinition(
        view_id=SemanticViewId.BOTTLENECKS_TEORICOS,
        name="Bottlenecks Teóricos",
        description="Fases com potencial de estrangulamento",
        schema_name="factory_semantic",
        fields=[
            "fase_id", "fase_nome",
            "carga_teorica_horas", "capacidade_horas",
            "utilizacao_pct", "is_bottleneck",
            "trust_score",
        ],
        filterable_fields=["fase_id", "is_bottleneck"],
        sortable_fields=["utilizacao_pct", "fase_nome"],
        trust_score=0.4,
        disclaimers=[
            "Bottleneck TEÓRICO — baseado em standards, não em dados reais",
            "Utilização calculada: carga_teorica / capacidade",
            "Não considera variabilidade, absentismo, ou paragens",
        ],
    ),
    
    SemanticViewId.MOLD_CONFLICTS_POTENCIAIS: SemanticViewDefinition(
        view_id=SemanticViewId.MOLD_CONFLICTS_POTENCIAIS,
        name="Conflitos de Moldes Potenciais",
        description="Moldes com atribuições sobrepostas",
        schema_name="factory_semantic",
        fields=[
            "molde_id", "molde_nome",
            "conflict_type", "ofs_afetados",
            "datas_conflito", "severidade",
            "trust_score",
        ],
        filterable_fields=["molde_id", "conflict_type", "severidade"],
        sortable_fields=["severidade", "ofs_afetados"],
        trust_score=0.6,
        disclaimers=[
            "Conflitos detectados com base em sobreposição de datas planeadas",
            "Não considera tempo real de ocupação do molde",
        ],
    ),
    
    SemanticViewId.QUALITY_HOTSPOTS: SemanticViewDefinition(
        view_id=SemanticViewId.QUALITY_HOTSPOTS,
        name="Hotspots de Qualidade",
        description="Fases/moldes com maior incidência de erros",
        schema_name="factory_semantic",
        fields=[
            "fase_id", "fase_nome",
            "molde_id", "erro_tipo",
            "total_erros", "total_ofs",
            "taxa_erro_pct", "fpy_pct",
            "trust_score",
        ],
        filterable_fields=["fase_id", "molde_id", "erro_tipo"],
        sortable_fields=["taxa_erro_pct", "total_erros"],
        trust_score=0.6,
        disclaimers=[
            "Taxa de erro baseada em registos de OrdemFabricoErros",
            "Pode não refletir todos os defeitos (apenas os registados)",
        ],
    ),
    
    SemanticViewId.SKILL_RISK: SemanticViewDefinition(
        view_id=SemanticViewId.SKILL_RISK,
        name="Risco de Competências",
        description="Fases com concentração de competências",
        schema_name="factory_semantic",
        fields=[
            "fase_id", "fase_nome",
            "aptos_count", "total_funcionarios",
            "cobertura_pct", "risk_level",
            "single_point_of_failure",
            "trust_score",
        ],
        filterable_fields=["fase_id", "risk_level", "single_point_of_failure"],
        sortable_fields=["risk_level", "aptos_count", "cobertura_pct"],
        requires_permission="view:hr_aggregated",  # Aggregated, not individual PII
        is_sensitive=False,  # Aggregated data only
        trust_score=0.7,
        disclaimers=[
            "Baseado em matriz de aptidões registada",
            "Não considera absentismo ou disponibilidade real",
        ],
    ),
    
    SemanticViewId.COST_TEORICO_POR_ORDEM: SemanticViewDefinition(
        view_id=SemanticViewId.COST_TEORICO_POR_ORDEM,
        name="Custo Teórico por Ordem",
        description="Custo teórico estimado por ordem de fabrico",
        schema_name="factory_semantic",
        fields=[
            "of_id", "produto_id",
            "horas_teoricas_total", "custo_hora_medio",
            "custo_teorico_eur", "custo_real_eur",
            "desvio_pct",
            "trust_score",
        ],
        filterable_fields=["of_id", "produto_id"],
        sortable_fields=["of_id", "custo_teorico_eur", "desvio_pct"],
        requires_permission="view:cost_data",  # Sensitive permission
        is_sensitive=True,
        trust_score=0.3,
        disclaimers=[
            "CUSTO TEÓRICO — NÃO representa custo real",
            "Baseado em standards × custo/hora de referência",
            "Não inclui custos indiretos, materiais, ou overhead",
            "Uso apenas para estimativas grosseiras",
        ],
    ),
}


# ============================================================================
# SQL VIEW DEFINITIONS
# ============================================================================

def get_view_sql(view_id: SemanticViewId) -> str:
    """
    Get SQL for creating a semantic view.
    
    All views filter by active_ingestion_id.
    """
    
    views = {
        SemanticViewId.LEAD_TIME_HISTORICO: """
        CREATE OR REPLACE VIEW factory_semantic.v_lead_time_historico AS
        SELECT 
            o.of_id,
            o.produto_id,
            o.modelo_id,
            o.data_entrada,
            o.data_conclusao,
            CASE 
                WHEN o.data_conclusao IS NOT NULL AND o.data_entrada IS NOT NULL 
                THEN o.data_conclusao - o.data_entrada 
                ELSE NULL 
            END as lead_time_dias,
            COALESCE(SUM(op.horas_reais), 0) as lead_time_horas_produtivas,
            0.7 as trust_score
        FROM factory_curated."order" o
        LEFT JOIN factory_curated.order_phase op ON o.of_id = op.of_id AND o.ingestion_id = op.ingestion_id
        WHERE o.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY o.of_id, o.produto_id, o.modelo_id, o.data_entrada, o.data_conclusao;
        """,
        
        SemanticViewId.BACKLOG_FASE_TEORICO: """
        CREATE OR REPLACE VIEW factory_semantic.v_backlog_fase_teorico AS
        SELECT 
            op.fase_id,
            op.fase_nome,
            COALESCE(SUM(op.horas_finais), 0) as backlog_horas_teoricas,
            COUNT(DISTINCT op.of_id) as backlog_ofs_count,
            COALESCE(pc.capacidade_horas, 8.0) as capacidade_horas_diaria,
            CASE 
                WHEN pc.capacidade_horas > 0 
                THEN ROUND(COALESCE(SUM(op.horas_finais), 0) / pc.capacidade_horas, 1)
                ELSE NULL 
            END as dias_para_limpar_teorico,
            0.5 as trust_score
        FROM factory_curated.order_phase op
        LEFT JOIN factory_curated.phase_capacity pc ON op.fase_id = pc.fase_id AND op.ingestion_id = pc.ingestion_id
        WHERE op.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
          AND op.estado NOT IN ('Concluido', 'Fechado')
        GROUP BY op.fase_id, op.fase_nome, pc.capacidade_horas;
        """,
        
        SemanticViewId.BOTTLENECKS_TEORICOS: """
        CREATE OR REPLACE VIEW factory_semantic.v_bottlenecks_teoricos AS
        SELECT 
            op.fase_id,
            op.fase_nome,
            COALESCE(SUM(op.horas_finais), 0) as carga_teorica_horas,
            COALESCE(pc.capacidade_horas, 8.0) as capacidade_horas,
            CASE 
                WHEN pc.capacidade_horas > 0 
                THEN ROUND((COALESCE(SUM(op.horas_finais), 0) / pc.capacidade_horas) * 100, 1)
                ELSE 0 
            END as utilizacao_pct,
            CASE 
                WHEN pc.capacidade_horas > 0 AND COALESCE(SUM(op.horas_finais), 0) > pc.capacidade_horas * 1.2
                THEN true 
                ELSE false 
            END as is_bottleneck,
            0.4 as trust_score
        FROM factory_curated.order_phase op
        LEFT JOIN factory_curated.phase_capacity pc ON op.fase_id = pc.fase_id AND op.ingestion_id = pc.ingestion_id
        WHERE op.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY op.fase_id, op.fase_nome, pc.capacidade_horas;
        """,
        
        SemanticViewId.MOLD_CONFLICTS_POTENCIAIS: """
        CREATE OR REPLACE VIEW factory_semantic.v_mold_conflicts_potenciais AS
        SELECT 
            mu.molde_id,
            m.molde_nome,
            'overlap' as conflict_type,
            COUNT(DISTINCT mu.of_id) as ofs_afetados,
            NULL as datas_conflito,
            CASE 
                WHEN COUNT(DISTINCT mu.of_id) > 3 THEN 'high'
                WHEN COUNT(DISTINCT mu.of_id) > 1 THEN 'medium'
                ELSE 'low'
            END as severidade,
            0.6 as trust_score
        FROM factory_curated.mold_usage mu
        JOIN factory_curated.mold m ON mu.molde_id = m.molde_id AND mu.ingestion_id = m.ingestion_id
        WHERE mu.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY mu.molde_id, m.molde_nome
        HAVING COUNT(DISTINCT mu.of_id) > 1;
        """,
        
        SemanticViewId.QUALITY_HOTSPOTS: """
        CREATE OR REPLACE VIEW factory_semantic.v_quality_hotspots AS
        SELECT 
            qe.fase_id,
            op.fase_nome,
            qe.molde_id,
            qe.erro_tipo,
            SUM(qe.quantidade) as total_erros,
            COUNT(DISTINCT qe.of_id) as total_ofs,
            ROUND(SUM(qe.quantidade)::numeric / NULLIF(COUNT(DISTINCT qe.of_id), 0) * 100, 1) as taxa_erro_pct,
            100.0 - ROUND(SUM(qe.quantidade)::numeric / NULLIF(COUNT(DISTINCT qe.of_id), 0) * 100, 1) as fpy_pct,
            0.6 as trust_score
        FROM factory_curated.quality_event qe
        LEFT JOIN factory_curated.order_phase op ON qe.of_id = op.of_id AND qe.fase_id = op.fase_id AND qe.ingestion_id = op.ingestion_id
        WHERE qe.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY qe.fase_id, op.fase_nome, qe.molde_id, qe.erro_tipo;
        """,
        
        SemanticViewId.SKILL_RISK: """
        CREATE OR REPLACE VIEW factory_semantic.v_skill_risk AS
        SELECT 
            sm.fase_id,
            sm.fase_nome,
            COUNT(CASE WHEN sm.apto THEN 1 END) as aptos_count,
            COUNT(*) as total_funcionarios,
            ROUND(COUNT(CASE WHEN sm.apto THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as cobertura_pct,
            CASE 
                WHEN COUNT(CASE WHEN sm.apto THEN 1 END) = 0 THEN 'critical'
                WHEN COUNT(CASE WHEN sm.apto THEN 1 END) = 1 THEN 'high'
                WHEN COUNT(CASE WHEN sm.apto THEN 1 END) <= 3 THEN 'medium'
                ELSE 'low'
            END as risk_level,
            COUNT(CASE WHEN sm.apto THEN 1 END) = 1 as single_point_of_failure,
            0.7 as trust_score
        FROM factory_curated.skill_matrix sm
        WHERE sm.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY sm.fase_id, sm.fase_nome;
        """,
        
        SemanticViewId.COST_TEORICO_POR_ORDEM: """
        CREATE OR REPLACE VIEW factory_semantic.v_cost_teorico_por_ordem AS
        SELECT 
            o.of_id,
            o.produto_id,
            COALESCE(SUM(op.horas_finais), 0) as horas_teoricas_total,
            COALESCE(AVG(cr.valor_hora_eur), 0) as custo_hora_medio,
            COALESCE(SUM(op.horas_finais), 0) * COALESCE(AVG(cr.valor_hora_eur), 0) as custo_teorico_eur,
            NULL::numeric as custo_real_eur,
            NULL::numeric as desvio_pct,
            0.3 as trust_score
        FROM factory_curated."order" o
        LEFT JOIN factory_curated.order_phase op ON o.of_id = op.of_id AND o.ingestion_id = op.ingestion_id
        LEFT JOIN factory_curated.cost_reference cr ON op.fase_id = cr.fase_id AND op.ingestion_id = cr.ingestion_id
        WHERE o.ingestion_id = (SELECT active_ingestion_id FROM factory_meta.active_run WHERE id = 1)
        GROUP BY o.of_id, o.produto_id;
        """,
    }
    
    return views.get(view_id, "")


def get_allowed_view_ids() -> List[SemanticViewId]:
    """Get list of allowed view IDs."""
    return list(SEMANTIC_VIEW_DEFINITIONS.keys())


def is_view_allowed(view_id: str) -> bool:
    """Check if a view ID is allowed."""
    try:
        SemanticViewId(view_id)
        return True
    except ValueError:
        return False


