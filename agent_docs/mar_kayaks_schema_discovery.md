# MAR-KAYAKS schema discovery

> Generated 2026-05-12 18:04 via `scripts/discover_mar_kayaks.py`.
> Server: `fabrica.nelo.eu:1039` · DB: `MAR-KAYAKS` · 284 base tables in `dbo`.
> Filtered 127 tables across 6 production-relevant buckets.

## Índice

- [Ordens de fabrico](#ordens-de-fabrico) — 23 tabelas
- [Artigos / Produtos / BOM](#artigos--produtos--bom) — 25 tabelas
- [Operações, fases e planeamento](#operaes-fases-e-planeamento) — 13 tabelas
- [Recursos (entidades, equipas, moldes, RH)](#recursos-entidades-equipas-moldes-rh) — 27 tabelas
- [Qualidade, problemas, inspecções](#qualidade-problemas-inspeces) — 10 tabelas
- [Stock, inventário, movimentos, encomendas](#stock-inventrio-movimentos-encomendas) — 29 tabelas
- [Recomendação de integração com ProdPlan ONE](#recomendacao-de-integracao-com-prodplan-one)

<a id="ordens-de-fabrico"></a>
## Ordens de fabrico

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `OF_CHECKLIST` | 2 995 204 | 19 | OFCH_ID | 4 | 0 |
| `OF_FP` | 2 627 279 | 52 | OFFP_ID | 5 | 6 |
| `OFFP_EQ` | 1 410 887 | 3 | OFFPEQ_OFFP_ID, OFFPEQ_E_ID | 2 | 0 |
| `ORDEMFABRICO` | 441 392 | 111 | OF_ID | 16 | 13 |
| `OF_ATTACH` | 130 420 | 12 | ATCH_ID | 2 | 0 |
| `TRANSP_OF` | 92 848 | 11 | TROF_TR_ID, TROF_OF_ID | 2 | 0 |
| `OFCH_LOCAL` | 57 954 | 2 | OFPROBS_OFCH_ID, OFPROBS_PROBSL_ID | 1 | 0 |
| `auxOrdemFabrico` | 7 880 | 30 | id | 0 | 1 |
| `OF_LOTE` | 7 083 | 4 | OFL_ID | 0 | 0 |
| `OF_ENTIDADE` | 5 642 | 6 | OFE_ID | 3 | 0 |
| `OF_PROPRIETARIO` | 3 823 | 11 | OFPROP_OF_ID, OFPROP_E_ID | 0 | 0 |
| `REP_OF_FP` | 3 413 | 10 | ROFFP_ID | 2 | 0 |
| `OF_OF_TIPOUSO` | 3 196 | 6 | OFOFTU_ID | 2 | 0 |
| `PROVAS_OF` | 1 575 | 3 | PRVOF_PRV_ID, PRVOF_OF_ID | 2 | 0 |
| `OFFP_GRAVIDADES` | 148 | 2 | FPGRAV_OFFP_ID, FPGRAV_OFFPGRAV_ID | 0 | 0 |
| `OF_RENTAL_PROVAS` | 110 | 10 | OFR_OF_ID, OFR_BOOKING_ID | 3 | 0 |
| `OF_VENDA` | 22 | 37 | OFV_ID | 3 | 0 |
| `OFFP_GRAVIDADE` | 5 | 3 | OFFPGRAV_ID | 0 | 0 |
| `EstadoOFAgente` | 4 | 3 | codEstado | 0 | 0 |
| `OF_TIPOUSO` | 3 | 3 | OFTU_ID | 0 | 2 |
| `OFFP_CL` | 3 | 4 | OFFPCL_ID | 0 | 1 |
| `OFFP_LINK` | 0 | 3 | — | 2 | 0 |
| `OFFP_PROBLEMA` | 0 | 4 | OFFPPROB_PROBS_ID, OFFPPROB_OFFP_ID, OFFPPROB_PROBSL_ID | 3 | 0 |

### `OF_CHECKLIST` — *2 995 204 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFCH_ID` | int | NO |  | **PK** |
| 2 | `OFCH_DESCR` | nvarchar(max) | NO |  |  |
| 3 | `OFCH_VISTO` | bit | YES |  |  |
| 4 | `OFCH_RESOLVIDO` | bit | YES |  |  |
| 5 | `OFCH_OF_ID` | int | YES |  | FK → `ORDEMFABRICO.OF_ID` |
| 6 | `OFCH_SEQUENCIA` | int | NO |  |  |
| 7 | `OFCH_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 8 | `OFCH_ESTADO` | int | YES |  |  |
| 9 | `OFCH_DESCR_EN` | nvarchar(max) | YES |  |  |
| 10 | `OFCH_FP_ID_CHK` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 11 | `OFCH_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 12 | `OFCH_GRAVIDADE` | int | NO |  |  |
| 13 | `OFCH_JSON_DOTS` | nvarchar(max) | YES |  |  |
| 14 | `OFCH_DATA_VERIFICACAO` | smalldatetime | YES |  |  |
| 15 | `OFCH_DATA_ACTUALIZACAO` | smalldatetime | YES |  |  |
| 16 | `OFCH_CULPA_CHEFE` | bit | NO |  |  |
| 17 | `OFCH_OFFP_ID` | int | YES |  | FK → `OF_FP.OFFP_ID` |
| 18 | `OFCH_MOLDE_REPARAR` | bit | NO |  |  |
| 19 | `OFCH_OFFP_ID_CULPA` | int | YES |  |  |

**PK**: `OFCH_ID`

**FKs declared (out)**:
- `OFCH_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `OFCH_FP_ID_CHK` → `FASES_PRODUCAO.FP_ID`
- `OFCH_OFFP_ID` → `OF_FP.OFFP_ID`
- `OFCH_OF_ID` → `ORDEMFABRICO.OF_ID`


**Implicit relations** _(by column naming)_:
- `OFCH_ID` → likely `OFCH_LOCAL`

**Sample (TOP 3)** *(showing 8 of 19 cols)*:

| `OFCH_ID` | `OFCH_DESCR` | `OFCH_VISTO` | `OFCH_RESOLVIDO` | `OFCH_OF_ID` | `OFCH_SEQUENCIA` | `OFCH_FP_ID` | `OFCH_ESTADO` |
|---|---|---|---|---|---|---|---|
| 75389996 | Tudo Ok da Laminagem | false | false | 10322962 | 1 | 36 | — |
| 75389997 | Tudo Ok da Corte | false | false | 10322962 | 2 | 28 | — |
| 75389998 | Tudo Ok da Laminagem | false | false | 10322963 | 1 | 36 | — |

---

### `OF_FP` — *2 627 279 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFP_ID` | int | NO |  | **PK** |
| 2 | `OFFP_OF_ID` | int | NO |  | FK → `ORDEMFABRICO.OF_ID` |
| 3 | `OFFP_FP_ID` | int | NO |  | FK → `FASES_PRODUCAO.FP_ID` |
| 4 | `OFFP_PROBLEMAS` | nvarchar(max) | YES |  |  |
| 5 | `OFFP_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 6 | `OFFP_DATAINICIO` | smalldatetime | YES |  |  |
| 7 | `OFFP_DATAFIM` | smalldatetime | YES |  |  |
| 8 | `OFFP_PESO` | float | NO |  |  |
| 9 | `OFFP_NUMUTIL` | int | NO |  |  |
| 10 | `OFFP_PESO_DECK_ANT` | float | NO |  |  |
| 11 | `OFFP_PESO_DECK_DP` | float | NO |  |  |
| 12 | `OFFP_PESO_CASCO_ANT` | float | NO |  |  |
| 13 | `OFFP_PESO_CASCO_DP` | float | NO |  |  |
| 14 | `OFFP_SERVER` | nvarchar(max) | NO |  |  |
| 15 | `OFFP_ARM_ID` | int | YES |  |  |
| 16 | `OFFP_SEQUENCIA` | smalldatetime | YES |  |  |
| 17 | `OFFP_OFFPCL_ID` | int | YES |  | FK → `OFFP_CL.OFFPCL_ID` |
| 18 | `OFFP_HORAS_REP` | float | NO |  |  |
| 19 | `OFFP_HORAS_REP_REAL` | float | NO |  |  |
| 20 | `OFFP_PECAS` | bit | NO |  |  |
| 21 | `OFFP_CONTROLO` | bit | NO |  |  |
| 22 | `OFFP_TEMPERATURA` | float | NO |  |  |
| 23 | `OFFP_HUMIDADE` | float | NO |  |  |
| 24 | `OFFP_CONTROLO_CRIS` | bit | NO |  |  |
| 25 | `OFFP_EMAIL_CRIS` | bit | NO |  |  |
| 26 | `OFFP_PROBS_GOLA` | nvarchar(2000) | YES |  |  |
| 27 | `OFFP_PROBS_INTERIOR` | int | YES |  |  |
| 28 | `OFFP_PROBS_PINTURA` | int | YES |  |  |
| 29 | `OFFP_PROBS_MOLDE` | int | YES |  |  |
| 30 | `OFFP_PROBS_LAMINAGEM` | int | YES |  |  |
| 31 | `OFFP_PROBS_DATA` | smalldatetime | YES |  |  |
| 32 | `OFFP_PROBS_LAM_INOCENTE` | bit | NO |  |  |
| 33 | `OFFP_PROBS_PINT_INOCENTE` | bit | NO |  |  |
| 34 | `OFFP_ORDEM` | int | NO |  |  |
| 35 | `OFFP_PESO_HIST` | nvarchar(max) | NO |  |  |
| 36 | `OFFP_LINHA_AUX` | int | YES |  |  |
| 37 | `OFFP_RETURN` | bit | NO |  |  |
| 38 | `OFFP_OFFP_ID_RETURN` | int | YES |  | FK → `OF_FP.OFFP_ID` |
| 39 | `OFFP_COEFICIENTE` | float | NO |  |  |
| 40 | `OFFP_TPCAM_ID` | int | YES |  | FK → `PRODUTO_CAMADA_TIPO.TPCAM_ID` |
| 41 | `OFFP_DATA_PREVISTA` | smalldatetime | YES |  |  |
| 42 | `OFFP_PLANEAMENTO` | bit | NO |  |  |
| 43 | `OFFP_TURN_ID` | int | YES |  |  |
| 44 | `OFFP_OF_ID_MLD` | int | YES |  |  |
| 45 | `OFFP_DATA_ENTREGA` | smalldatetime | YES |  |  |
| 46 | `OFFP_COEFICIENTE_X` | float | NO |  |  |
| 47 | `OFFP_RETORNO_GRAVE` | bit | NO |  |  |
| 48 | `OFFP_EMAIL` | nvarchar(max) | YES |  |  |
| 49 | `OFFP_VALOR_FACT` | float | NO |  |  |
| 50 | `OFFP_VALOR_CONTROL_1` | float | NO |  |  |
| 51 | `OFFP_VALOR_CONTROL_2` | float | NO |  |  |
| 52 | `OFFP_VALOR_CONTROL_3` | float | NO |  |  |

**PK**: `OFFP_ID`

**FKs declared (out)**:
- `OFFP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `OFFP_OFFP_ID_RETURN` → `OF_FP.OFFP_ID`
- `OFFP_OFFPCL_ID` → `OFFP_CL.OFFPCL_ID`
- `OFFP_OF_ID` → `ORDEMFABRICO.OF_ID`
- `OFFP_TPCAM_ID` → `PRODUTO_CAMADA_TIPO.TPCAM_ID`

**FKs declared (in)** — *6 references*:
- `OF_CHECKLIST.OFCH_OFFP_ID`
- `OF_FP.OFFP_OFFP_ID_RETURN`
- `OFFP_EQ.OFFPEQ_OFFP_ID`
- `OFFP_LINK.OFFPL_OFFP_ID_PROX`
- `OFFP_LINK.OFFPL_OFFP_ID_ANT`
- `OFFP_PROBLEMA.OFFPPROB_OFFP_ID`

**Implicit relations** _(by column naming)_:
- `OFFP_ID` → likely `OFFP_PROBLEMA`
- `OFFP_ARM_ID` → likely _(no obvious target)_
- `OFFP_TURN_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 52 cols)*:

| `OFFP_ID` | `OFFP_OF_ID` | `OFFP_FP_ID` | `OFFP_PROBLEMAS` | `OFFP_OBSERVACOES` | `OFFP_DATAINICIO` | `OFFP_DATAFIM` | `OFFP_PESO` |
|---|---|---|---|---|---|---|---|
| 567 | 70000 | 11 | — | — | 2007-10-26 00:00 | 2007-10-26 00:00 | 0.0 |
| 568 | 70001 | 11 | — | — | 2007-11-02 00:00 | 2007-11-02 00:00 | 0.0 |
| 569 | 70002 | 11 | — | — | 2007-11-08 00:00 | 2007-11-08 00:00 | 0.0 |

---

### `OFFP_EQ` — *1 410 887 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFPEQ_OFFP_ID` | int | NO |  | **PK** FK → `OF_FP.OFFP_ID` |
| 2 | `OFFPEQ_E_ID` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |
| 3 | `OFFPEQ_CHEFE` | bit | NO |  |  |

**PK**: `OFFPEQ_OFFP_ID, OFFPEQ_E_ID`

**FKs declared (out)**:
- `OFFPEQ_E_ID` → `ENTIDADE.E_ID`
- `OFFPEQ_OFFP_ID` → `OF_FP.OFFP_ID`


**Sample (TOP 3)**:

| `OFFPEQ_OFFP_ID` | `OFFPEQ_E_ID` | `OFFPEQ_CHEFE` |
|---|---|---|
| 747687 | 20350 | false |
| 749497 | 20356 | false |
| 750197 | 20345 | false |

---

### `ORDEMFABRICO` — *441 392 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OF_ID` | int | NO |  | **PK** FK → `ORDEMFABRICO.OF_ID` |
| 2 | `OF_DATA` | smalldatetime | NO |  |  |
| 3 | `OF_DATATRANSPORTE` | smalldatetime | YES |  |  |
| 4 | `OF_DATAENTREGA` | smalldatetime | YES |  |  |
| 5 | `OF_DATAPAGAMENTO` | smalldatetime | YES |  |  |
| 6 | `OF_DATAINICIO` | smalldatetime | YES |  |  |
| 7 | `OF_DATAFIM` | smalldatetime | YES |  |  |
| 8 | `OF_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 9 | `OF_PRECOCUSTO` | float | NO |  |  |
| 10 | `OF_PRECOVENDA` | float | NO |  |  |
| 11 | `OF_NOME` | nvarchar(max) | YES |  |  |
| 12 | `OF_MORADAENTREGA` | nvarchar(max) | YES |  |  |
| 13 | `OF_REFERENCIA` | nvarchar(max) | YES |  |  |
| 14 | `OF_TELEFONE` | nvarchar(max) | YES |  |  |
| 15 | `OF_EMAIL` | nvarchar(max) | YES |  |  |
| 16 | `OF_TRANSPORTE` | nvarchar(max) | YES |  |  |
| 17 | `OF_TRANSPORTEDOC` | nvarchar(max) | YES |  |  |
| 18 | `OF_AUTOCOLANTE` | nvarchar(max) | NO |  |  |
| 19 | `OF_DESCONTO` | float | NO |  |  |
| 20 | `OF_VALORPAGO` | float | NO |  |  |
| 21 | `OF_COEFICIENTE` | float | NO |  |  |
| 22 | `OF_PAGO` | bit | NO |  |  |
| 23 | `OF_DECKPINTURA` | bit | NO |  |  |
| 24 | `OF_CASCOPINTURA` | bit | NO |  |  |
| 25 | `OF_SUPERVISAO` | bit | NO |  |  |
| 26 | `OF_SUPERVISAOLAMINAGEM` | bit | NO |  |  |
| 27 | `OF_SEQUENCIA` | int | NO |  |  |
| 28 | `OF_OFTU_ID` | int | YES |  | FK → `OF_TIPOUSO.OFTU_ID` |
| 29 | `OF_TURN_ID` | int | YES |  | FK → `TURNO.TURN_ID` |
| 30 | `OF_ENC_ID` | int | YES |  | FK → `ENCOMENDA.ENC_ID` |
| 31 | `OF_P_ID` | int | NO |  | FK → `PRODUTO.P_ID` |
| 32 | `OF_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 33 | `OF_E_ID_ENC` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 34 | `OF_P_ID_CDECK` | int | YES |  | FK → `PRODUTO.P_ID` |
| 35 | `OF_P_ID_CCASCO` | int | YES |  | FK → `PRODUTO.P_ID` |
| 36 | `OF_OF_ID_MLD` | int | YES |  | FK → `ORDEMFABRICO.OF_ID` |
| 37 | `OF_FP_ID` | int | NO |  | FK → `FASES_PRODUCAO.FP_ID` |
| 38 | `OF_TR_ID` | int | YES |  |  |
| 39 | `OF_MOLDE_ACESSORIO` | bit | NO |  |  |
| 40 | `OF_CRIADOR` | nvarchar(max) | YES |  |  |
| 41 | `OF_ACTUALIZADOR` | nvarchar(max) | YES |  |  |
| 42 | `OF_DATAACTUALIZACAO` | smalldatetime | YES |  |  |
| 43 | `OF_P_ID_TOPO_FR` | int | YES |  |  |
| 44 | `OF_P_ID_TOPO_TR` | int | YES |  |  |
| 45 | `OF_P_ID_LATERAL_FR` | int | YES |  |  |
| 46 | `OF_P_ID_LATERAL_TR` | int | YES |  |  |
| 47 | `OF_P_ID_QUINAS` | int | YES |  |  |
| 48 | `OF_ARM_ID` | int | NO |  | FK → `ARMAZEM.ARM_ID` |
| 49 | `OF_ARM_ID_LAM` | int | NO |  |  |
| 50 | `OF_NUMUTIL` | int | NO |  |  |
| 51 | `OF_CUSTOS_CACHE` | float | YES |  |  |
| 52 | `OF_TRANSP` | bit | NO |  |  |
| 53 | `OF_FACT` | nvarchar(max) | YES |  |  |
| 54 | `OF_SUPERVISAOPINTURA` | bit | NO |  |  |
| 55 | `OF_P_ID_QUINAS_TR` | int | YES |  |  |
| 56 | `OF_P_ID_GOLA` | int | YES |  |  |
| 57 | `OF_DESCONTA_PESO` | bit | NO |  |  |
| 58 | `OF_P_ID_HIST` | nvarchar(max) | YES |  |  |
| 59 | `OF_REVISTO` | bit | NO |  |  |
| 60 | `OF_PARAPINTARFORA` | bit | NO |  |  |
| 61 | `OF_PREPREG` | bit | NO |  |  |
| 62 | `OF_TR_ID_ULT` | int | YES |  |  |
| 63 | `OF_TR_DESC_ULT` | nvarchar(max) | YES |  |  |
| 64 | `OF_TR_DATA_ULT` | smalldatetime | YES |  |  |
| 65 | `OF_PARAALTERAR` | bit | NO |  |  |
| 66 | `OF_TR_DATA_PREVISTA` | smalldatetime | YES |  |  |
| 67 | `OF_PLANO_DATA_PREVISTA` | smalldatetime | YES |  |  |
| 68 | `OF_PLANO_TURNO_PREVISTO` | int | YES |  |  |
| 69 | `OF_P_ID_AUTOCOLANTE` | int | YES |  |  |
| 70 | `OF_TAG_ID` | nvarchar(max) | YES |  |  |
| 71 | `OF_PRECOCUSTO_DT` | float | NO |  |  |
| 72 | `OF_UPDT` | bit | NO |  |  |
| 73 | `OF_ACERTO_RESINA` | float | NO |  |  |
| 74 | `OF_SEQUENCIA_UPD` | smalldatetime | YES |  |  |
| 75 | `OF_PINT_CLASS` | int | NO |  |  |
| 76 | `OF_PFORA_CLASS` | int | NO |  |  |
| 77 | `OF_LINHAACAB` | int | NO |  |  |
| 78 | `OF_ARM_FIXO` | bit | NO |  |  |
| 79 | `OF_COEFICIENTE_EXTRA` | float | NO |  |  |
| 80 | `OF_VERSAO_NOVA` | bit | NO |  |  |
| 81 | `OF_EM_ID` | int | YES |  | FK → `ENTIDADE_MORADA.EM_ID` |
| 82 | `OF_EM_ID_FACTURACAO` | int | YES |  |  |
| 83 | `OF_OF_ID_MAE` | int | YES |  | FK → `ORDEMFABRICO.OF_ID` |
| 84 | `OF_MOV_ID` | int | YES |  | FK → `MOVIMENTO.MOV_ID` |
| 85 | `OF_PROMO_CODE` | nvarchar(max) | YES |  |  |
| 86 | `OF_DATA_PROMO_DEALER` | date | YES |  |  |
| 87 | `OF_DATA_PROMO_CLIENT` | date | YES |  |  |
| 88 | `OF_PESO_DECK` | float | NO |  |  |
| 89 | `OF_PESO_CASCO` | float | NO |  |  |
| 90 | `OF_FALTA_MASCARA` | bit | NO |  |  |
| 91 | `OF_FALTA_DOCS_CLIENTE` | bit | NO |  |  |
| 92 | `OF_PROMO_EMAIL` | nvarchar(max) | YES |  |  |
| 93 | `OF_PRECOCUSTO_DT_INFLACIONADO` | float | NO |  |  |
| 94 | `OF_FALTA_AUTOCOLANTE_NOME` | bit | NO |  |  |
| 95 | `OF_FALTA_PROTECCAO_PAGAIA` | bit | NO |  |  |
| 96 | `OF_FALTA_GARRAFA` | bit | NO |  |  |
| 97 | `OF_FALTA_PARAFUSOS` | bit | NO |  |  |
| 98 | `OF_FALTA_PESOS` | bit | NO |  |  |
| 99 | `OF_FALTA_TRACTION_PADS` | bit | NO |  |  |
| 100 | `OF_FALTA_FINCA_PES` | bit | NO |  |  |
| 101 | `OF_FALTA_BANCO` | bit | NO |  |  |
| 102 | `OF_FALTA_LEME` | bit | NO |  |  |
| 103 | `OF_FALTA_CAPA` | bit | NO |  |  |
| 104 | `OF_FALTA_TOALHA` | bit | NO |  |  |
| 105 | `OF_RAL_MAIN` | nvarchar(max) | NO |  |  |
| 106 | `OF_RAL_SEC` | nvarchar(max) | NO |  |  |
| 107 | `OF_DUREZA_DECK` | int | NO |  |  |
| 108 | `OF_DUREZA_CASCO` | int | NO |  |  |
| 109 | `OF_DUREZA_PROA` | int | NO |  |  |
| 110 | `OF_SENSOR_ID_VACUO` | int | YES |  | FK → `IOT_SENSOR.SENSOR_ID` |
| 111 | `OF_TAG_NFC` | nvarchar(max) | YES |  |  |

**PK**: `OF_ID`

**FKs declared (out)**:
- `OF_ARM_ID` → `ARMAZEM.ARM_ID`
- `OF_ENC_ID` → `ENCOMENDA.ENC_ID`
- `OF_E_ID` → `ENTIDADE.E_ID`
- `OF_EM_ID` → `ENTIDADE_MORADA.EM_ID`
- `OF_E_ID_ENC` → `ENTIDADE.E_ID`
- `OF_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `OF_SENSOR_ID_VACUO` → `IOT_SENSOR.SENSOR_ID`
- `OF_MOV_ID` → `MOVIMENTO.MOV_ID`
- `OF_OFTU_ID` → `OF_TIPOUSO.OFTU_ID`
- `OF_OF_ID_MLD` → `ORDEMFABRICO.OF_ID`
- `OF_OF_ID_MAE` → `ORDEMFABRICO.OF_ID`
- `OF_ID` → `ORDEMFABRICO.OF_ID`
- `OF_P_ID` → `PRODUTO.P_ID`
- `OF_P_ID_CDECK` → `PRODUTO.P_ID`
- `OF_P_ID_CCASCO` → `PRODUTO.P_ID`
- `OF_TURN_ID` → `TURNO.TURN_ID`

**FKs declared (in)** — *13 references*:
- `ALARM.ALARM_OF_ID`
- `CENTRO_RESERVA_OFS.RO_OF_ID`
- `OF_CHECKLIST.OFCH_OF_ID`
- `OF_ENTIDADE.OFE_OF_ID`
- `OF_FP.OFFP_OF_ID`
- `OF_OF_TIPOUSO.OFOFTU_OF_ID`
- `OF_RENTAL_PROVAS.OFR_OF_ID`
- `ORDEMFABRICO.OF_OF_ID_MLD`
- `ORDEMFABRICO.OF_OF_ID_MAE`
- `ORDEMFABRICO.OF_ID`
- `PROVAS_BOOKING.PRVB_OF_ID`
- `PROVAS_OF.PRVOF_OF_ID`
- `TRANSP_OF.TROF_OF_ID`

**Implicit relations** _(by column naming)_:
- `OF_TR_ID` → likely _(no obvious target)_
- `OF_TAG_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 111 cols)*:

| `OF_ID` | `OF_DATA` | `OF_DATATRANSPORTE` | `OF_DATAENTREGA` | `OF_DATAPAGAMENTO` | `OF_DATAINICIO` | `OF_DATAFIM` | `OF_OBSERVACOES` |
|---|---|---|---|---|---|---|---|
| 8888 | 2001-11-14 00:00 | 2002-06-25 00:00 | — | 2002-07-03 00:00 | — | 2002-05-24 00:00 |  |
| 8889 | 2001-11-14 16:02 | 2002-03-28 00:00 | — | 2002-01-10 00:00 | 2002-01-02 00:00 | 2002-01-10 00:00 | AW |
| 8893 | 2001-11-14 16:05 | 2002-03-05 00:00 | — | — | 2002-02-21 00:00 | 2002-03-04 00:00 | 70 Kg - Q H S |

---

### `OF_ATTACH` — *130 420 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ATCH_ID` | int | NO |  | **PK** |
| 2 | `ATCH_NOME` | nvarchar(max) | YES |  |  |
| 3 | `ATCH_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `ATCH_OF_ID` | int | NO |  |  |
| 5 | `ATCH_IMAGE` | nvarchar(max) | NO |  |  |
| 6 | `ATCH_PUBLICO` | bit | NO |  |  |
| 7 | `ATCH_PRODUCAO` | bit | NO |  |  |
| 8 | `ATCH_TIPO` | int | YES |  | FK → `ATTACH_TIPO.TP_ATCH_ID` |
| 9 | `ATCH_ENVIADO_PROPRIETARIO` | bit | NO |  |  |
| 10 | `ATCH_ELIMINADO` | date | YES |  |  |
| 11 | `ATCH_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 12 | `ATCH_DATA` | date | YES |  |  |

**PK**: `ATCH_ID`

**FKs declared (out)**:
- `ATCH_TIPO` → `ATTACH_TIPO.TP_ATCH_ID`
- `ATCH_FP_ID` → `FASES_PRODUCAO.FP_ID`


**Implicit relations** _(by column naming)_:
- `ATCH_ID` → likely _(no obvious target)_
- `ATCH_OF_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 12 cols)*:

| `ATCH_ID` | `ATCH_NOME` | `ATCH_DESCRICAO` | `ATCH_OF_ID` | `ATCH_IMAGE` | `ATCH_PUBLICO` | `ATCH_PRODUCAO` | `ATCH_TIPO` |
|---|---|---|---|---|---|---|---|
| 1868 | 11771.jpg |  | 11771 | 11771_11771.jpg | false | false | 1 |
| 1869 | 11771_2.jpg |  | 11771 | 11771_11771_2.jpg | false | false | 1 |
| 1870 | 15273.jpg |  | 15273 | \\server\Documents\imagens_BD\15273_1... | false | false | 1 |

---

### `TRANSP_OF` — *92 848 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TROF_TR_ID` | int | NO |  | **PK** FK → `TRANSPORTE.TR_ID` |
| 2 | `TROF_OF_ID` | int | NO |  | **PK** FK → `ORDEMFABRICO.OF_ID` |
| 3 | `TROF_ENVIADO` | bit | NO |  |  |
| 4 | `TROF_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 5 | `TROF_LEVA_PECAS` | bit | NO |  |  |
| 6 | `TROF_DATA_CONFIRMACAO` | date | YES |  |  |
| 7 | `TROF_CONFIRMACAO_OBS` | nvarchar(max) | YES |  |  |
| 8 | `TROF_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 9 | `TROF_COMPRIMENTO` | float | NO |  |  |
| 10 | `TROF_LARGURA` | float | NO |  |  |
| 11 | `TROF_ALTURA` | float | NO |  |  |

**PK**: `TROF_TR_ID, TROF_OF_ID`

**FKs declared (out)**:
- `TROF_OF_ID` → `ORDEMFABRICO.OF_ID`
- `TROF_TR_ID` → `TRANSPORTE.TR_ID`


**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `TROF_TR_ID` | `TROF_OF_ID` | `TROF_ENVIADO` | `TROF_OBSERVACOES` | `TROF_LEVA_PECAS` | `TROF_DATA_CONFIRMACAO` | `TROF_CONFIRMACAO_OBS` | `TROF_DATA_CRIACAO` |
|---|---|---|---|---|---|---|---|
| 1 | 9465 | true | — | false | — | — | 2019-09-24 16:30 |
| 1 | 9466 | true | — | false | — | — | 2019-09-24 16:30 |
| 2 | 9501 | true | — | false | — | — | 2019-09-24 16:30 |

---

### `OFCH_LOCAL` — *57 954 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFPROBS_OFCH_ID` | int | NO |  | **PK** |
| 2 | `OFPROBS_PROBSL_ID` | int | NO |  | **PK** FK → `PROBS_LOCAL.PROBSL_ID` |

**PK**: `OFPROBS_OFCH_ID, OFPROBS_PROBSL_ID`

**FKs declared (out)**:
- `OFPROBS_PROBSL_ID` → `PROBS_LOCAL.PROBSL_ID`


**Implicit relations** _(by column naming)_:
- `OFPROBS_OFCH_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFPROBS_OFCH_ID` | `OFPROBS_PROBSL_ID` |
|---|---|
| 1670295 | 6 |
| 1670296 | 7 |
| 1670297 | 7 |

---

### `auxOrdemFabrico` — *7 880 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `id` | int | NO |  | **PK** |
| 2 | `modelo` | int | YES |  |  |
| 3 | `cdeck` | int | YES |  |  |
| 4 | `ccasco` | int | YES |  |  |
| 5 | `banco_frente` | int | YES |  |  |
| 6 | `banco_tras` | int | YES |  |  |
| 7 | `fincapes_frente` | int | YES |  |  |
| 8 | `fincapes_back` | int | YES |  |  |
| 9 | `strap_frente` | int | YES |  |  |
| 10 | `strap_tras` | int | YES |  |  |
| 11 | `leme` | int | YES |  |  |
| 12 | `ref` | varchar(2000) | YES |  |  |
| 13 | `obs` | nvarchar(max) | YES |  |  |
| 14 | `of_id` | int | YES |  |  |
| 15 | `nBarcos` | int | YES |  |  |
| 16 | `codAgente` | int | YES |  |  |
| 17 | `cor_topo_fr` | int | YES |  |  |
| 18 | `cor_topo_tr` | int | YES |  |  |
| 19 | `cor_lateral_fr` | int | YES |  |  |
| 20 | `cor_lateral_tr` | int | YES |  |  |
| 21 | `cor_quinas` | int | YES |  |  |
| 22 | `cor_quinas_tr` | int | YES |  |  |
| 23 | `cor_gola` | int | YES |  |  |
| 24 | `color_designer` | varchar(250) | YES |  |  |
| 25 | `cor_risca` | int | YES |  |  |
| 26 | `interior` | int | YES |  |  |
| 27 | `tampa_leme` | int | YES |  |  |
| 28 | `porta_numeros` | int | YES |  |  |
| 29 | `invoice` | varchar(2000) | YES |  |  |
| 30 | `preco_venda` | float | YES |  |  |

**PK**: `id`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `auxAnexos.aux_id`

**Implicit relations** _(by column naming)_:
- `of_id` → likely `OF_FP`

**Sample (TOP 3)** *(showing 8 of 30 cols)*:

| `id` | `modelo` | `cdeck` | `ccasco` | `banco_frente` | `banco_tras` | `fincapes_frente` | `fincapes_back` |
|---|---|---|---|---|---|---|---|
| 1 | 22152 | 20596 | 20596 | 20254 | 20511 | 20247 | — |
| 2 | 22152 | 20596 | 20596 | 20254 | 20511 | 20247 | — |
| 3 | 20156 | 20596 | 20596 | — | — | — | — |

---

### `OF_LOTE` — *7 083 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFL_ID` | int | NO |  | **PK** |
| 2 | `OFL_OF_ID` | int | NO |  |  |
| 3 | `OFL_P_ID` | int | NO |  |  |
| 4 | `OFL_LOTE` | varchar(50) | YES |  |  |

**PK**: `OFL_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `OFL_ID` → likely _(no obvious target)_
- `OFL_OF_ID` → likely _(no obvious target)_
- `OFL_P_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFL_ID` | `OFL_OF_ID` | `OFL_P_ID` | `OFL_LOTE` |
|---|---|---|---|
| 1 | 22673 | 20584 | 17667 |
| 2 | 31620 | 20597 | — |
| 3 | 31630 | 20583 | 17694 |

---

### `OF_ENTIDADE` — *5 642 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFE_ID` | int | NO |  | **PK** |
| 2 | `OFE_OF_ID` | int | NO |  | FK → `ORDEMFABRICO.OF_ID` |
| 3 | `OFE_OF_PRECOVENDA` | float | NO |  |  |
| 4 | `OFE_E_ID_ANTERIOR` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 5 | `OFE_DATA` | date | NO |  |  |
| 6 | `OFE_E_ID_RESPONSAVEL` | int | NO |  | FK → `ENTIDADE.E_ID` |

**PK**: `OFE_ID`

**FKs declared (out)**:
- `OFE_E_ID_ANTERIOR` → `ENTIDADE.E_ID`
- `OFE_E_ID_RESPONSAVEL` → `ENTIDADE.E_ID`
- `OFE_OF_ID` → `ORDEMFABRICO.OF_ID`


**Implicit relations** _(by column naming)_:
- `OFE_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFE_ID` | `OFE_OF_ID` | `OFE_OF_PRECOVENDA` | `OFE_E_ID_ANTERIOR` | `OFE_DATA` | `OFE_E_ID_RESPONSAVEL` |
|---|---|---|---|---|---|
| 4 | 118018 | 2000.0 | 25090 | 2020-02-28 | 24908 |
| 5 | 124200 | 1500.0 | 20042 | 2020-03-02 | 21532 |
| 6 | 121287 | 2200.0 | 19840 | 2020-03-02 | 21532 |

---

### `OF_PROPRIETARIO` — *3 823 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFPROP_OF_ID` | int | NO |  | **PK** |
| 2 | `OFPROP_E_ID` | int | NO |  | **PK** |
| 3 | `OFPROP_P_ID_BANCO` | int | YES |  |  |
| 4 | `OFPROP_BANCO_POSICAO` | int | YES |  |  |
| 5 | `OFPROP_BANCO_ALTURA` | int | YES |  |  |
| 6 | `OFPROP_P_ID_FPES` | int | YES |  |  |
| 7 | `OFPROP_FPES_POSICAO` | int | YES |  |  |
| 8 | `OFPROP_PAGAIA` | nvarchar(max) | YES |  |  |
| 9 | `OFPROP_PAGAIA_COMPRIMENTO` | nvarchar(max) | YES |  |  |
| 10 | `OFPROP_DATA` | date | YES |  |  |
| 11 | `OFPROP_P_ID_LEME` | int | YES |  |  |

**PK**: `OFPROP_OF_ID, OFPROP_E_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `OFPROP_OF_ID` → likely _(no obvious target)_
- `OFPROP_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `OFPROP_OF_ID` | `OFPROP_E_ID` | `OFPROP_P_ID_BANCO` | `OFPROP_BANCO_POSICAO` | `OFPROP_BANCO_ALTURA` | `OFPROP_P_ID_FPES` | `OFPROP_FPES_POSICAO` | `OFPROP_PAGAIA` |
|---|---|---|---|---|---|---|---|
| 8888 | 29776 | — | 14 | 0 | 20247 | 6 |  |
| 8893 | 25492 | 21483 | 3 | 0 | 20247 | 6 |  |
| 8896 | 30257 | — | 20 | 0 | 20247 | 18 |  |

---

### `REP_OF_FP` — *3 413 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ROFFP_ID` | int | NO |  | **PK** |
| 2 | `ROFFP_REP_ID` | int | NO |  | FK → `REPARACOES_PROVAS.REP_ID` |
| 3 | `ROFFP_FP_ID` | int | NO |  | FK → `FASES_PRODUCAO.FP_ID` |
| 4 | `ROFFP_OF_ID` | int | YES |  |  |
| 5 | `ROFFP_DATA_I` | smalldatetime | YES |  |  |
| 6 | `ROFFP_DATA_F` | smalldatetime | YES |  |  |
| 7 | `ROFFP_OBSERVACOES` | nvarchar(max) | NO |  |  |
| 8 | `ROFFP_PROBLEMAS` | nvarchar(max) | NO |  |  |
| 9 | `ROFFP_E_ID` | int | YES |  |  |
| 10 | `ROFFP_SEQUENCIA` | int | NO |  |  |

**PK**: `ROFFP_ID`

**FKs declared (out)**:
- `ROFFP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `ROFFP_REP_ID` → `REPARACOES_PROVAS.REP_ID`


**Implicit relations** _(by column naming)_:
- `ROFFP_ID` → likely _(no obvious target)_
- `ROFFP_OF_ID` → likely _(no obvious target)_
- `ROFFP_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 10 cols)*:

| `ROFFP_ID` | `ROFFP_REP_ID` | `ROFFP_FP_ID` | `ROFFP_OF_ID` | `ROFFP_DATA_I` | `ROFFP_DATA_F` | `ROFFP_OBSERVACOES` | `ROFFP_PROBLEMAS` |
|---|---|---|---|---|---|---|---|
| 126 | 64 | 1 | 132667 | 2023-05-09 09:02 | 2023-05-09 09:03 |  |  |
| 127 | 64 | 73 | 132667 | 2023-05-12 10:19 | 2023-05-12 10:19 |  |  |
| 128 | 64 | 2 | 132667 | 2023-05-12 10:19 | 2023-05-12 10:19 |  |  |

---

### `OF_OF_TIPOUSO` — *3 196 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFOFTU_ID` | int | NO |  | **PK** |
| 2 | `OFOFTU_OF_ID` | int | NO |  | FK → `ORDEMFABRICO.OF_ID` |
| 3 | `OFOFTU_OFTU_ID` | int | NO |  | FK → `OF_TIPOUSO.OFTU_ID` |
| 4 | `OFOFTU_DATAENTRADA` | smalldatetime | YES |  |  |
| 5 | `OFOFTU_DATASAIDA` | smalldatetime | YES |  |  |
| 6 | `OFOFTU_DATAPAGAMENTO` | smalldatetime | YES |  |  |

**PK**: `OFOFTU_ID`

**FKs declared (out)**:
- `OFOFTU_OFTU_ID` → `OF_TIPOUSO.OFTU_ID`
- `OFOFTU_OF_ID` → `ORDEMFABRICO.OF_ID`


**Implicit relations** _(by column naming)_:
- `OFOFTU_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFOFTU_ID` | `OFOFTU_OF_ID` | `OFOFTU_OFTU_ID` | `OFOFTU_DATAENTRADA` | `OFOFTU_DATASAIDA` | `OFOFTU_DATAPAGAMENTO` |
|---|---|---|---|---|---|
| 22640 | 9308 | 59 | 2001-12-14 00:00 | — | — |
| 22641 | 9405 | 59 | — | — | — |
| 22642 | 9438 | 1 | 2002-03-15 00:00 | — | — |

---

### `PROVAS_OF` — *1 575 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PRVOF_PRV_ID` | int | NO |  | **PK** FK → `PROVAS.PRV_ID` |
| 2 | `PRVOF_OF_ID` | int | NO |  | **PK** FK → `ORDEMFABRICO.OF_ID` |
| 3 | `PRVOF_PRECO` | decimal | YES |  |  |

**PK**: `PRVOF_PRV_ID, PRVOF_OF_ID`

**FKs declared (out)**:
- `PRVOF_OF_ID` → `ORDEMFABRICO.OF_ID`
- `PRVOF_PRV_ID` → `PROVAS.PRV_ID`


**Sample (TOP 3)**:

| `PRVOF_PRV_ID` | `PRVOF_OF_ID` | `PRVOF_PRECO` |
|---|---|---|
| 32 | 104253 | — |
| 32 | 121140 | — |
| 32 | 131447 | — |

---

### `OFFP_GRAVIDADES` — *148 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `FPGRAV_OFFP_ID` | int | NO |  | **PK** |
| 2 | `FPGRAV_OFFPGRAV_ID` | int | NO |  | **PK** |

**PK**: `FPGRAV_OFFP_ID, FPGRAV_OFFPGRAV_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `FPGRAV_OFFP_ID` → likely _(no obvious target)_
- `FPGRAV_OFFPGRAV_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `FPGRAV_OFFP_ID` | `FPGRAV_OFFPGRAV_ID` |
|---|---|
| 3619569 | 4 |
| 3619572 | 2 |
| 3619572 | 5 |

---

### `OF_RENTAL_PROVAS` — *110 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFR_OF_ID` | int | NO |  | **PK** FK → `ORDEMFABRICO.OF_ID` |
| 2 | `OFR_BOOKING_ID` | int | NO |  | **PK** |
| 3 | `OFR_DATA_ENTREGA` | smalldatetime | YES |  |  |
| 4 | `OFR_DATA_RECEBIDO` | smalldatetime | YES |  |  |
| 5 | `OFR_E_ID_ENTREGA` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 6 | `OFR_E_ID_RECEBIDO` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 7 | `OFR_BOOKING_NAME` | nvarchar(max) | NO |  |  |
| 8 | `OFR_BOOKING_NTEAM` | nvarchar(max) | NO |  |  |
| 9 | `OFR_BOOKING_VALOR` | float | NO |  |  |
| 10 | `OFR_E_ID_ATRIBUI` | int | YES |  |  |

**PK**: `OFR_OF_ID, OFR_BOOKING_ID`

**FKs declared (out)**:
- `OFR_E_ID_ENTREGA` → `ENTIDADE.E_ID`
- `OFR_E_ID_RECEBIDO` → `ENTIDADE.E_ID`
- `OFR_OF_ID` → `ORDEMFABRICO.OF_ID`


**Implicit relations** _(by column naming)_:
- `OFR_BOOKING_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 10 cols)*:

| `OFR_OF_ID` | `OFR_BOOKING_ID` | `OFR_DATA_ENTREGA` | `OFR_DATA_RECEBIDO` | `OFR_E_ID_ENTREGA` | `OFR_E_ID_RECEBIDO` | `OFR_BOOKING_NAME` | `OFR_BOOKING_NTEAM` |
|---|---|---|---|---|---|---|---|
| 119935 | 951 | 2000-01-01 00:00 | 2000-01-01 00:00 | 20597 | 20597 | Acerto barcos | NELO |
| 119991 | 982 | 2022-05-18 07:38 | — | 24908 | — | United States of America | United States of America |
| 121142 | 951 | 2000-01-01 00:00 | 2000-01-01 00:00 | 20597 | 20597 | Acerto barcos | NELO |

---

### `OF_VENDA` — *22 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFV_ID` | int | NO |  | **PK** |
| 2 | `OFV_DATA_SUBMETIDO` | date | NO |  |  |
| 3 | `OFV_NOME` | nvarchar(max) | NO |  |  |
| 4 | `OFV_MORADA` | nvarchar(max) | NO |  |  |
| 5 | `OFV_PS_ID` | int | NO |  | FK → `PAISES_SITE.ID` |
| 6 | `OFV_EMAIL` | nvarchar(max) | NO |  |  |
| 7 | `OFV_TELEFONE` | nvarchar(max) | NO |  |  |
| 8 | `OFV_OF_ID` | int | NO |  |  |
| 9 | `OFV_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 10 | `OFV_MODELO` | nvarchar(max) | NO |  |  |
| 11 | `OFV_ANO_FABRICO` | int | NO |  |  |
| 12 | `OFV_DESCRICAO` | nvarchar(max) | NO |  |  |
| 13 | `OFV_DANIF_DECK` | bit | NO |  |  |
| 14 | `OFV_DANIF_CASCO` | bit | NO |  |  |
| 15 | `OFV_DANIF_INTERIOR` | bit | NO |  |  |
| 16 | `OFV_DANIF_DESCRICAO` | nvarchar(max) | NO |  |  |
| 17 | `OFV_REPARADO` | nvarchar(max) | NO |  |  |
| 18 | `OFV_CUSTOMIZACOES` | nvarchar(max) | YES |  |  |
| 19 | `OFV_BANCO` | bit | NO |  |  |
| 20 | `OFV_FPES` | bit | NO |  |  |
| 21 | `OFV_LEME` | bit | NO |  |  |
| 22 | `OFV_PESOS` | bit | NO |  |  |
| 23 | `OFV_CAPA` | bit | NO |  |  |
| 24 | `OFV_FOTO_PERFIL` | nvarchar(max) | NO |  |  |
| 25 | `OFV_FOTO_DECK` | nvarchar(max) | NO |  |  |
| 26 | `OFV_FOTO_CASCO` | nvarchar(max) | NO |  |  |
| 27 | `OFV_FOTO_INTERIOR` | nvarchar(max) | NO |  |  |
| 28 | `OFV_FOTO_PROA` | nvarchar(max) | NO |  |  |
| 29 | `OFV_FOTO_RE` | nvarchar(max) | NO |  |  |
| 30 | `OFV_COMPRADO_NOVO` | nvarchar(max) | NO |  |  |
| 31 | `OFV_LOCALIZACAO_ACTUAL` | nvarchar(max) | NO |  |  |
| 32 | `OFV_PRECO_PEDIDO` | float | NO |  |  |
| 33 | `OFV_PRECO_OFERECIDO` | float | NO |  |  |
| 34 | `OFV_FP_ID` | int | NO |  | FK → `FASES_PRODUCAO.FP_ID` |
| 35 | `OFV_DATA_REVISAO` | date | YES |  |  |
| 36 | `OFV_NOTA_REVISAO` | int | NO |  |  |
| 37 | `OFV_OBSERVACOES_REVISAO` | nvarchar(max) | NO |  |  |

**PK**: `OFV_ID`

**FKs declared (out)**:
- `OFV_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `OFV_PS_ID` → `PAISES_SITE.ID`
- `OFV_P_ID` → `PRODUTO.P_ID`


**Implicit relations** _(by column naming)_:
- `OFV_ID` → likely _(no obvious target)_
- `OFV_OF_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 37 cols)*:

| `OFV_ID` | `OFV_DATA_SUBMETIDO` | `OFV_NOME` | `OFV_MORADA` | `OFV_PS_ID` | `OFV_EMAIL` | `OFV_TELEFONE` | `OFV_OF_ID` |
|---|---|---|---|---|---|---|---|
| 29 | 2022-01-20 | Carl | Granli | 169 | kjapp@me.com | +4746540930 | -1 |
| 30 | 2022-01-26 | sergio tavares | vrsa | 181 | miraventsergio@hotmail.com | +351960482830 | -1 |
| 31 | 2022-07-12 | Martin Hájek | Petržílkova 2486,Praha 5,15800 | 60 | krusmen@seznam.cz | +420605305281 | 119441 |

---

### `OFFP_GRAVIDADE` — *5 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFPGRAV_ID` | int | NO |  | **PK** |
| 2 | `OFFPGRAV_DESCRICAO` | nvarchar(max) | NO |  |  |
| 3 | `OFFPGRAV_PARAR` | bit | NO |  |  |

**PK**: `OFFPGRAV_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `OFFPGRAV_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFFPGRAV_ID` | `OFFPGRAV_DESCRICAO` | `OFFPGRAV_PARAR` |
|---|---|---|
| 1 | Preparação | false |
| 2 | Lixar/Polir | false |
| 3 | Transformação | true |

---

### `EstadoOFAgente` — *4 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codEstado` | int | NO |  | **PK** |
| 2 | `estado` | varchar(50) | YES |  |  |
| 3 | `estadoEN` | varchar(50) | YES |  |  |

**PK**: `codEstado`

**FKs declared (out)**: _(none)_


**Sample (TOP 3)**:

| `codEstado` | `estado` | `estadoEN` |
|---|---|---|
| 1 | Pendente | Pending |
| 2 | Em processamento | Processing |
| 3 | Entregue | Delivered |

---

### `OF_TIPOUSO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFTU_ID` | int | NO |  | **PK** |
| 2 | `OFTU_NOME` | nvarchar(max) | NO |  |  |
| 3 | `OFTU_OBSERVACOES` | nvarchar(max) | YES |  |  |

**PK**: `OFTU_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `OF_OF_TIPOUSO.OFOFTU_OFTU_ID`
- `ORDEMFABRICO.OF_OFTU_ID`

**Implicit relations** _(by column naming)_:
- `OFTU_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFTU_ID` | `OFTU_NOME` | `OFTU_OBSERVACOES` |
|---|---|---|
| 1 | 2ª Escolha |  |
| 2 | Teste/Stock | — |
| 59 | Cedidos |  |

---

### `OFFP_CL` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFPCL_ID` | int | NO |  | **PK** |
| 2 | `OFFPCL_DESC` | nvarchar(max) | NO |  |  |
| 3 | `OFFPCL_SEQUENCIA` | int | NO |  |  |
| 4 | `OFFPCL_DESC_EN` | nvarchar(max) | YES |  |  |

**PK**: `OFFPCL_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `OF_FP.OFFP_OFFPCL_ID`

**Implicit relations** _(by column naming)_:
- `OFFPCL_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `OFFPCL_ID` | `OFFPCL_DESC` | `OFFPCL_SEQUENCIA` | `OFFPCL_DESC_EN` |
|---|---|---|---|
| 1 | Muito Grave | 3 |  |
| 2 | Grave | 2 |  |
| 3 | Não Grave | 1 |  |

---

### `OFFP_LINK` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFPL_OFFP_ID_PROX` | int | NO |  | FK → `OF_FP.OFFP_ID` |
| 2 | `OFFPL_OFFP_ID_ANT` | int | NO |  | FK → `OF_FP.OFFP_ID` |
| 3 | `OFFPL_SEQUENCIA` | int | NO |  |  |

**PK**: _(none declared)_

**FKs declared (out)**:
- `OFFPL_OFFP_ID_PROX` → `OF_FP.OFFP_ID`
- `OFFPL_OFFP_ID_ANT` → `OF_FP.OFFP_ID`


**Sample**: _(table empty or unreadable)_

---

### `OFFP_PROBLEMA` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OFFPPROB_PROBS_ID` | int | NO |  | **PK** FK → `PROBS.PROBS_ID` |
| 2 | `OFFPPROB_OFFP_ID` | int | NO |  | **PK** FK → `OF_FP.OFFP_ID` |
| 3 | `OFFPPROB_PROBSL_ID` | int | NO |  | **PK** FK → `PROBS_LOCAL.PROBSL_ID` |
| 4 | `OFFPPROB_OBS` | nvarchar(max) | YES |  |  |

**PK**: `OFFPPROB_PROBS_ID, OFFPPROB_OFFP_ID, OFFPPROB_PROBSL_ID`

**FKs declared (out)**:
- `OFFPPROB_OFFP_ID` → `OF_FP.OFFP_ID`
- `OFFPPROB_PROBS_ID` → `PROBS.PROBS_ID`
- `OFFPPROB_PROBSL_ID` → `PROBS_LOCAL.PROBSL_ID`


**Sample**: _(table empty or unreadable)_

---

<a id="artigos--produtos--bom"></a>
## Artigos / Produtos / BOM

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `PRODUTO_COMPONENTE` | 117 900 | 16 | COMP_ID | 6 | 0 |
| `PRODUTO_FASE` | 42 811 | 19 | PRODF_ID | 4 | 4 |
| `PRODUTO_OPCOES` | 26 292 | 11 | POP_P_ID, POP_P_P_ID | 2 | 0 |
| `PRODUTO_CAMADA` | 16 229 | 5 | CAM_ID | 2 | 0 |
| `PRODUTO` | 14 016 | 121 | P_ID | 3 | 24 |
| `PRODUTO_ENTIDADE` | 7 687 | 9 | PF_P_ID, PF_E_ID | 3 | 0 |
| `PRODUTO_ATTACH` | 3 858 | 7 | AT_ID | 3 | 0 |
| `PRODUTO_LISTA_ITEMS` | 960 | 9 | PLI_ID | 1 | 0 |
| `PRODUTO_TIPO` | 421 | 11 | TP_ID | 3 | 6 |
| `PRODUTO_MODELO` | 319 | 3 | M_ID | 0 | 2 |
| `MEDIDAS` | 165 | 7 | MED_ID | 3 | 0 |
| `ArtigosGrupos` | 141 | 3 | id_orig, id_virtual | 0 | 0 |
| `ProdutoTipoAcessorio` | 88 | 2 | codTipo, codProduto | 2 | 0 |
| `PRODUTO_FASE_LINK` | 29 | 3 | PRODFL_PRODF_ID_PROX, PRODFL_PRODF_ID_ANT | 2 | 0 |
| `PRODUTO_LISTA` | 26 | 5 | PL_ID | 0 | 1 |
| `UNIDADE` | 22 | 2 | UNI_ID | 0 | 1 |
| `PRODUTO_TAMANHO` | 18 | 3 | TAM_ID | 0 | 2 |
| `PRODUTO_COEFICIENTE` | 15 | 6 | PCOEF_ID | 1 | 0 |
| `PRODUTO_CAMADA_TIPO` | 12 | 4 | TPCAM_ID | 1 | 4 |
| `PRODUTO_CONTABILIDADE_TIPO` | 10 | 3 | PCONT_ID | 0 | 0 |
| `PRODUTO_ESTADO` | 7 | 3 | EST_ID | 1 | 1 |
| `PRODUTO_NUMERO_POCOS` | 7 | 4 | NP_ID | 0 | 2 |
| `COMPONENTE_TIPO` | 4 | 2 | TPCOMP_ID | 0 | 1 |
| `PRODUTO_ATTACH_TIPO` | 2 | 2 | ATT_ID | 0 | 1 |
| `PRODUTO_PROB_CAUSA_SOL` | 0 | 4 | PP_ID | 2 | 0 |

### `PRODUTO_COMPONENTE` — *117 900 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `COMP_ID` | int | NO |  | **PK** |
| 2 | `COMP_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 3 | `COMP_P_P_ID` | int | NO |  | FK → `PRODUTO.P_ID` |
| 4 | `COMP_QUANTIDADE` | float | NO |  |  |
| 5 | `COMP_TPCOMP_ID` | int | NO |  | FK → `COMPONENTE_TIPO.TPCOMP_ID` |
| 6 | `COMP_OBS` | nvarchar(max) | YES |  |  |
| 7 | `COMP_DATA_ALT` | smalldatetime | YES |  |  |
| 8 | `COMP_FASE_FINAL` | bit | NO |  |  |
| 9 | `COMP_CONFIGURAVEL` | bit | NO |  |  |
| 10 | `COMP_UNICO` | bit | NO |  |  |
| 11 | `COMP_VALOR_EXTRA` | bit | NO |  |  |
| 12 | `COMP_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 13 | `COMP_ATRIB_ID` | int | YES |  | FK → `ATRIBUTO.ATRIB_ID` |
| 14 | `COMP_L_ID` | int | YES |  | FK → `LISTA.L_ID` |
| 15 | `COMP_ELIMINADO` | smalldatetime | YES |  |  |
| 16 | `COMP_GESTOR_MARCA` | bit | NO |  |  |

**PK**: `COMP_ID`

**FKs declared (out)**:
- `COMP_ATRIB_ID` → `ATRIBUTO.ATRIB_ID`
- `COMP_TPCOMP_ID` → `COMPONENTE_TIPO.TPCOMP_ID`
- `COMP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `COMP_L_ID` → `LISTA.L_ID`
- `COMP_P_ID` → `PRODUTO.P_ID`
- `COMP_P_P_ID` → `PRODUTO.P_ID`


**Implicit relations** _(by column naming)_:
- `COMP_ID` → likely `Competicao`

**Sample (TOP 3)** *(showing 8 of 16 cols)*:

| `COMP_ID` | `COMP_P_ID` | `COMP_P_P_ID` | `COMP_QUANTIDADE` | `COMP_TPCOMP_ID` | `COMP_OBS` | `COMP_DATA_ALT` | `COMP_FASE_FINAL` |
|---|---|---|---|---|---|---|---|
| 2 | 21388 | 20799 | 0.171 | 2 | — | — | false |
| 4 | 21389 | 20448 | 0.4 | 2 | — | — | false |
| 5 | 21389 | 20459 | 0.4 | 2 | — | — | false |

---

### `PRODUTO_FASE` — *42 811 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PRODF_ID` | int | NO |  | **PK** |
| 2 | `PRODF_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 3 | `PRODF_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 4 | `PRODF_DESCRICAO` | nvarchar(max) | YES |  |  |
| 5 | `PRODF_SEQUENCIA` | int | NO |  |  |
| 6 | `PRODF_TEMPO` | float | NO |  |  |
| 7 | `PRODF_DATA` | smalldatetime | NO |  |  |
| 8 | `PRODF_CRIADOR` | nvarchar(max) | NO |  |  |
| 9 | `PRODF_ACTUALIZADOR` | nvarchar(max) | YES |  |  |
| 10 | `PRODF_DATAACTUALIZACAO` | smalldatetime | YES |  |  |
| 11 | `PRODF_PRODF_ID` | int | YES |  | FK → `PRODUTO_FASE.PRODF_ID` |
| 12 | `PRODF_DATA_ELIMINADO` | smalldatetime | YES |  |  |
| 13 | `PRODF_STOCK` | float | NO |  |  |
| 14 | `PRODF_AUTOMATICA` | bit | NO |  |  |
| 15 | `PRODF_FABRICO` | bit | NO |  |  |
| 16 | `PRODF_COEFICIENTE` | float | NO |  |  |
| 17 | `PRODF_TPCAM_ID` | int | YES |  | FK → `PRODUTO_CAMADA_TIPO.TPCAM_ID` |
| 18 | `PRODF_PLANEAMENTO` | bit | NO |  |  |
| 19 | `PRODF_COEFICIENTE_X` | float | NO |  |  |

**PK**: `PRODF_ID`

**FKs declared (out)**:
- `PRODF_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `PRODF_P_ID` → `PRODUTO.P_ID`
- `PRODF_TPCAM_ID` → `PRODUTO_CAMADA_TIPO.TPCAM_ID`
- `PRODF_PRODF_ID` → `PRODUTO_FASE.PRODF_ID`

**FKs declared (in)** — *4 references*:
- `PLANO.PL_PRODF_ID`
- `PRODUTO_FASE_LINK.PRODFL_PRODF_ID_PROX`
- `PRODUTO_FASE_LINK.PRODFL_PRODF_ID_ANT`
- `PRODUTO_FASE.PRODF_PRODF_ID`

**Implicit relations** _(by column naming)_:
- `PRODF_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 19 cols)*:

| `PRODF_ID` | `PRODF_P_ID` | `PRODF_FP_ID` | `PRODF_DESCRICAO` | `PRODF_SEQUENCIA` | `PRODF_TEMPO` | `PRODF_DATA` | `PRODF_CRIADOR` |
|---|---|---|---|---|---|---|---|
| 12063 | 20982 | — | 1 - Limpeza dos moldes.  | 1 | 0.0 | 2009-09-28 13:35 | CRISTIANA\Guilherme |
| 12064 | 20982 | — | 1 – Utilizar uma espátula flexível pa... | 2 | 0.0 | 2009-09-28 13:59 | CRISTIANA\Guilherme |
| 12065 | 20982 | 2 |  | 82 | 0.0 | 2009-09-28 13:59 | CRISTIANA\Guilherme |

---

### `PRODUTO_OPCOES` — *26 292 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `POP_P_ID` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |
| 2 | `POP_P_P_ID` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |
| 3 | `POP_CORES` | bit | NO |  |  |
| 4 | `POP_TOPOS` | bit | NO |  |  |
| 5 | `POP_LATERAIS` | bit | NO |  |  |
| 6 | `POP_QUINAS` | bit | NO |  |  |
| 7 | `POP_CASCO` | bit | NO |  |  |
| 8 | `POP_GOLA` | bit | NO |  |  |
| 9 | `POP_RISCA` | bit | NO |  |  |
| 10 | `POP_EXTRA` | bit | NO |  |  |
| 11 | `POP_CUSTO_EXTRA_OF` | bit | NO |  |  |

**PK**: `POP_P_ID, POP_P_P_ID`

**FKs declared (out)**:
- `POP_P_ID` → `PRODUTO.P_ID`
- `POP_P_P_ID` → `PRODUTO.P_ID`


**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `POP_P_ID` | `POP_P_P_ID` | `POP_CORES` | `POP_TOPOS` | `POP_LATERAIS` | `POP_QUINAS` | `POP_CASCO` | `POP_GOLA` |
|---|---|---|---|---|---|---|---|
| 20155 | 20560 | false | false | false | false | false | false |
| 20155 | 20577 | true | true | true | true | true | true |
| 20155 | 20578 | true | true | true | true | true | true |

---

### `PRODUTO_CAMADA` — *16 229 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `CAM_ID` | int | NO |  | **PK** |
| 2 | `CAM_P_ID` | int | NO |  | FK → `PRODUTO.P_ID` |
| 3 | `CAM_TPCAM_ID` | int | NO |  | FK → `PRODUTO_CAMADA_TIPO.TPCAM_ID` |
| 4 | `CAM_DESCRICAO` | nvarchar(max) | YES |  |  |
| 5 | `CAM_SEQUENCIA` | int | NO |  |  |

**PK**: `CAM_ID`

**FKs declared (out)**:
- `CAM_P_ID` → `PRODUTO.P_ID`
- `CAM_TPCAM_ID` → `PRODUTO_CAMADA_TIPO.TPCAM_ID`


**Implicit relations** _(by column naming)_:
- `CAM_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `CAM_ID` | `CAM_P_ID` | `CAM_TPCAM_ID` | `CAM_DESCRICAO` | `CAM_SEQUENCIA` |
|---|---|---|---|---|
| 20772 | 20062 | 1 | Pre Gel | 1 |
| 20773 | 20062 | 1 | Carbono 200 | 2 |
| 20774 | 20062 | 1 | Roving 50 | 3 |

---

### `PRODUTO` — *14 016 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `P_ID` | int | NO |  | **PK** |
| 2 | `P_NOME` | nvarchar(max) | NO |  |  |
| 3 | `P_NOME_EN` | nvarchar(max) | YES |  |  |
| 4 | `P_DESCRICAO` | nvarchar(max) | YES |  |  |
| 5 | `P_PRECOCUSTO` | float | NO |  |  |
| 6 | `P_PRECOVENDA` | float | NO |  |  |
| 7 | `P_COEFICIENTE` | float | NO |  |  |
| 8 | `P_STOCK` | float | NO |  |  |
| 9 | `P_STOCKMIN` | float | NO |  |  |
| 10 | `P_NECESSIDADES` | float | NO |  |  |
| 11 | `P_CONVESAO` | float | NO |  |  |
| 12 | `P_MEDIDA` | nvarchar(max) | YES |  |  |
| 13 | `P_PESOLAM` | float | NO |  |  |
| 14 | `P_PESOACAB` | float | NO |  |  |
| 15 | `P_MPLAMINAGEM` | float | NO |  |  |
| 16 | `P_MODLAMINAGEM` | float | NO |  |  |
| 17 | `P_MPACABAMENTO` | float | NO |  |  |
| 18 | `P_MODACABAMENTO` | float | NO |  |  |
| 19 | `P_QTDDECK` | float | NO |  |  |
| 20 | `P_QTDCASCO` | float | NO |  |  |
| 21 | `P_FABRICOINTERNO` | bit | NO |  |  |
| 22 | `P_QTDENCOMENDA` | float | NO |  |  |
| 23 | `P_DATACRIACAO` | smalldatetime | YES |  |  |
| 24 | `P_IMAGEM` | nvarchar(max) | YES |  |  |
| 25 | `P_ACTIVO` | bit | NO |  |  |
| 26 | `P_NP_ID` | int | YES |  |  |
| 27 | `P_TAM_ID` | int | YES |  |  |
| 28 | `P_TP_ID` | int | YES |  |  |
| 29 | `P_M_ID` | int | YES |  |  |
| 30 | `P_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 31 | `P_PCONT_ID` | int | YES |  |  |
| 32 | `P_E_ID` | int | YES |  |  |
| 33 | `P_PONTO_ENCOMENDA` | int | NO |  |  |
| 34 | `P_UNI_ID` | int | YES |  |  |
| 35 | `P_LOJA` | bit | NO |  |  |
| 36 | `P_DESCRICAO_TECNICA` | nvarchar(max) | YES |  |  |
| 37 | `P_TEM_STOCK` | bit | NO |  |  |
| 38 | `P_COD_PAUTAL` | nvarchar(max) | NO |  |  |
| 39 | `P_TEMPO_PREPARACAO` | float | NO |  |  |
| 40 | `P_CRIADOR` | nvarchar(max) | YES |  |  |
| 41 | `P_ACTUALIZADOR` | nvarchar(max) | YES |  |  |
| 42 | `P_DATAACTUALIZACAO` | smalldatetime | YES |  |  |
| 43 | `P_TEMPO_SOLDA` | float | NO |  |  |
| 44 | `P_TEMPO_MONTAGEM` | float | NO |  |  |
| 45 | `P_QTDDECK_REAL` | float | NO |  |  |
| 46 | `P_QTDCASCO_REAL` | float | NO |  |  |
| 47 | `P_QTDDECK_REAL_TRANS` | float | NO |  |  |
| 48 | `P_QTDCASCO_REAL_TRANS` | float | NO |  |  |
| 49 | `P_PERC_TOPO_FR` | float | NO |  |  |
| 50 | `P_PERC_TOPO_TR` | float | NO |  |  |
| 51 | `P_PERC_LATERAL_FR` | float | NO |  |  |
| 52 | `P_PERC_LATERAL_TR` | float | NO |  |  |
| 53 | `P_PERC_QUINAS` | float | NO |  |  |
| 54 | `P_PRECODEALER` | float | NO |  |  |
| 55 | `P_FOLHA_ENC` | bit | NO |  |  |
| 56 | `P_DESCONTINUADO` | bit | NO |  |  |
| 57 | `P_CUSTO_CACHE` | float | YES |  |  |
| 58 | `P_PL_ID` | int | YES |  |  |
| 59 | `P_MODELO_COLORDESIGNER` | varchar(50) | YES |  |  |
| 60 | `P_DESENVOLVIMENTO` | bit | NO |  |  |
| 61 | `P_TP_ID_DISCIPLINA` | int | YES |  |  |
| 62 | `P_PECAS_CICLO` | int | NO |  |  |
| 63 | `P_CICLO_2PX` | bit | NO |  |  |
| 64 | `P_CICLO_TEMPO` | float | NO |  |  |
| 65 | `P_CICLO_PRENSA` | bit | NO |  |  |
| 66 | `P_QTD_MONTAGEM` | int | NO |  |  |
| 67 | `P_SET_TOPOS` | bit | NO |  |  |
| 68 | `P_SET_LATERAIS` | bit | NO |  |  |
| 69 | `P_SET_QUINAS` | bit | NO |  |  |
| 70 | `P_SET_CASCO` | bit | NO |  |  |
| 71 | `P_TEMPO_ESPERA` | int | NO |  |  |
| 72 | `P_SET_GOLA` | bit | NO |  |  |
| 73 | `P_SET_RISCA` | bit | NO |  |  |
| 74 | `P_PRECO_TEMP` | float | NO |  |  |
| 75 | `P_QTD_TOPOS` | float | NO |  |  |
| 76 | `P_QTD_QUINAS` | float | NO |  |  |
| 77 | `P_QTD_LATERAIS` | float | NO |  |  |
| 78 | `P_L_ID` | int | YES |  |  |
| 79 | `P_DIF_IDEAL_PA_D` | float | NO |  |  |
| 80 | `P_DIF_IDEAL_PA_LX` | float | NO |  |  |
| 81 | `P_DIF_IDEAL_LX_ACAB` | float | NO |  |  |
| 82 | `P_MO` | float | NO |  |  |
| 83 | `P_MP` | float | NO |  |  |
| 84 | `P_MS` | float | NO |  |  |
| 85 | `P_MERC` | float | NO |  |  |
| 86 | `P_SERV` | float | NO |  |  |
| 87 | `P_GGF` | float | NO |  |  |
| 88 | `P_COMPRIMENTO` | float | NO |  |  |
| 89 | `P_LARGURA` | float | NO |  |  |
| 90 | `P_ALTURA` | float | NO |  |  |
| 91 | `P_URL_IMG_PROD` | nvarchar(max) | YES |  |  |
| 92 | `P_RESINA_MIX` | bit | NO |  |  |
| 93 | `P_SAIDAS_AUTO` | int | NO |  |  |
| 94 | `P_UNI_ID_MOVIMENTOS` | int | YES |  |  |
| 95 | `P_UNI_MOV_FACTOR` | float | YES |  |  |
| 96 | `P_PERC_QUINAS_TR` | float | NO |  |  |
| 97 | `P_PERC_GOLA` | float | NO |  |  |
| 98 | `P_STOCK_LINHA` | bit | NO |  |  |
| 99 | `P_QTD_RESINA` | float | NO |  |  |
| 100 | `P_REF_UNIV` | nvarchar(max) | YES |  |  |
| 101 | `P_COLOR` | nvarchar(max) | YES |  |  |
| 102 | `P_3D` | nvarchar(max) | YES |  |  |
| 103 | `P_ARM_ID` | int | YES |  |  |
| 104 | `P_NCORES` | int | NO |  |  |
| 105 | `P_GERA_OF` | bit | NO |  |  |
| 106 | `P_ATRIB_ID_DESIGN` | int | YES |  |  |
| 107 | `P_EAN` | decimal | YES |  |  |
| 108 | `P_E_ID_RESP` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 109 | `P_E_ID_CRIADOR` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 110 | `P_DESCRICAO_EN` | nvarchar(max) | YES |  |  |
| 111 | `P_PESOLAM_UPD` | date | YES |  |  |
| 112 | `P_PESOACAB_UPD` | date | YES |  |  |
| 113 | `P_QTDDECK_REAL_UPD` | date | YES |  |  |
| 114 | `P_QTDCASCO_REAL_UPD` | date | YES |  |  |
| 115 | `P_PRECOVENDA_INTERNACIONAL` | float | NO |  |  |
| 116 | `P_NUM_CICLOS_DIA` | int | NO |  |  |
| 117 | `P_CO2` | float | NO |  |  |
| 118 | `P_PRECO_TEMP_INFLACIONADO` | float | NO |  |  |
| 119 | `P_CO2_DATA_ALTERADO` | date | YES |  |  |
| 120 | `P_CO2_OBSERVACOES` | nvarchar(max) | NO |  |  |
| 121 | `P_PESO_M2` | float | NO |  |  |

**PK**: `P_ID`

**FKs declared (out)**:
- `P_E_ID_CRIADOR` → `ENTIDADE.E_ID`
- `P_P_ID` → `PRODUTO.P_ID`
- `P_E_ID_RESP` → `ENTIDADE.E_ID`

**FKs declared (in)** — *24 references*:
- `AgenteEncomendaProduto.codProduto`
- `ALARM.ALARM_P_ID`
- `BOATCHOOSER_ANSWER_PRODUTO.BCAP_PRODUTO_ID`
- `ENT_CONFIG.ECONF_P_ID_MODELO`
- `ENT_CONFIG.ECONF_P_ID_ACESSORIO`
- `FASES_PRODUCAO.FP_P_ID`
- `LISTA_PRODUTO.LP_P_ID`
- `OF_VENDA.OFV_P_ID`
- `ORDEMFABRICO.OF_P_ID`
- `ORDEMFABRICO.OF_P_ID_CDECK`
- `ORDEMFABRICO.OF_P_ID_CCASCO`
- `PLANO.PL_P_ID`
- `PRODUTO_ATTACH.AT_P_ID`
- `PRODUTO_CAMADA.CAM_P_ID`
- `PRODUTO_COEFICIENTE.PCOEF_P_ID`
- `PRODUTO_COMPONENTE.COMP_P_ID`
- `PRODUTO_COMPONENTE.COMP_P_P_ID`
- `PRODUTO_ENTIDADE.PF_P_ID`
- `PRODUTO_FASE.PRODF_P_ID`
- `PRODUTO_OPCOES.POP_P_ID`
- … *(+4 more)*

**Implicit relations** _(by column naming)_:
- `P_ID` → likely `PROC_AREA_FONTE`
- `P_NP_ID` → likely _(no obvious target)_
- `P_TAM_ID` → likely _(no obvious target)_
- `P_TP_ID` → likely _(no obvious target)_
- `P_M_ID` → likely _(no obvious target)_
- `P_PCONT_ID` → likely _(no obvious target)_
- `P_E_ID` → likely _(no obvious target)_
- `P_UNI_ID` → likely _(no obvious target)_
- `P_PL_ID` → likely _(no obvious target)_
- `P_L_ID` → likely _(no obvious target)_
- `P_ARM_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 121 cols)*:

| `P_ID` | `P_NOME` | `P_NOME_EN` | `P_DESCRICAO` | `P_PRECOCUSTO` | `P_PRECOVENDA` | `P_COEFICIENTE` | `P_STOCK` |
|---|---|---|---|---|---|---|---|
| 20060 | K2 E (0) | — |  | 5.4836800000000006 | 0.0 | 0.0 | 0.0 |
| 20061 | K4 G L80 | — |  | -15.2887025 | 0.0 | 0.0 | -73.0 |
| 20062 | K4 SCS | — |  | 19.2297304 | 0.0 | 0.0 | 1.0 |

---

### `PRODUTO_ENTIDADE` — *7 687 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PF_P_ID` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |
| 2 | `PF_E_ID` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |
| 3 | `PF_QTD_MIN_ENC` | float | NO |  |  |
| 4 | `PF_PRECO` | float | NO |  |  |
| 5 | `PF_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 6 | `PF_CODIGO` | nvarchar(max) | YES |  |  |
| 7 | `PF_DESCRICAO` | nvarchar(max) | YES |  |  |
| 8 | `PF_UNI_ID` | int | YES |  | FK → `UNIDADE.UNI_ID` |
| 9 | `PF_CONVERSAO` | float | NO |  |  |

**PK**: `PF_P_ID, PF_E_ID`

**FKs declared (out)**:
- `PF_E_ID` → `ENTIDADE.E_ID`
- `PF_P_ID` → `PRODUTO.P_ID`
- `PF_UNI_ID` → `UNIDADE.UNI_ID`


**Sample (TOP 3)** *(showing 8 of 9 cols)*:

| `PF_P_ID` | `PF_E_ID` | `PF_QTD_MIN_ENC` | `PF_PRECO` | `PF_OBSERVACOES` | `PF_CODIGO` | `PF_DESCRICAO` | `PF_UNI_ID` |
|---|---|---|---|---|---|---|---|
| 20248 | 20423 | 0.0 | 0.0 |  |  | Pano - Rosa | 12 |
| 20248 | 21489 | 0.0 | 0.0 |  |  | Pano - Rosa | 12 |
| 20253 | 20288 | 0.0 | 63.5 |  | — | Madeira | 12 |

---

### `PRODUTO_ATTACH` — *3 858 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `AT_ID` | int | NO |  | **PK** |
| 2 | `AT_NOME` | nvarchar(max) | NO |  |  |
| 3 | `AT_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `AT_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 5 | `AT_IMAGE` | nvarchar(max) | NO |  |  |
| 6 | `AT_ATT_ID` | int | YES |  | FK → `PRODUTO_ATTACH_TIPO.ATT_ID` |
| 7 | `AT_EOBS_ID` | int | YES |  | FK → `ENTIDADE_OBS.EOBS_ID` |

**PK**: `AT_ID`

**FKs declared (out)**:
- `AT_EOBS_ID` → `ENTIDADE_OBS.EOBS_ID`
- `AT_P_ID` → `PRODUTO.P_ID`
- `AT_ATT_ID` → `PRODUTO_ATTACH_TIPO.ATT_ID`


**Implicit relations** _(by column naming)_:
- `AT_ID` → likely `ATRIB_ATRIB`

**Sample (TOP 3)**:

| `AT_ID` | `AT_NOME` | `AT_DESCRICAO` | `AT_P_ID` | `AT_IMAGE` | `AT_ATT_ID` | `AT_EOBS_ID` |
|---|---|---|---|---|---|---|
| 7 | 1.jpg |  | 20247 | \\server\Documents\imagens_BD\Produto... | 1 | — |
| 8 | 2.jpg |  | 20247 | \\server\Documents\imagens_BD\Produto... | 1 | — |
| 9 | 1.jpg |  | 20256 | \\server\Documents\imagens_BD\Produto... | 1 | — |

---

### `PRODUTO_LISTA_ITEMS` — *960 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PLI_ID` | int | NO |  | **PK** |
| 2 | `PLI_DESCR` | nvarchar(max) | NO |  |  |
| 3 | `PLI_PL_ID` | int | NO |  | FK → `PRODUTO_LISTA.PL_ID` |
| 4 | `PLI_SEQUENCIA` | int | NO |  |  |
| 5 | `PLI_FP_ID` | int | YES |  |  |
| 6 | `PLI_FP_ID_CHK` | int | NO |  |  |
| 7 | `PLI_CULPA_CHEFE` | bit | NO |  |  |
| 8 | `PLI_MOLDE_REPARAR` | bit | NO |  |  |
| 9 | `PLI_DESCR_EN` | nvarchar(max) | NO |  |  |

**PK**: `PLI_ID`

**FKs declared (out)**:
- `PLI_PL_ID` → `PRODUTO_LISTA.PL_ID`


**Implicit relations** _(by column naming)_:
- `PLI_ID` → likely _(no obvious target)_
- `PLI_FP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 9 cols)*:

| `PLI_ID` | `PLI_DESCR` | `PLI_PL_ID` | `PLI_SEQUENCIA` | `PLI_FP_ID` | `PLI_FP_ID_CHK` | `PLI_CULPA_CHEFE` | `PLI_MOLDE_REPARAR` |
|---|---|---|---|---|---|---|---|
| 24 | Conferir a proa, verificar se têm bol... | 2 | 1 | 1 | 8 | true | false |
| 25 | Conferir a ré, verificar se têm bolhas  | 2 | 2 | 1 | 8 | true | false |
| 26 | Procurar se existe alguma zona deslam... | 2 | 3 | 1 | 8 | true | false |

---

### `PRODUTO_TIPO` — *421 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TP_ID` | int | NO |  | **PK** |
| 2 | `TP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TP_NOME_EN` | nvarchar(max) | NO |  |  |
| 4 | `TP_DESCRICAO` | nvarchar(max) | YES |  |  |
| 5 | `TP_TP_ID` | int | YES |  | FK → `PRODUTO_TIPO.TP_ID` |
| 6 | `TP_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 7 | `TP_EDITAVEL` | bit | NO |  |  |
| 8 | `TP_ENT_OWNER` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 9 | `TP_ENT_OWNER_OBJ_OF` | int | NO |  |  |
| 10 | `TP_ENT_OWNER_OBJ_VAL` | float | NO |  |  |
| 11 | `TP_IMAGEM` | nvarchar(1024) | YES |  |  |

**PK**: `TP_ID`

**FKs declared (out)**:
- `TP_ENT_OWNER` → `ENTIDADE.E_ID`
- `TP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `TP_TP_ID` → `PRODUTO_TIPO.TP_ID`

**FKs declared (in)** — *6 references*:
- `COMUNICACAO_PRODUTO_TIPO.COMTP_TP_ID`
- `DOC_PRODUTO_TIPO.produto_tipo_tp_id`
- `ENT_TP_PROD.ETP_TP_ID`
- `INTERVALO.INTERVALO_TP_ID`
- `PRODUTO_TIPO.TP_TP_ID`
- `ProdutoTipoAcessorio.codTipo`

**Implicit relations** _(by column naming)_:
- `TP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `TP_ID` | `TP_NOME` | `TP_NOME_EN` | `TP_DESCRICAO` | `TP_TP_ID` | `TP_FP_ID` | `TP_EDITAVEL` | `TP_ENT_OWNER` |
|---|---|---|---|---|---|---|---|
| 1 | Kayak |  |  | — | 46 | false | — |
| 2 | Serralharia/Acessorios |  |  | — | 46 | false | — |
| 6 | Canoe Sprint Ep. | EC | — | 259 | 46 | false | — |

---

### `PRODUTO_MODELO` — *319 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `M_ID` | int | NO |  | **PK** |
| 2 | `M_NOME` | nvarchar(max) | NO |  |  |
| 3 | `M_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `M_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `CENTRO_MODELOS_QTD.CM_M_ID`
- `MEDIDAS.MED_M_ID`

**Implicit relations** _(by column naming)_:
- `M_ID` → likely `MOLDES`

**Sample (TOP 3)**:

| `M_ID` | `M_NOME` | `M_DESCRICAO` |
|---|---|---|
| 3 | Vanquish |  |
| 4 | Strozzy |  |
| 5 | Navigator |  |

---

### `MEDIDAS` — *165 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MED_ID` | int | NO |  | **PK** |
| 2 | `MED_NP_ID` | int | NO |  | FK → `PRODUTO_NUMERO_POCOS.NP_ID` |
| 3 | `MED_M_ID` | int | NO |  | FK → `PRODUTO_MODELO.M_ID` |
| 4 | `MED_TAM_ID` | int | NO |  | FK → `PRODUTO_TAMANHO.TAM_ID` |
| 5 | `MED_OBS` | nvarchar(max) | YES |  |  |
| 6 | `MED_MEDIDA` | float | NO |  |  |
| 7 | `MED_OBSERVACOES` | nvarchar(max) | YES |  |  |

**PK**: `MED_ID`

**FKs declared (out)**:
- `MED_M_ID` → `PRODUTO_MODELO.M_ID`
- `MED_NP_ID` → `PRODUTO_NUMERO_POCOS.NP_ID`
- `MED_TAM_ID` → `PRODUTO_TAMANHO.TAM_ID`


**Implicit relations** _(by column naming)_:
- `MED_ID` → likely `MEDIDAS`

**Sample (TOP 3)**:

| `MED_ID` | `MED_NP_ID` | `MED_M_ID` | `MED_TAM_ID` | `MED_OBS` | `MED_MEDIDA` | `MED_OBSERVACOES` |
|---|---|---|---|---|---|---|
| 2 | 1 | 42 | 4 | Proa e base | 244.5 | — |
| 3 | 1 | 42 | 4 | x | 47.5 | — |
| 4 | 1 | 42 | 3 | Proa e base | 244.5 | — |

---

### `ArtigosGrupos` — *141 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `id_orig` | int | NO |  | **PK** |
| 2 | `id_virtual` | int | NO |  | **PK** |
| 3 | `nome` | varchar(50) | YES |  |  |

**PK**: `id_orig, id_virtual`

**FKs declared (out)**: _(none)_


**Sample (TOP 3)**:

| `id_orig` | `id_virtual` | `nome` |
|---|---|---|
| 21513 | 90012 | Pants |
| 21514 | 90012 | Pants |
| 21515 | 90012 | Pants |

---

### `ProdutoTipoAcessorio` — *88 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codTipo` | int | NO |  | **PK** FK → `PRODUTO_TIPO.TP_ID` |
| 2 | `codProduto` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |

**PK**: `codTipo, codProduto`

**FKs declared (out)**:
- `codProduto` → `PRODUTO.P_ID`
- `codTipo` → `PRODUTO_TIPO.TP_ID`


**Sample (TOP 3)**:

| `codTipo` | `codProduto` |
|---|---|
| 6 | 20249 |
| 6 | 20257 |
| 6 | 20259 |

---

### `PRODUTO_FASE_LINK` — *29 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PRODFL_PRODF_ID_PROX` | int | NO |  | **PK** FK → `PRODUTO_FASE.PRODF_ID` |
| 2 | `PRODFL_PRODF_ID_ANT` | int | NO |  | **PK** FK → `PRODUTO_FASE.PRODF_ID` |
| 3 | `PRODFL_SEQUENCIA` | int | NO |  |  |

**PK**: `PRODFL_PRODF_ID_PROX, PRODFL_PRODF_ID_ANT`

**FKs declared (out)**:
- `PRODFL_PRODF_ID_PROX` → `PRODUTO_FASE.PRODF_ID`
- `PRODFL_PRODF_ID_ANT` → `PRODUTO_FASE.PRODF_ID`


**Sample (TOP 3)**:

| `PRODFL_PRODF_ID_PROX` | `PRODFL_PRODF_ID_ANT` | `PRODFL_SEQUENCIA` |
|---|---|---|
| 26914 | 26925 | 1 |
| 26915 | 26914 | 1 |
| 26916 | 26918 | 1 |

---

### `PRODUTO_LISTA` — *26 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PL_ID` | int | NO |  | **PK** |
| 2 | `PL_DESCR` | nvarchar(max) | YES |  |  |
| 3 | `PL_DATA` | smalldatetime | NO |  |  |
| 4 | `PL_ACTIVO` | bit | NO |  |  |
| 5 | `PL_FP_ID` | int | YES |  |  |

**PK**: `PL_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `PRODUTO_LISTA_ITEMS.PLI_PL_ID`

**Implicit relations** _(by column naming)_:
- `PL_ID` → likely `PLANEAMENTO_DIARIO`
- `PL_FP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PL_ID` | `PL_DESCR` | `PL_DATA` | `PL_ACTIVO` | `PL_FP_ID` |
|---|---|---|---|---|
| 1 | K2 | 2013-10-07 10:07 | true | — |
| 2 | K1 | 2013-10-07 11:08 | true | — |
| 3 |  | 2013-10-10 11:18 | false | — |

---

### `UNIDADE` — *22 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `UNI_ID` | int | NO |  | **PK** |
| 2 | `UNI_NOME` | nvarchar(50) | NO |  |  |

**PK**: `UNI_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `PRODUTO_ENTIDADE.PF_UNI_ID`

**Implicit relations** _(by column naming)_:
- `UNI_ID` → likely `UNIDADE`

**Sample (TOP 3)**:

| `UNI_ID` | `UNI_NOME` |
|---|---|
| 1 | Mts |
| 2 | Mts² |
| 3 | Placa |

---

### `PRODUTO_TAMANHO` — *18 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TAM_ID` | int | NO |  | **PK** |
| 2 | `TAM_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TAM_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `TAM_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `CENTRO_MODELOS_QTD.CM_TAM_ID`
- `MEDIDAS.MED_TAM_ID`

**Implicit relations** _(by column naming)_:
- `TAM_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TAM_ID` | `TAM_NOME` | `TAM_DESCRICAO` |
|---|---|---|
| 1 | XXL | — |
| 2 | L | — |
| 3 | ML | — |

---

### `PRODUTO_COEFICIENTE` — *15 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PCOEF_ID` | int | NO |  | **PK** |
| 2 | `PCOEF_P_ID` | int | NO |  | FK → `PRODUTO.P_ID` |
| 3 | `PCOEF_DATA` | smalldatetime | NO |  |  |
| 4 | `PCOEF_VALOR_HCOEF` | float | NO |  |  |
| 5 | `PCOEF_ACTIVO` | bit | NO |  |  |
| 6 | `PCOEF_VALOR_HORA` | float | NO |  |  |

**PK**: `PCOEF_ID`

**FKs declared (out)**:
- `PCOEF_P_ID` → `PRODUTO.P_ID`


**Implicit relations** _(by column naming)_:
- `PCOEF_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PCOEF_ID` | `PCOEF_P_ID` | `PCOEF_DATA` | `PCOEF_VALOR_HCOEF` | `PCOEF_ACTIVO` | `PCOEF_VALOR_HORA` |
|---|---|---|---|---|---|
| 1 | 20796 | 2017-01-01 00:00 | 4.75 | false | 11.418 |
| 2 | 20798 | 2017-01-01 00:00 | 1.42 | false | 8.113 |
| 3 | 20797 | 2017-01-01 00:00 | 1.35 | false | 8.388 |

---

### `PRODUTO_CAMADA_TIPO` — *12 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TPCAM_ID` | int | NO |  | **PK** |
| 2 | `TPCAM_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TPCAM_ORDEM` | float | NO |  |  |
| 4 | `TPCAM_TPCAM_ID_PAI` | int | YES |  | FK → `PRODUTO_CAMADA_TIPO.TPCAM_ID` |

**PK**: `TPCAM_ID`

**FKs declared (out)**:
- `TPCAM_TPCAM_ID_PAI` → `PRODUTO_CAMADA_TIPO.TPCAM_ID`

**FKs declared (in)** — *4 references*:
- `OF_FP.OFFP_TPCAM_ID`
- `PRODUTO_CAMADA.CAM_TPCAM_ID`
- `PRODUTO_CAMADA_TIPO.TPCAM_TPCAM_ID_PAI`
- `PRODUTO_FASE.PRODF_TPCAM_ID`

**Implicit relations** _(by column naming)_:
- `TPCAM_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TPCAM_ID` | `TPCAM_NOME` | `TPCAM_ORDEM` | `TPCAM_TPCAM_ID_PAI` |
|---|---|---|---|
| 1 | Deck | 1.0 | — |
| 2 | Casco | 2.0 | — |
| 3 | Boia esquerda | 1.0 | — |

---

### `PRODUTO_CONTABILIDADE_TIPO` — *10 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PCONT_ID` | int | NO |  | **PK** |
| 2 | `PCONT_NOME` | nvarchar(max) | NO |  |  |
| 3 | `PCONT_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `PCONT_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `PCONT_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PCONT_ID` | `PCONT_NOME` | `PCONT_DESCRICAO` |
|---|---|---|
| 1 | Matéria Prima | — |
| 2 | Matéria Subsidiaria | — |
| 3 | Serviços | — |

---

### `PRODUTO_ESTADO` — *7 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EST_ID` | int | NO |  | **PK** |
| 2 | `EST_NOME` | nvarchar(max) | NO |  |  |
| 3 | `EST_EST_ID` | int | YES |  | FK → `PRODUTO_ESTADO.EST_ID` |

**PK**: `EST_ID`

**FKs declared (out)**:
- `EST_EST_ID` → `PRODUTO_ESTADO.EST_ID`

**FKs declared (in)** — *1 references*:
- `PRODUTO_ESTADO.EST_EST_ID`

**Implicit relations** _(by column naming)_:
- `EST_ID` → likely `EstadoOFAgente`

**Sample (TOP 3)**:

| `EST_ID` | `EST_NOME` | `EST_EST_ID` |
|---|---|---|
| 1 | Em Uso | — |
| 2 | A Reparar | — |
| 3 | Para Abate | — |

---

### `PRODUTO_NUMERO_POCOS` — *7 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `NP_ID` | int | NO |  | **PK** |
| 2 | `NP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `NP_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `NP_NUM` | int | YES |  |  |

**PK**: `NP_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `CENTRO_MODELOS_QTD.CM_NP_ID`
- `MEDIDAS.MED_NP_ID`

**Implicit relations** _(by column naming)_:
- `NP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `NP_ID` | `NP_NOME` | `NP_DESCRICAO` | `NP_NUM` |
|---|---|---|---|
| 1 | K1 | Uma pessoa | 1 |
| 2 | K2 | Duas Pessoas | 2 |
| 3 | K4 | Quatro Pessoas | 4 |

---

### `COMPONENTE_TIPO` — *4 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TPCOMP_ID` | int | NO |  | **PK** |
| 2 | `TPCOMP_NOME` | nvarchar(max) | NO |  |  |

**PK**: `TPCOMP_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `PRODUTO_COMPONENTE.COMP_TPCOMP_ID`

**Implicit relations** _(by column naming)_:
- `TPCOMP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TPCOMP_ID` | `TPCOMP_NOME` |
|---|---|
| 1 | Associados |
| 2 | Componentes |
| 3 | Opcionais |

---

### `PRODUTO_ATTACH_TIPO` — *2 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ATT_ID` | int | NO |  | **PK** |
| 2 | `ATT_DESC` | nvarchar(max) | NO |  |  |

**PK**: `ATT_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `PRODUTO_ATTACH.AT_ATT_ID`

**Implicit relations** _(by column naming)_:
- `ATT_ID` → likely `ATTACH_TIPO`

**Sample (TOP 3)**:

| `ATT_ID` | `ATT_DESC` |
|---|---|
| 1 | Imagem |
| 2 | Documentos |

---

### `PRODUTO_PROB_CAUSA_SOL` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PP_ID` | int | NO |  | **PK** |
| 2 | `PP_PCS_ID` | int | NO |  | FK → `PROB_CAUSA_SOL.PCS_ID` |
| 3 | `PP_PCS_PCS_ID` | int | YES |  | FK → `PROB_CAUSA_SOL.PCS_ID` |
| 4 | `PP_DATA` | smalldatetime | NO |  |  |

**PK**: `PP_ID`

**FKs declared (out)**:
- `PP_PCS_ID` → `PROB_CAUSA_SOL.PCS_ID`
- `PP_PCS_PCS_ID` → `PROB_CAUSA_SOL.PCS_ID`


**Implicit relations** _(by column naming)_:
- `PP_ID` → likely _(no obvious target)_

**Sample**: _(table empty or unreadable)_

---

<a id="operaes-fases-e-planeamento"></a>
## Operações, fases e planeamento

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `DIAS_TRABALHO` | 15 637 | 2 | DTRB_ID | 0 | 0 |
| `COMUNICACAO_FASES_PRODUCAO` | 3 664 | 3 | — | 3 | 0 |
| `PLANO` | 2 760 | 13 | PL_ID | 3 | 0 |
| `Z_PrevisaoPlano` | 320 | 12 | — | 0 | 0 |
| `LACAGEM` | 86 | 5 | LAC_ID | 0 | 0 |
| `FASES_PRODUCAO` | 71 | 20 | FP_ID | 2 | 19 |
| `PLANEAMENTO_DIARIO` | 64 | 6 | PlaneamentoDiarioId | 1 | 0 |
| `INTERVALO` | 52 | 4 | INTERVALO_ID | 1 | 0 |
| `FERIAS` | 29 | 2 | — | 0 | 0 |
| `DIAS_FERIADOS_FERIAS` | 14 | 7 | DFF_ID | 0 | 0 |
| `FP_FP` | 11 | 3 | FPFP_FP_ID, FPFP_FP_FP_ID | 2 | 0 |
| `ESTACAO` | 5 | 4 | EST_ID | 0 | 0 |
| `TURNO` | 3 | 3 | TURN_ID | 0 | 1 |

### `DIAS_TRABALHO` — *15 637 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DTRB_ID` | int | NO |  | **PK** |
| 2 | `DTRB_DATA` | smalldatetime | NO |  |  |

**PK**: `DTRB_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `DTRB_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `DTRB_ID` | `DTRB_DATA` |
|---|---|
| 341 | 2016-01-04 00:00 |
| 342 | 2016-01-05 00:00 |
| 343 | 2016-01-06 00:00 |

---

### `COMUNICACAO_FASES_PRODUCAO` — *3 664 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `COMFP_COM_ID` | int | NO |  | FK → `COMUNICACAO.COM_ID` |
| 2 | `COMFP_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 3 | `COMFP_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |

**PK**: _(none declared)_

**FKs declared (out)**:
- `COMFP_COM_ID` → `COMUNICACAO.COM_ID`
- `COMFP_E_ID` → `ENTIDADE.E_ID`
- `COMFP_FP_ID` → `FASES_PRODUCAO.FP_ID`


**Sample (TOP 3)**:

| `COMFP_COM_ID` | `COMFP_FP_ID` | `COMFP_E_ID` |
|---|---|---|
| 1226 | 3 | 31609 |
| 1226 | 8 | 31654 |
| 1226 | 33 | 25128 |

---

### `PLANO` — *2 760 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PL_ID` | int | NO |  | **PK** |
| 2 | `PL_ANO` | int | NO |  |  |
| 3 | `PL_SEMANA` | int | NO |  |  |
| 4 | `PL_QTD` | float | NO |  |  |
| 5 | `PL_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 6 | `PL_P_ID` | int | NO |  | FK → `PRODUTO.P_ID` |
| 7 | `PL_L_ID` | int | NO |  |  |
| 8 | `PL_QTD_SOLDA` | float | NO |  |  |
| 9 | `PL_QTD_MONTAGEM` | float | NO |  |  |
| 10 | `PL_PRODF_ID` | int | YES |  | FK → `PRODUTO_FASE.PRODF_ID` |
| 11 | `PL_TEMPO` | float | NO |  |  |
| 12 | `PL_COMPLETO` | bit | NO |  |  |
| 13 | `PL_QTD_FEITA` | float | NO |  |  |

**PK**: `PL_ID`

**FKs declared (out)**:
- `PL_E_ID` → `ENTIDADE.E_ID`
- `PL_P_ID` → `PRODUTO.P_ID`
- `PL_PRODF_ID` → `PRODUTO_FASE.PRODF_ID`


**Implicit relations** _(by column naming)_:
- `PL_ID` → likely `PLANEAMENTO_DIARIO`
- `PL_L_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 13 cols)*:

| `PL_ID` | `PL_ANO` | `PL_SEMANA` | `PL_QTD` | `PL_E_ID` | `PL_P_ID` | `PL_L_ID` | `PL_QTD_SOLDA` |
|---|---|---|---|---|---|---|---|
| 60 | 2009 | 30 | 80.0 | 20378 | 21417 | 11 | 0.0 |
| 62 | 2009 | 30 | 41.0 | 20378 | 21419 | 11 | 0.0 |
| 64 | 2009 | 30 | 12.0 | 20378 | 20531 | 11 | 0.0 |

---

### `Z_PrevisaoPlano` — *320 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `OF` | int | NO |  |  |
| 2 | `Modelo` | nvarchar(max) | NO |  |  |
| 3 | `Cliente` | nvarchar(max) | NO |  |  |
| 4 | `Referencia` | nvarchar(max) | YES |  |  |
| 5 | `Dia` | int | NO |  |  |
| 6 | `Laminador` | int | NO |  |  |
| 7 | `Turno` | int | NO |  |  |
| 8 | `Molde` | int | NO |  |  |
| 9 | `Dt_Trans` | smalldatetime | NO |  |  |
| 10 | `Dt_Lam` | smalldatetime | NO |  |  |
| 11 | `Dif` | int | NO |  |  |
| 12 | `Cliente_id` | int | YES |  |  |

**PK**: _(none declared)_

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `Cliente_id` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 12 cols)*:

| `OF` | `Modelo` | `Cliente` | `Referencia` | `Dia` | `Laminador` | `Turno` | `Molde` |
|---|---|---|---|---|---|---|---|
| 901996 | Surf Ski 62 L AIR (L) | Nelo Portugal | Cangalho / Fluvial | 5 | 6 | 1 | 70915 |
| 902049 | Surf Ski 62 L AIR (L) | Nelo Portugal | Jonatan / Santander | 6 | 2 | 2 | 70915 |
| 902099 | Surf Ski 62 M WWR (L) | Nelo Portugal | Eliseu / Rental | 5 | 7 | 1 | 70921 |

---

### `LACAGEM` — *86 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `LAC_ID` | int | NO |  | **PK** |
| 2 | `LAC_DESCRICAO` | nvarchar(max) | YES |  |  |
| 3 | `LAC_QTD` | int | NO |  |  |
| 4 | `LAC_DATA_I` | smalldatetime | NO |  |  |
| 5 | `LAC_DATA_F` | smalldatetime | YES |  |  |

**PK**: `LAC_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `LAC_ID` → likely `LACAGEM`

**Sample (TOP 3)**:

| `LAC_ID` | `LAC_DESCRICAO` | `LAC_QTD` | `LAC_DATA_I` | `LAC_DATA_F` |
|---|---|---|---|---|
| 1 | Base K1 III | 150 | 2009-12-18 00:00 | 2009-12-18 16:56 |
| 2 | Base K2 III | 50 | 2009-12-18 00:00 | 2009-12-18 16:55 |
| 3 | Calha III | 15 | 2009-12-18 00:00 | 2009-12-18 16:57 |

---

### `FASES_PRODUCAO` — *71 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `FP_ID` | int | NO |  | **PK** |
| 2 | `FP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `FP_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `FP_SEQUENCIA` | int | NO |  |  |
| 5 | `FP_PRODUCAO` | bit | NO |  |  |
| 6 | `FP_AUTOMATICA` | bit | NO |  |  |
| 7 | `FP_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 8 | `FP_HORA_COEF` | float | NO |  |  |
| 9 | `FP_COR` | varchar(6) | YES |  |  |
| 10 | `FP_LISTA_ATRIBUIDOS` | bit | NO |  |  |
| 11 | `FP_COEF_EXTRA` | bit | NO |  |  |
| 12 | `FP_RETORNOS_POR_TEMPO` | bit | NO |  |  |
| 13 | `FP_P_ID` | int | YES |  | FK → `PRODUTO.P_ID` |
| 14 | `FP_PODE_REPETIR` | bit | NO |  |  |
| 15 | `FP_PLANEAMENTO` | bit | NO |  |  |
| 16 | `FP_ASPNET_ROLES` | nvarchar(max) | YES |  |  |
| 17 | `FP_PRE_REGISTO` | bit | NO |  |  |
| 18 | `FP_VALOR_REF_K1` | float | NO |  |  |
| 19 | `FP_VALOR_REF_K2` | float | NO |  |  |
| 20 | `FP_VALOR_REF_K4` | float | NO |  |  |

**PK**: `FP_ID`

**FKs declared (out)**:
- `FP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `FP_P_ID` → `PRODUTO.P_ID`

**FKs declared (in)** — *19 references*:
- `COMUNICACAO_FASES_PRODUCAO.COMFP_FP_ID`
- `ENT_MOV.MOVENT_FP_ID`
- `ENTIDADE_FASE.EFP_FP_ID`
- `FASES_PRODUCAO.FP_FP_ID`
- `FP_FP.FPFP_FP_ID`
- `FP_FP.FPFP_FP_FP_ID`
- `MOVIMENTO.MOV_FP_ID`
- `OF_ATTACH.ATCH_FP_ID`
- `OF_CHECKLIST.OFCH_FP_ID`
- `OF_CHECKLIST.OFCH_FP_ID_CHK`
- `OF_FP.OFFP_FP_ID`
- `OF_VENDA.OFV_FP_ID`
- `ORDEMFABRICO.OF_FP_ID`
- `PROB_CAUSA_SOL.PCS_FP_ID`
- `PRODUTO_COMPONENTE.COMP_FP_ID`
- `PRODUTO_FASE.PRODF_FP_ID`
- `PRODUTO_TIPO.TP_FP_ID`
- `REP_OF_FP.ROFFP_FP_ID`
- `TH.TH_FASE`

**Implicit relations** _(by column naming)_:
- `FP_ID` → likely `FP_FP`

**Sample (TOP 3)** *(showing 8 of 20 cols)*:

| `FP_ID` | `FP_NOME` | `FP_DESCRICAO` | `FP_SEQUENCIA` | `FP_PRODUCAO` | `FP_AUTOMATICA` | `FP_FP_ID` | `FP_HORA_COEF` |
|---|---|---|---|---|---|---|---|
| 1 | Laminagem | — | 10 | true | false | — | 1.0 |
| 2 | Cura | — | 11 | true | true | — | 1.0 |
| 3 | Corte | — | 13 | true | false | — | 1.0 |

---

### `PLANEAMENTO_DIARIO` — *64 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PlaneamentoDiarioId` | int | NO |  | **PK** |
| 2 | `Dia` | date | NO |  |  |
| 3 | `HoraInicio` | int | NO |  |  |
| 4 | `HoraFim` | int | NO |  |  |
| 5 | `NumeroFuncionarios` | int | NO |  |  |
| 6 | `TransporteId` | int | YES |  | FK → `TRANSPORTE.TR_ID` |

**PK**: `PlaneamentoDiarioId`

**FKs declared (out)**:
- `TransporteId` → `TRANSPORTE.TR_ID`


**Implicit relations** _(by column naming)_:
- `PlaneamentoDiarioId` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PlaneamentoDiarioId` | `Dia` | `HoraInicio` | `HoraFim` | `NumeroFuncionarios` | `TransporteId` |
|---|---|---|---|---|---|
| 1 | 2019-05-27 | 8 | 20 | 4 | 18039 |
| 2 | 2019-05-26 | 8 | 20 | 4 | 18039 |
| 3 | 2019-05-25 | 8 | 20 | 4 | 18039 |

---

### `INTERVALO` — *52 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `INTERVALO_ID` | int | NO |  | **PK** |
| 2 | `INTERVALO_INICIO` | int | NO |  |  |
| 3 | `INTERVALO_FIM` | int | NO |  |  |
| 4 | `INTERVALO_TP_ID` | int | NO |  | FK → `PRODUTO_TIPO.TP_ID` |

**PK**: `INTERVALO_ID`

**FKs declared (out)**:
- `INTERVALO_TP_ID` → `PRODUTO_TIPO.TP_ID`


**Implicit relations** _(by column naming)_:
- `INTERVALO_ID` → likely `INTERVALO`

**Sample (TOP 3)**:

| `INTERVALO_ID` | `INTERVALO_INICIO` | `INTERVALO_FIM` | `INTERVALO_TP_ID` |
|---|---|---|---|
| 8 | 100000 | 199999 | 6 |
| 9 | 901000 | 902999 | 8 |
| 10 | 30000 | 39999 | 7 |

---

### `FERIAS` — *29 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DATA` | smalldatetime | NO |  |  |
| 2 | `TIPO` | nvarchar(max) | NO |  |  |

**PK**: _(none declared)_

**FKs declared (out)**: _(none)_


**Sample (TOP 3)**:

| `DATA` | `TIPO` |
|---|---|
| 2012-02-20 00:00 | Férias |
| 2012-02-21 00:00 | Feriado |
| 2012-04-06 00:00 | Feriado |

---

### `DIAS_FERIADOS_FERIAS` — *14 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DFF_ID` | int | NO |  | **PK** |
| 2 | `DFF_MES` | int | NO |  |  |
| 3 | `DFF_DIA` | int | NO |  |  |
| 4 | `DFF_FIXO` | bit | NO |  |  |
| 5 | `DFF_FERIAS` | bit | NO |  |  |
| 6 | `DFF_FERIADO` | bit | NO |  |  |
| 7 | `DFF_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `DFF_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `DFF_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `DFF_ID` | `DFF_MES` | `DFF_DIA` | `DFF_FIXO` | `DFF_FERIAS` | `DFF_FERIADO` | `DFF_DESCRICAO` |
|---|---|---|---|---|---|---|
| 1 | 1 | 1 | true | false | true | Dia de Ano Novo |
| 2 | 3 | 30 | false | false | true | Sexta-feira Santa |
| 3 | 4 | 1 | false | false | true | Páscoa |

---

### `FP_FP` — *11 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `FPFP_FP_ID` | int | NO |  | **PK** FK → `FASES_PRODUCAO.FP_ID` |
| 2 | `FPFP_FP_FP_ID` | int | NO |  | **PK** FK → `FASES_PRODUCAO.FP_ID` |
| 3 | `FPFP_DESCR` | nvarchar(max) | YES |  |  |

**PK**: `FPFP_FP_ID, FPFP_FP_FP_ID`

**FKs declared (out)**:
- `FPFP_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `FPFP_FP_FP_ID` → `FASES_PRODUCAO.FP_ID`


**Sample (TOP 3)**:

| `FPFP_FP_ID` | `FPFP_FP_FP_ID` | `FPFP_DESCR` |
|---|---|---|
| 1 | 42 | — |
| 3 | 42 | — |
| 4 | 8 | — |

---

### `ESTACAO` — *5 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EST_ID` | int | NO |  | **PK** |
| 2 | `EST_FASE` | int | NO |  |  |
| 3 | `EST_E_ID` | int | NO |  |  |
| 4 | `EST_CODIGO` | int | NO |  |  |

**PK**: `EST_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `EST_ID` → likely `EstadoOFAgente`
- `EST_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EST_ID` | `EST_FASE` | `EST_E_ID` | `EST_CODIGO` |
|---|---|---|---|
| 1 | 1 | 21522 | 1 |
| 2 | 1 | 20343 | 2 |
| 3 | 1 | 20386 | 3 |

---

### `TURNO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TURN_ID` | int | NO |  | **PK** |
| 2 | `TURN_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TURN_SEQUENCIA` | int | NO |  |  |

**PK**: `TURN_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `ORDEMFABRICO.OF_TURN_ID`

**Implicit relations** _(by column naming)_:
- `TURN_ID` → likely `TURNO`

**Sample (TOP 3)**:

| `TURN_ID` | `TURN_NOME` | `TURN_SEQUENCIA` |
|---|---|---|
| 1 | Manhã | 1 |
| 2 | Tarde | 2 |
| 3 | Noite | 3 |

---

<a id="recursos-entidades-equipas-moldes-rh"></a>
## Recursos (entidades, equipas, moldes, RH)

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `ENT_MOV` | 166 119 | 20 | MOVENT_ID | 4 | 0 |
| `ENTIDADE_PHC_FACT` | 100 503 | 8 | — | 1 | 0 |
| `ENT_TP_PROD` | 22 832 | 5 | ETP_E_ID, ETP_TP_ID | 2 | 0 |
| `ENTIDADE` | 8 936 | 95 | E_ID | 5 | 61 |
| `MOLDES_MOV` | 3 673 | 5 | MLDU_ID | 1 | 0 |
| `ENTIDADE_FASE` | 1 269 | 11 | EFP_ID | 2 | 0 |
| `ENTIDADE_MORADA` | 952 | 15 | EM_ID | 3 | 1 |
| `ENTIDADE_PONTOS` | 866 | 13 | EP_ID | 0 | 0 |
| `ENTIDADE_PHC` | 751 | 3 | EPHC_ID | 1 | 1 |
| `ENTIDADE_TREINOS` | 401 | 11 | ETR_ID | 1 | 0 |
| `MOLDES` | 91 | 5 | MLD_ID | 1 | 1 |
| `ENTIDADE_EQUIPA` | 82 | 7 | EEQ_ID | 2 | 0 |
| `ENTIDADE_TIPO` | 36 | 5 | ENT_ID | 1 | 2 |
| `RH_DOC` | 19 | 5 | RHD_ID | 1 | 0 |
| `EQUIPA` | 17 | 4 | EQ_ID | 0 | 2 |
| `ENT_MOV_TIPO` | 15 | 6 | MET_ID | 1 | 2 |
| `MOLDES_TIPO` | 14 | 3 | MLDTP_ID | 0 | 1 |
| `RH_TIPO_DOC` | 6 | 2 | RHTD_ID | 0 | 1 |
| `ENT_TIPO_VINCULO` | 3 | 3 | TV_ID | 0 | 1 |
| `ENTIDADE_MORADA_TIPO` | 3 | 2 | EMT_ID | 0 | 1 |
| `ENT_ENT_PEDIDO_PROVISORIO` | 2 | 5 | EEP_ID | 0 | 0 |
| `ENTIDADE_DADOS` | 1 | 10 | EDADOS_ID | 2 | 0 |
| `RH_FORMACAO` | 1 | 6 | RHF_ID | 0 | 0 |
| `ENT_CONFIG` | 0 | 11 | ECONF_ID | 5 | 0 |
| `ENTIDADE_PROVAS` | 0 | 3 | — | 2 | 0 |
| `ENTIDADE_SUB` | 0 | 2 | e_master_id, e_sub_id | 2 | 0 |
| `RH_PROBLEMA` | 0 | 6 | RHP_ID | 0 | 0 |

### `ENT_MOV` — *166 119 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MOVENT_ID` | int | NO |  | **PK** |
| 2 | `MOVENT_MET_ID` | int | NO |  | FK → `ENT_MOV_TIPO.MET_ID` |
| 3 | `MOVENT_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 4 | `MOVENT_DATA_I` | smalldatetime | NO |  |  |
| 5 | `MOVENT_DATA_F` | smalldatetime | NO |  |  |
| 6 | `MOVENT_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 7 | `MOVENT_HORAS` | float | NO |  |  |
| 8 | `MOVENT_DATA_PAG` | smalldatetime | YES |  |  |
| 9 | `MOVENT_VALOR_HORA` | float | NO |  |  |
| 10 | `MOVENT_VALOR_PAGO` | float | NO |  |  |
| 11 | `MOVENT_CC` | float | NO |  |  |
| 12 | `MOVENT_PHC` | bit | NO |  |  |
| 13 | `MOVENT_ANO` | int | YES |  |  |
| 14 | `MOVENT_MES` | int | YES |  |  |
| 15 | `MOVENT_PROCESSADO` | bit | NO |  |  |
| 16 | `MOVENT_DESCONTA_LAMINADOR` | bit | NO |  |  |
| 17 | `MOVENT_OF_ID` | int | YES |  |  |
| 18 | `MOVENT_VAI_PHC` | bigint | NO |  |  |
| 19 | `MOVENT_E_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 20 | `MOVENT_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |

**PK**: `MOVENT_ID`

**FKs declared (out)**:
- `MOVENT_MET_ID` → `ENT_MOV_TIPO.MET_ID`
- `MOVENT_E_ID` → `ENTIDADE.E_ID`
- `MOVENT_E_E_ID` → `ENTIDADE.E_ID`
- `MOVENT_FP_ID` → `FASES_PRODUCAO.FP_ID`


**Implicit relations** _(by column naming)_:
- `MOVENT_ID` → likely _(no obvious target)_
- `MOVENT_OF_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 20 cols)*:

| `MOVENT_ID` | `MOVENT_MET_ID` | `MOVENT_E_ID` | `MOVENT_DATA_I` | `MOVENT_DATA_F` | `MOVENT_OBSERVACOES` | `MOVENT_HORAS` | `MOVENT_DATA_PAG` |
|---|---|---|---|---|---|---|---|
| 15357 | 7 | 20364 | 2009-06-01 08:00 | 2009-06-01 17:00 |  | 0.0 | 2010-02-05 00:00 |
| 15358 | 7 | 20369 | 2009-06-01 08:00 | 2009-06-01 17:00 |  | 0.0 | 2009-07-03 00:00 |
| 15359 | 8 | 20539 | 2009-06-01 08:00 | 2009-06-01 17:00 |  | 0.0 | 2009-07-03 00:00 |

---

### `ENTIDADE_PHC_FACT` — *100 503 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EPHCF_EPHC_ID` | int | YES |  | FK → `ENTIDADE_PHC.EPHC_ID` |
| 2 | `EPHCF_ANO` | int | NO |  |  |
| 3 | `EPHCF_MES` | int | NO |  |  |
| 4 | `EPHCF_DIA` | int | NO |  |  |
| 5 | `EPHCF_EPOCA` | int | NO |  |  |
| 6 | `EPHCF_TP_ID_DISCIP` | int | YES |  |  |
| 7 | `EPHCF_TP_ID` | int | YES |  |  |
| 8 | `EPHCF_FACTURADO` | float | NO |  |  |

**PK**: _(none declared)_

**FKs declared (out)**:
- `EPHCF_EPHC_ID` → `ENTIDADE_PHC.EPHC_ID`


**Implicit relations** _(by column naming)_:
- `EPHCF_TP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EPHCF_EPHC_ID` | `EPHCF_ANO` | `EPHCF_MES` | `EPHCF_DIA` | `EPHCF_EPOCA` | `EPHCF_TP_ID_DISCIP` | `EPHCF_TP_ID` | `EPHCF_FACTURADO` |
|---|---|---|---|---|---|---|---|
| — | 2022 | 6 | 3 | 2022 | — | — | 1139.35 |
| — | 2022 | 6 | 6 | 2022 | — | — | 154.47 |
| — | 2022 | 6 | 7 | 2022 | — | — | 1585.46 |

---

### `ENT_TP_PROD` — *22 832 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ETP_E_ID` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |
| 2 | `ETP_TP_ID` | int | NO |  | **PK** FK → `PRODUTO_TIPO.TP_ID` |
| 3 | `ETP_OBJ_OF` | int | NO |  |  |
| 4 | `ETP_OBJ_VAL` | float | NO |  |  |
| 5 | `ETP_BRAND_MANAGER` | bit | NO |  |  |

**PK**: `ETP_E_ID, ETP_TP_ID`

**FKs declared (out)**:
- `ETP_E_ID` → `ENTIDADE.E_ID`
- `ETP_TP_ID` → `PRODUTO_TIPO.TP_ID`


**Sample (TOP 3)**:

| `ETP_E_ID` | `ETP_TP_ID` | `ETP_OBJ_OF` | `ETP_OBJ_VAL` | `ETP_BRAND_MANAGER` |
|---|---|---|---|---|
| 19586 | 149 | 0 | 0.0 | false |
| 19586 | 151 | 0 | 0.0 | false |
| 19586 | 153 | 0 | 0.0 | false |

---

### `ENTIDADE` — *8 936 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `E_ID` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |
| 2 | `E_NOME` | nvarchar(max) | NO |  |  |
| 3 | `E_GENERO` | nvarchar(50) | YES |  |  |
| 4 | `E_DATANASCIMENTO` | smalldatetime | YES |  |  |
| 5 | `E_PESOCORPORAL` | float | NO |  |  |
| 6 | `E_CLUBE` | nvarchar(max) | YES |  |  |
| 7 | `E_NUMTREINOS` | int | NO |  |  |
| 8 | `E_CONTACTO` | nvarchar(max) | YES |  |  |
| 9 | `E_PAIS` | nvarchar(max) | YES |  |  |
| 10 | `E_CIDADE` | nvarchar(max) | YES |  |  |
| 11 | `E_MORADA` | nvarchar(max) | YES |  |  |
| 12 | `E_CODIGOPOSTAL` | nvarchar(50) | YES |  |  |
| 13 | `E_MORADAENTREGA` | nvarchar(max) | YES |  |  |
| 14 | `E_TELEFONE` | nvarchar(max) | YES |  |  |
| 15 | `E_EMAIL` | nvarchar(max) | YES |  |  |
| 16 | `E_COMPETICAO` | bit | NO |  |  |
| 17 | `E_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 18 | `E_PRAZOPAGAMENTO` | int | NO |  |  |
| 19 | `E_TRANSPORTEPAGO` | bit | NO |  |  |
| 20 | `E_VISITA` | bit | NO |  |  |
| 21 | `E_HORAHOMEM` | float | NO |  |  |
| 22 | `E_FAZENTREGA` | bit | NO |  |  |
| 23 | `E_PRAZOENTREGA` | int | NO |  |  |
| 24 | `E_TOURING` | bit | NO |  |  |
| 25 | `E_SPRINT` | bit | NO |  |  |
| 26 | `E_EXPEDITIONS` | bit | NO |  |  |
| 27 | `E_MARATHON` | bit | NO |  |  |
| 28 | `E_ENT_ID` | int | YES |  | FK → `ENTIDADE_TIPO.ENT_ID` |
| 29 | `E_ZG_ID` | int | YES |  | FK → `ZONA_GEOGRAFICA.ZG_ID` |
| 30 | `E_ACTIVO` | bit | NO |  |  |
| 31 | `E_FOTO` | nvarchar(max) | YES |  |  |
| 32 | `E_CONTRIBUINTE` | nvarchar(max) | YES |  |  |
| 33 | `E_CUSTOHORA` | float | NO |  |  |
| 34 | `E_DATAENTRADA` | smalldatetime | YES |  |  |
| 35 | `E_TV_ID` | int | YES |  | FK → `ENT_TIPO_VINCULO.TV_ID` |
| 36 | `E_FALTA_DESC_HORAS` | bit | NO |  |  |
| 37 | `E_HORAS_A_DOBRAR` | bit | NO |  |  |
| 38 | `E_EQ_ID` | int | YES |  | FK → `EQUIPA.EQ_ID` |
| 39 | `E_P_ID_FP` | int | YES |  |  |
| 40 | `E_FP_POS` | nvarchar(max) | YES |  |  |
| 41 | `E_P_ID_BANCO` | int | YES |  |  |
| 42 | `E_BANCO_POS` | nvarchar(max) | YES |  |  |
| 43 | `E_P_ID_STRAP` | nvarchar(max) | YES |  |  |
| 44 | `E_L_ID` | int | YES |  |  |
| 45 | `E_LOGIN` | nvarchar(max) | YES |  |  |
| 46 | `E_PASSWD` | nvarchar(max) | NO |  |  |
| 47 | `E_TIPO_UTIL` | int | NO |  |  |
| 48 | `E_TAM_CALCADO` | nvarchar(max) | NO |  |  |
| 49 | `E_TAM_CALCA` | nvarchar(max) | NO |  |  |
| 50 | `E_TAM_CAMISOLA` | nvarchar(max) | NO |  |  |
| 51 | `E_TAM_FATO` | nvarchar(max) | NO |  |  |
| 52 | `E_GOOGLE_CALENDAR` | nvarchar(max) | YES |  |  |
| 53 | `E_PHC_ID` | int | YES |  |  |
| 54 | `E_BENCH_CLASSE` | int | YES |  |  |
| 55 | `E_FACT_EPOCA` | decimal | YES |  |  |
| 56 | `E_FACT_TRIMESTRE` | decimal | YES |  |  |
| 57 | `E_DOURO_ID` | varchar(50) | YES |  |  |
| 58 | `E_DOURO_SERVICO` | int | YES |  |  |
| 59 | `E_DOURO_VALIDADE` | decimal | YES |  |  |
| 60 | `E_DESCONTO` | float | NO |  |  |
| 61 | `E_PAIS_ID` | int | YES |  |  |
| 62 | `E_MODALIDADE` | varchar(50) | YES |  |  |
| 63 | `E_CHEFE` | bit | NO |  |  |
| 64 | `E_FP_ID` | int | YES |  |  |
| 65 | `E_PRODUTIVIDADE` | float | NO |  |  |
| 66 | `E_ACESSO_WEB` | bit | NO |  |  |
| 67 | `E_PRECO_NACIONAL` | bit | NO |  |  |
| 68 | `E_E_ID` | int | YES |  |  |
| 69 | `E_NELO` | bit | NO |  |  |
| 70 | `E_TRANSPORTADOR` | bit | NO |  |  |
| 71 | `E_CARTAO_RFID` | nvarchar(12) | YES |  |  |
| 72 | `E_SHOP_ID` | int | YES |  |  |
| 73 | `E_ISENCAO_HORARIO` | bit | NO |  |  |
| 74 | `E_ALTURA` | float | NO |  |  |
| 75 | `E_CREDITO_PROMO` | float | NO |  |  |
| 76 | `E_TAXA_IRS` | float | NO |  |  |
| 77 | `E_BARCONUMERO` | nvarchar(max) | NO |  |  |
| 78 | `E_PAGAIANUMERO` | nvarchar(max) | NO |  |  |
| 79 | `E_BMI` | float | NO |  |  |
| 80 | `E_TEMPO` | float | NO |  |  |
| 81 | `E_GORDURA` | float | NO |  |  |
| 82 | `E_FLEXOES` | float | NO |  |  |
| 83 | `E_ABS` | float | NO |  |  |
| 84 | `E_FUMADOR` | bit | NO |  |  |
| 85 | `E_PREFERENCIA` | varchar(50) | YES |  |  |
| 86 | `E_TEMPO_500` | decimal | YES |  |  |
| 87 | `E_TEMPO_1000` | decimal | YES |  |  |
| 88 | `E_CERTIFICADO_CO2` | bit | NO |  |  |
| 89 | `E_URL` | nvarchar(255) | YES |  |  |
| 90 | `E_TAGS` | nvarchar(150) | YES |  |  |
| 91 | `E_RESULTADO` | int | NO |  |  |
| 92 | `E_NIVEL` | int | NO |  |  |
| 93 | `E_TESTES_PORTUGAL` | bit | NO |  |  |
| 94 | `E_RESPOSTA` | int | NO |  |  |
| 95 | `E_CONTA_POC` | nvarchar(max) | NO |  |  |

**PK**: `E_ID`

**FKs declared (out)**:
- `E_TV_ID` → `ENT_TIPO_VINCULO.TV_ID`
- `E_ID` → `ENTIDADE.E_ID`
- `E_ENT_ID` → `ENTIDADE_TIPO.ENT_ID`
- `E_EQ_ID` → `EQUIPA.EQ_ID`
- `E_ZG_ID` → `ZONA_GEOGRAFICA.ZG_ID`

**FKs declared (in)** — *61 references*:
- `FATURA.entidade_id`
- `AtletaProva.AtletaID`
- `AGENTE_FATURA.AFT_E_ID`
- `ALARM.ALARM_E_ID`
- `ALARM.ALARM_E_ID_REVISOR`
- `ALARM_TIPO_ENTIDADE.ATE_E_ID`
- `ARMAZEM.ARM_E_ID_RESP`
- `AUDIT_ENT.AUDE_E_ID`
- `CENTRO_RESERVA.RES_E_ID`
- `COMUNICACAO.COM_E_ID`
- `COMUNICACAO_FASES_PRODUCAO.COMFP_E_ID`
- `DOURO_AULA_ENTIDADE.AULAE_E_ID`
- `ENCOMENDA.ENC_E_ID`
- `ENT_CONFIG.ECONF_E_ID`
- `ENT_MOV.MOVENT_E_ID`
- `ENT_MOV.MOVENT_E_E_ID`
- `ENT_TP_PROD.ETP_E_ID`
- `ENTIDADE_DADOS.EDADOS_E_ID`
- `ENTIDADE.E_ID`
- `ENTIDADE_EQUIPA.EEQ_E_ID`
- … *(+41 more)*

**Implicit relations** _(by column naming)_:
- `E_L_ID` → likely _(no obvious target)_
- `E_PHC_ID` → likely _(no obvious target)_
- `E_DOURO_ID` → likely _(no obvious target)_
- `E_PAIS_ID` → likely _(no obvious target)_
- `E_FP_ID` → likely _(no obvious target)_
- `E_E_ID` → likely _(no obvious target)_
- `E_CARTAO_RFID` → likely _(no obvious target)_
- `E_SHOP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 95 cols)*:

| `E_ID` | `E_NOME` | `E_GENERO` | `E_DATANASCIMENTO` | `E_PESOCORPORAL` | `E_CLUBE` | `E_NUMTREINOS` | `E_CONTACTO` |
|---|---|---|---|---|---|---|---|
| 1 | teste | — | — | 0.0 | — | 0 | — |
| 19416 | Guy De Prins |  | 1979-12-16 00:00 | 66.0 | KCCM Mechelen | 9 |  |
| 19417 | Johan Dahl |  | — | 89.0 | River City Paddlers | 5 |  |

---

### `MOLDES_MOV` — *3 673 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MLDU_ID` | int | NO |  | **PK** |
| 2 | `MLDU_DATA` | smalldatetime | NO |  |  |
| 3 | `MLDU_TP_ID` | int | NO |  |  |
| 4 | `MLDU_MLD_ID` | int | NO |  | FK → `MOLDES.MLD_ID` |
| 5 | `MLDU_E_ID` | int | NO |  |  |

**PK**: `MLDU_ID`

**FKs declared (out)**:
- `MLDU_MLD_ID` → `MOLDES.MLD_ID`


**Implicit relations** _(by column naming)_:
- `MLDU_ID` → likely _(no obvious target)_
- `MLDU_TP_ID` → likely _(no obvious target)_
- `MLDU_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `MLDU_ID` | `MLDU_DATA` | `MLDU_TP_ID` | `MLDU_MLD_ID` | `MLDU_E_ID` |
|---|---|---|---|---|
| 8 | 2010-02-18 00:00 | 1 | 1 | 20537 |
| 9 | 2010-02-18 00:00 | 1 | 2 | 20537 |
| 10 | 2010-02-18 00:00 | 1 | 3 | 20537 |

---

### `ENTIDADE_FASE` — *1 269 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EFP_ID` | int | NO |  | **PK** |
| 2 | `EFP_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `EFP_FP_ID` | int | NO |  | FK → `FASES_PRODUCAO.FP_ID` |
| 4 | `EFP_DATAINICIO` | smalldatetime | YES |  |  |
| 5 | `EFP_DATAFIM` | smalldatetime | YES |  |  |
| 6 | `EFP_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 7 | `EFP_PRODUTIVIDADE` | int | NO |  |  |
| 8 | `EFP_CHEFE` | bit | NO |  |  |
| 9 | `EFP_QUALIFICADO` | bit | NO |  |  |
| 10 | `EFP_DURACAO` | float | NO |  |  |
| 11 | `EFP_SEQUENCIA` | int | NO |  |  |

**PK**: `EFP_ID`

**FKs declared (out)**:
- `EFP_E_ID` → `ENTIDADE.E_ID`
- `EFP_FP_ID` → `FASES_PRODUCAO.FP_ID`


**Implicit relations** _(by column naming)_:
- `EFP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `EFP_ID` | `EFP_E_ID` | `EFP_FP_ID` | `EFP_DATAINICIO` | `EFP_DATAFIM` | `EFP_OBSERVACOES` | `EFP_PRODUTIVIDADE` | `EFP_CHEFE` |
|---|---|---|---|---|---|---|---|
| 4 | 24482 | 5 | 2016-06-13 00:00 | — | — | 1 | false |
| 5 | 24483 | 3 | 2016-06-24 00:00 | — | — | 5 | false |
| 6 | 24484 | 5 | 2016-06-13 00:00 | — | — | 1 | true |

---

### `ENTIDADE_MORADA` — *952 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EM_ID` | int | NO |  | **PK** |
| 2 | `EM_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `EM_CONTACTO` | nvarchar(max) | YES |  |  |
| 4 | `EM_MORADA` | nvarchar(max) | NO |  |  |
| 5 | `EM_LONGITUDE` | decimal | YES |  |  |
| 6 | `EM_LATITUDE` | decimal | YES |  |  |
| 7 | `EM_DEFAULT` | bit | NO |  |  |
| 8 | `EM_EMAIL` | nvarchar(max) | YES |  |  |
| 9 | `EM_TELEFONE` | nvarchar(max) | YES |  |  |
| 10 | `EM_TIPO` | int | NO |  | FK → `ENTIDADE_MORADA_TIPO.EMT_ID` |
| 11 | `EM_NOME` | nvarchar(250) | YES |  |  |
| 12 | `EM_DELETED` | date | YES |  |  |
| 13 | `EM_PAISES_ID` | int | YES |  | FK → `PAISES_SITE.ID` |
| 14 | `EM_CONTRIBUINTE` | nvarchar(max) | YES |  |  |
| 15 | `EM_SITE` | nvarchar(max) | YES |  |  |

**PK**: `EM_ID`

**FKs declared (out)**:
- `EM_E_ID` → `ENTIDADE.E_ID`
- `EM_TIPO` → `ENTIDADE_MORADA_TIPO.EMT_ID`
- `EM_PAISES_ID` → `PAISES_SITE.ID`

**FKs declared (in)** — *1 references*:
- `ORDEMFABRICO.OF_EM_ID`

**Implicit relations** _(by column naming)_:
- `EM_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 15 cols)*:

| `EM_ID` | `EM_E_ID` | `EM_CONTACTO` | `EM_MORADA` | `EM_LONGITUDE` | `EM_LATITUDE` | `EM_DEFAULT` | `EM_EMAIL` |
|---|---|---|---|---|---|---|---|
| 1 | 23394 | — | Stenkolsgatan 3B 41707 Gothenburg, sw... | 11.971075400 | 57.718941900 | false | — |
| 2 | 20155 | — | Kanuschule Bodensee GmbH, Rosenstrass... | 9.418784000 | 47.526247000 | false | — |
| 3 | 24587 | — | Rådmann Halmrasts vei 9 1337 Sandvika... | 10.525236900 | 59.891672600 | false | — |

---

### `ENTIDADE_PONTOS` — *866 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EP_ID` | int | NO |  | **PK** |
| 2 | `EP_E_ID` | int | YES |  |  |
| 3 | `EP_PONTOS_ID` | int | YES |  |  |
| 4 | `EP_ANO` | int | NO |  |  |
| 5 | `EP_MES` | int | NO |  |  |
| 6 | `EP_DIASMES` | int | NO |  |  |
| 7 | `EP_HORAS` | float | NO |  |  |
| 8 | `EP_REPARACOES` | float | NO |  |  |
| 9 | `EP_PREMIO` | bit | NO |  |  |
| 10 | `EP_RESTO` | int | NO |  |  |
| 11 | `EP_DESCONTO` | int | NO |  |  |
| 12 | `EP_OBS` | nvarchar(max) | YES |  |  |
| 13 | `EP_EQ_ID` | int | YES |  |  |

