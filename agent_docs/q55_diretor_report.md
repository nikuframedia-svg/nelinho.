# Relatório do Diretor Industrial — 80 perguntas ao copiloto

**Q.55 · 2026-05-19 · modelo `gemma4:e4b` (o mesmo que está na fábrica)**

---

## O que fizemos, em duas linhas

Pusemos 80 perguntas ao copiloto — as mesmas que um chefe de turno faz: *"e se eu
puser 2 turnos?"*, *"onde está o gargalo?"*, *"o que faço para baixar o makespan?"*.
Cada resposta foi pesada por **três juízes independentes** que não se conhecem
entre si. Se os três concordam, a resposta vale. Se um discorda, vai à mesa.

Os três juízes:

| Juiz | O que é | O que verifica |
|------|---------|----------------|
| **SCM da casa** | o modelo causal da fábrica (`causal_query`, 23 variáveis) | a verdade-base: o que *deveria* acontecer |
| **verify_chain** | o portão de coerência que já corre em produção | a resposta do copiloto bate com a verdade-base? |
| **DoWhy** | biblioteca de inferência causal, juiz externo | a relação aguenta-se nos *dados*, ou é coincidência? |

O DoWhy faz a parte mais dura: gera 4.000 "dias de fábrica" sintéticos, estima o
efeito de cada alavanca **a partir dos dados** (não da nossa fórmula), e corre
**três refutadores** — troca a causa por ruído, injecta um falso confounder,
re-estima num subconjunto. Se a relação sobrevive aos três, é causal a sério.

---

## Veredicto

**74 em 80 verdes (92,5%).** E as 6 que ficaram a vermelho **não são erros de
raciocínio do copiloto** — explico cada uma abaixo. No que conta — o raciocínio
causal — o copiloto não cometeu um único erro substantivo em 48 perguntas.

```
intervention    18/19      "e se eu mexer nesta alavanca?"
abduction       13/13      "vi este valor — o que esperar a jusante?"
counterfactual  11/11      "e se tivéssemos feito X?"
multistep        5/5       várias alavancas ao mesmo tempo
forecast         8/8       "como evolui nos próximos turnos?"
state           15/16      ponto de situação da fábrica
recommendation   4/8       "o que devo fazer?"
─────────────────────────
TOTAL           74/80
```

**Pipeline causal (48 perguntas) — o coração do teste:**

- `verify_chain` aprovou **47/48**. Coerência média **0,979** (o portão exige 0,85).
- DoWhy cobriu **33** dessas perguntas e **concordou na direção em 32/33**.
- Os **3 refutadores passaram em 33/33** — nenhuma relação caiu ao ser atacada.

Traduzido: o copiloto raciocina bem sobre a fábrica, e o modelo causal por trás
dele não está a inventar — quando metemos um juiz externo a estimar tudo de novo
a partir de dados, **dá a mesma coisa**.

---

## As 6 "reprovações" — uma a uma, sem maquilhagem

Nenhuma é o copiloto a raciocinar mal. São três coisas diferentes:

### 1 vermelho — o copiloto acertou e o avaliador é que falhou

| Pergunta | O que se passou |
|----------|-----------------|
| **`st_wip`** — "Quantas ordens em aberto temos?" | O copiloto foi buscar a ferramenta `open_orders`. O teste esperava `wip`. **As duas estão certas** — "ordens em aberto" é literalmente `open_orders`. Régua do avaliador demasiado apertada. |

### 1 vermelho — o copiloto acertou, mas o pipeline tem um ponto cego

| Pergunta | O que se passou |
|----------|-----------------|
| **`int_double_shift_makespan`** — "Com 2 turnos, como muda o makespan?" | O copiloto respondeu **certo**: *"o makespan não muda, mantém-se em 280h, delta 0,0"*. No nosso modelo, o nº de turnos não toca no makespan (que é medido em horas-de-trabalho, não calendário). Mas o `verify_chain` deu **0,0** — não sabe avaliar uma resposta "nada muda". E o DoWhy, sobre uma relação que não existe, devolveu um ruído de −0,24h (0,08% de 280h) e isso chegou para "discordar da direção". **Os dois juízes tropeçam no efeito-nulo. O copiloto não.** |

### 4 vermelhos — o teste correu com a fábrica "às escuras"

