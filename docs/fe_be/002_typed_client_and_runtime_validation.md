# CONTRATO FE↔BE 002 — Cliente Tipado e Validação Runtime

## Metadata
- **ID**: FE-BE-002
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO
- **Depende de**: FE-BE-001

## Objectivo

Eliminar 404/422 silenciosos e garantir que o frontend:
- **Só chama endpoints existentes** (verificado em compile-time)
- **Só renderiza dados válidos** (verificado em runtime)
- **Falha de forma explícita e auditável** quando há mismatch

---

## Regras Inegociáveis

### R1: Zero `any` em Respostas Críticas
- Endpoints `/v1/explain/*`, `/v1/twin/*`, `/v1/factory/*` **NÃO PODEM** usar `any`.
- Se o tipo não existir: gerar ou bloquear feature.

### R2: Validação Runtime Obrigatória
- Toda resposta de endpoint crítico passa por validação Zod.
- Falha de validação → estado `DEGRADED` (não crash silencioso).

### R3: Datas em ISO8601 UTC
- Backend **SEMPRE** retorna datas em ISO8601 UTC.
- Frontend valida e converte para timezone local na renderização.

### R4: Cliente HTTP Único
- Toda chamada passa pelo cliente centralizado.
- Headers obrigatórios: `Authorization`, `X-Tenant-Id`, `X-Correlation-Id`.

---

## Implementação Frontend

### 1. Geração de Tipos a partir do OpenAPI

#### Dependências
```json
{
  "devDependencies": {
    "openapi-typescript": "^7.x",
    "openapi-fetch": "^0.x"
  },
  "dependencies": {
    "zod": "^3.x"
  }
}
```

#### Scripts
```json
{
  "scripts": {
    "gen:api": "openapi-typescript ../contracts/openapi.json -o src/gen/openapi.d.ts",
    "gen:api:check": "npm run gen:api && git diff --exit-code src/gen/openapi.d.ts"
  }
}
```

#### Output
```
frontend/src/gen/
├── openapi.d.ts    # Tipos gerados do OpenAPI
└── index.ts        # Re-exports
```

### 2. Validadores Runtime com Zod

#### Estrutura
```
frontend/src/lib/
├── validate.ts           # Utilitários de validação
├── schemas/
│   ├── index.ts          # Re-exports
│   ├── common.ts         # Schemas comuns (ProblemDetail, etc.)
│   ├── explained-value.ts # Schema ExplainedValue
│   ├── factory.ts        # Schemas Factory Data Product
│   └── twin.ts           # Schemas Twin Sandbox
```

#### API de Validação
```typescript
// validate.ts
import { z, ZodSchema, ZodError } from 'zod';

export type ValidationStatus = 'OK' | 'WARNING' | 'DEGRADED' | 'BLOCKED';

export interface ValidationResult<T> {
  success: boolean;
  data?: T;
  status: ValidationStatus;
  errors?: z.ZodIssue[];
  correlationId?: string;
}

export function validateOrThrow<T>(
  schema: ZodSchema<T>,
  payload: unknown,
  ctx: { correlationId?: string; endpoint?: string }
): T;

export function validateSafe<T>(
  schema: ZodSchema<T>,
  payload: unknown,
  ctx: { correlationId?: string; endpoint?: string }
): ValidationResult<T>;
```

### 3. HTTP Client Único

#### Estrutura
```
frontend/src/lib/
├── http-client.ts        # Cliente HTTP centralizado
├── api-client.ts         # Cliente tipado (usa openapi-fetch)
└── request-context.ts    # Context para headers
```

#### Features do Cliente
1. **Headers automáticos**: `Authorization`, `X-Tenant-Id`, `X-Correlation-Id`
2. **Validação runtime**: Zod schema quando disponível
3. **Mapeamento de erros**: ProblemDetail → UI state
4. **Retry com backoff**: Para erros transitórios
5. **Circuit breaker**: Protecção contra cascade failures

#### API do Cliente
```typescript
// http-client.ts
export interface RequestOptions<T> {
  schema?: ZodSchema<T>;      // Schema Zod para validação
  skipValidation?: boolean;   // Bypass (apenas para debug)
  retries?: number;           // Número de retries
  timeout?: number;           // Timeout em ms
}

export interface ApiResponse<T> {
  data: T | null;
  status: ValidationStatus;
  httpStatus: number;
  error?: ProblemDetail;
  validationErrors?: z.ZodIssue[];
  correlationId: string;
}

export async function request<T>(
  method: string,
  path: string,
  options?: RequestOptions<T>
): Promise<ApiResponse<T>>;
```

### 4. Estados de Resposta

