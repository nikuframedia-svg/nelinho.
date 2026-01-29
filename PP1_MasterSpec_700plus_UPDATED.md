# Master Spec Palantir‑Level — ProdPlan ONE / PP1 (até C30) + Governação FE↔BE + LLM‑Ready

**Data de compilação:** 2026-01-28
**Última actualização:** 2026-01-28 (com análise extensiva do backend)

Este documento consolida, ao milímetro, tudo o que o software deve ter com base em TODO o historial deste chat.
É escrito para ser colado no Cursor como contexto e como lista de requisitos implementáveis.

**Âmbito incluído:**
- Dataset kayaks (Excel) e limitações operacionais reais.
- Modelo PP1 (Decision OS) e ciclo fechado: Sense→Normalize→Twin→Decide→Sandbox→(Deploy/Observe/Learn).
- Factory Data Product (DB separada) + Explainability + Twin/Sandbox (C30).
- Governação FE↔BE (contracts, CI gates, E2E smoke, zero mock).
- LLM readiness (tool registry, deny‑by‑default, evidence required, dry-run enforcement).
- **NOVO:** Workforce Operations System (Dependency Graph, Risk Heatmap, Simulator, Training Recommendations).

**Âmbito excluído (por decisão de faseamento):** C40–C70 como produto completo (prescriptive engine avançado, execução automática, generative UI total).
Mesmo assim, o sistema aqui descrito já tem de ficar preparado para esses passos, sem os implementar integralmente.

---

## 🔥 SECÇÃO NOVA: Backend Implementation Reality (Janeiro 2026)

### BE.0 — Estado Actual da Implementação

#### Módulos Backend Implementados

| Módulo | Path | Estado | Endpoints |
|--------|------|--------|-----------|
| Factory Data Product | `src/factory_data_product/` | ✅ Implementado | `/v1/factory/*` |
| Explain | `src/explain/` | ✅ Implementado | `/v1/explain/*` |
| Twin/Sandbox | `src/twin/` | ✅ Implementado | `/v1/twin/*` |
| Governance | `src/governance/` | ✅ Implementado | `/v1/governance/*` |
| Copilot | `src/copilot/` | ✅ Implementado | `/api/copilot/*` |
| Workforce | `src/workforce/` | ✅ NOVO | `/v1/workforce/*` |
| DQA | `src/dqa/` | ⚠️ Parcial | (TrustIndex Calculator) |
| Capabilities | `src/shared/api/capabilities.py` | ✅ Implementado | `/capabilities/*` |

#### Ficheiros Críticos do Backend

```
src/
├── main.py                          # FastAPI entry point com todos os routers
├── shared/
│   ├── config.py                    # Configuração centralizada (pydantic-settings)
│   ├── database.py                  # SQLAlchemy 2.0 async setup
│   └── api/
│       └── capabilities.py          # Dynamic capability evaluation
├── factory_data_product/
│   ├── api/
│   │   └── endpoints.py             # Semantic queries + ingestion + meta
│   ├── models/
│   │   ├── meta.py                  # IngestionRun, ActiveRun, QualityCheckResult
│   │   └── curated.py               # Order, OrderPhase, Mold, SkillMatrix, etc.
│   └── config.py                    # TRUST_INDEX, BLOCKED_METRICS, thresholds
├── explain/
│   ├── api.py                       # /v1/explain/* endpoints
│   ├── catalog.py                   # METRIC_CATALOG completo
│   └── models/
│       └── explained_value.py       # ExplainedValue canónico
├── twin/
│   └── api.py                       # Scenarios, simulation, comparison
├── governance/
│   ├── api.py                       # Decision lifecycle endpoints
│   ├── service.py                   # SoD, hash chain, kill switch
│   └── models.py                    # DecisionRun, Approval, DecisionPolicy
├── copilot/
│   ├── api.py                       # Ask, action, suggestions, conversations
│   ├── service.py                   # Full orchestration (1200+ lines)
│   ├── guardrails.py                # Security, validation
│   ├── rag.py                       # RAG retrieval
│   ├── ollama_client.py             # LLM integration
│   └── context_builder.py           # Context facts building
├── workforce/                       # NOVO: Workforce Operations System
│   ├── api.py                       # 5 endpoints
│   ├── service.py                   # Core business logic
│   └── models.py                    # Pydantic models
└── dqa/
    └── trust_index.py               # TrustIndex calculator (4 components)
```

---

## BE.1 — Configuração Backend (src/shared/config.py)

### Configuração via pydantic-settings

```python
class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://prodplan:***@localhost:5432/prodplan_one"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    
    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    api_key_header: str = "X-API-Key"
    
    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Copilot/LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"
    copilot_embeddings_model: str = "all-minilm"
    copilot_rate_limit_per_hour: int = 60
    copilot_rate_limit_per_day: int = 300
    copilot_trust_index_threshold: float = 0.6
```

### Variáveis de Ambiente Obrigatórias

| Variável | Descrição | Default |
|----------|-----------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | localhost:5432 |
| `SECRET_KEY` | JWT signing key | **REQUIRED** |
| `OLLAMA_BASE_URL` | URL do Ollama local | http://localhost:11434 |
| `OLLAMA_MODEL` | Modelo LLM a usar | llama3:8b |
| `REDIS_URL` | Redis para cache/rate limiting | localhost:6379 |

---

## BE.2 — Factory Data Product (Implementação Real)

### BE.2.1 — Schemas PostgreSQL

```
factory_raw        # Append-only raw data
factory_curated    # Transformed business entities
factory_meta       # Ingestion runs, quality checks, activation history
factory_semantic   # Views para UI/LLM consumption
```

### BE.2.2 — Modelos Curated (src/factory_data_product/models/curated.py)

| Modelo | Tabela | Campos Chave | PII/Sensitive |
|--------|--------|--------------|---------------|
| `CuratedOrder` | `factory_curated.order` | of_id, produto_id, modelo_id, data_entrada, data_conclusao, quantidade, estado | Não |
| `CuratedOrderPhase` | `factory_curated.order_phase` | of_id, fase_id, horas_previstas, horas_reais, horas_finais, estado, molde_id | Não |
| `CuratedPhaseCapacity` | `factory_curated.phase_capacity` | fase_id, periodo, capacidade_horas, funcionarios_count | Não |
| `CuratedMold` | `factory_curated.mold` | molde_id, molde_nome, modelo_id, tipo, estado, em_manutencao | Não |
| `CuratedMoldUsage` | `factory_curated.mold_usage` | molde_id, of_id, fase_id, data_uso | Não |
| `CuratedQualityEvent` | `factory_curated.quality_event` | of_id, fase_id, erro_tipo, erro_descricao, quantidade, molde_id | Não |
| `CuratedSkillMatrix` | `factory_curated.skill_matrix` | funcionario_id, funcionario_nome, fase_id, apto, nivel | **PII** |
| `CuratedCostReference` | `factory_curated.cost_reference` | centro_custo, fase_id, valor_hora_eur | **Sensitive** |

### BE.2.3 — QuarantineMixin (para todos os modelos curated)

```python
class QuarantineMixin:
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    quarantine_code: Optional[str] = None  # e.g., INVALID_TIMING, MISSING_KEY
    quarantined_at: Optional[datetime] = None
```

### BE.2.4 — Modelos Meta (src/factory_data_product/models/meta.py)

| Modelo | Descrição | Estados |
|--------|-----------|---------|
| `IngestionRun` | Track de cada ingestão | RECEIVED, VALIDATING, FAILED, CURATING, SUCCEEDED, SKIPPED |
| `ActiveRun` | Singleton apontando para ingestão ativa | N/A (singleton) |
| `ActivationHistory` | Histórico de activações/rollbacks | N/A (audit log) |
| `QualityCheckResult` | Resultado de cada quality check | BLOCKING, WARNING, INFO |

### BE.2.5 — Trust Index por Segmento (src/factory_data_product/config.py)