As 4 perguntas de recomendação (`rec_menos_retrabalho`, `rec_melhor_otd`,
`rec_gargalo_laminagem`, `rec_cura_lenta`) falharam porque a camada de dados
operacionais **não estava ligada à base de dados** neste teste (o arnês corre
offline; o motor causal não precisa de base, mas as perguntas de "estado da
fábrica" precisam).

O que o copiloto respondeu? *"Não consigo recomendar uma ação porque as
sub-queries de diagnóstico falharam ao carregar os dados."* — **Isto é o
comportamento certo.** Um copiloto que inventasse números seria muito pior.
(Ainda por cima, o `rec_menos_retrabalho` até deu uma resposta causal boa —
"baixar o retrabalho a zero rende +388 €/dia" — só não bateu certo com a lista
de palavras-chave do avaliador.)

**Resumo honesto:** corrigidas 2 imprecisões do avaliador → **76/80**. Os 4
restantes resolvem-se a ligar o copiloto ao backend real — e aí medimos a fala
operacional a sério.

---

## O mais interessante: o que o DoWhy nos ensinou

O DoWhy não está aqui para dar uma medalha ao nosso modelo. Está para o pôr à
prova. E encontrou coisas que valem dinheiro:

### 1. As alavancas de entrada são causais a sério ✅

Das 19 alavancas-raiz da fábrica (turnos, routing, nº de operadores, moldes,
material, temperatura, idade dos moldes), o DoWhy confirmou **as 19**, todas com
os 3 refutadores a passar. Exemplos do que ele estimou *sozinho, a partir dos
dados*:

| Alavanca → efeito | Efeito estimado pelo DoWhy |
|-------------------|----------------------------|
| 2.º turno → faturação/dia | **+25.340 €** por turno extra |
| Material a 100% → faturação/dia | **+21.140 €** |
| Routing variante B → makespan | **−11,8 h** |
| +1 laminador → fila da Laminagem | **−0,36 h** |
| Moldes disponíveis → nº de setups | **−10 setups** por cada salto de disponibilidade |

Quando o copiloto diz "a variante B corta 12h ao makespan", o DoWhy, por um
caminho completamente diferente, diz "−11,8h". **Batem.**

### 2. O DoWhy linear é cego a efeitos em "V" ⚠️

Quatro pares ficaram fora da margem de grandeza. Dois deles são o mesmo e são
importantes: **temperatura → risco de qualidade**.

No nosso modelo, a relação é em **V**: frio a mais *e* calor a mais estragam a
qualidade — o ponto bom é no meio (19°C). O DoWhy, que assume relação em linha
reta, vê o frio a puxar para um lado e o calor para o outro, faz a média e
conclui "**efeito ~zero**". Está errado — mas errado de uma forma instrutiva.

> **Lição para a fábrica:** para a qualidade vs temperatura, **não troquem o
> modelo da casa por uma regressão estatística simples** — ela não vê o V.
> O modelo hand-coded capta-o; um estimador linear deita-o fora.

### 3. Há uma fronteira clara do que os dados conseguem provar 🧭

O DoWhy estimou limpo as 19 alavancas-raiz, mas teve de **saltar 10 pares**
(`laminagem_duration`, `curing_time`, `rework_rate`, `makespan`...). Porquê?
Essas variáveis são *resultados* de outras — não se mexem sozinhas. Em dados de
observação não há como isolar "e se eu forçasse a duração da laminagem a X" sem
mexer no que a causa.

> **Lição:** o modelo causal da casa **não é substituível** por "deitar dados a
> uma biblioteca". Os dados provam as alavancas de entrada; o resto — a cadeia
> interna da fábrica — precisa do modelo estrutural que construímos.

---

## O que eu decidiria, como diretor

| # | Decisão | Porquê |
|---|---------|--------|
| 1 | **Ligar o copiloto ao backend real e repetir as 8 perguntas operacionais.** | 4 dos 6 vermelhos são fome de dados, não erro. Só com a fábrica "acesa" se mede a fala operacional. |
| 2 | **Pôr um ramo "efeito nulo" no `verify_chain`.** | Hoje, se a resposta certa é "nada muda", o portão dá 0. Tem de saber aceitar um zero honesto. |
| 3 | **Manter o modelo da casa para qualidade × temperatura.** | O efeito é em V. Qualquer regressão linear — DoWhy incluído — vai falhá-lo. |
| 4 | **Renomear `makespan_hours`.** | Mede horas-de-trabalho, não calendário. Um operador vai assumir calendário e baralhar-se — como quase aconteceu na pergunta dos 2 turnos. |

**Sobre o modelo `gemma4:e4b`:** em 48 perguntas de raciocínio causal, **zero
erros substantivos**, coerência média 0,979. Para o copiloto causal, está bom
para produção. A fraqueza não está no modelo — está nas pontas do arnês de teste.

---

## Como reproduzir

```bash
$env:PYTHONPATH = "c:/Users/User/nelinho"
.\.venv\Scripts\python.exe scripts/test_llm_diretor_q55.py
```

- `scripts/dowhy_nelo_q55.py` — dataset sintético do NELO_DAG + tabela DoWhy
  (efeito + 3 refutadores por par causa→efeito).
- `scripts/test_llm_diretor_q55.py` — 80 prompts → copiloto → avaliação tripla.
- `scripts/last_diretor_q55_run.json` — resultado completo, máquina-legível.
- `scripts/q55_run_console.txt` — log da consola desta corrida.

*Corrida: 80 prompts, ~18 min de copiloto + ~1 min de DoWhy. 4.000 dias de
fábrica sintéticos, 29 pares causais estimados (19 confirmados, 10 saltados por
serem nós-resultado).*