| Estado | Condição | UI Behaviour |
|--------|----------|--------------|
| `OK` | 2xx + validação passou | Renderiza normalmente |
| `WARNING` | 2xx + validação com warnings | Renderiza + banner warning |
| `DEGRADED` | 2xx + validação falhou parcialmente | Renderiza parcial + alerta |
| `BLOCKED` | 4xx/5xx ou validação crítica falhou | Não renderiza + erro explícito |

---

## Implementação Backend

### 1. Response Models Obrigatórios

Todos os endpoints críticos DEVEM ter `response_model`:

```python
# ✅ Correcto
@router.get("/v1/explain/metric/{metric_id}", response_model=ExplainedValue)
async def get_metric(metric_id: str) -> ExplainedValue:
    ...

# ❌ Incorrecto
@router.get("/v1/explain/metric/{metric_id}")
async def get_metric(metric_id: str):
    return {...}  # Sem tipo!
```

### 2. Endpoints Críticos (Lista)

| Módulo | Endpoints | Response Model |
|--------|-----------|----------------|
| Explain | `/v1/explain/*` | `ExplainedValue`, `MetricDefinition` |
| Twin | `/v1/twin/scenarios/*` | `TwinScenario`, `TwinScenarioResult` |
| Factory | `/v1/factory/semantic/*` | `SemanticViewResponse` |
| Catalog | `/v1/catalog` | `CatalogResponse` |

### 3. Datas em ISO8601 UTC

```python
# Pydantic config para serialização de datas
from datetime import datetime, timezone

class BaseModel(PydanticBaseModel):
    class Config:
        json_encoders = {
            datetime: lambda v: v.astimezone(timezone.utc).isoformat()
        }
```

---

## Definition of Done (DoD)

### Gates de Saída

| Gate | Critério | Automatizado |
|------|----------|--------------|
| G1 | `npm run gen:api` não produz diff | ✅ CI |
| G2 | Endpoints críticos têm validação Zod | ✅ Tests |
| G3 | Zero `any` em ficheiros de endpoints críticos | ✅ ESLint |
| G4 | Backend endpoints têm response_model | ✅ Tests |
| G5 | Mismatch de schema gera DEGRADED, não crash | ✅ Tests |

### Testes Obrigatórios

```typescript
// Frontend tests
describe('Runtime Validation', () => {
  it('should validate ExplainedValue schema', () => {...});
  it('should return DEGRADED on partial schema match', () => {...});
  it('should return BLOCKED on critical validation failure', () => {...});
  it('should include correlation_id in validation errors', () => {...});
});

describe('HTTP Client', () => {
  it('should inject required headers', () => {...});
  it('should validate response with schema', () => {...});
  it('should map ProblemDetail to error state', () => {...});
  it('should retry on transient errors', () => {...});
});
```

---

## Ficheiros Criados/Modificados

### Frontend
- `frontend/package.json` — Dependências adicionadas
- `frontend/src/gen/openapi.d.ts` — Tipos gerados
- `frontend/src/lib/validate.ts` — Validação runtime
- `frontend/src/lib/schemas/*.ts` — Schemas Zod
- `frontend/src/lib/http-client.ts` — Cliente HTTP
- `frontend/src/lib/api-client.ts` — Cliente tipado

### Backend
- Verificação de `response_model` em endpoints críticos

### CI
- `.github/workflows/contract-gate.yml` — Gate adicional

---

## Exemplos de Uso

### Chamada a Endpoint com Validação
```typescript
import { request } from '@/lib/http-client';
import { ExplainedValueSchema } from '@/lib/schemas';

const response = await request<ExplainedValue>(
  'GET',
  '/v1/explain/metric/lead_time_medio_teorico',
  { schema: ExplainedValueSchema }
);

if (response.status === 'OK') {
  // Dados válidos, pode renderizar
  renderMetric(response.data);
} else if (response.status === 'DEGRADED') {
  // Dados parciais, mostrar com aviso
  renderMetricWithWarning(response.data, response.validationErrors);
} else {
  // BLOCKED - mostrar erro
  showError(response.error);
}
```

### Validação Manual
```typescript
import { validateOrThrow, validateSafe } from '@/lib/validate';
import { ExplainedValueSchema } from '@/lib/schemas';

// Throws on failure
const metric = validateOrThrow(ExplainedValueSchema, apiResponse, {
  correlationId: 'req-123',
  endpoint: '/v1/explain/metric/x'
});

// Returns result object
const result = validateSafe(ExplainedValueSchema, apiResponse, {
  correlationId: 'req-123'
});
if (!result.success) {
  console.error('Validation failed:', result.errors);
}
```

---

## Referências

- [OpenAPI TypeScript](https://github.com/drwpow/openapi-typescript)
- [Zod](https://zod.dev/)
- [openapi-fetch](https://openapi-ts.pages.dev/openapi-fetch/)
- Contrato FE-BE-001: Contrato Canónico
- Contrato C20: Explainability


