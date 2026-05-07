# Domain glossary — fábrica NELO

Reference para termos de domínio, números reais, fases, retrabalho, CoeficienteX. Sempre usar
estes valores em prompts/copy — NUNCA renderizar como mock data.

## A fábrica em números

- 122 operadores activos
- 41 fases de produção
- 510 moldes
- 61 padrões de routing
- 14.7 barcos/dia (média histórica)
- €30K-35K/dia target throughput
- 529.450 operações registadas (2024-2025)
- 89.836 erros (16.97% rate global)

## Fases mais críticas

| Fase | Tempo (moda) | Par % | Notas |
|---|---|---:|---|
| **Laminagem** | 4h | 88.5% | Fibra carbono/kevlar. Fase mais crítica. Par-by-default. |
| **Laminagem Infusão** | 24h | 58% (1 worker) | Processo diferente — TRATAR SEPARADAMENTE |
| **Cura** | 15h gap | — | Química — não é fila, é tempo real |
| **Desmolde** | curto | — | Ponto QC: 96.4% dos erros são detectados aqui |
| **Lixagem água** | — | — | 49.2% retrabalho (quase metade repete) |
| **Pintura Acabamento** | — | — | 42.4% retrabalho. 40 aptos na skill matrix mas só 22 trabalharam em 2024 |
| **Lixagem polimento** | — | — | 41.3% retrabalho |
| **Colagem (vários)** | — | — | Várias variantes (peças, barcos, golas) com gaps próprios |

## Cura/secagem (16 transições)

```
Laminagem            → Cura:                   15.0h
Pintura Acabam.      → Lixagem seco:           12.5h
Colagem Peças        → Pintura Acabam.:        19.5h
Colagem Peças        → Acabamento 2:           23.5h
Acabamento Enverniz. → Lixagem água:           18.0h
Colagem Barcos       → Pintura Acabam.:        19.0h
Colagem Golas        → Acabamento 3:           24.5h
Laminagem Infusão    → Cura:                   24.0h
... (16 transições; full list em src/plan/cpo/state.py NELO_CURING_GAPS_SEED)
```

**Estes não são filas — é química.** Operação seguinte não pode começar antes do gap mínimo
mesmo que operador esteja livre. Spelke axiom #6.

## Tempos — NUNCA usar standard

Os coeficientes standard (`FasesStandardModelos`) divergem **até 25× do real**. O CPO usa
sempre **tempos históricos reais** (`FaseOf_Inicio → FaseOf_Fim`), limpos com pipeline:

1. Remover zeros
2. Remover acima de P95
3. Moda dos limpos
4. Fallback: mediana ≠ 0

Se vires `FasesStandardModelos` a alimentar fitness ou decoder, é bug.

## CoeficienteX — DINHEIRO, NÃO TEMPO

**CoeficienteX é prémio/bónus € por operação.** Confirmado pelo CEO. O valor 6.1 na Laminagem
são €6.10 de prémio, não 6.1 horas.

### NUNCA usar CoeficienteX em:
- `src/plan/cpo/decoder.py` (cálculos de duração)
- `src/plan/cpo/fitness.py` (fitness function tempos)
- `src/plan/cpo/pair_assignment.py` (lógica de pares — usar mediana team_size histórico ≥ 2)
- `src/plan/cpo/state.py` (FactoryState)
- `src/plan/cpo/workforce.py` (assignment)

### USAR CoeficienteX em:
- `src/profit/services/bonus_payout_service.py` (payroll)
- `src/profit/services/cogs_calculator.py` (COGS)
- `src/hr/payroll/` (cálculo de prémios por op)

### Verificação antes de submit

Se editares qualquer ficheiro em `src/plan/cpo/`:

```bash
grep -ni "coeficiente" src/plan/cpo/*.py
# Esperado: zero matches OU só comentários históricos documentando o bug fixado
```

Histórico: bugs CX1-CX5 (CoeficienteX como tempo) foram fixados no FASE 1B.

## Retrabalho rates

Por fase (real, não inventado):

```
Lixagem água:        49.2%
Pintura Acabam.:     42.4%
Lixagem polimento:   41.3%
... outras < 30%
```

Implicação para fitness: capacity factor 1.5× quando `state.historical_error_rates[phase] >= 0.40`.
Status: ainda não implementado (Sprint E.1 do plano macro).

## Truck capacity (transporte)

- **Capacity (CEO baseline):** 50 barcos/camião
- **Moda real (histórico):** 26 barcos/camião

A regra `transport.complete_truck` Q.14.C tem variantes: `moda26` (default) vs `capacity50`.
Sugestões "completar camião" usam moda, não capacity.

## Glossário PT-PT (vocab nelinho)

| ✅ PT-PT (usar) | ❌ PT-BR / outras (não usar) |
|---|---|
| barco | embarcação, unidade |
| operador | colaborador, recurso |
| molde | tooling, ferramenta |
| retrabalho | rework |
| fase | estação, work center |
| utilizador | usuário |
| tu | você |
| camião | caminhão |
| registo | registro |
| gerir | gerenciar |
| equipamento | (universal) |
| ecrã | tela |

Concrete numbers > vague terms:
- "€2.400" não "valor significativo"
- "4 horas" não "algum tempo"
- "Sexta às 14h" não "nos próximos dias"

## Hipóteses NÃO confirmadas (cuidado)

| Hipótese | Status |
|---|---|
| H1: CoeficienteX = tempo 2º worker | ❌ ERRADO — é prémio € |
| H2: Threshold manutenção = 800 usos | ⚠️ INVENTADO — sem dados |
| H3: Gravidade 1=warning, 2=defeito | ⚠️ NÃO CONFIRMADO |
| H4: Laminagem 1 worker = erro registo | ⚠️ NÃO CONFIRMADO |
| H5: Data transporte = por dia | ⚠️ NÃO CONFIRMADO |

Se o teu código depende de uma hipótese não confirmada, marca como `# H2: ...` e abre uma
question para o Luís.

## Where these numbers come from

- `Folha_IA_extra.xlsx` (50MB ingestion source) — operações reais 2024-2025
- `factory.curated_*` tables (após ingest) — derived stats
- `src/plan/cpo/state.py` `NELO_CURING_GAPS_SEED` — cura/secagem hardcoded (não muda — é química)

Se um número aqui parece errado, verifica contra a Excel real OU pergunta ao Luís. Não inventar.
