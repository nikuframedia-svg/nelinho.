# Q.68.1.E — Mutmut REAL baseline (decoder + fitness + decisions)

**Data:** 2026-05-21
**Branch:** `feat/q60-qualidade-agentes`
**Sub-sprint:** Q.68.1.E (executivo, sem código de produto novo)

## Contexto (porquê este documento existe)

Auditoria H7 detectou que mutmut em `decoder.py` + `fitness.py` **nunca correu como
baseline real** — Q.67.3.B criou 94 mutation pin tests *antecipatoriamente* (baseados
em catálogo de operadores mutmut típicos, não em survivors reais). Q.61.41 só correu
smoke target em `decisions.py` (182 survivors). Este sub-sprint **mede de facto** e
documenta os números reais para alimentar Q.68.2.B (pin tests focados em top
survivors).

## Como correr

```powershell
# Decoder + fitness (Q.66.C.3 target — Spelke-critical)
pwsh scripts/mutation_test.ps1 -Module cpo

# Decisions (Q.61.41 target — SoD + propose/approve)
pwsh scripts/mutation_test.ps1 -Module decisions

# Smoke (sub-set de decisions, ~6 min)
pwsh scripts/mutation_test.ps1 -Module smoke
```

Notas operacionais:

- `mutmut` grava `.mutmut-cache` (sqlite single-file) no repo root. O script apaga-o
  entre targets para não misturar survivors. Se quiseres preservar resultados de um
  target específico para inspecção (`mutmut show <id>`), **não corras outro target a
  seguir** — copia a cache para `.mutmut-cache.cpo` primeiro.
- Tempos observados (laptop Luis, Windows + PowerShell 5.1):
  - `decisions.py` (smoke) — **356s** (~6 min) — 275 mutants em decisions.py
    propostos pelo mutmut.
  - `fitness.py` (Q.66.C.3 first half) — **720s** (~12 min) — 275 mutants.
  - `decoder.py` (Q.66.C.3 second half) — **estimado 30-40 min** se corrido em
    isolado; cumulativo com fitness.py o script `cpo` total ~45min.
- `pytest.ini` tem `asyncio_mode=auto`; mutmut runner usa
  `python -m pytest -x --tb=no -q <tests>` e cada mutant re-corre a suite alvo
  (~6-8 tests por target).

## Resultados reais

Fontes:
- `scripts/mutmut_baseline.json` (capturado 2026-05-20, dois runs concluídos)
- `scripts/mutmut_cpo_fitness_results.txt` (dump do `mutmut results` para fitness.py)
- `scripts/mutmut_cpo_fitness_run.log` (run completo: 275 mutants 72 killed)
- `.mutmut-cache` ainda vivo no momento desta análise → permitiu `mutmut show <id>`

| Módulo | LOC (actual) | Total mutants | Survivors | Killed | Mutation score | Tempo |
|---|---|---|---|---|---|---|
| `src/plan/cpo/decoder.py` | 195L (façade Q.66.D) + decoder_helpers 347L + decoder_kpis 203L + decoder_resources 546L = **1291L total no cluster** | — | **NÃO MEDIDO** | — | — | pending |
| `src/plan/cpo/fitness.py` | 380L | 275 | **203** | 72 | **26.18%** | 720s |
| `src/shared/api/decisions.py` | 562L | ≥182 (sample) | **182** | indeterminado (mutmut só reportou survivors) | ~45% est. | 356s |

> **decoder.py NÃO foi medido.** O baseline JSON marca-o como
> `status: pending_first_run` com nota "deferred para não exceder budget". O comando
> canónico `pwsh scripts/mutation_test.ps1 -Module cpo` corre fitness.py **e**
> decoder.py em sequência (limpa a cache entre os dois) — só fitness.py terminou
> no run de 2026-05-20. Para fechar este gap correr `-Module cpo` numa janela
> nocturna (estimado 30-40 min adicionais).

> **decisions.py killed count não foi capturado** porque o run de Q.61.41 só
> guardou o output bruto do `mutmut results` (que lista apenas survivors). Score
> estimado em ~45% no `mutmut_target.md` mas não verificado contra o total
> de mutants gerados.

## Top survivors fitness.py — 5 categorias dominantes

Amostragem de 15 mutants representativos via `mutmut show <id>` (cache 2026-05-20).
As categorias agrupam-se com clareza:

### 1. Magic-number tweak em weights / thresholds (≈ 80 survivors)

`w_tardiness=10.0` → `11.0`, `w_setups=0.5` → `1.5`, `w_quality_risk=0.10` → `1.1`,
`safety_penalty=1e6` → `2e6`, `w_causal_entropy=0.05` → `1.05`,
`truck_consolidation_tolerance_h=12.0` → `13.0`, `_NORM_MAKESPAN_H=1000.0` → `1001.0`.

Exemplos: mutants 5, 7, 9, 11, 34, 42, 167.

**Por que sobrevivem:** os tests de fitness assertam *cor relativa* (penaliza vs não
penaliza) mas raramente o valor numérico exacto. Q.67.3.B pin tests
(`tests/plan/test_fitness_mutation_pin_q67.py`) pinam alguns weights mas não o
conjunto completo de constantes `_NORM_*`.

### 2. Comparador flip `>` → `>=`, `==` → `!=`, `or` → `and` (≈ 50 survivors)

Exemplos: mutant 73 (`if rework_h > 0:` → `>= 0`), mutant 145
(`w_quality_risk > 0` → `>= 0`), mutant 53 (`truck_consolidation_weight > 0` → `>= 0`),
mutant 155 (`r >= threshold` → `r > threshold`), mutant 110
(`rate is None or float(rate) < threshold` → `... and ...`).