```python
TRUST_INDEX: Dict[str, int] = {
    "Erros": 92,
    "Fases": 85,
    "OrdensFabrico": 82,
    "Funcionarios": 75,
    "Moldes": 70,
    "Modelos": 75,
    "FasesOrdemFabrico_structure": 80,
    "FasesOrdemFabrico_HorasPrevistas": 58,
    "FasesOrdemFabrico_DataPrevista": 35,       # ⚠️ CRÍTICO: 4.8% coverage
    "FasesOrdemFabrico_Tempos": 62,
    "FasesStandardModelos": 60,
    "FuncionariosFaseOrdemFabrico": 55,
    "FuncionariosFasesAptos": 55,
    "OrdemFabricoErros": 67,
}
```

### BE.2.6 — Métricas Bloqueadas (BLOCKED_METRICS)

```python
BLOCKED_METRICS = {
    "oee_real": {
        "reason": "Não existem dados de paragens/máquinas",
        "required_data": ["machine_downtime", "planned_production_time"],
    },
    "availability_oee": {
        "reason": "Não existe tempo disponível vs planeado",
        "required_data": ["machine_status", "production_calendar"],
    },
    "otd_official": {
        "reason": "Não existe due_date/promessa comercial",
        "required_data": ["customer_promised_date", "actual_delivery_date"],
    },
    "productivity_individual_real": {
        "reason": "Não existem horas reais por funcionário",
        "required_data": ["employee_actual_hours", "employee_output"],
    },
    "cost_real_per_order": {
        "reason": "Não existem horas reais para calcular custo",
        "required_data": ["actual_hours_by_employee", "labor_cost_rates"],
    },
    "capacity_real_per_day": {
        "reason": "Não existe calendário produtivo real",
        "required_data": ["shift_calendar", "machine_availability"],
    },
    "mold_conflict_confirmed": {
        "reason": "DataPrevista tem apenas 4.8% de cobertura",
        "required_data": ["complete_scheduling_data"],
    },
}
```

### BE.2.7 — Métricas Permitidas (ALLOWED_METRICS)

```python
ALLOWED_METRICS = [
    "wip_theoretical",
    "backlog_theoretical_hours",
    "bottleneck_score_theoretical",
    "lead_time_historical",
    "quality_error_count",
    "quality_error_rate",
    "mold_conflict_potential",
    "skills_risk_score",
    "cost_theoretical_estimated",
]
```

### BE.2.8 — Semantic Labels

```python
SEMANTIC_LABELS = {
    "wip": "WIP teórico (ordens sem DataAcabamento)",
    "bottleneck": "Gargalo provável (backlog ÷ capacidade) — NÃO CONFIRMADO",
    "quality": "Dados de qualidade (limitado pela cobertura de FaseOfCulpada)",
    "lead_time": "Lead time histórico (DataAcabamento - DataCriacao)",
    "skills": "Risco de competências (baseado em FuncionariosFasesAptos)",
    "mold_conflict": "Conflitos POTENCIAIS (DataPrevista tem ~4.8% cobertura)",
    "cost": "Custo TEÓRICO estimado (ValorHora × HorasPrevistas) — NÃO REAL",
}
```

---

## BE.3 — Endpoints Semânticos (Implementados)

### GET /v1/factory/semantic/queries/wip

```python
@router.get("/semantic/queries/wip")
async def get_wip():
    return SemanticQueryResponse(
        data={
            "open_orders": 1523,
            "open_phases_total": 8456,
            "total_horas_previstas": 12450.5,
        },
        data_confidence=64.0,
        trust_status="WARNING",
        semantic_label="WIP teórico (ordens sem DataAcabamento)",
        metadata={
            "query_time": datetime.utcnow().isoformat(),
            "horas_previstas_coverage_pct": 43.4,
        },
    )
```

### GET /v1/factory/semantic/queries/backlog

```python
@router.get("/semantic/queries/backlog")
async def get_backlog():
    return SemanticQueryResponse(
        data={
            "total_backlog_hours": 4521.5,
            "phases_with_backlog": 45,
            "critical_phases": [...],
        },
        data_confidence=58.0,
        trust_status="WARNING",
        semantic_label="Backlog teórico (HorasPrevistas ÷ Capacidade)",
    )
```

### GET /v1/factory/semantic/queries/bottlenecks

```python
@router.get("/semantic/queries/bottlenecks")
async def get_bottlenecks(min_backlog_days: float = 5.0):
    return SemanticQueryResponse(
        data={
            "bottleneck_phases": [...],
            "total_bottleneck_hours": 1234.5,
        },
        data_confidence=58.0,
        trust_status="WARNING",
        semantic_label="Gargalos prováveis (backlog_days > threshold)",
    )
```

### GET /v1/factory/semantic/queries/quality

```python
@router.get("/semantic/queries/quality")
async def get_quality():
    return SemanticQueryResponse(
        data={
            "total_errors": 89836,
            "errors_without_culpada": 37303,
            "culpada_coverage_pct": 58.5,
            "top_error_types": [...],
        },
        data_confidence=67.0,
        trust_status="WARNING",
    )
```

### GET /v1/factory/semantic/queries/mold-conflicts

```python
@router.get("/semantic/queries/mold-conflicts")
async def get_mold_conflicts(occupancy_hours: int = 12):
    return SemanticQueryResponse(
        data={
            "potential_conflicts": [...],
            "total_molds_with_conflicts": 0,
            "warning": "DataPrevista tem apenas 4.8% de cobertura",
        },
        data_confidence=35.0,
        trust_status="DEGRADED",
    )
```

### GET /v1/factory/semantic/queries/skills-risk

```python
@router.get("/semantic/queries/skills-risk")
async def get_skills_risk():
    return SemanticQueryResponse(
        data={
            "phases_at_risk": [...],
            "spof_count": 3,
            "total_employees_active": 129,
        },
        data_confidence=55.0,
        trust_status="WARNING",
    )
```

---

## BE.4 — Explain Module (Implementação Completa)

### BE.4.1 — METRIC_CATALOG (src/explain/catalog.py)

```python
METRIC_CATALOG: Dict[str, MetricDefinition] = {
    "wip_theoretical": MetricDefinition(
        id="wip_theoretical",
        name="WIP (Theoretical)",
        name_pt="WIP Teórico",
        description="Count of open manufacturing orders",
        domain=MetricDomain.FACTORY,
        semantic_kind=SemanticKind.THEORETICAL,
        unit="count",
        formula="COUNT(OrdensFabrico WHERE DataAcabamento IS NULL)",
        sources=[DataSource(
            schema="factory_curated",
            table="order",
            fields=["of_id", "data_conclusao"],
            trust_index=82,
            coverage_pct=100.0,
        )],
        base_trust_index=82,
        assumptions=["DataAcabamento NULL means order is still open"],
        forbidden_claims=[
            "This is NOT physical WIP count",
            "Does NOT account for orders blocked in quality hold",
        ],
        how_to_improve=["Add order status field", "Integrate with MES"],
    ),
    
    "oee_real": MetricDefinition(
        id="oee_real",
        name="OEE (Real)",
        is_blocked=True,
        blocked_reason="Não existem dados de paragens/máquinas para calcular Availability",
        # ... blocked metrics have minimal configuration
    ),
    
    # ... 15+ more metrics defined
}
```

### BE.4.2 — ExplainedValue Model (src/explain/models/explained_value.py)

```python
class ExplainedValue(BaseModel):
    """Canonical model for ALL numerical outputs."""
    
    metric_id: str
    value: Optional[Union[int, float, Decimal, str]] = None  # null if not computable
    unit: str
    
    # Context
    period: TimePeriod  # start, end, timezone
    scope: ValueScope   # scope_type, scope_id, scope_name
    
    # Semantics
    semantics: SemanticInfo  # kind (theoretical/observed/imputed), completeness
    
    # Trust
    trust: TrustInfo  # index_0_100, coverage_pct, warnings, blocking_reasons
    
    # Lineage
    lineage: LineageInfo  # active_ingestion_id, sources, filters, computed_at, query_hash
    
    # Explanation
    explain: ExplainInfo  # definition, formula, assumptions, forbidden_claims, how_to_improve
    
    @property
    def is_blocked(self) -> bool:
        return len(self.trust.blocking_reasons) > 0
    
    @property
    def display_value(self) -> str:
        if self.is_blocked:
            return "BLOCKED"
        if self.value is None:
            return "—"
        if self.unit == "%":
            return f"{self.value:.1f}%"
        return str(self.value)
```

