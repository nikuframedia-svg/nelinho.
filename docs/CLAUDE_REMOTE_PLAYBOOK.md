# CLAUDE_REMOTE_PLAYBOOK — Routine diária 7h

> Guia para Claude Code remoto executar `user_input` pendentes + evoluir
> nelinho em modo background (ontologia, query graph, runbooks, refactor).
> Sempre em PR — nunca push directo.

## 0. Identidade do loop

- **Frequência**: 07:00 BRT (10:00 UTC) diário, via `CronCreate` + skill `schedule`
- **Input**: `GET /v1/user-input?status=pending` (com header `X-Tenant-Id`)
- **Output**: PR no branch `main` via `gh pr create` + actualização `PATCH /v1/user-input/{id}` com `status=done` + `result_pr_url`
- **Branch convention**: `claude-remote/q116.{slug}` (ou `q117/q118/...` rotativo por dia)

## 1. Routing table — keyword → sub-agent

Heurística: lê `user_input.what` + `user_input.where_page`. Se ambíguo, escalar via Telegram reply ao Luis (não adivinhar).

| Pista no texto | Sub-agent | Exemplo |
|---|---|---|
| `página`, `UI`, `botão`, `tabela`, `gráfico`, `Decisões`, `Overall`, `LLM`, `Configurações`, `frontend` | **nelo-frontend** | "muda cor do botão Sim na página Decisões" |
| `CPO`, `scheduler`, `axioma`, `Spelke`, `fitness`, `decoder`, `safety_net`, `MAP-Elites`, `replan`, `chromossoma` | **nelo-cpo** | "ajusta weight de OTD no fitness" |
| `cube`, `measure`, `dimension`, `migration`, `alembic`, `pgvector`, `schema`, `ERP`, `master_data`, `RLS` | **nelo-cube-bd** | "adiciona measure de overtime à cube" |
| `prompt`, `LLM`, `Ollama`, `gemma`, `RAG`, `ontologia`, `query graph`, `fact_pack`, `tool_executor` | **nelo-copiloto** | "melhora prompt do system para PT-PT" |
| `qualidade`, `defeito`, `rework`, `runbook`, `error_code`, `SOP`, `procedimento` | **nelo-qualidade** | "adiciona runbook para erro LAM-3" |
| `stock`, `MRP`, `shortage`, `purchase_order`, `armazém`, `material`, `BOM`, `transporte` | **nelo-supply** | "expor stock de matéria-prima X" |
| Pedido envolve revisão ou conflicto entre 2 áreas | **nelo-reviewer** | "revê impacto da alteração X na CPO + cube" |

**Conflito**: se `where_page="overall"` mas o texto fala de CPO scheduler → `nelo-cpo` (decide por código, não por UI tab).

## 2. Invariantes invioláveis (cópia de skill `nelinho-invariants`)

Antes de submeter PR, conferir:

| ID | Verificação | Comando |
|---|---|---|
| **CX1** | CoeficienteX nunca usado como tempo | `pwsh scripts/verify_invariants.py` (CX1 check) |
| **C1** | `Chromosome` (não `ChromosomeV4`), `routing_choices` preservado | mesmo script |
| **C2** | `compute_fitness` (não `evaluate_fitness`) | mesmo script |
| **G1** | `generations >= 200` (50 é bug recorrente) | mesmo script |
| **G2** | MAP-Elites z-axis = `idle_pct` | mesmo script |
| **D1** | Curing gaps via `phase_transition_gaps.min_gap_hours()` | mesmo script |
| **S1** | `ScheduleCommit.rejected_alternatives` + `user_preference_signal` presentes | mesmo script |
| **W1** | Decisões: nenhum `TODO: Execute actual action` em `src/shared/api/decisions.py` | mesmo script |
| **T1** | `pytest --collect-only` count ≥ 1800 | mesmo script |

**Bloqueante**: 7 axiomas Spelke (exclusividade operador, precedência monotónica, exclusividade molde, skill match, dual-resource Laminagem 88.5%, 16 transições cura química, safety_net ≥ baseline). Nenhum pode ser violado por código novo.

