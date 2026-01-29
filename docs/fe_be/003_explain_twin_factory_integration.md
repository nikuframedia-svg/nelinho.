# CONTRATO FE↔BE 003 — Integração Explain/Twin/Factory e UX Acção

## Metadata
- **ID**: FE-BE-003
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO
- **Depende de**: FE-BE-001, FE-BE-002, C20, C30, C10

## Objectivo

Garantir que o frontend representa o backend:
- **Sem inventar métricas** — todos os valores vêm do backend
- **Sem "dashboard morto"** — todos os KPIs têm explicação disponível
- **Com acção governada** — sugestões são simuladas no sandbox antes de executar

---

## Regras Inegociáveis

### R1: Zero KPI Sem Explicação
- Nenhum KPI é mostrado sem `ExplainedValue` disponível.
- Se o backend não retornar explicação → mostrar placeholder "Dados não disponíveis".

### R2: Sugestões Accionáveis
- Toda sugestão do backend tem CTA (Call to Action).
- CTAs principais: "Simular no Sandbox", "Ver Detalhes", "Marcar como Concluído".

### R3: Simulação Não Executa
- "Simular" **nunca** executa em produção.
- Fluxo: criar cenário Twin → aplicar delta → solve → comparar.

### R4: Frontend Não Calcula
- O frontend **NÃO calcula** KPIs.
- O frontend apenas **formata** e **apresenta** valores do backend.