**PK**: `EP_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `EP_ID` → likely _(no obvious target)_
- `EP_E_ID` → likely _(no obvious target)_
- `EP_PONTOS_ID` → likely _(no obvious target)_
- `EP_EQ_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 13 cols)*:

| `EP_ID` | `EP_E_ID` | `EP_PONTOS_ID` | `EP_ANO` | `EP_MES` | `EP_DIASMES` | `EP_HORAS` | `EP_REPARACOES` |
|---|---|---|---|---|---|---|---|
| 18 | 20362 | 3 | 2008 | 1 | 21 | 214.0 | 51.0 |
| 19 | 20363 | 7 | 2008 | 1 | 21 | 248.0 | 80.0 |
| 20 | 20364 | 7 | 2008 | 1 | 21 | 434.0 | 118.5 |

---

### `ENTIDADE_PHC` — *751 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EPHC_ID` | int | NO |  | **PK** |
| 2 | `EPHC_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `EPHC_PHC_ID` | int | NO |  |  |

**PK**: `EPHC_ID`

**FKs declared (out)**:
- `EPHC_E_ID` → `ENTIDADE.E_ID`

**FKs declared (in)** — *1 references*:
- `ENTIDADE_PHC_FACT.EPHCF_EPHC_ID`

**Implicit relations** _(by column naming)_:
- `EPHC_ID` → likely _(no obvious target)_
- `EPHC_PHC_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EPHC_ID` | `EPHC_E_ID` | `EPHC_PHC_ID` |
|---|---|---|
| 1 | 20107 | 38 |
| 2 | 23332 | 5018 |
| 3 | 21576 | 3732 |

---

### `ENTIDADE_TREINOS` — *401 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ETR_ID` | int | NO |  | **PK** |
| 2 | `ETR_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `ETR_DATA` | smalldatetime | NO |  |  |
| 4 | `ETR_TEMPO` | time | NO |  |  |
| 5 | `ETR_DESCRICAO` | nvarchar(max) | NO |  |  |
| 6 | `ETR_BARCO` | nvarchar(max) | NO |  |  |
| 7 | `ETR_DISTANCIA` | float | NO |  |  |
| 8 | `ETR_CIRCUITO` | bit | NO |  |  |
| 9 | `ETR_TRACK` | nvarchar(max) | NO |  |  |
| 10 | `ETR_PESOCORPORAL` | float | NO |  |  |
| 11 | `ETR_ELIMINADO` | smalldatetime | YES |  |  |

**PK**: `ETR_ID`

**FKs declared (out)**:
- `ETR_E_ID` → `ENTIDADE.E_ID`


**Implicit relations** _(by column naming)_:
- `ETR_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `ETR_ID` | `ETR_E_ID` | `ETR_DATA` | `ETR_TEMPO` | `ETR_DESCRICAO` | `ETR_BARCO` | `ETR_DISTANCIA` | `ETR_CIRCUITO` |
|---|---|---|---|---|---|---|---|
| 1 | 30549 | 2022-10-04 00:00 | 01:03:45 | Treino 1 | Ocean Ski 540 L SCS | 5.5 | false |
| 2 | 30549 | 2022-10-05 00:00 | 02:05:12 | Treino 2 | Ocean Ski 540 L SCS | 12.0 | false |
| 3 | 30549 | 2022-10-06 00:00 | 01:45:55 | Treino 3 | Ocean Ski 540 L SCS | 8.0 | false |

