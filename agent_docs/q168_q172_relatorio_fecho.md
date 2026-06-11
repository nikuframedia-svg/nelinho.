# Relatório de fecho — Campanha total Q.168→Q.172

**Objectivo (Luis, 2026-06-10):** "tornar o software mesmo funcional, com o CP-SAT a
respeitar a lógica toda, com os dados corretos, com todas as funcionalidades
interligadas, com tudo mesmo a sério, testa tudo, e resolve os bugs todos."

**Âmbito de partida:** auditoria de 459 agentes (2 rondas adversariais) → 143 bugs
confirmados + 164 achados por triar + 175 features rastreadas (23 com defeito).
Decisões registadas: escrita no ERP fica FORA (advisory honesto); push+merge
autorizado.

## Números antes → depois

| Métrica | Antes (2026-06-10) | Depois (2026-06-11) |
|---|---|---|
| `verify.ps1` | 2 gates vermelhos (dívida "conhecida") | **ALL GREEN** |
| `pytest tests/` completo | 143 bugs por corrigir; vermelhos pré-existentes | **4424 passed, 0 failed** (incl. live LLM+BD, 1ª vez) |
| `ruff check src/` | dezenas de violações + DTZ desligado | **100% limpo**, família DTZ inteira banida no CI |
| Ordens com due date real no CPO | 0% (loader deixava cair) | **79,2%** + tardiness no objectivo CP-SAT |
| Cura química em produção | **MORTA** (lookup id-vs-nome → gap 0.0h desde sempre) | viva nos 4 caminhos + validador |
| Makespan (A/B live, mesmo scope) | 4367 h (greedy) | **690 h** (CP-SAT global; tardiness 32k vs 3,05M h) |
| Validador universal | não existia | `validate_schedule` RECUSA escrita inválida nos 2 caminhos (robô + drag delta-aware), gate WG2 no CI |
| Copiloto Cube em produção | **MORTO** (prompt 47KB truncado por num_ctx=4096 → 100% abstain) | vivo (auto-size + erro honesto em truncação), provado na API servida |
| Clientes por camião (/expedicao) | 0/17 batches (coluna ORM inexistente desde Q.116.C) | **17/17** via `OF_E_ID_ENC` real |
| Backlog de achados (164) | por triar | **ZERO** — 92+18 corrigidos/arquivados, 41 já-corrigidos, 8 refutados, 7 decisões documentadas |
| Features rastreadas (175) | 152 FUNCIONA + 23 com defeito | **175/175** = 163 FUNCIONA + 12 removidas-honestas/fechadas (re-rastreio final por 8 agentes + Q.172.E) |
| Identidade nas escritas | autor = tenant UUID; SoD com roles hardcoded | user real (JWT/dev-header) + SoD com roles do contexto, provado live (403 no e2e) |
| Tempo (timezone) | 124 `utcnow()` + 83 `date.today()` + 27 sites finos | 0 — helpers canónicos (`utc_now`/`utc_now_naive`/`local_today`/`local_now_naive`), semântica decidida site a site |

## E2E novos (correm no fecho de cada fase)

- `scripts/e2e_plan_smoke.py` — **10/10**: robô→DRAFT→validador 7 checks→SoD
  403→grid→drag válido→drag recusado por axioma→reapply preserva override→operador.
- `scripts/q117_llm_live_verify.py` — copiloto (intent+LLM) e rule-author OK.

## Gates permanentes novos (nunca mais regride em silêncio)

1. **DTZ001/003/004/005/007/011/901** no ruff — família de bugs tz banida.
2. **test_tenant_route_coverage_q168d** — rota nova sem tenant/dev_only/whitelist parte o CI
   (apanhou 1 rota nova DURANTE a própria campanha).
3. **WG2** — validador universal ligado aos 2 caminhos de escrita.
4. **HD1** — padrões de mock no backend recusados (invariante #8).
5. Drift gate re-baselined: Q61_07 5→1, Q61_28 275→69, audit_coverage 1→0.

## Bugs de produção descobertos pelo MÉTODO (prova live obrigatória)

Nenhum destes era visível na suite de testes — só a prova live os apanhou:

1. **Cura química morta** — `phase_id` numérico vs mapa keyed por nome → 0.0h sempre.
2. **Sequências empatadas paralelas** — barco em 2 fases ao mesmo tempo.
3. **Copiloto Cube morto** — truncação silenciosa do prompt (num_ctx).
4. **Transporte sem clientes + suggestions 500** — atributo ORM inexistente, AttributeError engolido.
5. **Detectores do preview mortos** — liam `start`/`end` mas as ops têm `start_time`/`end_time`.

## Fora de âmbito (decisões registadas)

- Escrita real no ERP (feat/q44z) — advisory honesto na UI; campanha própria com aval da NELO.
- Refactor do OverallPage (1193 linhas) — diferido até o e2e dar rede; funcional e provado live.
- 2 sistemas de decisão — camadas intencionais (F4 do saneamento), fronteira documentada.
- Idempotência multi-worker do /ask — documentada; Redis quando o deploy mudar.

## Rastos

- Plano: `.claude/plans/analisa-o-projecto-de-fuzzy-pike.md`
- Triagem dos 164: `agent_docs/backlog_164_triagem.md` (+ veredictos em `_dbprof/`)
- Matriz axioma×caminho: `agent_docs/axiom_parity_matrix.md`
- Remoções: `DELETION_LOG.md`
- Commits: Q.168.A → Q.172.E (ver `git log --oneline`), ~35 commits, 1 sub-sprint = 1 commit,
  todos com teste-que-falhava-antes + prova live + reviewer independente antes do commit.
