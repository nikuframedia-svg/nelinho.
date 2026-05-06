# Spelke axioms — 7 invariants

Named after Elizabeth Spelke's "core knowledge" axioms — *invariants the system must respect
for its outputs to make sense*. The CPO scheduler is constrained to never violate any of these.

These are immovable. Não são heuristics, não são preferences — são contratos.

## The 7 axioms

### 1. Capacity ≥ 0

Nenhum centro de trabalho pode ter carga negativa. Se a soma de operações alocadas a um workcenter
ultrapassa a capacidade, é uma violação.

- **Where:** `src/plan/cpo/decoder.py` (carga calculada por slot)
- **Property test:** `test_axiom_capacity_non_negative` em
  `tests/plan/test_preview_delta_property.py`
- **Enforcer:** decoder rejeita; safety_net compara baseline ≥ candidate

### 2. Precedence monotonic (BOM phase order)

A ordem de fases é determinada pelo BOM (`FasesStandardModelos`). Cura **sempre** depois de
Laminagem. Desmolde **sempre** depois de Cura. Nunca paralelo, nunca invertido.

- **Where:** `src/plan/cpo/state.py` `min_gap_hours()` + `decoder.py:769`
- **Property test:** `test_axiom_precedence_monotonic`
- **Failure mode (D2):** sem cura/secagem entre fases químicas — fixed via
  `NELO_CURING_GAPS_SEED` em `state.py:33` (16 transições)

### 3. Mold exclusivity (1 poço ≠ 2 barcos at the same slot)

Um molde com 1 poço (a maioria dos 510) só pode estar a produzir um barco em cada momento.
Moldes multi-pocket usam capacidade declarada (`pocket_count`).

- **Where:** decoder enforces via mold availability tracking; CP-SAT L-RHO uses `AddNoOverlap`
  per mold_id
- **Status:** 🟡 PARCIAL — heurística no decoder; CP-SAT NoOverlap parcialmente formulado.
  Escape: pocket_count > 1 ainda não é first-class.
- **Pending test:** `test_axiom_mold_exclusivity_holds_for_1000_schedules` (Q.15.E.3)

### 4. Dual-resource Laminagem (par 88.5%)

Laminagem standard requer 2 operadores (par). Histórico real: 88.5% das ops Laminagem foram
feitas em par. **Não é CoeficienteX** — é mediana team_size histórico ≥ 2.

Excepções: **Laminagem Infusão** é processo diferente (24h moda, 58% com 1 worker) — TRATAR
SEPARADAMENTE.

- **Where:** `src/plan/cpo/state.py:154` `PAIR_PREFERRED_PHASES`
- **Property test:** `test_axiom_dual_resource_laminagem`
- **Enforcer:** `pair_assignment.py` — hungarian matching

### 5. Skill match (não-aptos rejeitados)

Operador só pode ser atribuído a fase se está em `FuncionariosFasesAptos`. Não existe "aprende
no trabalho" no scheduler.

- **Where:** `src/plan/cpo/workforce.py:23` `INFEASIBLE_COST = 1e12` (skill mismatch torna
  alocação infeasible)
- **Property test:** `test_axiom_skill_match`
- **Enforcer:** workforce decoder filtra antes de chamar Hungarian

### 6. Cura/secagem min_gap_hours (16 transições)

Tempo entre fases químicas não é fila — é química real. Operação seguinte NÃO PODE começar
antes do gap mínimo, mesmo que o operador esteja livre.

```
Laminagem            → Cura:                  15.0h
Pintura Acabam.      → Lixagem seco:          12.5h
Colagem Peças        → Pintura Acabam.:       19.5h
Colagem Peças        → Acabamento 2:          23.5h
Acabamento Enverniz. → Lixagem água:          18.0h
Colagem Barcos       → Pintura Acabam.:       19.0h
Colagem Golas        → Acabamento 3:          24.5h
Laminagem Infusão    → Cura:                  24.0h
... (16 total)
```

- **Where:** `src/plan/cpo/state.py:33-50` `NELO_CURING_GAPS_SEED`
- **Property test:** `test_axiom_curing_gaps_holds`
- **Migration:** `alembic/versions/023_phase_gaps.py`

### 7. Safety net (CPO ≥ baseline)

CPO nunca devolve um schedule pior que o baseline (heurístico simples). É o último guarda.

- **Where:** `src/plan/cpo/safety_net.py`
- **Status:** 🟡 INCOMPLETO — só compara 4 KPIs (num_late_orders, total_tardiness_hours,
  otd_delivery, makespan 1.5× cap). Falta throughput €/dia, quality_risk_score, setup_time,
  idle_operators. Sprint A.4 fechou parcialmente (Q.18 plan).

## How to verify before merging CPO/decoder/fitness change

```bash
# 1. Property tests (4 props, ~30s)
.\.venv\Scripts\python.exe -m pytest tests/plan/test_preview_delta_property.py -v

# 2. Read safety_net.py and confirm KPIs covered
grep -n "kpi" src/plan/cpo/safety_net.py

# 3. Run example schedule and inspect 7 axioms in result
curl -X POST http://localhost:8000/v1/plan/cpo/schedule \
  -H "X-Tenant-Id: 00000000-0000-0000-0000-000000000001" \
  -d '{"horizon_days": 7}'
# Inspect: schedule.axiom_violations should be []
```

Se property tests verde + safety_net 7 KPIs + curl axiom_violations vazio = OK.

Se property test falha, **NÃO** modificar o property test. Modificar o decoder/fitness até passar.

## Common rationalizations to push back on

| "É edge case, vou skipar a property test" | Edge cases são onde os axioms partem. Property tests existem precisamente para os apanhar. |
| "O safety_net já chumba, não preciso de teste explícito" | safety_net é defesa em profundidade. Test direct é defesa primária. |
| "Vou usar `==` para comparar capacidade" | Capacidade pode ser float (CP-SAT uses scaled ints; Python uses Decimal). Use `>=` com tolerance. |
| "Adiciono o axiom no decoder mas não no CP-SAT L-RHO" | Os dois caminhos têm que respeitar o invariant. Add to both or refuse the schedule. |