---

### `MOLDES` — *91 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MLD_ID` | int | NO |  | **PK** |
| 2 | `MLD_NOME` | nvarchar(max) | NO |  |  |
| 3 | `MLD_DATA` | smalldatetime | NO |  |  |
| 4 | `MLD_MLDTP_ID` | int | NO |  | FK → `MOLDES_TIPO.MLDTP_ID` |
| 5 | `MLD_UTILIZ` | int | NO |  |  |

**PK**: `MLD_ID`

**FKs declared (out)**:
- `MLD_MLDTP_ID` → `MOLDES_TIPO.MLDTP_ID`

**FKs declared (in)** — *1 references*:
- `MOLDES_MOV.MLDU_MLD_ID`

**Implicit relations** _(by column naming)_:
- `MLD_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `MLD_ID` | `MLD_NOME` | `MLD_DATA` | `MLD_MLDTP_ID` | `MLD_UTILIZ` |
|---|---|---|---|---|
| 1 | B ST 01 | 2010-02-16 19:52 | 1 | 0 |
| 2 | B ST 02 | 2010-02-16 19:52 | 1 | 1 |
| 3 | B ST 03 | 2010-02-16 19:52 | 1 | 1 |

---

### `ENTIDADE_EQUIPA` — *82 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EEQ_ID` | int | NO |  | **PK** |
| 2 | `EEQ_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `EEQ_EQ_ID` | int | NO |  | FK → `EQUIPA.EQ_ID` |
| 4 | `EEQ_DATA_ENTRADA` | smalldatetime | NO |  |  |
| 5 | `EEQ_DATA_SAIDA` | smalldatetime | YES |  |  |
| 6 | `EEQ_CHEFE` | bit | NO |  |  |
| 7 | `EEQ_E_E_ID` | int | YES |  |  |

**PK**: `EEQ_ID`

**FKs declared (out)**:
- `EEQ_E_ID` → `ENTIDADE.E_ID`
- `EEQ_EQ_ID` → `EQUIPA.EQ_ID`


**Implicit relations** _(by column naming)_:
- `EEQ_ID` → likely _(no obvious target)_
- `EEQ_E_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EEQ_ID` | `EEQ_E_ID` | `EEQ_EQ_ID` | `EEQ_DATA_ENTRADA` | `EEQ_DATA_SAIDA` | `EEQ_CHEFE` | `EEQ_E_E_ID` |
|---|---|---|---|---|---|---|
| 1 | 20365 | 1 | 2008-01-10 09:21 | 2012-03-31 23:59 | true | — |
| 2 | 20536 | 1 | 2009-02-10 09:21 | 2011-01-01 00:00 | false | — |
| 3 | 20364 | 2 | 2008-01-10 09:23 | 2011-01-01 00:00 | true | — |

---

### `ENTIDADE_TIPO` — *36 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ENT_ID` | int | NO |  | **PK** |
| 2 | `ENT_NOME` | nvarchar(max) | NO |  |  |
| 3 | `ENT_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `ENT_ENT_ID` | int | YES |  | FK → `ENTIDADE_TIPO.ENT_ID` |
| 5 | `ENT_FP_ID` | int | YES |  |  |

**PK**: `ENT_ID`

**FKs declared (out)**:
- `ENT_ENT_ID` → `ENTIDADE_TIPO.ENT_ID`

**FKs declared (in)** — *2 references*:
- `ENTIDADE.E_ENT_ID`
- `ENTIDADE_TIPO.ENT_ENT_ID`

**Implicit relations** _(by column naming)_:
- `ENT_ID` → likely `ENTIDADE_MORADA`
- `ENT_FP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `ENT_ID` | `ENT_NOME` | `ENT_DESCRICAO` | `ENT_ENT_ID` | `ENT_FP_ID` |
|---|---|---|---|---|
| 2 | Cliente |  | — | — |
| 5 | Laminador |  | 19 | 1 |
| 6 | Pintor |  | 19 | 18 |

