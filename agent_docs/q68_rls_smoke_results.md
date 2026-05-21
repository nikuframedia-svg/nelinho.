# Q.68.6.A — RLS isolation smoke (prod-like)

## Contexto

P16 da auditoria Q.68: o RLS multi-tenant entregue em Q.62.B criou 87
policies activas no DB + middleware + ContextVar + event listener + 14
testes unitários. Falta, no entanto, **prova ponta-a-ponta** com 2 tenants
reais e o role `nelinho_app` non-superuser — em dev o user é superuser por
design, logo RLS está aplicado mas **inerte** (Postgres bypassa policies
para roles superuser). Sem este smoke o "RLS está activo" é asserção; com
ele passa a ser verdade verificável.

Artefacto: `scripts/test_rls_isolation.sh`.

## O que o script prova

Passos 1-8 em `scripts/test_rls_isolation.sh`:

1. role `nelinho_app` existe (sai 1 se não — força aplicar
   `deploy/postgres/q62_rls_prod_role.sql`).
2. `pg_class.relrowsecurity = 1` em `plan.production_orders`
   (migration 056 aplicada).
3. cria 2 tenants A/B em `core.tenants` (idempotente, `ON CONFLICT DO
   NOTHING`).
4. popula 1 `production_order` por tenant via superuser
   (insert bypassa RLS, mas as linhas ficam tagged com `tenant_id`).
5. login como `nelinho_app`, `SET LOCAL app.tenant_id = A`, conta linhas
   → **esperado 1** (só vê A).
6. mesma sessão, `SET LOCAL app.tenant_id = B` → **esperado 1**.
7. sem `SET LOCAL` (ContextVar vazio) → **esperado 0** (fail-closed; o
   cast de string vazia para UUID falha silenciosamente e o predicate
   `tenant_id = current_setting('app.tenant_id')::uuid` filtra tudo).
8. `nelinho_app` autenticado como tenant A tenta `INSERT` linha com
   `tenant_id = B` → **esperado erro RLS** (WITH CHECK policy bloqueia).

Cleanup automático via `trap EXIT` — remove os 2 tenants + linhas mesmo
em falha.

## Estado actual (dev, 2026-05-21)

**RLS inerte por design.**

- `prodplan_one` corre com user superuser (`postgres` ou `prodplan`).
- `deploy/postgres/q62_rls_prod_role.sql` **não foi aplicado** (e bem —
  aplicar em dev quebra `FakeSession`/fixtures que não passam pelo
  middleware FastAPI; ver `multi_tenant_architecture.md` §4).
- Logo, `bash scripts/test_rls_isolation.sh` sai com **exit 1** no Step
  1 ("role nelinho_app missing").
- Comportamento esperado e documentado.

## Como correr prod-like (Q.69, na máquina NELO)

```bash
# UMA VEZ por máquina:
psql -U postgres -d prodplan_one \
     -f deploy/postgres/q62_rls_prod_role.sql

# password vault → env (ou usa default dev):
export NELINHO_APP_PASSWORD="<vault>"

# Smoke:
bash scripts/test_rls_isolation.sh \
     --report agent_docs/q68_rls_smoke_results.md
```

Output esperado em prod-like:

```
[HH:MM:SS] → Step 1: Verify nelinho_app role exists
[HH:MM:SS]    OK — role 'nelinho_app' presente
[HH:MM:SS] → Step 2: Verify RLS enabled em plan.production_orders
[HH:MM:SS]    OK — relrowsecurity=1
[HH:MM:SS] → Step 3: Create tenants A + B
[HH:MM:SS]    OK — 2 tenants em core.tenants
[HH:MM:SS] → Step 4: Populate 1 production_order por tenant
[HH:MM:SS]    OK — 2 linhas (1 por tenant)
[HH:MM:SS] → Step 5: Login as nelinho_app, SET LOCAL tenant_id=A
[HH:MM:SS]    Tenant A sees: 1 row(s) (expected: 1)
[HH:MM:SS] → Step 6: SET LOCAL tenant_id=B
[HH:MM:SS]    Tenant B sees: 1 row(s) (expected: 1)
[HH:MM:SS] → Step 7: Sem SET LOCAL (fail-closed)
[HH:MM:SS]    Sem SET LOCAL: 0 row(s) (expected: 0)
[HH:MM:SS] → Step 8: Cross-tenant write — A tenta INSERT como B
[HH:MM:SS]    OK — INSERT cross-tenant rejeitado pelo RLS
[HH:MM:SS] → Cleanup: remove test rows + tenants

RLS isolation PASSED
  - Tenant A: 1 (esperado 1)
  - Tenant B: 1 (esperado 1)
  - Sem SET LOCAL: 0 (esperado 0)
  - Cross-tenant INSERT bloqueado: sim
```

Exit 0 com `--report` apende uma secção `## Run <UTC timestamp>` a este
ficheiro para histórico.

## Carry-forward Q.69

- [ ] Correr o smoke na NELO uma vez (depois de `q62_rls_prod_role.sql`).
- [ ] Colar output verde na secção **Run real** abaixo.
- [ ] Adicionar invocação ao `scripts/dr-smoke.sh` se o resultado for
      determinístico em prod (gate de DR — confirma que restore não
      quebrou RLS).
- [ ] Hook em CI? Não — exige Postgres prod-like com role separado;
      manter como gate manual pós-deploy.

## Limitações conhecidas

- Smoke só cobre 1 tabela (`plan.production_orders`). As 86 restantes
  partilham o mesmo template de policy (`USING (tenant_id =
  current_setting(...))::uuid`), logo a prova vale por indução —
  mas se Luis quiser certeza explícita, replicar passos 4-8 para 2-3
  tabelas representativas (e.g. `quality.events`, `governance.audit_log`
  — nota: `audit_log` é global, não tenant-scoped).
- Não cobre escalada de privilégio via `SECURITY DEFINER` (não usamos).
- Não cobre RLS em copias replicadas/standbys (futuro Q.7x).

## Run real

_(secção a preencher quando o smoke correr na NELO; manter histórico —
um `## Run <timestamp>` por execução)._
