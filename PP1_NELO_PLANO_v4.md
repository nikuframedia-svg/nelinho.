# PP1 × NELO — O PLANO COMPLETO v4

## Sistema de IA Causal que Aprende com a Fábrica

NIKUFRA.AI — Abril 2026 — CONFIDENCIAL

14 partes • 34 bugs de código • 8 hipóteses (1 confirmada errada) • Sistema que aprende

---

# PARTE I — VISÃO E CONTEXTO

## 1. A Visão

O PP1 será o primeiro sistema industrial do mundo que mantém um modelo causal persistente da fábrica, simula intervenções e contrafactuais em tempo real, comunica as razões em linguagem natural, e **melhora com cada decisão que o gestor toma**.

O diferenciador final não é o scheduling nem o LLM. É o **conhecimento tácito acumulado** — 12 meses de decisões do gestor codificadas no sistema. Impossível de copiar.

**Princípio absoluto:** O software explica SEMPRE as consequências e o porquê. A pessoa diz sim ou não E pode dizer porquê. O software pensa como a pessoa.

## 2. Números-Chave da Nelo

| Métrica | Valor | Confiança | Notas dev |
|---|---|---|---|
| OFs/dia útil (2024) | 14.7 starts, 14.9 completions | ✅ CONFIRMADO | Throughput €/dia é sobre completions |
| Meta diária | €30.000-35.000/dia | ✅ CONFIRMADO CEO | Volume em euros |
| Preço médio/barco | ~€2.350 (€35K ÷ 14.9) | CALCULADO | Mix competição + recreio |
| Operações (6 anos) | 529.450 | ✅ DADOS | Muitas com duration=0 (registo batch) |
| Registos com erros | 89.836 | ✅ DADOS | ⚠️ CONFIRMAR: gravidade 1 vs 2 = warning vs defeito? |
| OFs com erros | 68,3% | ✅ DADOS | ⚠️ Pode ser QC normal, não 68% defeitos reais |
| Retrabalho Lixagem água | 49,2% | ✅ DADOS | Quase metade volta. Capacidade 1.5× |
| Retrabalho Pintura Acab. | 42,4% | ✅ DADOS | Idem |
| Retrabalho Lixagem polim. | 41,3% | ✅ DADOS | Idem |
| Workers que trabalharam 2024 | 122 | ✅ DADOS | Flag Activo=True diz 129 mas real são 122 |
| Fases activas | 41 | ✅ DADOS | |
| Padrões routing (por sequência) | 61 | ✅ DADOS | 39 por set, 61 por sequência ordenada |
| Moldes | 510 (397 em produção) | ✅ DADOS | Até 7 poços |
| Lead time — moda | 15 dias | ✅ DADOS | Barco "normal". Média 51 inflacionada |
| Lead time — mediana | 37 dias | ✅ DADOS | Barcos complexos demoram mais |
| WIP estimado | 220-540 barcos | ESTIMADO | ⚠️ CONFIRMAR real com CEO |
| Gap inter-fase — moda | 0h (23,6% imediatos) | ✅ DADOS | Ver constraints cura secção 3.8 |
| Tempos real vs standard | Divergem até 25× | ✅ DADOS | Standard INÚTIL. Ver secção 3.7 |
| Laminagem team size | 88,5% = 2 workers | ✅ DADOS | Baseado em dados históricos reais |
| Laminagem Infusão team | 58% = 1 worker, 40% = 2 | ✅ DADOS | Processo DIFERENTE |
| CoeficienteX | 6.1 na Laminagem | ✅ CONFIRMADO CEO | É DINHEIRO (prémio €), NÃO tempo. Ver secção 3.9 |
| Turnos | 95% turno único | ✅ DADOS | Capacidade = 8h/dia/worker |
| Pintura Acab. — aptos | 40 na skill matrix | ✅ DADOS | Mas só 22 trabalharam em 2024 |
| Colagem Golas — workers | 13 | ✅ DADOS | Mais restrito |
| Desmolde como QC | 96,4% erros detectados lá | ✅ DADOS | CQ Final detecta 3,6% |
| Threshold manutenção moldes | NÃO EXISTE NOS DADOS | ⚠️ INVENTADO | Zero colunas manutenção na tabela Moldes |
| Budget CPO | 60s cada 15 min | ⚠️ NÃO VALIDADO | Cada hora pode bastar |
| Pesos fitness | arbitrários | ⚠️ ARBITRÁRIOS | Sistema de aprendizagem ajusta |

## 3. Regras de Produção Extraídas dos Dados

### 3.1 Routing Real

61 padrões de routing por sequência (39 por set de fases sem considerar ordem). O CPO usa os 61 porque a ordem importa.

Exemplo K1 Vanquish L SCS (18 fases):
```
Não Laminado → Prep.Molde → Pintura gelcoat → LAMINAGEM (2 workers)
→ Cura → Desmolde → Corte → Colagem Peças → Acabamento 2
→ Lixagem polimento → CQ Montagem → Montagem → CQ Final
→ Armazém → Embalado → Entregue
```

### 3.2 Cadeia de Erros

| Fase Culpada | Detectada em | Erros | % |
|---|---|---|---|
| Laminagem | Desmolde | 25.111 | 48% |
| Pintura | Desmolde | 15.123 | 29% |
| Prep. Molde | Desmolde | 11.231 | 22% |

Desmolde é o ponto QC de facto (96,4%). CQ Final detecta 3,6%. Só 2 pontos de detecção.

### 3.3 Retrabalho

| Fase | Retornos | Taxa REAL | Implicação CPO |
|---|---|---|---|
| Lixagem água | 19.149 | **49,2%** | Capacidade 1.5× |
| Pintura Acabamento | 12.826 | **42,4%** | Capacidade 1.5× |
| Lixagem polimento | 16.221 | **41,3%** | Capacidade 1.5× |
| Lixagem seco | 5.572 | ~25% | Significativo |

NÃO é "buffer 15-20%" — é planear com capacidade 1.5× porque quase metade repete.

### 3.4 Skill Matrix

| Fase | Aptos (skill matrix) | Trabalharam 2024 | Nota |
|---|---|---|---|
| Laminagem | 85 | (confirmar) | 88.5% com 2 workers — PAR OBRIGATÓRIO |
| Laminagem Infusão | (confirmar) | (confirmar) | 58% com 1 worker — fase SEPARADA |
| Pintura Acabamento | **40** | **22** | Bottleneck é ALOCAÇÃO, não competência |
| Colagem Golas | 13 | (confirmar) | Mais restrito |

### 3.5 Moldes Multi-Cavidade

1 poço: 279 | 2: 53 | 3: 19 | 4: 36 | 5: 16 | 6: 64 | 7: 2

Agrupar ordens do mesmo modelo para maximizar utilização.

### 3.6 Transporte

| Métrica | Moda | Mediana | Média |
|---|---|---|---|
| Barcos/data transporte | **26** | 74 | 82 |

