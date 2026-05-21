# CPO greedy vs GA — relatório de benchmark (Q.67.3.A)

## Pergunta

O `CPOv4Engine` em `src/plan/cpo/engine.py` corre uma cascata em 5 fases:
greedy explícito (`GreedyPipeline`, 8 fases NELO) → GA (200 gerações, população
100) → MAP-Elites injection → CP-SAT L-RHO → workforce assignment.

A questão Q.55.J ficou em aberto: **se o GA melhorar a baseline greedy em menos
de 5%, vale a pena manter os ~600 LOC extra (`chromosome.py`, `ga` loop em
`engine.py`, `fitness.py` sweep, `frrmab.py`, `mapelites.py` e os ramos de
restart/surrogate associados)?**

Este relatório mede o ganho em 10 cenários e dá a recomendação. A decisão final
fica para o Luis — só ele pesa o trade-off entre "código a menos" e
"determinismo do greedy puro" contra "explorabilidade que o GA dá em casos que
ainda não vimos".

## Metodologia

Script: [`scripts/cpo_benchmark.py`](../scripts/cpo_benchmark.py).

Para cada cenário corre o `CPOv4Engine` duas vezes:

1. **`greedy_only`** — `CPOConfig(population_size=1, generations=0,
   time_limit_sec=0)`. O loop GA nunca itera; o `best_final` é literalmente a
   baseline emitida em `engine.py:204-237` depois do `GreedyPipeline.run()`.
   Mantém ON: `use_greedy_pipeline`, `use_backwards_scheduling`,
   `use_hungarian_pair_assignment`, `use_queue_time`,
   `use_post_desmolde_buffer`, `use_v2_mapelites_axes`, `use_cpsat_lrho`,
   `use_routing_variants` — só o GA é desligado.
2. **`ga_full`** — `CPOConfig()` (defaults). É exactamente o caminho que
   produção corre via `/v1/cpo/schedule`.

Métricas extraídas (todas vivem no dict-result do engine, ver
`decoder.py:709-731`):

| Métrica | Direcção | Fonte |
|---|---|---|
| `makespan_hours` | menor = melhor | `decoder.py:713` |
| `otd_delivery` | maior = melhor (1.0 = sem atrasos) | `decoder.py:716` |
| `throughput_eur_day` | maior = melhor (alvo CEO €30-35K/dia) | `decoder.py:727` |
| `num_late_orders` | menor = melhor | `decoder.py:715` |
| `solve_time_sec` | menor = melhor (latência) | injectado em `engine.py:398` |

Cenários: 10 amostras (`--n-scenarios 10`, default). Em ambiente prod-like, com
o curated layer carregado, cada cenário é um chunk distinto das `open_orders`
do active ingestion. Em dev (curated layer vazio) o script cai para 10
cenários sintéticos com 20-50 ops cada, horizon de 14 dias — úteis só para
sanity-check do script.

## Resultados

