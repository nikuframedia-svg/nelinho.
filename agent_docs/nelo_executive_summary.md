# ProdPlan ONE × NELO — sumário executivo

> Baseado em leitura directa do MAR-KAYAKS em `fabrica.nelo.eu:1039`
> a 2026-05-12. Todos os números abaixo são contagens reais sobre as
> tabelas de produção, não estimativas.

---

## 1. Volume e produto dominante

A base de dados MAR-KAYAKS é a primária do ERP (recovery FULL, criada em
2019-06-18). Hoje contém:

| Domínio | Linhas |
|---|---:|
| Ordens de fabrico (`ORDEMFABRICO`) | **441 392** |
| Execução por fase (`OF_FP`) | **2 627 279** |
| Routings declarados (`PRODUTO_FASE`) | **42 811** |
| BOM (`PRODUTO_COMPONENTE`) | **117 900** |
| Movimentos de stock (`MOVIMENTO`) | **12 392 449** |
| Catálogo de produtos (`PRODUTO`) | **14 016** |
| Fases de produção (`FASES_PRODUCAO`) | **71** |
| Moldes em sistema (`MOLDES`) | **91** |

**Top 5 produtos por nº de OFs (todo o histórico)**: `Standard III C (Base
X alu.)` 20 331 · `Tabua FP's K1 7` 15 680 · `Peso reciclado 250g Areia`
12 872 · `Foam FP K1` 12 700 · `Leme K1 7` 12 164.

Os 5 são componentes/acessórios da família K1 — confirmando que K1
(kayak single) é a classe dominante.

**Sub-amostra do demo package** (50 OFs fechadas dos últimos 6 meses,
filtradas para kayaks com routing + BOM completos) tem 23 K1, 6 K2, 5
C1, 3 V1, 1 K4, 1 Viper, mais 10 acessórios — 46 % K1.

---

## 2. Planeamento estruturado: abandonado em Outubro 2019

A tabela `PLANEAMENTO_DIARIO` contém **64 linhas no total**. A última
foi gravada em **2019-10-14**. As 10 linhas mais recentes cobrem
2019-08-25 a 2019-10-14 (turnos de 8h-20h, 2-6 funcionários, Transporte
ligado).

Desde Outubro de 2019 — **mais de 6 anos** — não foi escrita uma única
linha de planeamento estruturado nesta tabela. O planeamento vive desde
então fora da DB (Excel + decisões do gestor em tempo real).

Em contraste, a execução **continua a ser registada com normalidade**:
- `OF_FP`: 2.6 M linhas, ainda activamente populada.
- `MOVIMENTO`: 146 415 registos nos últimos 30 dias (~4 880/dia).
- Cada OF kayak média do demo gera 84.7 movimentos durante o ciclo.

> **Pain point identificado**: a fábrica regista o que aconteceu, mas
> não declara o que vai acontecer. O plano só existe fora da DB.

---

## 3. Operação activa: movimentos diários

Snapshot 2026-04-12 → 2026-05-12 (30 dias):

| Métrica | Valor |
|---|---:|
| Movimentos de stock | 146 415 |
| Média diária | ~4 880 |
| OFs com `OF_DATAFIM IS NULL` | 315 533 |
| OFs do demo (fechadas, últimos 30 dias, kayaks) | 50 |
| Média routing steps / OF kayak | 15.3 |
| Média BOM lines / OF kayak | 32.4 |
| Média movimentos / OF kayak | 84.7 |

**Caveat técnico sobre OFs abertas**: o campo `OF_DATAFIM` está NULL em
71 % das OFs históricas. Em parte é backlog real; em grande parte é
campo não preenchido sistematicamente. A definição operacional de
"ordem aberta" precisa de ser combinada com `OF_FP.OFFP_DATAFIM` da
fase final, não apenas `ORDEMFABRICO.OF_DATAFIM`.

---

## 4. Onde o PP1 entra concretamente

A NELO já tem três camadas a funcionar bem em DB:

1. **Encomendas** (`ENCOMENDA` 410 abertas + ordens directas).
2. **Catálogo + BOM + Routing** (14 016 produtos, 117 900 componentes,
   42 811 routing rows, com tempos K1/K2/K4 declarados por fase).
3. **Execução** (`OF_FP` 2.6 M linhas, MOVIMENTO 12.4 M linhas, com
   temperatura/humidade registadas nos passos de cura).

O que falta — e onde o PP1 ocupa o vazio — é a **camada de planeamento
entre encomenda e execução**:

- Gerar o `PLANEAMENTO_DIARIO` digitalmente em vez de manualmente. A
  tabela existe, está vazia desde 2019 — pode voltar a ser usada (ou
  espelhada no PP1).
- Correr o scheduler (GA + CPO) sobre o routing real (`PRODUTO_FASE`
  com referências K1/K2/K4 já declaradas) e a disponibilidade real de
  moldes/operadores.
- Audit trail das decisões: quem aprovou, quando, com base em quê.
- Decisões reversíveis sem perder histórico.

O PP1 **não substitui** ORDEMFABRICO, OF_FP, MOVIMENTO ou PRODUTO. Lê
estas tabelas via adapter SQL Server read-only (já implementado em
`src/adapters/nelo/services.py`). Escreve apenas no seu próprio
Postgres.

---

## 5. Próximo passo concreto

Antes do scheduler entrar a sério com dados reais da fábrica, a NELO
precisa de fazer três coisas pequenas:

1. **Aplicar `agent_docs/views_pp1.sql` no SQL Server** — 5 views
   read-only (`vw_pp1_orders`, `vw_pp1_routings`, `vw_pp1_bom`,
   `vw_pp1_schedule`, `vw_pp1_movements`) com colunas em inglês +
   `WITH (NOLOCK)`. Sintaxe revista. Idempotente
   (`CREATE OR ALTER VIEW`).

2. **Criar o login `pp1_reader`** com `GRANT SELECT` apenas nas 5
   views — o utilizador `nikufra` usado nesta exploração tem acesso
   às tabelas-base, o que é desnecessariamente largo para o adapter
   PP1. Comandos sugeridos no fim de `views_pp1.sql`.

3. **Validar o demo package** — `agent_docs/demo_orders.json` (50 OFs,
   3.2 MB) e `agent_docs/demo_orders.csv` (50 linhas, 10 KB). Apontar
   se o mapeamento routing/BOM/movimentos por OF corresponde ao que
   é executado na fábrica. Se houver desvios (e.g. routing extra que
   não está em `PRODUTO_FASE`), corrigir antes do scheduler começar
   a correr — não depois.

Depois destes três passos, o PP1 corre o scheduler com dados reais
da próxima semana e o gestor compara o plano gerado com a sua
intuição. **Sem migração, sem mudar nada no MAR-KAYAKS, sem risco
operacional.**

---

*Documento gerado por Claude com leitura directa da base de dados.
Fonte: `scripts/discover_mar_kayaks.py`, `scripts/build_demo_package.py`,
`scripts/health_check_nelo.py`. Reproduzível.*
