# Audit Baseline — Sprint Q.7 Fase 1

**Gerado em:** 2026-04-25 20:48 UTC

Snapshot do estado dos 17 módulos do PP1. Foco em **bugs reais** — 
imports partidos, testes em falta, hardcoded params §52b. Não reporta 
warnings de estilo. Re-correr com `python scripts/audit.py`.

## Resumo

| Métrica | Valor |
|---|---|
| Módulos | 17 |
| Verdes | 13 |
| Amarelos | 4 |
| Vermelhos | 0 |
| Ficheiros src | 318 |
| Linhas src | 76,393 |
| Testes colectados | 975 |
| Rotas API | 180 |
| Imports a falhar | 0 |
| TODO/FIXME | 14 |

## Por módulo

| Módulo | Health | src | lines | tests | collected | routes | TODOs | imp.err | hardcoded |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `core` | 🟢 green | 30 | 5,890 | 5 | 50 | 27 | 0 | **0** | 0 |
| `plan` | 🟢 green | 53 | 13,188 | 31 | 311 | 27 | 0 | **0** | 0 |
| `profit` | 🟢 green | 24 | 4,348 | 2 | 17 | 21 | 1 | **0** | 0 |
| `hr` | 🟢 green | 16 | 2,120 | 2 | 4 | 10 | 0 | **0** | 0 |
| `copilot` | 🟢 green | 54 | 14,641 | 17 | 222 | 6 | 3 | **0** | 0 |
| `ml` | 🟢 green | 25 | 2,754 | 9 | 61 | 4 | 0 | **0** | 0 |
| `explain` | 🟢 green | 5 | 2,371 | 2 | 5 | 13 | 2 | **0** | 0 |
| `factory_data_product` | 🟢 green | 34 | 10,682 | 5 | 41 | 0 | 0 | **0** | 0 |
| `governance` | 🟢 green | 15 | 5,897 | 15 | 150 | 27 | 0 | **0** | 0 |
| `shared` | 🟢 green | 27 | 5,888 | 5 | 34 | 0 | 5 | **0** | 0 |
| `twin` | 🟡 yellow | 4 | 1,493 | 0 | 0 | 9 | 0 | **0** | 0 |
| `sandbox` | 🟡 yellow | 2 | 675 | 0 | 0 | 7 | 0 | **0** | 0 |
| `supply` | 🟢 green | 9 | 2,025 | 3 | 21 | 12 | 0 | **0** | 0 |
| `workforce` | 🟢 green | 6 | 1,783 | 2 | 5 | 10 | 0 | **0** | 0 |
| `dqa` | 🟢 green | 10 | 1,629 | 5 | 54 | 1 | 1 | **0** | 0 |
| `improve` | 🟡 yellow | 2 | 434 | 0 | 0 | 6 | 0 | **0** | 0 |
| `legacy` | 🟡 yellow | 2 | 575 | 0 | 0 | 0 | 2 | **0** | 0 |

## Sem testes ou sem testes colectados (yellow)

Estes módulos não têm cobertura visível — Fase 3 candidata.

- `twin` — 4 ficheiros src, 0 test files, 0 testes colectados
- `sandbox` — 2 ficheiros src, 0 test files, 0 testes colectados
- `improve` — 2 ficheiros src, 0 test files, 0 testes colectados
- `legacy` — 2 ficheiros src, 0 test files, 0 testes colectados

---

*Re-gerar:* `python scripts/audit.py`
