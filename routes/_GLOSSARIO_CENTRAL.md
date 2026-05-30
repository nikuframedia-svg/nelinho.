# Glossário central de vocabulário ERP NELO

> **Estado:** 2026-05-24 — primeira versão criada na Q.81 (domínio QUALIDADE).
>
> Este é o **índice unificado** de todos os conceitos do ERP MAR-KAYAKS que o copiloto
> precisa de saber para responder a perguntas. Cada conceito tem **uma linha** com a
> tabela/coluna canónica, a regra/filtro a aplicar, a fonte que o provou e o grau de
> certeza.
>
> O ficheiro irmão [`_GLOSSARIO_BURACOS.md`](_GLOSSARIO_BURACOS.md) é o histórico
> forense do domínio MATERIAIS (Q.78/SubB2.3) — fica como trail; **as entradas vivas
> consolidadas estão aqui**.

---

## Formato

```
| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
```

- **conceito** — termo de negócio (ex.: "OF activa", "matéria-prima", "defeito grave").
- **domínio** — produção / materiais / qualidade / moldes / etc.
- **tabela.coluna** — onde está no ERP (SQL Server MAR-KAYAKS).
- **filtro/regra** — o predicado SQL que aplica o conceito.
- **fonte** — tabela ERP / view ERP / inferência por evidência / decisão analista.
- **grau** — `CONFIRMADO` (tabela autoritativa ou evidência inequívoca) /
  `HIPÓTESE FORTE` (evidência boa mas sem lookup formal) /
  `DECISÃO NEGÓCIO PENDENTE` (BD não decide, falta humano) /
  `FRONTEIRA` (atravessa domínios — não decidir sozinho).

Linhas só aparecem aqui depois de **um documento de domínio** as ter justificado
(`agent_docs/qXX_<dominio>_catalogo.md`).

---

## Domínio: PRODUÇÃO (Q.79 — `05ab3bb`)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Fase actual da OF | produção | `ORDEMFABRICO.OF_FP_ID` → `FASES_PRODUCAO.FP_NOME` | JOIN simples | tabela ERP | CONFIRMADO |
| OF activa | produção | `ORDEMFABRICO.OF_FP_ID` | `OF_FP_ID IN (fases FP_SEQUENCIA < 30)` | inferência por evidência (8.350 OFs activas em vs 30K falso-positivo do critério antigo) | HIPÓTESE FORTE |
| Lista das 71 fases | produção | `FASES_PRODUCAO` | `(FP_ID, FP_NOME, FP_SEQUENCIA)` | tabela ERP | CONFIRMADO |
| Sequência de fluxo | produção | `FASES_PRODUCAO.FP_SEQUENCIA` | escala 0–50 | tabela ERP | CONFIRMADO |
| Recovery paths (defeito → fase reprocessamento) | produção | `FP_FP` | 11 rows | tabela ERP | CONFIRMADO |
| Rota planeada por produto | produção | `PRODUTO_FASE` | 4.815 produtos / 42K rows | tabela ERP | CONFIRMADO |
| Tempo planeado por fase | produção | `PRODUTO_FASE.PRODF_TEMPO` | `> 0` | tabela ERP — **só 3.4% rows têm tempo>0** | parcial |
| OF "esquecida" (já produzida, OF_DATAFIM ficou NULL) | produção | `ORDEMFABRICO.OF_DATAFIM IS NULL AND OF_FP_ID em pós-produção` | — | inferência | HIPÓTESE FORTE |
| Turno de trabalho | produção | `PLANO_LAMINAGEM_LISTA_TURNOS` | (TURN_ID 1=Manhã, 2=Tarde, 3=Noite) | tabela ERP | CONFIRMADO |
| Tipo de uso da OF | produção | `ORDEMFABRICO.OF_OFTU_ID` → `OF_TIPOUSO` | 1=2ª Escolha / 2=Teste/Stock / 59=Cedidos | tabela ERP | CONFIRMADO |
| Linha de produção | produção | view `OF_LINHA_PROD` | id_of + linha (Linha 1, Linha 2) | view ERP | CONFIRMADO |
| Controlo ambiental por fase | produção | `OF_FP.OFFP_TEMPERATURA`, `OFFP_HUMIDADE` | — | tabela ERP | CONFIRMADO |
| Definição de "duração de fase" | produção | (calculável de `OFFP_DATAFIM - OFFP_DATAINICIO`) | inclui pausas? noite? — não decidido | — | **DECISÃO NEGÓCIO PENDENTE** |
| Definição de "atrasado" | produção | (face a `OFFP_DATA_PREVISTA` 15% ou `PRODF_TEMPO` 3.4% ou `OF_DATATRANSPORTE`?) | — | — | **DECISÃO NEGÓCIO PENDENTE** |

---

## Domínio: MATERIAIS (Q.78 / SubB2.3 — `220d811`)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Tipo de movimento | materiais | `MOVIMENTO_TIPO` | 15 valores | tabela ERP | CONFIRMADO |
| Consumo de produção | materiais | `MOVIMENTO.MOV_TPMOV_ID` | `= 11` (Saída como componente) | inferência + 4 amostras OF terminadas | CONFIRMADO |
| Reservas (planeamento, NÃO consumo) | materiais | `MOVIMENTO.MOV_TPMOV_ID` | `= 4` — separada de consumo | análise temporal (Reserva→Componente 1-3 meses) | CONFIRMADO |
| Tipo contabilístico do produto | materiais | `PRODUTO_CONTABILIDADE_TIPO` | 10 valores | tabela ERP | CONFIRMADO |
| Matéria-prima | materiais | `PRODUTO.P_PCONT_ID` | `= 1` (Matéria Prima, 5.913 produtos) | tabela ERP | CONFIRMADO |
| Unidade de medida | materiais | `UNIDADE` | 22 valores oficiais | tabela ERP | CONFIRMADO |
| Factor de conversão | materiais | `PRODUTO_UNIDADE.P_UNI_MOV_FACTOR` | aplicar `MOV_QUANTIDADE * COALESCE(P_UNI_MOV_FACTOR, 1)` | tabela ERP | CONFIRMADO |
| Estado de produto | materiais | `PRODUTO_ESTADO` | 7 valores | tabela ERP | CONFIRMADO |
| Tipo de molde | materiais (fronteira moldes) | `MOLDES_TIPO` | 14 valores | tabela ERP | FRONTEIRA |
| Tipo de componente | materiais | `COMPONENTE_TIPO` | 4 valores | tabela ERP | CONFIRMADO |

---

## Domínio: QUALIDADE (Q.81 — este sprint)

