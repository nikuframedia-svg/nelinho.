# Q.17 Logic-as-data — DSL, ACTION_WIRING, safety

Reference for the YAML-policy rule engine (Q.17.A→F). Read when working on
`src/governance/yaml_policy/`, `RegrasPage.tsx`, or extending DSL.

## Core idea

Toda a lógica configurável do sistema vive em YAML. Não só thresholds — regras de negócio
inteiras. A página `/regras` permite a admin escrever em PT-PT natural ("quando molde K1 7ML 03
atingir 850 usos, propor manutenção e bloquear novas alocações") e o **LLM escreve a regra em
YAML** com mecanismos de segurança (validação schema, dry-run, 7 axioms, Trust Gate, RBAC,
audit, rollback).

## Closed whitelists (NÃO extender sem sub-sprint dedicado)

**Tudo isto é Pydantic `Literal[...]` ou enum — LLM nunca emite fora destas listas por
construção.**

### 12 EventType

```
schedule_propose         schedule_committed       kpi_threshold_crossed
mold_usage_threshold     worker_absent            quality_event_logged
transport_loaded         phase_drift_detected     decision_pending
rule_rejected            wip_threshold            time_trigger
```

### 9 ActionType

```
alert            block            modify_fitness       reassign_worker
propose_maintenance              notify           set_config
create_decision                  pause_writes
```

### 8 ConditionOp

```
eq    ne    gt    lt    gte    lte    in    matches
```

### 7 AxiomRequirement

```
capacity_non_negative         precedence_monotonic       mold_exclusive
dual_resource_laminagem       skill_match                curing_gaps
safety_net_baseline
```

## Hard Pydantic invariants (LLM cannot opt out)

```python
class RuleSafety(BaseModel):
    requires_human_approval: Literal[True] = True   # ALWAYS true; LLM cannot set False
    kill_switch: Literal["admin_only"] = "admin_only"  # Admin SQL only; not via API
    max_fires_per_day: int = Field(ge=1, le=100)
    expires: Optional[date] = None
```

`Literal[True]` é enforced em runtime pelo Pydantic. Tentar passar `False` → ValidationError.

## ACTION_WIRING matrix

Single source of truth: which actions actually do something vs report stubbed.

**Backend** (`src/governance/yaml_policy/dispatchers.py`):

```python
ACTION_WIRING = {
    "alert":               True,    # ✅ emit_alert callback
    "block":               True,    # ✅ raises BlockingViolation in engine.on_event
    "modify_fitness":      True,    # ✅ TenantConfig set_config
    "set_config":          True,    # ✅ TenantConfigService
    "reassign_worker":     False,   # ⚠️ stubbed (Q.17.F.8 deferred)
    "propose_maintenance": False,   # ⚠️ stubbed (Q.17.F.7 deferred)
    "notify":              False,   # ⚠️ stubbed (no email/sms backend yet)
    "create_decision":     False,   # ⚠️ stubbed (Q.17.F.7)
    "pause_writes":        False,   # ⚠️ stubbed (Q.18.D scope)
}
```

**Frontend mirror** (`frontend/src/pages/admin/RegrasPage.tsx`):

```typescript
const WIRED: Record<string, boolean> = {
  alert: true, block: true, modify_fitness: true, set_config: true,
  reassign_worker: false, propose_maintenance: false, notify: false,
  create_decision: false, pause_writes: false,
};
```

**Test that enforces sync:**
`tests/governance/test_yaml_dispatchers_q17f.py::test_action_wiring_matrix_has_entry_per_action_type`

### Why this matrix is critical

The Q.17.F.1 risk #5 was: dispatcher reporting `status="ok"` when `wired=False` → operadores
acreditavam que regras estavam a aplicar quando não estavam. Trust-breaking. Use `_stubbed_or_ok()`
helper, NEVER string literal:

```python
# ❌ ERRADO
return DispatchResult(status="ok", ...)

# ✅ CORRECTO
return _stubbed_or_ok(action_type=ActionType.NOTIFY, callback_invoked=ctx.notify is not None)
```

`_stubbed_or_ok` returns `"ok"` when `ACTION_WIRING[action_type] is True AND callback_invoked is True`,
else `"stubbed"`.

## Engine semantics

```python
class RuleEngine:
    async def on_event(self, event_type: EventType, payload: dict, *, tenant_id: UUID):
        # 1. Indexed lookup
        rules = self._registry.get(event_type, [])
        # 2. Per-rule pipeline
        for rule in rules:
            if not rule.evaluate(payload):
                continue
            # 3. Rate limit (max_fires_per_day) + dedupe (60s window, sha256 fingerprint)
            if not await self._can_fire(rule, payload):
                continue
            # 4. Dispatch
            results = await self._dispatch_actions(rule, payload, ctx)
            # 5. Audit (Q.14.A rule_firing) + chain (Q.13.D) opcional
            await record_rule_firing(rule.id, payload, results)
            # 6. Block check (raises if any action.type=='block')
            if engine.block_results(results):
                raise BlockingViolation(...)
```

Blocking actions raise `HTTPException(409)` no caller (e.g. `/v1/plan/cpo/schedule`).

## 10 safety layers

| # | Layer | Where |
|---|---|---|
| 1 | Schema (Pydantic + JSON Schema) | `rule_schema.py` |
| 2 | Whitelist enums (LLM tools) | `llm_tools.py` |
| 3 | Spelke axiom pre-check | `safety_checks.AxiomChecker` |
| 4 | Sandbox dry-run | `safety_checks.run_safety_checks` (last-week data) |
| 5 | Trust Gate (TI ≥ 0.75) | `dqa/quality_gates.py` |
| 6 | RBAC write-gate | `shared/auth/rbac.py` (per action_type) |
| 7 | Approval workflow | `service.RuleProposalService` (proposed→approved→active) |
| 8 | Versioning + Rollback | `governance.tenant_rule_revision` table |
| 9 | Conflict resolver | `safety_checks.ConflictResolver` |
| 10 | Rate limit per rule | `engine._can_fire` (max_fires_per_day) |

## When extending DSL

If a real-world rule doesn't fit, the right path is **NOT** to add a free-form action. It's:

1. Open sub-sprint Q.17.B.X for the new EventType/ActionType
2. Update Pydantic enum + ACTION_WIRING matrix + frontend WIRED map + test_action_wiring_matrix
3. Add dispatcher + DispatchContext callback wiring
4. Add tests (unit dispatcher + integration engine.on_event)
5. Update LLM tools spec (`llm_tools.py`)
6. Document in this file

The DSL stays closed by design. Open DSL = security boundary lost.

## Endpoints

`/v1/governance/yaml-policy/` (mounted in `src/governance/api.py`):

| Method | Path | Purpose |
|---|---|---|
| POST | `/rules/propose` | NL → Ollama → validated rule (status=proposed) |
| GET  | `/rules?status_filter=` | List with pagination |
| GET  | `/rules/{rule_id}` | Detail + revisions |
| POST | `/rules/{rule_id}/approve` | proposed→approved (admin RBAC) |
| POST | `/rules/{rule_id}/reject` | proposed→rejected |
| POST | `/rules/{rule_id}/suspend` | active→suspended |
| POST | `/rules/{rule_id}/rollback` | * → previous revision |

Approval triggers `engine.install_rule()` immediately (rule starts firing on next matching event).

## Common rationalizations to push back on

| "Adiciono uma flag bypass para o requires_human_approval" | NUNCA. Literal[True] é por design. Se precisas auto-aplicar, abre sub-sprint para discutir. |
| "Adiciono um free-form action_type=custom_python" | Boundary lost. Closed whitelist é o ponto. |
| "Faço o LLM escolher um EventType fora dos enums via prompt eng" | LLM tools schema impede por construção (Pydantic + JSON schema). E se passasse, o validate Pydantic rejeitava. |
| "Skip da AxiomChecker para rules de dev" | A AxiomChecker é cheap (<10ms). Não há benefit. Fail-closed. |
| "ACTION_WIRING é só docs" | É contract testado em CI. Frontend mirrors backend. Mudar um sem o outro = test fail. |
