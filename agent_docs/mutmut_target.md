# Mutmut target — política de mutation score

## Context

Q.61.05 introduziu `scripts/mutation_test.ps1` que corre `mutmut` contra
módulos críticos (`src/shared/api/decisions.py`, etc). Q.61.41 fez o
primeiro run real e revelou **182 mutantes sobreviventes** em
`decisions.py` (smoke target, single module).

## Decisão (Q.62.E.9 + Q.66.C.3)

**Targets activos:**

| Módulo | Survivors goal | Notas |
|---|---|---|
| `src/shared/api/decisions.py` | <100 (baseline 182) | Q.62.E.9 |
| `src/plan/cpo/decoder.py` + `src/plan/cpo/fitness.py` | <100 inicial | Q.66.C.3 — Spelke axioms críticos (cura/secagem, mold exclusivo, capacity, precedence, safety_net baseline) |

Reduzir grind iterativo — touched-file pays.

**Não bloquear PRs** com mutation score. Razões:

- Mutmut é lento (~6 min para `decisions.py`, ~30 min só para
  `fitness.py`, >2h para `cpo/` inteiro).
- Sobreviventes muitas vezes são equivalent mutations (`x + 0 == x`).
- Coverage de cenários e propriedade Spelke é mais critical (já gated).
- Para `cpo/`, o scope é apenas `decoder.py` + `fitness.py` (Spelke
  core). Engine/scheduler/workforce ficam para targets dedicados se
  quisermos cobertura adicional — não vale correr 2h por release.

**Quando correr:**

- **Nightly**: kick-off automático (GitHub Actions cron) em PRs ao main.
- **Local**: developer corre quando muda código em `decisions.py`,
  `cpo/` ou `yaml_policy/`.

```powershell
pwsh scripts/mutation_test.ps1 -Module smoke     # decisions.py (~6 min)
pwsh scripts/mutation_test.ps1 -Module decisions # mais profundo
pwsh scripts/mutation_test.ps1 -Module cpo       # decoder.py + fitness.py (~30 min)
pwsh scripts/mutation_test.ps1 -Module all       # cpo + yaml_policy + decisions
```

**Cache:** mutmut grava `.mutmut-cache` no repo root (single sqlite). Ao
mudar de target apaga primeiro (`Remove-Item .mutmut-cache`) — sem isso
o resultado mistura mutações de targets diferentes.

## Baseline actual

Update este file quando o baseline melhorar (target: <100):

| Data | Módulo | Survivors | Killed | Total | Score est. |
|---|---|---|---|---|---|
| 2026-05-20 (Q.61.41) | decisions.py | 182 | ? | ? | ~45% |
| 2026-05-20 (Q.66.C.3) | cpo/fitness.py | **203** | 72 | 275 | **26%** |
| 2026-05-20 (Q.66.C.3) | cpo/decoder.py | pending first run | — | — | — |
| target Q.63 | decisions.py | <100 | — | — | >50% |
| target Q.67 | cpo/decoder.py + cpo/fitness.py | <100 | — | — | >50% |
| target Q.70 | decisions.py + cpo/ | <150 | — | — | >60% |

**Q.66.C.3 lição:** fitness.py ficou em 26% — confirma a hipótese de
Anthropic post-mortem. Coverage de cenário é alto (84 tests passam),
mas os tests não distinguem weights (`w_makespan=1.0` vs `0.0`),
flips boolean (`use_v2_weights=True` vs `False`), nem normalização
(`mean`→`sum`). Para reduzir, próxima vaga deve adicionar pelo menos
3-5 tests focados em mutmut survivors específicos (`mutmut show <id>`
→ pin test).

## Como reduzir survivors

Cada survivor sinaliza um teste que não distingue uma mutação semântica.
Estratégia (touched-file pays):

1. Run `mutmut show <id>` para ver o diff da mutação.
2. Se equivalent (e.g., dead code, ordem irrelevante): `# pragma: no cover`
   ou refactor para eliminar branch.
3. Se real: adicionar teste que falha com a mutação aplicada.

## Não-objectivos

- Não chasing 100% — equivalent mutations existem sempre.
- Não substituir property tests / Hypothesis (Spelke axioms já cobertos).