### Lookups vivas (5)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Escala de gravidade fina (Muito Bom → Muito Grave) | qualidade | `PROBS_CLASSIFICACAO` | 6 valores (CL_ID 1-6, ORDEM 1-6) | tabela ERP | CONFIRMADO |
| Escala de gravidade simples | qualidade | `OFFP_CL` | 3 valores (1=Muito Grave / 2=Grave / 3=Não Grave) | tabela ERP | CONFIRMADO |
| Tipo de remediação (NÃO é gravidade) | qualidade | `OFFP_GRAVIDADE` | 5 valores (Preparação / Lixar-Polir / Transformação / Reparar não-grave / Reparar grave-molde); col `OFFPGRAV_PARAR` indica se interrompe fluxo | tabela ERP — **REFUTA glossário antigo que dizia ser gravidade** | CONFIRMADO |
| Zona física do kayak | qualidade | `PROBS_LOCAL` | 7 valores (Interior/Gola/Proa/Ré/Deck/Casco/Emenda) | tabela ERP | CONFIRMADO |
| Lista das 71 fases (cross-domínio) | qualidade (fronteira produção) | `FASES_PRODUCAO` | (já em produção) | tabela ERP | FRONTEIRA → ver produção |

### Vivos / utilizáveis em rotas

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Defeito reportado num check (escala ampla) | qualidade | `OF_CHECKLIST.OFCH_GRAVIDADE` | `>= 1` (escala 0–3: 0=template OK / 1=leve / 2=médio / 3=grave); 131K em 3M = 4.4% | inferência por evidência (samples grav=3 são "Molde com deformações", "Interior mal molhado") | HIPÓTESE FORTE (sem lookup formal) |
| Defeito grave de molde | qualidade | `OF_CHECKLIST.OFCH_MOLDE_REPARAR` | `= 1` (84.347 rows, 2.8%) | tabela ERP | CONFIRMADO |
| Fase de origem do defeito (tracing) | qualidade | `OF_CHECKLIST.OFCH_OFFP_ID_CULPA` | JOIN `OF_FP` para chegar à fase. Cobertura 66% (1.99M de 3M) | tabela ERP | CONFIRMADO |
| Defeito por categoria (fina) | qualidade | `OF_FP.OFFP_PROBS_<INTERIOR/PINTURA/MOLDE/LAMINAGEM>` | aponta para `PROBS_CLASSIFICACAO.CL_ID` (1–6); cobertura ~0.47% por categoria | inferência confirmada (distribuição bate certo, top val=3 Normal) | CONFIRMADO |
| Retorno grave da OF | qualidade | `OF_FP.OFFP_RETORNO_GRAVE` | `= 1` (10.390 rows vivo 2022→) | tabela ERP | CONFIRMADO |
| Problemas em texto livre | qualidade | `OF_FP.OFFP_PROBLEMAS` | `IS NOT NULL AND <> ''` (138.101 rows, vivo 2013→, ~3.500/ano) | tabela ERP | CONFIRMADO (parsing LLM) |
| Data do registo de problema | qualidade | `OF_FP.OFFP_PROBS_DATA` | smalldatetime (57K rows, 2013–2026) | tabela ERP | CONFIRMADO |
| Defeito por zona física | qualidade | `OFCH_LOCAL` JOIN `PROBS_LOCAL` | 58.590 rows ligam OFCH_ID a zona (Deck/Emenda/Casco/Proa/Gola/Interior/Ré) | tabela ERP | CONFIRMADO |

### Mortos / piloto parado (NÃO PROMETER)

| conceito | domínio | tabela.coluna | razão para não usar | fonte | grau |
|---|---|---|---|---|---|
| Sistema OFFP_GRAVIDADES (atribuir remediação à fase) | qualidade | `OFFP_GRAVIDADES` | 140 fases em 2.64M = 0.005% cobertura; usado só entre 2024-12 e 2025-09 | tabela ERP (piloto parado) | EVITAR |
| Sistema OFFP_PROBLEMA (defeito estruturado por zona) | qualidade | `OFFP_PROBLEMA` | 0 rows — schema nunca usado | tabela ERP (morta) | EVITAR |
| Hierarquia PROBS (104) | qualidade | `PROBS` | só ligada a OFFP_PROBLEMA (que tem 0 rows) | tabela ERP (morta) | EVITAR |
| Sistema PROB_CAUSA_SOL (5-Why) | qualidade | `PROB_CAUSA_SOL` | 2 rows (registos 2009) — nunca decolou | tabela ERP (morta) | EVITAR |
| Flag VISTO no check | qualidade | `OF_CHECKLIST.OFCH_VISTO` | 99.7% False — workflow abandonado | tabela ERP | EVITAR |
| Flag RESOLVIDO no check | qualidade | `OF_CHECKLIST.OFCH_RESOLVIDO` | 99.99% False (73 True em 3M) — abandonado | tabela ERP | EVITAR |
| CULPA_CHEFE | qualidade | `OF_CHECKLIST.OFCH_CULPA_CHEFE` | 98.7% True (default não-actualizado) — não fiável | tabela ERP | EVITAR |
| Problemas GOLA texto | qualidade | `OF_FP.OFFP_PROBS_GOLA` | 402 rows, último 2017 — abandonado | tabela ERP | EVITAR |

### Buracos pendentes (analista NELO)

| conceito | domínio | tabela.coluna | bloqueio | grau |
|---|---|---|---|---|
| Vocabulário de OFCH_ESTADO | qualidade | `OF_CHECKLIST.OFCH_ESTADO` | int 67.5% NULL; distrib 1=841K, 3=117K, 5=11K, 4=5K, 2=1K; **sem lookup encontrada**; provável estado-do-flow do check | DECISÃO NEGÓCIO PENDENTE |
| Qual escala de gravidade é canónica? | qualidade | (3 escalas coexistem) | OFCH_GRAVIDADE 0–3 vs OFFP_PROBS_* 1–6 vs OFFP_CL 1–3 — qual para reporting oficial? | DECISÃO NEGÓCIO PENDENTE |
| "Defeito" mínimo é grav>=1 ou grav>=2? | qualidade | `OF_CHECKLIST.OFCH_GRAVIDADE` | factor 5× nas métricas conforme escolha | DECISÃO NEGÓCIO PENDENTE |

---

## Domínio: MOLDES (Q.82)

