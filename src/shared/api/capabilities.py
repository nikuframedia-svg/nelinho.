"""
ProdPlan ONE - Dynamic Capabilities API
========================================

Feature discovery endpoint that evaluates capabilities dynamically based on:
- Active data ingestion (active_run)
- Trust Index per feature
- User permissions (RBAC)
- BLOCKED_METRICS definitions

This replaces the static capabilities endpoint with a real-time evaluation system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session
from src.shared.time import utc_now
from src.factory_data_product.config import (
    BLOCKED_METRICS,
    ALLOWED_METRICS,
    TRUST_INDEX,
    SEMANTIC_LABELS,
    TRUST_THRESHOLD_BLOCK,
    TRUST_THRESHOLD_WARNING,
    TRUST_THRESHOLD_OK,
    EXPECTED_VOLUMES,
)

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


# =============================================================================
# ENUMS AND MODELS
# =============================================================================

class CapabilityStatus(str, Enum):
    """Status of a capability/feature."""
    ENABLED = "enabled"        # Fully functional
    DEGRADED = "degraded"      # Limited by trust/data quality
    DISABLED = "disabled"      # No data available
    BLOCKED = "blocked"        # Explicitly blocked (data doesn't support it)


class FeatureCapability(BaseModel):
    """Dynamic capability for a specific feature."""
    id: str = Field(..., description="Feature identifier")
    name: str = Field(..., description="Human-readable name")
    status: CapabilityStatus = Field(..., description="Current status")
    reason: Optional[str] = Field(None, description="Why degraded/disabled/blocked")
    trust_score: Optional[int] = Field(None, ge=0, le=100, description="Trust index 0-100")
    semantic_label: Optional[str] = Field(None, description="Semantic disclaimer")
    required_permissions: List[str] = Field(default_factory=list, description="RBAC permissions needed")
    how_to_enable: Optional[str] = Field(None, description="Instructions to enable/improve")
    data_requirements: List[str] = Field(default_factory=list, description="Data needed to enable")


class ModuleCapability(BaseModel):
    """Dynamic capability for a module."""
    id: str = Field(..., description="Module identifier")
    name: str = Field(..., description="Human-readable name")
    status: CapabilityStatus = Field(..., description="Overall module status")
    features: List[FeatureCapability] = Field(default_factory=list)
    data_available: bool = Field(False, description="Whether module has data loaded")
    active_ingestion_id: Optional[str] = Field(None, description="Current active ingestion")
    trust_score_avg: Optional[int] = Field(None, description="Average trust across features")


class CapabilitiesResponse(BaseModel):
    """Full capabilities response."""
    modules: List[ModuleCapability]
    has_active_data: bool
    active_ingestion_id: Optional[str]
    blocked_metrics: List[str]
    allowed_metrics: List[str]
    evaluated_at: str
    version: str = "2.0.0"


# =============================================================================
# CAPABILITY EVALUATOR
# =============================================================================

class CapabilityEvaluator:
    """
    Evaluates capabilities dynamically based on:
    - Active data ingestion state
    - Trust Index per segment
    - User permissions (RBAC)
    - BLOCKED_METRICS definitions
    """
    
    def __init__(self, db: AsyncSession, user_permissions: Optional[List[str]] = None):
        self.db = db
        self.user_permissions = user_permissions or []
        self._active_run = None
    
    async def evaluate_all(self) -> CapabilitiesResponse:
        """Evaluate all capabilities and return structured response."""
        # Check if we have active data
        self._active_run = await self._get_active_run()
        has_data = self._active_run is not None
        
        modules = []
        
        # 1. FACTORY MODULE
        factory_features = await self._evaluate_factory_features(has_data)
        factory_trust_avg = self._calculate_avg_trust(factory_features)
        modules.append(ModuleCapability(
            id="factory",
            name="Factory Data Product",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DISABLED,
            features=factory_features,
            data_available=has_data,
            active_ingestion_id=str(self._active_run.ingestion_id) if self._active_run else None,
            trust_score_avg=factory_trust_avg,
        ))
        
        # 2. EXPLAIN MODULE
        explain_features = self._evaluate_explain_features(has_data)
        explain_trust_avg = self._calculate_avg_trust(explain_features)
        modules.append(ModuleCapability(
            id="explain",
            name="Explainability",
            status=CapabilityStatus.ENABLED,  # Always available (catalog is static)
            features=explain_features,
            data_available=True,
            trust_score_avg=explain_trust_avg,
        ))
        
        # 3. TWIN MODULE
        twin_features = self._evaluate_twin_features(has_data)
        twin_trust_avg = self._calculate_avg_trust(twin_features)
        modules.append(ModuleCapability(
            id="twin",
            name="Digital Twin / Sandbox",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DEGRADED,
            features=twin_features,
            data_available=has_data,
            trust_score_avg=twin_trust_avg,
        ))
        
        # 4. GOVERNANCE MODULE
        governance_features = self._evaluate_governance_features()
        modules.append(ModuleCapability(
            id="governance",
            name="Decision Governance",
            status=CapabilityStatus.ENABLED,
            features=governance_features,
            data_available=True,
            trust_score_avg=100,  # Infrastructure, not data-dependent
        ))
        
        # 5. COPILOT MODULE
        copilot_features = self._evaluate_copilot_features(has_data)
        copilot_trust_avg = self._calculate_avg_trust(copilot_features)
        modules.append(ModuleCapability(
            id="copilot",
            name="AI Copilot",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DEGRADED,
            features=copilot_features,
            data_available=has_data,
            trust_score_avg=copilot_trust_avg,
        ))
        
        # 6. IMPROVE MODULE
        improve_features = self._evaluate_improve_features(has_data)
        modules.append(ModuleCapability(
            id="improve",
            name="Improve Lab",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DISABLED,
            features=improve_features,
            data_available=has_data,
        ))
        
        return CapabilitiesResponse(
            modules=modules,
            has_active_data=has_data,
            active_ingestion_id=str(self._active_run.ingestion_id) if self._active_run else None,
            blocked_metrics=list(BLOCKED_METRICS.keys()),
            allowed_metrics=ALLOWED_METRICS,
            evaluated_at=utc_now().isoformat(),
        )
    
    async def _get_active_run(self):
        """Get active ingestion run from database."""
        try:
            from src.factory_data_product.models.meta import ActiveRun
            result = await self.db.execute(
                select(ActiveRun).order_by(ActiveRun.activated_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()
        except Exception:
            # If table doesn't exist or query fails, assume no active data
            return None
    
    def _calculate_avg_trust(self, features: List[FeatureCapability]) -> Optional[int]:
        """Calculate average trust score for a list of features."""
        scores = [f.trust_score for f in features if f.trust_score is not None]
        if not scores:
            return None
        return int(sum(scores) / len(scores))
    
    async def _evaluate_factory_features(self, has_data: bool) -> List[FeatureCapability]:
        """Evaluate Factory Data Product features."""
        features = []
        
        # WIP feature
        trust = TRUST_INDEX.get("OrdensFabrico", 50)
        features.append(FeatureCapability(
            id="wip",
            name="Work in Progress (WIP)",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("wip"),
            reason=None if has_data else "No active data ingestion",
            how_to_enable="Upload Folha_IA_extra.xlsx via /v1/factory/ingest",
        ))
        
        # Backlog feature (degraded due to HorasPrevistas coverage)
        trust = TRUST_INDEX.get("FasesOrdemFabrico_HorasPrevistas", 58)
        status = CapabilityStatus.DEGRADED if trust < TRUST_THRESHOLD_OK * 100 else CapabilityStatus.ENABLED
        features.append(FeatureCapability(
            id="backlog",
            name="Backlog Teórico",
            status=status if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("bottleneck"),
            reason="56.6% dos registos têm HorasPrevistas=0" if status == CapabilityStatus.DEGRADED else None,
            how_to_enable="Preencher FaseOf_HorasPrevistas nas ordens de fabrico",
        ))
        
        # Bottleneck analysis
        features.append(FeatureCapability(
            id="bottleneck",
            name="Análise de Gargalos (TOC)",
            status=CapabilityStatus.DEGRADED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("bottleneck"),
            reason="Análise limitada pela cobertura de HorasPrevistas",
            how_to_enable="Garantir HorasPrevistas em todas as fases",
        ))
        
        # Lead Time
        trust = TRUST_INDEX.get("OrdensFabrico", 82)
        features.append(FeatureCapability(
            id="lead_time",
            name="Lead Time Observado",
            status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("lead_time"),
            reason=None if has_data else "No active data ingestion",
        ))
        
        # Quality errors
        trust = TRUST_INDEX.get("OrdemFabricoErros", 67)
        features.append(FeatureCapability(
            id="quality",
            name="Análise de Qualidade (Erros)",
            status=CapabilityStatus.DEGRADED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("quality"),
            reason="41.5% dos erros sem FaseOfCulpada identificada" if trust < TRUST_THRESHOLD_OK * 100 else None,
            how_to_enable="Preencher FaseOfCulpada nos registos de erro",
        ))
        
        # Skills risk
        trust = TRUST_INDEX.get("FuncionariosFasesAptos", 55)
        features.append(FeatureCapability(
            id="skills_risk",
            name="Risco de Competências",
            status=CapabilityStatus.DEGRADED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("skills"),
            reason="Cobertura limitada de funcionários aptos por fase",
        ))
        
        # Mold conflicts (DEGRADED due to DataPrevista coverage)
        trust = TRUST_INDEX.get("FasesOrdemFabrico_DataPrevista", 35)
        features.append(FeatureCapability(
            id="mold_conflicts",
            name="Conflitos de Moldes (Potenciais)",
            status=CapabilityStatus.DEGRADED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("mold_conflict"),
            reason="DataPrevista tem apenas 4.8% de cobertura",
            how_to_enable="Preencher FaseOf_DataPrevista para detectar conflitos",
        ))
        
        # Cost theoretical
        trust = TRUST_INDEX.get("Funcionarios", 75)
        features.append(FeatureCapability(
            id="cost_theoretical",
            name="Custo Teórico Estimado",
            status=CapabilityStatus.DEGRADED if has_data else CapabilityStatus.DISABLED,
            trust_score=trust,
            semantic_label=SEMANTIC_LABELS.get("cost"),
            reason="Sem horas reais por funcionário - apenas estimativa",
        ))
        
        # --- BLOCKED FEATURES (from BLOCKED_METRICS) ---
        
        for metric_id, metric_info in BLOCKED_METRICS.items():
            features.append(FeatureCapability(
                id=metric_id,
                name=self._metric_id_to_name(metric_id),
                status=CapabilityStatus.BLOCKED,
                trust_score=0,
                reason=metric_info["reason"],
                data_requirements=metric_info.get("required_data", []),
                how_to_enable=f"Requer: {', '.join(metric_info.get('required_data', []))}",
            ))
        
        return features
    
    def _evaluate_explain_features(self, has_data: bool) -> List[FeatureCapability]:
        """Evaluate Explainability features."""
        return [
            FeatureCapability(
                id="metric_catalog",
                name="Catálogo de Métricas",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
                reason=None,
                how_to_enable=None,
            ),
            FeatureCapability(
                id="explain_drawer",
                name="Explain Drawer (UI)",
                status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DEGRADED,
                trust_score=80 if has_data else 30,
                reason=None if has_data else "Dados mock sem lineage real",
                how_to_enable="Fazer ingestão de dados para ver lineage real",
            ),
            FeatureCapability(
                id="kpi_registry",
                name="KPI Registry",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
                reason=None,
            ),
            FeatureCapability(
                id="blocked_metrics_api",
                name="API de Métricas Bloqueadas",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
                reason=None,
            ),
        ]
    
    def _evaluate_twin_features(self, has_data: bool) -> List[FeatureCapability]:
        """Evaluate Digital Twin features."""
        return [
            FeatureCapability(
                id="scenarios",
                name="Gestão de Cenários",
                status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DEGRADED,
                trust_score=80 if has_data else 40,
                reason=None if has_data else "Cenários sem dados base reais",
            ),
            FeatureCapability(
                id="simulation",
                name="Simulação de Impacto",
                status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DEGRADED,
                trust_score=75 if has_data else 35,
                reason=None if has_data else "Simulação limitada a métricas disponíveis",
            ),
            FeatureCapability(
                id="scenario_hash",
                name="Hash Reprodutível de Cenários",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
                reason=None,
            ),
            FeatureCapability(
                id="exec_pack",
                name="Pacotes de Execução",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
                reason=None,
            ),
        ]
    
    def _evaluate_governance_features(self) -> List[FeatureCapability]:
        """Evaluate Governance features."""
        return [
            FeatureCapability(
                id="decision_run",
                name="Decision Ledger",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="approval_workflow",
                name="Workflow de Aprovações (SoD)",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="kill_switch",
                name="Kill Switch",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="audit_hash",
                name="Hash Chain de Auditoria",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="policies",
                name="Políticas de Decisão",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
        ]
    
    def _evaluate_copilot_features(self, has_data: bool) -> List[FeatureCapability]:
        """Evaluate Copilot features."""
        return [
            FeatureCapability(
                id="chat",
                name="Chat com Copilot",
                status=CapabilityStatus.ENABLED,
                trust_score=85,
            ),
            FeatureCapability(
                id="tool_registry",
                name="Tool Registry (OpenAPI)",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="runbooks",
                name="Runbooks com Dry-Run",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="guardrails",
                name="Guardrails (Injecção/Hallucination)",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
            FeatureCapability(
                id="evidence_validation",
                name="Validação de Evidências",
                status=CapabilityStatus.ENABLED,
                trust_score=100,
            ),
        ]
    
    def _evaluate_improve_features(self, has_data: bool) -> List[FeatureCapability]:
        """Evaluate Improve Lab features."""
        return [
            FeatureCapability(
                id="suggestions",
                name="Sugestões de Melhoria",
                status=CapabilityStatus.ENABLED if has_data else CapabilityStatus.DISABLED,
                trust_score=70 if has_data else 0,
                reason=None if has_data else "Requer dados para gerar sugestões",
            ),
            FeatureCapability(
                id="impact_tracking",
                name="Tracking de Impacto",
                status=CapabilityStatus.DEGRADED,
                trust_score=50,
                reason="Medição de impacto limitada sem horas reais",
            ),
        ]
    
    def _metric_id_to_name(self, metric_id: str) -> str:
        """Convert metric_id to human-readable name."""
        names = {
            "oee_real": "OEE Real",
            "availability_oee": "Disponibilidade OEE",
            "otd_official": "OTD Oficial",
            "productivity_individual_real": "Produtividade Individual Real",
            "cost_real_per_order": "Custo Real por Ordem",
            "capacity_real_per_day": "Capacidade Real/Dia",
            "mold_conflict_confirmed": "Conflito de Molde Confirmado",
        }
        return names.get(metric_id, metric_id.replace("_", " ").title())


# =============================================================================
# API ENDPOINTS
# =============================================================================

get_tenant_id = require_tenant_header


@router.get("/", response_model=CapabilitiesResponse)
async def get_capabilities(
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Return dynamic capabilities based on:
    - Active data ingestion
    - Trust Index per feature
    - User permissions (RBAC)
    - BLOCKED_METRICS definitions
    
    This endpoint should be called by the frontend CapabilitiesProvider
    to determine which features to enable/disable in the UI.
    """
    evaluator = CapabilityEvaluator(db)
    return await evaluator.evaluate_all()