CEO disse 50/camião. Se moda=26, o normal é meio camião. ⚠️ CONFIRMAR: data transporte é por camião ou por dia?

### 3.7 Tempos de Referência para o CPO

**Método:** Remover zeros + remover >P95 → moda dos limpos → fallback mediana ≠0.

| Fase | Referência | Método | Confiança |
|---|---|---|---|
| Lixagem polimento | **0.5h** | Moda limpa 52% | ALTA |
| Lixagem seco | **1.0h** | Moda limpa 54% | ALTA |
| Corte | **1.0h** | Moda limpa 44% | ALTA |
| Montagem/Finalização | **0.5h** | Moda limpa 37% | ALTA |
| Prep. Molde | **0.5h** | Moda limpa 17% | ALTA |
| Colagem Golas | **1.0h** | Moda limpa 38% | ALTA |
| CQ Montagem | **0.5h** | Moda limpa 31% | ALTA |
| Lixagem água | **0.5h** | Moda limpa 21% | ALTA |
| Colagem Peças | **3.0h** | Moda limpa 14% | MÉDIA |
| Laminagem standard | **4.0h** | Moda limpa 14% | MÉDIA |
| Colagem Barcos | **2.0h** | Moda limpa 10% | MÉDIA |
| Cura | **0.5h** | Moda limpa 11% | MÉDIA |
| Pintura Acabamento | **6.5h** | Mediana ≠0 | MÉDIA |
| Pintura gelcoat | **1.0h** | Mediana ≠0 | MÉDIA |
| Laminagem Infusão | **24.0h** | Moda limpa 9% | MÉDIA |

Fallback modelos novos: Standard × 2.

### 3.8 Constraints de Cura/Secagem

Tempos de processo químico. O CPO modela como `min_gap_hours`. A fase seguinte NÃO PODE começar antes. Não são filas a minimizar.

| Transição | min_gap_hours | n | Processo |
|---|---|---|---|
| Laminagem → Cura | **15.0h** | 17.012 | Cura estufa |
| Pintura Acabam. → Lixagem seco | **12.5h** | 20.335 | Secagem tinta |
| Colagem Peças → Pintura Acabam. | **19.5h** | 6.912 | Cura cola |
| Acabamento Enverniz. → Lixagem água | **18.0h** | 3.016 | Secagem verniz |
| Colagem Peças → Acabamento 2 | **23.5h** | 2.290 | Cura cola |
| Colagem Peças → Acabamento 3 | **21.5h** | 385 | Cura cola |
| Colagem Peças → Acab. Preparação | **23.5h** | 676 | Cura cola |
| Colagem Barcos → Pintura Acabam. | **19.0h** | 777 | Cura cola |
| Colagem Golas → Acabamento 3 | **24.5h** | 175 | Cura cola |
| Colagem Golas → Acabamento 2 | **24.0h** | 183 | Cura cola |
| Lixagem seco → Acab. Enverniz. | **21.5h** | 474 | Secagem |
| Lixagem seco → Acab. Pintura | **21.5h** | 548 | Secagem |
| Lixagem água → Acabamento 2 | **15.0h** | 999 | Secagem |
| Laminagem Infusão → Cura | **24.0h** | 300 | Cura infusão |
| Pintura Acabam. → Colagem Peças | **12.5h** | 1.229 | Secagem |
| Pintura Acabam. → Colagem Golas | **15.5h** | 134 | Secagem |

Transições NÃO listadas têm moda ≤ 2h — filas minimizáveis pelo CPO.

### 3.9 DESCOBERTA: CoeficienteX É Dinheiro, Não Tempo

**Confirmado pelo CEO:** "Esse campo refere-se ao valor do prémio em cada fase."

CoeficienteX = bónus/prémio (€) por operário por fase. O 6.1 na Laminagem são €6.10, não 6.1 horas.

**Errado no código (3 sítios):**
```
❌ pair_assignment.py:6 — "CoeficienteX > 0 encodes the second worker's time"
❌ state.py:59 — "phase codes that require a 2-person crew (CoeficienteX > 0)"
❌ default_configs.py:113 — "WF11 — Laminagem SEMPRE 2 workers (CoeficienteX > 0)"
```

**Critério correcto para pares:**
```python
# ❌ ERRADO
def requires_pair(phase_id):
    return coeficienteX[phase_id] > 0  # euros > 0 não significa pares

# ✅ CORRECTO
def requires_pair(phase_id):
    historical = get_team_sizes(phase_id)
    return sum(1 for t in historical if t >= 2) / len(historical) >= 0.80
```

**Onde CoeficienteX DEVE ser usado:** módulo Custos (src/profit/) — custo mão-de-obra, payroll, margem, throughput € real.

**Fixes:** CX1 (remover comentários), CX2 (critério histórico), CX3 (auditar tempos), CX4 (mover para profit), CX5 (alimentar custos).

**Lição:** Se H1 estava 100% errada, confirmar H2-H5 antes de implementar.

---

# PARTE II — O QUE O UTILIZADOR VÊ E FAZ

## 4. Filosofia de Interface

**Regra 1:** O software explica SEMPRE as consequências de tudo. Nunca propõe sem dizer porquê. Nunca executa sem mostrar o impacto.

**Regra 2:** A pessoa pode SEMPRE dizer sim ou não. E pode SEMPRE dizer PORQUÊ disse sim ou não. Esse porquê alimenta o cérebro que aprende.

**Regra 3:** Tudo é editável. O sistema NUNCA bloqueia uma edição humana. Se o gestor quer pôr um operador novato num barco difícil, o sistema avisa das consequências mas deixa fazer.

**Regra 4:** Advisory mode — o sistema NUNCA escreve no ERP sem aprovação.

## 5. Página de Colaboradores — CRUD Completo

O gestor gere toda a informação dos operadores num único sítio.

| Funcionalidade | Detalhe |
|---|---|
| Adicionar colaborador | Nome, função, custo/hora, data entrada, foto opcional |
| Eliminar colaborador | Soft delete — histórico mantém-se para ML e relatórios |
| Editar salário / custo hora | Histórico de alterações visível. CoeficienteX (prémio) vem do ERP |
| Editar grau de qualidade | Score 1-10. O ML sugere mas o gestor faz override manual |
| Editar skills | Checkbox por fase: o que sabe fazer. Adicionar/remover fases |
| Editar tier experiência | <5 meses, <12, >12 ou customizado. Afecta atribuição de barcos complexos |
| Ver histórico completo | Todas as operações, erros causados, fases feitas, modelos, produtividade |
| Comparar lado a lado | Seleccionar 2-3 operadores e comparar score, taxa erro, velocidade |
| Importar/exportar | CSV ou Excel — para carregar lista inicial ou backup |

