# Audit Baseline — Sprint Q.7 Fase 1

**Gerado em:** 2026-05-02 13:36 UTC

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
| Ficheiros src | 324 |
| Linhas src | 78,867 |
| Testes colectados | 1,105 |
| Rotas API | 180 |
| Imports a falhar | 0 |
| TODO/FIXME | 5 |

## Por módulo

| Módulo | Health | src | lines | tests | collected | routes | TODOs | imp.err | hardcoded |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `core` | 🟢 green | 30 | 5,992 | 5 | 50 | 27 | 0 | **0** | 0 |
| `plan` | 🟢 green | 53 | 13,577 | 33 | 327 | 27 | 0 | **0** | 0 |
| `profit` | 🟢 green | 24 | 4,382 | 2 | 17 | 21 | 1 | **0** | 0 |
| `hr` | 🟢 green | 16 | 2,120 | 2 | 4 | 10 | 0 | **0** | 0 |
| `copilot` | 🟢 green | 55 | 15,064 | 20 | 237 | 6 | 1 | **0** | 0 |
| `ml` | 🟢 green | 25 | 2,771 | 9 | 61 | 4 | 0 | **0** | 0 |
| `explain` | 🟢 green | 5 | 2,433 | 2 | 5 | 13 | 0 | **0** | 0 |
| `factory_data_product` | 🟢 green | 34 | 11,119 | 10 | 66 | 0 | 0 | **0** | 0 |
| `governance` | 🟢 green | 15 | 6,084 | 16 | 160 | 27 | 0 | **0** | 0 |
| `shared` | 🟢 green | 28 | 6,157 | 8 | 50 | 0 | 1 | **0** | 0 |
| `twin` | 🟢 green | 4 | 1,490 | 3 | 18 | 9 | 0 | **0** | 0 |
| `sandbox` | 🟢 green | 4 | 700 | 2 | 8 | 7 | 0 | **0** | 0 |
| `supply` | 🟢 green | 9 | 2,025 | 3 | 21 | 12 | 0 | **0** | 0 |
| `workforce` | 🟢 green | 6 | 1,934 | 3 | 10 | 10 | 0 | **0** | 0 |
| `dqa` | 🟢 green | 10 | 1,705 | 6 | 63 | 1 | 0 | **0** | 0 |
| `improve` | 🟢 green | 4 | 739 | 2 | 8 | 6 | 0 | **0** | 0 |
| `legacy` | 🟡 yellow | 2 | 575 | 0 | 0 | 0 | 2 | **0** | 0 |

## Sem testes ou sem testes colectados (yellow)

Estes módulos não têm cobertura visível — Fase 3 candidata.

- `legacy` — 2 ficheiros src, 0 test files, 0 testes colectados

---

*Re-gerar:* `python scripts/audit.py`
