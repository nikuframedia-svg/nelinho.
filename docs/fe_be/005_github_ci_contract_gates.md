# CONTRATO FE↔BE 005 — CI/CD no GitHub com Gates de Contrato

## Metadata
- **ID**: FE-BE-005
- **Versão**: 1.0.0
- **Data**: 2026-01-27
- **Estado**: IMPLEMENTADO
- **Depende de**: FE-BE-001, FE-BE-002, FE-BE-003, FE-BE-004

## Objectivo

Garantir que ao exportar para GitHub:
- **Qualquer drift quebra o merge** — contrato nunca diverge silenciosamente
- **Frontend nunca fica desalinhado** — tipos sempre sincronizados com OpenAPI
- **Qualidade mínima garantida** — testes passam antes de merge

---

## Arquitectura CI/CD

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Pull Request                                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Contract Gate  │   │  Backend Tests  │   │ Frontend Tests  │
│                 │   │                 │   │                 │
│ - OpenAPI diff  │   │ - Unit tests    │   │ - Lint          │
│ - Type gen diff │   │ - Integration   │   │ - Type check    │
│                 │   │                 │   │ - Unit tests    │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────┐
                    │   E2E Smoke     │
                    │                 │
                    │ - Dashboard     │
                    │ - Explain flow  │
                    │ - Simulate flow │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Merge Gate    │
                    │                 │
                    │ All checks pass │
                    │ → Allow merge   │
                    └─────────────────┘
```

---

## Workflows GitHub Actions

### A) Contract Gate (`contract-gate.yml`)

**Trigger**: Pull Request, Push to main/develop

**Steps**:
1. Checkout repository
2. Setup Python + Node.js
3. Install dependencies
4. Generate OpenAPI from backend
5. Compare with committed `contracts/openapi.json`
6. Generate TypeScript types from OpenAPI
7. Compare with committed `src/gen/openapi.d.ts`
8. Fail if any diff detected

**Failure Conditions**:
- OpenAPI schema changed but not committed
- Generated types changed but not committed

### B) Backend Tests (`backend-tests.yml`)

**Trigger**: Pull Request, Push to main/develop

**Steps**:
1. Checkout repository
2. Setup Python 3.11+
3. Install dependencies
4. Run linting (ruff/flake8)
5. Run type checking (mypy)
6. Run unit tests (pytest)
7. Run integration tests
8. Upload coverage report

**Failure Conditions**:
- Linting errors
- Type errors
- Test failures
- Coverage below threshold

### C) Frontend Tests (`frontend-tests.yml`)

**Trigger**: Pull Request, Push to main/develop

**Steps**:
1. Checkout repository
2. Setup Node.js 20+
3. Install dependencies
4. Run linting (ESLint strict mode)
5. Run type checking (TypeScript)
6. Run unit tests (Vitest)
7. Build production bundle
8. Upload coverage report

**Failure Conditions**:
- Linting errors (including `any` in critical files)
- Type errors
- Test failures
- Build failures

### D) E2E Smoke Tests (`e2e-smoke.yml`)

**Trigger**: Pull Request (after other checks pass)

**Steps**:
1. Checkout repository
2. Setup Python + Node.js
3. Start backend server
4. Start frontend dev server
5. Run Playwright smoke tests
6. Upload test artifacts (screenshots, videos)

**Smoke Test Scenarios**:
1. Dashboard loads successfully
2. KPI cards render with data
3. Click Explain icon → Drawer opens
4. Drawer shows correct sections
5. Click "Simular" → Sandbox panel opens
6. Simulation completes (mock or real)

---

## Branch Protection Rules

### Required for `main` and `develop`:

```yaml
required_status_checks:
  strict: true
  contexts:
    - "Contract Gate"
    - "Backend Tests"
    - "Frontend Tests"
    - "E2E Smoke Tests"

required_pull_request_reviews:
  required_approving_review_count: 1
  dismiss_stale_reviews: true