**Consequências automáticas:** Quando o gestor altera o grau de qualidade de um operador, o sistema mostra imediatamente: "Se subir o Paulo de 7 para 9, ele passa a ser elegível para barcos K1 de competição. Isto liberta 2 barcos que estavam em espera por operador qualificado. Quer continuar?"

**Aprendizagem:** Cada edição manual do gestor (subir score, adicionar skill, mudar tier) é um sinal de preferência gravado. Se o gestor sobe sempre o score de operadores que fazem poucos erros na Laminagem, o ML calibra o seu modelo de qualidade para pesar mais os erros de Laminagem.

## 6. Página de Planeamento — Atribuir Barcos + Pessoas

A página principal do gestor. Funciona em duas camadas sequenciais:

### 6.1 Camada 1 — Atribuir Barcos a Fases/Centros

| Funcionalidade | Detalhe |
|---|---|
| Vista por fase/centro | Colunas: Prep.Molde, Pintura, Laminagem, Cura, Desmolde, etc. Cada coluna mostra os barcos atribuídos |
| Drag-and-drop barcos | Arrastar barco de uma fase para outra, ou de "não atribuído" para uma fase |
| Sugestão automática | O CPO propõe a distribuição óptima. Aparece como "fantasma" que o gestor pode aceitar ou ajustar |
| Filtros | Por cliente, por modelo, por urgência, por data expedição |
| Cores por urgência | Vermelho = atrasado, amarelo = em risco, verde = no prazo, azul = antecipado |
| Timeline/Gantt | Vista temporal com barras por barco, agrupadas por fase |

**Consequências automáticas:** Quando o gestor arrasta o K1 Vanquish para Laminagem na terça, o sistema mostra instantaneamente:
- "Molde K1 7 ML (03) tem 780 usos — perto do limite. Risco de defeito: 23%"
- "Operadores disponíveis: Paulo Gomes + Maria Silva (score 8.2) OU João Costa + Ana Reis (score 6.1)"
- "Se usar Paulo+Maria, acabam às 14h. Se usar João+Ana, acabam às 16h30"
- "Impacto no throughput do dia: +€2.400 se acabar antes das 15h (entra na expedição de sexta)"

### 6.2 Camada 2 — Atribuir Pessoas a Barcos

Depois de definir que barcos vão para que fases, o gestor atribui operadores.

| Funcionalidade | Detalhe |
|---|---|
| Vista por operador | Lista de operadores com: nome, skills, score qualidade, disponibilidade, carga actual |
| Sugestão inteligente | O sistema sugere o melhor operador para cada barco com explicação: "Paulo Gomes — taxa erro 3% neste modelo, 12 anos experiência, disponível às 8h" |
| Drag-and-drop pessoas | Arrastar operador para um barco/fase |
| Alertas de conflito | Se atribuir operador sem skill para aquela fase: aviso amarelo. Se atribuir operador a 2 barcos ao mesmo tempo: aviso vermelho |
| Regra de pares | Na Laminagem, se atribuir só 1 operador: aviso "Laminagem standard precisa de 2 operadores (88.5% histórico). Quer continuar com 1?" |
| Retrabalho | Se barco tem retrabalho, sistema sugere: "Este barco voltou da Lixagem com defeito de pintura. Recomendo devolver ao causador: João Costa (chefe na operação original)" |
| Zero idle | Quando operador acaba, sistema sugere próxima tarefa com razão |

**Consequências automáticas:** Quando o gestor atribui o João Costa (score 6.1, tier <5 meses) a um K1 de competição, o sistema mostra:
- "João Costa tem taxa de erro de 18% em modelos K1 (vs 4% da média). O barco é para a Federação Francesa — cliente premium"
- "Alternativa: Paulo Gomes (taxa erro 3% em K1, disponível às 10h — 2h de espera)"
- "Se avançar com João, risco de retrabalho: 18%. Custo estimado se houver defeito: €340"
- "Quer atribuir João mesmo assim?"

Se o gestor disser "sim, o João precisa de praticar" — esse PORQUÊ fica gravado. O sistema aprende que o gestor às vezes aceita risco de qualidade para formação on-the-job.

## 7. Página de Despacho/Expedição

O gestor gere que barcos vão em cada expedição/transporte.

### 7.1 Vista de Expedições

| Funcionalidade | Detalhe |
|---|---|
| Lista de expedições | Data transporte, cliente, nº barcos, estado (completa/parcial/em risco) |
| Barcos por expedição | Lista com: modelo, estado actual (que fase), % conclusão, prazo, risco |
| Adicionar/remover barcos | Drag-and-drop barcos entre expedições, ou para "sem expedição" |
| Capacidade camião | Indicador visual: 26/50 barcos (moda real vs capacidade CEO) |
| Calendário | Vista mensal com expedições por dia, cores por estado |

### 7.2 Sugestões Inteligentes de Despacho

O sistema analisa cada expedição e sugere alterações com explicação completa:

| Tipo de sugestão | Exemplo |
|---|---|
| Antecipar barco | "O K2 da Federação Italiana está pronto 3 dias antes do previsto. Se o mover para a expedição de sexta (em vez de terça), o cliente recebe mais cedo e liberta espaço na expedição de terça. Quer mover?" |
| Atrasar barco | "O K1 Vanquish da equipa norueguesa está na Lixagem com 23% probabilidade de retrabalho. Se atrasar para a expedição seguinte (+4 dias), evita enviar com possível defeito. Quer atrasar?" |
| Trocar entre expedições | "A expedição de sexta tem 52 barcos (acima de 50/camião). A de segunda tem 18. Sugestão: mover 3 barcos K4 (menos urgentes, cliente sem data fixa) para segunda. Reduz risco logístico e equilibra carga" |
| Completar camião | "A expedição de terça tem 26 barcos (meio camião). Há 8 barcos prontos sem expedição atribuída. Se juntar 4 deles, poupa um camião na semana seguinte. Custo logístico poupado: ~€800" |
| Reagrupar por cliente | "A Federação Portuguesa tem 5 barcos em 3 expedições diferentes. Se agrupar na expedição de quinta (todos estarão prontos), o cliente recebe tudo junto. Quer reagrupar?" |

### 7.3 Consequências Sempre Visíveis

Cada alteração na expedição mostra impacto em cascata:

```
O gestor remove o K1 #4271 da expedição de sexta:

CONSEQUÊNCIAS:
→ Expedição sexta: 49 barcos (ok, cabe num camião)
→ K1 #4271 fica sem expedição — próxima disponível: terça (+4 dias)
→ Cliente (Fed. Francesa) notificado de atraso? [SIM/NÃO]
→ Impacto throughput: -€2.400 sexta, +€2.400 terça (neutro semanal)
→ Laminagem liberta 2 operadores sexta (podem fazer outro barco)
→ Risco: se mover para terça, concorre com 3 barcos K2 pela Laminagem

[ACEITAR] [REJEITAR] [PORQUÊ?]
```

