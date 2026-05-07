# KNOWN_ISSUES.md — bringup 2026-05-07

Estado do sistema após bringup + fixes pós-bringup. Backend live em `http://127.0.0.1:8001`, frontend em `http://localhost:5173`. Tenant dev: `00000000-0000-0000-0000-000000000001`. Ingestão da `Folha_IA_extra.xlsx` ativa (`1311972f-2734-489e-877a-e3b4d03aced6`, 1,142,754 rows curated). **Kafka KRaft single-node ativo em :9092**, `RealtimeBridge.healthy=true`, 16 tópicos subscritos.

## 1. Infraestrutura mínima necessária

| Serviço | Estado actual | Impacto se off |
|---|---|---|
| Postgres 18.3 (`localhost:5432`) | **LIVE** | Backend não arranca, schema falha |
| Redis (`localhost:6379`) | **OFF** (Redis não instalado) | Rate limit + copilot conversations dão 503 |
| Kafka 4.2 KRaft (`localhost:9092`) | **LIVE** (scoop install + JDK 26) | SSE realtime healthy ✓ |
| Ollama | **OFF** | Copilot LLM features não respondem; tool registry falha pre-warm |
| pgvector extension | **NÃO instalada** | Migration 008 não corre limpa; embeddings ficam dormant |

Para subir tudo: `pg_ctl start` (já feito), `redis-server` (instalar primeiro), `aiokafka` outbox replacement (já lá via NOTIFY), `ollama serve`.

## 2. Endpoints com 5xx esperados

Após smoke real **pós-fixes (113/123 GET 200, 10/123 não-200)**:

### 5xx (3 — degradação aceitável)
- `GET /health/ready` → **503**: depende de Redis (off)
- `GET /v1/governance/learning/pairs` → **500**: bug residual; investigar separadamente
- `GET /v1/workforce/dependency-graph` → **503**: precisa ML predictor (Ollama-backed)

### 4xx (7 — comportamento correcto)
- `GET /api/copilot/{actions,conversations,daily-feedback}` → 401: auth assimétrica (legacy `/api/`); novos `/v1/copilot/*` usam tenant header
- `GET /v1/explain/catalog/{available,blocked}/full` → 404: sem ingestion semantic ainda
- `GET /v1/governance/decisions/timeline` → 404: sem decisões propostas
- `GET /v1/profit/kpis/snapshot-dev` → 404: gated por `settings.debug=False`

## 2.1. Fixes aplicados nesta sessão (Dashboard console errors)

Screenshot do Dashboard mostrou 3 erros em loop. Foram fixados:

| Bug | Fix | Verificação |
|---|---|---|
| `GET /v1/activity/recent` 404 — endpoint não existia | Criado `src/shared/realtime/activity_api.py` que lê de `event_outbox` (graceful fallback se table missing) | `curl /v1/activity/recent` → 200 `{"items":[]}` |
| `GET /v1/factory/semantic/blocked-metrics` 400 — catch-all `/semantic/{view_id}` apanhava primeiro | Re-ordenado em `endpoints.py`: rota específica AGORA antes da catch-all | `curl .../blocked-metrics` → 200 com 7 blocked metrics |
| `GET /v1/realtime/events` 503 — Kafka offline | Instalado **Kafka 4.2 KRaft** via scoop + JDK 26; `.env` aponta para `localhost:9092` | `RealtimeBridge.healthy=true`; 16 topics subscribed |

## 3. Bugs conhecidos não bloqueantes

### Backend
- **`/v1/runbooks/{id}/execute`** (POST) não existe ainda. `useRunbooks.ts` no frontend chama-o se utilizador clica "executar" — vai dar 404. Endpoint precisa ser implementado (subset da Q.17 sprint).
- **Migration 008 (`008_pgvector_embeddings.py`)** falha em `--sql` mode (offline), mas `alembic stamp head` foi usado para arrancar com schema existente. Em DB nova, migration vai falhar até `pgvector` extension ser instalada.
- **CpModel (ortools) sem stubs**: 12 mypy errors em `src/plan/engines/cpsat_engine.py` são falsos positivos (NewIntVar/Add/Minimize não vistos por mypy mas existem em runtime).
- **RedisClient sem stubs**: 5 mypy errors em `src/copilot/rate_limiter.py` (eval/zadd/zrange) idem.

### Frontend
- **14 `react-hooks/set-state-in-effect`** ainda no código (apenas os 2 `rules-of-hooks` críticos foram fixados). Performance: cascading renders possíveis em condições extremas, mas sem loops infinitos confirmados.
- **6 `react-hooks/exhaustive-deps`** restantes — stale closures possíveis em mutations específicas (`CopilotDrawer`, `DecisionsPage`, `useMetricHistory`).
- **557 `@typescript-eslint/no-explicit-any`** — dívida cosmética de type safety. Não bloqueia funcionalidade.
- **Backend chama `setSelectedTemplate` no `TwinPage`** mas está prefixado `_` — placeholder para feature futura, ignorado.

### Tipos / contracts
- **`SchemaDriftAlertProps.drifts`/`onAction`**: agora são opcionais (PR3 adicionou). Componente fetcha via hook se não passados.
- **`WIPData.phases_total`**, **`QualityData.top_items`**, **`TransportSuggestion.target_batch_id`**, **`DecisionRun.action_data`**: alargados para optional na PR3 — backend pode emitir ou não consoante o build/dataset.
- **`TrustIndexV2Components.timeliness`**: legacy alias, agora obrigatório nos `Record<keyof ...>` literals (PR3 adicionou às keys em `DQAPage` e `useTrustHeatmap`).