**Outros invariantes do projecto (CLAUDE.md):**
- `requires_human_approval=True` em todas decisões Q.17 (`Literal[True]`)
- Frontend zero mocks (`const MOCK_X`, `data ?? [{...}]` proibidos)
- PT-PT estrito (utilizador, registo, gerir, fase, camião)
- Audit trail via `audit_change()` em cada mutação
- Tenant injection obrigatória (`X-Tenant-Id` header em todos os endpoints)

## 3. Padrão de PR

**Branch**: `claude-remote/q116.{slug}` ou similar — slug a partir de `what` truncado a 30 chars kebab-case.

**Commits**: 1 commit lógico = 1 sub-sprint Q.X.Y. Title ≤72 chars formato `Q.116.A: descrição curta`. Body explica WHY, refere `user_input.id`.

**Trailer obrigatório**:
```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

**PR body**:
```markdown
## Pedido original (user_input #{id})

> {what}

**Onde**: {where_page}  
**Razão económica**: {economic_reason}  
**Autor**: {author}

## Implementação

- Sub-agent: {sub-agent}
- Sub-sprints criados: Q.116.A, Q.116.B...
- Ficheiros tocados: {N} (ver diff)

## Verificações

- [x] `pwsh scripts/verify.ps1` verde
- [x] `pytest tests/{path}/test_q116_*.py -v` verde (N tests)
- [x] `npm run build` verde (se frontend)
- [x] `pwsh scripts/verify_invariants.py` zero violações
- [x] Zero mocks no diff
- [x] PT-PT
- [x] Audit trail em cada mutation

## Como testar manualmente

1. `nitro` (sobe stack)
2. {passos do user_input.where_page}
3. Confirmar comportamento esperado

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 4. Cenários de stop

Quando parar e escalar via Telegram reply ao Luis (em vez de continuar a tentar):

| Sinal | Acção |
|---|---|
| Violação de axioma Spelke detectada por safety_net | STOP — `reply` Telegram com axioma + linha + sugestão; NÃO submeter PR |
| Encoding/charset issue MSSQL→Postgres | STOP — invocar skill `nelinho-debug`; se não resolve em 1 tentativa, escalar |
| `pytest` red 3+ tentativas | STOP — escalar com diff actual + stderr |
| `user_input.what` ambíguo (Claude não consegue decidir sub-agent) | STOP — pedir esclarecimento via Telegram, NÃO adivinhar |
| Conflito com PR aberto em `main` | STOP — escalar; Luis decide merge order |
| `npm run build` falha por dependência | STOP — escalar; NÃO instalar packages novos sem aprovação |
| Migration conflito alembic heads | STOP — escalar; merge heads requer judgement humano |

**Sucesso**: PR aberto + `user_input.status=done` + `result_pr_url` actualizado + GitHub Action `pr-review.yml` aprovada.

## 5. Checklist pré-PR

Antes de `gh pr create`, correr **TODOS** os comandos abaixo. Qualquer red → STOP, não submeter.

```powershell
# 1. Lint Python
ruff check .

# 2. Type check Python
mypy src/ --strict-equality

# 3. Lint Frontend (zero mocks)
cd frontend && npm run lint
grep -rn "const MOCK_" src/ && echo "MOCK FOUND — abort" && exit 1
grep -rn " ?? \[{" src/ && echo "FALLBACK MOCK — abort" && exit 1
cd ..

# 4. Build frontend
cd frontend && npm run build && cd ..

# 5. Type check Frontend
cd frontend && npx tsc --noEmit && cd ..

# 6. Tests
pytest tests/{novo_path}/ -v

# 7. Invariants
pwsh scripts/verify_invariants.py

# 8. Verify geral (sobe stack, smokes)
pwsh scripts/verify.ps1
```

**Zero mocks check** (Q.115 invariant):
```bash
git diff main --name-only -- 'frontend/**/*.tsx' | xargs grep -l 'const MOCK_\|??\s*\[\{' && echo "MOCK leaked"
```

## 6. Mapa de sub-agents (responsabilidades)