**Por que sobrevivem:** os tests não exercitam o exact-boundary case (ex.: penalty
quando weight é exactamente 0, ou quando hard-hit cai exactamente em threshold).

### 3. Defaults `or 1` / `or 0` removidos ou trocados (≈ 35 survivors)

Exemplos: mutant 200 (`schedule.get("setups", 0)` → `schedule.get("setups", 1)`),
mutant 130 (`makespan_hours` default `0` → `1`), mutant 265 (`queue_depth, 0) or 0` →
`queue_depth, 0) and 0`).

**Por que sobrevivem:** tests passam sempre schedules totalmente preenchidos —
nunca testam o branch "campo ausente / falsy → default".

### 4. Branch dispatch `use_v2_weights` / None substitution (≈ 25 survivors)

Exemplos: mutant 1 (typedef trocado para `None`), mutant 15
(`quality_risk_hard_threshold: float = 0.4` → `None`), mutant 19
(`use_v2_weights: bool = False` → `None`), mutant 25 (`w_v2_idle_operators` → `None`),
mutant 51 (`fitness = _v2_fitness(...)` → `fitness = None`), mutant 232
(toda a expressão `cfg.w_v2_makespan * norm_makespan + …` → `None`).

**Por que sobrevivem:** se o teste só atinge o ramo legacy (default) e nunca o ramo
v2, mutações no caminho v2 não são apanhadas. Q.67.3.B inclui pin tests que
forçam ambos os ramos, mas não em todas as branches (truck consolidation, causal
entropy, hard-hit penalty).

### 5. String / identifier renaming (≈ 13 survivors)

Exemplos: mutant 134 (`"total_tardiness_hours"` → `"XXtotal_tardiness_hoursXX"`),
mutant 239 (`"modelo_id"` → `"XXmodelo_idXX"`), mutant 252, 257, 274 (warning
strings mutadas).

**Por que sobrevivem:** schedules-fixture usam keys diferentes ou o código tem
fallback via `or`. Estes são parcialmente equivalent mutations (logging strings
não afectam fitness), mas o key "total_tardiness_hours" → "XX…XX" indica um
caminho não testado a sério.

**Resíduo (~equivalent ou cosméticos)** — mutações em strings de docstring/log,
parametro `repr=False` → `repr=True` (mutant 44), ordens de assignment irrelevantes.

## Decoder.py — comparação com Q.67.3.B pins

Q.67.3.B criou 44 pin tests para `decoder.py` (helpers pré-decomposição em Q.66.D).
Pós-Q.66.D, decoder.py é só 195L (façade) e a lógica vive em
`decoder_helpers.py` (347L) + `decoder_kpis.py` (203L) + `decoder_resources.py`
(546L). Os pin tests existentes targetam funções helper como `_pocket_count`,
`classify_rework_phase`, `_is_desmolde`, `_last_on_machine_has_different_family`,
`_estimate_utilization`, `_empty_result`, `compute_mold_batches`.

- **Antes Q.67.3.B:** survivors não medido (pending_first_run).
- **Após Q.67.3.B:** survivors não medido (pending_first_run).
- **Effectiveness dos pins:** **DESCONHECIDA** até correr `-Module cpo` no fluxo
  decomposto. Hipótese (Q.67.3.B doc): pin tests cobrem operadores mutmut típicos
  no façade — survivors devem cair significativamente vs estimativa pré-pin.

Acção: incluir decoder.py no próximo nocturnal CI run.

## Recomendação Q.68.2.B

Prioridade descendente para pin tests focados:

1. **`decisions.py` — 182 survivors sem pin existente.** Maior ROI. Necessita primeiro
   um run para popular `.mutmut-cache` e listar os 182 IDs, depois `mutmut show <id>`
   em batches de 30 para classificar. Pin tests devem viver em
   `tests/shared/test_decisions_mutation_pin_q68.py` (paralelo de
   `test_fitness_mutation_pin_q67.py`).

2. **`decoder.py` — medir baseline ANTES de mais pins.** Q.67.3.B é
   anticipatório; até correr o módulo não sabemos quantos survivors restam nem
   onde estão. Comando: `pwsh scripts/mutation_test.ps1 -Module cpo`.

3. **`fitness.py` — top 20 survivors sobreviventes a Q.67.3.B.** Categorias
   1+2+3 acima cobrem ≈165 dos 203. Pin tests adicionais devem:
   - Assertar valores numéricos exactos (não só "penaliza vs não") para weights
     `w_tardiness`, `w_setups`, `w_quality_risk`, `safety_penalty`,
     `_NORM_*` (categoria 1).
   - Exercitar boundary cases (penalty quando weight == 0, hard-hit exactamente
     em threshold) (categoria 2).
   - Forçar schedules com keys em falta para apanhar `or default` (categoria 3).

4. **Truck consolidation + causal entropy + hard-hit penalty** — três
   sub-caminhos do `_legacy_fitness` que estão mal testados (categoria 4).

**Não-objectivos:**
- Não atingir 100% — equivalent mutations (warning strings, ordem irrelevante)
  são tolerados conforme `mutmut_target.md`.
- Não substituir property tests Spelke — estes operam a outro nível (invariantes
  de schedule, não de KPI numérico).

## Próximos passos operacionais

1. Reservar uma janela nocturna (≥1h) para correr `-Module cpo` (fitness +
   decoder) e `-Module decisions` em sequência.
2. Após o run, **preservar** a cache de cada target (`Copy-Item .mutmut-cache
   .mutmut-cache.decisions` antes de mudar de target).
3. Para cada cache preservada, gerar `mutmut show <id>` em batch para os top 30
   survivors → input para Q.68.2.B pin tests.
4. Actualizar `agent_docs/mutmut_target.md` com a nova linha de baseline (Data,
   Módulo, Survivors, Killed, Total, Score real).