O botão **[PORQUÊ?]** é crucial. Quando o gestor clica, aparece campo de texto livre: "Porque é que aceita/rejeita esta sugestão?" A resposta é gravada no commit e alimenta a aprendizagem.

## 8. Timeline de Aprovação (Write-Gate)

Todas as sugestões do sistema — planeamento, despacho, workforce, manutenção — passam por aqui.

| Funcionalidade | Detalhe |
|---|---|
| Feed de sugestões | Lista cronológica, mais recentes em cima |
| Agrupamento por criticidade | Crítico (vermelho), importante (amarelo), optimização (verde) |
| Delta view | Cada sugestão mostra APENAS o que muda vs. plano actual |
| Alternativas MAP-Elites | Para sugestões de scheduling: 5-10 alternativas com trade-offs |
| Aprovar individual | Botão aprovar + campo opcional "porquê" |
| Aprovar em bloco | Seleccionar várias, aprovar de uma vez |
| Rejeitar com razão | Botão rejeitar + campo "porquê" (alimenta aprendizagem) |
| Modificar antes de aprovar | Editar a sugestão, depois aprovar a versão modificada |
| Auto-aprovação | Configurável por tipo: "aprovar automaticamente realocações de operadores idle" |
| Anti-fatigue | Se >20 sugestões pendentes, agrupar por impacto e mostrar só top 5 |
| Histórico | Todas as aprovações/rejeições com timestamp, user, razão |

**A sugestão NUNCA é só um número.** Cada sugestão inclui:
- O QUE muda (delta)
- PORQUÊ o sistema propõe (causa)
- O QUE ACONTECE se aceitar (consequência positiva)
- O QUE ACONTECE se rejeitar (consequência negativa)
- ALTERNATIVAS (se existirem)

Exemplo:
```
SUGESTÃO #847 — Prioridade: ALTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

O QUE: Mover 3 barcos K2 da Laminagem de terça para quarta

PORQUÊ: O molde K2 7 L (02) vai estar em manutenção terça
(CEO pediu manutenção preventiva na semana passada).
Sem molde, os 3 barcos ficam parados.

SE ACEITAR: Os 3 barcos acabam quarta em vez de terça (+1 dia).
A expedição de sexta mantém-se (margem de 2 dias).
Throughput terça desce €7K mas quarta sobe €7K. Neutro semanal.

SE REJEITAR: Os 3 barcos esperam terça sem molde disponível.
Acabam quarta na mesma mas com 8h de idle na Laminagem.
2 laminadores parados terça (custo: €120 cada = €240).

ALTERNATIVA: Usar molde K2 7 L (01) (2 poços em vez de 4).
Demora mais 2h mas não atrasa. Throughput neutro.

[ACEITAR]  [REJEITAR]  [ACEITAR ALTERNATIVA]
Porquê? [________________________________________]
```

## 9. Dashboard CEO

| Métrica | Visualização |
|---|---|
| Throughput €/dia | Número grande + gráfico tendência 30 dias. Meta: linha a €30K |
| OTD | Percentagem + tendência. Barcos entregues no prazo |
| Qualidade 1ª passagem | Percentagem sem retrabalho |
| Backlog por cliente | Tabela: cliente, barcos pendentes, valor €, prazo mais próximo |
| Expedições próximas 7 dias | Lista com nº barcos, estado, risco |
| Alertas activos | Moldes para manutenção, operadores ausentes, materiais em falta |
| Relatório por cliente | Gerado automaticamente, exportável PDF |

Sem jargão técnico. O CEO vê €, prazos e riscos.

## 10. Tablet Operador (chão de fábrica)

| Funcionalidade | Detalhe |
|---|---|
| Próxima tarefa | Barco, modelo, molde, parceiro (se par), tempo estimado |
| Instruções | Routing específico, observações do modelo |
| Botão "Comecei" / "Acabei" | Alimenta tempos reais e Trust Index Freshness |
| Botão "Problema" | Reportar defeito, molde danificado, falta material |
| Histórico do dia | O que já fez hoje, tempo total |

Sem plano global. Sem KPIs. Sem decisões. Só a SUA tarefa.

---

# PARTE III — ARQUITECTURA

## 11. Princípios Inalteráveis

1. **"LLM propõe, kernel decide"** — kernel determinístico, nunca alucina
2. **Safety net** — NUNCA devolver pior que baseline
3. **Advisory mode** — NUNCA escrever no ERP sem aprovação
4. **Explicar sempre** — cada sugestão com porquê + consequências
5. **Aprendizagem contínua** — cada sim/não + porquê torna o sistema mais inteligente
6. **Tudo editável** — o humano NUNCA é bloqueado
7. **TUDO configurável** — literalmente TUDO. Cada parâmetro, cada threshold, cada peso, cada regra, cada constraint pode ser alterado pelo utilizador. O sistema NUNCA tem valores hardcoded que o utilizador não consegue mudar. Se o sistema aprendeu uma regra automaticamente e o utilizador discorda, o utilizador ganha. SEMPRE.

### 11.1 O Que "TUDO Configurável" Significa na Prática

O utilizador consegue alterar:

**Scheduling / CPO:**
- Pesos da fitness (makespan, tardiness, setup, quality, throughput, idle) — slider ou campo numérico
- Frequência de replaneamento (cada 15 min, 30 min, 1h, manual)
- Budget temporal do CPO (30s, 60s, 120s, 5 min)
- Número de alternativas do MAP-Elites (3, 5, 10, 20)
- Horizonte de planeamento (1 dia, 2 dias, 1 semana)
- Objectivo principal (throughput €, OTD, qualidade, equilíbrio)

**Routing e Fases:**
- Sequência de fases por modelo (editar routing template)
- Adicionar/remover fases a um modelo
- Criar routing alternativo (A/B) para qualquer modelo
- Tempos de referência por fase (override sobre o valor calculado pelo sistema)
- Constraints de cura/secagem (min_gap_hours entre qualquer par de fases)
- Adicionar/remover fases inteiras ao catálogo

**Moldes:**
- Threshold de manutenção por molde (usos, dias, ou manual)
- Associação molde-modelo (que molde pode fazer que modelo)
- Poços por molde
- Estado do molde (activo, manutenção, inactivo)
- Custo de setup por transição de molde

**Workforce / Colaboradores:**
- Tudo do CRUD (secção 5): salário, skills, qualidade, tier
- Regra de pares por fase (obrigatório, recomendado, opcional)
- Score mínimo de qualidade por tipo de barco
- Quem pode aprovar sugestões (roles, permissões)
- Turnos e calendário (dias úteis, feriados, ausências)
- Custo/hora por operador e por turno

**Qualidade:**
- Threshold de alerta de qualidade (P(erro) > X%)
- Regra de retrabalho (volta ao causador sim/não, por fase)
- Gravidade dos erros (que tipos contam como defeito real)
- Factor de capacidade por fase (1.5× nas lixagens, configurável)

