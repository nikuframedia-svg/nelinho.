# CONTRATO 020 — Explainability

## Status
**IMPLEMENTADO**

## Objectivo
Nenhum número sai do sistema sem:
- Definição formal
- Fórmula
- Linhagem (lineage)
- Nível de confiança (trust)
- Limitações explícitas
- Sugestões accionáveis para melhorar qualidade/cobertura

## Conceito Central: ExplainedValue

Todo valor relevante é representado como **ExplainedValue**:

```json
{
  "metric_id": "backlog_horas_teoricas",
  "value": 245.5,
  "unit": "hours",
  "period": {
    "type": "as_of",
    "timestamp": "2026-01-27T10:30:00Z"
  },
  "scope": {
    "level": "phase",
    "phase_id": "F001",
    "fase_nome": "Montagem"
  },
  "semantics": {
    "kind": "theoretical",
    "completeness": "partial"
  },
  "trust": {
    "index_0_100": 65,
    "coverage_pct": 78.5,
    "warnings": ["20% das ordens sem horas_previstas"],
    "blocking_reasons": []
  },
  "lineage": {
    "active_ingestion_id": "abc123-...",
    "sources": [
      {"schema": "factory_curated", "table_or_view": "order_phase", "fields": ["horas_finais", "estado"]}
    ],
    "filters": {"estado": "NOT IN ('Concluido', 'Fechado')"},
    "computed_at_utc": "2026-01-27T10:30:00Z",
    "query_hash": "sha256:..."
  },
  "explain": {
    "definition": "Soma das horas teóricas das fases pendentes",
    "formula": "SUM(horas_finais) WHERE estado NOT IN ('Concluido', 'Fechado')",
    "assumptions": [
      "horas_finais = COALESCE(horas_previstas, horas_standard)",
      "Fases sem horas assumem 0"
    ],
    "forbidden_claims": [
      "Não representa carga real de trabalho",
      "Não usar para OEE, OTD, ou custo real"
    ],
    "what_it_means": "Estimativa teórica da carga pendente baseada em standards",
    "how_to_improve": [
      "Preencher FaseOf_HorasPrevistas para todas as fases",
      "Validar StandardHoras no cadastro de modelos"
    ]
  }
}
```

## Regras de Publicação

### 1. Sem ExplainedValue, Não Há API
Endpoints que devolvem métricas têm de incluir `ExplainedValue`:
- Embutido no resultado
- Ou referenciado por `metric_id` no `meta.explained_value_map`

### 2. Trust Threshold
```
Se trust.index_0_100 < 40:
  - Automações bloqueadas
  - Modo "sugestão" apenas
  - UI mostra alerta prominente
```

### 3. Nomes Reflectem Semântica
- Dados teóricos → nome inclui "teórico" ou "estimado"
- Dados observados → pode usar nome "real"
- NUNCA usar nome que sugere observação quando é aproximação

### 4. UI Não Inventa Contexto
- Tooltips alimentados por `explain.what_it_means`
- Disclaimers vindos de `explain.forbidden_claims`
- Sugestões de melhoria vindas de `explain.how_to_improve`

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    METRICS CATALOG                               │
│              (METRICS_CATALOG.json versionado)                  │
│                                                                  │
│  - metric_id                                                     │
│  - nome legível                                                  │
│  - definição formal                                              │
│  - fórmula                                                       │
│  - fontes                                                        │
│  - anti-claims                                                   │
│  - parâmetros aceites                                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    METRIC REGISTRY                               │
│              (Runtime + Validation)                              │
│                                                                  │
│  - Carrega catálogo                                              │
│  - Valida metric_id                                              │
│  - Calcula ExplainedValue                                        │
│  - Aplica trust rules                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │  /explain/  │ │  /factory/  │ │  /improve/  │
   │   metric/   │ │  semantic/* │ │suggestions/*│
   │             │ │             │ │             │
   │ExplainedVal │ │data + meta. │ │suggestions  │
   │definition   │ │explained_   │ │+ explained  │
   │+ examples   │ │value_map    │ │_impacts     │
   └─────────────┘ └─────────────┘ └─────────────┘
```

## APIs Obrigatórias

### GET /v1/explain/metric/{metric_id}
Devolve definição formal + exemplos

### POST /v1/explain/value
Recebe `{metric_id, params, context}` e devolve `ExplainedValue`

### Todos os endpoints /factory/semantic/*
Devolvem:
```json
{
  "data": [...],
  "meta": {
    "total": 100,
    "page": 1,
    "explained_value_map": {
      "backlog_horas_teoricas": { ... ExplainedValue ... },
      "utilizacao_pct": { ... ExplainedValue ... }
    }
  }
}
```

## Ficheiros Implementados

```
src/explainability/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── explained_value.py    # ExplainedValue model completo
├── catalog/
│   ├── __init__.py
│   ├── registry.py           # MetricRegistry runtime
│   └── loader.py             # Load METRICS_CATALOG.json
├── api/
│   ├── __init__.py
│   └── endpoints.py          # /v1/explain/* endpoints
└── tests/
    ├── __init__.py
    └── test_explainability.py

docs/20_explainability/
├── CONTRACT.md
└── METRICS_CATALOG.json      # Versioned catalog
```

## CI Gate Test

```yaml
# .github/workflows/explainability-gate.yml
- Varre endpoints de métricas/semantic
- Valida presença de:
  - metric_id
  - lineage
  - trust
  - explain
  - active_ingestion_id
- Valida forbidden_claims contém proibições relevantes
- FALHA build se não conformes
```

## Critérios de Aceitação

- [x] 100% das métricas expostas têm ExplainedValue completo
- [x] Se métrica não suportada: `value=null`, `completeness=insufficient`, `blocking_reasons` preenchido
- [x] Catálogo versionado existe e está alinhado com endpoints
- [x] UI tooltips alimentados por `explain`
- [x] Trust < 40 → automações bloqueadas

## Anti-Padrões Proibidos

| Anti-Padrão | Consequência |
|-------------|--------------|
| "Números mágicos" sem fórmula | Build falha |
| KPIs com nomes que insinuam observação real quando são aproximações | Revisão obrigatória |
| UI a gerar disclaimers manualmente | Rejeitado em code review |
| Endpoint sem `ExplainedValue` | CI gate falha |