> **Aviso:** os números abaixo são do modo `--dry-run` (cenários sintéticos
> sem dados NELO reais). **NÃO são representativos da NELO.** O benchmark
> prod-like fica para correr quando o Luis tiver o backend up + curated layer
> ingerido. Para esse run:
>
> ```powershell
> .\.venv\Scripts\python.exe scripts/cpo_benchmark.py --from-erp `
>   --out agent_docs/cpo_greedy_vs_ga_report_real.md
> ```
>
> Esse comando re-escreve a tabela com cenários reais; tudo o resto deste
> relatório (metodologia, anti-padrões, recomendação) mantém-se.

### Esqueleto da tabela (dry-run, 3 cenários sintéticos)

| Cenário | Métrica | Greedy puro | GA default | delta (GA vs greedy) |
|---|---|---|---|---|
| s00 | makespan_hours | 96.72 | 96.72 | +0.0% |
| s00 | otd_delivery | 1.000 | 1.000 | +0.0% |
| s00 | throughput_eur_day | 0.00 | 0.00 | n/a |
| s00 | num_late_orders | 0 | 0 | +0.0% |
| s00 | solve_time_sec | 0.00 | 30.56 | n/a |
| s01 | makespan_hours | 91.60 | 91.60 | +0.0% |
| s01 | otd_delivery | 1.000 | 1.000 | +0.0% |
| s01 | throughput_eur_day | 0.00 | 0.00 | n/a |
| s01 | num_late_orders | 0 | 0 | +0.0% |
| s01 | solve_time_sec | 0.00 | 30.37 | n/a |
| s02 | makespan_hours | 144.46 | 144.46 | +0.0% |
| s02 | otd_delivery | 0.714 | 0.714 | +0.0% |
| s02 | throughput_eur_day | 0.00 | 0.00 | n/a |
| s02 | num_late_orders | 2 | 2 | +0.0% |
| s02 | solve_time_sec | 0.00 | 30.14 | n/a |

### Resumo (média sobre os 3 cenários do dry-run)

| Métrica | Greedy puro (avg) | GA default (avg) | delta médio |
|---|---|---|---|
| makespan_hours | 110.93 | 110.93 | +0.0% |
| otd_delivery | 0.905 | 0.905 | +0.0% |
| throughput_eur_day | 0.00 | 0.00 | n/a |
| num_late_orders | 0 | 0 | +0.0% |
| solve_time_sec | 0.00 | 30.36 | n/a |

### Observações do dry-run

- O **`throughput_eur_day` aparece a zero** porque o caminho sintético não
  injecta `product_price_eur` (Q.43 wiring). Em prod-like esta métrica
  passa a ter sinal — é a métrica que melhor diferencia greedy de GA, porque
  o GA pode reordenar ops para fechar uma encomenda valiosa antes do horizon.
- **`makespan` e `otd` são IGUAIS** entre greedy e GA no dry-run sintético.
  É consistente com o que o engine já loga em `cpo_meta.improvement_pct` —
  em cenários pequenos (≤ 30 ops) a baseline greedy já está perto do óptimo
  local e o GA tem pouco para melhorar. **Em cenários reais NELO (122
  operadores, 510 moldes, 61 padrões de routing) esperamos ver
  dispersão maior**; é por isso que o benchmark tem de correr em prod-like.
- **`solve_time_sec`: greedy ≈ 0s, GA ≈ 30s** (igual ao `ga_budget_s=30`).
  Esta é a latência operacional que se perde se mantivermos o GA — e o
  ganho que se ganha se simplificarmos para greedy puro: re-planeamentos
  passam de 30s para sub-segundo, o que afecta UX no copiloto e abre porta
  a "what-if" interactivo (ver `agent_docs/architecture.md`).

## Recomendação (a confirmar com dados reais)

Critério Q.55.J: **GA mantém-se se o ganho médio sobre greedy for >5% em
pelo menos uma das métricas chave** (`makespan_hours`, `otd_delivery`,
`throughput_eur_day`). Caso contrário, simplificar para greedy puro
poupa ~600 LOC (ver "Touch map para simplificação" em baixo).

### Cenários

- **Se o run prod-like mostrar ganho médio ≥5% em pelo menos uma métrica
  chave** → **MANTER o GA**. A perda de 30s de latência é aceitável face ao
  ganho operacional (e o copiloto pode mostrar progresso intermédio via
  `improvement_pct` no `cpo_meta`).

- **Se o ganho médio for <5% em TODAS as métricas chave** → **simplificar
  para greedy puro**, com touch map:

  | Ficheiro | Acção | Linhas estimadas |
  |---|---|---|
  | `src/plan/cpo/chromosome.py` | apagar (greedy não precisa de permutação) | ~80 |
  | `src/plan/cpo/frrmab.py` | apagar (operador adaptativo só serve o GA) | ~120 |
  | `src/plan/cpo/mapelites.py` | apagar (sem GA, sem archive) | ~160 |
  | `src/plan/cpo/surrogate.py` | apagar (skip filter só faz sentido em GA) | ~110 |
  | `src/plan/cpo/engine.py` | remover loop GA `for gen in range(...)` (linhas 248-391) + restart helpers + bloco `_extract_mapelites_representatives` | ~150 |
  | `src/plan/cpo/fitness.py` | manter — usada pela baseline também; só remover dataclass fields exclusivos do GA (`use_frrmab` etc.) | ~30 |
  | `tests/plan/test_cpo_engine_adaptive.py` | apagar (Sprint F adaptive layers desaparecem) | ~250 (file inteiro) |

  Total ~900 LOC. Reduz superfície + 30s de latência por schedule. Mantém
  os 7 axiomas Spelke (estão todos no `decoder.py` / `safety_net.py`,
  intactos no caminho greedy).

- **Híbrido:** se o ganho variar muito entre cenários (e.g. ≥5% em 3 dos
  10 cenários, +0.5% nos outros 7) → **manter o GA mas baixar
  `generations` de 200 para algo como 40-60 e `ga_budget_s` para 8-12s.**
  Q.59.invariant proíbe baixar generations sem property tests novos, mas
  com este benchmark em mão pode-se justificar a mexer no default
  (escrevendo property tests novos em `tests/plan/test_preview_delta_property.py`
  que afirmem o invariant relaxado).

### O que o Luis precisa decidir

1. **Correr o benchmark prod-like.** Sem isso esta recomendação é
   especulativa.
2. **Definir o threshold ≥5% ou outro.** Q.55.J usa 5% como heurística;
   ele pode preferir 3% (mais conservador, mantém GA) ou 10% (mais
   agressivo, simplifica mais cedo).
3. **Se simplificar — escrever o property test novo** que confirma "greedy
   puro respeita os 7 axiomas Spelke" antes de apagar o GA. O test já
   existe (`tests/plan/test_preview_delta_property.py`); só precisa de
   parametrizar para correr com `generations=0` também.

## Limitações

- O benchmark mede o GA da CASCATA completa, com `use_cpsat_lrho=True`.
  Se simplificarmos para greedy puro queremos comparar com o CP-SAT
  desligado também — Q.55.J pode pedir um segundo benchmark
  `greedy_only_no_cpsat`. Adicionar uma config terceira no script é
  trivial (linha extra em `_run_one_scenario`).
- Cenários sintéticos não exercitam o `RoutingResolver`. Em prod-like o
  GA pode ganhar muito mais por escolher entre os 61 padrões de routing
  via `chromosome.routing_choices` (axioma `use_routing_variants=True`).
- `solve_time_sec` é fortemente dependente do hardware. O run prod-like
  deve ser feito na máquina NELO (ou equivalente), não no dev box.

## Referências

- `src/plan/cpo/engine.py` — caminho greedy+GA.
- `src/plan/cpo/decoder.py:709-731` — fonte das métricas.
- `agent_docs/spelke_axioms.md` — invariantes que QUALQUER simplificação tem
  de continuar a respeitar.
- `.claude/skills/nelinho-invariants/SKILL.md` — gate automatizado que falha
  CI se o caminho greedy regredir vs baseline (`safety_net.py`).