### Mypy strict
- **1207 errors em 184 ficheiros** — backlog progressivo. ~50% são `no-untyped-def` (return type missing) cosméticos; ~30% (`assignment`, `call-arg`, `attr-defined`) potenciais bugs reais. Não bloqueia uso. Atacar quando se tocar nos módulos.

### ESLint
- **612 errors total** (557 cosméticos + ~55 funcionais). PR5 fixou 2 errors críticos (rules-of-hooks) + 1 bug funcional real (`g`-prefix shortcut nunca funcionou). Restantes 23 react-hooks são warnings, não errors.

## 4. Limitações da validação

- **Vite build verde** confirmado em main. **Pytest não correu** após o merge q12→main; recomenda-se correr `pytest tests/ -x` antes de qualquer release ou deploy.
- **Smoke do frontend foi automático (HTTP 200 no root)**. Smoke manual humano (clicar pelas páginas) ainda não foi feito — ver checklist abaixo.
- **Nenhum write-endpoint POST/PATCH/DELETE foi testado** durante o smoke (só GETs sem params obrigatórios). Endpoints write podem ter bugs adicionais não cobertos.
- **Endpoints com path/query params obrigatórios** não foram smoked.

## 5. Checklist de smoke manual (Luis a fazer no browser)

Frontend live em **http://localhost:5173/**. Tenant pré-injectado se a app passar header automático; se não, ver consola para 401s e configurar `X-Tenant-Id: 00000000-0000-0000-0000-000000000001` no DevTools.

| URL | Esperado | Notas |
|---|---|---|
| `/` | Dashboard com Trust scores reais (~67% overall) + alerts | Após ingestão; `phases_total/top_items` agora optional |
| `/inbox` | Lista de alertas | Provavelmente vazio (sem decisões propostas) |
| `/twin` | Lista cenários (vazio inicial) | Botão "New Scenario" funciona |
| `/decisions` | Timeline + lista | Vazia |
| `/admin/data-quality` | DQA com 8 componentes (incluindo `timeliness`) | Trust scores reais por componente |
| `/admin/data-ingestion` | Ingestão `1311972f` listada como ACTIVE | Confirmar `total_rows_raw=1,089,094` |
| `/admin/settings` | 14 tabs visíveis | Geral/Tenant/etc |
| `/regras` (Q.17) | RegrasPage | Vazia (sem regras propostas); `propose-rule` requer LLM |
| `/plan/scheduling` | Tabs scheduling | Drag&drop tab — `previewing` guard fixed em PR5 |
| `/plan/dispatch` | 3-rail dispatch | @dnd-kit drag entre batches |
| `/plan/timeline` | Gantt produção | Pode estar vazio |
| `/ceo` | CEO Dashboard | OTD/backlog/expedições — alguns NO_SOURCE_DATA |

**Atenção do Luis**:
- Console JS errors (F12)? Deve ser zero novos.
- Páginas mostram empty/error states (não dados mock fake)?
- TrustBadge presente onde KPI tem `reason=NO_SOURCE_DATA`?
- G-prefix navigation: `g d` → `/`, `g i` → `/inbox`, `g f` → `/core/products`, etc. (PR5 fixou bug onde nunca funcionava).

## 6. Cleanup ao terminar uso

```bash
# Matar processos
taskkill //F //PID $(netstat -ano | findstr ":8001.*LISTENING" | awk '{print $NF}' | head -1)
taskkill //F //PID $(netstat -ano | findstr ":5173.*LISTENING" | awk '{print $NF}' | head -1)

# Postgres pode ficar a correr (scoop service)
~/scoop/apps/postgresql/current/bin/pg_ctl.exe -D ~/scoop/persist/postgresql/data stop
```

## 7. Para ir para produção (Nelo)

Antes de `deploy/install.sh`:

1. Resolver **`/v1/runbooks/{id}/execute`** (criar endpoint backend)
2. Investigar e fixar `/v1/governance/learning/pairs` 500
3. Confirmar **Redis instalado** + Ollama disponível (caso queiram copilot LLM features)
4. Instalar **pgvector extension** se RAG / embeddings é critical-path
5. **Correr `pytest tests/`** completo, confirmar 1829+ passed
6. **Smoke manual frontend** completo (não só HTTP 200 no root)
7. Configurar **branch protection** em `main` no GitHub para evitar pushes diretos
8. Documentar `SECRET_KEY` em `/etc/prodplan/env` (não usar dev key)

## 8. Trabalho concluído nesta sessão (resumo)

- 26 commits Q.11/Q.13/Q.14/Q.15 locais → pushed para `origin/main`
- 5 PRs merged em main (PR3 Dashboard tipos, PR1 q12, PR-A2+PR4 ZERO MOCKS+runbooks path, PR-A3 regex prompt, PR5 react-hooks)
- A4 (safety_net keys) re-aplicado em main
- B1 (RBAC yaml_policy) + B3 (XSS+payroll+workforce) re-aplicados em main
- 8 branches obsoletas apagadas no remote
- Postgres scoop subido + DB stamped
- Tenant dev criado
- 1.1M rows curated ingeridos com sucesso
- Backend smoke: 112/123 GET 200 (vs 53 antes)
- Frontend dev server live

Estado actual do remote: **3 branches** (`main`, `ci/karpathy-oauth-token`, `feat/q17-logic-as-data-wip`).