### BE.4.3 — ExplainedValueBuilder

```python
class ExplainedValueBuilder:
    """Fluent builder for ExplainedValue."""
    
    def __init__(self, metric_id: str):
        self.metric_id = metric_id
        self._data = {}
    
    def with_value(self, value: Any, unit: str): ...
    def with_period(self, start: datetime, end: datetime): ...
    def with_scope(self, scope_type: str, scope_id: str): ...
    def with_semantics(self, kind: str, completeness: str): ...
    def with_trust(self, index: float, coverage: float): ...
    def with_lineage(self, ingestion_id: str, sources: List[str]): ...
    def with_explanation(self, definition: str, formula: str): ...
    def add_warning(self, warning: str): ...
    def add_blocked_reason(self, reason: str): ...
    def build(self) -> ExplainedValue: ...
```

---

## BE.5 — Twin/Sandbox Module (src/twin/api.py)

### BE.5.1 — Endpoints Implementados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/v1/twin/baseline` | GET | Get current factory baseline state |
| `/v1/twin/scenarios` | GET/POST | List or create scenarios |
| `/v1/twin/scenarios/{id}` | GET/DELETE | Get or delete scenario |
| `/v1/twin/scenarios/{id}/apply-delta` | POST | Apply delta to scenario |
| `/v1/twin/scenarios/{id}/simulate` | POST | Run simulation |
| `/v1/twin/scenarios/{id}/solve` | POST | Solve scenario (timeboxed) |
| `/v1/twin/scenarios/{id}/compare` | GET | Compare with baseline |

### BE.5.2 — Baseline State

```python
def create_baseline_state() -> Dict[str, Any]:
    """Create baseline from Factory Data Product KPIs."""
    return {
        "wip": {"value": 1523, "trust": 82, "status": "OK"},
        "backlog_hours": {"value": 4521, "trust": 58, "status": "WARNING"},
        "bottleneck_score": {"value": 67, "trust": 55, "status": "WARNING"},
        # ... theoretical KPIs only
        
        # BLOCKED metrics
        "oee_real": {"value": None, "blocked": True, "reason": "No machine data"},
        "otd_official": {"value": None, "blocked": True, "reason": "No due dates"},
    }
```

### BE.5.3 — Delta Types

```python
class DeltaType(str, Enum):
    CAPACITY_OVERRIDE = "capacity_override"      # Override phase capacity
    STANDARD_OVERRIDE = "standard_override"      # Override product×phase standard
    MOLD_OCCUPANCY = "mold_occupancy_hours"      # Change mold occupancy assumption
    PRIORITY_POLICY = "priority_policy"          # Change scheduling policy
    ADD_TRAINING = "add_training"                # Train employee for phase
    REMOVE_EMPLOYEE = "remove_employee"          # Simulate unavailability
    ADD_EMPLOYEE = "add_employee"                # Simulate hiring
```

---

## BE.6 — Governance Module (src/governance/)

### BE.6.1 — Decision Lifecycle

```
PROPOSED → PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED
              ↓                            ↓
          REJECTED                      FAILED
              ↓                            ↓
       ROLLED_BACK ←───────────────── ROLLED_BACK
```

### BE.6.2 — Endpoints Implementados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/v1/governance/policies` | GET | List all decision policies |
| `/v1/governance/policies/{type}` | GET | Get policy for decision type |
| `/v1/governance/decisions/propose` | POST | Propose new decision |
| `/v1/governance/decisions` | GET | List decisions (with filters) |
| `/v1/governance/decisions/{id}` | GET | Get decision details |
| `/v1/governance/decisions/{id}/approve` | POST | Approve/reject/request changes |
| `/v1/governance/decisions/{id}/execute` | POST | Execute approved decision |
| `/v1/governance/decisions/{id}/rollback` | POST | Rollback executed decision |
| `/v1/governance/decisions/{id}/audit-pack` | GET | Get complete audit pack |
| `/v1/governance/kill-switch` | POST | Activate emergency kill switch |
| `/v1/governance/decisions/pending/me` | GET | Get pending approvals for user |

### BE.6.3 — Separation of Duties (SoD)

```python
class SoDViolationError(Exception):
    """Separation of Duties violation."""
    pass

# In approve_decision:
if decision.get("requires_different_approver", True):
    if approved_by == decision["proposed_by"]:
        raise SoDViolationError(
            f"SoD violation: {approved_by} cannot approve their own decision"
        )
```

### BE.6.4 — Audit Hash Chain

```python
def _calculate_audit_hash(
    decision_id: str,
    policy_version: str,
    input_hash: Optional[str],
    outcome_hash: Optional[str],
    prev_hash: Optional[str],
) -> str:
    data = f"{decision_id}|{policy_version}|{input_hash}|{outcome_hash}|{prev_hash}"
    return hashlib.sha256(data.encode()).hexdigest()
```

### BE.6.5 — Default Policies

```python
DEFAULT_POLICIES = [
    {
        "decision_type": "standard_override",
        "autonomy_level": "L2",
        "requires_approval": True,
        "required_approvers": 1,
        "requires_different_approver": True,
    },
    {
        "decision_type": "capacity_override",
        "autonomy_level": "L2",
        "requires_approval": True,
        "required_approvers": 1,
    },
    {
        "decision_type": "kill_switch",
        "autonomy_level": "L1",
        "requires_approval": False,  # Emergency - no approval needed
    },
]
```

---

## BE.7 — Copilot Module (src/copilot/) — Implementação Completa

### BE.7.1 — Endpoints Implementados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/copilot/ask` | POST | Ask question to Copilot |
| `/api/copilot/action` | POST | Execute action |
| `/api/copilot/suggestions` | GET | Get suggestions |
| `/api/copilot/daily-feedback` | GET | Get daily feedback |
| `/api/copilot/rag/ingest` | POST | Ingest documents to RAG |
| `/api/copilot/conversations` | GET | List conversations |
| `/api/copilot/conversations/{id}` | GET | Get conversation |
| `/api/copilot/conversations/{id}/messages` | GET | Get messages |

### BE.7.2 — CopilotService (1200+ lines)

```python
class CopilotService:
    """Full orchestration service for Copilot."""
    
    async def process_ask(self, request: CopilotAskRequest) -> Tuple[CopilotResponse, Dict]:
        # 1. Security flag check
        if check_security_flag(request.user_query):
            return self._create_security_flag_response(correlation_id)
        
        # 2. Intent detection
        intent = self._detect_intent(request.user_query)
        
        # 3. Fast path for KPI queries (no LLM needed!)
        if intent == "kpi_current":
            fast_response = await self._handle_fast_path_kpi(request)
            if fast_response:
                return fast_response
        
        # 4. Build context facts
        context_facts = await build_context_facts(session, tenant_id)
        
        # 5. Retrieve RAG chunks (if needed)
        rag_chunks = await retrieve_rag_chunks(session, tenant_id, query)
        
        # 6. Render prompt
        prompt = await self._render_prompt(query, context_facts, rag_chunks)
        
        # 7. Call Ollama
        llm_response = await ollama_client.chat(prompt, model, format="json")
        
        # 8. Normalize and validate response
        validation_passed, errors = validate_response_structure(llm_response)
        
        # 9. Create CopilotResponse with evidence
        response = CopilotResponse(
            suggestion_id=uuid4(),
            correlation_id=correlation_id,
            type="ANSWER",
            intent=intent,
            summary=llm_response.get("summary"),
            facts=[...],  # With citations
            actions=[...],
            warnings=[...],
            meta={...},
        )
        
        # 10. Redact PII if needed
        response = redact_response(response, employee_names, has_hr_role)
        
        # 11. Store audit
        await self._store_audit(correlation_id, suggestion_id, ...)
        
        return response, audit_data
```

### BE.7.3 — Intent Detection

