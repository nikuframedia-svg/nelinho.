# Multi-tenant Architecture — Decisão Q.67.5

## Contexto

Q.62.B entregou RLS multi-tenant em 87 tabelas + middleware + ContextVar
+ event listener + 14 testes. Custo runtime estimado ~10%. Em Q.67.5
decidiu-se MANTER esta arquitectura (caminho A — recomendado), em vez de
fixar single-tenant NELO (caminho B).

## Decisão

**MANTER multi-tenant + RLS.**

### Razões

1. **Já está testado + prod-ready** (Q.62.B): 87 policies + middleware +
   ContextVar + event listener + 14 testes verdes. Apagar = quebrar pipeline
   testado.
2. **Apagar implicaria revisão de 87 policies** + migration drop + remoção
   de middleware + remoção de ContextVar + remoção de event listener — risco
   alto, não-reversível sem refactor grande.
3. **Custo ~10% aceitável** para optionalidade futura (outros clientes
   eventuais — Cosmar, FishingKayak, etc.).
4. **Defense-in-depth**: RLS dá protecção mesmo se um bug aplicacional
   esquecer tenant filter no query.

### Caminho B (NÃO escolhido)

Fixar single-tenant exigiria:
- alembic migration 061_q67_drop_rls.py (DROP POLICY × 87)
- Apagar TenantContextMiddleware + _set_tenant_id_on_transaction_begin
- Apagar ContextVar app.tenant_id
- Apagar 14 testes RLS
- Manter `require_tenant_header` para auditoria (não enforcement)

Estimado 3-5 dias com alto risco. Sem ganho real para single-tenant
actual.

## Invariantes

1. **`X-Tenant-Id` header obrigatório** em todos os requests (excepto
   `/health`, `/openapi.json`). Validado por `require_tenant_header`.
2. **Dev tenant**: `00000000-0000-0000-0000-000000000001`.
3. **Em prod**: aplicar `deploy/postgres/q62_rls_prod_role.sql` UMA VEZ
   para criar role `nelinho_app` non-superuser. Sem isto, RLS está aplicado
   mas inerte (superuser bypassa policies por design).
4. **Event listener**: cada transacção (begin) executa `SET LOCAL
   app.tenant_id = '<UUID>'` baseado em `ContextVar`. Falha se ContextVar
   vazio (não-bypassable).
5. **Q.67.4 copilot SQL livre**: role `nelinho_copilot` (SELECT-only)
   também respeita RLS — o copiloto SÓ vê dados do tenant configurado.

## 87 tabelas com RLS (Q.62.B)

Listar via:
```sql
SELECT schemaname, tablename
FROM pg_policies
WHERE policyname = 'tenant_isolation'
ORDER BY schemaname, tablename;
```

Schemas cobertos: `plan, core, supply, hr, quality, profit, governance,
dqa, twin, factory_curated, factory_meta, reports, shared, improve, sandbox`.

Tabelas SEM `tenant_id` (não-RLS — global): `core.audit_log`,
`core.tenants`, `core.etl_run`, schemas de Alembic.

## Verificação

### Smoke RLS prod-like (Q.67.5.A1)

```bash
# 1. Aplicar role + RLS effective
psql -U postgres -d prodplan_one -f deploy/postgres/q62_rls_prod_role.sql

# 2. Criar 2 tenants
psql -U postgres -d prodplan_one -c "
INSERT INTO core.tenants (id, name) VALUES
  ('11111111-1111-1111-1111-111111111111', 'Tenant A'),
  ('22222222-2222-2222-2222-222222222222', 'Tenant B');
"

# 3. Popular dados (1 ordem por tenant)
psql -U postgres -d prodplan_one -c "
INSERT INTO plan.production_orders (id, tenant_id, ...)
VALUES
  (gen_random_uuid(), '11111111-...', ...),
  (gen_random_uuid(), '22222222-...', ...);
"

# 4. Login como nelinho_app + tentar SELECT como Tenant A
psql -U nelinho_app -d prodplan_one -c "
SET LOCAL app.tenant_id = '11111111-1111-1111-1111-111111111111';
SELECT count(*) FROM plan.production_orders;
-- Esperado: 1 (não 2)
"

# 5. Trocar para Tenant B
psql -U nelinho_app -d prodplan_one -c "
SET LOCAL app.tenant_id = '22222222-2222-2222-2222-222222222222';
SELECT count(*) FROM plan.production_orders;
-- Esperado: 1 (não 2)
"

# 6. Sem SET LOCAL → 0 rows (fail-closed)
psql -U nelinho_app -d prodplan_one -c "
SELECT count(*) FROM plan.production_orders;
-- Esperado: 0 (ContextVar vazio)
"
```

### Dev (superuser)

Em dev, `prodplan` user é superuser por default. RLS está criado mas inerte.
**NÃO** aplicar `q62_rls_prod_role.sql` em dev — quebraria tests
(FakeSession + fixtures não passam pelo middleware).

## Decisões pendentes Q.68+

- **Tenant onboarding flow** (Q.68.X): UI + API para criar tenant + provisionar
  primeiro user admin. Hoje é manual via INSERT psql.
- **Tenant data export** (Q.68.X): GDPR right-to-data-portability.
- **Cross-tenant aggregation**: dashboards "todos os tenants" exigem role
  separado (nelinho_global_reader) com BYPASSRLS. Não implementado.

## Referências

- `alembic/versions/056_q62_b_rls_enable.py` — migration que cria as 87 policies
- `src/shared/auth/tenant_context.py` — ContextVar + middleware
- `src/shared/database.py` — event listener (`_set_tenant_id_on_transaction_begin`)
- `deploy/postgres/q62_rls_prod_role.sql` — prod role provisioning
- `deploy/postgres/q67_copilot_role.sql` — copilot read-only role (também respeita RLS)
- `tests/shared/test_rls_*.py` — 14 testes regressão
