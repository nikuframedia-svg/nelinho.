# src/governance

**Propósito: decision ledger + Q.17 YAML policy + audit log pipeline. Toda a mudança de estado autoritativa passa por aqui.**

## Invariantes locais (always-true neste módulo)

- Q.17 rules: `requires_human_approval=True` (Pydantic `Literal[True]` — LLM não pode opt-out).
- `kill_switch` é `Literal["admin_only"]` — SQL-only, nunca via API/LLM.
- SoD enforced via `check_sod()` em `src/shared/auth/rbac.py` — proposer ≠ approver.
- ACTION_WIRING matrix em `yaml_policy/dispatchers.py` é mirrored no frontend `RegrasPage.tsx` `WIRED:` map (test: `test_action_wiring_matrix_has_entry_per_action_type`).
- Toda a transição de estado escreve `*_revision` ou `audit_log` na MESMA transacção (audit trail intact).
- DSL é closed whitelist: 12 events × 9 actions × 8 ops × 7 axioms.

## Quando entrar aqui, lê primeiro

- `service.py` — 1669L god-file (proposer/approver/executor/rollbacker — Q.66.D.3 vai decompor).
- `audit_service.py:49` `audit_change()` — entry point único (Q.66.B.1 com `trace_id` column).
- `action_executor.py` — onde os outputs tocam `plan.cpo.commits` (8 ignores em import-linter contract 3).
- `yaml_policy/dispatchers.py` — ACTION_WIRING matrix + `_stubbed_or_ok()` helper.

## Comandos

```powershell
.\.venv\Scripts\python.exe -m pytest tests/governance/ -q   # canary 348+
```

## Anti-padrões deste módulo

- NÃO criar `DecisionApproval` no `propose()` — só no `approve()` (bug Q.61.09).
- NÃO editar `governance/service.py` E `plan/cpo/` no mesmo commit (cycle risk, Fase 4 vai inverter via event bus).
- NÃO escrever audit fora da transacção do state change (lost-update entre app crash e audit insert).
- NÃO devolver `status="ok"` quando `wired=False` — usa `_stubbed_or_ok()` (Q.17.F.1).
- NÃO flipar `wired=False→True` num lado sem flipar no outro (frontend/backend mirror).

## Referências

- `agent_docs/q17_logic_as_data.md` — DSL whitelist + 10 layers segurança.
- `agent_docs/spelke_axioms.md` — axiom 7 (audit trail).