```python
def _detect_intent(self, user_query: str) -> str:
    """Detect intent from user query."""
    query_lower = user_query.lower()
    
    # Fast detection for short KPI queries
    if len(query_lower.split()) <= 5:
        kpi_keywords = ["oee", "fpy", "rework", "availability"]
        if any(kw in query_lower for kw in kpi_keywords):
            return "kpi_current"
    
    # Quality summary
    if any(w in query_lower for w in ["qualidade", "quality", "erros"]):
        if any(w in query_lower for w in ["resumo", "summary"]):
            return "quality_summary"
    
    # Plan summary
    if any(w in query_lower for w in ["plano", "plan", "scheduling"]):
        return "plan_summary"
    
    # HR summary
    if any(w in query_lower for w in ["hr", "funcionários", "employees"]):
        return "hr_summary"
    
    return "generic"
```

### BE.7.4 — Fast Path for KPIs (No LLM)

```python
async def _handle_fast_path_kpi(self, request, correlation_id, start_time):
    """Respond directly from KPI snapshot without LLM."""
    kpi_snapshot = await self._fetch_kpi_snapshot()
    
    # Map query to KPIs
    kpi_mappings = {
        "oee": ("oee", "OEE"),
        "availability": ("availability", "Disponibilidade"),
        "performance": ("performance", "Performance"),
        "fpy": ("quality_fpy", "FPY"),
        "rework": ("rework_rate", "Taxa de Retrabalho"),
    }
    
    # Build response with citations
    facts = []
    for kpi_key, kpi_label in detected_kpis:
        value = kpi_snapshot.get(kpi_key, {}).get("value")
        if value:
            facts.append({
                "text": f"{kpi_label}: {value:.2f}%",
                "citations": [create_system_data_citation(...)],
            })
    
    return CopilotResponse(
        type="ANSWER",
        summary=f"{kpi_label}: {value:.2f}%",
        facts=facts,
        meta={"fast_path": True, "latency_ms": latency},
    )
```

### BE.7.5 — Security Guardrails

```python
def check_security_flag(user_query: str) -> bool:
    """Check for prompt injection attempts."""
    dangerous_patterns = [
        r"ignore.*previous.*instructions",
        r"disregard.*above",
        r"you.*are.*now",
        r"pretend.*to.*be",
        r"system.*prompt",
        r"<\|.*\|>",
        r"\[\[.*\]\]",
    ]
    return any(re.search(p, user_query, re.I) for p in dangerous_patterns)

def validate_response_structure(llm_response: Dict) -> Tuple[bool, List[str]]:
    """Validate LLM response structure."""
    errors = []
    
    # Required fields
    if not llm_response.get("summary"):
        errors.append("Missing summary")
    
    # Facts must have citations
    for fact in llm_response.get("facts", []):
        if not fact.get("citations"):
            errors.append("Fact without citations")
    
    return len(errors) == 0, errors
```

### BE.7.6 — Explanation Quality Validation

```python
def _validate_explanation_quality(self, llm_response, user_query, origins):
    """Validate explanation quality for recommendations."""
    errors = []
    
    # Reject shallow explanations (just "OEE is 18.7%")
    shallow_patterns = [
        r'^[A-Za-z\s]+é\s+\d+\.?\d*%\.?$',
        r'^\d+\.?\d*%\.?$',
    ]
    if any(re.match(p, summary) for p in shallow_patterns):
        errors.append("EXPLANATION_TOO_SHALLOW")
    
    # Must have causal link
    causal_keywords = ["porque", "devido", "baseia", "reforça", "causa"]
    if not any(kw in combined_text.lower() for kw in causal_keywords):
        errors.append("EXPLANATION_MISSING_CAUSAL_LINK")
    
    # Block false causality when origins != SYSTEM_DATA
    if has_non_system_data_origin:
        false_patterns = [r"para melhorar\s+\w+", r"devido a\s+\w+\s+baixo"]
        if any(re.search(p, text) for p in false_patterns):
            errors.append("EXPLANATION_FALSE_CAUSALITY")
    
    return errors
```

---

## BE.8 — Workforce Module (NOVO: src/workforce/)

### BE.8.1 — Endpoints Implementados

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/v1/workforce/dependency-graph` | GET | Get workforce dependency graph |
| `/v1/workforce/cascade-impact/{phase_id}` | GET | Calculate cascade impact |
| `/v1/workforce/simulate` | POST | Simulate workforce changes |
| `/v1/workforce/training-recommendations` | GET | Get training recommendations |
| `/v1/workforce/scenarios/compare` | POST | Compare workforce scenarios |

### BE.8.2 — Dependency Graph

```python
async def get_dependency_graph(self) -> Dict[str, Any]:
    """Build dependency graph from FuncionariosFasesAptos + Funcionarios + Fases."""
    
    # Query skills
    skills_query = select(
        CuratedSkillMatrix.funcionario_id,
        CuratedSkillMatrix.funcionario_nome,
        CuratedSkillMatrix.fase_id,
        CuratedSkillMatrix.fase_nome,
        CuratedSkillMatrix.is_active,
    )
    
    # Build nodes and edges
    nodes = []
    edges = []
    spof_nodes = []
    
    for skill in skills:
        # Phase node
        nodes.append({
            "id": phase_id,
            "type": "phase",
            "label": skill.fase_nome,
            "risk_level": self._calculate_risk_level(emp_count),
            "data": {"employee_count": emp_count},
        })
        
        # Employee node
        nodes.append({
            "id": emp_id,
            "type": "employee",
            "label": skill.funcionario_nome,
        })
        
        # Aptitude edge
        edges.append({
            "id": f"apt-{emp_id}-{phase_id}",
            "source": emp_id,
            "target": phase_id,
            "type": "aptitude",
        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "total_employees": len(employee_set),
            "total_phases": len(phase_set),
            "spof_nodes": spof_nodes,
        },
        "trust_index": 55,
        "semantic_label": "Grafo baseado em FuncionariosFasesAptos (aptidões teóricas)",
    }
```

### BE.8.3 — Cascade Impact Analysis

```python
async def calculate_cascade_impact(self, phase_id: str) -> Dict:
    """Calculate cascading impact if phase becomes unavailable."""
    
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
            ]
        },
        {
            "level": 3,
            "type": "downstream",
            "title": "FASES A JUSANTE",
            "items": [
                {"label": "Acabamento", "value": f"+{blocked} ordens bloqueadas"},
            ]
        },
        {
            "level": 4,
            "type": "economic",
            "title": "IMPACTO ECONÓMICO (TEÓRICO)",
            "items": [
                {"label": "Custo backlog em risco", "value": f"€{cost:.0f}"},
                {"label": "⚠️ NÃO INCLUI", "value": "custo real, penalidades"},
            ]
        }
    ]
    
    return {
        "source_phase": phase_id,
        "levels": levels,
        "estimated_daily_cost": daily_cost,
        "trust_index": 55,
        "warnings": ["Valores são TEÓRICOS"],
    }
```

### BE.8.4 — Training Recommendations

```python
async def get_training_recommendations(self, limit: int = 10) -> List[Dict]:
    """Generate training recommendations ordered by impact."""
    
    # Find SPOF phases
    spof_query = select(
        CuratedSkillMatrix.fase_id,
        CuratedSkillMatrix.fase_nome,
        func.count(CuratedSkillMatrix.funcionario_id).label("emp_count"),
    ).group_by(...).having(func.count(...) <= 2)
    
    recommendations = []
    for phase in spof_phases:
        recommendations.append({
            "id": f"rec-{i}",
            "priority": "critical" if phase.emp_count == 1 else "high",
            "employee_id": candidate_id,
            "employee_name": candidate_name,
            "target_phase_id": phase.fase_id,
            "target_phase_name": phase.fase_nome,
            "reasoning": [
                f"Esta fase tem apenas {phase.emp_count} funcionário(s) apto(s)",
                "Cross-training eliminaria o SPOF",
            ],
            "expected_impact": {
                "spof_eliminated": phase.emp_count == 1,
                "risk_reduction": 35,
            },
            "estimated_cost": {
                "hours": 40,
                "cost": 40 * 5.54,  # median hourly rate
            },
            "trust_index": 55,
        })
    
    return sorted(recommendations, key=lambda x: x["priority"])
