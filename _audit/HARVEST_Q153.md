# Q.153.E — Harvest & limpeza de branches (decisões documentadas)

**Data:** 2026-06-01. **Branch:** `feat/q153-planeamento-operacional` (base em main local
`b2f03aa`, **sem push**). **Âmbito:** decidir o que aproveitar das branches antigas para o goal
"/overall 100% operacional". Conclusão: **nada de essencial fica por integrar** — o núcleo já está
em main (via Q.131) e o resto é de baixo valor para este goal. **Nenhuma branch/worktree é apagada
aqui** (operação destrutiva → fica para o Luis confirmar, à boleia do push em E).

---

## 1. `feat/q126-cpo-real-dag` (worktree `C:/Users/User/nelinho-q126`) — ABANDONAR documentado

- **O que tem:** repontar o CPO de Excel→`factory_raw` (durações/rotas/molds/skills/WIP reais) +
  calibração causal-DAG opt-in (`src/copilot/causal/calibration.py`, `nelo_dag.py`,
  `scripts/calibrate_nelo_dag.py`).
- **Estado vs main:** a parte de **durações/rotas reais já está em main** (via Q.131, ver
  `[[project_q131_cpo_real_data]]`). Só fica por integrar a **calibração causal-DAG**, que vive em
  `src/copilot/causal/` e **não afecta a correcção do plano** (`src/plan/cpo/*`).
- **Decisão:** **abandonar documentado.** Baixo valor para "/overall operacional"; é tuning de um
  módulo de copiloto, ortogonal à lógica do plano que o Q.153.A1-A3 já corrigiu. Se um dia se
  quiser: **port manual** (não cherry-pick — `state.py`/`scheduler_run.py`/`routing_resolver.py`
  conflituam), com `tests/plan/test_q126_*` como rede.
- **Limpeza sugerida (Luis confirma):** `git worktree remove C:/Users/User/nelinho-q126` +
  `git branch -D feat/q126-cpo-real-dag` quando confirmado que a calibração não é precisa.

## 2. `feat/decisao-plano-operadores` — ABANDONAR documentado

- **O que tem:** páginas "Plan v4" (Expedição/Decisões/Inbox) + `AssignmentTable.tsx` (troca de par
  operador).
- **Estado vs main:** **superada por main** — Expedição/Decisões/Inbox já existem e estão mais
  avançadas. Conflito garantido em `App.tsx`/`Sidebar.tsx`/`lib/api.ts`.
- **Decisão:** **abandonar documentado.** Único pedaço talvez útil no futuro: o padrão de
  `AssignmentTable.tsx` (trocar o par de operadores) para um sub-sprint futuro "Trocar par" no
  /overall — mas hoje a edição de operador já se faz pelo drag Por-Pessoa + `OperationEditSheet`
  (Q.147/Q.148), por isso **não é prioritário**.
- **Limpeza sugerida (Luis confirma):** `git branch -D feat/decisao-plano-operadores`.

## 3. 13 worktrees `worktree-agent-*` (todas `locked`) — LIMPEZA sugerida

- **O que são:** worktrees legacy de agentes paralelos (Q.52-54), **sem trabalho de planeamento**
  relevante. Ver `[[agent_worktree_unreliable]]` (worktrees de agentes dão bases stale — não
  isolam de forma fiável).
- **Decisão:** candidatas a limpeza; **não apagar sem o Luis** (estão `locked`; podem conter WIP
  não inspeccionado).
- **Limpeza sugerida (Luis confirma), por worktree:**
  `git worktree remove --force .claude/worktrees/agent-<id>` (precisa de `--force` por estarem
  locked) + `git branch -D worktree-agent-<id>`. IDs:
  `a1311771e1b3398b9, a1bc10396ed3bff00, a289e05778403a42c, a450a8061d69a58d3, a594058de4606622b,`
  `a5e13fde3491f9eda, a7f7317475438819b, a92bafa1e2cdadab2, a94c28a58550304e7, ab4d52d95e52fe1de,`
  `adf8672b67937c701, ae1a55dfc44276541, ae5cb60b815e008d4`.

## 4. Branches já merged em main (candidatas a apagar) — LIMPEZA sugerida

`feat/q131-cpo-real-data`, `feat/q136-planeamento-barcos`, `feat/q137-auto-replan`,
`feat/q142-robo-prod` (e outras Q.1xx já consolidadas em main, ver
`[[project_q131_cpo_real_data]]`/`[[project_q137_robo_automatico]]`). **Confirmar `git branch
--merged main` antes de apagar.** Não fazer aqui.

---

## O que esta ronda Q.153 entregou (C0→D3, 6 commits sobre os 7 base A1-C1)

| Sub-sprint | Entrega | Verificação |
|---|---|---|
| **C0** | toggle "Só barcos" (expor `is_boat`, predicado Q.136, plano+actuals) | live: ON=867 barcos / OFF=1912; 38 testes |
| **C2** | tirar barco por drag (RemoveZone) + painel de excluídos + repor | live: exclude/reinclude 200; painel limpa via invalidate |
| **C3** | sequência por modelo: botão no /overall + CTA replan + expor `product_id` | live: abre ModeloSheet na tab Fases; 18 fases c/ row id |
| **D1** | preview de consequência no drag (MoveBoatConfirm) + `reason` no reorder | live: drag→modal→confirmar→commit `manual_drag` DRAFT c/ reason |
| **D2** | apply-move reaplicável (delta `manual_drag`+`to_ts`) — edições /producao sobrevivem ao replan | live: apply-move→delta `tipo=manual_drag`; teste de sobrevivência |
| **D3** | apagar código morto (PlaneamentoPage/DragDropPlanner) + teste do header migrado | tsc verde; 171 testes (−8 +3) |

**Diferidos (precisam tuning live, baixo valor agora):** A4 (janela deslizante/orçamento GA —
`generations≥100` obrigatório), A5 (`avg_utilization` sobre span real — quebra pin tests, cosmético).

**Dívida B1 (não-bug):** o `approve-by-sha` duplica a lógica SoD+audit de `schedule.py` em vez de
extrair helper partilhado. Limpeza opcional para uma ronda futura.

## E — Push

A branch **ainda não tem push**. Não fazer `git push` sem o Luis pedir (a 1ª vez sincroniza
`feat/q153-planeamento-operacional` com origin). Antes do push: `& .\scripts\verify.ps1` (gate fica
vermelho por dívida pré-existente — `test_synonyms_match_consumo` + ruff/BLE001 pré-Q.153, **não**
desta ronda).
