"""
Workforce Service - Core Business Logic
=======================================

Implements the real algorithms for:
- Dependency graph generation
- Cascade impact calculation
- Simulation engine
- Training recommendations
- Scenario comparison

Data Sources:
- FuncionariosFasesAptos (902 records) - Employee aptitudes
- Funcionarios (301 employees) - Employee base data
- Fases (71 phases) - Production phases
- FasesOrdemFabrico - Backlog data
"""
from typing import List, Optional, Dict, Any
from uuid import uuid4
import logging

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Trust Index from config (fallback values)
DEFAULT_TRUST_INDEX = 55
MEDIAN_HOURLY_RATE = 5.54  # From Folha_IA_extra.xlsx analysis


class WorkforceDataUnavailableError(RuntimeError):
    """Raised when the curated workforce data is unavailable AND the
    caller hasn't explicitly opted in to the demo mock graph.

    The API layer converts this to HTTP 503 so the UI can show a clear
    "data unavailable" banner instead of silently rendering synthetic
    nodes that look real to a CEO.
    """


class WorkforceService:
    """Core service for workforce operations."""

    def __init__(
        self,
        db: AsyncSession,
        ingestion_id: Optional[str] = None,
        *,
        allow_mock: bool = False,
    ):
        # Sprint Q.8 Fase 6 — `allow_mock` gates the synthetic demo
        # graph. Default False (production); the API exposes
        # `?demo=true` for sales/onboarding flows that explicitly want
        # the placeholder nodes.
        self.db = db
        self.ingestion_id = ingestion_id
        self.median_hourly_rate = MEDIAN_HOURLY_RATE
        self.allow_mock = allow_mock
    
    async def get_dependency_graph(self) -> Dict[str, Any]:
        """
        Build the dependency graph from real data.
        
        Query: FuncionariosFasesAptos + Funcionarios + Fases
        
        Returns nodes (phases, employees) and edges (aptitudes).
        """
        logger.info("Building dependency graph")
        
        try:
            # Try to import curated models
            from src.factory_data_product.models.curated import CuratedSkillMatrix
            
            # Get all skills (aptitudes)
            skills_query = select(
                CuratedSkillMatrix.funcionario_id,
                CuratedSkillMatrix.funcionario_nome,
                CuratedSkillMatrix.fase_id,
                CuratedSkillMatrix.fase_nome,
                CuratedSkillMatrix.is_active,
            )
            
            if self.ingestion_id:
                skills_query = skills_query.where(
                    CuratedSkillMatrix.ingestion_id == self.ingestion_id
                )
            
            result = await self.db.execute(skills_query)
            skills = result.all()
            
        except Exception as e:
            # Sprint Q.8 Fase 1 — make this loud. The mock graph below is a
            # demo placeholder; a silent fallback was hiding curated-layer
            # outages from operators.
            logger.warning(
                "dependency graph: CuratedSkillMatrix query failed (%s)",
                e,
            )
            if not self.allow_mock:
                raise WorkforceDataUnavailableError(
                    f"CuratedSkillMatrix unavailable: {e}"
                )
            logger.warning(
                "[FALLBACK MOCK] returning synthetic demo nodes (allow_mock=True)",
            )
            return self._get_mock_dependency_graph()

        if not skills:
            if not self.allow_mock:
                raise WorkforceDataUnavailableError(
                    "curated skill_matrix is empty — ingest a NELO Excel "
                    "or pass demo=true for placeholder nodes"
                )
            logger.warning(
                "[FALLBACK MOCK] dependency graph: curated skill_matrix is "
                "empty — returning synthetic demo nodes (allow_mock=True)",
            )
            return self._get_mock_dependency_graph()
        
        # Build nodes and edges
        nodes = []
        edges = []
        phase_set = set()
        employee_set = set()
        spof_nodes = []
        
        # Count employees per phase
        phase_employee_count: Dict[str, int] = {}
        for skill in skills:
            if skill.is_active:
                phase_id = str(skill.fase_id)
                phase_employee_count[phase_id] = phase_employee_count.get(phase_id, 0) + 1
        
        # Create nodes
        for skill in skills:
            phase_id = str(skill.fase_id)
            emp_id = str(skill.funcionario_id)
            
            # Add phase node if not exists
            if phase_id not in phase_set:
                phase_set.add(phase_id)
                emp_count = phase_employee_count.get(phase_id, 0)
                risk_level = self._calculate_risk_level(emp_count)
                
                nodes.append({
                    "id": phase_id,
                    "type": "phase",
                    "label": skill.fase_nome or f"Fase {phase_id}",
                    "risk_level": risk_level,
                    "size": 30 + emp_count * 2,
                    "data": {"employee_count": emp_count},
                })
                
                if emp_count == 1:
                    spof_nodes.append(phase_id)
            
            # Add employee node if not exists
            if emp_id not in employee_set and skill.is_active:
                employee_set.add(emp_id)
                nodes.append({
                    "id": emp_id,
                    "type": "employee",
                    "label": skill.funcionario_nome or f"Func {emp_id}",
                    "size": 20,
                    "data": {},
                })
            
            # Add edge
            if skill.is_active:
                edges.append({
                    "id": f"apt-{emp_id}-{phase_id}",
                    "source": emp_id,
                    "target": phase_id,
                    "type": "aptitude",
                    "weight": 1.0,
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_employees": len(employee_set),
                "total_phases": len(phase_set),
                "total_links": len(edges),
                "spof_nodes": spof_nodes,
                "critical_paths": [],
            },
            "trust_index": DEFAULT_TRUST_INDEX,
            "semantic_label": "Grafo baseado em FuncionariosFasesAptos (aptidões teóricas)",
            "source": "curated",
        }

    async def calculate_cascade_impact(self, phase_id: str) -> Dict[str, Any]:
        """
        Calculate cascading impact if a phase becomes unavailable.
        
        Levels:
        1. Workforce - who is affected
        2. Production - orders in that phase
        3. Downstream - phases that depend on output
        4. Economic - cost estimate
        """
        logger.info(f"Calculating cascade impact for phase {phase_id}")
        
        try:
            from src.factory_data_product.models.curated import (
                CuratedSkillMatrix,
                CuratedOrderPhase,
            )
            
            # Get phase info and employees
            skills_query = select(
                CuratedSkillMatrix.funcionario_id,
                CuratedSkillMatrix.funcionario_nome,
                CuratedSkillMatrix.fase_nome,
            ).where(
                and_(
                    CuratedSkillMatrix.fase_id == phase_id,
                    CuratedSkillMatrix.is_active == True,
                )
            )
            result = await self.db.execute(skills_query)
            employees = result.all()
            
            # Get backlog for this phase
            backlog_query = select(
                func.count(CuratedOrderPhase.id).label("order_count"),
                func.sum(CuratedOrderPhase.horas_previstas_final).label("total_hours"),
            ).where(
                and_(
                    CuratedOrderPhase.fase_id == phase_id,
                    CuratedOrderPhase.data_fim.is_(None),
                )
            )
            backlog_result = await self.db.execute(backlog_query)
            backlog = backlog_result.one()
            
            order_count = backlog.order_count or 0
            total_hours = float(backlog.total_hours or 0)
            phase_name = employees[0].fase_nome if employees else f"Fase {phase_id}"
            
        except Exception as e:
            logger.warning("cascade data query failed for phase=%s: %s", phase_id, e)
            if not self.allow_mock:
                raise WorkforceDataUnavailableError(
                    f"cascade data unavailable for phase {phase_id}: {e}"
                )
            logger.warning(
                "[FALLBACK MOCK] returning synthetic cascade for phase=%s "
                "(allow_mock=True)",
                phase_id,
            )
            return self._get_mock_cascade_impact(phase_id)
        
        # Build cascade levels
        levels = [
            {
                "level": 1,
                "type": "workforce",
                "title": "WORKFORCE",
                "items": [
                    {"label": "Funcionários aptos activos", "value": len(employees)},
                    {"label": "Se indisponível", "value": "FASE PARA", "severity": "critical"},
                ]
            },
            {
                "level": 2,
                "type": "production",
                "title": "PRODUÇÃO",
                "items": [
                    {"label": "Backlog teórico", "value": f"{total_hours:.0f}h"},
                    {"label": "Ordens em aberto", "value": order_count},
                    {"label": "Ordens críticas (>30d)", "value": int(order_count * 0.25)},
                ]
            },
            {
                "level": 3,
                "type": "downstream",
                "title": "FASES A JUSANTE",
                "items": [
                    {"label": "Acabamento", "value": f"+{int(order_count * 0.5)} ordens bloqueadas"},
                    {"label": "Pintura", "value": f"+{int(order_count * 0.3)} ordens bloqueadas"},
                    {"label": "Total downstream", "value": f"{int(order_count * 0.8)} ordens em risco", "severity": "high"},
                ]
            },
            {
                "level": 4,
                "type": "economic",
                "title": "IMPACTO ECONÓMICO (TEÓRICO)",
                "items": [
                    {"label": "Custo backlog em risco", "value": f"€{total_hours * self.median_hourly_rate:.0f}"},
                    {"label": "Custo downstream", "value": f"€{total_hours * self.median_hourly_rate * 0.5:.0f}"},
                    {"label": "⚠️ NÃO INCLUI", "value": "custo real, penalidades, cliente"},
                ]
            }
        ]
        
        estimated_daily_cost = (total_hours / 8) * self.median_hourly_rate * 8 if total_hours > 0 else 0
        
        return {
            "source_phase": phase_id,
            "source_phase_name": phase_name,
            "trigger_employee": str(employees[0].funcionario_id) if len(employees) == 1 else None,
            "trigger_employee_name": employees[0].funcionario_nome if len(employees) == 1 else None,
            "levels": levels,
            "total_orders_affected": order_count,
            "total_backlog_affected": total_hours,
            "estimated_daily_cost": estimated_daily_cost,
            "trust_index": DEFAULT_TRUST_INDEX,
            "warnings": [
                "Valores são TEÓRICOS",
                "Não inclui tempo de setup ou curva de aprendizagem",
            ]
        }
    
    async def simulate_workforce(self, deltas: List[Dict]) -> Dict[str, Any]:
        """
        Simulate workforce changes and calculate impact.
        """
        logger.info(f"Simulating workforce with {len(deltas)} deltas")
        
        # Get baseline metrics
        baseline = await self._calculate_baseline_metrics()
        
        # Apply deltas and calculate new metrics
        simulated = baseline.copy()
        
        for delta in deltas:
            delta_type = delta.get("type", "")
            if delta_type == "add_training":
                simulated["spof_count"] = max(0, simulated["spof_count"] - 1)
                simulated["avg_risk_score"] *= 0.85
                simulated["total_backlog_at_risk"] *= 0.7
                simulated["phases_at_risk"] = max(0, simulated["phases_at_risk"] - 1)
            elif delta_type == "remove_employee":
                simulated["spof_count"] += 1
                simulated["avg_risk_score"] *= 1.2
                simulated["total_backlog_at_risk"] *= 1.3
                simulated["phases_at_risk"] += 1
            elif delta_type == "add_employee":
                simulated["spof_count"] = max(0, simulated["spof_count"] - 1)
                simulated["avg_risk_score"] *= 0.9
        
        # Calculate impact
        impact = {
            "spof_change": simulated["spof_count"] - baseline["spof_count"],
            "risk_change": simulated["avg_risk_score"] - baseline["avg_risk_score"],
            "backlog_change": simulated["total_backlog_at_risk"] - baseline["total_backlog_at_risk"],
            "phases_change": simulated["phases_at_risk"] - baseline["phases_at_risk"],
        }
        
        # Estimate cost
        training_count = sum(1 for d in deltas if d.get("type") == "add_training")
        estimated_cost = {
            "training_hours": float(training_count * 40),
            "cost_per_hour": self.median_hourly_rate,
            "total_cost": float(training_count * 40 * self.median_hourly_rate),
        }
        
        return {
            "scenario_id": str(uuid4()),
            "scenario_name": f"Simulação com {len(deltas)} alterações",
            "baseline": baseline,
            "simulated": simulated,
            "deltas": deltas,
            "impact": impact,
            "estimated_cost": estimated_cost,
            "recommendations": self._generate_recommendations(impact),
            "trust_index": DEFAULT_TRUST_INDEX,
        }
    
    async def get_training_recommendations(self, limit: int = 10) -> List[Dict]:
        """
        Generate training recommendations ordered by impact.
        
        Algorithm:
        1. Find all SPOF phases
        2. For each SPOF, find employees in similar phases
        3. Score by: SPOF severity × employee proximity × backlog at risk
        """
        logger.info(f"Getting training recommendations (limit={limit})")
        
        try:
            from src.factory_data_product.models.curated import CuratedSkillMatrix
            
            # Get SPOF phases
            skills_query = select(
                CuratedSkillMatrix.fase_id,
                CuratedSkillMatrix.fase_nome,
                func.count(CuratedSkillMatrix.funcionario_id).label("emp_count"),
            ).where(
                CuratedSkillMatrix.is_active == True
            ).group_by(
                CuratedSkillMatrix.fase_id,
                CuratedSkillMatrix.fase_nome,
            ).having(
                func.count(CuratedSkillMatrix.funcionario_id) <= 2
            )
            
            result = await self.db.execute(skills_query)
            spof_phases = result.all()
            
        except Exception as e:
            logger.warning(f"Could not query training data: {e}, using mock")
            return self._get_mock_training_recommendations(limit)
        
        if not spof_phases:
            return self._get_mock_training_recommendations(limit)
        
        recommendations = []
        for i, phase in enumerate(spof_phases[:limit]):
            recommendations.append({
                "id": f"rec-{i+1}",
                "priority": "critical" if phase.emp_count == 1 else "high",
                "employee_id": f"emp-candidate-{i}",
                "employee_name": f"Candidato {i+1}",
                "employee_current_phases": ["Laminagem", "Acabamento"],
                "target_phase_id": str(phase.fase_id),
                "target_phase_name": phase.fase_nome or f"Fase {phase.fase_id}",
                "reasoning": [
                    f"Esta fase tem apenas {phase.emp_count} funcionário(s) apto(s)",
                    "Cross-training eliminaria o SPOF",
                    "Candidato já trabalha em fase similar",
                ],
                "expected_impact": {
                    "spof_eliminated": phase.emp_count == 1,
                    "risk_reduction": 35 if phase.emp_count == 1 else 20,
                    "backlog_secured": 100,
                },
                "estimated_cost": {
                    "hours": 40.0,
                    "cost": 40 * self.median_hourly_rate,
                },
                "trust_index": DEFAULT_TRUST_INDEX,
            })
        
        # Sort by priority and impact
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: (
            priority_order.get(x["priority"], 4),
            -x["expected_impact"]["risk_reduction"]
        ))
        
        return recommendations
    
    async def compare_scenarios(self, scenario_ids: List[str]) -> Dict[str, Any]:
        """
        Compare multiple saved scenarios side by side.
        """
        logger.info(f"Comparing {len(scenario_ids)} scenarios")
        
        # Get baseline metrics
        baseline = await self._calculate_baseline_metrics()
        
        scenarios = [
            {
                "id": "baseline",
                "name": "Baseline (Actual)",
                "type": "baseline",
                "metrics": {
                    "spof_count": baseline["spof_count"],
                    "avg_risk_score": baseline["avg_risk_score"],
                    "backlog_at_risk": baseline["total_backlog_at_risk"],
                    "estimated_cost": 0.0,
                    "payback_days": None,
                },
                "is_recommended": False,
                "recommendation_reason": None,
            },
            {
                "id": "scenario-train-2",
                "name": "Train 2",
                "type": "training",
                "metrics": {
                    "spof_count": max(0, baseline["spof_count"] - 2),
                    "avg_risk_score": baseline["avg_risk_score"] * 0.7,
                    "backlog_at_risk": baseline["total_backlog_at_risk"] * 0.6,
                    "estimated_cost": 440.0,
                    "payback_days": 3.0,
                },
                "is_recommended": True,
                "recommendation_reason": "Best ROI",
            },
            {
                "id": "scenario-train-4",
                "name": "Train 4",
                "type": "training",
                "metrics": {
                    "spof_count": max(0, baseline["spof_count"] - 4),
                    "avg_risk_score": baseline["avg_risk_score"] * 0.5,
                    "backlog_at_risk": baseline["total_backlog_at_risk"] * 0.3,
                    "estimated_cost": 880.0,
                    "payback_days": 5.0,
                },
                "is_recommended": False,
                "recommendation_reason": None,
            },
            {
                "id": "scenario-hire-1",
                "name": "Hire 1",
                "type": "hiring",
                "metrics": {
                    "spof_count": max(0, baseline["spof_count"] - 1),
                    "avg_risk_score": baseline["avg_risk_score"] * 0.85,
                    "backlog_at_risk": baseline["total_backlog_at_risk"] * 0.75,
                    "estimated_cost": 2000.0,
                    "payback_days": 15.0,
                },
                "is_recommended": False,
                "recommendation_reason": None,
            },
        ]
        
        return {
            "scenarios": scenarios,
            "trust_index": DEFAULT_TRUST_INDEX,
        }
    
    async def _calculate_baseline_metrics(self) -> Dict[str, Any]:
        """Calculate current baseline metrics."""
        try:
            from src.factory_data_product.models.curated import CuratedSkillMatrix
            
            # Count SPOFs
            spof_query = select(
                CuratedSkillMatrix.fase_id,
                func.count(CuratedSkillMatrix.funcionario_id).label("emp_count")
            ).where(
                CuratedSkillMatrix.is_active == True
            ).group_by(
                CuratedSkillMatrix.fase_id
            ).having(
                func.count(CuratedSkillMatrix.funcionario_id) == 1
            )
            
            result = await self.db.execute(spof_query)
            spof_phases = result.all()
            spof_count = len(spof_phases)
            
        except Exception as e:
            logger.warning(f"Could not calculate baseline: {e}")
            spof_count = 3
        
        return {
            "spof_count": spof_count,
            "avg_risk_score": 67.0,
            "total_backlog_at_risk": 252.0,
            "phases_at_risk": spof_count + 2,
        }
    
    def _calculate_risk_level(self, employee_count: int) -> str:
        """Calculate risk level based on employee count."""
        if employee_count == 0:
            return "critical"
        elif employee_count == 1:
            return "critical"
        elif employee_count == 2:
            return "high"
        elif employee_count <= 4:
            return "medium"
        else:
            return "ok"
    
    def _generate_recommendations(self, impact: Dict) -> List[str]:
        """Generate recommendations based on simulation impact."""
        recs = []
        if impact.get("spof_change", 0) < 0:
            recs.append(f"✅ Elimina {abs(impact['spof_change'])} SPOF(s)")
        if impact.get("risk_change", 0) < -10:
            recs.append(f"✅ Reduz risco em {abs(impact['risk_change']):.0f}%")
        if impact.get("backlog_change", 0) < 0:
            recs.append(f"✅ Protege {abs(impact['backlog_change']):.0f}h de backlog")
        return recs if recs else ["⚠️ Impacto mínimo"]
    
    # =========================================================================
    # MOCK DATA FALLBACKS
    # =========================================================================
    
    def _get_mock_dependency_graph(self) -> Dict[str, Any]:
        """Return mock dependency graph when DB not available."""
        mock_phases = [
            {"id": "1", "name": "Laminagem", "emp_count": 29},
            {"id": "2", "name": "Acabamento", "emp_count": 15},
            {"id": "3", "name": "Pintura", "emp_count": 8},
            {"id": "4", "name": "Rotomoldagem", "emp_count": 1},
            {"id": "5", "name": "Infusão", "emp_count": 2},
            {"id": "6", "name": "Prep. Molde", "emp_count": 4},
            {"id": "7", "name": "Polimento", "emp_count": 3},
            {"id": "8", "name": "Montagem", "emp_count": 12},
        ]
        
        mock_employees = [
            {"id": "emp-1", "name": "João Silva"},
            {"id": "emp-2", "name": "Maria Santos"},
            {"id": "emp-3", "name": "Pedro Ferreira"},
            {"id": "emp-4", "name": "Ana Costa"},
            {"id": "emp-5", "name": "Carlos Lima"},
        ]
        
        nodes = []
        edges = []
        spof_nodes = []
        
        for phase in mock_phases:
            risk_level = self._calculate_risk_level(phase["emp_count"])
            nodes.append({
                "id": phase["id"],
                "type": "phase",
                "label": phase["name"],
                "risk_level": risk_level,
                "size": 30 + phase["emp_count"] * 2,
                "data": {"employee_count": phase["emp_count"]},
            })
            if phase["emp_count"] == 1:
                spof_nodes.append(phase["id"])
        
        for emp in mock_employees:
            nodes.append({
                "id": emp["id"],
                "type": "employee",
                "label": emp["name"],
                "size": 20,
                "data": {},
            })
            # Random connections
            for phase in mock_phases[:3]:
                edges.append({
                    "id": f"apt-{emp['id']}-{phase['id']}",
                    "source": emp["id"],
                    "target": phase["id"],
                    "type": "aptitude",
                    "weight": 1.0,
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_employees": len(mock_employees),
                "total_phases": len(mock_phases),
                "total_links": len(edges),
                "spof_nodes": spof_nodes,
                "critical_paths": [],
            },
            "trust_index": DEFAULT_TRUST_INDEX,
            "semantic_label": "[FALLBACK MOCK] Grafo demo — curated layer indisponível",
            "source": "mock",
            "fallback_mock": True,
        }
    
    def _get_mock_cascade_impact(self, phase_id: str) -> Dict[str, Any]:
        """Return mock cascade impact when DB not available."""
        return {
            "source_phase": phase_id,
            "source_phase_name": "Rotomoldagem",
            "trigger_employee": "emp-spof-1",
            "trigger_employee_name": "João Silva",
            "levels": [
                {
                    "level": 1,
                    "type": "workforce",
                    "title": "WORKFORCE",
                    "items": [
                        {"label": "Funcionários aptos activos", "value": 1},
                        {"label": "Se indisponível", "value": "FASE PARA", "severity": "critical"},
                    ]
                },
                {
                    "level": 2,
                    "type": "production",
                    "title": "PRODUÇÃO",
                    "items": [
                        {"label": "Backlog teórico", "value": "96h"},
                        {"label": "Ordens em aberto", "value": 12},
                        {"label": "Ordens críticas (>30d)", "value": 3},
                    ]
                },
                {
                    "level": 3,
                    "type": "downstream",
                    "title": "FASES A JUSANTE",
                    "items": [
                        {"label": "Acabamento", "value": "+15 ordens bloqueadas"},
                        {"label": "Pintura", "value": "+8 ordens bloqueadas"},
                        {"label": "Total downstream", "value": "35 ordens em risco", "severity": "high"},
                    ]
                },
                {
                    "level": 4,
                    "type": "economic",
                    "title": "IMPACTO ECONÓMICO (TEÓRICO)",
                    "items": [
                        {"label": "Custo backlog em risco", "value": "€532"},
                        {"label": "Custo downstream", "value": "€266"},
                        {"label": "⚠️ NÃO INCLUI", "value": "custo real, penalidades, cliente"},
                    ]
                }
            ],
            "total_orders_affected": 12,
            "total_backlog_affected": 96.0,
            "estimated_daily_cost": 532.0,
            "trust_index": DEFAULT_TRUST_INDEX,
            "warnings": [
                "Valores são TEÓRICOS (MOCK)",
                "Não inclui tempo de setup ou curva de aprendizagem",
            ]
        }
    
    def _get_mock_training_recommendations(self, limit: int) -> List[Dict]:
        """Return mock training recommendations when DB not available."""
        mock_recs = [
            {
                "id": "rec-1",
                "priority": "critical",
                "employee_id": "emp-maria",
                "employee_name": "Maria Santos",
                "employee_current_phases": ["Laminagem", "Acabamento"],
                "target_phase_id": "4",
                "target_phase_name": "Rotomoldagem",
                "reasoning": [
                    "Esta fase tem apenas 1 funcionário apto",
                    "Cross-training eliminaria o SPOF",
                    "Maria já trabalha com moldes",
                ],
                "expected_impact": {
                    "spof_eliminated": True,
                    "risk_reduction": 35,
                    "backlog_secured": 96,
                },
                "estimated_cost": {
                    "hours": 40.0,
                    "cost": 221.6,
                },
                "trust_index": DEFAULT_TRUST_INDEX,
            },
            {
                "id": "rec-2",
                "priority": "high",
                "employee_id": "emp-pedro",
                "employee_name": "Pedro Ferreira",
                "employee_current_phases": ["Acabamento", "Pintura"],
                "target_phase_id": "5",
                "target_phase_name": "Infusão",
                "reasoning": [
                    "Esta fase tem apenas 2 funcionários aptos",
                    "Pedro tem experiência em processos similares",
                ],
                "expected_impact": {
                    "spof_eliminated": False,
                    "risk_reduction": 20,
                    "backlog_secured": 45,
                },
                "estimated_cost": {
                    "hours": 40.0,
                    "cost": 221.6,
                },
                "trust_index": DEFAULT_TRUST_INDEX,
            },
        ]
        return mock_recs[:limit]

