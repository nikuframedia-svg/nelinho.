# Q.135 — Dívida create_all/alembic: medição honesta + guard anti-regressão

**Branch:** `feat/q135-alembic-parity` (de `main` pós-merge Q.134). Pedido do Luis: "faz um
plano para [a dívida create_all/alembic: ~35 tabelas fora do alembic]". Entrega: merge local, sem push.

## Descoberta principal — a premissa estava ERRADA

O relatório do fim do Q.134 dizia "~35-49 tabelas create_all-only; fresh-DB faz 75 vs ~110 real;
o upgrade head já não aborta mas faltam tabelas". **Isso estava errado** — era um artefacto de uma
contagem FILTRADA por schema (o "75" excluía governance/supply/twin/dqa/ml/improve/sandbox/shared/
factory_meta).

**Medição definitiva (2026-05-31), BD fresca pura-alembic** (`DROP DATABASE` + `init-db.sql` +
`alembic upgrade head`):
- **125 tabelas** (= 124 ORM de `Base.metadata` + `alembic_version`). Breakdown por schema bate
  EXACTAMENTE com `Base.metadata`: core 19, plan 23, governance 12, profit 8, hr 8, supply 8,
  quality 4, factory_meta 4, dqa 3, twin 3, shared 3, reports 2, ml 1, improve 1, sandbox 1,
  factory_curated 10, factory_raw 1, public 13(+alembic_version).
- **NÃO há tabelas em falta.** As migrações 001-066 (incl. 055a Q.62.A.3 + 066 Q.134) já criam as
  124 tabelas ORM. A migração 067 catch-up que ia escrever criou **0 tabelas** (no-op) → removida.
- **Dev DB real = 146 tabelas.** A diferença (21) é toda `factory_raw` (22 dev vs 1 fresca) =
  mirrors do ERP NELO (`scripts/q75_setup_raw_mirror.py`, sync SQL Server), **não-ORM, fora do
  alembic de propósito**. Todos os outros schemas batem dev↔fresca.
- **RLS já está 100% completo** — 0 tenant tables sem policy `tenant_isolation` na BD fresca
  (056=87 + 065=7 + 066=2 cobrem tudo; o `test_rls_table_coverage_q62_b` confirma).

**Conclusão:** o risco de produção ("upgrade head abortar / faltar tabelas") **NÃO existe** —
fechou-se em Q.62.A.3 + Q.134. A premissa do pedido era o meu erro de medição do Q.134.

## O que RESTA mesmo (cosmético, decisão do Luis: lock-in leve)

1. **Drift de COLUNAS** (~808 ops no `alembic check`, REAL mesmo numa BD pura-alembic):
   474 `modify_default`, 248 índices (138 remove / 110 add, maioria renames),
   48 `modify_type` (vários espúrios, ex.: `TIMESTAMP` vs `DateTime` = idênticos), 18 `modify_comment`,
   ~24 risky (dropar índice HNSW, 4 colunas, fks/constraints). **Cosmético** (mesmo data), **tolerado
   pelo CI** (`alembic check` é `continue-on-error`). O Luis escolheu **NÃO** fazer o reconcílio
   grande/arriscado agora — fica como dívida documentada (era já o plano "Q.67.9.X").
2. **Gap das extensões no fresh-DB** (descoberto): as migrações usam `uuid_generate_v4()`
   (q115_a01) mas NENHUMA cria a extensão `uuid-ossp`/`pgcrypto` (só a 008 cria `vector`). Logo
   `alembic upgrade head` numa BD fresca **sem `init-db.sql`** rebenta. Em produção o provisioning
   corre `scripts/init-db.sql` antes (deploy/systemd) → OK. Mas o **job `alembic` do CI não corria
   init-db.sql** → estava a rebentar no upgrade head. Corrigido (ver abaixo).

## O que foi feito (Q.135)

- **Teste de paridade** `tests/integration/test_alembic_table_parity.py`: numa BD pura-alembic, toda
  a tabela de `Base.metadata` existe (`ORM ⊆ BD`, subset — tolera factory_raw/marts extra). Skip
  gracioso sem BD (integration). Análogo do `test_rls_table_coverage_q62_b` (cobertura RLS, que já
  existia). **Guard anti-regressão**: falha se um modelo novo ficar create_all-only.
- **CI job `alembic`** (`.github/workflows/ci.yml`): (1) novo passo que corre `scripts/init-db.sql`
  (extensões + schemas) ANTES do `alembic upgrade head` — espelha produção, corrige o vermelho;
  (2) novo passo HARD que corre os 2 guards (paridade tabelas + cobertura RLS) numa BD pura-alembic.
  O `alembic check` continua `continue-on-error` (drift de colunas tolerado).
- **Limpeza:** removido `# noqa: F401` redundante (F401 é ignorado globalmente no ruff.toml → RUF100)
  no teste novo e no `test_rls_coverage_qr_audit.py` — mantém `ruff check tests/` (CI) verde.

## Verificação
- Fresh DB: `init-db.sql` + `alembic upgrade head` SUCEDE; 125 tabelas; `ORM ⊆ BD` ✓.
- 2 guards (paridade + RLS) **passam** contra a BD fresca pura-alembic; **skip** sem BD.
- `ruff` limpo nos ficheiros tocados; `verify.ps1` ALL GREEN (ver gate).
- Sem alterações a migrações (067 no-op removida) → zero risco de schema.

## Dívida deixada (honesta, fora do âmbito por decisão)
- Reconcílio do drift de colunas (~808 ops) → `alembic check` 100% verde + flip CI hard-fail.
  Grande, delicado, cosmético. Sprint futuro se/quando o Luis quiser.
- O job `test` do CI corre `pytest tests/` SEM postgres → os testes `@pytest.mark.integration` que
  se auto-ligam (ex.: o RLS coverage existente) FALHAM lá (pré-existente). O novo teste faz skip
  gracioso; um conftest a saltar `integration` sem infra fecharia a classe (não feito — fora do âmbito).
