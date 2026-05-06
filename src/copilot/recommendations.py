"""
ProdPlan ONE - COPILOT Recommendations Generator
=================================================

Gera recomendações baseadas em análise de dados OEE, qualidade e performance.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from src.plan.models.schedule import ProductionSchedule, ScheduleStatus

logger = logging.getLogger(__name__)


class Recommendation:
    """Recomendação estruturada."""
    
    def __init__(
        self,
        priority: int,
        category: str,
        title: str,
        description: str,
        impact_metric: str,
        impact_value: float,
        affected_phases: List[str] = None,
        suggested_actions: List[str] = None,
        data_evidence: Dict[str, Any] = None,
    ):
        self.priority = priority
        self.category = category  # "QUALITY", "PERFORMANCE", "MAINTENANCE", "STANDARD_WORK"
        self.title = title
        self.description = description
        self.impact_metric = impact_metric  # "rework_rate", "performance", "oee", etc.
        self.impact_value = impact_value  # Valor atual do métrica
        self.affected_phases = affected_phases or []
        self.suggested_actions = suggested_actions or []
        self.data_evidence = data_evidence or {}
        self.generated_at = datetime.now(timezone.utc)


async def generate_recommendations(
    session: AsyncSession,
    tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """
    Gerar recomendações baseadas em análise de dados.
    
    Returns:
        Lista de recomendações estruturadas.
    """
    recommendations = []
    
    try:
        # 1. Analisar rework rate e qualidade
        rework_analysis = await _analyze_rework_rate(session, tenant_id)
        if rework_analysis:
            recommendations.append(rework_analysis)
        
        # 2. Analisar performance por fase
        performance_analysis = await _analyze_performance(session, tenant_id)
        if performance_analysis:
            recommendations.append(performance_analysis)
        
        # 3. Analisar fases com problemas frequentes
        maintenance_analysis = await _analyze_maintenance_needs(session, tenant_id)
        if maintenance_analysis:
            recommendations.append(maintenance_analysis)
        
        # Ordenar por prioridade (1 = mais importante)
        recommendations.sort(key=lambda r: r.get("priority", 999))
        
        # Limitar a 3-5 recomendações principais
        return recommendations[:5]
        
    except Exception as e:
        logger.error(f"Erro ao gerar recomendações: {e}", exc_info=True)
        return []


async def _analyze_rework_rate(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """Analisar taxa de retrabalho e gerar recomendação."""
    try:
        from sqlalchemy import select, func, and_
        
        # Contar orders total e orders com problemas
        orders_total_query = select(func.count(func.distinct(ProductionSchedule.order_id))).where(
            ProductionSchedule.tenant_id == tenant_id
        )
        orders_total_result = await session.execute(orders_total_query)
        orders_total = orders_total_result.scalar() or 0
        
        orders_completed_query = select(func.count(func.distinct(ProductionSchedule.order_id))).where(
            and_(
                ProductionSchedule.tenant_id == tenant_id,
                ProductionSchedule.status == ScheduleStatus.COMPLETED,
            )
        )
        orders_completed_result = await session.execute(orders_completed_query)
        orders_completed = orders_completed_result.scalar() or 0
        
        if orders_total == 0:
            return None
        
        # Calcular rework rate (simplificado: orders não completadas = rework)
        orders_with_issues = orders_total - orders_completed
        rework_rate = (orders_with_issues / orders_total) * 100.0 if orders_total > 0 else 0.0
        
        # Se rework rate > 50%, recomendar Quality Gate
        if rework_rate > 50.0:
            # Identificar fase crítica (assumir Laminagem como fase inicial comum)
            return {
                "priority": 1,
                "category": "QUALITY",
                "title": "Quality Gate",
                "description": f"Implementar checkpoint de qualidade após fase de Laminagem para detetar defeitos mais cedo (reduzindo taxa de retrabalho de {rework_rate:.1f}%).",
                "impact_metric": "rework_rate",
                "impact_value": rework_rate,
                "affected_phases": ["Laminagem"],
                "suggested_actions": [
                    "Implementar inspeção visual após Laminagem",
                    "Adicionar teste de qualidade antes de avançar para próxima fase",
                    "Criar alerta automático para defeitos críticos",
                ],
                "data_evidence": {
                    "orders_total": orders_total,
                    "orders_with_issues": orders_with_issues,
                    "rework_rate": rework_rate,
                },
                "origins": ["BEST_PRACTICE", "HEURISTIC_REASONING"],
                "confidence": "MEDIUM",
                "limitations": [
                    "Sem evidência direta por fase/ativo, recomendação baseada em heurística e boas práticas",
                    "Rework rate calculado a partir de orders total vs completed (simplificação)",
                ],
                "next_steps": ["RUNBOOK"],
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Erro ao analisar rework rate: {e}")
        return None


async def _analyze_performance(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """Analisar performance e gerar recomendação."""
    try:
        from sqlalchemy import select, func, and_, case
        
        # Calcular performance média
        performance_query = select(
            func.avg(ProductionSchedule.scheduled_duration_hours).label("avg_standard"),
            func.avg(
                case(
                    (
                        and_(
                            ProductionSchedule.actual_start.isnot(None),
                            ProductionSchedule.actual_end.isnot(None),
                        ),
                        func.extract('epoch', ProductionSchedule.actual_end - ProductionSchedule.actual_start) / 3600.0
                    ),
                    else_=None
                )
            ).label("avg_actual"),
        ).where(
            and_(
                ProductionSchedule.tenant_id == tenant_id,
                ProductionSchedule.scheduled_duration_hours.isnot(None),
                ProductionSchedule.actual_start.isnot(None),
                ProductionSchedule.actual_end.isnot(None),
            )
        )
        performance_result = await session.execute(performance_query)
        perf_row = performance_result.first()
        
        if not perf_row or not perf_row.avg_standard or not perf_row.avg_actual or perf_row.avg_actual == 0:
            return None
        
        performance = min(100.0, (float(perf_row.avg_standard) / float(perf_row.avg_actual)) * 100.0)
        
        # Se performance < 70%, recomendar Standard Work
        if performance < 70.0:
            # Query worst-performing phases dynamically
            worst_phases_query = select(
                ProductionSchedule.operation_code,
                func.avg(ProductionSchedule.scheduled_duration_hours).label("avg_std"),
                func.avg(
                    func.extract('epoch', ProductionSchedule.actual_end - ProductionSchedule.actual_start) / 3600.0
                ).label("avg_actual"),
            ).where(
                and_(
                    ProductionSchedule.tenant_id == tenant_id,
                    ProductionSchedule.actual_start.isnot(None),
                    ProductionSchedule.actual_end.isnot(None),
                    ProductionSchedule.scheduled_duration_hours.isnot(None),
                    ProductionSchedule.operation_code.isnot(None),
                )
            ).group_by(ProductionSchedule.operation_code).limit(10)

            worst_result = await session.execute(worst_phases_query)
            phase_rows = worst_result.all()

            # Find phases where actual > standard (worst performers)
            slow_phases = []
            for row in phase_rows:
                if row.avg_std and row.avg_actual and row.avg_actual > 0:
                    phase_perf = min(100.0, (float(row.avg_std) / float(row.avg_actual)) * 100.0)
                    if phase_perf < 80.0:
                        slow_phases.append({"phase": row.operation_code, "performance": round(phase_perf, 1)})

            slow_phases.sort(key=lambda x: x["performance"])
            affected = [p["phase"] for p in slow_phases[:3]] or ["(sem dados por fase)"]

            return {
                "priority": 2,
                "category": "PERFORMANCE",
                "title": "Standard Work",
                "description": f"Standardizar processos de {', '.join(affected)} para melhorar taxa de desempenho de {performance:.1f}%.",
                "impact_metric": "performance",
                "impact_value": performance,
                "affected_phases": affected,
                "suggested_actions": [
                    f"Documentar procedimentos padrão para {affected[0]}",
                    "Criar checklists operacionais por fase",
                    "Implementar treino para operadores nas fases críticas",
                ],
                "data_evidence": {
                    "avg_standard_time": float(perf_row.avg_standard),
                    "avg_actual_time": float(perf_row.avg_actual),
                    "performance": performance,
                },
                "origins": ["SYSTEM_DATA", "BEST_PRACTICE"],
                "confidence": "MEDIUM_HIGH",
                "limitations": [
                    "Performance calculada a partir de tempo padrão vs real médio",
                    "Não considera variações sazonais ou contextuais",
                ],
                "next_steps": ["RUNBOOK", "INSTRUMENTATION"],
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Erro ao analisar performance: {e}")
        return None


async def _analyze_maintenance_needs(
    session: AsyncSession,
    tenant_id: UUID,
) -> Optional[Dict[str, Any]]:
    """
    Analisar necessidades de manutenção baseado em dados de erros reais.

    Queries the Factory Data Product semantic layer for quality events
    and identifies the top error types and affected phases.
    """
    try:
        # Try to get quality data from semantic layer (curated error data)
        try:
            from src.factory_data_product.services.semantic_queries_inmemory import SemanticQueriesInMemory
            sq = SemanticQueriesInMemory()
            quality_result = sq.quality_analysis()

            if quality_result and quality_result.get("status") != "BLOCKED":
                rows = quality_result.get("rows", [])
                if rows:
                    # Find top error types by count
                    top_errors = sorted(rows, key=lambda r: r.get("total_erros", 0), reverse=True)[:5]
                    top_phases = list({e.get("fase_nome", "Desconhecida") for e in top_errors if e.get("fase_nome")})
                    top_error_types = list({e.get("erro_tipo", "Desconhecido") for e in top_errors if e.get("erro_tipo")})
                    total_errors = sum(e.get("total_erros", 0) for e in top_errors)

                    return {
                        "priority": 3,
                        "category": "MAINTENANCE",
                        "title": "Manutenção Preventiva — Fases Críticas",
                        "description": (
                            f"As fases {', '.join(top_phases[:3])} concentram os tipos de erro "
                            f"mais frequentes ({', '.join(top_error_types[:3])}), "
                            f"totalizando {total_errors} ocorrências. "
                            f"Implementar manutenção preventiva e inspeções regulares."
                        ),
                        "impact_metric": "quality_errors",
                        "impact_value": total_errors,
                        "affected_phases": top_phases[:5],
                        "suggested_actions": [
                            f"Investigar causa-raiz do erro '{top_error_types[0]}'" if top_error_types else "Investigar erros mais frequentes",
                            "Criar calendário de manutenção preventiva para fases afetadas",
                            "Implementar checklist de inspeção visual pós-operação",
                            "Documentar histórico de problemas por molde/máquina",
                        ],
                        "data_evidence": {
                            "total_errors_top5": total_errors,
                            "top_error_types": top_error_types[:5],
                            "top_phases": top_phases[:5],
                            "source": "factory_data_product.quality_analysis",
                        },
                        "origins": ["SYSTEM_DATA", "BEST_PRACTICE"],
                        "confidence": "HIGH",
                        "limitations": [
                            "Análise limitada aos dados de erro do último ficheiro ingerido",
                        ],
                        "next_steps": ["RUNBOOK", "INSTRUMENTATION"],
                    }
        except ImportError:
            logger.debug("SemanticQueriesInMemory not available for maintenance analysis")
        except Exception as e:
            logger.debug(f"Semantic quality query failed: {e}")

        # Fallback: generic recommendation when no error data available
        return {
            "priority": 3,
            "category": "MAINTENANCE",
            "title": "Manutenção Moldes",
            "description": "Agendar inspeção/polimento regular de moldes. Sem dados de erros disponíveis para análise detalhada.",
            "impact_metric": "quality",
            "impact_value": 0.0,
            "affected_phases": [],
            "suggested_actions": [
                "Ingerir dados de erros (OrdemFabricoErros) para análise detalhada",
                "Criar calendário de manutenção preventiva de moldes",
            ],
            "data_evidence": {"note": "Sem dados de erros — recomendação genérica"},
            "origins": ["BEST_PRACTICE", "DATA_GAP"],
            "confidence": "LOW",
            "limitations": ["Sem dados de erros na base de dados"],
            "next_steps": ["INSTRUMENTATION"],
        }

    except Exception as e:
        logger.warning(f"Erro ao analisar manutenção: {e}")
        return None

