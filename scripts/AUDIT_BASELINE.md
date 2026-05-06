# Audit Baseline — Sprint Q.7 Fase 1

**Gerado em:** 2026-05-02 16:05 UTC

Snapshot do estado dos 17 módulos do PP1. Foco em **bugs reais** — 
imports partidos, testes em falta, hardcoded params §52b. Não reporta 
warnings de estilo. Re-correr com `python scripts/audit.py`.

## Resumo

| Métrica | Valor |
|---|---|
| Módulos | 17 |
| Verdes | 16 |
| Amarelos | 1 |
| Vermelhos | 0 |
| Ficheiros src | 328 |
| Linhas src | 82,452 |
| Testes colectados | 1,257 |
| Rotas API | 180 |
| Imports a falhar | 0 |
| TODO/FIXME | 9 |

## Por módulo

| Módulo | Health | src | lines | tests | collected | routes | TODOs | imp.err | hardcoded |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `core` | 🟢 green | 30 | 6,268 | 5 | 50 | 27 | 0 | **0** | 0 |
| `plan` | 🟢 green | 53 | 14,056 | 34 | 346 | 27 | 1 | **0** | 0 |
| `profit` | 🟢 green | 24 | 4,472 | 4 | 26 | 21 | 1 | **0** | 0 |
| `hr` | 🟢 green | 16 | 2,375 | 4 | 14 | 10 | 0 | **0** | 0 |
| `copilot` | 🟢 green | 57 | 15,962 | 20 | 237 | 6 | 1 | **0** | 0 |
| `ml` | 🟢 green | 26 | 3,345 | 10 | 67 | 4 | 0 | **0** | 0 |
| `explain` | 🟢 green | 5 | 2,437 | 2 | 5 | 13 | 0 | **0** | 0 |
| `factory_data_product` | 🟢 green | 34 | 10,774 | 11 | 74 | 0 | 3 | **0** | 0 |
| `governance` | 🟢 green | 15 | 6,593 | 16 | 162 | 27 | 0 | **0** | 0 |
| `shared` | 🟢 green | 29 | 6,657 | 17 | 135 | 0 | 1 | **0** | 0 |
| `twin` | 🟢 green | 4 | 1,485 | 3 | 18 | 9 | 0 | **0** | 0 |
| `sandbox` | 🟢 green | 4 | 811 | 2 | 8 | 7 | 0 | **0** | 0 |
| `supply` | 🟢 green | 9 | 2,100 | 5 | 30 | 12 | 0 | **0** | 0 |
| `workforce` | 🟢 green | 6 | 1,924 | 3 | 10 | 10 | 0 | **0** | 0 |
| `dqa` | 🟢 green | 10 | 1,867 | 6 | 67 | 1 | 0 | **0** | 0 |
| `improve` | 🟢 green | 4 | 751 | 2 | 8 | 6 | 0 | **0** | 0 |
| `legacy` | 🟡 yellow | 2 | 575 | 0 | 0 | 0 | 2 | **0** | 0 |

## Sem testes ou sem testes colectados (yellow)

Estes módulos não têm cobertura visível — Fase 3 candidata.

- `legacy` — 2 ficheiros src, 0 test files, 0 testes colectados

---

*Re-gerar:* `python scripts/audit.py`