```

### BE.8.5 — Workforce Simulation

```python
async def simulate_workforce(self, deltas: List[Dict]) -> Dict:
    """Simulate workforce changes and calculate impact."""
    
    baseline = await self._calculate_baseline_metrics()
    simulated = baseline.copy()
    
    for delta in deltas:
        if delta["type"] == "add_training":
            simulated["spof_count"] = max(0, simulated["spof_count"] - 1)
            simulated["avg_risk_score"] *= 0.85
        elif delta["type"] == "remove_employee":
            simulated["spof_count"] += 1
            simulated["avg_risk_score"] *= 1.2
        elif delta["type"] == "add_employee":
            simulated["spof_count"] = max(0, simulated["spof_count"] - 1)
            simulated["avg_risk_score"] *= 0.9
    
    return {
        "scenario_id": str(uuid4()),
        "baseline": baseline,
        "simulated": simulated,
        "impact": {
            "spof_change": simulated["spof_count"] - baseline["spof_count"],
            "risk_change": simulated["avg_risk_score"] - baseline["avg_risk_score"],
        },
        "recommendations": self._generate_recommendations(impact),
        "trust_index": 55,
    }
```

---

## BE.9 — DQA Module (src/dqa/trust_index.py)

### BE.9.1 — TrustIndex Calculator

```python
class TrustIndexCalculator:
    """
    Calculate TrustIndex (0-1 scale) with 4 components:
    - Completeness (30%): % of required fields filled
    - Validity (30%): % of values within valid ranges
    - Consistency (20%): Cross-field conflicts
    - Timeliness (20%): Latency vs SLA
    """
    
    def calculate(self, entity: Dict, latency_ms: int = 0) -> Dict:
        completeness = self._calculate_completeness(entity)
        validity = self._calculate_validity(entity)
        consistency = self._calculate_consistency(entity)
        timeliness = self._calculate_timeliness(latency_ms)
        
        trust_index = (
            completeness * 0.30 +
            validity * 0.30 +
            consistency * 0.20 +
            timeliness * 0.20
        )
        
        return {
            "trust_index": round(trust_index, 3),
            "components": {
                "completeness": completeness,
                "validity": validity,
                "consistency": consistency,
                "timeliness": timeliness,
            },
            "issues": self._detect_issues(entity, latency_ms),
            "repair_recommended": 0.65 <= trust_index < 0.70,
        }
```

### BE.9.2 — Component Weights

| Component | Weight | What it Measures |
|-----------|--------|------------------|
| Completeness | 30% | % of required fields filled |
| Validity | 30% | % of values within valid ranges |
| Consistency | 20% | Cross-field conflicts |
| Timeliness | 20% | Latency vs SLA |

### BE.9.3 — Thresholds

```python
TRUST_THRESHOLD_BLOCK = 0.50   # Below this = BLOCKED
TRUST_THRESHOLD_WARNING = 0.70 # Below this = WARNING
TRUST_THRESHOLD_OK = 0.85      # Above this = OK
```

---

## BE.10 — Capabilities Module (src/shared/api/capabilities.py)

### BE.10.1 — CapabilityStatus Enum

```python
class CapabilityStatus(str, Enum):
    ENABLED = "enabled"      # Fully functional
    DEGRADED = "degraded"    # Limited by trust/data quality
    DISABLED = "disabled"    # No data available
    BLOCKED = "blocked"      # Explicitly blocked (data doesn't support it)
```

### BE.10.2 — CapabilityEvaluator

```python
class CapabilityEvaluator:
    """Evaluate capabilities dynamically based on:
    - Active data ingestion state
    - Trust Index per segment
    - User permissions (RBAC)
    - BLOCKED_METRICS definitions
    """
    
    async def evaluate_all(self) -> CapabilitiesResponse:
        modules = []
        
        # 1. Factory Module
        factory_features = await self._evaluate_factory_features(has_data)
        modules.append(ModuleCapability(
            id="factory",
            name="Factory Data Product",
            status=ENABLED if has_data else DISABLED,
            features=factory_features,
        ))
        
        # 2. Explain Module
        modules.append(ModuleCapability(
            id="explain",
            name="Explainability",
            status=ENABLED,  # Always available (catalog is static)
        ))
        
        # 3. Twin Module
        modules.append(ModuleCapability(
            id="twin",
            name="Digital Twin / Sandbox",
            status=ENABLED if has_data else DEGRADED,
        ))
        
        # 4. Governance Module
        modules.append(ModuleCapability(
            id="governance",
            name="Decision Governance",
            status=ENABLED,
        ))
        
        # 5. Copilot Module
        modules.append(ModuleCapability(
            id="copilot",
            name="AI Copilot",
            status=ENABLED if has_data else DEGRADED,
        ))
        
        # 6. Improve Module
        modules.append(ModuleCapability(
            id="improve",
            name="Improve Lab",
            status=ENABLED if has_data else DISABLED,
        ))
        
        return CapabilitiesResponse(
            modules=modules,
            has_active_data=has_data,
            blocked_metrics=list(BLOCKED_METRICS.keys()),
            allowed_metrics=ALLOWED_METRICS,
        )
```

### BE.10.3 — Capabilities Endpoints

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/capabilities/` | GET | Full capabilities response |
| `/capabilities/modules` | GET | List modules with status |
| `/capabilities/features` | GET | List features (filterable) |
| `/capabilities/blocked` | GET | List blocked capabilities |
| `/capabilities/degraded` | GET | List degraded capabilities |
| `/capabilities/summary` | GET | Summary for dashboard |

---

## 1) Factos do dataset (o chão manda no produto)

### 1.1 Volumetria e cobertura (facto)
- Ordens (OrdensFabrico): 27911
- Ordens abertas (DataAcabamento NULL): 1387 (5.0%)
- Fases ordem×fase (FasesOrdemFabrico): 529450
- DataPrevista preenchida: 25227 (4.8%)
- HorasPrevistas = 0: 299466 (56.6%)
- Funcionários: 301 | ativos: 129 (42.9%)
- ValorHora = 0: 43 (14.3%)
- Moldes: 510 | em estado 15 (código sem dicionário): 458
- Erros: 89836 | sem fase culpada: 37303 (41.5%)
- Standards: 15445 | chaves duplicadas: 217 | chaves conflituosas: 105
- Mismatch molde↔produto: 109 linhas em 51 ordens

### 1.2 Limitações duras (o que NÃO existe nos dados)
- Não existem horas reais por funcionário (não há actual_hours por pessoa).
- Não existe calendário produtivo (turnos/feriados/paragens planeadas).
- Não existem paragens/estado de máquina (logo, OEE real é impossível).
- Não existe due_date/promessa comercial inequívoca (logo, OTD oficial é impossível).
- Não existe setup explícito por molde/fase com timeline real (apenas hipótese 12h a partir de DataPrevista).

---

## 2) Proibições absolutas (hard blocks) — anti‑mentira operacional

### 2.1 Métricas/claims proibidos (backend + UI + LLM)
- OEE real e qualquer derivado chamado "OEE" (BLOCKED).
- Availability em sentido OEE (tempo disponível/planeado) (BLOCKED).
- OTD oficial / promessas de entrega (BLOCKED).
- Custo real por ordem (BLOCKED).
- Produtividade individual real (BLOCKED).
- Capacidade real por dia (BLOCKED).
- "Conflito confirmado" de molde (só 'potencial' e com coverage).

### 2.2 Nomenclatura permitida (se precisares de métricas alternativas)
- "Lead time histórico" (observed) — nunca 'prazo prometido'.
- "Backlog teórico" e "gargalo provável" (theoretical) — nunca 'confirmado'.
- "Taxa de execução de fases" (se existirem timestamps) — nunca 'availability'.

---

## 3) Objetivo de produto (Decision OS) — a obra final

### 3.1 O que é o produto
- Um sistema operativo de decisão industrial, orientado a exceções.
- Cada insight vem com explicação e next actions.
- Toda a ação passa por sandbox (what‑if) antes de qualquer commit/executar.
- Governança e rastreabilidade em tudo (audit, correlation_id, lineage).

### 3.2 O que NÃO é o produto
- Não é PowerBI com filtros.
- Não é um chatbot que 'opina' sem evidência.
- Não é um MES real (ainda) — é um copiloto de decisão com dados batch.

---

## 4) Arquitetura de sistema (on‑prem)