**Transporte / Expedição:**
- Capacidade por camião (50 barcos ou outro)
- Buffer dias antes de expedição
- Prioridade de clientes
- Regras de agrupamento (por cliente, por modelo, livre)

**Alertas:**
- Que alertas estão activos/inactivos
- Thresholds de cada alerta (barco > X dias, stock < Y, molde > Z usos)
- Quem recebe que alerta (gestor, chefe secção, operador)
- Frequência (imediato, diário, semanal)

**Custos:**
- Custo/hora por centro de trabalho
- Prémios/bónus por fase (CoeficienteX editável)
- Preço de venda por modelo (para throughput €/dia)
- Custo de materiais por modelo

**Aprendizagem:**
- Regras aprendidas: ver, activar, desactivar, eliminar, editar
- Pesos aprendidos: ver actual vs default, fazer reset
- DPO: ver pares de preferência, remover pares errados
- Auto-aprovação: que tipos de sugestão o sistema pode auto-aprovar

**Trust Index:**
- Pesos dos 7 componentes
- Gates (a que TI o sistema bloqueia o quê)
- Freshness threshold (quantas horas até dados serem "velhos")

**Sistema:**
- Idioma (PT, EN, DE)
- Tema (escuro, claro, automático)
- Formato datas, números, moeda
- Frequência de relatórios automáticos
- Quem vê o quê (RBAC por ecrã, por módulo, por acção)

### 11.2 Como Funciona Tecnicamente

Cada parâmetro configurável segue este padrão:

```python
# Nunca isto:
MIN_WORKERS_PINTURA = 18  # hardcoded, ninguém muda

# Sempre isto:
config = ConfigStore.get("min_workers_pintura",
    default=18,                        # valor default
    source="learned_rule_R12",         # de onde veio (regra aprendida, manual, sistema)
    editable=True,                     # utilizador pode mudar
    last_changed_by="gestor",          # quem mudou por último
    last_changed_at="2026-05-10",      # quando
    reason="CEO pediu nunca menos de 18",  # porquê
)
```

Cada alteração do utilizador é gravada com: quem, quando, valor anterior, valor novo, porquê. Isto permite:
- Audit trail completo (quem mudou o quê e quando)
- Rollback (voltar ao valor anterior)
- O sistema de aprendizagem saber que o utilizador fez override (e porquê)

### 11.3 Hierarquia de Configuração

```
1. Override manual do utilizador      → GANHA SEMPRE
2. Regra aprendida confirmada         → ganha se não há override
3. Regra aprendida não confirmada     → sugerida, não aplicada
4. Default do sistema                 → fallback
```

Se o sistema aprendeu "nunca propor mudanças na Laminagem à sexta" mas o gestor vai ao painel de configuração e desactiva essa regra, a regra morre. O utilizador SEMPRE ganha.

## 12. Stack na Máquina

| Componente | Tecnologia | Estado |
|---|---|---|
| OS | Ubuntu 24.04 LTS | ✅ A correr |
| Backend | FastAPI + Python 3.11 | ✅ A correr |
| Base dados | PostgreSQL 16 + pgvector | ✅ A correr |
| LLM | Ollama + Gemma 4 E4B | ✅ GPU com drivers |
| Scheduling | CPO v4.0 (Python + OR-Tools) | ✅ Implementado (com bugs) |
| Frontend | React 19 + Vite + shadcn/ui | ✅ 41 páginas |
| Cache | Redis (opcional) | Instalar com apt quando necessário |
| ERP cliente | SQL Server (Nelo) | ❌ Não ligado |
| Deploy | **Nativo + systemd. Sem Docker.** | ✅ |

**Sem Docker. Sem containers. Sem Compose.** Tudo instalado directamente no Linux com apt/pip. Cada serviço gerido pelo systemd:

```bash
# PostgreSQL — já está como serviço systemd
sudo systemctl enable postgresql

# PP1 Backend — criar serviço systemd
# /etc/systemd/system/pp1-backend.service
[Unit]
Description=PP1 Backend
After=postgresql.service

[Service]
User=pp1
WorkingDirectory=/opt/pp1
ExecStart=/opt/pp1/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# Ollama — já corre como serviço
sudo systemctl enable ollama

# Redis — quando necessário
sudo apt install redis-server
sudo systemctl enable redis-server
```

Máquina liga → tudo arranca. Serviço crasha → systemd reinicia. Zero Docker.

## 13. 5 Camadas

```
Layer 1 — RLM: estado da fábrica explorado via sub-queries, não na prompt
Layer 2 — POETIQ: gerar → executar (kernel) → criticar → refinar
Layer 3 — Kernel CPO v4.0: 6 fases cascading, budget ~60s
Layer 4a — RAG: pgvector + routing templates + skill matrix + erros
Layer 4b — LLM fine-tuned causal (quando houver dados suficientes)
Layer 5 — Trust Index + Causal Coherence gate

TRANSVERSAL — APRENDIZAGEM: cada decisão do gestor → 4 camadas de learning
```

## 14. Schedule-as-Code

```python
ScheduleCommit:
    commit_id: str               # SHA-256
    parent_id: str               # cadeia imutável
    author: str                  # humano ou agent
    timestamp: datetime
    message: str                 # razão
    delta: dict                  # o que mudou
    kpis: dict                   # snapshot KPIs
    alternatives: list           # MAP-Elites representativas
    rejected_alternatives: list  # CRÍTICO — cenários rejeitados + KPIs + razão
    trust_index: float
    user_reason: str             # PORQUÊ do gestor (campo livre)
    user_preference_signal: dict # Tolman: aceite vs rejeitado
```

`rejected_alternatives` + `user_reason` são os campos mais valiosos de todo o sistema.

## 15. Trust Index — 7+1 Componentes

C=Completeness (0.15), V=Validity (0.20), F=Freshness (0.15), K=Consistency (0.20), P=Provenance (0.15), A=Anomaly (0.10), E=Evidence (0.05), CC=Causal Coherence (futuro).

Gates: TI < 0.50 → sugestão. TI < 0.75 → aprovação humana obrigatória. TI < 0.80 → qualidade bloqueada.

---

# PARTE IV — CPO v4.0: O MOTOR

## 16. Classificação: DRCFFS-R

Dual-Resource Constrained Flexible Flow Shop with Re-entrance. NP-hard.

## 17. Pipeline Greedy — 8 Fases

```
1. DEMAND AGGREGATION → Net demand
2. BACKWARDS SCHEDULING → Latest-start por fase (puxado transporte)
3. ROUTING SELECTION → Routing A ou B
4. SETUP GROUPING → Agrupar por molde
5. MULTI-CENTER DISPATCH → Schedule por centro + operador
6. WORKFORCE ASSIGNMENT → Hungarian (skill × quality × tier)
7. BUFFER & JIT → Buffers baseados em variância histórica
8. SCORING → KPIs (makespan, tardiness, €/dia, quality_risk)
```