---

### `RH_DOC` — *19 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `RHD_ID` | int | NO |  | **PK** |
| 2 | `RHD_TIPO_ID` | int | YES |  | FK → `RH_TIPO_DOC.RHTD_ID` |
| 3 | `RHD_DATA_ALTERACAO` | decimal | YES |  |  |
| 4 | `RHD_TITULO` | varchar(250) | YES |  |  |
| 5 | `RHD_FICHEIRO` | varchar(250) | YES |  |  |

**PK**: `RHD_ID`

**FKs declared (out)**:
- `RHD_TIPO_ID` → `RH_TIPO_DOC.RHTD_ID`


**Implicit relations** _(by column naming)_:
- `RHD_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `RHD_ID` | `RHD_TIPO_ID` | `RHD_DATA_ALTERACAO` | `RHD_TITULO` | `RHD_FICHEIRO` |
|---|---|---|---|---|
| 2 | 1 | 20140107 | teste | 13890892659464.jpg |
| 3 | 5 | 20131111 | Resina Ampreg 22 | 1384192775983.pdf |
| 4 | 5 | 20131208 | Resina Sicomin SR 1500 | 13865245468522.pdf |

---

### `EQUIPA` — *17 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EQ_ID` | int | NO |  | **PK** |
| 2 | `EQ_NOME` | nvarchar(max) | NO |  |  |
| 3 | `EQ_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 4 | `EQ_DATA_ELIMINADO` | smalldatetime | YES |  |  |

**PK**: `EQ_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `ENTIDADE.E_EQ_ID`
- `ENTIDADE_EQUIPA.EEQ_EQ_ID`