### 4.1 Componentes principais
- Reverse proxy (Nginx/Traefik) — termina TLS e roteia /api e /v1.
- Backend API (FastAPI) — contratos, auth, tenancy, explain, twin, factory, workforce, governance, copilot.
- DB app (`prodplan`) — utilizadores, RBAC, políticas, auditoria, cenários.
- DB data product (`prodplan_factory`) — RAW/CURATED/META/SEMANTIC.
- Ollama (LLM) local — apenas acessível pelo backend (localhost), nunca exposto na LAN.
- Redis — rate limiting, caching.
- Observabilidade — logs estruturados, métricas Prometheus, dashboards de operação.

### 4.2 Rede on‑prem (acesso)
- Utilizadores acedem via browser na LAN: `https://prodplan.local` (DNS interno).
- Backend expõe apenas 80/443 internamente; DBs e Ollama não expostos.
- Acesso externo só via VPN (WireGuard) se necessário.

---

## 5) Estratégia de fusão (src vs legacy) — o que fazer quando há 'enterprise theatre'

### 5.1 Diagnóstico (do chat)
- `prodplan-one/src/`: arquitetura rica mas com KPIs hardcoded/mock e router factory não registado (relatado).
- `backend/ + kayak_production/`: pipeline real, trust index em respostas, endpoints semânticos funcionais (relatado).

### 5.2 Estratégia correta (strangler)
- Declarar SoT: dados reais e semântica vêm do data product, não de mocks.
- Portar pipeline real (ingest/curated/semantic) para o módulo `factory_data_product` no src.
- Eliminar hardcoded KPIs: qualquer métrica sem dados reais deve ser BLOCKED.
- Migrar endpoints `/api/semantic/*` para `/v1/factory/semantic/*` com os mesmos outputs + explained metadata.
- Só depois migrar frontend para `/v1/*` e matar legacy.

---

## 6) Contratos (tudo o que foi definido neste chat)

### 6.1 C000 — Auditoria total (GATE 0)
- Varredura do repo: stack, frameworks, ORM, migrations, jobs, filas.
- Inventário factual de endpoints (método, path, handler, auth, schemas).
- Inventário factual de modelos/DB (migrations, tabelas reais).
- Inventário de testes e execução (ou razões de bloqueio).
- Gap analysis PP1 ↔ sistema ↔ dados Excel.
- Regra: claim sem path+linha = UNVERIFIED.

### 6.2 C010 — Factory Data Product (prodplan_factory)
- DB separada `prodplan_factory`.
- Schemas: factory_raw, factory_curated, factory_meta, factory_semantic.
- RAW append-only; rollback lógico via active_run.
- Ingest idempotente por hash do ficheiro; row_hash por linha.
- Quality gates BLOCKING e WARNING.
- Views SEMANTIC allow-listed; UI/LLM só consomem SEMANTIC/Explain endpoints.

### 6.3 C020 — Explainability (ExplainedValue canónico)
- Todos os números saem em envelope ExplainedValue.
- Semantics: theoretical/observed/imputed; completeness complete/partial/insufficient.
- Trust: index_0_100, coverage_pct, warnings, blocking_reasons.
- Lineage: active_ingestion_id, sources, filters, computed_at, query_hash.
- Explain: definition, formula, assumptions, forbidden_claims, what_it_means, how_to_improve.
- Bloqueios: métricas proibidas retornam BLOCKED e value=null.

### 6.4 C030 — Twin Lite (Sandbox)
- Cenários Git-like: baseline = active_run.
- Deltas idempotentes: capacity override, standard override, mold occupancy hours, priority policy.
- Solve timeboxed; best-effort em DEGRADED.
- Compare com diffs explicados (ExplainedValue).
- Proteção TOCTOU: se baseline mudou, pedir rebase.

### 6.5 FE↔BE 005 — CI gates (relatado implementado)
- Contract gate: OpenAPI diff + types drift.
- Backend tests: lint, type, unit, integration.
- Frontend tests: lint, tsc, unit, build.
- E2E smoke (Playwright): dashboard, explain flow, simulate flow, /health, /capabilities, /catalog.

### 6.6 FE↔BE 007 — LLM guardrails (relatado implementado)
- tool_registry.json gerado a partir do OpenAPI.
- deny-by-default tool router.
- evidence validator (metric_id, active_ingestion_id, computed_at_utc, trust.index_0_100).
- injection detection (prompt + SQL).
- dry-run enforcement para writes.
- golden set adversarial em CI.

---

## 7) Feature Set completo — lista exaustiva por camadas

### 7.1 Data Product: Ingestão, Curadoria, Semântica, Meta

- DP.001 Upload de XLSX via API (multipart) com metadata (tenant_id, user_id, notes).
- DP.002 Ingest via CLI/worker para ambientes on-prem sem UI.
- DP.003 Hash do ficheiro (SHA256) e idempotência (skip ou duplicate_of).
- DP.004 Row hashing (SHA256) por linha normalizada para auditoria.
- DP.005 RAW append-only por ingestion_id (nunca apagar em rollback).
- DP.006 Curated rebuildable e determinístico por ingestion_id.
- DP.007 Quality report automático pós-ingest: volumetria, coverage, conflitos, mismatches, outliers.
- DP.008 Quality gates BLOCKING: business key uniqueness e integridade referencial.
- DP.009 Quality gates WARNING: coverage baixos, conflitos standards, culpada missing, etc.
- DP.010 Active run singleton com activate/rollback lógico.
- DP.011 Activation history (auditoria de activações e rollbacks).
- DP.012 PII policy: mascarar nomes; limitar acesso a ValorHora por role.
- DP.013 Semantic catalog allow-list: views e parâmetros permitidos.
- DP.014 Semantic endpoints read-only: pagination, sorting allow-list, filters allow-list.
- DP.015 Performance: materialized views opcionais para ranking e dashboards críticos.
- DP.016 Observabilidade: métricas ingest_duration, rows_loaded, gate_failures por check_id.

### 7.2 Métricas permitidas (com fórmula + trust)

- M.001 Lead time histórico por produto/período (mean, median, p90, p95) com validação de negativos.
- M.002 WIP teórico: ordens abertas + fases abertas filtrando fases de produção.
- M.003 HorasPrevistas_Final: regra fase>0 else standard>0 else unknown; source tagging.
- M.004 Backlog teórico por fase: Σ HorasPrevistas_Final / CapacidadeHorasDia.
- M.005 Bottlenecks prováveis: rank por backlog_days com severidade configurável.
- M.006 Conflitos potenciais de molde: overlaps de DataPrevista sob occupancy_hours; mostrar coverage.
- M.007 Hotspots de qualidade: pareto por erro, gravidade, fase de avaliação; bucket sem culpada.
- M.008 Qualidade por molde: erros culpados por uso (onde possível).
- M.009 Risco de competências: aptos ativos por fase vs necessidade teórica; SPOF.
- M.010 Custo teórico estimado: Σ ValorHora_valid × HorasPrevistas_Final (nunca custo real).

### 7.3 Explainability e Evidence (cada valor explicado)

- EX.001 ExplainedValue canónico em todos os endpoints numéricos.
- EX.002 GET /v1/explain/metric/{metric_id} devolve definição e exemplos.
- EX.003 POST /v1/explain/value calcula e devolve ExplainedValue com lineage.
- EX.004 Explain drawer universal no frontend (1 clique em qualquer número).
- EX.005 Evidence panel: active_run, sources, fields, filters, query_hash.
- EX.006 Export evidence JSON para auditoria (download/copy).
- EX.007 Forbidden claims obrigatórios em métricas sensíveis.
- EX.008 How_to_improve sempre presente (data improvements + alavancas simuláveis).

### 7.4 Twin / Sandbox (C30)

- TW.001 POST /v1/twin/scenarios cria cenário com baseline pinned ao active_run.
- TW.002 POST /v1/twin/scenarios/{id}/deltas aplica delta idempotente (delta_idempotency_key).
- TW.003 POST /v1/twin/scenarios/{id}/solve recomputa métricas; timeboxed; best-effort.
- TW.004 GET /v1/twin/scenarios/{id}/compare retorna diffs explicados.
- TW.005 Delta: capacity_override por fase e janela temporal.
- TW.006 Delta: standard_override por produto×fase com governance flags.
- TW.007 Delta: mold_occupancy_hours (global ou por fase).
- TW.008 Delta: policy de priorização (SPT/EDD/FIFO) rotulada como simulação.
- TW.009 Proteção TOCTOU: se active_run mudou, exigir rebase.
- TW.010 Scenario UI: histórico de deltas, warnings, confiança agregada.

