# Postgres deployment scripts

Scripts que vivem fora do `alembic upgrade head` porque exigem direitos
de superuser, ou tocam em `ALTER ROLE`/`CREATE ROLE`.

## `q62_rls_prod_role.sql` — Q.62.B.1 RLS effective em prod

**Quando aplicar:** uma vez, em prod, depois de `alembic upgrade head`
ter aplicado as RLS policies (migration `056_q62_b_rls_enable`).

```bash
psql -U postgres -h <host> -d nelinho_prod -f q62_rls_prod_role.sql
```

**Não aplicar em dev/test** — o utilizador postgres dev é superuser e
ignora RLS por design; o stack funciona sem este passo. Em prod, sem
isto, as policies estão criadas mas inertes (superuser bypass).

**Pre-requisitos:**

- DB existe e tem schema migrado (Q.62.A chain repair completo).
- DB user `nelinho_user` existe (usado pelo backend FastAPI).

**Verificação post-apply (smoke 4 passos):**

```sql
-- 1. nelinho_user não pode logar como superuser
\du nelinho_user
-- (espera ver "No superuser" e "Cannot SET ROLE TO" excepto nelinho_app)

-- 2. Login como nelinho_user, sem SET LOCAL, retorna setting vazio:
SELECT current_setting('app.tenant_id', true);
-- → ''

-- 3. Insert dummy row e tenta select de outro tenant:
SET LOCAL app.tenant_id = '00000000-0000-0000-0000-000000000001';
SELECT count(*) FROM plan.schedule_commit;  -- N rows
SET LOCAL app.tenant_id = '00000000-0000-0000-0000-000000000002';
SELECT count(*) FROM plan.schedule_commit;  -- 0 rows (RLS isolou)

-- 4. Sem SET LOCAL — RLS bloqueia tudo:
RESET app.tenant_id;
SELECT count(*) FROM plan.schedule_commit;  -- 0 rows (fail-closed)
```

**Rollback (emergência):**

```sql
REVOKE nelinho_app FROM nelinho_user;
DROP ROLE nelinho_app;
ALTER USER nelinho_user WITH SUPERUSER;  -- só se necessario
```

---

## Outros scripts (futuro)

- `q63_*.sql` — operational migrations que `alembic upgrade head` não cobre.
- `q64_*.sql` — supply gap migrations se tiverem partes superuser-only.