## 18. Cromossoma

```python
ChromosomeV4:
    permutation: list[int]           # ordem processamento (PRIMARY)
    routing_choices: dict[int, str]  # operation_id → "A" ou "B"
    setup_grouping_gap: int
    buffer_pct: float
    worker_quality_weight: float
```

Decode: 1D → 3D (máquina por min load, worker por skill × quality, time por earliest).

## 19. Pipeline CPO — 6 Fases

| Fase | Tempo | O que faz |
|---|---|---|
| 1. Greedy 8-phase | 2s | Solução viável |
| 2. GA + FRRMAB | 30s | 100 pop × 200 gen, c=0.2 |
| 3. MAP-Elites 3D | 5s | 10×10×5, 5-10 alternativas |
| 4. Surrogate RF | embebido | Pre-screen 80%, threshold=1.2× |
| 5. CP-SAT Rolling Horizon | 15s | L-RHO warm-start |
| 6. Workforce Optimizer | 3s | Hungarian + quality risk |
| **TOTAL** | **~60s** | |

## 20. Fitness

```python
fitness = (
    0.20 × makespan +
    0.25 × tardiness_transporte +
    0.15 × idle_operadores +
    0.15 × setup_time_total +
    0.10 × quality_risk_score +
    0.15 × (-throughput_euro_dia)
)
# ⚠️ PESOS ARBITRÁRIOS. Sistema de aprendizagem (Camada 2) ajusta
# com base nas preferências reveladas do gestor após ~50 commits.
```

---

# PARTE V — O SISTEMA DE APRENDIZAGEM

## 21. Princípio

Cada decisão do gestor torna o sistema mais inteligente. Cada rejeição é tão valiosa como cada aprovação. O porquê da decisão é o data point mais valioso.

## 22. Camada 1 — Regras Explícitas (funciona dia 1, zero ML)

Detectar padrões nas rejeições e criar regras verificáveis.

```python
# Se gestor rejeita 5× cenários que mexem Laminagem à sexta:
Rule("Não propor alterações Laminagem à sexta", confidence=0.92)

# Se gestor sempre escolhe menos setup quando throughput similar:
Rule("Preferir menos setup a mais throughput (delta < 5%)", confidence=0.85)

# Se gestor sempre sobe score de operadores com poucos erros Laminagem:
Rule("Peso erros Laminagem > peso erros outras fases no score", confidence=0.78)
```

Cada regra é proposta ao gestor: "Reparei que nunca aceita X. Quero evitar propor no futuro. Confirma?" Se confirma → regra activa. Se rejeita → padrão descartado.

~200 linhas Python. Sem dependências ML. Contadores sobre commits.

## 23. Camada 2 — Pesos Adaptativos (precisa ~50 commits)

Os pesos da fitness do GA adaptam-se às preferências reveladas.

Método: para cada commit com rejected_alternatives, extrair delta KPIs → regressão logística → coeficientes = pesos implícitos → blend 70% learned + 30% default.

Exemplo após 3 meses: setup sobe de 15% para 22%, quality_risk sobe de 10% para 18%. O sistema reporta ao gestor.

## 24. Camada 3 — DPO no LLM (precisa ~500 pares, ~6 meses)

Direct Preference Optimization. O LLM aprende não só O QUE o gestor prefere mas COMO pensa. Estilo de comunicação, prioridades implícitas, vocabulário, timing.

## 25. Camada 4 — ABLkit (loop contínuo)

Quando o LLM erra um diagnóstico, o kernel corrige. O par (erro, correcção) treina o LLM. Melhora especificamente nos erros que comete.

## 26. Pipeline de Aprendizagem ao Longo do Tempo

```
DIA 1 → Regras default. Pesos default. LLM base.
         Mas CADA decisão do gestor é gravada com contexto + porquê.

MÊS 1 (30 commits):
  → Camada 1: primeiras regras ("nunca < 18 pintores", "manutenção preventiva")
  → O gestor já nota: "este sistema está a parar de me propor coisas que eu rejeito"

MÊS 3 (120 commits):
  → Camada 2: pesos fitness ajustados (setup 15%→22%, quality 10%→18%)
  → O gestor nota: "os planos são melhores, mais parecidos com o que eu faria"

MÊS 6 (300 commits):
  → Camada 3: primeiro DPO fine-tuning
  → Taxa de rejeição: ~10% (vs ~40% no mês 1)
  → O gestor nota: "o sistema já pensa como eu"

MÊS 12 (600+ commits):
  → Todas as camadas estabilizadas
  → O sistema É o gestor digitalizado
  → Se o gestor se reformar, o conhecimento fica
```

## 27. O Que GRAVAR Desde o Dia 1

1. Estado da fábrica no momento (WIP, carga, operadores, moldes)
2. TODOS os cenários gerados (não só o escolhido)
3. KPIs de cada cenário
4. Qual foi escolhido + timestamp + user
5. Quais foram rejeitados + KPIs
6. **PORQUÊ** (campo livre do gestor — o data point mais valioso)
7. Contexto temporal (dia, hora, proximidade expedição)

Sem isto, o sistema NUNCA aprende.

---

# PARTE VI — O LLM

## 28. POETIQ Loop

Gerar (LLM + RLM) → Executar (CPO) → Criticar (feedback causal) → Refinar. 2-5 iterações. Score = kernel × 0.7 + llm × 0.3.

## 29. Code-First Causal Prompting

```python
# Intervenção (Rung 2)
do(K1_Vanquish.routing = 'B')
query: completion_date, transport.on_time

# Contrafactual (Rung 3)
counterfactual(observed: throughput = 22000, intervention: remove(transport='2026-05-15'))

# Abdução
observe(retrabalho_lixagem rose 15% to 23%)
task: identify root_cause using Mill_method_of_difference
```

## 30. 7 Tipos de Pares Causais

Estado factual (15%), Intervenção simples (20%), Intervenção composta (10%), Contrafactual (15%), Abdução (15%), Common cause (10%), Cadeia longa (15%).

## 31. DoWhy-GCM, PCMCI+, Verificação 5 Camadas

DAG formal com 22 nós e 3 confundidores. Inferência causal formal. Descoberta causal após 3-6 meses. Verificação: syntax → DAG → direction → NLI → kernel. CC ≥ 0.85.

---

# PARTE VII — REQUISITOS FUNCIONAIS

## 32. Write-Gate (10 requisitos)

WG01-WG10: Timeline, delta view, aprovação individual/bloco, auto-aprovação, anti-fatigue, MAP-Elites alternativas, campo "porquê" OBRIGATÓRIO em rejeições.

## 33. Factory Map (6 requisitos)

FM01-FM06: Mapa visual, visão actual/futura, % rutura, KPIs, carga sobre linha.

## 34. Gestão Colaboradores (10 requisitos)