**Implicit relations** _(by column naming)_:
- `EQ_ID` → likely `EQUIPA`

**Sample (TOP 3)**:

| `EQ_ID` | `EQ_NOME` | `EQ_DATA_CRIACAO` | `EQ_DATA_ELIMINADO` |
|---|---|---|---|
| 1 | Equipa 1 - Alexandre | 2009-03-10 09:17 | 2018-09-20 00:00 |
| 2 | Equipa 2 - Jorge Barge | 2009-03-10 09:17 | 2018-09-20 00:00 |
| 3 | Equipa 3 - Vitor Clone | 2009-03-10 09:17 | 2018-09-20 00:00 |

---

### `ENT_MOV_TIPO` — *15 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MET_ID` | int | NO |  | **PK** |
| 2 | `MET_NOME` | nvarchar(max) | NO |  |  |
| 3 | `MET_DESCRICAO` | nvarchar(max) | NO |  |  |
| 4 | `MET_MET_ID` | int | YES |  | FK → `ENT_MOV_TIPO.MET_ID` |
| 5 | `MET_DESCONTA_HORAS` | bit | NO |  |  |
| 6 | `MET_FACTOR` | int | NO |  |  |

**PK**: `MET_ID`

**FKs declared (out)**:
- `MET_MET_ID` → `ENT_MOV_TIPO.MET_ID`

**FKs declared (in)** — *2 references*:
- `ENT_MOV.MOVENT_MET_ID`
- `ENT_MOV_TIPO.MET_MET_ID`

**Implicit relations** _(by column naming)_:
- `MET_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `MET_ID` | `MET_NOME` | `MET_DESCRICAO` | `MET_MET_ID` | `MET_DESCONTA_HORAS` | `MET_FACTOR` |
|---|---|---|---|---|---|
| 1 | Horas Extra | Horas extraordinarias | — | false | 1 |
| 2 | Faltas |  | — | false | 1 |
| 4 | Injustificada |  | 2 | true | 1 |

---

### `MOLDES_TIPO` — *14 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MLDTP_ID` | int | NO |  | **PK** |
| 2 | `MLDTP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `MLDTP_NUMUTIL` | int | NO |  |  |

**PK**: `MLDTP_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `MOLDES.MLD_MLDTP_ID`

**Implicit relations** _(by column naming)_:
- `MLDTP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `MLDTP_ID` | `MLDTP_NOME` | `MLDTP_NUMUTIL` |
|---|---|---|
| 1 | Banco Standard | 4 |
| 2 | Banco Ultra Low | 4 |
| 3 | Banco Nelo | 4 |

---

### `RH_TIPO_DOC` — *6 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `RHTD_ID` | int | NO |  | **PK** |
| 2 | `RHTD_NOME` | varchar(50) | YES |  |  |

**PK**: `RHTD_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `RH_DOC.RHD_TIPO_ID`

**Implicit relations** _(by column naming)_:
- `RHTD_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `RHTD_ID` | `RHTD_NOME` |
|---|---|
| 1 | Plano formação |
| 2 | Planta emergência |
| 3 | Relatório anual |

---

### `ENT_TIPO_VINCULO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TV_ID` | int | NO |  | **PK** |
| 2 | `TV_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TV_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `TV_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `ENTIDADE.E_TV_ID`

**Implicit relations** _(by column naming)_:
- `TV_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TV_ID` | `TV_NOME` | `TV_DESCRICAO` |
|---|---|---|
| 1 | Sem vinculo | — |
| 2 | Contrato a prazo | — |
| 3 | Sem termo | — |

---

### `ENTIDADE_MORADA_TIPO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EMT_ID` | int | NO |  | **PK** |
| 2 | `EMT_TIPO` | varchar(150) | NO |  |  |

**PK**: `EMT_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `ENTIDADE_MORADA.EM_TIPO`

**Implicit relations** _(by column naming)_:
- `EMT_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EMT_ID` | `EMT_TIPO` |
|---|---|
| 1 | Shipping address |
| 2 | Website info |
| 3 | Billing address |

---