| Agent | Owns | Read-only outside |
|---|---|---|
| **nelo-cpo** | `src/plan/cpo/`, `src/plan/api/`, `src/plan/services/`, `src/shared/api/decisions.py`, fitness weights | tudo o resto |
| **nelo-cube-bd** | `cube/model/**/*.yml`, `alembic/versions/**`, `src/shared/model_registry.py`, modelos SQLAlchemy, ETLs `src/adapters/nelo/etl/` | tudo o resto |
| **nelo-copiloto** | `src/copilot/**`, prompts, RAG, tool_executor, ontology, FactoryStateQuery, fact_pack | tudo o resto |
| **nelo-qualidade** | `src/quality/`, `defect_zone_service`, `defect_risk_service`, runbooks, rework | tudo o resto |
| **nelo-supply** | `src/supply/`, MRP, stock, purchase_orders, transport | tudo o resto |
| **nelo-frontend** | `frontend/src/**`, sem tocar em modelos backend | tudo o resto |
| **nelo-reviewer** | Read-only de tudo + escreve relatórios; aplica `pwsh scripts/verify.ps1`; bloqueia merge | só escrita em `agent_docs/q*_review.md` |

## 7. Modo 2 — background (sem user_input pendente)

Quando `GET /v1/user-input?status=pending` devolver `[]`, o loop NÃO termina silenciosamente — escolhe trabalho de fundo segundo **rotação semanal**:

| Dia da semana | Foco | Sub-agent | Output esperado |
|---|---|---|---|
| Segunda | Ontologia (`src/copilot/ontology/entities.py`) | nelo-copiloto | +5 entidades/relações novas descobertas em ETL recentes |
| Terça | Ontologia (continuação) + validação de consistência | nelo-copiloto | refactor de relações com confidence <0.5 |
| Quarta | Query graph (`FactoryStateQuery`) — novos sub-queries | nelo-copiloto | 1-2 métodos novos que respondem a perguntas do copilot que ficaram sem resposta últimos 7d |
| Quinta | Query graph — performance + truncagem token budget | nelo-copiloto | optimização de budget em métodos >150 tokens |
| Sexta | Runbooks aprendidos (re-run `learn_runbook_from_history` para top-20 error_codes) | nelo-qualidade | runbooks novos para aprovação humana |
| Sábado | Runbooks — revisão dos pendentes + sugerir aprovação/rejeição | nelo-qualidade | PR com sugestões de aprovação (Luis confirma) |
| Domingo | Refactor código — sigla `nelinho-discipline` (pequenas melhorias, sem features novas) | qualquer agent | PR com 1-3 refactors pequenos justificados |

**Regra geral Modo 2**: PR description tem que justificar valor concreto ("este sub-query elimina 3 questões do copilot que ficaram sem contexto na semana de X-Y"). Sem valor justificável → não criar PR.

## 8. Heurística "sub-agent ambíguo" (fallback)

Se o pedido toca em ≥2 áreas, escalonar usando **nelo-reviewer como meta-agente**:
1. nelo-reviewer lê o pedido + escreve `agent_docs/q116_routing_decision.md` explicando porquê escolheu cada agent
2. Decompõe o pedido em sub-sprints separados (Q.116.A para frontend, Q.116.B para backend, etc.)
3. Cada sub-sprint vai ao sub-agent apropriado
4. PR final agrupa todos os sub-commits

## 9. Falhas conhecidas a evitar (memória)

- **Worktree não isola** ([memory:agent_worktree_unreliable](.)): NÃO usar `isolation:"worktree"` para sub-agents — dá bases stale. Trabalhar no checkout principal, sequencial.
- **Charset MSSQL→Postgres**: forçar UTF-8 explícito nos ETLs (`adapters/nelo/etl/`).
- **Q.17 `requires_human_approval=True`**: nunca opt-out, mesmo que LLM "decida" que é seguro.
- **CoeficienteX nunca em `src/plan/cpo/`**: invariante CX1, falha CI imediatamente.
- **Frontend zero mocks**: nunca `const MOCK_X` nem `?? [{...}]`. Empty state + retry SEMPRE.

## 10. PT-PT vocabulário

Usar consistentemente (não PT-BR):
- "utilizador" não "usuário"
- "registo" não "registro"
- "tu" não "você"
- "camião" não "caminhão"
- "fase" (não "etapa" para fases de produção)
- "gerir" não "gerenciar"
- "encomenda" (cliente) vs "ordem de fabrico" (interna)

---

*Documento vivo. Actualizado em cada PR significativo.  
Última actualização: 2026-05-28 (Q.115.R initial).*
