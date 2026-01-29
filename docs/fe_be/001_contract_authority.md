# CONTRATO FE↔BE 001 — Contrato Canónico e Governança de API

## Metadata
- **ID**: FE-BE-001
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO

## Objectivo

Garantir que:
1. O backend é a **fonte canónica** dos contratos (OpenAPI + schemas).
2. O frontend **compila contra contratos gerados**, não contra suposições.
3. Qualquer **drift quebra o CI** (nunca chega a produção).

---

## Regras Inegociáveis

### R1: Backend é Autoridade Canónica
- O contrato canónico de explainability é **`ExplainedValue`** (definido no backend).
- O frontend **NÃO define** contratos de rede alternativos.
- OpenAPI gerado pelo backend é a **única fonte de verdade**.

### R2: Validação de Existência
- Qualquer endpoint chamado pelo frontend **tem de existir** no OpenAPI.
- CI gates validam esta regra automaticamente.

### R3: Proibições
- **PROIBIDO**: Frontend definir interfaces de API ad-hoc.
- **PROIBIDO**: Endpoints sem schema no OpenAPI.
- **PROIBIDO**: Erros com formato ad-hoc (fora do envelope padrão).

---

## Implementação

### 1. Exportar OpenAPI Estático (Artefacto de Contrato)

#### Script de Exportação
```
prodplan-one/scripts/export_openapi.py
```

**Funcionalidade**:
- Gera `contracts/openapi.json` a partir do FastAPI
- Calcula hash SHA256 do contrato
- Cria `contracts/openapi.meta.json` com metadata

**Uso**:
```bash
cd prodplan-one
python scripts/export_openapi.py
```

**Output**:
```
contracts/
├── openapi.json          # OpenAPI 3.1 spec completa
└── openapi.meta.json     # { "hash": "sha256:...", "version": "...", "generated_at": "..." }
```

### 2. Versionamento do Contrato

#### Header de Resposta
Todas as respostas do backend incluem:
```
X-Api-Contract: openapi@<sha256_short>
X-Api-Version: 1.0.0
```

#### Validação no Frontend
- Frontend lê `X-Api-Contract` header em cada resposta.
- Se header ausente ou hash diferente: UI mostra **banner DEGRADED**.
- Não bloqueia operação, mas alerta o utilizador.

### 3. Envelope de Erro Uniforme (RFC 7807)

#### Schema
```json
{
  "type": "string",          // URI que identifica o tipo de problema
  "title": "string",         // Descrição curta human-readable
  "status": "integer",       // HTTP status code
  "detail": "string",        // Explicação detalhada específica desta ocorrência
  "instance": "string",      // URI da instância específica do problema
  "error_code": "string",    // Código interno para programmatic handling
  "correlation_id": "string" // ID para correlação em logs
}
```

#### Exemplo
```json
{
  "type": "https://prodplan.io/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Field 'order_id' must be a valid UUID.",
  "instance": "/v1/orders/create",
  "error_code": "VALIDATION_FAILED",
  "correlation_id": "req-abc123-def456"
}
```

#### Implementação
- `src/shared/errors/problem_detail.py` - Modelo base
- `src/shared/errors/handlers.py` - Exception handlers
- Middleware adiciona `correlation_id` automaticamente

### 4. Catálogo Allow-List

#### Endpoint
```
GET /v1/catalog
```

#### Response Schema
```json
{
  "contract_version": "1.0.0",
  "contract_hash": "sha256:abc123...",
  "endpoints": [
    {
      "path": "/v1/factory/semantic/{view_id}",
      "method": "GET",
      "module": "factory",
      "requires_auth": true,
      "rate_limit": "100/min"
    }
  ],
  "views": [
    {
      "id": "v_lead_time_historico",
      "module": "factory_semantic",
      "requires_permission": null
    }
  ],
  "metrics": [
    {
      "id": "lead_time_medio_teorico",
      "version": "1.0.0",
      "status": "active",
      "trust_required": 50
    }
  ],
  "schema_versions": {
    "raw": "1.0.0",
    "curated": "1.0.0",
    "semantic": "1.0.0",
    "api": "1.0.0"
  }
}
```

---

## Definition of Done (DoD)

### Gates de Saída Obrigatórios

| Gate | Critério | Automatizado |
|------|----------|--------------|
| G1 | `contracts/openapi.json` existe e é gerado automaticamente | ✅ CI |
| G2 | Frontend compila com tipos gerados a partir do OpenAPI | ✅ CI |
| G3 | CI falha se OpenAPI gerado ≠ ficheiro committed | ✅ CI |
| G4 | Erros do backend seguem sempre o envelope RFC7807 | ✅ Tests |
| G5 | Header `X-Api-Contract` presente em todas as respostas | ✅ Tests |
| G6 | Endpoint `/v1/catalog` retorna schema válido | ✅ Tests |

### CI Workflow

```yaml
# .github/workflows/contract-gate.yml
name: Contract Gate

on:
  pull_request:
    paths:
      - 'prodplan-one/src/**'
      - 'prodplan-one/contracts/**'
      - 'prodplan-one/frontend/**'

jobs:
  contract-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Generate OpenAPI
        run: |
          cd prodplan-one
          python scripts/export_openapi.py
      
      - name: Check Contract Drift
        run: |
          cd prodplan-one
          git diff --exit-code contracts/openapi.json || \
            (echo "❌ OpenAPI drift detected! Regenerate and commit." && exit 1)
      
      - name: Generate Frontend Types
        run: |
          cd prodplan-one/frontend
          npm run generate:types
      
      - name: Build Frontend
        run: |
          cd prodplan-one/frontend
          npm run build
```

---

## Ficheiros Criados/Modificados

### Backend
- `prodplan-one/scripts/export_openapi.py` - Script de exportação
- `prodplan-one/contracts/openapi.json` - Contrato gerado
- `prodplan-one/contracts/openapi.meta.json` - Metadata do contrato
- `prodplan-one/src/shared/errors/problem_detail.py` - RFC7807 models
- `prodplan-one/src/shared/errors/handlers.py` - Exception handlers
- `prodplan-one/src/shared/middleware/contract_header.py` - Header middleware
- `prodplan-one/src/catalog/api/endpoints.py` - Catálogo API

### Frontend
- `prodplan-one/frontend/src/lib/api-types.ts` - Tipos gerados
- `prodplan-one/frontend/src/hooks/useContractValidation.ts` - Validação runtime

### CI
- `.github/workflows/contract-gate.yml` - CI workflow

---

## Glossário

| Termo | Definição |
|-------|-----------|
| **Contrato Canónico** | OpenAPI spec gerada pelo backend, única fonte de verdade |
| **Drift** | Diferença entre contrato committed e contrato gerado |
| **RFC7807** | Standard para Problem Details (erro estruturado) |
| **ExplainedValue** | Envelope de valor explicável (C20) |

---

## Referências

- [RFC 7807 - Problem Details for HTTP APIs](https://tools.ietf.org/html/rfc7807)
- [OpenAPI 3.1 Specification](https://spec.openapis.org/oas/v3.1.0)
- Contrato C20 - Explainability
- Contrato C10 - Factory Data Product