enforce_admins: true

restrictions: null

allow_force_pushes: false
allow_deletions: false
```

---

## Workflow Files

### contract-gate.yml

```yaml
name: Contract Gate

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

jobs:
  contract-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install backend dependencies
        run: |
          cd prodplan-one
          pip install -r requirements.txt
      
      - name: Generate OpenAPI
        run: |
          cd prodplan-one
          python scripts/export_openapi.py
      
      - name: Check OpenAPI drift
        run: |
          cd prodplan-one
          if ! git diff --exit-code contracts/openapi.json; then
            echo "❌ OpenAPI contract drift detected!"
            exit 1
          fi
      
      - name: Install frontend dependencies
        run: |
          cd prodplan-one/frontend
          npm ci
      
      - name: Generate TypeScript types
        run: |
          cd prodplan-one/frontend
          npm run gen:api
      
      - name: Check types drift
        run: |
          cd prodplan-one/frontend
          if ! git diff --exit-code src/gen/openapi.d.ts; then
            echo "❌ TypeScript types drift detected!"
            exit 1
          fi
```

---

## Definition of Done (DoD)

### Gates de Saída

| Gate | Critério | Workflow |
|------|----------|----------|
| G1 | OpenAPI committed = generated | contract-gate |
| G2 | Types committed = generated | contract-gate |
| G3 | Backend lint pass | backend-tests |
| G4 | Backend types pass | backend-tests |
| G5 | Backend tests pass | backend-tests |
| G6 | Frontend lint pass | frontend-tests |
| G7 | Frontend types pass | frontend-tests |
| G8 | Frontend tests pass | frontend-tests |
| G9 | Frontend build pass | frontend-tests |
| G10 | E2E smoke pass | e2e-smoke |

### PR Merge Blocked If:

1. ❌ OpenAPI mudou e não foi committed
2. ❌ Tipos gerados mudaram e não foram committed
3. ❌ Testes unitários falharam
4. ❌ Lint/type check falhou
5. ❌ E2E smoke falhou
6. ❌ Build falhou

---

## Comandos Locais

### Verificar contrato antes de commit:

```bash
# Backend: gerar OpenAPI
cd prodplan-one
python scripts/export_openapi.py

# Frontend: gerar tipos
cd prodplan-one/frontend
npm run gen:api

# Verificar se há alterações
git status
```

### Executar testes localmente:

```bash
# Backend
cd prodplan-one
pytest

# Frontend
cd prodplan-one/frontend
npm run test
npm run lint:strict

# E2E (requer servers a correr)
cd prodplan-one/frontend
npm run test:e2e
```

---

## Ficheiros Criados

### GitHub Actions
- `.github/workflows/contract-gate.yml`
- `.github/workflows/backend-tests.yml`
- `.github/workflows/frontend-tests.yml`
- `.github/workflows/e2e-smoke.yml`

### Playwright
- `prodplan-one/frontend/playwright.config.ts`
- `prodplan-one/frontend/e2e/smoke.spec.ts`

### Scripts
- `prodplan-one/scripts/export_openapi.py` (já existe)

---

## Troubleshooting

### "OpenAPI drift detected"

```bash
# Regenerar e commitar
cd prodplan-one
python scripts/export_openapi.py
git add contracts/openapi.json
git commit -m "chore: update OpenAPI contract"
```

### "Types drift detected"

```bash
# Regenerar e commitar
cd prodplan-one/frontend
npm run gen:api
git add src/gen/openapi.d.ts
git commit -m "chore: update generated types"
```

### "E2E smoke failed"

1. Verificar logs do Playwright
2. Ver screenshots/videos nos artifacts
3. Executar localmente para debug:
   ```bash
   npm run test:e2e -- --debug
   ```

---

## Referências

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Playwright Documentation](https://playwright.dev/)
- Contrato FE-BE-001 - Contrato Canónico
- Contrato FE-BE-002 - Cliente Tipado