GC01-GC10: CRUD completo — adicionar, eliminar, editar salário/custo, editar qualidade com override sobre ML, editar skills por fase, editar tier, histórico, comparação, import/export. Tudo editável.

## 35. MRP (8 requisitos)

MR01-MR08: Config MP, prospeção, erros por fornecedor, alertas falta, stock mínimo, correcção manual, histórico, tudo editável.

## 36. Planeamento (24 requisitos)

PL01-PL24: Granularidade 15 min, setup optimization, 61 routing templates + A/B, backwards transporte, tempos históricos NUNCA standard, buffer pós-Desmolde, moldes multi-cavidade, throughput €/dia, replaneamento contínuo, drag-and-drop barcos, sugestão automática com consequências.

## 37. Despacho/Expedição (8 requisitos)

DE01: Vista expedições com estado (completa/parcial/risco)
DE02: Adicionar/remover barcos por drag-and-drop
DE03: Sugestões inteligentes de troca entre expedições com explicação completa
DE04: Indicador capacidade camião (26 moda vs 50 CEO)
DE05: Antecipar barcos prontos cedo com impacto cliente
DE06: Atrasar barcos em risco qualidade com custo de retrabalho
DE07: Completar camião (juntar barcos sem expedição)
DE08: Reagrupar por cliente (tudo junto em vez de 3 expedições)

Cada sugestão com: O QUE + PORQUÊ + SE ACEITAR + SE REJEITAR + ALTERNATIVA.

## 38. Workforce (12 requisitos)

WF01-WF12: Auto-reallocation, skill tiers, smart assignment, pares Laminagem (dados históricos, NÃO CoeficienteX), bottlenecks (Pintura 40 aptos/22 reais, Colagem Golas 13). Retrabalho volta ao causador.

## 39. Qualidade (11 requisitos)

QA01-QA11: Causador, retrabalho accountability, ML quality risk, manutenção preventiva moldes (threshold CONFIGURÁVEL, não hardcoded), buffer capacidade 1.5× nas lixagens.

## 40. Alertas (8), Stock (4), Custos (6), Relatórios (5), Config (30+)

Alertas: falta dados, material, barcos > X dias, molde > threshold — todos com thresholds editáveis.
Custos: CS05 throughput €/dia, CS06 CoeficienteX como prémio real. Preço venda por modelo editável.
Config: ver secção 11.1 — TUDO é configurável. 30+ categorias de parâmetros. Cada um com default, override, audit trail, e razão.

### Página de Configuração

| Secção | O que contém |
|---|---|
| Scheduling | Pesos fitness, frequência replaneamento, budget CPO, horizonte, nº alternativas |
| Routing | Templates por modelo, fases, sequência, routing A/B, tempos referência |
| Cura/Secagem | min_gap_hours por par de fases — tabela editável |
| Moldes | Threshold manutenção, associação modelo, poços, custo setup |
| Workforce | Regra pares por fase, score mínimo, turnos, calendário |
| Qualidade | Threshold alerta, regra retrabalho, factor capacidade |
| Transporte | Capacidade camião, buffer dias, prioridade clientes |
| Alertas | On/off por alerta, thresholds, destinatários |
| Custos | Custo/hora, prémios, preço venda, materiais |
| Aprendizagem | Regras aprendidas (ver/editar/eliminar), pesos learned, DPO pares |
| Trust Index | Pesos componentes, gates, freshness threshold |
| Sistema | Idioma, tema, formatos, RBAC, relatórios |

Cada parâmetro mostra: valor actual, quem definiu, quando, porquê, valor default, botão reset.

---

# PARTE VIII — ECOSSISTEMA: LIGAÇÕES EM FALTA

15 ligações entre módulos partidas. Prioridades:

1. plan ← profit (throughput €/dia na fitness)
2. plan ← state (constraints cura/secagem)
3. commits + rejected_alternatives (aprendizagem)
4. plan ← hr (turnos, ausências)
5. plan ← supply (stock matéria-prima)
6. plan ← dqa (Trust Index gateia scheduler)
7. explain ← plan (explain traces)
8. sandbox ← plan (simulação com scheduler)

---

# PARTE IX — ROADMAP HONESTO (24 semanas)

## 41. Fase 0 — Bugs + Fundação (Semanas 1-3)

- **PRIMEIRO:** Fixes CoeficienteX (CX1-CX5)
- **SEGUNDO:** Confirmar H3, H4, H5 com CEO (10 min)
- **TERCEIRO:** Implementar ConfigStore — ZERO valores hardcoded no código. Cada parâmetro vem da DB com default, override, audit trail (ver secção 11.2)
- Resolver 10 bugs CPO v3.0
- Adicionar 16 constraints cura/secagem ao decoder (da ConfigStore, editáveis)
- Implementar rejected_alternatives + user_reason no ScheduleCommit
- Ligar plan ← profit (throughput €/dia)
- Ligar máquina à rede Nelo → SQL Server

## 42. Fase 1 — Copilot + Colaboradores (Semanas 4-6)

- LLM responde perguntas com dados reais (testar 100 perguntas)
- RAG com 61 routing templates, skill matrix, erros
- Página de Colaboradores (CRUD completo)
- Camada 1 aprendizagem activa

## 43. Fase 2 — Planeamento + Timeline + Config (Semanas 7-9)

- Página de Planeamento (atribuir barcos + pessoas com drag-and-drop)
- Timeline de Aprovação com consequências e campo "porquê"
- **Página de Configuração (secção 11.1) — TUDO editável pelo utilizador**
- CPO greedy 8-fases com dados Nelo
- Backwards scheduling com datas transporte

## 44. Fase 3 — CPO Completo + Despacho (Semanas 10-13)

- GA+FRRMAB + MAP-Elites 3D + Surrogate + CP-SAT
- Página de Despacho/Expedição com sugestões inteligentes
- Copilot chama CPO via POETIQ one-shot
- Camada 2 aprendizagem activa (50+ commits)

## 45. Fase 4 — ML + Qualidade (Semanas 14-17)

- Quality risk model (XGBoost, 89K erros)
- Mold maintenance model
- Trust Index completo (7 componentes)
- Ligar módulos em falta (hr, supply, dqa)

## 46. Fase 5 — Fine-tuning + Polish (Semanas 18-21)

- Fine-tuning QLoRA se necessário
- POETIQ iterativo
- Tablet operador (chão de fábrica)
- Dashboard CEO

## 47. Fase 6 — Produção (Semanas 22-24)

- Stress test, PCMCI+ (se dados suficientes), DPO batch (se 500+ pares)
- Documentação + SLA

---

# PARTE X — FÓRMULA DE ANÁLISE DE DADOS HISTÓRICOS

## 48. O Método