### 7.5 Governance Module (NOVO)

- GV.001 POST /v1/governance/decisions/propose - criar proposta de decisão.
- GV.002 POST /v1/governance/decisions/{id}/approve - aprovar/rejeitar com SoD.
- GV.003 POST /v1/governance/decisions/{id}/execute - executar decisão aprovada.
- GV.004 POST /v1/governance/decisions/{id}/rollback - reverter decisão executada.
- GV.005 GET /v1/governance/decisions/{id}/audit-pack - pacote completo de auditoria.
- GV.006 POST /v1/governance/kill-switch - emergência sem aprovação.
- GV.007 Hash chain para integridade de auditoria.
- GV.008 Políticas por tipo de decisão (autonomy level, approvers needed).
- GV.009 Separation of Duties enforcement.
- GV.010 Timeline completa de eventos por decisão.

### 7.6 Copilot Module (NOVO - Implementado)

- CP.001 POST /api/copilot/ask - perguntar com intent detection.
- CP.002 Fast path para KPIs (sem LLM, < 500ms).
- CP.003 Context building com operational snapshot + RAG.
- CP.004 Ollama integration com format="json".
- CP.005 Response validation com estrutura canónica.
- CP.006 Security guardrails (prompt injection, SQL injection).
- CP.007 Explanation quality validation para recomendações.
- CP.008 PII redaction por role (HR_MANAGER vê tudo, outros não).
- CP.009 Audit storage com correlation_id e hashes.
- CP.010 Rate limiting (60/hora, 300/dia configuráveis).

### 7.7 Workforce Module (NOVO - Implementado)

- WF.001 GET /v1/workforce/dependency-graph - grafo de dependências funcionário↔fase.
- WF.002 GET /v1/workforce/cascade-impact/{phase_id} - impacto em cascata.
- WF.003 POST /v1/workforce/simulate - simular alterações workforce.
- WF.004 GET /v1/workforce/training-recommendations - recomendações de formação.
- WF.005 POST /v1/workforce/scenarios/compare - comparar cenários workforce.
- WF.006 SPOF detection (Single Points of Failure).
- WF.007 Risk level calculation por fase (critical/high/medium/low/ok).
- WF.008 Training cost estimation (€5.54/h mediana).
- WF.009 Payback period calculation.
- WF.010 Scenario comparison matrix.

### 7.8 Frontend Action-first (sem C40+)

- FE.001 Boot handshake: /health, /v1/capabilities, /v1/factory/meta/active-run, /v1/explain/catalog, /v1/factory/semantic/catalog.
- FE.002 Capabilities-driven UI: esconder features não suportadas pelo backend.
- FE.003 Ops Inbox: lista priorizada de exceções (bottlenecks, quality, skills, molds, data quality).
- FE.004 Cada card tem TrustBadge + Explain + Simular.
- FE.005 Factory Explorer: navegar views allow-listed com filtros fortes e paginação.
- FE.006 Explain Inspector: drawer universal com fórmula, inputs, trust, lineage, limitações.
- FE.007 Sandbox Studio: criar cenário, aplicar delta, solve, compare, export report.
- FE.008 Data Product Studio: active_run, quality report, gates, regressões, checklist de melhoria de dados.
- FE.009 0% mock data runtime: CI gate + lint rule + grep guard.
- FE.010 Runtime validation (Zod) para payloads críticos; mismatch = ContractViolation UI.
- FE.011 **NOVO:** Workforce Dashboard com Risk Heatmap, Dependency Graph, SPOF Alerts.
- FE.012 **NOVO:** Training Recommendations UI com priorização por impacto.
- FE.013 **NOVO:** Scenario Comparison Matrix para comparar cenários workforce.
- FE.014 **NOVO:** Command Palette (⌘+K) para navegação rápida.
- FE.015 **NOVO:** Notifications Panel com alertas em tempo real.
- FE.016 **NOVO:** Live Activity Feed no dashboard.
- FE.017 **NOVO:** Focus Mode para métricas (fullscreen analysis).

### 7.9 FE↔BE e CI (gates)

- CI.001 OpenAPI drift gate: falha se OpenAPI mudou e não foi committed.
- CI.002 Types drift gate: falha se tipos gerados mudaram e não foram committed.
- CI.003 Backend lint/type/unit/integration gates.
- CI.004 Frontend lint/type/unit/build gates.
- CI.005 E2E smoke: dashboard load, explain flow, simulate flow, capabilities/catalog checks.
- CI.006 No-fake-data gate: falha se mock data em runtime fora de tests/storybook.

### 7.10 LLM readiness (sem execução automática)

- LLM.001 Tool registry gerado do OpenAPI; deny-by-default.
- LLM.002 Evidence required para claims numéricos (metric_id + active_run + trust + computed_at).
- LLM.003 Prompt injection detection + SQL injection detection.
- LLM.004 Dry-run enforcement para writes; direct action requests viram sandbox suggestion.
- LLM.005 Golden set adversarial tests em CI; falha bloqueia merge.
- LLM.006 LLM nunca exposto ao DB nem a endpoints não allow-listed.

---

## 8) Inventário de Endpoints (Backend Real)

### 8.1 Health & Capabilities

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/health` | Health check | ✅ |
| GET | `/capabilities/` | Full capabilities | ✅ |
| GET | `/capabilities/modules` | List modules | ✅ |
| GET | `/capabilities/features` | List features | ✅ |
| GET | `/capabilities/blocked` | Blocked features | ✅ |
| GET | `/capabilities/summary` | Summary | ✅ |

### 8.2 Factory Data Product

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/v1/factory/meta/active-run` | Active ingestion | ✅ |
| GET | `/v1/factory/meta/quality-report/{id}` | Quality report | ✅ |
| GET | `/v1/factory/meta/schema-drift` | Schema drift | ✅ |
| GET | `/v1/factory/semantic/queries/wip` | WIP theoretical | ✅ |
| GET | `/v1/factory/semantic/queries/backlog` | Backlog theoretical | ✅ |
| GET | `/v1/factory/semantic/queries/bottlenecks` | Bottlenecks | ✅ |
| GET | `/v1/factory/semantic/queries/quality` | Quality analysis | ✅ |
| GET | `/v1/factory/semantic/queries/mold-conflicts` | Mold conflicts | ✅ |
| GET | `/v1/factory/semantic/queries/skills-risk` | Skills risk | ✅ |
| GET | `/v1/factory/semantic/queries/lead-time` | Lead time | ✅ |
| POST | `/v1/factory/ingest` | Upload XLSX | ✅ |
| POST | `/v1/factory/activate/{id}` | Activate run | ✅ |
| POST | `/v1/factory/rollback/{id}` | Rollback | ✅ |

### 8.3 Explain

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/v1/explain/metric/{metric_id}` | Metric definition | ✅ |
| GET | `/v1/explain/catalog` | All metrics | ✅ |
| GET | `/v1/explain/blocked` | Blocked metrics | ✅ |

### 8.4 Twin/Sandbox

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/v1/twin/baseline` | Baseline state | ✅ |
| GET/POST | `/v1/twin/scenarios` | List/Create scenarios | ✅ |
| GET/DELETE | `/v1/twin/scenarios/{id}` | Get/Delete scenario | ✅ |
| POST | `/v1/twin/scenarios/{id}/apply-delta` | Apply delta | ✅ |
| POST | `/v1/twin/scenarios/{id}/simulate` | Run simulation | ✅ |
| POST | `/v1/twin/scenarios/{id}/solve` | Solve scenario | ✅ |
| GET | `/v1/twin/scenarios/{id}/compare` | Compare | ✅ |

