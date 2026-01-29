# CONTRATO FE↔BE 006 — No Fake Data e Proveniência

## Metadata
- **ID**: FE-BE-006
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO
- **Depende de**: FE-BE-001, FE-BE-002, FE-BE-003

## Objectivo

Garantir que em produção:
- **Não existe mock data** — nenhum fallback inventado, nenhum número fabricado
- **Qualquer número tem proveniência** — trust index, coverage, lineage
- **UI reflete confiança real** — utilizador sabe quando dados são degradados

---

## Regras Duras

### 1. Proibição de Mock Data em Produção

**Imports proibidos** em `src/` (exceto testes):

```
❌ PROIBIDO em src/ (runtime)
├── @faker-js/faker
├── faker
├── chance
├── mock-data
├── sample-data
├── sampleData
├── mockData
├── __mocks__
└── .mock.

✅ PERMITIDO apenas em:
├── __tests__/
├── *.test.*
├── *.spec.*
├── *.stories.*
└── e2e/
```

### 2. KPI Components Tipagem Estrita

```typescript
// ❌ PROIBIDO
interface KPICardProps {
  value: number;
  label: string;
}

// ✅ OBRIGATÓRIO
interface KPICardProps {
  data: ExplainedValue;
  // Permite verificar trust, coverage, lineage
}
```

### 3. UI Obrigatória de Proveniência

Todo valor numérico crítico deve mostrar:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `trust.index_0_100` | ✅ Sim | Trust badge (0-100) |
| `trust.coverage_pct` | ✅ Sim | Coverage percentage |
| `lineage.active_ingestion_id` | ⚠️ Quando aplicável | Source tracking |
| `lineage.computed_at_utc` | ⚠️ Quando aplicável | Freshness indicator |

### 4. Comportamento por Nível de Trust

| Trust Index | Estado UI | Comportamento |
|-------------|-----------|---------------|
| 80-100 | 🟢 OK | Normal operation |
| 50-79 | 🟡 WARNING | Show warning badge |
| 20-49 | 🟠 DEGRADED | Show degraded state, disable auto-actions |
| 0-19 | 🔴 BLOCKED | Show blocked state, prevent all actions |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend Runtime                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Data Flow Enforcement                      │   │
│  │                                                               │   │
│  │  API Response ──► ExplainedValue ──► KPICard/DataTable       │   │
│  │                        │                    │                 │   │
│  │                        ▼                    ▼                 │   │
│  │                   TrustBadge        ProvenanceTooltip        │   │
│  │                   (always shown)    (on hover/click)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Trust-Based Actions                        │   │
│  │                                                               │   │
│  │  Trust ≥ 80 ──► Actions enabled                              │   │
│  │  Trust 50-79 ──► Actions enabled with warning                │   │
│  │  Trust < 50 ──► Auto-actions disabled                        │   │
│  │  Trust < 20 ──► All actions blocked                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementação

### 1. Script de Verificação (`scripts/no_fake_data_check.sh`)

```bash
#!/bin/bash
# Verifica se existe mock data em código de produção

FORBIDDEN_PATTERNS=(
  "@faker-js/faker"
  "faker"
  "chance"
  "mock-data"
  "sampleData"
  "mockData"
  "__mocks__"
  ".mock."
  "MOCK_"
  "FAKE_"
  "SAMPLE_"
)

# Diretórios a verificar (excluindo testes)
SEARCH_DIRS="src"
EXCLUDE_PATTERNS="__tests__|\.test\.|\.spec\.|\.stories\.|e2e|__mocks__"

errors=0

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  matches=$(grep -rn "$pattern" "$SEARCH_DIRS" \
    --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
    | grep -vE "$EXCLUDE_PATTERNS" || true)
  
  if [ -n "$matches" ]; then
    echo "❌ Found forbidden pattern '$pattern':"
    echo "$matches"
    errors=$((errors + 1))
  fi
done

if [ $errors -gt 0 ]; then
  echo ""
  echo "❌ Found $errors forbidden mock data patterns in production code!"
  exit 1
fi

echo "✅ No mock data found in production code"
exit 0
```

### 2. ESLint Plugin (`eslint-plugin-no-fake-data`)

```javascript
// eslint-local-rules/no-fake-data.js
module.exports = {
  rules: {
    "no-mock-imports": {
      create(context) {
        const forbiddenModules = [
          "@faker-js/faker",
          "faker",
          "chance",
        ];
        
        return {
          ImportDeclaration(node) {
            const source = node.source.value;
            if (forbiddenModules.some(m => source.includes(m))) {
              context.report({
                node,
                message: `Mock library "${source}" is forbidden in production code.`,
              });
            }
          },
        };
      },
    },
    
    "kpi-requires-explained-value": {
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (node.name.name === "KPICard") {
              const hasDataProp = node.attributes.some(
                attr => attr.name && attr.name.name === "data"
              );
              if (!hasDataProp) {
                context.report({
                  node,
                  message: "KPICard must receive 'data' prop of type ExplainedValue.",
                });
              }
            }
          },
        };
      },
    },
  },
};
```

### 3. TrustBadge Component