```python
def valor_referencia(dados_raw):
    # PASSO 1: Remover zeros (registo batch, não realidade)
    nao_zeros = dados_raw[dados_raw > 0.05]
    
    # PASSO 2: Remover > P95 (outliers)
    p95 = nao_zeros.quantile(0.95)
    limpos = nao_zeros[nao_zeros <= p95]
    
    # PASSO 3: Moda (arredondada a 0.5h)
    moda = (limpos * 2).round() / 2
    moda_val = moda.mode().iloc[0]
    moda_pct = (moda == moda_val).sum() / len(moda) * 100
    
    # PASSO 4: Se moda ≥ 8% → usar. Senão → mediana ≠0
    if moda_val > 0 and moda_pct >= 8:
        return moda_val  # pico real
    else:
        return round(nao_zeros.median() * 2) / 2  # fallback
```

### Erros a NUNCA cometer

1. Nunca usar a **média** — SEMPRE inflacionada por outliers
2. Nunca usar mediana **sem filtrar zeros** — zeros são registo mal feito
3. Nunca aceitar **moda=0** para fases com trabalho real
4. Nunca misturar **tempo de trabalho** com **tempo de espera**
5. Nunca confundir **gap inter-fase** com **fila** — cura não é fila

---

# PARTE XI — AUDITORIA DE CÓDIGO (34 problemas)

## 49. P0 — Fix antes de demo (11 items)

| ID | Problema | Fix |
|---|---|---|
| CX1 | CoeficienteX comentários errados (3 ficheiros) | Remover |
| CX2 | Critério pares = CoeficienteX > 0 | Mudar para mediana team_size ≥ 2 |
| CX3 | CoeficienteX pode entrar em contas tempo | Auditar decoder, fitness |
| CX4 | CoeficienteX no workforce em vez de profit | Mover para src/profit/ |
| CX5 | Custos sem prémios reais | Alimentar com CoeficienteX |
| D1 | Setup counter sempre zero | Implementar comparação setup_family |
| D2 | Sem constraints cura/secagem | Adicionar min_gap_hours (16 transições) |
| F1 | Sem throughput €/dia | Adicionar à fitness |
| WG1 | Aprovação não executa acção | Implementar ActionExecutor |
| CO1 | Sem rejected_alternatives | Adicionar campo + user_reason ao commit |
| C1 | Sem routing_choices no cromossoma | Adicionar dict + mutação flip A↔B |

## 50. P1 — Fix para CPO funcional (10 items)

D3 (quality_weight não usado), D4 (sem backwards), D5 (workers sem skills), F2 (sem idle), F4 (quality OFF), E1 (50 gen não 200), ME1 (eixos errados), ST1 (sem cura data), TI1 (4 de 7 componentes), WG2 (rollback não funciona).

## 51. P2 — Fix qualidade (8 items)

D6 (batch threshold), D7 (soft horizon), F3 (pesos não normalizados), FR1 (flip_routing é 2-opt reverse), FR2 (decay ineficiente), E2 (surrogate OFF), E3 (reward perdido), SN1 (makespan ignorado no safety net).

## 52. P3 — Nice to have (5 items)

C2, C3, ME2, TI2, F5 (cascata D1).

## 52b. P0 ADICIONAL — Eliminar valores hardcoded

O princípio "TUDO configurável" exige que ZERO parâmetros estejam hardcoded no código. Cada valor que hoje é constante no Python tem de migrar para ConfigStore (DB + API + UI de configuração).

Valores hardcoded conhecidos a migrar:

| Ficheiro | Valor hardcoded | Migrar para ConfigStore |
|---|---|---|
| fitness.py | w_makespan=1.0, w_tardiness=10.0, w_setups=0.5 | config.scheduling.fitness_weights |
| engine.py | generations=50, population=100 | config.scheduling.ga_params |
| engine.py | use_surrogate=False | config.scheduling.surrogate_enabled |
| frrmab.py | c=0.2, window=200 | config.scheduling.frrmab_params |
| mapelites.py | grid dimensions | config.scheduling.mapelites_grid |
| decoder.py | horizon_end | config.scheduling.horizon_days |
| safety_net.py | comparison thresholds | config.scheduling.safety_thresholds |
| trust_index.py | component weights (30,30,20,20) | config.trust.component_weights |
| trust_index.py | gates (0.50, 0.60, 0.70, 0.75, 0.80) | config.trust.gates |
| state.py | phase pair rules | config.workforce.pair_rules |
| default_configs.py | todos os defaults | config.* (migrar tudo) |

Padrão: `config = ConfigStore.get(key, default=X, editable=True)`. Nunca `X = 0.5`.

---

# PARTE XII — PRESSUPOSTOS vs CONFIRMADOS

## 53. Confirmado

Meta €30-35K/dia ✅, 61 routings ✅, Laminagem 88.5% pares ✅, Desmolde 96.4% ✅, Retrabalho real ✅, 122 workers ✅, 40/22 Pintura ✅, Tempos referência ✅, 16 constraints cura ✅, CoeficienteX = prémio € ✅

## 54. Hipóteses

| # | Status | Pressuposto |
|---|---|---|
| H1 | ❌ **ERRADO** | CoeficienteX = tempo 2º worker → é prémio € |
| H2 | ⚠️ INVENTADO | Threshold manutenção = 800 usos → sem dados |
| H3 | ⚠️ CONFIRMAR | Gravidade 1 vs 2 = warning vs defeito |
| H4 | ⚠️ CONFIRMAR | Laminagem 1 worker = erro registo |
| H5 | ⚠️ CONFIRMAR | Data transporte = por dia |
| H6 | Implementável | Replaneamento 15 min (ajustável) |
| H7 | Implementável | Pesos fitness (aprendizagem ajusta) |
| H8 | Estimado | WIP 220-540 (confirmar) |

**LIÇÃO H1:** Custo de confirmar = 10 min. Custo de construir sobre erro = semanas.

---

# PARTE XIII — MOAT COMPETITIVO

5 barreiras: Kernel DRCFFS-R (18-24 meses replicar), Dataset causal proprietário, Conhecimento tácito acumulado (impossível copiar), Compounding 12 insights, Causal discovery contínuo.

Nenhum concorrente tem: kernel causal verificável + aprendizagem com preferências + on-premise air-gapped + preço PME.

---

# PARTE XIV — REFERÊNCIAS

Mlekusch & Hartl (2025) DRCFFS, Li et al. (2025) FJSP-MW, L-RHO (2025) ICLR, Lu et al. (2018) concise chromosome, MAP-Elites MEHH (2022), Fan et al. (2025) DRCFJSP, CARE Duke (2025), MIT Press (2025) code prompts, DoWhy-GCM (JMLR 2024), PCMCI+ Tigramite, CP-SAT Rostering (Brenndoerfer 2025).

Dados Nelo: Folha_IA_Extra.xlsx 57MB, 10 tabelas, 529.450 operações, 89.836 erros, 2020-2026.

---

*PP1 × NELO — O Plano Completo v4*

*NIKUFRA.AI — Abril 2026 — Confidencial*

*O software que explica, aprende, e pensa como o gestor.*