### R5: ExplainedValue é Canónico
- O modelo canónico é `ExplainedValue` (backend).
- Qualquer tipo frontend (`ExplainableValue`, `KPIData`, etc.) é view-model derivado.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ KPICard │  │ DataTable│  │Suggestion│  │   Sandbox   │  │
│  │         │  │          │  │   Card   │  │    Panel    │  │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └──────┬──────┘  │
│       │            │             │               │          │
│       ▼            ▼             ▼               ▼          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  ExplainDrawer                        │  │
│  │  (aceita ExplainedValue, renderiza explicação)       │  │
│  └──────────────────────────────────────────────────────┘  │
│       │            │             │               │          │
│       ▼            ▼             ▼               ▼          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   API Clients                         │  │
│  │  explainApi | twinApi | factoryApi | catalogApi      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                              │
├─────────────────────────────────────────────────────────────┤
│  /v1/explain/*  │  /v1/twin/*  │  /v1/factory/*  │ /v1/catalog │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementação Frontend

### 1. API Clients

#### Explain API
```typescript
// frontend/src/lib/api/explain.ts
export const explainApi = {
  getMetric: (metricId: string) => 
    httpClient.get<ExplainedValue>(`/v1/explain/metric/${metricId}`, {
      schema: ExplainedValueSchema
    }),
  
  computeValue: (payload: ComputeValueRequest) =>
    httpClient.post<ExplainedValue>('/v1/explain/value', payload, {
      schema: ExplainedValueSchema
    }),
  
  getCatalog: () =>
    httpClient.get<MetricCatalog>('/v1/explain/catalog'),
  
  getBlockedMetrics: () =>
    httpClient.get<MetricInfo[]>('/v1/explain/blocked-metrics'),
};
```

#### Twin API
```typescript
// frontend/src/lib/api/twin.ts
export const twinApi = {
  createScenario: (request: CreateScenarioRequest) =>
    httpClient.post<TwinScenario>('/v1/twin/scenarios', request, {
      schema: TwinScenarioSchema
    }),
  
  getScenario: (scenarioId: string) =>
    httpClient.get<TwinScenario>(`/v1/twin/scenarios/${scenarioId}`, {
      schema: TwinScenarioSchema
    }),
  
  applyDelta: (scenarioId: string, delta: ApplyDeltaRequest) =>
    httpClient.post<TwinScenario>(
      `/v1/twin/scenarios/${scenarioId}/deltas`,
      delta,
      { schema: TwinScenarioSchema }
    ),
  
  solve: (scenarioId: string) =>
    httpClient.post<TwinScenarioResult>(
      `/v1/twin/scenarios/${scenarioId}/solve`,
      undefined,
      { schema: TwinScenarioResultSchema }
    ),
  
  compare: (scenarioId: string, otherId: string) =>
    httpClient.get<ScenarioCompareResponse>(
      `/v1/twin/scenarios/${scenarioId}/compare`,
      { params: { other_id: otherId } }
    ),
};
```

#### Factory API
```typescript
// frontend/src/lib/api/factory.ts
export const factoryApi = {
  getActiveRun: () =>
    httpClient.get<ActiveRun>('/v1/factory/meta/active-run'),
  
  getSemanticView: (viewId: SemanticViewId, params?: ViewParams) =>
    httpClient.get<SemanticViewResponse>(
      `/v1/factory/semantic/${viewId}`,
      { params, schema: SemanticViewResponseSchema }
    ),
  
  getQualityReport: (ingestionId: string) =>
    httpClient.get<QualityReport>(`/v1/factory/meta/quality-report/${ingestionId}`),
};
```

### 2. Componentes Core

#### KPICard
```typescript
// frontend/src/components/kpi/KPICard.tsx

interface KPICardProps {
  metricId: string;          // ID da métrica no catálogo
  value?: ExplainedValue;    // Valor pré-carregado (opcional)
  showTrustBadge?: boolean;  // Mostrar badge de trust
  onExplainClick?: () => void;
}

// Regra: Se value não está disponível, mostra skeleton/placeholder
// Regra: Sempre tem ícone "i" para abrir ExplainDrawer
```

#### ExplainDrawer (Refatorado)
```typescript
// frontend/src/components/explain/ExplainDrawer.tsx

interface ExplainDrawerProps {
  open: boolean;
  onClose: () => void;
  
  // Aceita ExplainedValue completo OU metricId para fetch
  value?: ExplainedValue;
  metricId?: string;
}

// Secções do Drawer:
// 1. Header: metric_id, value, unit, trust badge
// 2. Semantics: kind (theoretical/observed), completeness
// 3. Trust: index, coverage, warnings, blocking_reasons
// 4. Explain: definition, formula, assumptions
// 5. Limitations: forbidden_claims (em vermelho)
// 6. Improvements: how_to_improve[] com CTAs
// 7. Lineage: sources, filters, computed_at, ingestion_id
```

#### SuggestionCard
```typescript
// frontend/src/components/suggestions/SuggestionCard.tsx

interface SuggestionCardProps {
  suggestion: Suggestion;
  onSimulate?: (suggestion: Suggestion) => void;
  onViewDetails?: (suggestion: Suggestion) => void;
}

// Tipos de CTA baseados em suggestion.action_type:
// - DATA_IMPROVEMENT: "Adicionar Dados", impacto em trust
// - OPERATIONAL_LEVER: "Simular no Sandbox"
// - TRAINING: "Ver Plano de Formação"
```

#### SandboxSimulationPanel
```typescript
// frontend/src/components/sandbox/SandboxSimulationPanel.tsx

interface SandboxSimulationPanelProps {
  suggestion: Suggestion;
  onClose: () => void;
}

// Fluxo:
// 1. Criar cenário: twinApi.createScenario({ title: `Simulação: ${suggestion.title}` })
// 2. Aplicar delta: twinApi.applyDelta(scenarioId, suggestion.delta)
// 3. Resolver: twinApi.solve(scenarioId)
// 4. Mostrar comparação: baseline vs cenário
```

### 3. Hooks

#### useExplainedValue
```typescript
// frontend/src/hooks/useExplainedValue.ts

export function useExplainedValue(metricId: string) {
  return useQuery({
    queryKey: ['explain', 'metric', metricId],
    queryFn: () => explainApi.getMetric(metricId),
    staleTime: 5 * 60 * 1000, // 5 minutos
  });
}
```

#### useSandboxSimulation
```typescript
// frontend/src/hooks/useSandboxSimulation.ts

export function useSandboxSimulation() {
  const [scenario, setScenario] = useState<TwinScenario | null>(null);
  const [result, setResult] = useState<TwinScenarioResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const simulate = async (suggestion: Suggestion) => {
    setIsLoading(true);
    try {
      // 1. Criar cenário
      const scenarioRes = await twinApi.createScenario({
        title: `Simulação: ${suggestion.title}`,
      });
      
      // 2. Aplicar delta
      await twinApi.applyDelta(scenarioRes.data.id, suggestion.delta);
      
      // 3. Resolver
      const resultRes = await twinApi.solve(scenarioRes.data.id);
      
      setScenario(scenarioRes.data);
      setResult(resultRes.data);
    } finally {
      setIsLoading(false);
    }
  };
  
  return { scenario, result, isLoading, simulate };
}
```

---

## Regras de Renderização

### KPI Cards

| Condição | Renderização |
|----------|--------------|
| `value` disponível + `trust.index >= 60` | Card normal com valor |
| `value` disponível + `trust.index < 60` | Card com warning badge |
| `value` disponível + `blocking_reasons.length > 0` | Card bloqueado (cinza) |
| `value` não disponível | Skeleton/Placeholder |
| `semantics.kind === 'theoretical'` | Badge "Teórico" visível |

### Sugestões

| Tipo de Sugestão | CTA Principal | CTA Secundário |
|------------------|---------------|----------------|
| Data Improvement | "Adicionar Dados" | "Ver Impacto" |
| Capacity Adjustment | "Simular" | "Ver Detalhes" |
| Scheduling Change | "Simular" | "Ver Calendário" |
| Quality Action | "Criar Ticket" | "Ver Histórico" |

### Simulação Sandbox

| Estado | UI |
|--------|-----|
| `isLoading` | Spinner + "A criar cenário..." |
| `solver_status === 'ok'` | Diff cards com cores (verde/vermelho) |
| `solver_status === 'best_effort'` | Diff cards + warning banner |
| `solver_status === 'failed'` | Error card com retry |
| `solver_status === 'timeout'` | Timeout card com "Tentar novamente" |

---

## Definition of Done (DoD)

### Gates de Saída

| Gate | Critério | Automatizado |
|------|----------|--------------|
| G1 | ExplainDrawer faz chamadas reais a `/v1/explain/*` | ✅ Tests |
| G2 | Botão "Simular" cria cenário Twin e apresenta diff | ✅ Tests |
| G3 | Nenhum KPI mostrado sem explicação disponível | ✅ Lint rule |
| G4 | Todos os CTAs têm handlers implementados | ✅ Tests |
| G5 | Trust badge visível em todos os KPI cards | ✅ Visual tests |

### Testes Obrigatórios

```typescript
describe('KPICard', () => {
  it('should show explain icon on all cards');
  it('should open ExplainDrawer on icon click');
  it('should show placeholder when value not available');
  it('should show warning badge when trust < 60');
});

describe('ExplainDrawer', () => {
  it('should fetch ExplainedValue from backend');
  it('should render all sections correctly');
  it('should show forbidden_claims in red');
  it('should render CTAs for how_to_improve');
});

describe('SuggestionCard', () => {
  it('should show "Simular" button for operational suggestions');
  it('should show data improvement checklist');
  it('should call onSimulate when button clicked');
});

describe('SandboxSimulation', () => {
  it('should create scenario via twinApi');
  it('should apply delta and solve');
  it('should display KPI diff correctly');
  it('should handle solver timeout gracefully');
});
```

---

## Ficheiros Criados/Modificados

### Frontend
- `frontend/src/lib/api/explain.ts` — API client Explain
- `frontend/src/lib/api/twin.ts` — API client Twin
- `frontend/src/lib/api/factory.ts` — API client Factory
- `frontend/src/components/kpi/KPICard.tsx` — Card de KPI com Explain
- `frontend/src/components/explain/ExplainDrawer.tsx` — Drawer refatorado
- `frontend/src/components/suggestions/SuggestionCard.tsx` — Card de sugestão
- `frontend/src/components/sandbox/SandboxSimulationPanel.tsx` — Painel de simulação
- `frontend/src/hooks/useExplainedValue.ts` — Hook para ExplainedValue
- `frontend/src/hooks/useSandboxSimulation.ts` — Hook para simulação

---

## Glossário

| Termo | Definição |
|-------|-----------|
| **ExplainedValue** | Modelo canónico do backend para valores explicáveis |
| **Sandbox** | Ambiente de simulação sem impacto em produção |
| **Delta** | Alteração incremental a aplicar num cenário |
| **Trust Index** | Índice de confiança (0-100) de um valor |
| **CTA** | Call to Action — botão de acção |

---

## Referências

- Contrato C20 - Explainability
- Contrato C30 - Twin Lite e Sandbox
- Contrato C10 - Factory Data Product
- Contrato FE-BE-001 - Contrato Canónico
- Contrato FE-BE-002 - Cliente Tipado