```typescript
// src/components/TrustBadge.tsx
interface TrustBadgeProps {
  trust: ExplainedValue["trust"];
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

function TrustBadge({ trust, size = "md", showLabel = true }: TrustBadgeProps) {
  const { index_0_100, coverage_pct, warnings, blocking_reasons } = trust ?? {};
  
  const status = getTrustStatus(index_0_100);
  // OK | WARNING | DEGRADED | BLOCKED
  
  return (
    <div className={styles[status]}>
      <TrustIcon status={status} />
      {showLabel && <span>{index_0_100}%</span>}
      <Tooltip>
        Coverage: {coverage_pct}%
        {warnings?.length && <WarningList warnings={warnings} />}
        {blocking_reasons?.length && <BlockedList reasons={blocking_reasons} />}
      </Tooltip>
    </div>
  );
}
```

### 4. ProvenanceInfo Component

```typescript
// src/components/ProvenanceInfo.tsx
interface ProvenanceInfoProps {
  lineage: ExplainedValue["lineage"];
  compact?: boolean;
}

function ProvenanceInfo({ lineage, compact = false }: ProvenanceInfoProps) {
  if (!lineage) return null;
  
  const { active_ingestion_id, computed_at_utc, sources, query_hash } = lineage;
  
  return (
    <div className="provenance-info">
      <span title={`Ingestion: ${active_ingestion_id}`}>
        📦 {truncate(active_ingestion_id, 8)}
      </span>
      <span title={computed_at_utc}>
        🕐 {formatRelative(computed_at_utc)}
      </span>
      {!compact && sources && (
        <span>📊 {sources.length} sources</span>
      )}
    </div>
  );
}
```

### 5. Strict KPICard

```typescript
// src/components/kpi/KPICard.tsx
interface KPICardProps {
  data: ExplainedValue; // OBRIGATÓRIO - não aceita value/label separados
  onExplain?: () => void;
  className?: string;
}

function KPICard({ data, onExplain, className }: KPICardProps) {
  // Validação runtime
  if (!data || !data.metric_id) {
    throw new Error("KPICard requires ExplainedValue with metric_id");
  }
  
  const { value, unit, trust, lineage, explain } = data;
  const trustStatus = getTrustStatus(trust?.index_0_100);
  
  // Bloquear renderização se trust muito baixo
  if (trustStatus === "BLOCKED") {
    return <BlockedKPICard reason={trust?.blocking_reasons?.[0]} />;
  }
  
  return (
    <Card className={cn("kpi-card", trustStatus, className)}>
      <CardHeader>
        <TrustBadge trust={trust} size="sm" />
        {onExplain && <ExplainButton onClick={onExplain} />}
      </CardHeader>
      
      <CardBody>
        <Value value={value} unit={unit} />
        <Label>{explain?.definition || data.metric_id}</Label>
      </CardBody>
      
      <CardFooter>
        <ProvenanceInfo lineage={lineage} compact />
      </CardFooter>
    </Card>
  );
}
```

---

## CI Integration

### GitHub Actions Step

```yaml
- name: Check for mock data in production code
  run: |
    chmod +x scripts/no_fake_data_check.sh
    ./scripts/no_fake_data_check.sh
```

### ESLint Configuration

```javascript
// .eslintrc.js
module.exports = {
  plugins: ["local-rules"],
  rules: {
    "local-rules/no-mock-imports": "error",
    "local-rules/kpi-requires-explained-value": "error",
  },
  overrides: [
    {
      files: ["**/__tests__/**", "**/*.test.*", "**/*.spec.*", "**/*.stories.*"],
      rules: {
        "local-rules/no-mock-imports": "off",
      },
    },
  ],
};
```

---

## Ficheiros

### Backend
N/A - Este contrato é primariamente frontend/CI.

### Frontend
- `frontend/src/components/TrustBadge.tsx`
- `frontend/src/components/ProvenanceInfo.tsx`
- `frontend/src/components/kpi/KPICard.tsx` (atualizado)
- `frontend/src/lib/trust-utils.ts`
- `frontend/eslint-local-rules/no-fake-data.js`

### Scripts
- `scripts/no_fake_data_check.sh`

### CI
- `.github/workflows/no-fake-data.yml`

---

## Definition of Done (DoD)

### Gates de Saída

| Gate | Critério | Automatizado |
|------|----------|--------------|
| G1 | Script `no_fake_data_check.sh` passa | ✅ CI |
| G2 | ESLint no-mock-imports passa | ✅ CI |
| G3 | KPICard só aceita ExplainedValue | ✅ TypeScript |
| G4 | TrustBadge visível em todos KPIs | ✅ Tests |
| G5 | Proveniência disponível on-hover | ✅ Tests |
| G6 | Trust < 50 desabilita auto-actions | ✅ Tests |

### Testes Obrigatórios

```typescript
describe("No Fake Data", () => {
  it("should not have mock imports in production code");
  it("should reject KPICard without ExplainedValue");
});

describe("TrustBadge", () => {
  it("should show OK for trust >= 80");
  it("should show WARNING for trust 50-79");
  it("should show DEGRADED for trust 20-49");
  it("should show BLOCKED for trust < 20");
});

describe("KPICard Trust Behavior", () => {
  it("should enable actions when trust >= 80");
  it("should show warning when trust 50-79");
  it("should disable auto-actions when trust < 50");
  it("should block all actions when trust < 20");
});
```

---

## Referências

- Contrato FE-BE-001 - Contrato Canónico
- Contrato FE-BE-002 - Cliente Tipado
- Contrato FE-BE-003 - ExplainedValue
- C20 - Explainability