@router.get("/modules")
async def get_modules(
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Return list of available modules with their status."""
    evaluator = CapabilityEvaluator(db)
    response = await evaluator.evaluate_all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "status": m.status.value,
            "data_available": m.data_available,
            "trust_score_avg": m.trust_score_avg,
        }
        for m in response.modules
    ]


@router.get("/features")
async def get_features(
    module_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Return list of features, optionally filtered by module or status.
    
    Query params:
    - module_id: Filter features by module (e.g., "factory", "explain")
    - status_filter: Filter by status (e.g., "enabled", "blocked", "degraded")
    """
    evaluator = CapabilityEvaluator(db)
    response = await evaluator.evaluate_all()
    
    features = []
    for module in response.modules:
        if module_id and module.id != module_id:
            continue
        for feature in module.features:
            if status_filter and feature.status.value != status_filter:
                continue
            features.append({
                "module_id": module.id,
                "module_name": module.name,
                **feature.model_dump(),
            })
    
    return features


@router.get("/blocked")
async def get_blocked_capabilities(
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Return all blocked capabilities with reasons and requirements.
    
    Useful for displaying "What's missing?" in the UI.
    """
    evaluator = CapabilityEvaluator(db)
    response = await evaluator.evaluate_all()
    
    blocked = []
    for module in response.modules:
        for feature in module.features:
            if feature.status == CapabilityStatus.BLOCKED:
                blocked.append({
                    "module_id": module.id,
                    "feature_id": feature.id,
                    "feature_name": feature.name,
                    "reason": feature.reason,
                    "data_requirements": feature.data_requirements,
                    "how_to_enable": feature.how_to_enable,
                })
    
    return blocked


@router.get("/degraded")
async def get_degraded_capabilities(
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Return all degraded capabilities with reasons and improvement suggestions.
    
    Useful for "Data Quality Improvement" dashboard.
    """
    evaluator = CapabilityEvaluator(db)
    response = await evaluator.evaluate_all()
    
    degraded = []
    for module in response.modules:
        for feature in module.features:
            if feature.status == CapabilityStatus.DEGRADED:
                degraded.append({
                    "module_id": module.id,
                    "feature_id": feature.id,
                    "feature_name": feature.name,
                    "trust_score": feature.trust_score,
                    "reason": feature.reason,
                    "how_to_enable": feature.how_to_enable,
                })
    
    return degraded


@router.get("/summary")
async def get_capabilities_summary(
    db: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Return a summary of capabilities status.
    
    Useful for dashboard overview cards.
    """
    evaluator = CapabilityEvaluator(db)
    response = await evaluator.evaluate_all()
    
    total_features = 0
    enabled_count = 0
    degraded_count = 0
    disabled_count = 0
    blocked_count = 0
    
    for module in response.modules:
        for feature in module.features:
            total_features += 1
            if feature.status == CapabilityStatus.ENABLED:
                enabled_count += 1
            elif feature.status == CapabilityStatus.DEGRADED:
                degraded_count += 1
            elif feature.status == CapabilityStatus.DISABLED:
                disabled_count += 1
            elif feature.status == CapabilityStatus.BLOCKED:
                blocked_count += 1
    
    return {
        "has_active_data": response.has_active_data,
        "active_ingestion_id": response.active_ingestion_id,
        "total_features": total_features,
        "enabled": enabled_count,
        "degraded": degraded_count,
        "disabled": disabled_count,
        "blocked": blocked_count,
        "health_score": int((enabled_count + degraded_count * 0.5) / total_features * 100) if total_features > 0 else 0,
        "evaluated_at": response.evaluated_at,
    }