### 8.5 Governance

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/v1/governance/policies` | List policies | ✅ |
| GET | `/v1/governance/policies/{type}` | Get policy | ✅ |
| POST | `/v1/governance/decisions/propose` | Propose decision | ✅ |
| GET | `/v1/governance/decisions` | List decisions | ✅ |
| GET | `/v1/governance/decisions/{id}` | Get decision | ✅ |
| POST | `/v1/governance/decisions/{id}/approve` | Approve | ✅ |
| POST | `/v1/governance/decisions/{id}/execute` | Execute | ✅ |
| POST | `/v1/governance/decisions/{id}/rollback` | Rollback | ✅ |
| GET | `/v1/governance/decisions/{id}/audit-pack` | Audit pack | ✅ |
| POST | `/v1/governance/kill-switch` | Kill switch | ✅ |
| GET | `/v1/governance/decisions/pending/me` | My pending | ✅ |

### 8.6 Copilot

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| POST | `/api/copilot/ask` | Ask question | ✅ |
| POST | `/api/copilot/action` | Execute action | ✅ |
| GET | `/api/copilot/suggestions` | Get suggestions | ✅ |
| GET | `/api/copilot/daily-feedback` | Daily feedback | ✅ |
| POST | `/api/copilot/rag/ingest` | Ingest to RAG | ✅ |
| GET | `/api/copilot/conversations` | List conversations | ✅ |
| GET | `/api/copilot/conversations/{id}` | Get conversation | ✅ |
| GET | `/api/copilot/conversations/{id}/messages` | Get messages | ✅ |

### 8.7 Workforce (NOVO)

| Método | Endpoint | Descrição | Implementado |
|--------|----------|-----------|--------------|
| GET | `/v1/workforce/dependency-graph` | Dependency graph | ✅ |
| GET | `/v1/workforce/cascade-impact/{phase_id}` | Cascade impact | ✅ |
| POST | `/v1/workforce/simulate` | Simulate changes | ✅ |
| GET | `/v1/workforce/training-recommendations` | Training recs | ✅ |
| POST | `/v1/workforce/scenarios/compare` | Compare scenarios | ✅ |

---

## 9) Frontend — blueprint detalhado (Palantir-feel)

### 9.1 Páginas e objetivos
- **Ops Inbox**: Resolver exceções. É a home. Tudo aqui tem Explain e Simular.
- **Factory Explorer**: Explorar views allow-listed e fazer drilldown com evidence.
- **Twin Sandbox**: Criar cenários, aplicar deltas, solve, compare.
- **Explain Inspector**: Componente global; abre em qualquer métrica.
- **Data Product Studio**: Active run, quality report, gates, regressões, ações de melhoria de dados.
- **NOVO: Workforce Dashboard**: Risk Heatmap, Dependency Graph, SPOF Alerts, Training Recommendations.

### 9.2 Componentes obrigatórios (sem mock data)
- TrustBadge(index, coverage, status)
- EvidenceChip(active_run, query_hash, sources)
- ExplainDrawer(ExplainedValue)
- EvidencePanel(lineage, filters, assumptions, forbidden_claims)
- KpiCard(value + trust + explain)
- ScenarioPanel(create/apply/solve/compare)
- DiffViewer(before/after + confidence)
- BlockedState(reason + how_to_unblock)
- CapabilitiesGate(render-if-supported)
- **NOVO:** RiskHeatmap(phases × risk score)
- **NOVO:** DependencyGraph(nodes + edges + SPOF highlighting)
- **NOVO:** SPOFAlertPanel(critical alerts)
- **NOVO:** TrainingRecommendationList(prioritized by impact)
- **NOVO:** CascadeImpactView(4 levels)
- **NOVO:** WorkforceSimulator(what-if deltas)
- **NOVO:** ScenarioComparisonMatrix(side-by-side comparison)
- **NOVO:** CommandPalette(⌘+K universal search)
- **NOVO:** NotificationsPanel(real-time alerts)
- **NOVO:** LiveActivityFeed(system events)
- **NOVO:** FocusModeModal(fullscreen metric analysis)
- **NOVO:** Sparkline(inline mini charts)
- **NOVO:** TrendIndicator(up/down/neutral)

### 9.3 Interações críticas (o que faz isto ser 'action-first')
- Clicar num número abre Explain Drawer (nunca tooltip fraco).
- No Explain Drawer, 'Como melhorar' tem botões: 'Simular' e 'Checklist de dados'.
- Em Ops Inbox, cada exceção tem CTA 'Simular' que cria cenário e aplica delta default.
- O Sandbox devolve diffs com confiança; UI nunca diz 'garantido'.
- UI mostra sempre active_run no topo (versão dos dados).
- Se capabilities não incluir twin/explain/factory, UI esconde o flow (0 404s).
- **NOVO:** ⌘+K abre Command Palette para navegação instantânea.
- **NOVO:** Click em fase no Risk Heatmap → Cascade Impact View.
- **NOVO:** Training Recommendations → click → abre Simulator com delta pre-filled.

---

## 10) Segurança e RBAC (on‑prem)

### 10.1 Roles Definidos

```python
class Role(str, Enum):
    ADMIN_PLATFORM = "admin_platform"
    HR_MANAGER = "hr_manager"
    PLANNER = "planner"
    ENGINEER = "engineer"
    OPERATOR = "operator"
    VIEWER = "viewer"
```

### 10.2 PII Access Control

| Dado | HR_MANAGER | ADMIN | Outros |
|------|------------|-------|--------|
| Funcionario_Nome | ✅ | ✅ | ❌ (redacted) |
| FuncionarioValorHora | ✅ | ✅ | ❌ (hidden) |
| Employee performance | ✅ | ✅ | ❌ |

### 10.3 Headers Obrigatórios

| Header | Descrição | Obrigatório |
|--------|-----------|-------------|
| `X-Tenant-Id` | UUID do tenant | Sim |
| `X-User-Id` | ID do utilizador | Sim |
| `Authorization` | Bearer token JWT | Sim |
| `X-Correlation-Id` | ID para tracing | Auto-gerado |

---

## 11) Observabilidade (SLOs e métricas)

### 11.1 SLOs

| Endpoint | p95 Target | Notes |
|----------|------------|-------|
| `/v1/factory/semantic/*` | < 800ms | Com cache/materialized |
| `/v1/explain/value` | < 1200ms | Sem LLM |
| `/v1/twin/solve` | < 10s | Timeboxed |
| `/api/copilot/ask` (fast path) | < 500ms | KPI queries |
| `/api/copilot/ask` (LLM) | < 10s | Full LLM path |

### 11.2 Métricas Prometheus

```
request_latency_ms{route, method, status}
semantic_query_latency_ms{view_id}
explain_compute_latency_ms{metric_id}
twin_solve_latency_ms{scenario_size}
copilot_ask_latency_ms{intent, fast_path}
quality_gate_failures_total{gate_id, severity}
dataprevista_coverage_pct
horasprev_final_coverage_pct
spof_count_total
```

---

## 12) Resumo das Diferenças vs Documento Original

| Área | Original | Actualizado |
|------|----------|-------------|
| Backend Modules | 5 (Factory, Explain, Twin, Governance, Copilot) | 7 (+Workforce, +Capabilities) |
| Endpoints | ~30 | 50+ |
| Copilot Features | Basic ask/action | Full orchestration, fast path, guardrails, intent detection |
| Workforce | Não existia | Dependency Graph, Cascade Impact, Simulation, Training Recs |
| Trust Index | Config only | Calculator with 4 components |
| Capabilities | Static | Dynamic evaluation per module/feature |
| Frontend Components | ~20 | 30+ (new workforce, command palette, etc.) |

---

## 13) Próximos Passos Recomendados

1. **Conectar Semantic Queries a dados reais** (atualmente retornam mock data)
2. **Implementar Quality Gates no pipeline de ingestão**
3. **Adicionar testes E2E para Workforce module**
4. **Implementar materialized views para performance**
5. **Adicionar export PDF para Workforce Report**
6. **Integrar Governance com Workforce Simulator** (aprovar cenários)
7. **Adicionar WebSocket para notificações real-time**
8. **Implementar RAG real com embeddings** (atualmente mock)

---

*Documento compilado automaticamente a partir da análise extensiva do backend em 2026-01-28.*
*Todas as informações reflectem o estado actual do código em `/Users/martimnicolau/nelo final /prodplan-one/`.*