Investigação completa em `agent_docs/q82_moldes_catalogo.md`.

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Catálogo de moldes (moldes-de-casco) | moldes | view `OF_IDS_MLD` | 1.506 OFs-molde; JOIN com ORDEMFABRICO 100% match | view ERP | CONFIRMADO |
| Tipo de molde (acessórios) | moldes | `MOLDES_TIPO` | 14 valores (Banco Standard/Ultra Low/Nelo/Rotativo/Rotofix, Caixa Rotativo, Travessa, Tampa Leme, Strap, FP's Surf Ski, Leme Surf Ski, Leme Sea Vanquish, FP's pq, FP's gr) | tabela ERP | CONFIRMADO |
| Estado actual do molde | moldes | `OF_IDS_MLD` JOIN `ORDEMFABRICO.OF_FP_ID` | 9 estados via parse OF_NOME 100% match (FP=15 Em Uso, 17 Abatido, 11 Não Laminado, 14 A Reparar, 16 Para Abate, 2 Cura, 1 Laminagem, 46 Montagem, 8 QA Final, 20 CNC, 13 Para reparar) | tabela ERP + parse | CONFIRMADO |
| Molde "Em Uso" (operacional hoje) | moldes | `OF_IDS_MLD` JOIN `ORDEMFABRICO` | `OF_FP_ID = 15` (764 moldes) | tabela ERP | CONFIRMADO |
| Molde abatido (sucata) | moldes | `OF_IDS_MLD` JOIN `ORDEMFABRICO` | `OF_FP_ID = 17` (599 moldes) | tabela ERP | CONFIRMADO |
| Molde em reparação | moldes | `OF_IDS_MLD` JOIN `ORDEMFABRICO` | `OF_FP_ID IN (14 A Reparar, 13 Para reparar, 16 Para Abate)` | tabela ERP | CONFIRMADO |
| Plano de laminagem por molde | moldes | view `Z_PrevisaoPlano` | 339 rows cobrindo 4 semanas; `Molde` é FK `OF_IDS_MLD.OF_ID` (100% match) | view ERP | CONFIRMADO |
| Carga semanal de molde (próxima) | moldes | `Z_PrevisaoPlano` | `GROUP BY Molde HAVING COUNT(*) >= N` | view ERP | CONFIRMADO |
| Discriminador classe molde/matriz | moldes (fronteira produto) | `OF_CLASSES_MOLDES_MATRIZES` | TP_ID 82=Moldes / 83=Matrizes / -1=blank | tabela ERP | CONFIRMADO |
| Movimentação histórica de molde | moldes | `MOLDES_MOV` | congelado em 2017-10-31; 83% Ago-2010; MLDU_TP_ID monovalor | tabela ERP | EVITAR |
| Catálogo MOLDES (tabela base) | moldes | `MOLDES` | só catálogo acessórios congelado Fev-Abr 2010 (91 rows); usar `OF_IDS_MLD` em vez | tabela ERP (morta para casco) | EVITAR |
| Flag MOLDE_ACESSORIO em OF | moldes | `ORDEMFABRICO.OF_MOLDE_ACESSORIO` | `= 1` (107 rows; sub-classificação parcial — NÃO é critério "OF-é-molde") | tabela ERP | EVITAR como critério principal |
| Link OF-de-kayak → OF-do-molde | moldes (fronteira produção) | `ORDEMFABRICO.OF_OF_ID_MLD` | cobertura caiu de 96-99% (2018) para 0% (2019-2026); campo abandonado | tabela ERP | EVITAR |
| Tracing defeito → molde culpado | moldes (fronteira qualidade) | `OF_CHECKLIST.OFCH_OFFP_ID_CULPA` → `OF_FP.OFFP_OF_ID` → `OF_OF_ID_MLD` | **REFUTA Q.81 §7** — 0/33.605 defeitos vivos "Molde baço"+"deformações" 2019-2026 têm OF_OF_ID_MLD apontado | inferência | EVITAR (morto desde 2019) |
| Defeito categórico no molde (escala 1-6) | moldes (fronteira qualidade) | `OF_FP.OFFP_PROBS_MOLDE` | int 1-6 (PROBS_CLASSIFICACAO); top val 4=Não grave (7.903), 5=Grave (2.116); cobertura 0.47% | tabela ERP | FRONTEIRA |
| Check de manutenção de molde | moldes (fronteira qualidade) | `OF_CHECKLIST.OFCH_MOLDE_REPARAR` | `= 1` (84.347 rows, 2.8%) | tabela ERP | FRONTEIRA |
| Empregados ligados a moldes | moldes (fronteira workforce) | `OF_MLD_EMPREGADOS` | 159 rows (subset RH) | view ERP | FRONTEIRA |
| Dicionário componentes (poços/tamanhos/modelos) | moldes (fronteira produto) | `MOLDES_CONST_MOD_TAM_NP` | 1.070 construções + 319 modelos + 18 tamanhos + 7 poços + 2 tipos | view ERP | FRONTEIRA |
| Catálogo produtos-construção | moldes (fronteira produto) | view `OF_PRODUTOS_MLD` | 2.111 rows; todos `P_TP_ID = 84` | view ERP | FRONTEIRA |
| Data de criação de molde | moldes | `OF_IDS_MLD` JOIN `ORDEMFABRICO.OF_DATAINICIO` | 86% NULL ou 1900-01-01; **NÃO fiável para idade-de-parque** | tabela ERP | DECISÃO NEGÓCIO PENDENTE |
| Reactivação do tracing molde-defeito | moldes | `ORDEMFABRICO.OF_OF_ID_MLD` | requer patch no front-end Laravel para tornar campo obrigatório | — | DECISÃO NEGÓCIO PENDENTE |
| Critério canónico "molde activo" | moldes | `OF_IDS_MLD` | 3 hipóteses: `FP_ID=15` estrito (764) / `IN(15,14,16)` (803) / `FP_ID<35` (850) | inferência | DECISÃO NEGÓCIO PENDENTE |

---

## Domínio: WORKFORCE / RH (Q.82)

Investigação completa em `agent_docs/q82_workforce_catalogo.md`.

### Vivos / utilizáveis em rotas (16)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Colaborador NELO (definição canónica) | workforce | `ENTIDADE` JOIN `ENTIDADE_TIPO` | `E_ENT_ID IN (SELECT ENT_ID FROM ENTIDADE_TIPO WHERE ENT_ENT_ID=19)` (sub-tipos de "Empregado") | tabela ERP (igual a `FuncionariosActivos`, 158 rows) | CONFIRMADO |
| Colaborador activo | workforce | `ENTIDADE` | `E_ACTIVO = 1` AND filtro acima | tabela ERP | CONFIRMADO |
| View oficial de colaboradores activos | workforce | view `FuncionariosActivos` | 158 rows (`E_ID, E_NOME, E_EMAIL`) | view ERP | CONFIRMADO |
| Especialização do colaborador | workforce | `ENTIDADE.E_ENT_ID` → `ENTIDADE_TIPO.ENT_NOME` | 36 sub-tipos de `ENT_ENT_ID=19` (Laminador, Pintor, Acabador, etc) | tabela ERP | CONFIRMADO |
| Fase canónica do cargo | workforce | `ENTIDADE_TIPO.ENT_FP_ID` | cada sub-tipo de 19 tem fase principal (Laminador→1, Pintor→18, Desmoldador→6) | tabela ERP | CONFIRMADO |
| Tipo de evento RH | workforce | `ENT_MOV_TIPO` | 15 valores (13 vivos): Horas Extra/Justificada/Injustificada/Baixa SS/Baixa Seguro/Férias/Banco H. (A dever/A haver)/Horas Ajudante/Horas perdidas | tabela ERP | CONFIRMADO |
| Evento RH (tabela facto) | workforce | `ENT_MOV` | 166K rows 2009→2026, ~150-200 ops/ano | tabela ERP | CONFIRMADO |
| Horas de um evento RH | workforce | `ENT_MOV` (calculado) | `DATEDIFF(MINUTE, MOVENT_DATA_I, MOVENT_DATA_F) / 60.0` — **MOVENT_HORAS é sempre 0, NÃO usar** | inferência (8.8M horas totais) | CONFIRMADO |
| Operador × fase de OF (facto) | workforce | `OFFP_EQ` | `(OFFPEQ_OFFP_ID → OFFP_ID, OFFPEQ_E_ID → E_ID, OFFPEQ_CHEFE)` 1.42M rows, 330 ops históricos | tabela ERP | CONFIRMADO |
| Turno | workforce | `TURNO` | 3 valores (1=Manhã, 2=Tarde, 3=Noite) | tabela ERP | CONFIRMADO |
| Turno de uma fase de OF | workforce (fronteira produção) | `OF_FP.OFFP_TURN_ID` → `TURNO.TURN_ID` | **resolve gap Q.79 §6**; cobertura 2.6% (68.7K/2.64M); útil só para laminagem | tabela ERP | CONFIRMADO |
| Equipa formal | workforce | `EQUIPA` | 17 rows: 14 dissolvidas 2018-09-20; 3 activas (Zebra, HD, O Miguel) | tabela ERP | CONFIRMADO |
| Operador × equipa | workforce | `ENTIDADE_EQUIPA` | `(EEQ_E_ID, EEQ_EQ_ID, EEQ_DATA_ENTRADA, EEQ_DATA_SAIDA, EEQ_CHEFE)` | tabela ERP | CONFIRMADO |
| Calendário fabril (dias úteis) | workforce | `DIAS_TRABALHO` | 15.6K rows 2016→2078 | tabela ERP | CONFIRMADO |
| Evento "Horas Ajudante" → OF | workforce | `ENT_MOV` | `MOVENT_MET_ID = 13 AND MOVENT_OF_ID IS NOT NULL` (7.230 rows, 4.270 OFs distintas) | tabela ERP | CONFIRMADO |
| Vencimento médio agregado por fase (anonimizado) | workforce | view `Funcionarios_vencimento_medio` | 32 rows `(fpid, fpnome, Emps, media_hora)` — **agregado, eticamente OK** | view ERP | CONFIRMADO |
| Documento RH (formação/EPI/segurança) | workforce | `RH_DOC` JOIN `RH_TIPO_DOC` | 6 tipos; 19 docs | tabela ERP | CONFIRMADO |

### HIPÓTESE FORTE (2)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Operador-principal-da-fase (vs ajudante) | workforce | `OFFP_EQ.OFFPEQ_CHEFE` | `=1` (87% dos rows, 1.24M True / 178K False) | inferência | HIPÓTESE FORTE |
| Cálculo de horas RH canónico | workforce | `ENT_MOV` derivado | `SUM(DATEDIFF(MINUTE, DATA_I, DATA_F)/60.0)` — confirmar se desconta almoço/feriados | inferência | HIPÓTESE FORTE |

### DECISÃO NEGÓCIO PENDENTE — ÉTICA (7)

| conceito | domínio | tabela.coluna | bloqueio | grau |
|---|---|---|---|---|
| Defeitos por operador (ranking individual) | workforce | view `RetornosFuncionario` | **AVALIAÇÃO INDIVIDUAL** — view 88.7K rows existe; agregar por Fase, NUNCA por Funcionario sem aprovação Luís+RH+jurídico | DECISÃO NEGÓCIO PENDENTE |
| Top operadores por horas extra (individual) | workforce | `ENT_MOV WHERE MET=1 GROUP BY MOVENT_E_ID` | avaliação individual | DECISÃO NEGÓCIO PENDENTE |
| Faltas por operador (individual) | workforce | `ENT_MOV WHERE MET IN (4,5,6,7,8,9) GROUP BY MOVENT_E_ID` | exposição de absentismo individual | DECISÃO NEGÓCIO PENDENTE |
| Salário/custo-hora individual | workforce | `ENTIDADE.E_CUSTOHORA` / `E_HORAHOMEM` / `E_TAXA_IRS` | dados pessoais sensíveis (134/158 colaboradores) | DECISÃO NEGÓCIO PENDENTE |
| Responsável por retorno estacionado (nome exposto) | workforce | view `of_Retornos_Estacionados.Responsavel` | nome em texto; usar com máscara? | DECISÃO NEGÓCIO PENDENTE |
| Produtividade individual | workforce | `ENTIDADE.E_PRODUTIVIDADE` (39/158) + `OFFP_EQ` | avaliação individual | DECISÃO NEGÓCIO PENDENTE |
| Semântica exacta de OFFPEQ_CHEFE | workforce | `OFFP_EQ.OFFPEQ_CHEFE` | 87% True — operador-principal vs ajudante? confirmar | DECISÃO NEGÓCIO PENDENTE |

### FRONTEIRA (5)

| conceito | domínio | tabela.coluna | razão | fonte | grau |
|---|---|---|---|---|---|
| Cliente / particular / fornecedor (master ENTIDADE) | comercial / supply | `ENTIDADE.E_ENT_ID IN (2, 17, 18, 33, 42, 48)` | 8.000+ rows fora do scope WORKFORCE | tabela ERP | FRONTEIRA |
| Empresas de transporte | logística | `TransporteOperador` | 15 rows (MAERSK, MSC, Trackimo) — não é workforce humano | tabela ERP | FRONTEIRA |
| Empregados ligados a moldes | moldes | view `OF_MLD_EMPREGADOS` | 159 rows | view ERP | FRONTEIRA |
| Atleta NELO patrocinado | comercial | `ENTIDADE.E_NELO=1` (44 rows) | **NÃO é colaborador** — 43/44 são `E_ENT_ID=2 Cliente` (atletas patrocinados); **REFUTA hipótese "E_NELO=trabalhador"** | tabela ERP | FRONTEIRA |
| Defeito por origem por fase | qualidade | view `RetornosFuncionario GROUP BY Fase` | alternativa por fase do `OFCH_OFFP_ID_CULPA` da Q.81; ética bloqueia uso individual | view ERP | FRONTEIRA |

### EVITAR (9)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Sistema de pontos/prémios | workforce | `ENTIDADE_PONTOS` (866) + `PONTOS` (14 lookup) | morto desde 2015; piloto não escalou | EVITAR |
| Catálogo de formações | workforce | `RH_FORMACAO` (1 row dummy 1900-01-01) | schema-cemitério | EVITAR |
| Problemas/irregularidades RH | workforce | `RH_PROBLEMA` (0 rows) | schema-cemitério | EVITAR |
| Caixa de ideias | workforce | `IDEIA_COLAB` (209) | uso irregular 2010-2024 | EVITAR |
| Campo MOVENT_HORAS | workforce | `ENT_MOV.MOVENT_HORAS` | sempre 0 — usar DATEDIFF | EVITAR |
| Campo MOVENT_ANO / MOVENT_MES | workforce | `ENT_MOV.MOVENT_ANO/MES` | 1 row total — usar `YEAR(MOVENT_DATA_I)` | EVITAR |
| Filtro E_NELO=1 para "colaborador" | workforce | `ENTIDADE.E_NELO=1` | é atleta patrocinado; 43/44 são Cliente | EVITAR |
| Equipas históricas 1-14 | workforce | `EQUIPA EQ_DATA_ELIMINADO IS NOT NULL` | 14 dissolvidas 2018-09-20 | EVITAR |

---

## Domínio: COMERCIAL / FINANCEIRO (Q.82)

Investigação completa em `agent_docs/q82_comercial_catalogo.md`.

### Vivos / utilizáveis em rotas (19)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Facturação oficial NELO | comercial | `ENTIDADE_PHC_FACT.EPHCF_FACTURADO` | `GROUP BY EPHCF_ANO/MES/DIA`; 100K rows 2009-2026 = €125M; espelho PHC externo | tabela ERP | CONFIRMADO |
| Liga facturação a entidade (cliente) | comercial | `ENTIDADE_PHC_FACT.EPHCF_EPHC_ID` JOIN `ENTIDADE_PHC.EPHC_PHC_ID` | JOIN via `EPHC_PHC_ID` (NÃO `EPHC_ID`) → `ENTIDADE.E_ID` | tabela ERP | CONFIRMADO |
| Facturação por disciplina-pai | comercial | `ENTIDADE_PHC_FACT.EPHCF_TP_ID_DISCIP` JOIN `PRODUTO_TIPO` | TP_ID 149=Canoe Sprint, 151=Ocean, 241=Marathon, 242=Fitness (60K NULL) | tabela ERP | CONFIRMADO |
| Facturação por categoria fina (modelo) | comercial | `ENTIDADE_PHC_FACT.EPHCF_TP_ID` JOIN `PRODUTO_TIPO` | TP_ID 6=Canoe Sprint Ep. (58% facturação!), 243=Ocean, 244=Marathon, 246=Fitness Ep. | tabela ERP | CONFIRMADO |
| Estado de encomenda wholesale | comercial | `ENCOMENDA.ENC_EE_ID` JOIN `ENCOMENDA_ESTADO` | 1=Recebida / 2=Em Curso / 3=Fechada | tabela ERP | CONFIRMADO |
| Estado encomenda OF-agente | comercial | `EstadoOFAgente` | 1=Pendente / 2=Em processamento / 3=Entregue / 4=Reparação | tabela ERP | CONFIRMADO |
| Estado workflow web agentes | comercial | `AgenteEncomendaEstado` | 1=Saved / 2=Submitted / 3=Sent | tabela ERP | CONFIRMADO |
| Categorização de entidade (master) | comercial | `ENTIDADE.E_ENT_ID` JOIN `ENTIDADE_TIPO` | filtrar `IN (2 Cliente, 18 Fornecedor, 17 Proprietario, 42/48 Atletas, 33/44 Douro Academy, 45 Correio, 47 Potencial)` | tabela ERP | CONFIRMADO |
| Hierarquia tipos entidade | comercial | `ENTIDADE_TIPO.ENT_ENT_ID` | sub-tipos: Douro Academy/Eliminados são filhos de Cliente; ~30 Empregado-sub é FRONTEIRA workforce | tabela ERP | CONFIRMADO |
| Cliente NELO | comercial | `ENTIDADE.E_ENT_ID` | `= 2` (1.349 rows) | tabela ERP | CONFIRMADO |
| Fornecedor | comercial | `ENTIDADE.E_ENT_ID` | `= 18` (804 rows) | tabela ERP | CONFIRMADO |
| Facturação por agente comercial (trimestral) | comercial | `vAgente_Faturacao` | 46 agentes, 2009-2026, €65M (52% PHC total); sistema independente | view ERP | CONFIRMADO |
| Facturação agente YTD | comercial | `vAgente_Facturacao_Epoca_Actual` | 33 rows; agentes activos época corrente | view ERP | CONFIRMADO |
| Liga agente a contagem facturas | comercial | `AGENTE_FATURA` | 9.720 rows, AFT_E_ID + AFT_F_NO + AFT_CONTABILIZAR | tabela ERP | CONFIRMADO |
| Pedido de compra interna/externa | comercial | `PEDIDOS` | 116K rows 2017-2026; `PED_APROVADO` único flag fiável (9.6% True); `PED_E_ID` é destinatário | tabela ERP | CONFIRMADO |
| Pedido aprovado | comercial | `PEDIDOS.PED_APROVADO` | `= 1` (11.131 rows) | tabela ERP | CONFIRMADO |
| Pedido ligado a OF | comercial | `PEDIDOS.PED_OF_ID` | `IS NOT NULL` (28K, 24%) | tabela ERP | CONFIRMADO |
| Custo transporte expedição (despesa) | comercial | `CORREIO_FACT.CORRF_VALOR_SEM_IVA` | top: Fema €152K, FedEx Rangel €48K, DHL €30K; vivo 2020-2025 | tabela ERP | CONFIRMADO |
| Preço de venda da OF | comercial | `ORDEMFABRICO.OF_PRECOVENDA` | `> 0` (234K rows, ~53% cobertura pós-2019; €604 avg); cobertura caiu de 83→43-57% pós-2019 | tabela ERP | CONFIRMADO |
| Preço de custo da OF | comercial | `ORDEMFABRICO.OF_PRECOCUSTO` | `> 0` (407K rows, 92%; €200 avg); ~700 valores negativos = correcções contabilísticas | tabela ERP | CONFIRMADO |
| Preço design pintura personalizada | comercial | `vPSD.P_PRECOVENDA` JOIN `vPSD.P_MACRO` | 6 níveis: Premade €80 / Basic €135 / Brilliant €200 / Expert €370 | view ERP | CONFIRMADO |

### HIPÓTESE FORTE (1)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Época desportiva (Out-Set) | comercial | `ENTIDADE_PHC_FACT.EPHCF_EPOCA` | ~27% das facts de Out-Dez vão para época seguinte | inferência | HIPÓTESE FORTE |

### FRONTEIRA (2)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Tipo/Disciplina de produto | comercial (fronteira produção) | `PRODUTO_TIPO` | 422+ valores; hierarquia Kayak (1) → Ocean Racing (251) → Ocean (243) | FRONTEIRA |
| Sub-tipos de Empregado (ENT_ID 19+filhos) | comercial (fronteira workforce) | `ENTIDADE_TIPO` | ~30 sub-tipos cobertos por workforce | FRONTEIRA |

### EVITAR (14)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Pagamento da OF | comercial | `ORDEMFABRICO.OF_PAGO` / `OF_DATAPAGAMENTO` | morto desde 2011; cobertura 71% (2009) → <1% (2018+); pagamentos migraram para PHC sem ligação OF | EVITAR |
| Flag pagamento pedido | comercial | `PEDIDOS.PED_PAGO` / `PED_PAGAR` | 0.5% True em 116K | EVITAR |
| Data pagamento pedido | comercial | `PEDIDOS.PED_PAGODATA` | 0.5% cobertura | EVITAR |
| Tabela FATURA (OCR facturas recebidas) | comercial | `FATURA` | módulo piloto 2025+; `entidade_id` 100% NULL; só RECEBIDAS de fornecedor | EVITAR |
| View saldo cliente | comercial | `vSaldoCliente` | 284 rows mas 89% saldo NULL; view parcial em construção | EVITAR |
| Sistema encomenda web agentes | comercial | `AgenteEncomenda` / `AgenteEncomendaProduto` | 14+59 rows totais; último 2013-08; abandonado | EVITAR |
| Loja física PT | comercial | `VendaLoja` / `VendaLojaProduto` | 223+511 rows 2014-2019; abandonada (Magento substituiu) | EVITAR |
| Revenda kayaks usados (YourNelo) | comercial | `OF_VENDA` | 22 rows; nome enganador (é segunda-mão); todos FP_ID=58 | EVITAR (excepto perguntas YourNelo) |
| Tracking encomenda | comercial | `Encomenda_trk` | 7 rows dummy 2017 | EVITAR |
| Pedido provisório rascunho | comercial | `ENT_ENT_PEDIDO_PROVISORIO` | 3 rows JSON dev/teste | EVITAR |
| Notícias agentes | comercial | `noticias_agentes` | 9 rows 2014 | EVITAR |
| Publicidade agentes | comercial | `PublicidadeAgentes` | 1 row banner | EVITAR |
| **Magento loja online** | comercial | `shop_order_item` | **CAIXA-PRETA** — linked server Magento, `nikufra` sem permissão `Ad hoc Distributed Queries`; **confirmado de novo Q.82** | EVITAR |
| Linha de produção "Linha 0" | comercial (fronteira produção) | `OF_LINHA_PROD.linha` | 83.6% (370K) em "Linha 0" — default "não atribuído", não linha real | EVITAR (filtrar `!= 'Linha 0'`) |

### DECISÃO NEGÓCIO PENDENTE (8)

| conceito | domínio | tabela.coluna | bloqueio | grau |
|---|---|---|---|---|
| Diferença Proprietário (5.897) vs Cliente (1.349) | comercial | `ENTIDADE.E_ENT_ID` | Proprietário é maior bucket; hipótese: ex-donos via OF_VENDA. Contam para top de facturação? | DECISÃO NEGÓCIO PENDENTE |
| Sistema oficial de facturação venda | comercial | (PHC vs FATURA?) | PHC é único vivo para receita; FATURA é OCR de RECEBIDAS | DECISÃO NEGÓCIO PENDENTE |
| Pedidos internos "Fábrica" (E_ID=19747) | comercial | `PEDIDOS WHERE PED_E_ID=19747` | 27.980 (24%) com destinatário "Fábrica" marcada como Cliente — requisição interna ou venda? | DECISÃO NEGÓCIO PENDENTE |
| OF_PAGO post-mortem | comercial | `ORDEMFABRICO.OF_PAGO` | morto desde 2011 sem substituto OF→pagamento | DECISÃO NEGÓCIO PENDENTE |
| EPHCF_EPOCA semântica | comercial | `ENTIDADE_PHC_FACT.EPHCF_EPOCA` | sugere "ano desportivo Out-Set" mas não confirmado | DECISÃO NEGÓCIO PENDENTE |
| Facturas sem entidade (€14.8M) | comercial | `ENTIDADE_PHC_FACT WHERE EPHCF_EPHC_ID IS NULL` | 14.416 facts (14%); provavelmente vendas balcão/B2C | DECISÃO NEGÓCIO PENDENTE |
| `VendaLojaProduto.tipo` | comercial | `VendaLojaProduto.tipo` | distribuição não bate com PRODUTO_TIPO.TP_ID; baixa prioridade | DECISÃO NEGÓCIO PENDENTE |
| `Encomenda_trk.codOperador`/`codEstado` | comercial | `Encomenda_trk` | sem lookups; tabela 7 rows residual | DECISÃO NEGÓCIO PENDENTE |

---

## Domínio: LOGÍSTICA / TRANSPORTES (Q.82)

Investigação completa em `agent_docs/q82_logistica_catalogo.md`.

### Lookups vivas (7)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Tipo de transporte (hierárquica) | logistica | `TRANSP_TIPO` | 58 valores; root via `TRTP_TRTP_ID`. Roots: 10=Exportação / 11=Importação / 19=Deslocações / 53=CO2 | tabela ERP | CONFIRMADO |
| Destino aduaneiro | logistica | `TRANSP_DESTINO` | 4 valores: 5=Nacional / 6=U.E. / 7=Outros / 8=Todos | tabela ERP | CONFIRMADO |
| Tipo de despesa de viagem | logistica (fronteira financeiro) | `TRANSP_DESP_TIPO` | 20 valores (Hotel/Voos/Combustível/Nelo Truck/Vistos/Portagens) | tabela ERP | FRONTEIRA |
| Classificação de culpa em alteração de data | logistica | `TRANSP_DATAS_CLASSIFICACAO` | 3 valores: 1=Culpa Nelo / 2=Culpa Transportador / 3=Culpa Cliente | tabela ERP | CONFIRMADO |
| Operador de transporte marítimo/aéreo | logistica | `TransporteOperador` | 15 valores (Maersk, MSC, CMA-CGM, Cosco, Hapag-Lloyd, YangMing, Evergreen, Trackimo, Vodafone) | tabela ERP | CONFIRMADO |
| Porto de destino global | logistica | `TransportePorto` | 570 portos com latitude/longitude/countryCode | tabela ERP | CONFIRMADO |
| País destino + coef. CO2 | logistica | `PAISES` | 202 países com `PAISES_COEFICIENTE_CO2` | tabela ERP | CONFIRMADO |

### Operacionais vivas (utilizáveis em rotas)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Transporte (registo mestre) | logistica | `TRANSPORTE` | PK=TR_ID; 11.380 rows vivo 2001→2026 | tabela ERP | CONFIRMADO |
| Data canónica do transporte | logistica | `TRANSPORTE.TR_DATA` | 99.9% cobertura | tabela ERP | CONFIRMADO |
| Junção transporte ↔ OFs (N:M) | logistica | `TRANSP_OF` | PK composta (TROF_TR_ID, TROF_OF_ID); 93K rows / 84K OFs / 9.816 transportes 2019→2026 | tabela ERP | CONFIRMADO |
| OF expedida | logistica (fronteira produção) | `TRANSP_OF` JOIN `TRANSPORTE` | `WHERE TROF_ENVIADO = 1 AND TR_DATA IS NOT NULL` — bate 99% com `ORDEMFABRICO.OF_FP_ID = 12` (Entregue) | inferência por evidência (5.874 OFs 2024 / 5.826 em fase 12) | FRONTEIRA |
| Transporte próprio (Nelo Truck) vs externo | logistica | `TRANSPORTE.TR_TRANSPORTE_NOSSO` | **98.5% False** (apenas 176 próprios em 17 anos) | tabela ERP | CONFIRMADO |
| Documento aduaneiro do transporte | logistica | `TRANSP_DOCS` | 46.918 rows; tipos via `TRANSP_DOCS_STD` (CMR, BL, AWB, DU, Euro 1, Packing List, Seguro, Fumigação) | tabela ERP | CONFIRMADO |
| Documento aduaneiro tratado vs pendente | logistica | `TRANSP_DOCS.TRDOC_TRATADO` | 79% True (37.245/46.918) | tabela ERP | CONFIRMADO |
| Histórico de alterações de datas | logistica | `TRANSP_DATAS` | 3.027 rows; data antiga + nova + culpa via TRDT_TRDTCL_ID | tabela ERP | CONFIRMADO |
| Atraso por culpa cliente | logistica | `TRANSP_DATAS WHERE TRDT_TRDTCL_ID = 3` | 2.110 (70% dos atrasos) | tabela ERP | CONFIRMADO |
| Atraso por culpa Nelo | logistica | `TRANSP_DATAS WHERE TRDT_TRDTCL_ID = 1` | 791 (26%) | tabela ERP | CONFIRMADO |
| Atraso por culpa transportador | logistica | `TRANSP_DATAS WHERE TRDT_TRDTCL_ID = 2` | 126 (4%) | tabela ERP | CONFIRMADO |
| Despesa de viagem (equipa) | logistica (fronteira financeiro) | `TRANSP_DESP` | 4.021 rows; Voos €621K + Hotel €340K + Nelo Truck 1 €257K — **NÃO é custo de transporte de produto**, é despesas de viagens de equipa atribuídas a TRTP_ID=19 | tabela ERP | FRONTEIRA |
| Dimensões 3D da OF | logistica | `TRANSP_OF.TROF_COMPRIMENTO/TROF_LARGURA/TROF_ALTURA` | float; cobertura desigual | tabela ERP | CONFIRMADO |
| OF leva peças (não kayak completo) | logistica | `TRANSP_OF.TROF_LEVA_PECAS` | bit; **0.3% True** (312/93K) | tabela ERP | CONFIRMADO |
| Tipos hierárquica TRANSP_TIPO root=10 Exportação | logistica | `TRANSP_TIPO` filtro root=10 | 90% dos transportes (10.304/11.380); excluir root=19 Deslocações | inferência | CONFIRMADO |

### Tracking GPS — quase tudo MORTO

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Coordenadas GPS actuais do transporte | logistica | `TRANSPORTE.TR_LATITUDE/TR_LONGITUDE` | max(TR_COORD_ULT_UPD) = 2023-02-13; apenas 411 rows com coord set | EVITAR |
| Tracking GPS Trackimo | logistica | `Trackimo_DeviceLocation` | max = 2022-08-08; 5.173 rows mortos | EVITAR |
| Localização instantânea via parceiros | logistica | `TransporteLocalizacao` | max = 2023-01-11; 39.122 rows mortos | EVITAR |
| Percurso registado | logistica | `TransportePercurso` | max = 2023-01-19 | EVITAR |
| View tracking | logistica | `vTrackingTransporte` | max = 2023-02-13; só 1 row em 2023 | EVITAR |
| Histórico percurso (excepção Nelo Asia) | logistica | `TransportePercursoHistorico` | 40.659 rows vivos até hoje mas **apenas para 1 encomenda** (TR_ID=24436, operador YangMing) | EVITAR para regra geral |
| Verificação de transporte | logistica | `TRANSPORTE_VERIFICACAO` | 0 rows — schema-cemitério | EVITAR |
| Tracking root CO2 Deslocações | logistica | `TRANSP_TIPO` root=53 | 0 transportes usam — piloto sustentabilidade não decolou | EVITAR |
| Vista OF+Transporte denormalizada | logistica | `vOF_Transporte` | 67 cols, 443K rows mas **cobertura TR_ID: 0.7%** — view legada não actualizada | EVITAR (usar JOIN directa) |

### Cemitério de produção (REFUTAÇÃO de Q.79 §6)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Data de transporte na OF | produção (fronteira logística) | `ORDEMFABRICO.OF_DATATRANSPORTE` | **MORTO desde 2009-03-27**. Q.79 §6 cita-o como utilizável; **refutar**. Para "OF expedida" usar `TRANSP_OF` + `TR_DATA` | EVITAR (REFUTAÇÃO Q.79) |
| Data de entrega da OF | produção (fronteira logística) | `ORDEMFABRICO.OF_DATAENTREGA` | Cobertura 1% (5.545/443K); pico 2022 (4.214) depois quase zero | EVITAR |

### DECISÃO NEGÓCIO PENDENTE (5)

| conceito | domínio | tabela.coluna | bloqueio | grau |
|---|---|---|---|---|
| Estado de workflow do transporte | logistica | `TRANSPORTE.TR_ESTADO_COD` | int 85% NULL; valores 2/3/4 sem lookup | DECISÃO NEGÓCIO PENDENTE |
| Categorias de valor TRANSP_VAL (2-8) | logistica | `TRANSP_VAL.TRVAL_VAL_ID` | 7 categorias sempre presentes (médias €450/€474/€63/€5/€3/€21/€1) sem lookup | DECISÃO NEGÓCIO PENDENTE |
| "OF expedida" canónica | logistica (fronteira produção) | (4 candidatas) | `TR_DATA` vs `TROF_DATA_CRIACAO` vs `TR_DATA_ENTREGA` (15%) vs `TROF_DATA_CONFIRMACAO` (0.7%) | DECISÃO NEGÓCIO PENDENTE |
| TRANSP_DESP cabe em logística? | logistica (fronteira financeiro) | `TRANSP_DESP` | despesas de viagens de equipa, não transporte de kayak | DECISÃO NEGÓCIO PENDENTE |
| Tracking GPS recuperar ou desligar? | logistica | (todos sistemas tracking) | morto desde 2023 excepto 1 container | DECISÃO NEGÓCIO PENDENTE |

---

## Domínio: IoT / ENERGIA / CURA (Q.82)

Investigação completa em `agent_docs/q82_iot_catalogo.md`.

### Lookups vivas (5)

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Tipo de sensor (driver técnico) | iot | `IOT_SENSOR_TIPO` | 7 valores (Shelly 3EM/Raspberry Temp/Weather API/Shelly Pro 3Em/Shelly Pro EM/Raspberry Vacuum/Solar Log) | tabela ERP | CONFIRMADO |
| Catálogo de sensores | iot | `IOT_SENSOR` | 32 sensores nominais; `SENSOR_ACTIVO=1 AND SENSOR_LAST_SEEN >= '2026-05-01'` filtra 14 vivos hoje | tabela ERP | CONFIRMADO |
| Catálogo de sondas termo-higrómetro | iot | `TH_SONDA` | 5 sondas físicas (Fábrica Norte/Estufa Laminagem 60/30/Exterior/Estufa Pintura Acabamento); TH parou de receber dados em 2025-02-26 | tabela ERP | CONFIRMADO |
| Regras de alarme por sensor | iot | `IOT_SENSOR_ALARM` | 14 thresholds (FIELD + MIN/MAX + horário + dias). 6 activos, 8 inactivos. Regra-tipo: Estufa 30 ≥45°C de madrugada | tabela ERP | CONFIRMADO |
| Tipo de alarme de workflow (NÃO sensor) | iot/produção | `ALARM_TIPO` | 6 valores (Entrou/Saiu/Verifica Entrega/Stocks/Facturas/Fases Produção). TALARM_ID=6 nunca usado em 110K rows | tabela ERP | CONFIRMADO |

### Vivos / utilizáveis em rotas

| conceito | domínio | tabela.coluna | filtro/regra | fonte | grau |
|---|---|---|---|---|---|
| Série temporal IoT (energia + ambiental + vácuo) | iot | `IOT_SENSOR_DATA` | 3.725.328 rows, vivo desde 2025-02-03 hoje (5-min); SD_POWER_1..3 / SD_CURRENT_1..3 / SD_TEMPERATURE / SD_HUM / SD_PRESSURE | tabela ERP | CONFIRMADO |
| Energia eléctrica (consumo por quadro) | iot/energia | `IOT_SENSOR_DATA` + `IOT_SENSOR` | sensores tipo IN (1,4,5) com SENSOR_POWERMETER=1; quadros vivos: AVAC, Quadro Nave Sul/Norte, CNC Azul/Vermelha, Compressores Vácuo, Quadro pintura, Estufa peças, Calandra | tabela ERP + amostragem | CONFIRMADO |
| Temperatura/humidade ambiental (estufas) | iot/ambiental | `IOT_SENSOR_DATA` | sensores 12 (Estufa 60), 14 (Estufa 30), 17 (Estufa Peças), 15 (Exterior) | tabela ERP (Estufa 60 a 71°C avg) | CONFIRMADO |
| Pressão de vácuo (infusão) | iot/vacuo | `IOT_SENSOR_DATA` | sensores tipo 6 (Raspberry Vacuum); **12 dos 13 inactivos** — só sensor 27 (Pressão Vacuo 1) com regra activa | tabela ERP — 12/13 inactivos | HIPÓTESE FORTE |
| **Validação empírica dos 16 gaps de cura** | iot/produção (fronteira) | `IOT_SENSOR_DATA` JOIN `OF_FP` por timestamp | método: filtrar OF_FP numa transição cura e cruzar com IoT da estufa durante a janela | inferência (OF 141973: gap 15.77h, Estufa 60 a 71°C avg bate `NELO_CURING_GAPS_SEED` LAMINAGEM→CURA=15h) | CONFIRMADO para LAMINAGEM→CURA |
| Workflow OF entrou/saiu fase | iot/produção (fronteira) | `ALARM` | `ALARM_TALARM_ID IN (1=Entrou, 2=Saiu, 3=Verifica Entrega)`; `ALARM_OF_ID` set em 91%; vivo 2008-2026 | tabela ERP — **workflow, NÃO sensor físico** | CONFIRMADO |
| Último alarme físico disparado | iot | `IOT_SENSOR_ALARM.SA_LAST_ALARM` | timestamp Unix; **só estado actual, sem histórico** | tabela ERP | CONFIRMADO |

### EVITAR (9)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Temperatura/humidade por fase OF | iot/produção | `OF_FP.OFFP_TEMPERATURA`, `OFFP_HUMIDADE` | placeholder vazio: 99.99% das 2.638.277 rows são 0.0; **Q.79 classificou como CONFIRMADO mas é mentira-de-schema** | EVITAR |
| Sensor de vácuo associado a OF | iot/produção | `ORDEMFABRICO.OF_SENSOR_ID_VACUO` | 2 valores em 443.334 rows (0.00045%) | EVITAR |
| Tabela TH (termo-higrómetro legado) | iot | `TH` | **substituída por `IOT_SENSOR_DATA` em 2025-02-26**; última row 2025-02-26 13:00 | EVITAR (para perguntas pós-2025-02) |
| ALARM_TIPO_ENTIDADE | iot | `ALARM_TIPO_ENTIDADE` | 0 rows — schema nunca usado | EVITAR |
| Alarme tipo 6 "Fases Produção" | iot | `ALARM` com `ALARM_TALARM_ID = 6` | catalogado mas 0 rows | EVITAR |
| Solar Log medições | iot/energia | `IOT_SENSOR_DATA` com `SD_SENSOR_ID = 40` | declara mas 0 rows; sensores 50/51 (Energia Produção/Consumo) também pararam 2025-11 | EVITAR (driver Solar não funcional) |
| Coluna TH_FASE | iot | `TH.TH_FASE` | só 2 valores observados; tabela TH morta | EVITAR |
| Report_Table_20171114 | iot | `Report_Table_20171114` | relatório one-off de 2017 | EVITAR |

### FRONTEIRA (1)

| conceito | domínio | tabela.coluna | razão | grau |
|---|---|---|---|---|
| Tabelas SensoresTeste* (8 tabelas) | iot/atleta | `SensoresTeste/SensoresTesteSerie/SensoresTesteSerieValores/...` | **fora-de-scope IoT factory** — são testes com atletas (pitch/roll/heading); possível domínio futuro "performance de barcos" | FRONTEIRA |

### DECISÃO NEGÓCIO PENDENTE (4)

| conceito | domínio | tabela.coluna | bloqueio | grau |
|---|---|---|---|---|
| Status do parque de vácuo | iot/vacuo | sensores 21,27-38 | 12/13 inactivos. Foram fisicamente removidos ou só desligados? | DECISÃO NEGÓCIO PENDENTE |
| OFFP_TEMPERATURA/HUMIDADE foi protocolo manual abandonado? | iot/produção | `OF_FP.OFFP_TEMPERATURA/HUMIDADE` | placeholder vazio — protocolo manual operador nunca preencheu, ou foi sempre auto-0.0? | DECISÃO NEGÓCIO PENDENTE |
| Protocolo de cura por modelo | iot/produção (fronteira) | `NELO_CURING_GAPS_SEED` em `src/plan/cpo/state.py` | seed assume 15h LAMINAGEM→CURA genérico; é igual para K1 Surf Ski e Sea Vanquish? | DECISÃO NEGÓCIO PENDENTE |
| Logging persistente de alarmes IoT | iot | (não existe) | `IOT_SENSOR_ALARM.SA_LAST_ALARM` só guarda último timestamp; não há histórico | DECISÃO NEGÓCIO PENDENTE |

---

## Convenções

- **CONFIRMADO**: vocabulário tem tabela-lookup autoritativa OU evidência inequívoca em
  dados reais (cross-check com múltiplas amostras). Pode-se construir rota agora.
- **HIPÓTESE FORTE**: evidência boa em dados mas sem lookup formal. Pode-se construir
  rota com nota explícita "interpretação interna NELO".
- **DECISÃO NEGÓCIO PENDENTE**: pergunta que só humano da NELO decide (a BD não tem a
  resposta). Bloqueia rotas dependentes até reunião com analista.
- **FRONTEIRA**: conceito atravessa domínios (ex.: MOLDES_TIPO é catalogado em
  MATERIAIS mas o domínio MOLDES vai cobrir o uso). Não decidir sozinho.
- **EVITAR**: schema-cemitério, piloto parado, ou flag não-fiável. Nunca usar em rotas.

---

*Mantido pela campanha LLM→SQL accuracy. 8 domínios mapeados: MATERIAIS (Q.78),
PRODUÇÃO (Q.79), QUALIDADE (Q.81), MOLDES (Q.82), WORKFORCE (Q.82), COMERCIAL (Q.82),
LOGÍSTICA (Q.82), IoT (Q.82). Próxima fase: rotas determinísticas extra ou Cube
semântico — ver relatório consolidado Q.82.*