### `ENT_ENT_PEDIDO_PROVISORIO` — *2 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EEP_ID` | int | NO |  | **PK** |
| 2 | `EEP_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 3 | `EEP_E_ID_RESP` | int | NO |  |  |
| 4 | `EEP_E_ID_FORN` | int | NO |  |  |
| 5 | `EEP_JSON` | nvarchar(max) | NO |  |  |

**PK**: `EEP_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `EEP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EEP_ID` | `EEP_DATA_CRIACAO` | `EEP_E_ID_RESP` | `EEP_E_ID_FORN` | `EEP_JSON` |
|---|---|---|---|---|
| 5850 | 2025-09-30 13:54 | 20597 | 20342 | [{"p_id":42003,"mov_quantidade":3.0,"... |
| 5873 | 2025-11-04 11:05 | 30323 | 40521 | [{"p_id":53792,"mov_quantidade":1.0,"... |

---

### `ENTIDADE_DADOS` — *1 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EDADOS_ID` | int | NO |  | **PK** |
| 2 | `EDADOS_EMPRESA` | nvarchar(max) | NO |  |  |
| 3 | `EDADOS_MORADA` | nvarchar(max) | NO |  |  |
| 4 | `EDADOS_CODPOSTAL` | nvarchar(max) | NO |  |  |
| 5 | `EDADOS_PAISES_ID` | int | YES |  | FK → `PAISES.PAISES_ID` |
| 6 | `EDADOS_CONTACTO` | nvarchar(max) | NO |  |  |
| 7 | `EDADOS_CONTRIBUINTE` | nvarchar(max) | NO |  |  |
| 8 | `EDADOS_DATA` | smalldatetime | NO |  |  |
| 9 | `EDADOS_PHC_NUMERO` | int | YES |  |  |
| 10 | `EDADOS_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |

**PK**: `EDADOS_ID`

**FKs declared (out)**:
- `EDADOS_E_ID` → `ENTIDADE.E_ID`
- `EDADOS_PAISES_ID` → `PAISES.PAISES_ID`


**Implicit relations** _(by column naming)_:
- `EDADOS_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 10 cols)*:

| `EDADOS_ID` | `EDADOS_EMPRESA` | `EDADOS_MORADA` | `EDADOS_CODPOSTAL` | `EDADOS_PAISES_ID` | `EDADOS_CONTACTO` | `EDADOS_CONTRIBUINTE` | `EDADOS_DATA` |
|---|---|---|---|---|---|---|---|
| 1 | Hangzhou Fuyang Fangzhou Boat Co Ltd | AEROPORTO DE HANGZHOU | 4485-062 | — | 399293773@qq.com |  | 2016-03-22 15:43 |

---

### `RH_FORMACAO` — *1 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `RHF_ID` | int | NO |  | **PK** |
| 2 | `RHF_TITULO` | varchar(250) | YES |  |  |
| 3 | `RHF_DESCRICAO` | varchar(max) | YES |  |  |
| 4 | `RHF_DURACAO` | varchar(50) | YES |  |  |
| 5 | `RHF_DATA_PREVISTA` | smalldatetime | YES |  |  |
| 6 | `RHF_DATA_REALIZACAO` | smalldatetime | YES |  |  |

**PK**: `RHF_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `RHF_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `RHF_ID` | `RHF_TITULO` | `RHF_DESCRICAO` | `RHF_DURACAO` | `RHF_DATA_PREVISTA` | `RHF_DATA_REALIZACAO` |
|---|---|---|---|---|---|
| 3 | FORMAÇÃO HST _Certificados_Grupo 1 |  |  | 1900-01-01 00:00 | 1900-01-01 00:00 |

---

### `ENT_CONFIG` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ECONF_ID` | int | NO |  | **PK** |
| 2 | `ECONF_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `ECONF_P_ID_MODELO` | int | NO |  | FK → `PRODUTO.P_ID` |
| 4 | `ECONF_P_ID_ACESSORIO` | int | YES |  | FK → `PRODUTO.P_ID` |
| 5 | `ECONF_ATRIB_ID` | int | NO |  | FK → `ATRIBUTO.ATRIB_ID` |
| 6 | `ECONF_ATRIB_ATRIB_ID` | int | YES |  | FK → `ATRIBUTO.ATRIB_ID` |
| 7 | `ECONF_VALOR` | float | NO |  |  |
| 8 | `ECONF_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 9 | `ECONF_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 10 | `ECONF_DATA_ACTUALIZACAO` | smalldatetime | YES |  |  |
| 11 | `ECONF_OF_ID` | int | YES |  |  |

**PK**: `ECONF_ID`

**FKs declared (out)**:
- `ECONF_ATRIB_ID` → `ATRIBUTO.ATRIB_ID`
- `ECONF_ATRIB_ATRIB_ID` → `ATRIBUTO.ATRIB_ID`
- `ECONF_E_ID` → `ENTIDADE.E_ID`
- `ECONF_P_ID_MODELO` → `PRODUTO.P_ID`
- `ECONF_P_ID_ACESSORIO` → `PRODUTO.P_ID`


**Implicit relations** _(by column naming)_:
- `ECONF_ID` → likely _(no obvious target)_
- `ECONF_OF_ID` → likely _(no obvious target)_

**Sample**: _(table empty or unreadable)_

---

### `ENTIDADE_PROVAS` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EPRV_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 2 | `EPRV_PRV_ID` | int | NO |  | FK → `PROVAS.PRV_ID` |
| 3 | `EPRV_RESULTADO` | int | NO |  |  |

**PK**: _(none declared)_

**FKs declared (out)**:
- `EPRV_E_ID` → `ENTIDADE.E_ID`
- `EPRV_PRV_ID` → `PROVAS.PRV_ID`


**Sample**: _(table empty or unreadable)_

---

### `ENTIDADE_SUB` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `e_master_id` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |
| 2 | `e_sub_id` | int | NO |  | **PK** FK → `ENTIDADE.E_ID` |

**PK**: `e_master_id, e_sub_id`

**FKs declared (out)**:
- `e_master_id` → `ENTIDADE.E_ID`
- `e_sub_id` → `ENTIDADE.E_ID`


**Sample**: _(table empty or unreadable)_

---

### `RH_PROBLEMA` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `RHP_ID` | int | NO |  | **PK** |
| 2 | `RHP_IRREGULARIDADE` | varchar(4000) | YES |  |  |
| 3 | `RHP_ACCAO` | varchar(4000) | YES |  |  |
| 4 | `RHP_DATA_PREVISTA` | smalldatetime | YES |  |  |
| 5 | `RHP_DATA_RESOLUCAO` | smalldatetime | YES |  |  |
| 6 | `RHP_RESOLVIDO` | bit | YES |  |  |

**PK**: `RHP_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `RHP_ID` → likely _(no obvious target)_

**Sample**: _(table empty or unreadable)_

---

<a id="qualidade-problemas-inspeces"></a>
## Qualidade, problemas, inspecções

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `REPARACOES_PROVAS` | 2 026 | 8 | REP_ID | 1 | 1 |
| `PROBS` | 104 | 3 | PROBS_ID | 1 | 2 |
| `AUDIT` | 38 | 15 | AUD_ID | 2 | 2 |
| `AVALIACOES_ITEMS` | 10 | 6 | AITEM_ID | 1 | 0 |
| `AUDIT_TIPO` | 8 | 3 | AUDT_ID | 1 | 2 |
| `PROBS_LOCAL` | 7 | 2 | PROBSL_ID | 0 | 2 |
| `PROBS_CLASSIFICACAO` | 6 | 3 | CL_ID | 0 | 0 |
| `PROB_CAUSA_SOL_TIPO` | 3 | 2 | TPPCS_ID | 0 | 1 |
| `PROB_CAUSA_SOL` | 2 | 8 | PCS_ID | 2 | 2 |
| `AUDIT_ENT` | 0 | 2 | — | 2 | 0 |

### `REPARACOES_PROVAS` — *2 026 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `REP_ID` | int | NO |  | **PK** |
| 2 | `REP_RECEBIDO` | smalldatetime | NO |  |  |
| 3 | `REP_ENTREGA` | smalldatetime | NO |  |  |
| 4 | `REP_ATLETA` | nvarchar(max) | NO |  |  |
| 5 | `REP_EQUIPA` | nvarchar(max) | NO |  |  |
| 6 | `REP_CONTACTO` | nvarchar(max) | NO |  |  |
| 7 | `REP_NOTAS` | nvarchar(max) | NO |  |  |
| 8 | `REP_E_ID_RESPONSAVEL` | int | NO |  | FK → `ENTIDADE.E_ID` |

**PK**: `REP_ID`

**FKs declared (out)**:
- `REP_E_ID_RESPONSAVEL` → `ENTIDADE.E_ID`

**FKs declared (in)** — *1 references*:
- `REP_OF_FP.ROFFP_REP_ID`

**Implicit relations** _(by column naming)_:
- `REP_ID` → likely `REP_OF_FP`

**Sample (TOP 3)**:

| `REP_ID` | `REP_RECEBIDO` | `REP_ENTREGA` | `REP_ATLETA` | `REP_EQUIPA` | `REP_CONTACTO` | `REP_NOTAS` | `REP_E_ID_RESPONSAVEL` |
|---|---|---|---|---|---|---|---|
| 64 | 2023-05-08 00:00 | 2023-05-13 09:00 | K4 | GB |  | Partido na emenda atrás  | 24908 |
| 65 | 2023-05-08 00:00 | 2023-05-09 10:00 | V1 | FRA |  |  | 24908 |
| 66 | 2023-05-08 00:00 | 2023-05-09 09:00 | C2 | China |  | Falta um rebite no taco da frente  | 24908 |

---

### `PROBS` — *104 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PROBS_ID` | int | NO |  | **PK** |
| 2 | `PROBS_DSCR` | nvarchar(max) | NO |  |  |
| 3 | `PROBS_PROBS_ID` | int | YES |  | FK → `PROBS.PROBS_ID` |

**PK**: `PROBS_ID`

**FKs declared (out)**:
- `PROBS_PROBS_ID` → `PROBS.PROBS_ID`

**FKs declared (in)** — *2 references*:
- `OFFP_PROBLEMA.OFFPPROB_PROBS_ID`
- `PROBS.PROBS_PROBS_ID`

**Implicit relations** _(by column naming)_:
- `PROBS_ID` → likely `PROBS`

**Sample (TOP 3)**:

| `PROBS_ID` | `PROBS_DSCR` | `PROBS_PROBS_ID` |
|---|---|---|
| 1 | Interior | — |
| 2 | Pintura | — |
| 3 | Molde | — |

---

### `AUDIT` — *38 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `AUD_ID` | int | NO |  | **PK** |
| 2 | `AUD_DESC` | nvarchar(max) | YES |  |  |
| 3 | `AUD_CAUSA` | nvarchar(max) | YES |  |  |
| 4 | `AUD_PROP` | nvarchar(max) | YES |  |  |
| 5 | `AUD_DATACONC` | smalldatetime | YES |  |  |
| 6 | `AUD_DATACRIAC` | smalldatetime | YES |  |  |
| 7 | `AUD_DATACONCREAL` | smalldatetime | YES |  |  |
| 8 | `AUD_RESULT` | nvarchar(max) | YES |  |  |
| 9 | `AUD_OBS` | nvarchar(max) | YES |  |  |
| 10 | `AUD_AUDT_ID` | int | YES |  | FK → `AUDIT_TIPO.AUDT_ID` |
| 11 | `AUD_E_ID` | int | YES |  |  |
| 12 | `AUD_AUD_ID` | int | YES |  | FK → `AUDIT.AUD_ID` |
| 13 | `AUD_PONTOSIT` | nvarchar(max) | YES |  |  |
| 14 | `AUD_RESPONSAVEIS` | nvarchar(max) | YES |  |  |
| 15 | `AUD_ELIMINADO` | bit | NO |  |  |

**PK**: `AUD_ID`

**FKs declared (out)**:
- `AUD_AUD_ID` → `AUDIT.AUD_ID`
- `AUD_AUDT_ID` → `AUDIT_TIPO.AUDT_ID`

**FKs declared (in)** — *2 references*:
- `AUDIT.AUD_AUD_ID`
- `AUDIT_ENT.AUDE_AUD_ID`

**Implicit relations** _(by column naming)_:
- `AUD_ID` → likely `AUDIT_TIPO`
- `AUD_E_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 15 cols)*:

| `AUD_ID` | `AUD_DESC` | `AUD_CAUSA` | `AUD_PROP` | `AUD_DATACONC` | `AUD_DATACRIAC` | `AUD_DATACONCREAL` | `AUD_RESULT` |
|---|---|---|---|---|---|---|---|
| 1 |  |  |  | — | 2011-11-26 00:00 | — |  |
| 2 | c | c | c | — | — | — | — |
| 3 | a | c | v | 2011-12-15 00:00 | 2011-10-26 12:06 | — | — |

---

### `AVALIACOES_ITEMS` — *10 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `AITEM_ID` | int | NO |  | **PK** |
| 2 | `AITEM_DESCR` | nvarchar(max) | NO |  |  |
| 3 | `AITEM_EOBSTP_ID` | int | NO |  | FK → `ENTIDADE_OBS_TIPO.EOBSTP_ID` |
| 4 | `AITEM_ORDEM` | int | NO |  |  |
| 5 | `AITEM_DESATIVADO` | date | YES |  |  |
| 6 | `AITEM_OBS` | nvarchar(max) | YES |  |  |

**PK**: `AITEM_ID`

**FKs declared (out)**:
- `AITEM_EOBSTP_ID` → `ENTIDADE_OBS_TIPO.EOBSTP_ID`


**Implicit relations** _(by column naming)_:
- `AITEM_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `AITEM_ID` | `AITEM_DESCR` | `AITEM_EOBSTP_ID` | `AITEM_ORDEM` | `AITEM_DESATIVADO` | `AITEM_OBS` |
|---|---|---|---|---|---|
| 1 | Conhecimentos Técnicos | 23 | 1 | — | Conjunto de noções que o colaborador ... |
| 2 | Sentido de Qualidade | 23 | 2 | — | Cumprimento das suas tarefas com qual... |
| 3 | Sentido de Prazo | 23 | 3 | — | Cumprimento dos prazos estabelecidos.... |

---

### `AUDIT_TIPO` — *8 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `AUDT_ID` | int | NO |  | **PK** |
| 2 | `AUDT_NOME` | nvarchar(max) | NO |  |  |
| 3 | `AUDT_AUDT_ID` | int | YES |  | FK → `AUDIT_TIPO.AUDT_ID` |

**PK**: `AUDT_ID`

**FKs declared (out)**:
- `AUDT_AUDT_ID` → `AUDIT_TIPO.AUDT_ID`

**FKs declared (in)** — *2 references*:
- `AUDIT.AUD_AUDT_ID`
- `AUDIT_TIPO.AUDT_AUDT_ID`

**Implicit relations** _(by column naming)_:
- `AUDT_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `AUDT_ID` | `AUDT_NOME` | `AUDT_AUDT_ID` |
|---|---|---|
| 1 | Não Conformidade | 3 |
| 2 | Oportunidade de Melhoria | 3 |
| 3 | Externas | — |

---

### `PROBS_LOCAL` — *7 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PROBSL_ID` | int | NO |  | **PK** |
| 2 | `PROBSL_DSCR` | nvarchar(max) | NO |  |  |

**PK**: `PROBSL_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `OFCH_LOCAL.OFPROBS_PROBSL_ID`
- `OFFP_PROBLEMA.OFFPPROB_PROBSL_ID`

**Implicit relations** _(by column naming)_:
- `PROBSL_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PROBSL_ID` | `PROBSL_DSCR` |
|---|---|
| 1 | Interior |
| 2 | Gola |
| 3 | Proa |

---

### `PROBS_CLASSIFICACAO` — *6 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `CL_ID` | int | NO |  | **PK** |
| 2 | `NOME` | nvarchar(50) | YES |  |  |
| 3 | `ORDEM` | int | YES |  |  |

**PK**: `CL_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `CL_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `CL_ID` | `NOME` | `ORDEM` |
|---|---|---|
| 1 | Muito Bom | 1 |
| 2 | Bom | 2 |
| 3 | Normal | 3 |

---

### `PROB_CAUSA_SOL_TIPO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TPPCS_ID` | int | NO |  | **PK** |
| 2 | `TPPCS_DESCRICAO` | nvarchar(max) | NO |  |  |

**PK**: `TPPCS_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `PROB_CAUSA_SOL.PCS_TPPCS_ID`

**Implicit relations** _(by column naming)_:
- `TPPCS_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TPPCS_ID` | `TPPCS_DESCRICAO` |
|---|---|
| 1 | Causa |
| 2 | Problema |
| 3 | Solução |

---

### `PROB_CAUSA_SOL` — *2 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PCS_ID` | int | NO |  | **PK** |
| 2 | `PCS_DESCRICAO` | nvarchar(max) | NO |  |  |
| 3 | `PCS_DATACRIACAO` | smalldatetime | NO |  |  |
| 4 | `PCS_CRIADOR` | nvarchar(max) | NO |  |  |
| 5 | `PCS_DATAACTUALIZACAO` | smalldatetime | YES |  |  |
| 6 | `PCS_ACTUALIZADOR` | nvarchar(max) | YES |  |  |
| 7 | `PCS_TPPCS_ID` | int | NO |  | FK → `PROB_CAUSA_SOL_TIPO.TPPCS_ID` |
| 8 | `PCS_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |

**PK**: `PCS_ID`

**FKs declared (out)**:
- `PCS_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `PCS_TPPCS_ID` → `PROB_CAUSA_SOL_TIPO.TPPCS_ID`

**FKs declared (in)** — *2 references*:
- `PRODUTO_PROB_CAUSA_SOL.PP_PCS_ID`
- `PRODUTO_PROB_CAUSA_SOL.PP_PCS_PCS_ID`

**Implicit relations** _(by column naming)_:
- `PCS_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `PCS_ID` | `PCS_DESCRICAO` | `PCS_DATACRIACAO` | `PCS_CRIADOR` | `PCS_DATAACTUALIZACAO` | `PCS_ACTUALIZADOR` | `PCS_TPPCS_ID` | `PCS_FP_ID` |
|---|---|---|---|---|---|---|---|
| 25 | Matriz com pormenores descolados quan... | 2009-09-28 10:44 | PASSOS\FMarcal | 2009-09-28 10:49 | PASSOS\FMarcal | 2 | 27 |
| 26 | Acabamento na zona exterior do suport... | 2009-10-28 13:31 | NunoAndré-PC\Nuno André | — | — | 2 | 8 |

---

### `AUDIT_ENT` — *0 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `AUDE_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 2 | `AUDE_AUD_ID` | int | YES |  | FK → `AUDIT.AUD_ID` |

**PK**: _(none declared)_

**FKs declared (out)**:
- `AUDE_AUD_ID` → `AUDIT.AUD_ID`
- `AUDE_E_ID` → `ENTIDADE.E_ID`


**Sample**: _(table empty or unreadable)_

---

<a id="stock-inventrio-movimentos-encomendas"></a>
## Stock, inventário, movimentos, encomendas

| Tabela | Linhas | Cols | PK | FK out | FK in |
|---|---:|---:|---|---:|---:|
| `MOVIMENTO` | 12 392 449 | 41 | MOV_ID | 5 | 3 |
| `PEDIDOS` | 115 793 | 18 | PED_ID, PED_E_ID | 0 | 2 |
| `TRANSP_VAL` | 76 047 | 3 | TRVAL_VAL_ID, TRVAL_TR_ID | 2 | 0 |
| `TRANSP_DOCS` | 46 810 | 8 | TRDOC_DOCS_ID, TRDOC_TR_ID | 2 | 0 |
| `TRANSPORTE` | 11 363 | 43 | TR_ID | 5 | 9 |
| `TRANSP_DESP` | 4 021 | 7 | TRDESP_ID | 2 | 0 |
| `TRANSP_DATAS` | 3 016 | 7 | TRDT_ID | 2 | 0 |
| `LISTA_PRODUTO` | 2 134 | 15 | LP_L_ID, LP_P_ID | 2 | 0 |
| `TRANSP_ENTIDADE` | 2 003 | 15 | TRE_ID | 3 | 0 |
| `ENCOMENDA` | 410 | 13 | ENC_ID | 2 | 1 |
| `LISTA` | 163 | 6 | L_ID | 1 | 4 |
| `TRANSP_DOCS_STD` | 101 | 3 | DOCS_ID | 0 | 2 |
| `LISTA_COORDENADAS` | 84 | 7 | LCOORD_ID | 1 | 0 |
| `AgenteEncomendaProduto` | 59 | 6 | codEncomenda, codProduto | 2 | 0 |
| `TRANSP_TIPO` | 58 | 9 | TRTP_ID | 1 | 5 |
| `MOVIMENTO_ATTACH` | 37 | 5 | MATCH_ID | 1 | 0 |
| `TRANSP_TRACKER` | 34 | 3 | TRACKER_ID | 0 | 0 |
| `ARMAZEM` | 25 | 9 | ARM_ID | 1 | 1 |
| `TRANSP_DESP_TIPO` | 20 | 3 | TRDESPTP_ID | 0 | 1 |
| `TRANSP_DOCS_DEST_TIPO` | 20 | 3 | DTD_DEST_ID, DTD_TRTP_ID, DTD_DOCS_ID | 3 | 0 |
| `MOVIMENTO_TIPO` | 15 | 2 | TPMOV_ID | 0 | 0 |
| `AgenteEncomenda` | 14 | 11 | codEncomenda | 0 | 1 |
| `Encomenda_trk` | 7 | 12 | codEncomenda | 0 | 0 |
| `LISTA_MOVIMENTO` | 5 | 4 | LM_ID | 1 | 0 |
| `TRANSP_DESTINO` | 4 | 2 | DEST_ID | 0 | 2 |
| `AgenteEncomendaEstado` | 3 | 2 | codEstado | 0 | 0 |
| `ENCOMENDA_ESTADO` | 3 | 3 | EE_ID | 0 | 1 |
| `TRANSP_DATAS_CLASSIFICACAO` | 3 | 2 | TRDTCL_ID | 0 | 1 |
| `LISTA_TIPO` | 2 | 2 | LTP_ID | 1 | 2 |

### `MOVIMENTO` — *12 392 449 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MOV_ID` | int | NO |  | **PK** |
| 2 | `MOV_DATA` | smalldatetime | YES |  |  |
| 3 | `MOV_DATASAIDA` | smalldatetime | YES |  |  |
| 4 | `MOV_QUANTIDADE` | float | NO |  |  |
| 5 | `MOV_PRECOUNITARIO` | float | NO |  |  |
| 6 | `MOV_PRECOVENDA` | float | NO |  |  |
| 7 | `MOV_DESCONTO` | float | NO |  |  |
| 8 | `MOV_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 9 | `MOV_PROBLEMA` | nvarchar(max) | YES |  |  |
| 10 | `MOV_NUMUTIL` | int | NO |  |  |
| 11 | `MOV_OF_ID` | int | YES |  |  |
| 12 | `MOV_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 13 | `MOV_P_ID` | int | YES |  |  |
| 14 | `MOV_TPMOV_ID` | int | NO |  |  |
| 15 | `MOV_MOV_ID` | int | YES |  | FK → `MOVIMENTO.MOV_ID` |
| 16 | `MOV_ARM_ID` | int | YES |  |  |
| 17 | `MOV_LM_ID` | int | YES |  |  |
| 18 | `MOV_SERVER` | nvarchar(max) | NO |  |  |
| 19 | `MOV_TR_ID` | int | YES |  |  |
| 20 | `MOV_PRODF_ID` | int | YES |  |  |
| 21 | `MOV_PL_ID` | int | YES |  |  |
| 22 | `MOV_QTD_BAL` | float | NO |  |  |
| 23 | `MOV_DECK_PART` | nvarchar(max) | NO |  |  |
| 24 | `MOV_LOTE` | nvarchar(max) | YES |  |  |
| 25 | `MOV_ACERTO` | bit | NO |  |  |
| 26 | `MOV_ACESSORIO_ADICIONAL` | bit | NO |  |  |
| 27 | `MOV_DEFEITUOSO` | bit | NO |  |  |
| 28 | `MOV_SATISFEITO` | bit | NO |  |  |
| 29 | `MOV_ID_PEDIDO` | int | YES |  |  |
| 30 | `MOV_ATRIB_ID` | int | YES |  |  |
| 31 | `MOV_SHOP_ORDER_ID` | varchar(50) | YES |  |  |
| 32 | `MOV_SHOP_ORDER_ITEM_ID` | int | YES |  |  |
| 33 | `MOV_SHOP_UPDATED_AT` | smalldatetime | YES |  |  |
| 34 | `MOV_E_ID_RESPONSAVEL` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 35 | `MOV_SHOP_SHIPPING` | nvarchar(max) | YES |  |  |
| 36 | `MOV_SHOP_ENTITY_ID` | int | YES |  |  |
| 37 | `MOV_DATA_APROVADO` | smalldatetime | YES |  |  |
| 38 | `MOV_E_ID_APROVA` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 39 | `MOV_ENVIA_ANEXO` | bit | NO |  |  |
| 40 | `MOV_FP_ID` | int | YES |  | FK → `FASES_PRODUCAO.FP_ID` |
| 41 | `MOV_OFFP_ID` | int | YES |  |  |

**PK**: `MOV_ID`

**FKs declared (out)**:
- `MOV_E_ID_RESPONSAVEL` → `ENTIDADE.E_ID`
- `MOV_E_ID` → `ENTIDADE.E_ID`
- `MOV_E_ID_APROVA` → `ENTIDADE.E_ID`
- `MOV_FP_ID` → `FASES_PRODUCAO.FP_ID`
- `MOV_MOV_ID` → `MOVIMENTO.MOV_ID`

**FKs declared (in)** — *3 references*:
- `MOVIMENTO_ATTACH.MATCH_MOV_ID`
- `MOVIMENTO.MOV_MOV_ID`
- `ORDEMFABRICO.OF_MOV_ID`

**Implicit relations** _(by column naming)_:
- `MOV_ID` → likely `MOVIMENTO`
- `MOV_OF_ID` → likely _(no obvious target)_
- `MOV_P_ID` → likely _(no obvious target)_
- `MOV_TPMOV_ID` → likely _(no obvious target)_
- `MOV_ARM_ID` → likely _(no obvious target)_
- `MOV_LM_ID` → likely _(no obvious target)_
- `MOV_TR_ID` → likely _(no obvious target)_
- `MOV_PRODF_ID` → likely _(no obvious target)_
- `MOV_PL_ID` → likely _(no obvious target)_
- `MOV_ATRIB_ID` → likely _(no obvious target)_
- `MOV_SHOP_ORDER_ID` → likely _(no obvious target)_
- `MOV_SHOP_ORDER_ITEM_ID` → likely _(no obvious target)_
- `MOV_SHOP_ENTITY_ID` → likely _(no obvious target)_
- `MOV_OFFP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 41 cols)*:

| `MOV_ID` | `MOV_DATA` | `MOV_DATASAIDA` | `MOV_QUANTIDADE` | `MOV_PRECOUNITARIO` | `MOV_PRECOVENDA` | `MOV_DESCONTO` | `MOV_OBSERVACOES` |
|---|---|---|---|---|---|---|---|
| 15388524 | 2023-11-17 10:02 | — | 0.5 | 0.29 | 0.0 | 0.0 | OF: 10280906 |
| 15388525 | 2023-11-17 10:02 | — | 0.5 | 0.29 | 0.0 | 0.0 | OF: 10280906 |
| 15388526 | 2023-11-17 10:02 | — | 0.0 | 0.25 | 0.0 | 0.0 | OF: 10280906 |

---

### `PEDIDOS` — *115 793 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `PED_ID` | int | NO |  | **PK** |
| 2 | `PED_DATA` | smalldatetime | NO |  |  |
| 3 | `PED_E_ID_RESPONSAVEL` | int | YES |  |  |
| 4 | `PED_E_ID_APROVADOR` | int | YES |  |  |
| 5 | `PED_DATA_APROVADO` | smalldatetime | YES |  |  |
| 6 | `PED_APROVADO` | bit | NO |  |  |
| 7 | `PED_EMAIL` | nvarchar(max) | YES |  |  |
| 8 | `PED_CONTACTO` | nvarchar(max) | YES |  |  |
| 9 | `PED_NOTAS` | nvarchar(max) | YES |  |  |
| 10 | `PED_PT` | bit | NO |  |  |
| 11 | `PED_E_ID` | int | NO |  | **PK** |
| 12 | `PED_OF_ID` | int | YES |  |  |
| 13 | `PED_SHOP_ORDER_ID` | varchar(50) | YES |  |  |
| 14 | `PED_PRONTOPAGAMENTO` | bit | NO |  |  |
| 15 | `PED_PAGO` | bit | NO |  |  |
| 16 | `PED_PAGODATA` | date | YES |  |  |
| 17 | `PED_PAGAR` | bit | NO |  |  |
| 18 | `PED_PRIORITARIO` | bit | NO |  |  |

**PK**: `PED_ID, PED_E_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `SGIDI_PASTA.SGIDIP_PED_ID`
- `SGIDI_PASTA.SGIDIP_E_ID`

**Implicit relations** _(by column naming)_:
- `PED_ID` → likely `PEDIDOS`
- `PED_E_ID` → likely _(no obvious target)_
- `PED_OF_ID` → likely _(no obvious target)_
- `PED_SHOP_ORDER_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 18 cols)*:

| `PED_ID` | `PED_DATA` | `PED_E_ID_RESPONSAVEL` | `PED_E_ID_APROVADOR` | `PED_DATA_APROVADO` | `PED_APROVADO` | `PED_EMAIL` | `PED_CONTACTO` |
|---|---|---|---|---|---|---|---|
| 0 | 2025-10-21 11:48 | 20683 | — | — | false | NUNO.VELOSO@NELO.EU | Sr. Edgar |
| 0 | 2025-10-21 09:03 | 20683 | — | — | false | pedrofonseca@decatlo-compositos.com | Sr,Pedro Fonseca |
| 0 | 2025-10-21 10:00 | 20683 | — | — | false | sandra.neves@plastirso.pt |  |

---

### `TRANSP_VAL` — *76 047 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRVAL_VAL_ID` | int | NO |  | **PK** FK → `VALOR.VAL_ID` |
| 2 | `TRVAL_TR_ID` | int | NO |  | **PK** FK → `TRANSPORTE.TR_ID` |
| 3 | `TRVAL_VALOR` | float | NO |  |  |

**PK**: `TRVAL_VAL_ID, TRVAL_TR_ID`

**FKs declared (out)**:
- `TRVAL_TR_ID` → `TRANSPORTE.TR_ID`
- `TRVAL_VAL_ID` → `VALOR.VAL_ID`


**Sample (TOP 3)**:

| `TRVAL_VAL_ID` | `TRVAL_TR_ID` | `TRVAL_VALOR` |
|---|---|---|
| 2 | 1 | 0.0 |
| 2 | 2 | 0.0 |
| 2 | 3 | 0.0 |

---

### `TRANSP_DOCS` — *46 810 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRDOC_DOCS_ID` | int | NO |  | **PK** FK → `TRANSP_DOCS_STD.DOCS_ID` |
| 2 | `TRDOC_TR_ID` | int | NO |  | **PK** FK → `TRANSPORTE.TR_ID` |
| 3 | `TRDOC_DOCS_NOME` | nvarchar(max) | NO |  |  |
| 4 | `TRDOC_DOC_CAMINHO` | nvarchar(max) | YES |  |  |
| 5 | `TRDOC_TRATADO` | bit | NO |  |  |
| 6 | `TRDOC_OBSERVACOES` | nvarchar(max) | NO |  |  |
| 7 | `TRDOC_DOCNUM` | nvarchar(max) | NO |  |  |
| 8 | `TRDOC_DATA` | smalldatetime | YES |  |  |

**PK**: `TRDOC_DOCS_ID, TRDOC_TR_ID`

**FKs declared (out)**:
- `TRDOC_DOCS_ID` → `TRANSP_DOCS_STD.DOCS_ID`
- `TRDOC_TR_ID` → `TRANSPORTE.TR_ID`


**Sample (TOP 3)**:

| `TRDOC_DOCS_ID` | `TRDOC_TR_ID` | `TRDOC_DOCS_NOME` | `TRDOC_DOC_CAMINHO` | `TRDOC_TRATADO` | `TRDOC_OBSERVACOES` | `TRDOC_DOCNUM` | `TRDOC_DATA` |
|---|---|---|---|---|---|---|---|
| 6 | 1 | Factura nossa | — | false |  |  | — |
| 6 | 2129 | Factura | — | true |  | 29005806 | 2009-01-08 00:00 |
| 6 | 2130 | Factura | — | true |  | 29005807 | 2009-01-09 00:00 |

---

### `TRANSPORTE` — *11 363 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TR_ID` | int | NO |  | **PK** |
| 2 | `TR_DEST_ID` | int | YES |  | FK → `TRANSP_DESTINO.DEST_ID` |
| 3 | `TR_TRTP_ID` | int | YES |  | FK → `TRANSP_TIPO.TRTP_ID` |
| 4 | `TR_E_ID` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 5 | `TR_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 6 | `TR_DATA` | date | YES |  |  |
| 7 | `TR_DATA_REGRESSO` | date | YES |  |  |
| 8 | `TR_PAISES_ID` | int | YES |  | FK → `PAISES.PAISES_ID` |
| 9 | `TR_MORADA` | nvarchar(max) | NO |  |  |
| 10 | `TR_OBSERVACOES` | nvarchar(max) | NO |  |  |
| 11 | `TR_DESCRICAO` | nvarchar(max) | NO |  |  |
| 12 | `TR_TRANSPORTE_NOSSO` | bit | NO |  |  |
| 13 | `TR_GOOGLE_NAO` | bit | NO |  |  |
| 14 | `TR_CONTACTO_DESTINO` | nvarchar(max) | NO |  |  |
| 15 | `TR_TRACK_TIPO` | nvarchar(max) | YES |  |  |
| 16 | `TR_TRACK_NR` | nvarchar(max) | YES |  |  |
| 17 | `TR_DOCSENVIADOS` | bit | YES |  |  |
| 18 | `TR_PUBLICO` | bit | NO |  |  |
| 19 | `TR_TRACK_LINK` | nvarchar(max) | YES |  |  |
| 20 | `TR_CELESTE` | nvarchar(max) | YES |  |  |
| 21 | `TR_DATA_ENTREGA_PREV` | date | YES |  |  |
| 22 | `TR_DATA_ENTREGA` | date | YES |  |  |
| 23 | `TR_TRACKER_DATA` | date | YES |  |  |
| 24 | `TR_TRACKER_ID` | int | YES |  |  |
| 25 | `TR_TRTP_ID_EMB` | int | YES |  | FK → `TRANSP_TIPO.TRTP_ID` |
| 26 | `TR_OPERADOR_CODIGO` | int | YES |  |  |
| 27 | `TR_PORTO_CODIGO` | int | YES |  |  |
| 28 | `TR_LATITUDE` | decimal | YES |  |  |
| 29 | `TR_LONGITUDE` | decimal | YES |  |  |
| 30 | `TR_COORD_ULT_UPD` | datetime | YES |  |  |
| 31 | `TR_ESTADO_COD` | int | YES |  |  |
| 32 | `TR_DATA_PREV_CHEG` | decimal | YES |  |  |
| 33 | `TR_HORA_PREV_CHEG` | decimal | YES |  |  |
| 34 | `TR_AUX_ORDER` | int | YES |  |  |
| 35 | `TR_LATITUDE_ORIG` | decimal | YES |  |  |
| 36 | `TR_LONGITUDE_ORIG` | decimal | YES |  |  |
| 37 | `TR_LATITUDE_DEST` | decimal | YES |  |  |
| 38 | `TR_LONGITUDE_DEST` | decimal | YES |  |  |
| 39 | `TR_VALOR_ESTIMADO` | float | NO |  |  |
| 40 | `TR_OBS_CLIENTE` | nvarchar(max) | YES |  |  |
| 41 | `TR_CO2` | float | NO |  |  |
| 42 | `TR_DISTANCIA` | float | NO |  |  |
| 43 | `TR_QUARTOS` | int | NO |  |  |

**PK**: `TR_ID`

**FKs declared (out)**:
- `TR_E_ID` → `ENTIDADE.E_ID`
- `TR_PAISES_ID` → `PAISES.PAISES_ID`
- `TR_DEST_ID` → `TRANSP_DESTINO.DEST_ID`
- `TR_TRTP_ID` → `TRANSP_TIPO.TRTP_ID`
- `TR_TRTP_ID_EMB` → `TRANSP_TIPO.TRTP_ID`

**FKs declared (in)** — *9 references*:
- `PLANEAMENTO_DIARIO.TransporteId`
- `SGIDI_PASTA.SGIDIP_TR_ID`
- `TRANSP_DATAS.TRDT_TR_ID`
- `TRANSP_DESP.TRDESP_TR_ID`
- `TRANSP_DOCS.TRDOC_TR_ID`
- `TRANSP_ENTIDADE.TRE_TR_ID`
- `TRANSP_OF.TROF_TR_ID`
- `TRANSP_VAL.TRVAL_TR_ID`
- `TRANSPORTE_VERIFICACAO.TRV_TR_ID`

**Implicit relations** _(by column naming)_:
- `TR_ID` → likely `TransporteDestino`
- `TR_TRACKER_ID` → likely _(no obvious target)_
- `TR_ESTADO_COD` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 43 cols)*:

| `TR_ID` | `TR_DEST_ID` | `TR_TRTP_ID` | `TR_E_ID` | `TR_DATA_CRIACAO` | `TR_DATA` | `TR_DATA_REGRESSO` | `TR_PAISES_ID` |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 4 | 20513 | 2009-01-12 17:07 | 2001-10-31 | — | 143 |
| 2 | — | 4 | — | 2009-01-12 17:07 | 2001-11-01 | — | — |
| 3 | — | 4 | — | 2009-01-12 17:07 | 2001-11-01 | — | — |

---

### `TRANSP_DESP` — *4 021 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRDESP_ID` | int | NO |  | **PK** |
| 2 | `TRDESP_TRDESPTP_ID` | int | NO |  | FK → `TRANSP_DESP_TIPO.TRDESPTP_ID` |
| 3 | `TRDESP_TR_ID` | int | NO |  | FK → `TRANSPORTE.TR_ID` |
| 4 | `TRDESP_OBS` | nvarchar(max) | YES |  |  |
| 5 | `TRDESP_QTD` | int | NO |  |  |
| 6 | `TRDESP_VALOR` | numeric | NO |  |  |
| 7 | `TRDESP_VALOR_ESTIMADO` | numeric | NO |  |  |

**PK**: `TRDESP_ID`

**FKs declared (out)**:
- `TRDESP_TRDESPTP_ID` → `TRANSP_DESP_TIPO.TRDESPTP_ID`
- `TRDESP_TR_ID` → `TRANSPORTE.TR_ID`


**Implicit relations** _(by column naming)_:
- `TRDESP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TRDESP_ID` | `TRDESP_TRDESPTP_ID` | `TRDESP_TR_ID` | `TRDESP_OBS` | `TRDESP_QTD` | `TRDESP_VALOR` | `TRDESP_VALOR_ESTIMADO` |
|---|---|---|---|---|---|---|
| 14 | 3 | 3147 |  | 1 | 1641.27 | 0.00 |
| 16 | 1 | 3147 |  | 1 | 20.51 | 0.00 |
| 17 | 5 | 3147 | André | 1 | 386.19 | 0.00 |

---

### `TRANSP_DATAS` — *3 016 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRDT_ID` | int | NO |  | **PK** |
| 2 | `TRDT_TR_ID` | int | NO |  | FK → `TRANSPORTE.TR_ID` |
| 3 | `TRDT_DATA_ACTUAL` | date | NO |  |  |
| 4 | `TRDT_DATA_NOVA` | date | NO |  |  |
| 5 | `TRDT_TRDTCL_ID` | int | NO |  | FK → `TRANSP_DATAS_CLASSIFICACAO.TRDTCL_ID` |
| 6 | `TRDT_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 7 | `TRDT_DATA_CRIACAO` | smalldatetime | NO |  |  |

**PK**: `TRDT_ID`

**FKs declared (out)**:
- `TRDT_TRDTCL_ID` → `TRANSP_DATAS_CLASSIFICACAO.TRDTCL_ID`
- `TRDT_TR_ID` → `TRANSPORTE.TR_ID`


**Implicit relations** _(by column naming)_:
- `TRDT_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TRDT_ID` | `TRDT_TR_ID` | `TRDT_DATA_ACTUAL` | `TRDT_DATA_NOVA` | `TRDT_TRDTCL_ID` | `TRDT_OBSERVACOES` | `TRDT_DATA_CRIACAO` |
|---|---|---|---|---|---|---|
| 4 | 18012 | 2018-12-07 | 2018-12-14 | 3 |  | 2019-09-24 09:00 |
| 5 | 18121 | 2018-01-04 | 2019-01-04 | 1 | erro no ano | 2019-09-24 09:00 |
| 6 | 18092 | 2018-12-07 | 2018-12-14 | 1 | O transporte só saiu na terça e passo... | 2019-09-24 09:00 |

---

### `LISTA_PRODUTO` — *2 134 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `LP_L_ID` | int | NO |  | **PK** FK → `LISTA.L_ID` |
| 2 | `LP_P_ID` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |
| 3 | `LP_QTD` | float | NO |  |  |
| 4 | `LP_OBS` | nvarchar(max) | NO |  |  |
| 5 | `LP_SITIO` | nvarchar(max) | NO |  |  |
| 6 | `LP_CORES` | bit | NO |  |  |
| 7 | `LP_TOPOS` | bit | NO |  |  |
| 8 | `LP_LATERAIS` | bit | NO |  |  |
| 9 | `LP_QUINAS` | bit | NO |  |  |
| 10 | `LP_CASCO` | bit | NO |  |  |
| 11 | `LP_GOLA` | bit | NO |  |  |
| 12 | `LP_RISCA` | bit | NO |  |  |
| 13 | `LP_EXTRA` | bit | NO |  |  |
| 14 | `LP_CUSTO_EXTRA_OF` | bit | NO |  |  |
| 15 | `LP_DECK` | bit | NO |  |  |

**PK**: `LP_L_ID, LP_P_ID`

**FKs declared (out)**:
- `LP_L_ID` → `LISTA.L_ID`
- `LP_P_ID` → `PRODUTO.P_ID`


**Sample (TOP 3)** *(showing 8 of 15 cols)*:

| `LP_L_ID` | `LP_P_ID` | `LP_QTD` | `LP_OBS` | `LP_SITIO` | `LP_CORES` | `LP_TOPOS` | `LP_LATERAIS` |
|---|---|---|---|---|---|---|---|
| 4 | 20246 | 5.0 |  | Cx B2 | false | false | false |
| 4 | 20247 | 10.0 |  | Cx FP 1 | false | false | false |
| 4 | 20248 | 20.0 |  | AG G5 | false | false | false |

---

### `TRANSP_ENTIDADE` — *2 003 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRE_ID` | int | NO |  | **PK** |
| 2 | `TRE_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 3 | `TRE_TR_ID` | int | NO |  | FK → `TRANSPORTE.TR_ID` |
| 4 | `TRE_DATA_IDA` | smalldatetime | YES |  |  |
| 5 | `TRE_DATA_VOLTA` | smalldatetime | YES |  |  |
| 6 | `TRE_VOO_IDA` | nvarchar(max) | YES |  |  |
| 7 | `TRE_VOO_VOLTA` | nvarchar(max) | YES |  |  |
| 8 | `TRE_IDA_CONF` | bit | NO |  |  |
| 9 | `TRE_VOLTA_CONF` | bit | NO |  |  |
| 10 | `TRE_NOITES` | int | NO |  |  |
| 11 | `TRE_MARCADO` | bit | NO |  |  |
| 12 | `TRE_PAGO` | bit | NO |  |  |
| 13 | `TRE_TRTP_ID` | int | YES |  | FK → `TRANSP_TIPO.TRTP_ID` |
| 14 | `TRE_VALOR_ORCAMENTADO` | float | NO |  |  |
| 15 | `TRE_VALOR_REAL` | float | NO |  |  |

**PK**: `TRE_ID`

**FKs declared (out)**:
- `TRE_E_ID` → `ENTIDADE.E_ID`
- `TRE_TRTP_ID` → `TRANSP_TIPO.TRTP_ID`
- `TRE_TR_ID` → `TRANSPORTE.TR_ID`


**Implicit relations** _(by column naming)_:
- `TRE_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 15 cols)*:

| `TRE_ID` | `TRE_E_ID` | `TRE_TR_ID` | `TRE_DATA_IDA` | `TRE_DATA_VOLTA` | `TRE_VOO_IDA` | `TRE_VOO_VOLTA` | `TRE_IDA_CONF` |
|---|---|---|---|---|---|---|---|
| 9 | 20620 | 3147 | 2011-01-16 00:00 | 2011-01-24 00:00 | LH1179 | SQ226 | true |
| 10 | 20680 | 3147 | 2011-01-17 00:00 | 2011-01-24 00:00 | LH1179 | SQ226 | true |
| 11 | 20642 | 3148 | 2011-01-04 00:00 | 2011-01-06 00:00 | FR8348 | FR8347 | true |

---

### `ENCOMENDA` — *410 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ENC_ID` | int | NO |  | **PK** |
| 2 | `ENC_DATAENCOMENDA` | smalldatetime | NO |  |  |
| 3 | `ENC_DATAPREVISTAENTREGA` | smalldatetime | YES |  |  |
| 4 | `ENC_DATAENTREGA` | smalldatetime | YES |  |  |
| 5 | `ENC_MORADAENTREGA` | nvarchar(max) | YES |  |  |
| 6 | `ENC_PRECOTOTAL` | float | NO |  |  |
| 7 | `ENC_TOTALPAGO` | float | NO |  |  |
| 8 | `ENC_OBSERVACOES` | nvarchar(max) | YES |  |  |
| 9 | `ENC_NOME` | nvarchar(max) | NO |  |  |
| 10 | `ENC_TRANSPORTE` | nvarchar(max) | YES |  |  |
| 11 | `ENC_E_ID` | int | NO |  | FK → `ENTIDADE.E_ID` |
| 12 | `ENC_EE_ID` | int | NO |  | FK → `ENCOMENDA_ESTADO.EE_ID` |
| 13 | `ENC_TR_ID` | int | YES |  |  |

**PK**: `ENC_ID`

**FKs declared (out)**:
- `ENC_EE_ID` → `ENCOMENDA_ESTADO.EE_ID`
- `ENC_E_ID` → `ENTIDADE.E_ID`

**FKs declared (in)** — *1 references*:
- `ORDEMFABRICO.OF_ENC_ID`

**Implicit relations** _(by column naming)_:
- `ENC_ID` → likely `ENCOMENDA_ESTADO`
- `ENC_TR_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 13 cols)*:

| `ENC_ID` | `ENC_DATAENCOMENDA` | `ENC_DATAPREVISTAENTREGA` | `ENC_DATAENTREGA` | `ENC_MORADAENTREGA` | `ENC_PRECOTOTAL` | `ENC_TOTALPAGO` | `ENC_OBSERVACOES` |
|---|---|---|---|---|---|---|---|
| 1129 | 1900-01-01 00:00 | — | 2001-12-15 00:00 |  | 0.0 | 0.0 | — |
| 1130 | 1900-01-01 00:00 | — | 2002-06-30 00:00 |  | 0.0 | 0.0 | — |
| 1131 | 1900-01-01 00:00 | — | 2002-03-15 00:00 |  | 0.0 | 0.0 | — |

---

### `LISTA` — *163 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `L_ID` | int | NO |  | **PK** |
| 2 | `L_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 3 | `L_DESCRICAO` | nvarchar(max) | NO |  |  |
| 4 | `L_OBS` | nvarchar(max) | NO |  |  |
| 5 | `L_LTP_ID` | int | NO |  | FK → `LISTA_TIPO.LTP_ID` |
| 6 | `L_IMAGEM` | nvarchar(max) | YES |  |  |

**PK**: `L_ID`

**FKs declared (out)**:
- `L_LTP_ID` → `LISTA_TIPO.LTP_ID`

**FKs declared (in)** — *4 references*:
- `LISTA_COORDENADAS.LCOORD_L_ID`
- `LISTA_MOVIMENTO.LM_L_ID`
- `LISTA_PRODUTO.LP_L_ID`
- `PRODUTO_COMPONENTE.COMP_L_ID`

**Implicit relations** _(by column naming)_:
- `L_ID` → likely `LISTA_PRODUTO`

**Sample (TOP 3)**:

| `L_ID` | `L_DATA_CRIACAO` | `L_DESCRICAO` | `L_OBS` | `L_LTP_ID` | `L_IMAGEM` |
|---|---|---|---|---|---|
| 4 | 2009-04-15 00:00 | Camião |  | 1 | — |
| 8 | 2009-04-23 00:00 | Terroso (Entrdas/Saidas) |  | 1 | — |
| 11 | 2009-07-01 00:00 | Serralharia |   | 1 | — |

---

### `TRANSP_DOCS_STD` — *101 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DOCS_ID` | int | NO |  | **PK** |
| 2 | `DOCS_NOME` | nvarchar(max) | NO |  |  |
| 3 | `DOCS_DESCRICAO` | nvarchar(max) | YES |  |  |

**PK**: `DOCS_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `TRANSP_DOCS_DEST_TIPO.DTD_DOCS_ID`
- `TRANSP_DOCS.TRDOC_DOCS_ID`

**Implicit relations** _(by column naming)_:
- `DOCS_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `DOCS_ID` | `DOCS_NOME` | `DOCS_DESCRICAO` |
|---|---|---|
| 6 | Factura nossa | — |
| 7 | DU | Modelo 3 - preencher data e código |
| 10 | Fumigação | Certificado Fumigação |

---

### `LISTA_COORDENADAS` — *84 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `LCOORD_ID` | int | NO |  | **PK** |
| 2 | `LCOORD_L_ID` | int | NO |  | FK → `LISTA.L_ID` |
| 3 | `LCOORD_1` | int | NO |  |  |
| 4 | `LCOORD_2` | int | NO |  |  |
| 5 | `LCOORD_3` | int | NO |  |  |
| 6 | `LCOORD_4` | int | NO |  |  |
| 7 | `LCOORD_ATRIB_ID` | int | NO |  |  |

**PK**: `LCOORD_ID`

**FKs declared (out)**:
- `LCOORD_L_ID` → `LISTA.L_ID`


**Implicit relations** _(by column naming)_:
- `LCOORD_ID` → likely _(no obvious target)_
- `LCOORD_ATRIB_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `LCOORD_ID` | `LCOORD_L_ID` | `LCOORD_1` | `LCOORD_2` | `LCOORD_3` | `LCOORD_4` | `LCOORD_ATRIB_ID` |
|---|---|---|---|---|---|---|
| 1 | 23 | 364 | 28 | 420 | 70 | 9 |
| 2 | 23 | 280 | 28 | 329 | 70 | 4 |
| 4 | 23 | 469 | 42 | 497 | 63 | 13 |

---

### `AgenteEncomendaProduto` — *59 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codEncomenda` | int | NO |  | **PK** FK → `AgenteEncomenda.codEncomenda` |
| 2 | `codProduto` | int | NO |  | **PK** FK → `PRODUTO.P_ID` |
| 3 | `qtd` | int | YES |  |  |
| 4 | `preco` | decimal | YES |  |  |
| 5 | `auxTipo` | int | YES |  |  |
| 6 | `auxUnitario` | decimal | YES |  |  |

**PK**: `codEncomenda, codProduto`

**FKs declared (out)**:
- `codEncomenda` → `AgenteEncomenda.codEncomenda`
- `codProduto` → `PRODUTO.P_ID`


**Sample (TOP 3)**:

| `codEncomenda` | `codProduto` | `qtd` | `preco` | `auxTipo` | `auxUnitario` |
|---|---|---|---|---|---|
| 1 | 22362 | 1 | 73.17 | 11 | 73.17 |
| 1 | 22363 | 1 | 56.91 | 10 | 56.91 |
| 1 | 22420 | 1 | — | 10 | — |

---

### `TRANSP_TIPO` — *58 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRTP_ID` | int | NO |  | **PK** |
| 2 | `TRTP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TRTP_TRTP_ID` | int | YES |  | FK → `TRANSP_TIPO.TRTP_ID` |
| 4 | `TRTP_PESO_VOLUMETRICO` | float | NO |  |  |
| 5 | `TRTP_APLICA_VOLUMETRICO` | bit | NO |  |  |
| 6 | `TRTP_FACTOR_CO2` | float | NO |  |  |
| 7 | `TRTP_COMPRIMENTO` | float | NO |  |  |
| 8 | `TRTP_LARGURA` | float | NO |  |  |
| 9 | `TRTP_ALTURA` | float | NO |  |  |

**PK**: `TRTP_ID`

**FKs declared (out)**:
- `TRTP_TRTP_ID` → `TRANSP_TIPO.TRTP_ID`

**FKs declared (in)** — *5 references*:
- `TRANSP_DOCS_DEST_TIPO.DTD_TRTP_ID`
- `TRANSP_ENTIDADE.TRE_TRTP_ID`
- `TRANSP_TIPO.TRTP_TRTP_ID`
- `TRANSPORTE.TR_TRTP_ID`
- `TRANSPORTE.TR_TRTP_ID_EMB`

**Implicit relations** _(by column naming)_:
- `TRTP_ID` → likely _(no obvious target)_

**Sample (TOP 3)** *(showing 8 of 9 cols)*:

| `TRTP_ID` | `TRTP_NOME` | `TRTP_TRTP_ID` | `TRTP_PESO_VOLUMETRICO` | `TRTP_APLICA_VOLUMETRICO` | `TRTP_FACTOR_CO2` | `TRTP_COMPRIMENTO` | `TRTP_LARGURA` |
|---|---|---|---|---|---|---|---|
| 1 | Avião | 10 | 0.0 | false | 0.0 | 0.0 | 0.0 |
| 2 | Camião | 10 | 0.0 | false | 0.0 | 0.0 | 0.0 |
| 3 | Barco | 10 | 0.0 | false | 0.0 | 0.0 | 0.0 |

---

### `MOVIMENTO_ATTACH` — *37 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `MATCH_ID` | int | NO |  | **PK** |
| 2 | `MATCH_NOME` | nvarchar(max) | NO |  |  |
| 3 | `MATCH_DESCRICAO` | nvarchar(max) | YES |  |  |
| 4 | `MATCH_MOV_ID` | int | NO |  | FK → `MOVIMENTO.MOV_ID` |
| 5 | `MATCH_FILE` | nvarchar(max) | NO |  |  |

**PK**: `MATCH_ID`

**FKs declared (out)**:
- `MATCH_MOV_ID` → `MOVIMENTO.MOV_ID`


**Implicit relations** _(by column naming)_:
- `MATCH_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `MATCH_ID` | `MATCH_NOME` | `MATCH_DESCRICAO` | `MATCH_MOV_ID` | `MATCH_FILE` |
|---|---|---|---|---|
| 12 | SIKA - Biresin CH80 - Endurecedor (B)... |  | 1661273 | \\server\Documents\imagens_BD\Docs_Mo... |
| 14 | SIKA - Biresin CR82, CH80 - Temperatu... |  | 1661274 | \\server\Documents\imagens_BD\Docs_Mo... |
| 15 | SIKA - Biresin CR82 - Resina (A) (Seg... |  | 1661276 | \\server\Documents\imagens_BD\Docs_Mo... |

---

### `TRANSP_TRACKER` — *34 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRACKER_ID` | int | NO |  | **PK** |
| 2 | `TRACKER_NOME` | nvarchar(max) | NO |  |  |
| 3 | `TRACKER_ACTIVO` | bit | NO |  |  |

**PK**: `TRACKER_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `TRACKER_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TRACKER_ID` | `TRACKER_NOME` | `TRACKER_ACTIVO` |
|---|---|---|
| 1039338 | Nelo 2 | false |
| 1039492 | Nelo 9 | true |
| 1039775 | NELO 10 | false |

---

### `ARMAZEM` — *25 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `ARM_ID` | int | NO |  | **PK** |
| 2 | `ARM_NOME` | nvarchar(max) | NO |  |  |
| 3 | `ARM_OBS` | nvarchar(max) | YES |  |  |
| 4 | `ARM_DATA_CRIACAO` | smalldatetime | NO |  |  |
| 5 | `ARM_ACTIVO` | bit | NO |  |  |
| 6 | `ARM_TEM_STOCK` | bit | NO |  |  |
| 7 | `ARM_E_ID_RESP` | int | YES |  | FK → `ENTIDADE.E_ID` |
| 8 | `ARM_E_ID_AJUD` | int | YES |  |  |
| 9 | `ARM_PRINTER_IP` | nvarchar(max) | YES |  |  |

**PK**: `ARM_ID`

**FKs declared (out)**:
- `ARM_E_ID_RESP` → `ENTIDADE.E_ID`

**FKs declared (in)** — *1 references*:
- `ORDEMFABRICO.OF_ARM_ID`

**Implicit relations** _(by column naming)_:
- `ARM_ID` → likely `ARMAZEM`

**Sample (TOP 3)** *(showing 8 of 9 cols)*:

| `ARM_ID` | `ARM_NOME` | `ARM_OBS` | `ARM_DATA_CRIACAO` | `ARM_ACTIVO` | `ARM_TEM_STOCK` | `ARM_E_ID_RESP` | `ARM_E_ID_AJUD` |
|---|---|---|---|---|---|---|---|
| 1 | Fábrica 1 (Can) | Fábrica de Canidelo | 2009-04-14 10:10 | true | true | — | — |
| 2 | Camião Nelo | Camião das provas | 2009-04-14 10:11 | true | false | — | — |
| 3 | Fábrica 2 (Most) | teste | 2009-04-14 11:35 | true | false | — | — |

---

### `TRANSP_DESP_TIPO` — *20 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRDESPTP_ID` | int | NO |  | **PK** |
| 2 | `TRDESPTP_NOME` | nvarchar(max) | NO |  |  |
| 3 | `trdesptp_eliminado` | smalldatetime | YES |  |  |

**PK**: `TRDESPTP_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `TRANSP_DESP.TRDESP_TRDESPTP_ID`

**Implicit relations** _(by column naming)_:
- `TRDESPTP_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TRDESPTP_ID` | `TRDESPTP_NOME` | `trdesptp_eliminado` |
|---|---|---|
| 1 | Hotel | — |
| 2 | Voos | — |
| 3 | Alimentação | — |

---

### `TRANSP_DOCS_DEST_TIPO` — *20 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DTD_DEST_ID` | int | NO |  | **PK** FK → `TRANSP_DESTINO.DEST_ID` |
| 2 | `DTD_TRTP_ID` | int | NO |  | **PK** FK → `TRANSP_TIPO.TRTP_ID` |
| 3 | `DTD_DOCS_ID` | int | NO |  | **PK** FK → `TRANSP_DOCS_STD.DOCS_ID` |

**PK**: `DTD_DEST_ID, DTD_TRTP_ID, DTD_DOCS_ID`

**FKs declared (out)**:
- `DTD_DEST_ID` → `TRANSP_DESTINO.DEST_ID`
- `DTD_DOCS_ID` → `TRANSP_DOCS_STD.DOCS_ID`
- `DTD_TRTP_ID` → `TRANSP_TIPO.TRTP_ID`


**Sample (TOP 3)**:

| `DTD_DEST_ID` | `DTD_TRTP_ID` | `DTD_DOCS_ID` |
|---|---|---|
| 7 | 9 | 7 |
| 7 | 9 | 11 |
| 7 | 16 | 7 |

---

### `MOVIMENTO_TIPO` — *15 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TPMOV_ID` | int | NO |  | **PK** |
| 2 | `TPMOV_NOME` | nvarchar(max) | NO |  |  |

**PK**: `TPMOV_ID`

**FKs declared (out)**: _(none)_


**Implicit relations** _(by column naming)_:
- `TPMOV_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TPMOV_ID` | `TPMOV_NOME` |
|---|---|
| 1 | Entrada |
| 2 | Saida |
| 4 | Reserva |

---

### `AgenteEncomenda` — *14 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codEncomenda` | int | NO |  | **PK** |
| 2 | `codAgente` | int | YES |  |  |
| 3 | `codOF` | int | YES |  |  |
| 4 | `data` | decimal | YES |  |  |
| 5 | `modoEnvio` | int | YES |  |  |
| 6 | `estado` | int | YES |  |  |
| 7 | `obs` | varchar(4000) | YES |  |  |
| 8 | `nomeEnvio` | varchar(150) | YES |  |  |
| 9 | `moradaEnvio` | varchar(500) | YES |  |  |
| 10 | `telefoneEnvio` | varchar(50) | YES |  |  |
| 11 | `custoEnvio` | decimal | YES |  |  |

**PK**: `codEncomenda`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `AgenteEncomendaProduto.codEncomenda`

**Sample (TOP 3)** *(showing 8 of 11 cols)*:

| `codEncomenda` | `codAgente` | `codOF` | `data` | `modoEnvio` | `estado` | `obs` | `nomeEnvio` |
|---|---|---|---|---|---|---|---|
| 1 | 21033 | — | 20121121 | 1 | 2 | URGENT!  | — |
| 2 | 21035 | 105928 | 20121127 | 2 | 2 |  |  |
| 3 | 20494 | 1 | 20121129 | 2 | 2 | Avec la prochaine livraison.    il me... |  |

---

### `Encomenda_trk` — *7 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codEncomenda` | int | NO |  | **PK** |
| 2 | `codOperador` | int | YES |  |  |
| 3 | `referencia` | varchar(50) | YES |  |  |
| 4 | `dataPartida` | decimal | YES |  |  |
| 5 | `dataChegada` | decimal | YES |  |  |
| 6 | `dataPrevistaChegada` | decimal | YES |  |  |
| 7 | `horaPrevistaChegada` | decimal | YES |  |  |
| 8 | `codEstado` | int | YES |  |  |
| 9 | `latitude` | decimal | YES |  |  |
| 10 | `longitude` | decimal | YES |  |  |
| 11 | `ultUpdate` | datetime | YES |  |  |
| 12 | `auxOrder` | int | YES |  |  |

**PK**: `codEncomenda`

**FKs declared (out)**: _(none)_


**Sample (TOP 3)** *(showing 8 of 12 cols)*:

| `codEncomenda` | `codOperador` | `referencia` | `dataPartida` | `dataChegada` | `dataPrevistaChegada` | `horaPrevistaChegada` | `codEstado` |
|---|---|---|---|---|---|---|---|
| 1 | 8 | HLXU8009325 | 20170701 | — | — | — | 3 |
| 2 | 2 | MSKU6500992 | 20170701 | — | — | — | 3 |
| 3 | 7 | KKLUOPO153936 | 20170701 | — | 20170712 | 93500 | 3 |

---

### `LISTA_MOVIMENTO` — *5 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `LM_ID` | int | NO |  | **PK** |
| 2 | `LM_L_ID` | int | NO |  | FK → `LISTA.L_ID` |
| 3 | `LM_DATA` | smalldatetime | NO |  |  |
| 4 | `LM_TIPO` | nvarchar(max) | NO |  |  |

**PK**: `LM_ID`

**FKs declared (out)**:
- `LM_L_ID` → `LISTA.L_ID`


**Implicit relations** _(by column naming)_:
- `LM_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `LM_ID` | `LM_L_ID` | `LM_DATA` | `LM_TIPO` |
|---|---|---|---|
| 1 | 4 | 2009-05-01 11:34 | Movimento do Armazem "Fábrica 1" para... |
| 2 | 4 | 2009-05-20 16:37 | Reposição de Stock do armazem "Camião... |
| 4 | 4 | 2009-06-12 14:17 | Reposição de Stock do armazem "Camião... |

---

### `TRANSP_DESTINO` — *4 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `DEST_ID` | int | NO |  | **PK** |
| 2 | `DEST_NOME` | nvarchar(max) | NO |  |  |

**PK**: `DEST_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *2 references*:
- `TRANSP_DOCS_DEST_TIPO.DTD_DEST_ID`
- `TRANSPORTE.TR_DEST_ID`

**Implicit relations** _(by column naming)_:
- `DEST_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `DEST_ID` | `DEST_NOME` |
|---|---|
| 5 | Nacional |
| 6 | U.E. |
| 7 | Outros |

---

### `AgenteEncomendaEstado` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `codEstado` | int | NO |  | **PK** |
| 2 | `Estado` | varchar(50) | YES |  |  |

**PK**: `codEstado`

**FKs declared (out)**: _(none)_


**Sample (TOP 3)**:

| `codEstado` | `Estado` |
|---|---|
| 1 | Saved |
| 2 | Submitted |
| 3 | Sent |

---

### `ENCOMENDA_ESTADO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `EE_ID` | int | NO |  | **PK** |
| 2 | `EE_NOME` | nvarchar(max) | NO |  |  |
| 3 | `EE_SEQUENCIA` | int | NO |  |  |

**PK**: `EE_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `ENCOMENDA.ENC_EE_ID`

**Implicit relations** _(by column naming)_:
- `EE_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `EE_ID` | `EE_NOME` | `EE_SEQUENCIA` |
|---|---|---|
| 1 | Recebida | 1 |
| 2 | Em Curso | 2 |
| 3 | Fechada | 3 |

---

### `TRANSP_DATAS_CLASSIFICACAO` — *3 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `TRDTCL_ID` | int | NO |  | **PK** |
| 2 | `TRDTCL_NOME` | nvarchar(max) | NO |  |  |

**PK**: `TRDTCL_ID`

**FKs declared (out)**: _(none)_

**FKs declared (in)** — *1 references*:
- `TRANSP_DATAS.TRDT_TRDTCL_ID`

**Implicit relations** _(by column naming)_:
- `TRDTCL_ID` → likely _(no obvious target)_

**Sample (TOP 3)**:

| `TRDTCL_ID` | `TRDTCL_NOME` |
|---|---|
| 1 | Culpa Nelo |
| 2 | Culpa Transportador |
| 3 | Culpa Cliente |

---

### `LISTA_TIPO` — *2 rows*

| # | Column | Type | Null | Default | Notes |
|---|---|---|---|---|---|
| 1 | `LTP_ID` | int | NO |  | **PK** FK → `LISTA_TIPO.LTP_ID` |
| 2 | `LTP_DESCR` | nvarchar(max) | NO |  |  |

**PK**: `LTP_ID`

**FKs declared (out)**:
- `LTP_ID` → `LISTA_TIPO.LTP_ID`

**FKs declared (in)** — *2 references*:
- `LISTA.L_LTP_ID`
- `LISTA_TIPO.LTP_ID`

**Sample (TOP 3)**:

| `LTP_ID` | `LTP_DESCR` |
|---|---|
| 1 | Listas de produção |
| 2 | Listas de produtos/opcionais |

---

<a id="recomendacao-de-integracao-com-prodplan-one"></a>
## Recomendação de integração com ProdPlan ONE

Baseado em row counts, FKs declaradas e cobertura semântica:

### Master data — espelhar localmente (read sync)

| Tabela | Linhas | Porquê |
|---|---:|---|
| `PRODUTO` | 14 016 | Catálogo de produtos — root da hierarquia. |
| `PRODUTO_FASE` | 42 811 | Routings: produto × fase. Define operações esperadas. |
| `PRODUTO_COMPONENTE` | 117 900 | BOM — componentes por produto. |
| `FASES_PRODUCAO` | 71 | Master de fases (= work centres do MES). |
| `FP_FP` | 11 | Precedências entre fases (DAG do routing). |
| `ENTIDADE` | 8 936 | Pessoas / clientes / fornecedores / operadores. |
| `MOLDES` | 91 | Master de moldes — recurso crítico (510 esperados). |
| `ARMAZEM` | 25 | Master de armazéns. |
| `ESTACAO` | 5 | Master de estações. |
| `TURNO` | 3 | Calendário de turnos. |

### Transactional — ler via adapter (nunca escrever)

| Tabela | Linhas | Porquê |
|---|---:|---|
| `ORDEMFABRICO` | 441 392 | Ordens de fabrico — fonte de demand para o scheduler. |
| `OF_FP` | 2 627 279 | OF × Fase — estado de execução por operação. |
| `OFFP_PROBLEMA` | 0 | Problemas registados durante execução de fases. |
| `MOVIMENTO` | 12 392 449 | Movimentos de stock — base para WIP / cura. |
| `MOLDES_MOV` | 3 673 | Movimentos de moldes — utilização do recurso. |
| `ENCOMENDA` | 410 | Encomendas de cliente — demand. |
| `PLANEAMENTO_DIARIO` | 64 | Planeamento manual do gestor (baseline). |
| `Z_PrevisaoPlano` | 320 | Previsão de plano gerada por sistema. |

### Reference / lookup — incluir em mirror inicial

- `PRODUTO_TIPO`, `PRODUTO_ESTADO`, `PRODUTO_MODELO`, `PRODUTO_TAMANHO`
- `MOLDES_TIPO`, `MOVIMENTO_TIPO`, `OFFP_GRAVIDADE`
- `ENCOMENDA_ESTADO`, `EstadoOFAgente`, `OF_TIPOUSO`
- `UNIDADE`, `MEDIDAS`, `EQUIPA`

### Skip — não usar no scope ProdPlan

- Laravel infra: `migrations`, `failed_jobs`, `telescope_*`, `personal_access_tokens`, `notifications`, `job_batches`
- Caches: `ShopCache`, `rfid_cache`, `GASTOS_CACHE`
- One-shot exports: `Report_Table_20171114`, `exports`, `imports`, `failed_import_rows`
- Auth legacy: `USERS`, `users_laravel` (usar a auth do ProdPlan)

### Notas

- Sample rows com strings > 40 chars truncadas (`...`). Datas e números raw.
- FKs **declaradas** são as únicas com integridade referencial garantida pela DB.
  As **implícitas** (`_ID`, `_COD`, `_REF`) requerem validação de aplicação.
- Row counts via `sys.partitions` (DMV `sys.dm_db_partition_stats` precisa de `VIEW DATABASE STATE` que `nikufra` não tem). Precisão até ao último checkpoint — não 100% live, mas chega para dimensionar integração.
