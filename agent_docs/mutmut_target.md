# Mutmut target — política de mutation score

## Context

Q.61.05 introduziu `scripts/mutation_test.ps1` que corre `mutmut` contra
módulos críticos (`src/shared/api/decisions.py`, etc). Q.61.41 fez o
primeiro run real e revelou **182 mutantes sobreviventes** em
`decisions.py` (smoke target, single module).

## Decisão (Q.62.E.9)

**Target: <100 sobreviventes em `decisions.py`** (proxy de mutation
score >50%). Reduzir grind iterativo — touched-file pays.

**Não bloquear PRs** com mutation score. Razões:

- Mutmut é lento (~6 min para `decisions.py`, ~30 min para `cpo/`).
- Sobreviventes muitas vezes são equivalent mutations (`x + 0 == x`).
- Coverage de cenários e propriedade Spelke é mais critical (já gated).

**Quando correr:**

- **Nightly**: kick-off automático (GitHub Actions cron) em PRs ao main.
- **Local**: developer corre quando muda código em `decisions.py`,
  `cpo/` ou `yaml_policy/`.

```powershell
pwsh scripts/mutation_test.ps1 -Module smoke     # decisions.py (~6 min)
pwsh scripts/mutation_test.ps1 -Module decisions # mais profundo
pwsh scripts/mutation_test.ps1 -Module all       # cpo + yaml_policy + decisions
```

## Baseline actual

Update este file quando o baseline melhorar (target: <100):

| Data | Módulo | Survivors | Killed | Score est. |
|---|---|---|---|---|
| 2026-05-20 (Q.61.41) | decisions.py | 182 | ? | ~45% |
| target Q.63 | decisions.py | <100 | — | >50% |
| target Q.65 | decisions.py + cpo/ | <150 | — | >60% |

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
