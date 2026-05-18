# NELO MAR-KAYAKS — deep-scan completo
_Gerado 2026-05-17 12:45 — read-only, user nikufra (DataReader)._

## 0. Servidor
- Versao: `Microsoft SQL Server 2016 (SP1) (KB3182545) - 13.0.4001.0 (X64) `
- DB: `MAR-KAYAKS` | login: `nikufra` | hora servidor: `2026-05-17 12:45:17.887000`

## 1. Inventario
- **284 tabelas**, **55 views**, **~29,108,165 linhas** (tabelas).

### 1.1 Tabelas (ordenado por nr. de linhas)

| # | schema.tabela | linhas | criada | modificada (schema) |
|---|---|--:|---|---|
| 1 | dbo.MOVIMENTO | 12,402,826 | 2019-06-18 | 2026-05-17 |
| 2 | dbo.IOT_SENSOR_DATA | 3,637,617 | 2025-02-03 | 2026-05-17 |
| 3 | dbo.OF_CHECKLIST | 2,997,803 | 2019-06-18 | 2026-05-17 |
| 4 | dbo.OF_FP | 2,629,039 | 2019-06-18 | 2026-05-17 |
| 5 | dbo.telescope_entries | 2,471,772 | 2023-08-07 | 2026-05-17 |
| 6 | dbo.OFFP_EQ | 1,412,103 | 2019-06-18 | 2026-05-17 |
| 7 | dbo.SensoresTesteSerieValores | 639,548 | 2019-06-18 | 2026-05-17 |
| 8 | dbo.TH | 586,376 | 2024-01-29 | 2026-05-17 |
| 9 | dbo.ORDEMFABRICO | 441,644 | 2019-06-18 | 2026-05-17 |
| 10 | dbo.telescope_entries_tags | 187,831 | 2023-08-07 | 2026-05-17 |
| 11 | dbo.ENT_MOV | 166,327 | 2019-06-18 | 2026-05-17 |
| 12 | dbo.Velocidade | 142,340 | 2021-11-10 | 2026-05-17 |
| 13 | dbo.OF_ATTACH | 130,751 | 2019-06-18 | 2026-05-17 |
| 14 | dbo.PRODUTO_COMPONENTE | 117,952 | 2019-06-18 | 2026-05-17 |
| 15 | dbo.PEDIDOS | 116,010 | 2021-02-01 | 2026-05-17 |
| 16 | dbo.ALARM | 110,264 | 2019-06-18 | 2026-05-17 |
| 17 | dbo.ENTIDADE_PHC_FACT | 100,516 | 2019-11-07 | 2026-05-17 |
| 18 | dbo.TRANSP_OF | 92,902 | 2019-06-18 | 2026-05-17 |
| 19 | dbo.TRANSP_VAL | 76,054 | 2019-06-18 | 2026-05-17 |
| 20 | dbo.OFCH_LOCAL | 58,189 | 2019-06-18 | 2026-05-17 |
| 21 | dbo.TRANSP_DOCS | 46,797 | 2019-06-18 | 2026-05-17 |
| 22 | dbo.PRODUTO_FASE | 42,829 | 2019-06-18 | 2026-05-17 |
| 23 | dbo.TransportePercursoHistorico | 40,484 | 2019-06-18 | 2026-05-17 |
| 24 | dbo.TransporteLocalizacao | 39,122 | 2019-06-18 | 2026-05-17 |
| 25 | dbo.logs_web | 30,105 | 2019-06-18 | 2026-05-17 |
| 26 | dbo.TransportePercursoHistoricoDetalhe | 27,152 | 2019-06-18 | 2026-05-17 |
| 27 | dbo.PRODUTO_OPCOES | 26,292 | 2019-06-18 | 2026-05-17 |
| 28 | dbo.SGIDI_FICHEIRO | 25,869 | 2019-06-18 | 2026-05-17 |
| 29 | dbo.ENT_TP_PROD | 22,832 | 2019-06-18 | 2026-05-17 |
| 30 | dbo.Trackimo_Access | 20,313 | 2019-06-18 | 2026-05-17 |
| 31 | dbo.PRODUTO_CAMADA | 16,229 | 2019-06-18 | 2026-05-17 |
| 32 | dbo.DIAS_TRABALHO | 15,637 | 2019-06-18 | 2026-05-17 |
| 33 | dbo.aux_ValoresProd | 14,077 | 2021-12-07 | 2026-05-17 |
| 34 | dbo.PRODUTO | 14,025 | 2025-04-29 | 2026-05-17 |
| 35 | dbo.ENTIDADE_OBS_ITEM | 13,099 | 2019-11-14 | 2026-05-17 |
| 36 | dbo.CENTRO_RESERVA_CHECKLIST | 12,522 | 2019-06-18 | 2026-05-17 |
| 37 | dbo.TRANSPORTE | 11,364 | 2019-06-18 | 2026-05-17 |
| 38 | dbo.AGENTE_FATURA | 9,709 | 2019-06-18 | 2026-05-17 |
| 39 | dbo.CORREIO_FACT | 9,036 | 2020-10-22 | 2026-05-17 |
| 40 | dbo.ENTIDADE | 8,947 | 2025-03-21 | 2026-05-17 |
| 41 | dbo.auxOrdemFabrico | 7,880 | 2019-06-18 | 2026-05-17 |
| 42 | dbo.PRODUTO_ENTIDADE | 7,691 | 2019-06-18 | 2026-05-17 |
| 43 | dbo.SGIDI_PASTA | 7,495 | 2019-06-18 | 2026-05-17 |
| 44 | dbo.OF_LOTE | 7,083 | 2019-06-18 | 2026-05-17 |
| 45 | dbo.OF_ENTIDADE | 5,644 | 2020-02-27 | 2026-05-17 |
| 46 | dbo.Trackimo_DeviceLocation | 5,173 | 2019-06-18 | 2026-05-17 |
| 47 | dbo.IMPORT | 4,739 | 2019-06-18 | 2026-05-17 |
| 48 | dbo.ENTIDADE_OBS | 4,142 | 2019-06-18 | 2026-05-17 |
| 49 | dbo.CENTRO_MODELOS_QTD | 4,081 | 2019-06-18 | 2026-05-17 |
| 50 | dbo.TRANSP_DESP | 4,021 | 2019-06-18 | 2026-05-17 |
| 51 | dbo.PRODUTO_ATTACH | 3,862 | 2019-06-18 | 2026-05-17 |
| 52 | dbo.COMUNICACAO_FASES_PRODUCAO | 3,849 | 2024-07-18 | 2025-03-21 |
| 53 | dbo.OF_PROPRIETARIO | 3,826 | 2024-06-14 | 2026-05-17 |
| 54 | dbo.Report_Table_20171114 | 3,688 | 2019-06-18 | 2019-06-18 |
| 55 | dbo.MOLDES_MOV | 3,673 | 2019-06-18 | 2026-05-17 |
| 56 | dbo.CENTRO_RESERVA_QUARTOS | 3,550 | 2019-06-18 | 2026-05-17 |
| 57 | dbo.auxAnexos | 3,539 | 2019-06-18 | 2026-05-17 |
| 58 | dbo.PORTAO | 3,455 | 2021-01-11 | 2026-05-17 |
| 59 | dbo.REP_OF_FP | 3,416 | 2023-04-14 | 2026-05-17 |
| 60 | dbo.OF_OF_TIPOUSO | 3,196 | 2019-06-18 | 2026-05-17 |
| 61 | dbo.CENTRO_RESERVA_OFS | 3,172 | 2019-06-18 | 2026-05-17 |
| 62 | dbo.TRANSP_DATAS | 3,017 | 2019-06-18 | 2026-05-17 |
| 63 | dbo.PLANO | 2,760 | 2019-06-18 | 2026-05-17 |
| 64 | dbo.BOATCHOOSER_ANSWER_PRODUTO | 2,499 | 2024-01-23 | 2026-05-17 |
| 65 | dbo.CENTRO_RESERVA_TRANSFER | 2,386 | 2019-06-18 | 2026-05-17 |
| 66 | dbo.AGENTE_FATURACAO | 2,236 | 2019-06-18 | 2026-05-17 |
| 67 | dbo.LISTA_PRODUTO | 2,134 | 2019-06-18 | 2026-05-17 |
| 68 | dbo.REPARACOES_PROVAS | 2,028 | 2023-04-27 | 2026-05-17 |
| 69 | dbo.TRANSP_ENTIDADE | 2,003 | 2019-06-18 | 2026-05-17 |
| 70 | dbo.CENTRO_RESERVA | 1,694 | 2019-06-18 | 2026-05-17 |
| 71 | dbo.PROVAS_OF | 1,579 | 2024-07-18 | 2026-05-17 |
| 72 | dbo.ENTIDADE_FASE | 1,270 | 2019-06-18 | 2026-05-17 |
| 73 | dbo.AtletaProva | 1,208 | 2021-10-25 | 2026-05-17 |
| 74 | dbo.IDEIA_EVOL | 1,064 | 2019-06-18 | 2026-05-17 |
| 75 | dbo.FATURA | 1,013 | 2025-10-15 | 2026-05-17 |
| 76 | dbo.PRODUTO_LISTA_ITEMS | 960 | 2019-06-18 | 2026-05-17 |
| 77 | dbo.ENTIDADE_MORADA | 952 | 2019-06-18 | 2026-05-17 |
| 78 | dbo.ENTIDADE_PONTOS | 866 | 2019-06-18 | 2026-05-17 |
| 79 | dbo.TransportePercurso | 847 | 2019-06-18 | 2026-05-17 |
| 80 | dbo.AGENTE_FATURACAO_UPDATE | 841 | 2019-06-18 | 2026-05-17 |
| 81 | dbo.PROVAS_BOOKING | 800 | 2025-02-20 | 2026-05-17 |
| 82 | dbo.ENTIDADE_PHC | 751 | 2019-06-18 | 2026-05-17 |
| 83 | dbo.SensoresTesteSerie | 736 | 2019-06-18 | 2026-05-17 |
| 84 | dbo.GASTOS_CACHE | 593 | 2019-06-18 | 2026-05-17 |
| 85 | dbo.TransportePorto | 570 | 2019-06-18 | 2026-05-17 |
| 86 | dbo.VendaLojaProduto | 511 | 2019-06-18 | 2026-05-17 |
| 87 | dbo.CORREIO_TARIFAS | 480 | 2023-11-29 | 2026-05-17 |
| 88 | dbo.PRODUTO_TIPO | 422 | 2019-06-18 | 2026-05-17 |
| 89 | dbo.IDEIA_TAREFA | 412 | 2019-06-18 | 2026-05-17 |
| 90 | dbo.ENCOMENDA | 410 | 2019-06-18 | 2026-05-17 |
| 91 | dbo.ENTIDADE_TREINOS | 401 | 2022-10-07 | 2026-05-17 |
| 92 | dbo.IDEIA | 325 | 2025-05-30 | 2026-05-17 |
| 93 | dbo.PRODUTO_MODELO | 319 | 2019-06-18 | 2026-05-17 |
| 94 | dbo.PROVAS_FICHEIROS | 307 | 2025-06-30 | 2026-05-17 |
| 95 | dbo.Z_PrevisaoPlano | 303 | 2019-06-18 | 2019-06-18 |
| 96 | dbo.DRAG_VELOCIDADE | 276 | 2023-06-02 | 2026-05-17 |
| 97 | dbo.KPI_OBJECTIVO | 267 | 2025-02-11 | 2026-05-17 |
| 98 | dbo.PAISES_SITE | 256 | 2019-06-18 | 2026-05-17 |
| 99 | dbo.country-codes2 | 250 | 2019-06-18 | 2020-08-28 |
| 100 | dbo.CENTRO_ESTAGIO_DESPESAS | 249 | 2019-06-18 | 2026-05-17 |
| 101 | dbo.TransporteNavio | 247 | 2019-06-18 | 2026-05-17 |
| 102 | dbo.DOC_PRODUTO_TIPO | 233 | 2019-06-18 | 2026-05-17 |
| 103 | dbo.VendaLoja | 223 | 2019-06-18 | 2026-05-17 |
| 104 | dbo.DOC | 214 | 2019-06-18 | 2026-05-17 |
| 105 | dbo.CORREIO_ZONA_PAIS | 212 | 2023-11-28 | 2026-05-17 |
| 106 | dbo.IDEIA_COLAB | 209 | 2019-06-18 | 2026-05-17 |
| 107 | dbo.PAISES | 202 | 2019-06-18 | 2026-05-17 |
| 108 | dbo.MEDIDAS | 165 | 2019-06-18 | 2026-05-17 |
| 109 | dbo.COMUNICACAO_PRODUTO_TIPO | 164 | 2023-11-09 | 2023-11-22 |
| 110 | dbo.LISTA | 163 | 2019-06-18 | 2026-05-17 |
| 111 | dbo.SensoresTeste | 163 | 2019-06-18 | 2026-05-17 |
| 112 | dbo.COMUNICACAO_ANEXO | 150 | 2023-11-09 | 2026-05-17 |
| 113 | dbo.OFFP_GRAVIDADES | 148 | 2024-12-11 | 2026-05-17 |
| 114 | dbo.ArtigosGrupos | 141 | 2019-06-18 | 2026-05-17 |
| 115 | dbo.TransporteLocalPesquisado | 136 | 2019-06-18 | 2026-05-17 |
| 116 | dbo.ShopCache | 131 | 2019-06-18 | 2026-05-17 |
| 117 | dbo.Prova | 125 | 2021-10-25 | 2026-05-17 |
| 118 | dbo.Meeting | 123 | 2021-11-01 | 2026-05-17 |
| 119 | dbo.KPI | 115 | 2025-02-11 | 2026-05-17 |
| 120 | dbo.ATRIBUTO | 111 | 2019-06-18 | 2026-05-17 |
| 121 | dbo.OF_RENTAL_PROVAS | 110 | 2022-03-21 | 2026-05-17 |
| 122 | dbo.aux_ValoresProducao | 109 | 2021-12-07 | 2026-05-17 |
| 123 | dbo.PROBS | 104 | 2019-06-18 | 2026-05-17 |
| 124 | dbo.TRANSP_DOCS_STD | 101 | 2019-06-18 | 2026-05-17 |
| 125 | dbo.COMUNICACAO | 100 | 2023-11-22 | 2026-05-17 |
| 126 | dbo.MOLDES | 91 | 2019-06-18 | 2026-05-17 |
| 127 | dbo.SensoresTesteVideo | 91 | 2019-06-18 | 2026-05-17 |
| 128 | dbo.ProdutoTipoAcessorio | 88 | 2019-06-18 | 2026-05-17 |
| 129 | dbo.LACAGEM | 86 | 2019-06-18 | 2026-05-17 |
| 130 | dbo.LISTA_COORDENADAS | 84 | 2020-07-21 | 2026-05-17 |
| 131 | dbo.ENTIDADE_EQUIPA | 82 | 2019-06-18 | 2026-05-17 |
| 132 | dbo.PROC_AREA_ENT | 80 | 2019-06-18 | 2026-05-17 |
| 133 | dbo.IDEIA_DOC | 78 | 2019-06-18 | 2026-05-17 |
| 134 | dbo.PROC_AREA | 74 | 2019-06-18 | 2026-05-17 |
| 135 | dbo.SensoresTesteSeriePosicoes | 74 | 2019-06-18 | 2026-05-17 |
| 136 | dbo.PROC_AREA_FONTE | 72 | 2019-06-18 | 2026-05-17 |
| 137 | dbo.IDEIA_CLASSIFICACAO | 72 | 2019-06-18 | 2026-05-17 |
| 138 | dbo.FASES_PRODUCAO | 71 | 2019-06-18 | 2026-05-17 |
| 139 | dbo.TransporteDestino | 65 | 2019-06-18 | 2026-05-17 |
| 140 | dbo.PLANEAMENTO_DIARIO | 64 | 2019-06-18 | 2026-05-17 |
| 141 | dbo.AgenteEncomendaProduto | 59 | 2019-06-18 | 2026-05-17 |
| 142 | dbo.TRANSP_TIPO | 58 | 2019-06-18 | 2026-05-17 |
| 143 | dbo.SensoresTesteAtleta | 54 | 2019-06-18 | 2026-05-17 |
| 144 | dbo.INTERVALO | 52 | 2019-06-18 | 2026-05-17 |
| 145 | dbo.ENTIDADE_OBS_TIPO | 47 | 2019-06-18 | 2026-05-17 |
| 146 | dbo.BOATCHOOSER_ANSWER | 45 | 2024-01-23 | 2026-05-17 |
| 147 | dbo.AUDIT | 38 | 2019-06-18 | 2026-05-17 |
| 148 | dbo.MOVIMENTO_ATTACH | 37 | 2019-06-18 | 2026-05-17 |
| 149 | dbo.ENTIDADE_TIPO | 36 | 2019-06-18 | 2026-05-17 |
| 150 | dbo.TRANSP_TRACKER | 34 | 2019-06-18 | 2026-05-17 |
| 151 | dbo.IDEIA_ESTADO | 33 | 2019-06-18 | 2026-05-17 |
| 152 | dbo.IOT_SENSOR | 32 | 2024-07-16 | 2026-05-17 |
| 153 | dbo.DOURO_AULA_MONITOR | 32 | 2019-06-18 | 2026-05-17 |
| 154 | dbo.Trackimo_Device | 30 | 2019-06-18 | 2026-05-17 |
| 155 | dbo.PRODUTO_FASE_LINK | 29 | 2019-06-18 | 2026-05-17 |
| 156 | dbo.FERIAS | 29 | 2019-06-18 | 2019-06-18 |
| 157 | dbo.exports | 27 | 2025-04-03 | 2026-05-17 |
| 158 | dbo.job_batches | 27 | 2025-04-03 | 2026-05-17 |
| 159 | dbo.DOC_TITLE | 27 | 2019-06-18 | 2026-05-17 |
| 160 | dbo.PRODUTO_LISTA | 26 | 2019-06-18 | 2026-05-17 |
| 161 | dbo.ARMAZEM | 25 | 2019-06-18 | 2026-05-17 |
| 162 | dbo.notifications | 25 | 2025-04-03 | 2026-05-17 |
| 163 | dbo.migrations | 24 | 2023-08-07 | 2026-05-17 |
| 164 | dbo.OF_VENDA | 22 | 2021-11-09 | 2026-05-17 |
| 165 | dbo.UNIDADE | 22 | 2019-06-18 | 2026-05-17 |
| 166 | dbo.PROVAS | 21 | 2025-02-20 | 2026-05-17 |
| 167 | dbo.DOC_DESCRIPTION | 21 | 2019-06-18 | 2026-05-17 |
| 168 | dbo.DOURO_AULA | 20 | 2022-10-11 | 2026-05-17 |
| 169 | dbo.TRANSP_DESP_TIPO | 20 | 2019-06-18 | 2026-05-17 |
| 170 | dbo.TRANSP_DOCS_DEST_TIPO | 20 | 2019-06-18 | 2026-05-17 |
| 171 | dbo.SGIDI_FX_CLASSIFIC | 20 | 2019-06-18 | 2026-05-17 |
| 172 | dbo.RH_DOC | 19 | 2019-06-18 | 2026-05-17 |
| 173 | dbo.PRODUTO_TAMANHO | 18 | 2019-06-18 | 2026-05-17 |
| 174 | dbo.DRAG_BARCO | 18 | 2023-05-31 | 2026-05-17 |
| 175 | dbo.EQUIPA | 17 | 2019-06-18 | 2026-05-17 |
| 176 | dbo.ATRIB_ATRIB | 16 | 2019-06-18 | 2026-05-17 |
| 177 | dbo.ATTACH_TIPO | 15 | 2019-06-18 | 2026-05-17 |
| 178 | dbo.ENT_MOV_TIPO | 15 | 2019-06-18 | 2026-05-17 |
| 179 | dbo.MOVIMENTO_TIPO | 15 | 2019-06-18 | 2026-05-17 |
| 180 | dbo.PRODUTO_COEFICIENTE | 15 | 2019-06-18 | 2026-05-17 |
| 181 | dbo.TransporteOperador | 15 | 2019-06-18 | 2026-05-17 |
| 182 | dbo.PONTOS | 14 | 2019-06-18 | 2026-05-17 |
| 183 | dbo.MOLDES_TIPO | 14 | 2019-06-18 | 2026-05-17 |
| 184 | dbo.IOT_SENSOR_ALARM | 14 | 2025-03-25 | 2026-05-17 |
| 185 | dbo.AgenteEncomenda | 14 | 2019-06-18 | 2026-05-17 |
| 186 | dbo.CENTRO_ESTAGIO | 14 | 2019-06-18 | 2026-05-17 |
| 187 | dbo.BOATCHOOSER_QUESTION | 14 | 2024-01-19 | 2026-05-17 |
| 188 | dbo.DIAS_FERIADOS_FERIAS | 14 | 2019-06-18 | 2026-05-17 |
| 189 | dbo.sysdiagrams | 13 | 2019-06-18 | 2019-06-18 |
| 190 | dbo.PRODUTO_CAMADA_TIPO | 12 | 2019-06-18 | 2026-05-17 |
| 191 | dbo.PROC_CLASSIFIC | 12 | 2019-06-18 | 2026-05-17 |
| 192 | dbo.CORREIO_ZONAS | 12 | 2023-11-28 | 2026-05-17 |
| 193 | dbo.CENTRO_RESERVA_CHEKLIST_ITEMS | 12 | 2019-06-18 | 2026-05-17 |
| 194 | dbo.FP_FP | 11 | 2019-06-18 | 2026-05-17 |
| 195 | dbo.IDEIA_ENTIDADE | 10 | 2019-06-18 | 2026-05-17 |
| 196 | dbo.AVALIACOES_ITEMS | 10 | 2019-11-05 | 2026-05-17 |
| 197 | dbo.PRODUTO_CONTABILIDADE_TIPO | 10 | 2019-06-18 | 2026-05-17 |
| 198 | dbo.USERS | 10 | 2019-06-18 | 2026-05-17 |
| 199 | dbo.noticias_agentes | 9 | 2019-06-18 | 2026-05-17 |
| 200 | dbo.AUDIT_TIPO | 8 | 2019-06-18 | 2026-05-17 |
| 201 | dbo.Encomenda_trk | 7 | 2019-06-18 | 2026-05-17 |
| 202 | dbo.IOT_SENSOR_TIPO | 7 | 2024-07-15 | 2026-05-17 |
| 203 | dbo.VALOR | 7 | 2019-06-18 | 2026-05-17 |
| 204 | dbo.SGIDI_TIPO | 7 | 2019-06-18 | 2026-05-17 |
| 205 | dbo.PRODUTO_ESTADO | 7 | 2019-06-18 | 2026-05-17 |
| 206 | dbo.PRODUTO_NUMERO_POCOS | 7 | 2019-06-18 | 2026-05-17 |
| 207 | dbo.PROBS_LOCAL | 7 | 2019-06-18 | 2026-05-17 |
| 208 | dbo.PROBS_CLASSIFICACAO | 6 | 2019-06-18 | 2026-05-17 |
| 209 | dbo.ORCAMENTO_PRODUTO | 6 | 2025-07-08 | 2026-05-17 |
| 210 | dbo.PROC_FONTE | 6 | 2019-06-18 | 2026-05-17 |
| 211 | dbo.SGIDI | 6 | 2019-06-18 | 2026-05-17 |
| 212 | dbo.RH_TIPO_DOC | 6 | 2019-06-18 | 2026-05-17 |
| 213 | dbo.IDEIA_CLASSIFIC_CHECK | 6 | 2023-02-08 | 2023-02-08 |
| 214 | dbo.ALARM_TIPO | 6 | 2019-06-18 | 2026-05-17 |
| 215 | dbo.ESTACAO | 5 | 2019-06-18 | 2026-05-17 |
| 216 | dbo.LISTA_MOVIMENTO | 5 | 2019-06-18 | 2026-05-17 |
| 217 | dbo.TH_SONDA | 5 | 2020-05-06 | 2026-05-17 |
| 218 | dbo.OFFP_GRAVIDADE | 5 | 2024-12-11 | 2026-05-17 |
| 219 | dbo.PROC_ARQUIVO | 4 | 2019-06-18 | 2026-05-17 |
| 220 | dbo.PROC_TIPO | 4 | 2019-06-18 | 2026-05-17 |
| 221 | dbo.SensoresPosicao | 4 | 2019-06-18 | 2026-05-17 |
| 222 | dbo.TRANSP_DESTINO | 4 | 2019-06-18 | 2026-05-17 |
| 223 | dbo.MeetingEstado | 4 | 2019-06-18 | 2026-05-17 |
| 224 | dbo.EstadoOFAgente | 4 | 2019-06-18 | 2026-05-17 |
| 225 | dbo.ACELERADOR_VARIAVEIS | 4 | 2019-06-18 | 2019-06-18 |
| 226 | dbo.BOATCHOOSER_GROUPS | 4 | 2024-02-02 | 2026-05-17 |
| 227 | dbo.DOURO_AULA_ENTIDADE | 4 | 2022-10-28 | 2025-03-21 |
| 228 | dbo.DOC_TYPE | 4 | 2019-06-18 | 2026-05-17 |
| 229 | dbo.CENTRO_RESERVA_ESTADO | 4 | 2019-06-18 | 2026-05-17 |
| 230 | dbo.CENTRO_RESERVA_TRANSFER_RESPONS | 4 | 2019-06-18 | 2026-05-17 |
| 231 | dbo.COMPONENTE_TIPO | 4 | 2019-06-18 | 2026-05-17 |
| 232 | dbo.ENCOMENDA_ESTADO | 3 | 2019-06-18 | 2026-05-17 |
| 233 | dbo.BOATCHOOSER_QUIZ | 3 | 2024-07-11 | 2026-05-17 |
| 234 | dbo.AgenteEncomendaEstado | 3 | 2019-06-18 | 2026-05-17 |
| 235 | dbo.ENT_TIPO_VINCULO | 3 | 2019-06-18 | 2026-05-17 |
| 236 | dbo.ENT_ENT_PEDIDO_PROVISORIO | 3 | 2020-11-20 | 2026-05-17 |
| 237 | dbo.ENTIDADE_MORADA_TIPO | 3 | 2019-06-18 | 2026-05-17 |
| 238 | dbo.IDEIA_REUNIAO | 3 | 2019-06-18 | 2026-05-17 |
| 239 | dbo.TRANSP_DATAS_CLASSIFICACAO | 3 | 2019-06-18 | 2026-05-17 |
| 240 | dbo.TURNO | 3 | 2019-06-18 | 2026-05-17 |
| 241 | dbo.PROVAS_BOOKING_ESTADO | 3 | 2024-10-21 | 2026-05-17 |
| 242 | dbo.PROB_CAUSA_SOL_TIPO | 3 | 2019-06-18 | 2026-05-17 |
| 243 | dbo.OF_TIPOUSO | 3 | 2019-06-18 | 2026-05-17 |
| 244 | dbo.OFFP_CL | 3 | 2019-06-18 | 2026-05-17 |
| 245 | dbo.ORCAMENTO | 2 | 2025-07-10 | 2026-05-17 |
| 246 | dbo.PROB_CAUSA_SOL | 2 | 2019-06-18 | 2026-05-17 |
| 247 | dbo.PROC_TIPO_ENT | 2 | 2019-06-18 | 2026-05-17 |
| 248 | dbo.PRODUTO_ATTACH_TIPO | 2 | 2019-06-18 | 2026-05-17 |
| 249 | dbo.VALOR_TIPO | 2 | 2019-06-18 | 2026-05-17 |
| 250 | dbo.VARIAVEIS | 2 | 2020-06-29 | 2026-05-17 |
| 251 | dbo.users_laravel | 2 | 2023-11-27 | 2026-05-17 |
| 252 | dbo.TransporteTmp_Percurso | 2 | 2021-04-26 | 2026-05-17 |
| 253 | dbo.SensoresLogin | 2 | 2019-06-18 | 2026-05-17 |
| 254 | dbo.SensoresLoginSessao | 2 | 2019-06-18 | 2026-05-17 |
| 255 | dbo.rfid_cache | 2 | 2025-02-05 | 2026-05-17 |
| 256 | dbo.IDEIA_TPCOL | 2 | 2019-06-18 | 2026-05-17 |
| 257 | dbo.LISTA_TIPO | 2 | 2019-06-18 | 2026-05-17 |
| 258 | dbo.MAILS | 2 | 2019-06-18 | 2026-05-17 |
| 259 | dbo.ACTUALIZACOES | 2 | 2019-06-18 | 2026-05-17 |
| 260 | dbo.Competicao | 1 | 2021-10-25 | 2026-05-17 |
| 261 | dbo.ENTIDADE_DADOS | 1 | 2019-06-18 | 2026-05-17 |
| 262 | dbo.RH_FORMACAO | 1 | 2019-06-18 | 2026-05-17 |
| 263 | dbo.testes | 1 | 2019-06-18 | 2026-05-17 |
| 264 | dbo.TH_SCHED | 1 | 2021-01-19 | 2026-05-17 |
| 265 | dbo.PublicidadeAgentes | 1 | 2019-06-18 | 2026-05-17 |
| 266 | dbo.PROVAS_PROVAS_BOOKING_ESTADO | 0 | 2024-10-21 | 2025-02-20 |
| 267 | dbo.PRODUTO_PROB_CAUSA_SOL | 0 | 2019-06-18 | 2026-05-17 |
| 268 | dbo.personal_access_tokens | 0 | 2023-08-07 | 2026-05-17 |
| 269 | dbo.OFFP_LINK | 0 | 2019-06-18 | 2019-06-18 |
| 270 | dbo.OFFP_PROBLEMA | 0 | 2019-06-18 | 2026-05-17 |
| 271 | dbo.telescope_monitoring | 0 | 2023-08-07 | 2023-08-07 |
| 272 | dbo.RH_PROBLEMA | 0 | 2019-06-18 | 2026-05-17 |
| 273 | dbo.ZONA_GEOGRAFICA | 0 | 2019-06-18 | 2026-05-17 |
| 274 | dbo.TRANSPORTE_VERIFICACAO | 0 | 2019-06-18 | 2026-05-17 |
| 275 | dbo.TransporteSP | 0 | 2019-06-18 | 2026-05-17 |
| 276 | dbo.ENTIDADE_PROVAS | 0 | 2026-01-30 | 2026-01-30 |
| 277 | dbo.ENTIDADE_SUB | 0 | 2019-06-18 | 2026-05-17 |
| 278 | dbo.failed_import_rows | 0 | 2025-04-03 | 2026-05-17 |
| 279 | dbo.failed_jobs | 0 | 2023-08-07 | 2026-05-17 |
| 280 | dbo.imports | 0 | 2025-04-03 | 2026-05-17 |
| 281 | dbo.ENT_CONFIG | 0 | 2019-06-18 | 2026-05-17 |
| 282 | dbo.ALARM_TIPO_ENTIDADE | 0 | 2019-06-18 | 2026-05-17 |
| 283 | dbo.AUDIT_ENT | 0 | 2019-06-18 | 2025-03-21 |
| 284 | dbo.AuxEstado | 0 | 2019-06-18 | 2026-05-17 |

### 1.2 Views

| # | schema.view | linhas |
|---|---|--:|
| 1 | dbo.ACABADORES | 166
| 2 | dbo.CONSTRUCAO_DETALHE_IDS | 1,019
| 3 | dbo.CONSTRUCAO_DETALHE_NUMP | 7
| 4 | dbo.CONSTRUCAO_DETALHE_TIPO_ASS | 16
| 5 | dbo.CONSTRUCAO_FAMILIA | 1,019
| 6 | dbo.Dealers_MailChimp | 46
| 7 | dbo.ENC_ENTIDADES | 1,348
| 8 | dbo.ENC_ESTADOS | 3
| 9 | dbo.ENC_IDS | 410
| 10 | dbo.FORNECEDOR_IDS | 803
| 11 | dbo.Funcionarios_vencimento_medio | 32
| 12 | dbo.FuncionariosActivos | 158
| 13 | dbo.MODELOS_CL_CONST_MOD_TAM_NP | 1,422
| 14 | dbo.MODELOS_IDS | 1,807
| 15 | dbo.MOLDES_CONST_MOD_TAM_NP | 1,416
| 16 | dbo.Moldes_movimentacao | 28
| 17 | dbo.OF_CLASSES_KAYAK | 56
| 18 | dbo.OF_CLASSES_MOLDES_MATRIZES | 3
| 19 | dbo.OF_EMBALAGENS | 45
| 20 | dbo.OF_ENCOMENDAS | 411
| 21 | dbo.OF_ENTIDADES | 8,762
| 22 | dbo.OF_ESTADOS | 72
| 23 | dbo.of_Fases_ord | 2,527,738
| 24 | dbo.OF_IDS | 441,644
| 25 | dbo.OF_IDS_MLD | 1,506
| 26 | dbo.OF_LINHA_PROD | 441,742
| 27 | dbo.OF_MLD_EMPREGADOS | 159
| 28 | dbo.OF_OFTIPOUSO | 4
| 29 | dbo.OF_PRODUTOS | ERRO: ('21000', '[21000] [Microsoft][ODBC SQL Server Driver][SQL S |
| 30 | dbo.OF_PRODUTOS_MLD | 2,111
| 31 | dbo.OF_PRODUTOS_V2 | 5,512
| 32 | dbo.of_Retornos_Estacionados | 8
| 33 | dbo.OFCOMP_CLASSES | 211
| 34 | dbo.OFCOMP_PRODUTOS | 7,444
| 35 | dbo.PLANO_LAMINAGEM_LISTA_TURNOS | 4
| 36 | dbo.produto_stocks_por_armazem | 8,045
| 37 | dbo.RESINA_OFS | 1
| 38 | dbo.RetornosFuncionario | 88,604
| 39 | dbo.shop_order_item | ERRO: ('42000', "[42000] [Microsoft][ODBC SQL Server Driver][SQL S |
| 40 | dbo.TRANSP_OFS | 5
| 41 | dbo.TRANSP_SEMANA | 8
| 42 | dbo.vAgente_Facturacao_Epoca_Actual | 33
| 43 | dbo.vAgente_Faturacao | 2,029
| 44 | dbo.vCores | 69
| 45 | dbo.vCoresAutocolante | 18
| 46 | dbo.vModelosSite | 5
| 47 | dbo.vMovsPowerHouseNotShop | 61
| 48 | dbo.vOF_Transporte | 441,644
| 49 | dbo.vPecasEmFases | 123
| 50 | dbo.vPecasLaminadas | 12,024
| 51 | dbo.vProdutosEN | 14,025
| 52 | dbo.vPSD | 766
| 53 | dbo.vSaldoCliente | 284
| 54 | dbo.vSubEntidades | 0
| 55 | dbo.vTrackingTransporte | 1,654

## 2. Colunas (todas as tabelas e views)

### dbo.ACABADORES  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |

### dbo.ACELERADOR_VARIAVEIS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EQUIPAS | float |  | N | NULL |
| DIAS | float |  | N | NULL |
| BARCOS | float |  | N | NULL |
| TIPO | nvarchar | 50 | N | NULL |

### dbo.ACTUALIZACOES  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ACT_ID | int |  | N | NULL |
| ACT_DATA | smalldatetime |  | N | NULL |
| ACT_TIPO | nvarchar | -1 | N | NULL |
| ACT_ID_PROD | int |  | N | NULL |
| ACT_ID_ANT | int |  | N | NULL |
| ACT_ID_NOVO | int |  | N | NULL |
| ACT_COMPLETO | bigint |  | N | NULL |
| ACT_TIPO_COMP | int |  | N | NULL |
| ACT_TP_ID | int |  | Y | NULL |
| ACT_FP_ID | int |  | Y | NULL |
| ACT_QTD | float |  | Y | NULL |

### dbo.AGENTE_FATURA  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AFT_E_ID | int |  | N | NULL |
| AFT_F_NO | numeric |  | N | NULL |
| AFT_CONTABILIZAR | bit |  | N | NULL |

### dbo.AGENTE_FATURACAO  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AF_ID | int |  | N | NULL |
| AF_E_ID | int |  | N | NULL |
| AF_ANO | int |  | N | NULL |
| AF_TRIMESTRE | int |  | N | NULL |
| AF_VALOR | decimal |  | Y | NULL |
| AF_DESCONTAR | decimal |  | N | NULL |
| AF_OBS | varchar | 4000 | Y | NULL |

### dbo.AGENTE_FATURACAO_UPDATE  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AFU_ID | int |  | N | NULL |
| AFU_DATA | datetime |  | N | NULL |

### dbo.ALARM  (12 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ALARM_ID | int |  | N | NULL |
| ALARM_DESCRICAO | nvarchar | -1 | Y | NULL |
| ALARM_DATA | smalldatetime |  | N | NULL |
| ALARM_DISPENSADO | bit |  | N | NULL |
| ALARM_OF_ID | int |  | Y | NULL |
| ALARM_P_ID | int |  | Y | NULL |
| ALARM_E_ID | int |  | Y | NULL |
| ALARM_TALARM_ID | int |  | Y | NULL |
| ALARM_FACT | int |  | Y | NULL |
| ALARM_REVISTO | smalldatetime |  | Y | NULL |
| ALARM_E_ID_REVISOR | int |  | Y | NULL |
| ALARM_REVISOR_OBS | nvarchar | -1 | Y | NULL |

### dbo.ALARM_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TALARM_ID | int |  | N | NULL |
| TALARM_NOME | nvarchar | 50 | N | NULL |

### dbo.ALARM_TIPO_ENTIDADE  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ATE_TALARM_ID | int |  | N | NULL |
| ATE_E_ID | int |  | N | NULL |

### dbo.ARMAZEM  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ARM_ID | int |  | N | NULL |
| ARM_NOME | nvarchar | -1 | N | NULL |
| ARM_OBS | nvarchar | -1 | Y | NULL |
| ARM_DATA_CRIACAO | smalldatetime |  | N | NULL |
| ARM_ACTIVO | bit |  | N | NULL |
| ARM_TEM_STOCK | bit |  | N | NULL |
| ARM_E_ID_RESP | int |  | Y | NULL |
| ARM_E_ID_AJUD | int |  | Y | NULL |
| ARM_PRINTER_IP | nvarchar | -1 | Y | NULL |

### dbo.ATRIBUTO  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ATRIB_ID | int |  | N | NULL |
| ATRIB_NOME_PT | nvarchar | -1 | N | NULL |
| ATRIB_NOME_EN | nvarchar | -1 | N | NULL |
| ATRIB_DESCR_PT | nvarchar | -1 | Y | NULL |
| ATRIB_DESCR_EN | nvarchar | -1 | Y | NULL |
| ATRIB_FAMILIA_PT | nvarchar | -1 | Y | NULL |
| ATRIB_FAMILIA_EN | nvarchar | -1 | Y | NULL |
| ATRIB_ABREV_PT | nvarchar | -1 | Y | NULL |
| ATRIB_ABREV_EN | nvarchar | -1 | Y | NULL |
| ATRIB_ORDEM | float |  | N | NULL |

### dbo.ATRIB_ATRIB  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AA_ID | int |  | N | NULL |
| AA_ATRIB_ID | int |  | N | NULL |
| AA_ATRIB_ATRIB_ID | int |  | N | NULL |
| AA_OBRIGATORIO | bit |  | N | NULL |
| AA_STEP | float |  | N | NULL |
| AA_MAX | float |  | N | NULL |
| AA_MIN | float |  | N | NULL |

### dbo.ATTACH_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_ATCH_ID | int |  | N | NULL |
| TP_ATCH_NOME | varchar | 150 | N | NULL |

### dbo.AUDIT  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AUD_ID | int |  | N | NULL |
| AUD_DESC | nvarchar | -1 | Y | NULL |
| AUD_CAUSA | nvarchar | -1 | Y | NULL |
| AUD_PROP | nvarchar | -1 | Y | NULL |
| AUD_DATACONC | smalldatetime |  | Y | NULL |
| AUD_DATACRIAC | smalldatetime |  | Y | NULL |
| AUD_DATACONCREAL | smalldatetime |  | Y | NULL |
| AUD_RESULT | nvarchar | -1 | Y | NULL |
| AUD_OBS | nvarchar | -1 | Y | NULL |
| AUD_AUDT_ID | int |  | Y | NULL |
| AUD_E_ID | int |  | Y | NULL |
| AUD_AUD_ID | int |  | Y | NULL |
| AUD_PONTOSIT | nvarchar | -1 | Y | NULL |
| AUD_RESPONSAVEIS | nvarchar | -1 | Y | NULL |
| AUD_ELIMINADO | bit |  | N | NULL |

### dbo.AUDIT_ENT  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AUDE_E_ID | int |  | Y | NULL |
| AUDE_AUD_ID | int |  | Y | NULL |

### dbo.AUDIT_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AUDT_ID | int |  | N | NULL |
| AUDT_NOME | nvarchar | -1 | N | NULL |
| AUDT_AUDT_ID | int |  | Y | NULL |

### dbo.AVALIACOES_ITEMS  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AITEM_ID | int |  | N | NULL |
| AITEM_DESCR | nvarchar | -1 | N | NULL |
| AITEM_EOBSTP_ID | int |  | N | NULL |
| AITEM_ORDEM | int |  | N | NULL |
| AITEM_DESATIVADO | date |  | Y | NULL |
| AITEM_OBS | nvarchar | -1 | Y | NULL |

### dbo.AgenteEncomenda  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomenda | int |  | N | NULL |
| codAgente | int |  | Y | NULL |
| codOF | int |  | Y | NULL |
| data | decimal |  | Y | NULL |
| modoEnvio | int |  | Y | NULL |
| estado | int |  | Y | NULL |
| obs | varchar | 4000 | Y | NULL |
| nomeEnvio | varchar | 150 | Y | NULL |
| moradaEnvio | varchar | 500 | Y | NULL |
| telefoneEnvio | varchar | 50 | Y | NULL |
| custoEnvio | decimal |  | Y | NULL |

### dbo.AgenteEncomendaEstado  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEstado | int |  | N | NULL |
| Estado | varchar | 50 | Y | NULL |

### dbo.AgenteEncomendaProduto  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomenda | int |  | N | NULL |
| codProduto | int |  | N | NULL |
| qtd | int |  | Y | NULL |
| preco | decimal |  | Y | NULL |
| auxTipo | int |  | Y | NULL |
| auxUnitario | decimal |  | Y | NULL |

### dbo.ArtigosGrupos  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id_orig | int |  | N | NULL |
| id_virtual | int |  | N | NULL |
| nome | varchar | 50 | Y | NULL |

### dbo.AtletaProva  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDAtletaProva | int |  | N | NULL |
| AtletaID | int |  | N | NULL |
| ProvaID | int |  | N | NULL |
| Pista | varchar | 5 | Y | NULL |

### dbo.AuxEstado  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEstado | int |  | N | NULL |
| estado | varchar | 50 | Y | NULL |

### dbo.BOATCHOOSER_ANSWER  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BCA_ID | int |  | N | NULL |
| BCA_QUESTION_ID | int |  | Y | NULL |
| BCA_ANSWER | nvarchar | 250 | Y | NULL |
| BCA_SLUG | nvarchar | 50 | Y | NULL |
| BCA_ICON | nvarchar | 100 | Y | NULL |

### dbo.BOATCHOOSER_ANSWER_PRODUTO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BCAP_ANSWER_ID | int |  | N | NULL |
| BCAP_PRODUTO_ID | int |  | N | NULL |
| BCAP_PONTOS | int |  | Y | NULL |

### dbo.BOATCHOOSER_GROUPS  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BCG_ID | int |  | N | NULL |
| BCG_NAME | nvarchar | 50 | N | NULL |
| BCG_ORDER | int |  | Y | NULL |
| BCG_ICON | nvarchar | 100 | Y | NULL |
| BCG_SLUG | nvarchar | 50 | Y | NULL |
| BCG_ACTIVE | bit |  | N | NULL |
| BCG_QUIZ_ID | int |  | Y | NULL |

### dbo.BOATCHOOSER_QUESTION  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BCQ_ID | int |  | N | NULL |
| BCQ_QUESTION | nvarchar | 250 | Y | NULL |
| BCQ_SLUG | nvarchar | 50 | Y | NULL |
| BCQ_ORDER | int |  | Y | NULL |
| BCQ_ACTIVE | bit |  | N | NULL |
| BCQ_GROUP_ID | int |  | Y | NULL |
| BCQ_REQUIRED | bit |  | N | NULL |

### dbo.BOATCHOOSER_QUIZ  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BCZ_ID | int |  | N | NULL |
| BCZ_NAME | nvarchar | 150 | N | NULL |
| BCZ_SLUG | nvarchar | 50 | Y | NULL |

### dbo.CENTRO_ESTAGIO  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CE_ID | int |  | N | NULL |
| CE_NOME | nvarchar | -1 | N | NULL |
| CE_MORADA | nvarchar | -1 | Y | NULL |
| CE_TELEFONE | nvarchar | -1 | Y | NULL |
| CE_CONTACTO | nvarchar | -1 | Y | NULL |
| CE_CE_ID | int |  | Y | NULL |
| CE_COR | nvarchar | -1 | Y | NULL |
| CE_NUMPESS | int |  | N | NULL |

### dbo.CENTRO_ESTAGIO_DESPESAS  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CED_ID | int |  | N | NULL |
| CED_OBS | nvarchar | -1 | Y | NULL |
| CED_DATA | smalldatetime |  | N | NULL |
| CED_VALOR | float |  | N | NULL |
| CED_CE_ID | int |  | N | NULL |

### dbo.CENTRO_MODELOS_QTD  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CM_ID | int |  | N | NULL |
| CM_RES_ID | int |  | N | NULL |
| CM_NP_ID | int |  | Y | NULL |
| CM_M_ID | int |  | Y | NULL |
| CM_TAM_ID | int |  | Y | NULL |
| CM_QTD | int |  | N | NULL |
| CM_MODELO | nvarchar | -1 | N | NULL |

### dbo.CENTRO_RESERVA  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RES_ID | int |  | N | NULL |
| RES_E_ID | int |  | N | NULL |
| RES_CE_ID | int |  | N | NULL |
| RES_DATA | smalldatetime |  | N | NULL |
| RES_DATA_INI | smalldatetime |  | N | NULL |
| RES_DATA_FIM | smalldatetime |  | N | NULL |
| RES_OBS | nvarchar | -1 | Y | NULL |
| RES_TPCR_ID | int |  | Y | NULL |
| RES_DATA_TPCR | smalldatetime |  | N | NULL |
| RES_TR_ID | int |  | Y | NULL |
| RES_CONTACTO | nvarchar | -1 | Y | NULL |
| RES_FACTURADO | bit |  | N | NULL |
| RES_EQUIPA | nvarchar | -1 | Y | NULL |
| RES_PAIS_ID | int |  | Y | NULL |
| RES_OBS_FACT | nvarchar | -1 | Y | NULL |

### dbo.CENTRO_RESERVA_CHECKLIST  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CRCHKL_CRCHKLI_ID | int |  | N | NULL |
| CRCHKL_RES_ID | int |  | N | NULL |
| CRCHKL_DESCR | nvarchar | -1 | N | NULL |
| CRCHKL_TRATADO | bit |  | N | NULL |

### dbo.CENTRO_RESERVA_CHEKLIST_ITEMS  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CRCHKLI_ID | int |  | N | NULL |
| CRCHKLI_DESCR | nvarchar | -1 | N | NULL |
| CRCHKLI_ALARME | bit |  | N | NULL |
| CRCHKLI_ALARMEDIAS | int |  | N | NULL |
| CRCHKLI_STD | bit |  | N | NULL |
| CRCHKLI_ELIMINADO | smalldatetime |  | Y | NULL |

### dbo.CENTRO_RESERVA_ESTADO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPCR_ID | int |  | N | NULL |
| TPCR_NOME | nvarchar | -1 | N | NULL |
| TPCR_SEQUENCIA | int |  | N | NULL |
| TPCR_RESERVA_BARCOS | bit |  | N | NULL |

### dbo.CENTRO_RESERVA_OFS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RO_RES_ID | int |  | N | NULL |
| RO_OF_ID | int |  | N | NULL |
| RO_DATA_INI | smalldatetime |  | N | NULL |
| RO_DATA_FIM | smalldatetime |  | N | NULL |

### dbo.CENTRO_RESERVA_QUARTOS  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CRQ_ID | int |  | N | NULL |
| CRQ_DATA_ENT | smalldatetime |  | Y | NULL |
| CRQ_DATA_SAI | smalldatetime |  | Y | NULL |
| CRQ_SINGLE | int |  | N | NULL |
| CRQ_DOUBLE | int |  | N | NULL |
| CRQ_TRIPLE | int |  | N | NULL |
| CRQ_PRECO | float |  | N | NULL |
| CRQ_PRECO_NOSSO | float |  | N | NULL |
| CRQ_RES_ID | int |  | N | NULL |

### dbo.CENTRO_RESERVA_TRANSFER  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CRT_ID | int |  | N | NULL |
| CRT_DATA | smalldatetime |  | Y | NULL |
| CRT_OBS | nvarchar | -1 | Y | NULL |
| CRT_PAX | int |  | N | NULL |
| CRT_PRECO | float |  | N | NULL |
| CRT_RES_ID | int |  | N | NULL |
| CRT_CRTR_ID | int |  | Y | NULL |
| CRT_TRATADO | bit |  | N | NULL |

### dbo.CENTRO_RESERVA_TRANSFER_RESPONS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CRTR_ID | int |  | N | NULL |
| CRTR_DESC | nvarchar | -1 | N | NULL |
| CRTR_VALOR | float |  | N | NULL |

### dbo.COMPONENTE_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPCOMP_ID | int |  | N | NULL |
| TPCOMP_NOME | nvarchar | -1 | N | NULL |

### dbo.COMUNICACAO  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| COM_ID | int |  | N | NULL |
| COM_DATA | date |  | N | NULL |
| COM_ASSUNTO | nvarchar | -1 | N | NULL |
| COM_MENSAGEM | nvarchar | -1 | N | NULL |
| COM_ENVIADO | bit |  | N | NULL |
| COM_PARA | nvarchar | -1 | N | NULL |
| COM_REPLYTO | nvarchar | -1 | Y | NULL |
| COM_PRODUCAO | bit |  | N | NULL |
| COM_ISENCAO | bit |  | N | NULL |
| COM_E_ID | int |  | Y | NULL |

### dbo.COMUNICACAO_ANEXO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| COMATCH_ID | int |  | N | NULL |
| COMATCH_COM_ID | int |  | N | NULL |
| COMATCH_ORIGEM | nvarchar | -1 | N | NULL |

### dbo.COMUNICACAO_FASES_PRODUCAO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| COMFP_COM_ID | int |  | N | NULL |
| COMFP_FP_ID | int |  | Y | NULL |
| COMFP_E_ID | int |  | Y | NULL |

### dbo.COMUNICACAO_PRODUTO_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| COMTP_COM_ID | int |  | N | NULL |
| COMTP_TP_ID | int |  | N | NULL |

### dbo.CONSTRUCAO_DETALHE_IDS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_DESCONTINUADO | bit |  | N | NULL |

### dbo.CONSTRUCAO_DETALHE_NUMP  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| NP_ID | int |  | N | NULL |
| NP_NOME | nvarchar | -1 | N | NULL |

### dbo.CONSTRUCAO_DETALHE_TIPO_ASS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_ID | int |  | N | NULL |
| TP_NOME | nvarchar | -1 | N | NULL |

### dbo.CONSTRUCAO_FAMILIA  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_P_ID | int |  | Y | NULL |

### dbo.CORREIO_FACT  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CORRF_ID | int |  | N | NULL |
| CORRF_FORNECEDOR | nvarchar | -1 | N | NULL |
| CORRF_GUIA | nvarchar | -1 | Y | NULL |
| CORRF_REFERENCIA_ENVIO | nvarchar | -1 | Y | NULL |
| CORRF_DATA | smalldatetime |  | Y | NULL |
| CORRF_RUBRICA | nvarchar | -1 | Y | NULL |
| CORRF_VALOR_SEM_IVA | float |  | N | NULL |
| CORRF_DESCRICAO | nvarchar | -1 | Y | NULL |
| CORRF_DATA_CRIACAO | smalldatetime |  | N | NULL |
| CORRF_DATA_MODIFICACAO | smalldatetime |  | Y | NULL |

### dbo.CORREIO_TARIFAS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CT_ID | int |  | N | NULL |
| CT_PESO_MAX | float |  | Y | NULL |
| CT_TARIFA | decimal |  | Y | NULL |
| CT_ZONA_ID | int |  | Y | NULL |

### dbo.CORREIO_ZONAS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CZ_ID | int |  | N | NULL |
| CZ_NOME | nvarchar | 50 | N | NULL |
| CZ_E_ID | int |  | N | NULL |

### dbo.CORREIO_ZONA_PAIS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CZP_ZONA_ID | int |  | N | NULL |
| CZP_PAIS_ID | int |  | N | NULL |

### dbo.Competicao  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDCompeticao | int |  | N | NULL |
| NomeCompeticao | varchar | 100 | N | NULL |

### dbo.DIAS_FERIADOS_FERIAS  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DFF_ID | int |  | N | NULL |
| DFF_MES | int |  | N | NULL |
| DFF_DIA | int |  | N | NULL |
| DFF_FIXO | bit |  | N | NULL |
| DFF_FERIAS | bit |  | N | NULL |
| DFF_FERIADO | bit |  | N | NULL |
| DFF_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.DIAS_TRABALHO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DTRB_ID | int |  | N | NULL |
| DTRB_DATA | smalldatetime |  | N | NULL |

### dbo.DOC  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| doc_title_id | int |  | N | NULL |
| doc_description_id | int |  | N | NULL |
| folder | nvarchar | -1 | N | NULL |
| year | nvarchar | -1 | N | NULL |
| doc_type_id | int |  | N | NULL |
| created_at | smalldatetime |  | Y | NULL |
| update_at | smalldatetime |  | Y | NULL |
| is_public | bit |  | Y | NULL |
| available_all | bit |  | Y | NULL |
| url | nvarchar | -1 | N | NULL |
| entidades_allowed | nvarchar | -1 | N | NULL |
| entidades_blocked | nvarchar | -1 | N | NULL |
| doc_titulo | nvarchar | 50 | Y | NULL |
| doc_message | nvarchar | -1 | Y | NULL |

### dbo.DOC_DESCRIPTION  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| description | nvarchar | -1 | Y | NULL |

### dbo.DOC_PRODUTO_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| doc_doc_id | int |  | N | NULL |
| produto_tipo_tp_id | int |  | N | NULL |

### dbo.DOC_TITLE  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| title | nvarchar | -1 | Y | NULL |
| cover | nvarchar | -1 | Y | NULL |

### dbo.DOC_TYPE  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| type | nvarchar | -1 | Y | NULL |

### dbo.DOURO_AULA  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AULA_ID | int |  | N | NULL |
| AULA_DATA | smalldatetime |  | Y | NULL |
| AULA_QTD | int |  | N | NULL |
| AULA_PRECO | float |  | Y | NULL |
| AULA_DESCONTO | float |  | Y | NULL |
| AULA_OBS | varchar | 2000 | N | NULL |
| AULA_P_ID | int |  | N | NULL |
| AULA_MOV_ID | int |  | Y | NULL |
| AULA_MODALIDADE | varchar | 50 | Y | NULL |

### dbo.DOURO_AULA_ENTIDADE  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AULAE_AULA_ID | int |  | N | NULL |
| AULAE_E_ID | int |  | N | NULL |
| AULAE_DATA | date |  | N | NULL |
| AULAE_INTERESSE | int |  | Y | NULL |
| AULAE_PRESENCA | bit |  | N | NULL |
| AULAE_NOTAS_PROF | nvarchar | -1 | N | NULL |

### dbo.DOURO_AULA_MONITOR  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AM_AULA_ID | int |  | N | NULL |
| AM_E_ID | int |  | N | NULL |
| AM_HORAS | int |  | Y | NULL |
| AM_VALOR_PAGO | float |  | Y | NULL |

### dbo.DRAG_BARCO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| BARCO_ID | int |  | N | NULL |
| BARCO_NOME | nvarchar | 150 | N | NULL |
| BARCO_ID_DISCIPLINA | int |  | Y | NULL |

### dbo.DRAG_VELOCIDADE  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DRAG_ID | int |  | N | NULL |
| DRAG_BARCO_ID | int |  | N | NULL |
| DRAG_VELOCIDADE | decimal |  | N | NULL |
| DRAG_ARRASTO | decimal |  | N | NULL |

### dbo.Dealers_MailChimp  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_EMAIL | nvarchar | -1 | Y | NULL |
| fname | nvarchar | -1 | Y | NULL |
| lname | nvarchar | -1 | Y | NULL |
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| E_PAIS | nvarchar | -1 | Y | NULL |

### dbo.ENCOMENDA  (13 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ENC_ID | int |  | N | NULL |
| ENC_DATAENCOMENDA | smalldatetime |  | N | NULL |
| ENC_DATAPREVISTAENTREGA | smalldatetime |  | Y | NULL |
| ENC_DATAENTREGA | smalldatetime |  | Y | NULL |
| ENC_MORADAENTREGA | nvarchar | -1 | Y | NULL |
| ENC_PRECOTOTAL | float |  | N | NULL |
| ENC_TOTALPAGO | float |  | N | NULL |
| ENC_OBSERVACOES | nvarchar | -1 | Y | NULL |
| ENC_NOME | nvarchar | -1 | N | NULL |
| ENC_TRANSPORTE | nvarchar | -1 | Y | NULL |
| ENC_E_ID | int |  | N | NULL |
| ENC_EE_ID | int |  | N | NULL |
| ENC_TR_ID | int |  | Y | NULL |

### dbo.ENCOMENDA_ESTADO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EE_ID | int |  | N | NULL |
| EE_NOME | nvarchar | -1 | N | NULL |
| EE_SEQUENCIA | int |  | N | NULL |

### dbo.ENC_ENTIDADES  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |

### dbo.ENC_ESTADOS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EE_ID | int |  | N | NULL |
| EE_NOME | nvarchar | -1 | N | NULL |

### dbo.ENC_IDS  (1 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ENC_ID | int |  | N | NULL |

### dbo.ENTIDADE  (95 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| E_GENERO | nvarchar | 50 | Y | NULL |
| E_DATANASCIMENTO | smalldatetime |  | Y | NULL |
| E_PESOCORPORAL | float |  | N | NULL |
| E_CLUBE | nvarchar | -1 | Y | NULL |
| E_NUMTREINOS | int |  | N | NULL |
| E_CONTACTO | nvarchar | -1 | Y | NULL |
| E_PAIS | nvarchar | -1 | Y | NULL |
| E_CIDADE | nvarchar | -1 | Y | NULL |
| E_MORADA | nvarchar | -1 | Y | NULL |
| E_CODIGOPOSTAL | nvarchar | 50 | Y | NULL |
| E_MORADAENTREGA | nvarchar | -1 | Y | NULL |
| E_TELEFONE | nvarchar | -1 | Y | NULL |
| E_EMAIL | nvarchar | -1 | Y | NULL |
| E_COMPETICAO | bit |  | N | NULL |
| E_OBSERVACOES | nvarchar | -1 | Y | NULL |
| E_PRAZOPAGAMENTO | int |  | N | NULL |
| E_TRANSPORTEPAGO | bit |  | N | NULL |
| E_VISITA | bit |  | N | NULL |
| E_HORAHOMEM | float |  | N | NULL |
| E_FAZENTREGA | bit |  | N | NULL |
| E_PRAZOENTREGA | int |  | N | NULL |
| E_TOURING | bit |  | N | NULL |
| E_SPRINT | bit |  | N | NULL |
| E_EXPEDITIONS | bit |  | N | NULL |
| E_MARATHON | bit |  | N | NULL |
| E_ENT_ID | int |  | Y | NULL |
| E_ZG_ID | int |  | Y | NULL |
| E_ACTIVO | bit |  | N | NULL |
| E_FOTO | nvarchar | -1 | Y | NULL |
| E_CONTRIBUINTE | nvarchar | -1 | Y | NULL |
| E_CUSTOHORA | float |  | N | NULL |
| E_DATAENTRADA | smalldatetime |  | Y | NULL |
| E_TV_ID | int |  | Y | NULL |
| E_FALTA_DESC_HORAS | bit |  | N | NULL |
| E_HORAS_A_DOBRAR | bit |  | N | NULL |
| E_EQ_ID | int |  | Y | NULL |
| E_P_ID_FP | int |  | Y | NULL |
| E_FP_POS | nvarchar | -1 | Y | NULL |
| E_P_ID_BANCO | int |  | Y | NULL |
| E_BANCO_POS | nvarchar | -1 | Y | NULL |
| E_P_ID_STRAP | nvarchar | -1 | Y | NULL |
| E_L_ID | int |  | Y | NULL |
| E_LOGIN | nvarchar | -1 | Y | NULL |
| E_PASSWD | nvarchar | -1 | N | NULL |
| E_TIPO_UTIL | int |  | N | NULL |
| E_TAM_CALCADO | nvarchar | -1 | N | NULL |
| E_TAM_CALCA | nvarchar | -1 | N | NULL |
| E_TAM_CAMISOLA | nvarchar | -1 | N | NULL |
| E_TAM_FATO | nvarchar | -1 | N | NULL |
| E_GOOGLE_CALENDAR | nvarchar | -1 | Y | NULL |
| E_PHC_ID | int |  | Y | NULL |
| E_BENCH_CLASSE | int |  | Y | NULL |
| E_FACT_EPOCA | decimal |  | Y | NULL |
| E_FACT_TRIMESTRE | decimal |  | Y | NULL |
| E_DOURO_ID | varchar | 50 | Y | NULL |
| E_DOURO_SERVICO | int |  | Y | NULL |
| E_DOURO_VALIDADE | decimal |  | Y | NULL |
| E_DESCONTO | float |  | N | NULL |
| E_PAIS_ID | int |  | Y | NULL |
| E_MODALIDADE | varchar | 50 | Y | NULL |
| E_CHEFE | bit |  | N | NULL |
| E_FP_ID | int |  | Y | NULL |
| E_PRODUTIVIDADE | float |  | N | NULL |
| E_ACESSO_WEB | bit |  | N | NULL |
| E_PRECO_NACIONAL | bit |  | N | NULL |
| E_E_ID | int |  | Y | NULL |
| E_NELO | bit |  | N | NULL |
| E_TRANSPORTADOR | bit |  | N | NULL |
| E_CARTAO_RFID | nvarchar | 12 | Y | NULL |
| E_SHOP_ID | int |  | Y | NULL |
| E_ISENCAO_HORARIO | bit |  | N | NULL |
| E_ALTURA | float |  | N | NULL |
| E_CREDITO_PROMO | float |  | N | NULL |
| E_TAXA_IRS | float |  | N | NULL |
| E_BARCONUMERO | nvarchar | -1 | N | NULL |
| E_PAGAIANUMERO | nvarchar | -1 | N | NULL |
| E_BMI | float |  | N | NULL |
| E_TEMPO | float |  | N | NULL |
| E_GORDURA | float |  | N | NULL |
| E_FLEXOES | float |  | N | NULL |
| E_ABS | float |  | N | NULL |
| E_FUMADOR | bit |  | N | NULL |
| E_PREFERENCIA | varchar | 50 | Y | NULL |
| E_TEMPO_500 | decimal |  | Y | NULL |
| E_TEMPO_1000 | decimal |  | Y | NULL |
| E_CERTIFICADO_CO2 | bit |  | N | NULL |
| E_URL | nvarchar | 255 | Y | NULL |
| E_TAGS | nvarchar | 150 | Y | NULL |
| E_RESULTADO | int |  | N | NULL |
| E_NIVEL | int |  | N | NULL |
| E_TESTES_PORTUGAL | bit |  | N | NULL |
| E_RESPOSTA | int |  | N | NULL |
| E_CONTA_POC | nvarchar | -1 | N | NULL |

### dbo.ENTIDADE_DADOS  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EDADOS_ID | int |  | N | NULL |
| EDADOS_EMPRESA | nvarchar | -1 | N | NULL |
| EDADOS_MORADA | nvarchar | -1 | N | NULL |
| EDADOS_CODPOSTAL | nvarchar | -1 | N | NULL |
| EDADOS_PAISES_ID | int |  | Y | NULL |
| EDADOS_CONTACTO | nvarchar | -1 | N | NULL |
| EDADOS_CONTRIBUINTE | nvarchar | -1 | N | NULL |
| EDADOS_DATA | smalldatetime |  | N | NULL |
| EDADOS_PHC_NUMERO | int |  | Y | NULL |
| EDADOS_E_ID | int |  | N | NULL |

### dbo.ENTIDADE_EQUIPA  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EEQ_ID | int |  | N | NULL |
| EEQ_E_ID | int |  | N | NULL |
| EEQ_EQ_ID | int |  | N | NULL |
| EEQ_DATA_ENTRADA | smalldatetime |  | N | NULL |
| EEQ_DATA_SAIDA | smalldatetime |  | Y | NULL |
| EEQ_CHEFE | bit |  | N | NULL |
| EEQ_E_E_ID | int |  | Y | NULL |

### dbo.ENTIDADE_FASE  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EFP_ID | int |  | N | NULL |
| EFP_E_ID | int |  | N | NULL |
| EFP_FP_ID | int |  | N | NULL |
| EFP_DATAINICIO | smalldatetime |  | Y | NULL |
| EFP_DATAFIM | smalldatetime |  | Y | NULL |
| EFP_OBSERVACOES | nvarchar | -1 | Y | NULL |
| EFP_PRODUTIVIDADE | int |  | N | NULL |
| EFP_CHEFE | bit |  | N | NULL |
| EFP_QUALIFICADO | bit |  | N | NULL |
| EFP_DURACAO | float |  | N | NULL |
| EFP_SEQUENCIA | int |  | N | NULL |

### dbo.ENTIDADE_MORADA  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EM_ID | int |  | N | NULL |
| EM_E_ID | int |  | N | NULL |
| EM_CONTACTO | nvarchar | -1 | Y | NULL |
| EM_MORADA | nvarchar | -1 | N | NULL |
| EM_LONGITUDE | decimal |  | Y | NULL |
| EM_LATITUDE | decimal |  | Y | NULL |
| EM_DEFAULT | bit |  | N | NULL |
| EM_EMAIL | nvarchar | -1 | Y | NULL |
| EM_TELEFONE | nvarchar | -1 | Y | NULL |
| EM_TIPO | int |  | N | NULL |
| EM_NOME | nvarchar | 250 | Y | NULL |
| EM_DELETED | date |  | Y | NULL |
| EM_PAISES_ID | int |  | Y | NULL |
| EM_CONTRIBUINTE | nvarchar | -1 | Y | NULL |
| EM_SITE | nvarchar | -1 | Y | NULL |

### dbo.ENTIDADE_MORADA_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EMT_ID | int |  | N | NULL |
| EMT_TIPO | varchar | 150 | N | NULL |

### dbo.ENTIDADE_OBS  (13 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EOBS_ID | int |  | N | NULL |
| EOBS_DATA | smalldatetime |  | N | NULL |
| EOBS_E_ID | int |  | N | NULL |
| EOBS_DESCR | nvarchar | -1 | N | NULL |
| EOBS_OBS | nvarchar | -1 | N | NULL |
| EOBS_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| EOBS_E_ID_CRIADOR | int |  | N | NULL |
| EOBS_EOBSTP_ID | int |  | Y | NULL |
| EOBS_CERTIFICADO | bit |  | N | NULL |
| EOBS_DATA_INI | date |  | Y | NULL |
| EOBS_DATA_FIM | date |  | Y | NULL |
| EOBS_DURACAO | int |  | N | NULL |
| EOBS_EOBSTP_ID_CLASSIFIC | int |  | Y | NULL |

### dbo.ENTIDADE_OBS_ITEM  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EOBSITEM_ID | int |  | N | NULL |
| EOBSITEM_DESCR | nvarchar | -1 | N | NULL |
| EOBSITEM_VALOR | float |  | N | NULL |
| EOBSITEM_OBS | nvarchar | -1 | Y | NULL |
| EOBSITEM_EOBS_ID | int |  | N | NULL |

### dbo.ENTIDADE_OBS_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EOBSTP_ID | int |  | N | NULL |
| EOBSTP_TIPO | nvarchar | -1 | N | NULL |
| EOBSTP_ID_ID | int |  | Y | NULL |

### dbo.ENTIDADE_PHC  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EPHC_ID | int |  | N | NULL |
| EPHC_E_ID | int |  | N | NULL |
| EPHC_PHC_ID | int |  | N | NULL |

### dbo.ENTIDADE_PHC_FACT  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EPHCF_EPHC_ID | int |  | Y | NULL |
| EPHCF_ANO | int |  | N | NULL |
| EPHCF_MES | int |  | N | NULL |
| EPHCF_DIA | int |  | N | NULL |
| EPHCF_EPOCA | int |  | N | NULL |
| EPHCF_TP_ID_DISCIP | int |  | Y | NULL |
| EPHCF_TP_ID | int |  | Y | NULL |
| EPHCF_FACTURADO | float |  | N | NULL |

### dbo.ENTIDADE_PONTOS  (13 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EP_ID | int |  | N | NULL |
| EP_E_ID | int |  | Y | NULL |
| EP_PONTOS_ID | int |  | Y | NULL |
| EP_ANO | int |  | N | NULL |
| EP_MES | int |  | N | NULL |
| EP_DIASMES | int |  | N | NULL |
| EP_HORAS | float |  | N | NULL |
| EP_REPARACOES | float |  | N | NULL |
| EP_PREMIO | bit |  | N | NULL |
| EP_RESTO | int |  | N | NULL |
| EP_DESCONTO | int |  | N | NULL |
| EP_OBS | nvarchar | -1 | Y | NULL |
| EP_EQ_ID | int |  | Y | NULL |

### dbo.ENTIDADE_PROVAS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EPRV_E_ID | int |  | N | NULL |
| EPRV_PRV_ID | int |  | N | NULL |
| EPRV_RESULTADO | int |  | N | NULL |

### dbo.ENTIDADE_SUB  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| e_master_id | int |  | N | NULL |
| e_sub_id | int |  | N | NULL |

### dbo.ENTIDADE_TIPO  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ENT_ID | int |  | N | NULL |
| ENT_NOME | nvarchar | -1 | N | NULL |
| ENT_DESCRICAO | nvarchar | -1 | Y | NULL |
| ENT_ENT_ID | int |  | Y | NULL |
| ENT_FP_ID | int |  | Y | NULL |

### dbo.ENTIDADE_TREINOS  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ETR_ID | int |  | N | NULL |
| ETR_E_ID | int |  | N | NULL |
| ETR_DATA | smalldatetime |  | N | NULL |
| ETR_TEMPO | time |  | N | NULL |
| ETR_DESCRICAO | nvarchar | -1 | N | NULL |
| ETR_BARCO | nvarchar | -1 | N | NULL |
| ETR_DISTANCIA | float |  | N | NULL |
| ETR_CIRCUITO | bit |  | N | NULL |
| ETR_TRACK | nvarchar | -1 | N | NULL |
| ETR_PESOCORPORAL | float |  | N | NULL |
| ETR_ELIMINADO | smalldatetime |  | Y | NULL |

### dbo.ENT_CONFIG  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ECONF_ID | int |  | N | NULL |
| ECONF_E_ID | int |  | N | NULL |
| ECONF_P_ID_MODELO | int |  | N | NULL |
| ECONF_P_ID_ACESSORIO | int |  | Y | NULL |
| ECONF_ATRIB_ID | int |  | N | NULL |
| ECONF_ATRIB_ATRIB_ID | int |  | Y | NULL |
| ECONF_VALOR | float |  | N | NULL |
| ECONF_OBSERVACOES | nvarchar | -1 | Y | NULL |
| ECONF_DATA_CRIACAO | smalldatetime |  | N | NULL |
| ECONF_DATA_ACTUALIZACAO | smalldatetime |  | Y | NULL |
| ECONF_OF_ID | int |  | Y | NULL |

### dbo.ENT_ENT_PEDIDO_PROVISORIO  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EEP_ID | int |  | N | NULL |
| EEP_DATA_CRIACAO | smalldatetime |  | N | NULL |
| EEP_E_ID_RESP | int |  | N | NULL |
| EEP_E_ID_FORN | int |  | N | NULL |
| EEP_JSON | nvarchar | -1 | N | NULL |

### dbo.ENT_MOV  (20 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MOVENT_ID | int |  | N | NULL |
| MOVENT_MET_ID | int |  | N | NULL |
| MOVENT_E_ID | int |  | N | NULL |
| MOVENT_DATA_I | smalldatetime |  | N | NULL |
| MOVENT_DATA_F | smalldatetime |  | N | NULL |
| MOVENT_OBSERVACOES | nvarchar | -1 | Y | NULL |
| MOVENT_HORAS | float |  | N | NULL |
| MOVENT_DATA_PAG | smalldatetime |  | Y | NULL |
| MOVENT_VALOR_HORA | float |  | N | NULL |
| MOVENT_VALOR_PAGO | float |  | N | NULL |
| MOVENT_CC | float |  | N | NULL |
| MOVENT_PHC | bit |  | N | NULL |
| MOVENT_ANO | int |  | Y | NULL |
| MOVENT_MES | int |  | Y | NULL |
| MOVENT_PROCESSADO | bit |  | N | NULL |
| MOVENT_DESCONTA_LAMINADOR | bit |  | N | NULL |
| MOVENT_OF_ID | int |  | Y | NULL |
| MOVENT_VAI_PHC | bigint |  | N | NULL |
| MOVENT_E_E_ID | int |  | Y | NULL |
| MOVENT_FP_ID | int |  | Y | NULL |

### dbo.ENT_MOV_TIPO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MET_ID | int |  | N | NULL |
| MET_NOME | nvarchar | -1 | N | NULL |
| MET_DESCRICAO | nvarchar | -1 | N | NULL |
| MET_MET_ID | int |  | Y | NULL |
| MET_DESCONTA_HORAS | bit |  | N | NULL |
| MET_FACTOR | int |  | N | NULL |

### dbo.ENT_TIPO_VINCULO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TV_ID | int |  | N | NULL |
| TV_NOME | nvarchar | -1 | N | NULL |
| TV_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.ENT_TP_PROD  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ETP_E_ID | int |  | N | NULL |
| ETP_TP_ID | int |  | N | NULL |
| ETP_OBJ_OF | int |  | N | NULL |
| ETP_OBJ_VAL | float |  | N | NULL |
| ETP_BRAND_MANAGER | bit |  | N | NULL |

### dbo.EQUIPA  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EQ_ID | int |  | N | NULL |
| EQ_NOME | nvarchar | -1 | N | NULL |
| EQ_DATA_CRIACAO | smalldatetime |  | N | NULL |
| EQ_DATA_ELIMINADO | smalldatetime |  | Y | NULL |

### dbo.ESTACAO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EST_ID | int |  | N | NULL |
| EST_FASE | int |  | N | NULL |
| EST_E_ID | int |  | N | NULL |
| EST_CODIGO | int |  | N | NULL |

### dbo.Encomenda_trk  (12 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomenda | int |  | N | NULL |
| codOperador | int |  | Y | NULL |
| referencia | varchar | 50 | Y | NULL |
| dataPartida | decimal |  | Y | NULL |
| dataChegada | decimal |  | Y | NULL |
| dataPrevistaChegada | decimal |  | Y | NULL |
| horaPrevistaChegada | decimal |  | Y | NULL |
| codEstado | int |  | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| ultUpdate | datetime |  | Y | NULL |
| auxOrder | int |  | Y | NULL |

### dbo.EstadoOFAgente  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEstado | int |  | N | NULL |
| estado | varchar | 50 | Y | NULL |
| estadoEN | varchar | 50 | Y | NULL |

### dbo.FASES_PRODUCAO  (20 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| FP_ID | int |  | N | NULL |
| FP_NOME | nvarchar | -1 | N | NULL |
| FP_DESCRICAO | nvarchar | -1 | Y | NULL |
| FP_SEQUENCIA | int |  | N | NULL |
| FP_PRODUCAO | bit |  | N | NULL |
| FP_AUTOMATICA | bit |  | N | NULL |
| FP_FP_ID | int |  | Y | NULL |
| FP_HORA_COEF | float |  | N | NULL |
| FP_COR | varchar | 6 | Y | NULL |
| FP_LISTA_ATRIBUIDOS | bit |  | N | NULL |
| FP_COEF_EXTRA | bit |  | N | NULL |
| FP_RETORNOS_POR_TEMPO | bit |  | N | NULL |
| FP_P_ID | int |  | Y | NULL |
| FP_PODE_REPETIR | bit |  | N | NULL |
| FP_PLANEAMENTO | bit |  | N | NULL |
| FP_ASPNET_ROLES | nvarchar | -1 | Y | NULL |
| FP_PRE_REGISTO | bit |  | N | NULL |
| FP_VALOR_REF_K1 | float |  | N | NULL |
| FP_VALOR_REF_K2 | float |  | N | NULL |
| FP_VALOR_REF_K4 | float |  | N | NULL |

### dbo.FATURA  (22 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| fat_id | bigint |  | N | NULL |
| billed_to | nvarchar | 255 | Y | NULL |
| invoice_number | nvarchar | 255 | Y | NULL |
| date_of_issue | date |  | Y | NULL |
| due_date | date |  | Y | NULL |
| subtotal | decimal |  | Y | NULL |
| discount | decimal |  | Y | NULL |
| vat | decimal |  | Y | NULL |
| total | decimal |  | Y | NULL |
| company_name | nvarchar | 255 | Y | NULL |
| company_mobile | nvarchar | 255 | Y | NULL |
| company_email | nvarchar | 255 | Y | NULL |
| company_website | nvarchar | 255 | Y | NULL |
| company_vat_number | nvarchar | 255 | Y | NULL |
| email_from | nvarchar | 255 | Y | NULL |
| email_subject | nvarchar | 255 | Y | NULL |
| filename | nvarchar | 255 | Y | NULL |
| lancada | bit |  | N | NULL |
| pedido_id | int |  | Y | NULL |
| entidade_id | int |  | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.FERIAS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DATA | smalldatetime |  | N | NULL |
| TIPO | nvarchar | -1 | N | NULL |

### dbo.FORNECEDOR_IDS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |

### dbo.FP_FP  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| FPFP_FP_ID | int |  | N | NULL |
| FPFP_FP_FP_ID | int |  | N | NULL |
| FPFP_DESCR | nvarchar | -1 | Y | NULL |

### dbo.FuncionariosActivos  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| E_EMAIL | nvarchar | -1 | Y | NULL |

### dbo.Funcionarios_vencimento_medio  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| fpid | int |  | N | NULL |
| fpnome | nvarchar | -1 | N | NULL |
| Emps | int |  | Y | NULL |
| media_hora | float |  | Y | NULL |

### dbo.GASTOS_CACHE  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id_master | int |  | N | NULL |
| qtd | decimal |  | Y | NULL |
| valor | decimal |  | Y | NULL |
| refs | int |  | Y | NULL |

### dbo.IDEIA  (39 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ID_ID | int |  | N | NULL |
| ID_DESCRICAO | nvarchar | -1 | N | NULL |
| ID_SUGESTAO | nvarchar | -1 | N | NULL |
| ID_FONTE | nvarchar | -1 | N | NULL |
| ID_DATA | smalldatetime |  | N | NULL |
| ID_E_ID | int |  | N | NULL |
| ID_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| ID_IDCL_ID_GRAU | int |  | Y | NULL |
| ID_IDCL_ID_TIPO | int |  | Y | NULL |
| ID_IDCL_ID_RELEV | int |  | Y | NULL |
| ID_IDCL_ID_PRIORI | int |  | Y | NULL |
| ID_IDCL_ID_FACIL | int |  | Y | NULL |
| ID_IDEST_ID | int |  | Y | NULL |
| ID_ID_ID | int |  | Y | NULL |
| ID_DATA_INICIO | smalldatetime |  | Y | NULL |
| ID_DATA_FIM | smalldatetime |  | Y | NULL |
| ID_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| ID_TEM_IDI | bit |  | N | NULL |
| ID_FEEDBACK | nvarchar | -1 | Y | NULL |
| ID_AVAL_1 | int |  | N | NULL |
| ID_AVAL_2 | int |  | N | NULL |
| ID_AVAL_3 | int |  | N | NULL |
| ID_AVAL_4 | int |  | N | NULL |
| ID_AVAL_5 | int |  | N | NULL |
| ID_AVAL_6 | int |  | N | NULL |
| ID_AVAL_7 | int |  | N | NULL |
| ID_AVAL_TP | int |  | N | NULL |
| ID_AVAL_RF | int |  | N | NULL |
| ID_AVAL_RH | int |  | N | NULL |
| ID_COMUNICACAO | nvarchar | -1 | N | NULL |
| ID_OBSERVACOES | nvarchar | -1 | N | NULL |
| ID_LICOES | nvarchar | -1 | N | NULL |
| ID_PROP_INTELECT | nvarchar | -1 | N | NULL |
| ID_RESULTADO_PI | nvarchar | -1 | N | NULL |
| ID_E_ID_COORDENADOR | int |  | Y | NULL |
| ID_OBJECTIVOS_ESPERADOS | nvarchar | -1 | N | NULL |
| ID_ORCAMENTO | nvarchar | -1 | N | NULL |
| ID_ENTIDADES_EXTERNAS | nvarchar | -1 | N | NULL |
| ID_TIPOLOGIA | nvarchar | -1 | N | NULL |

### dbo.IDEIA_CLASSIFICACAO  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDCL_ID | int |  | N | NULL |
| IDCL_CLASSIFIC | nvarchar | -1 | N | NULL |
| IDCL_DESCRICAO | nvarchar | -1 | Y | NULL |
| IDCL_DATA | smalldatetime |  | N | NULL |
| IDCL_IDCL_ID | int |  | Y | NULL |

### dbo.IDEIA_CLASSIFIC_CHECK  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDCLCHK_IDCL_ID | int |  | N | NULL |
| IDCLCHK_PERIODICIDADE | int |  | N | NULL |
| IDCLCHK_DIASEMANA | int |  | N | NULL |
| IDCLCHK_DATAINICIO | date |  | N | NULL |

### dbo.IDEIA_COLAB  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDCOL_ID | int |  | N | NULL |
| IDCOL_E_ID | int |  | N | NULL |
| IDCOL_ID_ID | int |  | Y | NULL |
| IDCOL_IDEV_ID | int |  | Y | NULL |
| IDCOL_TPCOL_ID | int |  | N | NULL |
| IDCOL_DATA | smalldatetime |  | N | NULL |

### dbo.IDEIA_DOC  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDDOC_ID | int |  | N | NULL |
| IDDOC_NOME | nvarchar | -1 | Y | NULL |
| IDDOC_DESCRICAO | nvarchar | -1 | Y | NULL |
| IDDOC_CAMINHO | nvarchar | -1 | N | NULL |
| IDDOC_E_ID | int |  | N | NULL |
| IDDOC_ID_ID | int |  | N | NULL |
| IDDOC_DATA | smalldatetime |  | N | NULL |
| IDDOC_IDDOC_ID | int |  | Y | NULL |

### dbo.IDEIA_ENTIDADE  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDENT_ID_ID | int |  | N | NULL |
| IDENT_E_ID | int |  | N | NULL |
| IDENT_OBS | nvarchar | -1 | Y | NULL |

### dbo.IDEIA_ESTADO  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDEST_ID | int |  | N | NULL |
| IDEST_ESTADO | nvarchar | -1 | N | NULL |
| IDEST_DESCRICAO | nvarchar | -1 | Y | NULL |
| IDEST_DATA | smalldatetime |  | N | NULL |
| IDEST_IDEST_ID | int |  | Y | NULL |
| IDEST_SEQUENCIA | int |  | N | NULL |
| IDEST_INACTIVO | bit |  | N | NULL |

### dbo.IDEIA_EVOL  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDEV_ID | int |  | N | NULL |
| IDEV_ID_ID | int |  | N | NULL |
| IDEV_IDEST_ID | int |  | N | NULL |
| IDEV_DATA_I | smalldatetime |  | N | NULL |
| IDEV_DATA_F | smalldatetime |  | Y | NULL |
| IDEV_DATA_APROV | smalldatetime |  | Y | NULL |
| IDEV_SCORE | int |  | Y | NULL |
| IDEV_APROV_OBS | nvarchar | -1 | Y | NULL |
| IDEV_IDEV_ID | int |  | Y | NULL |

### dbo.IDEIA_REUNIAO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDR_ID | int |  | N | NULL |
| IDR_NOME | nvarchar | -1 | N | NULL |
| IDR_DESCR | nvarchar | -1 | Y | NULL |
| IDR_DATA | smalldatetime |  | N | NULL |
| IDR_ID_ID | int |  | N | NULL |
| IDR_ELIMINADO | smalldatetime |  | Y | NULL |

### dbo.IDEIA_TAREFA  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDTAR_ID | int |  | N | NULL |
| IDTAR_IDEV_ID | int |  | N | NULL |
| IDTAR_E_ID | int |  | N | NULL |
| IDTAR_DESCRICAO | nvarchar | -1 | N | NULL |
| IDTAR_OBS | nvarchar | -1 | Y | NULL |
| IDTAR_DATA | smalldatetime |  | N | NULL |
| IDTAR_DATA_I | smalldatetime |  | Y | NULL |
| IDTAR_DATA_F | smalldatetime |  | Y | NULL |
| IDTAR_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| IDTAR_IDTAR_ID | int |  | Y | NULL |
| IDTAR_DESVIO | int |  | N | NULL |
| IDTAR_RESULTADOS | nvarchar | -1 | Y | NULL |
| IDTAR_DATA_P_I | smalldatetime |  | Y | NULL |
| IDTAR_DATA_P_F | smalldatetime |  | Y | NULL |
| IDTAR_RESULTADOS_P | nvarchar | -1 | Y | NULL |

### dbo.IDEIA_TPCOL  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPCOL_ID | int |  | N | NULL |
| TPCOL_NOME | nvarchar | -1 | N | NULL |

### dbo.IMPORT  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ID | int |  | N | NULL |
| REGISTO | int |  | N | NULL |
| DESCRICAO | nvarchar | -1 | N | NULL |

### dbo.INTERVALO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| INTERVALO_ID | int |  | N | NULL |
| INTERVALO_INICIO | int |  | N | NULL |
| INTERVALO_FIM | int |  | N | NULL |
| INTERVALO_TP_ID | int |  | N | NULL |

### dbo.IOT_SENSOR  (18 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SENSOR_ID | int |  | N | NULL |
| SENSOR_NAME | nvarchar | 150 | N | NULL |
| SENSOR_LOCATION | nvarchar | 150 | Y | NULL |
| SENSOR_URL | nvarchar | 255 | Y | NULL |
| SENSOR_TEMP | bit |  | N | NULL |
| SENSOR_HUM | bit |  | N | NULL |
| SENSOR_POWERMETER | bit |  | N | NULL |
| SENSOR_SWITCH | bit |  | N | NULL |
| SENSOR_CHART_FROM | nvarchar | 10 | Y | NULL |
| SENSOR_CHART_TO | nvarchar | 10 | Y | NULL |
| SENSOR_TIPO_ID | int |  | N | NULL |
| SENSOR_ACTIVO | bit |  | N | NULL |
| SENSOR_INTERVAL | int |  | N | NULL |
| SENSOR_EXTRAS | nvarchar | 255 | Y | NULL |
| SENSOR_CHECK_ALIVE | bit |  | N | NULL |
| SENSOR_LAST_SEEN | datetime |  | Y | NULL |
| SENSOR_NOTIFICATION_SENT | bit |  | N | NULL |
| SENSOR_PARENT_ID | int |  | Y | NULL |

### dbo.IOT_SENSOR_ALARM  (19 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SA_ID | bigint |  | N | NULL |
| SA_NOME | nvarchar | 255 | N | NULL |
| SA_SENSOR_ID | bigint |  | N | NULL |
| SA_FIELD | nvarchar | 255 | N | NULL |
| SA_MIN | float |  | Y | NULL |
| SA_MAX | float |  | Y | NULL |
| SA_TEST_INTERVAL | int |  | N | NULL |
| SA_ALARM_COOLDOWN | int |  | N | NULL |
| SA_LAST_ALARM | bigint |  | Y | NULL |
| SA_ACTIVE_FROM | time |  | Y | NULL |
| SA_ACTIVE_TO | time |  | Y | NULL |
| SA_ALARM_ACTIVE | bit |  | N | NULL |
| SA_SUNDAY | bit |  | N | NULL |
| SA_MONDAY | bit |  | N | NULL |
| SA_TUESDAY | bit |  | N | NULL |
| SA_WEDNESDAY | bit |  | N | NULL |
| SA_THURSDAY | bit |  | N | NULL |
| SA_FRIDAY | bit |  | N | NULL |
| SA_SATURDAY | bit |  | N | NULL |

### dbo.IOT_SENSOR_DATA  (12 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SD_ID | int |  | N | NULL |
| SD_SENSOR_ID | int |  | N | NULL |
| SD_DATE | datetime |  | N | NULL |
| SD_POWER_1 | int |  | Y | NULL |
| SD_POWER_2 | int |  | Y | NULL |
| SD_POWER_3 | int |  | Y | NULL |
| SD_CURRENT_1 | decimal |  | Y | NULL |
| SD_CURRENT_2 | decimal |  | Y | NULL |
| SD_CURRENT_3 | decimal |  | Y | NULL |
| SD_TEMPERATURE | decimal |  | Y | NULL |
| SD_HUM | decimal |  | Y | NULL |
| SD_PRESSURE | float |  | Y | NULL |

### dbo.IOT_SENSOR_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ST_ID | int |  | N | NULL |
| ST_NAME | nvarchar | 50 | N | NULL |
| ST_CLASS | nvarchar | 50 | Y | NULL |

### dbo.KPI  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| KPI_ID | int |  | N | NULL |
| KPI_DATA | date |  | N | NULL |
| KPI_NOME | nvarchar | -1 | N | NULL |
| KPI_DESCRICAO | nvarchar | -1 | N | NULL |
| KPI_KPI_ID | int |  | Y | NULL |
| KPI_ORDEM | int |  | N | NULL |
| KPI_AUTOMATICO | bit |  | N | NULL |
| KPI_ROLE | nvarchar | -1 | Y | NULL |

### dbo.KPI_OBJECTIVO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| KPIO_ID | int |  | N | NULL |
| KPIO_KPI_ID | int |  | N | NULL |
| KPIO_DATA | date |  | N | NULL |
| KPIO_VALOR | float |  | N | NULL |
| KPIO_OBJECTIVO | float |  | N | NULL |
| KPIO_OBJECTIVO_DATA | date |  | Y | NULL |

### dbo.LACAGEM  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| LAC_ID | int |  | N | NULL |
| LAC_DESCRICAO | nvarchar | -1 | Y | NULL |
| LAC_QTD | int |  | N | NULL |
| LAC_DATA_I | smalldatetime |  | N | NULL |
| LAC_DATA_F | smalldatetime |  | Y | NULL |

### dbo.LISTA  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| L_ID | int |  | N | NULL |
| L_DATA_CRIACAO | smalldatetime |  | N | NULL |
| L_DESCRICAO | nvarchar | -1 | N | NULL |
| L_OBS | nvarchar | -1 | N | NULL |
| L_LTP_ID | int |  | N | NULL |
| L_IMAGEM | nvarchar | -1 | Y | NULL |

### dbo.LISTA_COORDENADAS  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| LCOORD_ID | int |  | N | NULL |
| LCOORD_L_ID | int |  | N | NULL |
| LCOORD_1 | int |  | N | NULL |
| LCOORD_2 | int |  | N | NULL |
| LCOORD_3 | int |  | N | NULL |
| LCOORD_4 | int |  | N | NULL |
| LCOORD_ATRIB_ID | int |  | N | NULL |

### dbo.LISTA_MOVIMENTO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| LM_ID | int |  | N | NULL |
| LM_L_ID | int |  | N | NULL |
| LM_DATA | smalldatetime |  | N | NULL |
| LM_TIPO | nvarchar | -1 | N | NULL |

### dbo.LISTA_PRODUTO  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| LP_L_ID | int |  | N | NULL |
| LP_P_ID | int |  | N | NULL |
| LP_QTD | float |  | N | NULL |
| LP_OBS | nvarchar | -1 | N | NULL |
| LP_SITIO | nvarchar | -1 | N | NULL |
| LP_CORES | bit |  | N | NULL |
| LP_TOPOS | bit |  | N | NULL |
| LP_LATERAIS | bit |  | N | NULL |
| LP_QUINAS | bit |  | N | NULL |
| LP_CASCO | bit |  | N | NULL |
| LP_GOLA | bit |  | N | NULL |
| LP_RISCA | bit |  | N | NULL |
| LP_EXTRA | bit |  | N | NULL |
| LP_CUSTO_EXTRA_OF | bit |  | N | NULL |
| LP_DECK | bit |  | N | NULL |

### dbo.LISTA_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| LTP_ID | int |  | N | NULL |
| LTP_DESCR | nvarchar | -1 | N | NULL |

### dbo.MAILS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MAIL_ID | int |  | N | NULL |
| MAIL_NOME | nvarchar | -1 | N | NULL |
| MAIL_SUBJECT | nvarchar | -1 | Y | NULL |
| MAIL_BODY | nvarchar | -1 | Y | NULL |

### dbo.MEDIDAS  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MED_ID | int |  | N | NULL |
| MED_NP_ID | int |  | N | NULL |
| MED_M_ID | int |  | N | NULL |
| MED_TAM_ID | int |  | N | NULL |
| MED_OBS | nvarchar | -1 | Y | NULL |
| MED_MEDIDA | float |  | N | NULL |
| MED_OBSERVACOES | nvarchar | -1 | Y | NULL |

### dbo.MODELOS_CL_CONST_MOD_TAM_NP  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | Y | NULL |
| nome | nvarchar | -1 | Y | NULL |
| tipo | varchar | 11 | N | NULL |
| p_descontinuado | int |  | N | NULL |

### dbo.MODELOS_IDS  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |

### dbo.MOLDES  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MLD_ID | int |  | N | NULL |
| MLD_NOME | nvarchar | -1 | N | NULL |
| MLD_DATA | smalldatetime |  | N | NULL |
| MLD_MLDTP_ID | int |  | N | NULL |
| MLD_UTILIZ | int |  | N | NULL |

### dbo.MOLDES_CONST_MOD_TAM_NP  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| nome | nvarchar | -1 | N | NULL |
| tipo | varchar | 11 | N | NULL |

### dbo.MOLDES_MOV  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MLDU_ID | int |  | N | NULL |
| MLDU_DATA | smalldatetime |  | N | NULL |
| MLDU_TP_ID | int |  | N | NULL |
| MLDU_MLD_ID | int |  | N | NULL |
| MLDU_E_ID | int |  | N | NULL |

### dbo.MOLDES_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MLDTP_ID | int |  | N | NULL |
| MLDTP_NOME | nvarchar | -1 | N | NULL |
| MLDTP_NUMUTIL | int |  | N | NULL |

### dbo.MOVIMENTO  (41 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MOV_ID | int |  | N | NULL |
| MOV_DATA | smalldatetime |  | Y | NULL |
| MOV_DATASAIDA | smalldatetime |  | Y | NULL |
| MOV_QUANTIDADE | float |  | N | NULL |
| MOV_PRECOUNITARIO | float |  | N | NULL |
| MOV_PRECOVENDA | float |  | N | NULL |
| MOV_DESCONTO | float |  | N | NULL |
| MOV_OBSERVACOES | nvarchar | -1 | Y | NULL |
| MOV_PROBLEMA | nvarchar | -1 | Y | NULL |
| MOV_NUMUTIL | int |  | N | NULL |
| MOV_OF_ID | int |  | Y | NULL |
| MOV_E_ID | int |  | Y | NULL |
| MOV_P_ID | int |  | Y | NULL |
| MOV_TPMOV_ID | int |  | N | NULL |
| MOV_MOV_ID | int |  | Y | NULL |
| MOV_ARM_ID | int |  | Y | NULL |
| MOV_LM_ID | int |  | Y | NULL |
| MOV_SERVER | nvarchar | -1 | N | NULL |
| MOV_TR_ID | int |  | Y | NULL |
| MOV_PRODF_ID | int |  | Y | NULL |
| MOV_PL_ID | int |  | Y | NULL |
| MOV_QTD_BAL | float |  | N | NULL |
| MOV_DECK_PART | nvarchar | -1 | N | NULL |
| MOV_LOTE | nvarchar | -1 | Y | NULL |
| MOV_ACERTO | bit |  | N | NULL |
| MOV_ACESSORIO_ADICIONAL | bit |  | N | NULL |
| MOV_DEFEITUOSO | bit |  | N | NULL |
| MOV_SATISFEITO | bit |  | N | NULL |
| MOV_ID_PEDIDO | int |  | Y | NULL |
| MOV_ATRIB_ID | int |  | Y | NULL |
| MOV_SHOP_ORDER_ID | varchar | 50 | Y | NULL |
| MOV_SHOP_ORDER_ITEM_ID | int |  | Y | NULL |
| MOV_SHOP_UPDATED_AT | smalldatetime |  | Y | NULL |
| MOV_E_ID_RESPONSAVEL | int |  | Y | NULL |
| MOV_SHOP_SHIPPING | nvarchar | -1 | Y | NULL |
| MOV_SHOP_ENTITY_ID | int |  | Y | NULL |
| MOV_DATA_APROVADO | smalldatetime |  | Y | NULL |
| MOV_E_ID_APROVA | int |  | Y | NULL |
| MOV_ENVIA_ANEXO | bit |  | N | NULL |
| MOV_FP_ID | int |  | Y | NULL |
| MOV_OFFP_ID | int |  | Y | NULL |

### dbo.MOVIMENTO_ATTACH  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MATCH_ID | int |  | N | NULL |
| MATCH_NOME | nvarchar | -1 | N | NULL |
| MATCH_DESCRICAO | nvarchar | -1 | Y | NULL |
| MATCH_MOV_ID | int |  | N | NULL |
| MATCH_FILE | nvarchar | -1 | N | NULL |

### dbo.MOVIMENTO_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPMOV_ID | int |  | N | NULL |
| TPMOV_NOME | nvarchar | -1 | N | NULL |

### dbo.Meeting  (37 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codConvidado | int |  | N | NULL |
| nome | varchar | 150 | Y | NULL |
| voo_chegada | varchar | 150 | Y | NULL |
| data_chegada | decimal |  | Y | NULL |
| hora_chegada | decimal |  | Y | NULL |
| voo_saida | varchar | 150 | Y | NULL |
| data_saida | decimal |  | Y | NULL |
| hora_saida | decimal |  | Y | NULL |
| custo_voo | decimal |  | Y | NULL |
| voo_marcado | bit |  | Y | NULL |
| transfer | bit |  | Y | NULL |
| partilha_com | int |  | Y | NULL |
| nome_acompanhante | varchar | 150 | Y | NULL |
| tipo_quarto | int |  | Y | NULL |
| quarto_reservado | bit |  | Y | NULL |
| estado | int |  | Y | NULL |
| obs | text | 2147483647 | Y | NULL |
| data_criacao | datetime |  | N | NULL |
| agente | bit |  | N | NULL |
| prova | varchar | 50 | Y | NULL |
| acompanhante | bit |  | Y | NULL |
| pago | bit |  | Y | NULL |
| pais | int |  | Y | NULL |
| refeicoes_extra | varchar | 500 | Y | NULL |
| hotel | varchar | 50 | Y | NULL |
| Email | varchar | 255 | Y | NULL |
| Contacto | varchar | 30 | Y | NULL |
| Cidade | varchar | 255 | Y | NULL |
| Foto | varchar | -1 | Y | NULL |
| PassaporteID | varchar | 255 | Y | NULL |
| PassaporteFoto | nvarchar | -1 | Y | NULL |
| TamanhoShirt | varchar | 5 | Y | NULL |
| FotoAcompanhante | varchar | -1 | Y | NULL |
| PassaporteAcompanhanteID | varchar | 255 | Y | NULL |
| PassaporteAcompanhanteFoto | varchar | -1 | Y | NULL |
| TamanhoShirtAcompanhante | varchar | 5 | Y | NULL |
| CodConvite | varchar | 10 | Y | NULL |

### dbo.MeetingEstado  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEstado | int |  | N | NULL |
| estado | varchar | 50 | Y | NULL |

### dbo.Moldes_movimentacao  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF_ID | int |  | N | NULL |
| OF_NOME | nvarchar | -1 | Y | NULL |
| p_nome | nvarchar | -1 | Y | NULL |

### dbo.OFCH_LOCAL  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFPROBS_OFCH_ID | int |  | N | NULL |
| OFPROBS_PROBSL_ID | int |  | N | NULL |

### dbo.OFCOMP_CLASSES  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| tp_id | int |  | Y | NULL |
| tp_nome | nvarchar | -1 | Y | NULL |

### dbo.OFCOMP_PRODUTOS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_TP_ID | int |  | Y | NULL |
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_MEDIDA | nvarchar | 50 | N | NULL |

### dbo.OFFP_CL  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFPCL_ID | int |  | N | NULL |
| OFFPCL_DESC | nvarchar | -1 | N | NULL |
| OFFPCL_SEQUENCIA | int |  | N | NULL |
| OFFPCL_DESC_EN | nvarchar | -1 | Y | NULL |

### dbo.OFFP_EQ  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFPEQ_OFFP_ID | int |  | N | NULL |
| OFFPEQ_E_ID | int |  | N | NULL |
| OFFPEQ_CHEFE | bit |  | N | NULL |

### dbo.OFFP_GRAVIDADE  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFPGRAV_ID | int |  | N | NULL |
| OFFPGRAV_DESCRICAO | nvarchar | -1 | N | NULL |
| OFFPGRAV_PARAR | bit |  | N | NULL |

### dbo.OFFP_GRAVIDADES  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| FPGRAV_OFFP_ID | int |  | N | NULL |
| FPGRAV_OFFPGRAV_ID | int |  | N | NULL |

### dbo.OFFP_LINK  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFPL_OFFP_ID_PROX | int |  | N | NULL |
| OFFPL_OFFP_ID_ANT | int |  | N | NULL |
| OFFPL_SEQUENCIA | int |  | N | NULL |

### dbo.OFFP_PROBLEMA  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFPPROB_PROBS_ID | int |  | N | NULL |
| OFFPPROB_OFFP_ID | int |  | N | NULL |
| OFFPPROB_PROBSL_ID | int |  | N | NULL |
| OFFPPROB_OBS | nvarchar | -1 | Y | NULL |

### dbo.OF_ATTACH  (12 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ATCH_ID | int |  | N | NULL |
| ATCH_NOME | nvarchar | -1 | Y | NULL |
| ATCH_DESCRICAO | nvarchar | -1 | Y | NULL |
| ATCH_OF_ID | int |  | N | NULL |
| ATCH_IMAGE | nvarchar | -1 | N | NULL |
| ATCH_PUBLICO | bit |  | N | NULL |
| ATCH_PRODUCAO | bit |  | N | NULL |
| ATCH_TIPO | int |  | Y | NULL |
| ATCH_ENVIADO_PROPRIETARIO | bit |  | N | NULL |
| ATCH_ELIMINADO | date |  | Y | NULL |
| ATCH_FP_ID | int |  | Y | NULL |
| ATCH_DATA | date |  | Y | NULL |

### dbo.OF_CHECKLIST  (19 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFCH_ID | int |  | N | NULL |
| OFCH_DESCR | nvarchar | -1 | N | NULL |
| OFCH_VISTO | bit |  | Y | NULL |
| OFCH_RESOLVIDO | bit |  | Y | NULL |
| OFCH_OF_ID | int |  | Y | NULL |
| OFCH_SEQUENCIA | int |  | N | NULL |
| OFCH_FP_ID | int |  | Y | NULL |
| OFCH_ESTADO | int |  | Y | NULL |
| OFCH_DESCR_EN | nvarchar | -1 | Y | NULL |
| OFCH_FP_ID_CHK | int |  | Y | NULL |
| OFCH_OBSERVACOES | nvarchar | -1 | Y | NULL |
| OFCH_GRAVIDADE | int |  | N | NULL |
| OFCH_JSON_DOTS | nvarchar | -1 | Y | NULL |
| OFCH_DATA_VERIFICACAO | smalldatetime |  | Y | NULL |
| OFCH_DATA_ACTUALIZACAO | smalldatetime |  | Y | NULL |
| OFCH_CULPA_CHEFE | bit |  | N | NULL |
| OFCH_OFFP_ID | int |  | Y | NULL |
| OFCH_MOLDE_REPARAR | bit |  | N | NULL |
| OFCH_OFFP_ID_CULPA | int |  | Y | NULL |

### dbo.OF_CLASSES_KAYAK  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| tp_id | int |  | Y | NULL |
| tp_nome | nvarchar | -1 | Y | NULL |

### dbo.OF_CLASSES_MOLDES_MATRIZES  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_ID | int |  | N | NULL |
| TP_NOME | nvarchar | -1 | N | NULL |

### dbo.OF_EMBALAGENS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_NP_ID | int |  | Y | NULL |

### dbo.OF_ENCOMENDAS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ENC_ID | int |  | N | NULL |
| ENC_NOME | nvarchar | -1 | N | NULL |
| ENC_E_ID | int |  | N | NULL |

### dbo.OF_ENTIDADE  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFE_ID | int |  | N | NULL |
| OFE_OF_ID | int |  | N | NULL |
| OFE_OF_PRECOVENDA | float |  | N | NULL |
| OFE_E_ID_ANTERIOR | int |  | N | NULL |
| OFE_DATA | date |  | N | NULL |
| OFE_E_ID_RESPONSAVEL | int |  | N | NULL |

### dbo.OF_ENTIDADES  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| E_ENT_ID | int |  | Y | NULL |
| efp_fp_id | int |  | Y | NULL |
| E_MORADA | nvarchar | -1 | Y | NULL |
| E_TELEFONE | nvarchar | -1 | Y | NULL |
| E_EMAIL | nvarchar | -1 | Y | NULL |

### dbo.OF_ESTADOS  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| FP_ID | int |  | N | NULL |
| FP_NOME | nvarchar | -1 | N | NULL |
| FP_SEQUENCIA | int |  | N | NULL |
| FP_FP_ID | int |  | Y | NULL |
| fp_pode_repetir | int |  | N | NULL |

### dbo.OF_FP  (52 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFFP_ID | int |  | N | NULL |
| OFFP_OF_ID | int |  | N | NULL |
| OFFP_FP_ID | int |  | N | NULL |
| OFFP_PROBLEMAS | nvarchar | -1 | Y | NULL |
| OFFP_OBSERVACOES | nvarchar | -1 | Y | NULL |
| OFFP_DATAINICIO | smalldatetime |  | Y | NULL |
| OFFP_DATAFIM | smalldatetime |  | Y | NULL |
| OFFP_PESO | float |  | N | NULL |
| OFFP_NUMUTIL | int |  | N | NULL |
| OFFP_PESO_DECK_ANT | float |  | N | NULL |
| OFFP_PESO_DECK_DP | float |  | N | NULL |
| OFFP_PESO_CASCO_ANT | float |  | N | NULL |
| OFFP_PESO_CASCO_DP | float |  | N | NULL |
| OFFP_SERVER | nvarchar | -1 | N | NULL |
| OFFP_ARM_ID | int |  | Y | NULL |
| OFFP_SEQUENCIA | smalldatetime |  | Y | NULL |
| OFFP_OFFPCL_ID | int |  | Y | NULL |
| OFFP_HORAS_REP | float |  | N | NULL |
| OFFP_HORAS_REP_REAL | float |  | N | NULL |
| OFFP_PECAS | bit |  | N | NULL |
| OFFP_CONTROLO | bit |  | N | NULL |
| OFFP_TEMPERATURA | float |  | N | NULL |
| OFFP_HUMIDADE | float |  | N | NULL |
| OFFP_CONTROLO_CRIS | bit |  | N | NULL |
| OFFP_EMAIL_CRIS | bit |  | N | NULL |
| OFFP_PROBS_GOLA | nvarchar | 2000 | Y | NULL |
| OFFP_PROBS_INTERIOR | int |  | Y | NULL |
| OFFP_PROBS_PINTURA | int |  | Y | NULL |
| OFFP_PROBS_MOLDE | int |  | Y | NULL |
| OFFP_PROBS_LAMINAGEM | int |  | Y | NULL |
| OFFP_PROBS_DATA | smalldatetime |  | Y | NULL |
| OFFP_PROBS_LAM_INOCENTE | bit |  | N | NULL |
| OFFP_PROBS_PINT_INOCENTE | bit |  | N | NULL |
| OFFP_ORDEM | int |  | N | NULL |
| OFFP_PESO_HIST | nvarchar | -1 | N | NULL |
| OFFP_LINHA_AUX | int |  | Y | NULL |
| OFFP_RETURN | bit |  | N | NULL |
| OFFP_OFFP_ID_RETURN | int |  | Y | NULL |
| OFFP_COEFICIENTE | float |  | N | NULL |
| OFFP_TPCAM_ID | int |  | Y | NULL |
| OFFP_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| OFFP_PLANEAMENTO | bit |  | N | NULL |
| OFFP_TURN_ID | int |  | Y | NULL |
| OFFP_OF_ID_MLD | int |  | Y | NULL |
| OFFP_DATA_ENTREGA | smalldatetime |  | Y | NULL |
| OFFP_COEFICIENTE_X | float |  | N | NULL |
| OFFP_RETORNO_GRAVE | bit |  | N | NULL |
| OFFP_EMAIL | nvarchar | -1 | Y | NULL |
| OFFP_VALOR_FACT | float |  | N | NULL |
| OFFP_VALOR_CONTROL_1 | float |  | N | NULL |
| OFFP_VALOR_CONTROL_2 | float |  | N | NULL |
| OFFP_VALOR_CONTROL_3 | float |  | N | NULL |

### dbo.OF_IDS  (1 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF_ID | int |  | N | NULL |

### dbo.OF_IDS_MLD  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF_ID | int |  | N | NULL |
| OF_NOME | nvarchar | -1 | Y | NULL |

### dbo.OF_LINHA_PROD  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id_of | int |  | N | NULL |
| linha | varchar | 7 | N | NULL |

### dbo.OF_LOTE  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFL_ID | int |  | N | NULL |
| OFL_OF_ID | int |  | N | NULL |
| OFL_P_ID | int |  | N | NULL |
| OFL_LOTE | varchar | 50 | Y | NULL |

### dbo.OF_MLD_EMPREGADOS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | Y | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| E_ENT_ID | int |  | Y | NULL |

### dbo.OF_OFTIPOUSO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFTU_ID | int |  | N | NULL |
| OFTU_NOME | nvarchar | -1 | N | NULL |

### dbo.OF_OF_TIPOUSO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFOFTU_ID | int |  | N | NULL |
| OFOFTU_OF_ID | int |  | N | NULL |
| OFOFTU_OFTU_ID | int |  | N | NULL |
| OFOFTU_DATAENTRADA | smalldatetime |  | Y | NULL |
| OFOFTU_DATASAIDA | smalldatetime |  | Y | NULL |
| OFOFTU_DATAPAGAMENTO | smalldatetime |  | Y | NULL |

### dbo.OF_PRODUTOS  (29 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| p_nome | nvarchar | -1 | N | NULL |
| P_TP_ID | int |  | Y | NULL |
| P_NP_ID | int |  | Y | NULL |
| P_M_ID | int |  | Y | NULL |
| P_TAM_ID | int |  | Y | NULL |
| P_P_ID | int |  | Y | NULL |
| P_PRECOCUSTO | float |  | N | NULL |
| P_PRECOVENDA | float |  | N | NULL |
| P_ID_CONST | int |  | Y | NULL |
| P_ID_LEME | int |  | Y | NULL |
| P_ID_LEME_QTD | float |  | Y | NULL |
| P_ID_FPES | int |  | Y | NULL |
| P_ID_FPES_QTD | float |  | Y | NULL |
| P_ID_FPESTR | int |  | Y | NULL |
| P_ID_FPESTR_QTD | float |  | Y | NULL |
| P_ID_STRAP | int |  | Y | NULL |
| P_ID_STRAP_QTD | float |  | Y | NULL |
| P_ID_BANCO | int |  | Y | NULL |
| P_ID_BANCO_QTD | float |  | Y | NULL |
| P_ID_CAPA | int |  | Y | NULL |
| P_ID_CAPA_QTD | int |  | N | NULL |
| P_ID_MATTPINTURA | int |  | Y | NULL |
| P_ID_MATTPINTURA_QTD | float |  | Y | NULL |
| P_ID_TAMPACINCO | int |  | Y | NULL |
| P_ID_TAMPACINCO_QTD | float |  | Y | NULL |
| P_ID_PN | int |  | Y | NULL |
| P_ID_PN_QTD | float |  | Y | NULL |
| p_descontinuado | int |  | N | NULL |

### dbo.OF_PRODUTOS_MLD  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_TP_ID | int |  | Y | NULL |
| P_NP_ID | int |  | Y | NULL |
| P_M_ID | int |  | Y | NULL |
| P_TAM_ID | int |  | Y | NULL |
| P_ID_CONST | int |  | Y | NULL |
| P_P_ID | int |  | Y | NULL |

### dbo.OF_PRODUTOS_V2  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| p_tp_id | int |  | Y | NULL |
| p_id | int |  | N | NULL |
| p_nome | nvarchar | -1 | N | NULL |
| p_l_id | int |  | Y | NULL |
| p_np_id | int |  | Y | NULL |
| p_m_id | int |  | Y | NULL |
| p_tam_id | int |  | Y | NULL |
| p_p_id | int |  | Y | NULL |
| p_id_const | int |  | Y | NULL |
| p_precocusto | float |  | N | NULL |
| p_precovenda | float |  | N | NULL |

### dbo.OF_PROPRIETARIO  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFPROP_OF_ID | int |  | N | NULL |
| OFPROP_E_ID | int |  | N | NULL |
| OFPROP_P_ID_BANCO | int |  | Y | NULL |
| OFPROP_BANCO_POSICAO | int |  | Y | NULL |
| OFPROP_BANCO_ALTURA | int |  | Y | NULL |
| OFPROP_P_ID_FPES | int |  | Y | NULL |
| OFPROP_FPES_POSICAO | int |  | Y | NULL |
| OFPROP_PAGAIA | nvarchar | -1 | Y | NULL |
| OFPROP_PAGAIA_COMPRIMENTO | nvarchar | -1 | Y | NULL |
| OFPROP_DATA | date |  | Y | NULL |
| OFPROP_P_ID_LEME | int |  | Y | NULL |

### dbo.OF_RENTAL_PROVAS  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFR_OF_ID | int |  | N | NULL |
| OFR_BOOKING_ID | int |  | N | NULL |
| OFR_DATA_ENTREGA | smalldatetime |  | Y | NULL |
| OFR_DATA_RECEBIDO | smalldatetime |  | Y | NULL |
| OFR_E_ID_ENTREGA | int |  | Y | NULL |
| OFR_E_ID_RECEBIDO | int |  | Y | NULL |
| OFR_BOOKING_NAME | nvarchar | -1 | N | NULL |
| OFR_BOOKING_NTEAM | nvarchar | -1 | N | NULL |
| OFR_BOOKING_VALOR | float |  | N | NULL |
| OFR_E_ID_ATRIBUI | int |  | Y | NULL |

### dbo.OF_TIPOUSO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFTU_ID | int |  | N | NULL |
| OFTU_NOME | nvarchar | -1 | N | NULL |
| OFTU_OBSERVACOES | nvarchar | -1 | Y | NULL |

### dbo.OF_VENDA  (37 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OFV_ID | int |  | N | NULL |
| OFV_DATA_SUBMETIDO | date |  | N | NULL |
| OFV_NOME | nvarchar | -1 | N | NULL |
| OFV_MORADA | nvarchar | -1 | N | NULL |
| OFV_PS_ID | int |  | N | NULL |
| OFV_EMAIL | nvarchar | -1 | N | NULL |
| OFV_TELEFONE | nvarchar | -1 | N | NULL |
| OFV_OF_ID | int |  | N | NULL |
| OFV_P_ID | int |  | Y | NULL |
| OFV_MODELO | nvarchar | -1 | N | NULL |
| OFV_ANO_FABRICO | int |  | N | NULL |
| OFV_DESCRICAO | nvarchar | -1 | N | NULL |
| OFV_DANIF_DECK | bit |  | N | NULL |
| OFV_DANIF_CASCO | bit |  | N | NULL |
| OFV_DANIF_INTERIOR | bit |  | N | NULL |
| OFV_DANIF_DESCRICAO | nvarchar | -1 | N | NULL |
| OFV_REPARADO | nvarchar | -1 | N | NULL |
| OFV_CUSTOMIZACOES | nvarchar | -1 | Y | NULL |
| OFV_BANCO | bit |  | N | NULL |
| OFV_FPES | bit |  | N | NULL |
| OFV_LEME | bit |  | N | NULL |
| OFV_PESOS | bit |  | N | NULL |
| OFV_CAPA | bit |  | N | NULL |
| OFV_FOTO_PERFIL | nvarchar | -1 | N | NULL |
| OFV_FOTO_DECK | nvarchar | -1 | N | NULL |
| OFV_FOTO_CASCO | nvarchar | -1 | N | NULL |
| OFV_FOTO_INTERIOR | nvarchar | -1 | N | NULL |
| OFV_FOTO_PROA | nvarchar | -1 | N | NULL |
| OFV_FOTO_RE | nvarchar | -1 | N | NULL |
| OFV_COMPRADO_NOVO | nvarchar | -1 | N | NULL |
| OFV_LOCALIZACAO_ACTUAL | nvarchar | -1 | N | NULL |
| OFV_PRECO_PEDIDO | float |  | N | NULL |
| OFV_PRECO_OFERECIDO | float |  | N | NULL |
| OFV_FP_ID | int |  | N | NULL |
| OFV_DATA_REVISAO | date |  | Y | NULL |
| OFV_NOTA_REVISAO | int |  | N | NULL |
| OFV_OBSERVACOES_REVISAO | nvarchar | -1 | N | NULL |

### dbo.ORCAMENTO  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| numero | char | 15 | Y | NULL |
| data_publica | datetime |  | N | NULL |
| taxa_iva | int |  | Y | NULL |
| isDealerPrice | tinyint |  | N | NULL |
| subtotal | decimal |  | N | NULL |
| transporte | decimal |  | N | NULL |
| total | decimal |  | N | NULL |
| ent_id | int |  | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.ORCAMENTO_PRODUTO  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| qtd | decimal |  | Y | NULL |
| desconto | decimal |  | N | NULL |
| orc_id | bigint |  | N | NULL |
| prod_id | bigint |  | N | NULL |
| preco | decimal |  | Y | NULL |
| subtotal | decimal |  | Y | NULL |

### dbo.ORDEMFABRICO  (111 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF_ID | int |  | N | NULL |
| OF_DATA | smalldatetime |  | N | NULL |
| OF_DATATRANSPORTE | smalldatetime |  | Y | NULL |
| OF_DATAENTREGA | smalldatetime |  | Y | NULL |
| OF_DATAPAGAMENTO | smalldatetime |  | Y | NULL |
| OF_DATAINICIO | smalldatetime |  | Y | NULL |
| OF_DATAFIM | smalldatetime |  | Y | NULL |
| OF_OBSERVACOES | nvarchar | -1 | Y | NULL |
| OF_PRECOCUSTO | float |  | N | NULL |
| OF_PRECOVENDA | float |  | N | NULL |
| OF_NOME | nvarchar | -1 | Y | NULL |
| OF_MORADAENTREGA | nvarchar | -1 | Y | NULL |
| OF_REFERENCIA | nvarchar | -1 | Y | NULL |
| OF_TELEFONE | nvarchar | -1 | Y | NULL |
| OF_EMAIL | nvarchar | -1 | Y | NULL |
| OF_TRANSPORTE | nvarchar | -1 | Y | NULL |
| OF_TRANSPORTEDOC | nvarchar | -1 | Y | NULL |
| OF_AUTOCOLANTE | nvarchar | -1 | N | NULL |
| OF_DESCONTO | float |  | N | NULL |
| OF_VALORPAGO | float |  | N | NULL |
| OF_COEFICIENTE | float |  | N | NULL |
| OF_PAGO | bit |  | N | NULL |
| OF_DECKPINTURA | bit |  | N | NULL |
| OF_CASCOPINTURA | bit |  | N | NULL |
| OF_SUPERVISAO | bit |  | N | NULL |
| OF_SUPERVISAOLAMINAGEM | bit |  | N | NULL |
| OF_SEQUENCIA | int |  | N | NULL |
| OF_OFTU_ID | int |  | Y | NULL |
| OF_TURN_ID | int |  | Y | NULL |
| OF_ENC_ID | int |  | Y | NULL |
| OF_P_ID | int |  | N | NULL |
| OF_E_ID | int |  | Y | NULL |
| OF_E_ID_ENC | int |  | Y | NULL |
| OF_P_ID_CDECK | int |  | Y | NULL |
| OF_P_ID_CCASCO | int |  | Y | NULL |
| OF_OF_ID_MLD | int |  | Y | NULL |
| OF_FP_ID | int |  | N | NULL |
| OF_TR_ID | int |  | Y | NULL |
| OF_MOLDE_ACESSORIO | bit |  | N | NULL |
| OF_CRIADOR | nvarchar | -1 | Y | NULL |
| OF_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| OF_DATAACTUALIZACAO | smalldatetime |  | Y | NULL |
| OF_P_ID_TOPO_FR | int |  | Y | NULL |
| OF_P_ID_TOPO_TR | int |  | Y | NULL |
| OF_P_ID_LATERAL_FR | int |  | Y | NULL |
| OF_P_ID_LATERAL_TR | int |  | Y | NULL |
| OF_P_ID_QUINAS | int |  | Y | NULL |
| OF_ARM_ID | int |  | N | NULL |
| OF_ARM_ID_LAM | int |  | N | NULL |
| OF_NUMUTIL | int |  | N | NULL |
| OF_CUSTOS_CACHE | float |  | Y | NULL |
| OF_TRANSP | bit |  | N | NULL |
| OF_FACT | nvarchar | -1 | Y | NULL |
| OF_SUPERVISAOPINTURA | bit |  | N | NULL |
| OF_P_ID_QUINAS_TR | int |  | Y | NULL |
| OF_P_ID_GOLA | int |  | Y | NULL |
| OF_DESCONTA_PESO | bit |  | N | NULL |
| OF_P_ID_HIST | nvarchar | -1 | Y | NULL |
| OF_REVISTO | bit |  | N | NULL |
| OF_PARAPINTARFORA | bit |  | N | NULL |
| OF_PREPREG | bit |  | N | NULL |
| OF_TR_ID_ULT | int |  | Y | NULL |
| OF_TR_DESC_ULT | nvarchar | -1 | Y | NULL |
| OF_TR_DATA_ULT | smalldatetime |  | Y | NULL |
| OF_PARAALTERAR | bit |  | N | NULL |
| OF_TR_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| OF_PLANO_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| OF_PLANO_TURNO_PREVISTO | int |  | Y | NULL |
| OF_P_ID_AUTOCOLANTE | int |  | Y | NULL |
| OF_TAG_ID | nvarchar | -1 | Y | NULL |
| OF_PRECOCUSTO_DT | float |  | N | NULL |
| OF_UPDT | bit |  | N | NULL |
| OF_ACERTO_RESINA | float |  | N | NULL |
| OF_SEQUENCIA_UPD | smalldatetime |  | Y | NULL |
| OF_PINT_CLASS | int |  | N | NULL |
| OF_PFORA_CLASS | int |  | N | NULL |
| OF_LINHAACAB | int |  | N | NULL |
| OF_ARM_FIXO | bit |  | N | NULL |
| OF_COEFICIENTE_EXTRA | float |  | N | NULL |
| OF_VERSAO_NOVA | bit |  | N | NULL |
| OF_EM_ID | int |  | Y | NULL |
| OF_EM_ID_FACTURACAO | int |  | Y | NULL |
| OF_OF_ID_MAE | int |  | Y | NULL |
| OF_MOV_ID | int |  | Y | NULL |
| OF_PROMO_CODE | nvarchar | -1 | Y | NULL |
| OF_DATA_PROMO_DEALER | date |  | Y | NULL |
| OF_DATA_PROMO_CLIENT | date |  | Y | NULL |
| OF_PESO_DECK | float |  | N | NULL |
| OF_PESO_CASCO | float |  | N | NULL |
| OF_FALTA_MASCARA | bit |  | N | NULL |
| OF_FALTA_DOCS_CLIENTE | bit |  | N | NULL |
| OF_PROMO_EMAIL | nvarchar | -1 | Y | NULL |
| OF_PRECOCUSTO_DT_INFLACIONADO | float |  | N | NULL |
| OF_FALTA_AUTOCOLANTE_NOME | bit |  | N | NULL |
| OF_FALTA_PROTECCAO_PAGAIA | bit |  | N | NULL |
| OF_FALTA_GARRAFA | bit |  | N | NULL |
| OF_FALTA_PARAFUSOS | bit |  | N | NULL |
| OF_FALTA_PESOS | bit |  | N | NULL |
| OF_FALTA_TRACTION_PADS | bit |  | N | NULL |
| OF_FALTA_FINCA_PES | bit |  | N | NULL |
| OF_FALTA_BANCO | bit |  | N | NULL |
| OF_FALTA_LEME | bit |  | N | NULL |
| OF_FALTA_CAPA | bit |  | N | NULL |
| OF_FALTA_TOALHA | bit |  | N | NULL |
| OF_RAL_MAIN | nvarchar | -1 | N | NULL |
| OF_RAL_SEC | nvarchar | -1 | N | NULL |
| OF_DUREZA_DECK | int |  | N | NULL |
| OF_DUREZA_CASCO | int |  | N | NULL |
| OF_DUREZA_PROA | int |  | N | NULL |
| OF_SENSOR_ID_VACUO | int |  | Y | NULL |
| OF_TAG_NFC | nvarchar | -1 | Y | NULL |

### dbo.PAISES  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PAISES_ID | int |  | N | NULL |
| PAISES_NOME | nvarchar | -1 | N | NULL |
| PAISES_COEFICIENTE_CO2 | float |  | N | NULL |

### dbo.PAISES_SITE  (20 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ID | int |  | N | NULL |
| NAME | nvarchar | -1 | Y | NULL |
| ISO2 | char | 2 | Y | NULL |
| ISO3 | char | 3 | Y | NULL |
| IANA | nvarchar | 10 | Y | NULL |
| IOC | char | 3 | Y | NULL |
| CURRENCY_CODE | nvarchar | 10 | Y | NULL |
| CURRENCY_NAME | nvarchar | 150 | Y | NULL |
| DISPLAY_NAME | nvarchar | 500 | Y | NULL |
| CAPITAL | nvarchar | 500 | Y | NULL |
| CONTINENT | char | 2 | Y | NULL |
| DIAL | varchar | 20 | Y | NULL |
| GEONAME | decimal |  | Y | NULL |
| INTERMEDIATE_REGION_CODE | int |  | Y | NULL |
| INTERMEDIATE_REGION_NAME | nvarchar | 250 | Y | NULL |
| LANGUAGES | varchar | 150 | Y | NULL |
| REGION_CODE | int |  | Y | NULL |
| REGION_NAME | nvarchar | 50 | Y | NULL |
| SUB_REGION_CODE | int |  | Y | NULL |
| SUB_REGION_NAME | nvarchar | 50 | Y | NULL |

### dbo.PEDIDOS  (18 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PED_ID | int |  | N | NULL |
| PED_DATA | smalldatetime |  | N | NULL |
| PED_E_ID_RESPONSAVEL | int |  | Y | NULL |
| PED_E_ID_APROVADOR | int |  | Y | NULL |
| PED_DATA_APROVADO | smalldatetime |  | Y | NULL |
| PED_APROVADO | bit |  | N | NULL |
| PED_EMAIL | nvarchar | -1 | Y | NULL |
| PED_CONTACTO | nvarchar | -1 | Y | NULL |
| PED_NOTAS | nvarchar | -1 | Y | NULL |
| PED_PT | bit |  | N | NULL |
| PED_E_ID | int |  | N | NULL |
| PED_OF_ID | int |  | Y | NULL |
| PED_SHOP_ORDER_ID | varchar | 50 | Y | NULL |
| PED_PRONTOPAGAMENTO | bit |  | N | NULL |
| PED_PAGO | bit |  | N | NULL |
| PED_PAGODATA | date |  | Y | NULL |
| PED_PAGAR | bit |  | N | NULL |
| PED_PRIORITARIO | bit |  | N | NULL |

### dbo.PLANEAMENTO_DIARIO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PlaneamentoDiarioId | int |  | N | NULL |
| Dia | date |  | N | NULL |
| HoraInicio | int |  | N | NULL |
| HoraFim | int |  | N | NULL |
| NumeroFuncionarios | int |  | N | NULL |
| TransporteId | int |  | Y | NULL |

### dbo.PLANO  (13 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PL_ID | int |  | N | NULL |
| PL_ANO | int |  | N | NULL |
| PL_SEMANA | int |  | N | NULL |
| PL_QTD | float |  | N | NULL |
| PL_E_ID | int |  | Y | NULL |
| PL_P_ID | int |  | N | NULL |
| PL_L_ID | int |  | N | NULL |
| PL_QTD_SOLDA | float |  | N | NULL |
| PL_QTD_MONTAGEM | float |  | N | NULL |
| PL_PRODF_ID | int |  | Y | NULL |
| PL_TEMPO | float |  | N | NULL |
| PL_COMPLETO | bit |  | N | NULL |
| PL_QTD_FEITA | float |  | N | NULL |

### dbo.PLANO_LAMINAGEM_LISTA_TURNOS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TURN_ID | int |  | Y | NULL |
| TURN_NOME | nvarchar | -1 | N | NULL |
| TURN_SEQUENCIA | int |  | Y | NULL |

### dbo.PONTOS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PONTOS_ID | int |  | N | NULL |
| PONTOS_MIN | float |  | N | NULL |
| PONTOS_MAX | float |  | N | NULL |
| PONTOS_PONTOS | int |  | N | NULL |

### dbo.PORTAO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PORTAO_ID | int |  | N | NULL |
| PORTAO_E_ID | int |  | N | NULL |
| PORTAO_DATA | smalldatetime |  | N | NULL |

### dbo.PROBS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROBS_ID | int |  | N | NULL |
| PROBS_DSCR | nvarchar | -1 | N | NULL |
| PROBS_PROBS_ID | int |  | Y | NULL |

### dbo.PROBS_CLASSIFICACAO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CL_ID | int |  | N | NULL |
| NOME | nvarchar | 50 | Y | NULL |
| ORDEM | int |  | Y | NULL |

### dbo.PROBS_LOCAL  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROBSL_ID | int |  | N | NULL |
| PROBSL_DSCR | nvarchar | -1 | N | NULL |

### dbo.PROB_CAUSA_SOL  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PCS_ID | int |  | N | NULL |
| PCS_DESCRICAO | nvarchar | -1 | N | NULL |
| PCS_DATACRIACAO | smalldatetime |  | N | NULL |
| PCS_CRIADOR | nvarchar | -1 | N | NULL |
| PCS_DATAACTUALIZACAO | smalldatetime |  | Y | NULL |
| PCS_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| PCS_TPPCS_ID | int |  | N | NULL |
| PCS_FP_ID | int |  | Y | NULL |

### dbo.PROB_CAUSA_SOL_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPPCS_ID | int |  | N | NULL |
| TPPCS_DESCRICAO | nvarchar | -1 | N | NULL |

### dbo.PROC_AREA  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROC_ID | int |  | N | NULL |
| PROC_NOME | nvarchar | -1 | N | NULL |
| PROC_DATA | smalldatetime |  | N | NULL |
| PROC_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| PROC_CLSP_ID_PERIOD | int |  | Y | NULL |
| PROC_CLSP_ID_IMPORT | int |  | Y | NULL |
| PROC_TPPROC_ID | int |  | N | NULL |
| PROC_PROC_ID | int |  | Y | NULL |

### dbo.PROC_AREA_ENT  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROCAE_ID | int |  | N | NULL |
| PROCAE_PROC_ID | int |  | Y | NULL |
| PROCAE_E_ID | int |  | N | NULL |
| PROCAE_PROCTPE_ID | int |  | N | NULL |
| PROCAE_PROCAF_ID | int |  | Y | NULL |

### dbo.PROC_AREA_FONTE  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROCAF_ID | int |  | N | NULL |
| PROCAF_PROC_ID | int |  | N | NULL |
| PROCAF_PROCFT_ID | int |  | Y | NULL |
| PROCAF_E_ID | int |  | N | NULL |
| PROCAF_PROCARQ_ID | int |  | Y | NULL |
| PROCAF_NOME | nvarchar | -1 | Y | NULL |
| PROCAF_DESCRICAO | nvarchar | -1 | Y | NULL |
| PROCAF_DATA | smalldatetime |  | N | NULL |
| PROCAF_DATA_ELIMINADO | smalldatetime |  | Y | NULL |

### dbo.PROC_ARQUIVO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROCARQ_ID | int |  | N | NULL |
| PROCARQ_NOME | nvarchar | -1 | N | NULL |

### dbo.PROC_CLASSIFIC  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CLSP_ID | int |  | N | NULL |
| CLSP_NOME | nvarchar | -1 | N | NULL |
| CLSP_CLSP_ID | int |  | Y | NULL |
| CLSP_SEQUENCIA | decimal |  | N | NULL |

### dbo.PROC_FONTE  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROCFT_ID | int |  | N | NULL |
| PROCFT_NOME | nvarchar | -1 | N | NULL |

### dbo.PROC_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPPROC_ID | int |  | N | NULL |
| TPPROC_NOME | nvarchar | -1 | Y | NULL |
| TPPROC_NIVEL | int |  | N | NULL |

### dbo.PROC_TIPO_ENT  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PROCTPE_ID | int |  | N | NULL |
| PROCTPE_NOME | nvarchar | -1 | N | NULL |

### dbo.PRODUTO  (121 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_NOME_EN | nvarchar | -1 | Y | NULL |
| P_DESCRICAO | nvarchar | -1 | Y | NULL |
| P_PRECOCUSTO | float |  | N | NULL |
| P_PRECOVENDA | float |  | N | NULL |
| P_COEFICIENTE | float |  | N | NULL |
| P_STOCK | float |  | N | NULL |
| P_STOCKMIN | float |  | N | NULL |
| P_NECESSIDADES | float |  | N | NULL |
| P_CONVESAO | float |  | N | NULL |
| P_MEDIDA | nvarchar | -1 | Y | NULL |
| P_PESOLAM | float |  | N | NULL |
| P_PESOACAB | float |  | N | NULL |
| P_MPLAMINAGEM | float |  | N | NULL |
| P_MODLAMINAGEM | float |  | N | NULL |
| P_MPACABAMENTO | float |  | N | NULL |
| P_MODACABAMENTO | float |  | N | NULL |
| P_QTDDECK | float |  | N | NULL |
| P_QTDCASCO | float |  | N | NULL |
| P_FABRICOINTERNO | bit |  | N | NULL |
| P_QTDENCOMENDA | float |  | N | NULL |
| P_DATACRIACAO | smalldatetime |  | Y | NULL |
| P_IMAGEM | nvarchar | -1 | Y | NULL |
| P_ACTIVO | bit |  | N | NULL |
| P_NP_ID | int |  | Y | NULL |
| P_TAM_ID | int |  | Y | NULL |
| P_TP_ID | int |  | Y | NULL |
| P_M_ID | int |  | Y | NULL |
| P_P_ID | int |  | Y | NULL |
| P_PCONT_ID | int |  | Y | NULL |
| P_E_ID | int |  | Y | NULL |
| P_PONTO_ENCOMENDA | int |  | N | NULL |
| P_UNI_ID | int |  | Y | NULL |
| P_LOJA | bit |  | N | NULL |
| P_DESCRICAO_TECNICA | nvarchar | -1 | Y | NULL |
| P_TEM_STOCK | bit |  | N | NULL |
| P_COD_PAUTAL | nvarchar | -1 | N | NULL |
| P_TEMPO_PREPARACAO | float |  | N | NULL |
| P_CRIADOR | nvarchar | -1 | Y | NULL |
| P_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| P_DATAACTUALIZACAO | smalldatetime |  | Y | NULL |
| P_TEMPO_SOLDA | float |  | N | NULL |
| P_TEMPO_MONTAGEM | float |  | N | NULL |
| P_QTDDECK_REAL | float |  | N | NULL |
| P_QTDCASCO_REAL | float |  | N | NULL |
| P_QTDDECK_REAL_TRANS | float |  | N | NULL |
| P_QTDCASCO_REAL_TRANS | float |  | N | NULL |
| P_PERC_TOPO_FR | float |  | N | NULL |
| P_PERC_TOPO_TR | float |  | N | NULL |
| P_PERC_LATERAL_FR | float |  | N | NULL |
| P_PERC_LATERAL_TR | float |  | N | NULL |
| P_PERC_QUINAS | float |  | N | NULL |
| P_PRECODEALER | float |  | N | NULL |
| P_FOLHA_ENC | bit |  | N | NULL |
| P_DESCONTINUADO | bit |  | N | NULL |
| P_CUSTO_CACHE | float |  | Y | NULL |
| P_PL_ID | int |  | Y | NULL |
| P_MODELO_COLORDESIGNER | varchar | 50 | Y | NULL |
| P_DESENVOLVIMENTO | bit |  | N | NULL |
| P_TP_ID_DISCIPLINA | int |  | Y | NULL |
| P_PECAS_CICLO | int |  | N | NULL |
| P_CICLO_2PX | bit |  | N | NULL |
| P_CICLO_TEMPO | float |  | N | NULL |
| P_CICLO_PRENSA | bit |  | N | NULL |
| P_QTD_MONTAGEM | int |  | N | NULL |
| P_SET_TOPOS | bit |  | N | NULL |
| P_SET_LATERAIS | bit |  | N | NULL |
| P_SET_QUINAS | bit |  | N | NULL |
| P_SET_CASCO | bit |  | N | NULL |
| P_TEMPO_ESPERA | int |  | N | NULL |
| P_SET_GOLA | bit |  | N | NULL |
| P_SET_RISCA | bit |  | N | NULL |
| P_PRECO_TEMP | float |  | N | NULL |
| P_QTD_TOPOS | float |  | N | NULL |
| P_QTD_QUINAS | float |  | N | NULL |
| P_QTD_LATERAIS | float |  | N | NULL |
| P_L_ID | int |  | Y | NULL |
| P_DIF_IDEAL_PA_D | float |  | N | NULL |
| P_DIF_IDEAL_PA_LX | float |  | N | NULL |
| P_DIF_IDEAL_LX_ACAB | float |  | N | NULL |
| P_MO | float |  | N | NULL |
| P_MP | float |  | N | NULL |
| P_MS | float |  | N | NULL |
| P_MERC | float |  | N | NULL |
| P_SERV | float |  | N | NULL |
| P_GGF | float |  | N | NULL |
| P_COMPRIMENTO | float |  | N | NULL |
| P_LARGURA | float |  | N | NULL |
| P_ALTURA | float |  | N | NULL |
| P_URL_IMG_PROD | nvarchar | -1 | Y | NULL |
| P_RESINA_MIX | bit |  | N | NULL |
| P_SAIDAS_AUTO | int |  | N | NULL |
| P_UNI_ID_MOVIMENTOS | int |  | Y | NULL |
| P_UNI_MOV_FACTOR | float |  | Y | NULL |
| P_PERC_QUINAS_TR | float |  | N | NULL |
| P_PERC_GOLA | float |  | N | NULL |
| P_STOCK_LINHA | bit |  | N | NULL |
| P_QTD_RESINA | float |  | N | NULL |
| P_REF_UNIV | nvarchar | -1 | Y | NULL |
| P_COLOR | nvarchar | -1 | Y | NULL |
| P_3D | nvarchar | -1 | Y | NULL |
| P_ARM_ID | int |  | Y | NULL |
| P_NCORES | int |  | N | NULL |
| P_GERA_OF | bit |  | N | NULL |
| P_ATRIB_ID_DESIGN | int |  | Y | NULL |
| P_EAN | decimal |  | Y | NULL |
| P_E_ID_RESP | int |  | Y | NULL |
| P_E_ID_CRIADOR | int |  | Y | NULL |
| P_DESCRICAO_EN | nvarchar | -1 | Y | NULL |
| P_PESOLAM_UPD | date |  | Y | NULL |
| P_PESOACAB_UPD | date |  | Y | NULL |
| P_QTDDECK_REAL_UPD | date |  | Y | NULL |
| P_QTDCASCO_REAL_UPD | date |  | Y | NULL |
| P_PRECOVENDA_INTERNACIONAL | float |  | N | NULL |
| P_NUM_CICLOS_DIA | int |  | N | NULL |
| P_CO2 | float |  | N | NULL |
| P_PRECO_TEMP_INFLACIONADO | float |  | N | NULL |
| P_CO2_DATA_ALTERADO | date |  | Y | NULL |
| P_CO2_OBSERVACOES | nvarchar | -1 | N | NULL |
| P_PESO_M2 | float |  | N | NULL |

### dbo.PRODUTO_ATTACH  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AT_ID | int |  | N | NULL |
| AT_NOME | nvarchar | -1 | N | NULL |
| AT_DESCRICAO | nvarchar | -1 | Y | NULL |
| AT_P_ID | int |  | Y | NULL |
| AT_IMAGE | nvarchar | -1 | N | NULL |
| AT_ATT_ID | int |  | Y | NULL |
| AT_EOBS_ID | int |  | Y | NULL |

### dbo.PRODUTO_ATTACH_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ATT_ID | int |  | N | NULL |
| ATT_DESC | nvarchar | -1 | N | NULL |

### dbo.PRODUTO_CAMADA  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CAM_ID | int |  | N | NULL |
| CAM_P_ID | int |  | N | NULL |
| CAM_TPCAM_ID | int |  | N | NULL |
| CAM_DESCRICAO | nvarchar | -1 | Y | NULL |
| CAM_SEQUENCIA | int |  | N | NULL |

### dbo.PRODUTO_CAMADA_TIPO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPCAM_ID | int |  | N | NULL |
| TPCAM_NOME | nvarchar | -1 | N | NULL |
| TPCAM_ORDEM | float |  | N | NULL |
| TPCAM_TPCAM_ID_PAI | int |  | Y | NULL |

### dbo.PRODUTO_COEFICIENTE  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PCOEF_ID | int |  | N | NULL |
| PCOEF_P_ID | int |  | N | NULL |
| PCOEF_DATA | smalldatetime |  | N | NULL |
| PCOEF_VALOR_HCOEF | float |  | N | NULL |
| PCOEF_ACTIVO | bit |  | N | NULL |
| PCOEF_VALOR_HORA | float |  | N | NULL |

### dbo.PRODUTO_COMPONENTE  (16 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| COMP_ID | int |  | N | NULL |
| COMP_P_ID | int |  | Y | NULL |
| COMP_P_P_ID | int |  | N | NULL |
| COMP_QUANTIDADE | float |  | N | NULL |
| COMP_TPCOMP_ID | int |  | N | NULL |
| COMP_OBS | nvarchar | -1 | Y | NULL |
| COMP_DATA_ALT | smalldatetime |  | Y | NULL |
| COMP_FASE_FINAL | bit |  | N | NULL |
| COMP_CONFIGURAVEL | bit |  | N | NULL |
| COMP_UNICO | bit |  | N | NULL |
| COMP_VALOR_EXTRA | bit |  | N | NULL |
| COMP_FP_ID | int |  | Y | NULL |
| COMP_ATRIB_ID | int |  | Y | NULL |
| COMP_L_ID | int |  | Y | NULL |
| COMP_ELIMINADO | smalldatetime |  | Y | NULL |
| COMP_GESTOR_MARCA | bit |  | N | NULL |

### dbo.PRODUTO_CONTABILIDADE_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PCONT_ID | int |  | N | NULL |
| PCONT_NOME | nvarchar | -1 | N | NULL |
| PCONT_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.PRODUTO_ENTIDADE  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PF_P_ID | int |  | N | NULL |
| PF_E_ID | int |  | N | NULL |
| PF_QTD_MIN_ENC | float |  | N | NULL |
| PF_PRECO | float |  | N | NULL |
| PF_OBSERVACOES | nvarchar | -1 | Y | NULL |
| PF_CODIGO | nvarchar | -1 | Y | NULL |
| PF_DESCRICAO | nvarchar | -1 | Y | NULL |
| PF_UNI_ID | int |  | Y | NULL |
| PF_CONVERSAO | float |  | N | NULL |

### dbo.PRODUTO_ESTADO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EST_ID | int |  | N | NULL |
| EST_NOME | nvarchar | -1 | N | NULL |
| EST_EST_ID | int |  | Y | NULL |

### dbo.PRODUTO_FASE  (19 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRODF_ID | int |  | N | NULL |
| PRODF_P_ID | int |  | Y | NULL |
| PRODF_FP_ID | int |  | Y | NULL |
| PRODF_DESCRICAO | nvarchar | -1 | Y | NULL |
| PRODF_SEQUENCIA | int |  | N | NULL |
| PRODF_TEMPO | float |  | N | NULL |
| PRODF_DATA | smalldatetime |  | N | NULL |
| PRODF_CRIADOR | nvarchar | -1 | N | NULL |
| PRODF_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| PRODF_DATAACTUALIZACAO | smalldatetime |  | Y | NULL |
| PRODF_PRODF_ID | int |  | Y | NULL |
| PRODF_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| PRODF_STOCK | float |  | N | NULL |
| PRODF_AUTOMATICA | bit |  | N | NULL |
| PRODF_FABRICO | bit |  | N | NULL |
| PRODF_COEFICIENTE | float |  | N | NULL |
| PRODF_TPCAM_ID | int |  | Y | NULL |
| PRODF_PLANEAMENTO | bit |  | N | NULL |
| PRODF_COEFICIENTE_X | float |  | N | NULL |

### dbo.PRODUTO_FASE_LINK  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRODFL_PRODF_ID_PROX | int |  | N | NULL |
| PRODFL_PRODF_ID_ANT | int |  | N | NULL |
| PRODFL_SEQUENCIA | int |  | N | NULL |

### dbo.PRODUTO_LISTA  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PL_ID | int |  | N | NULL |
| PL_DESCR | nvarchar | -1 | Y | NULL |
| PL_DATA | smalldatetime |  | N | NULL |
| PL_ACTIVO | bit |  | N | NULL |
| PL_FP_ID | int |  | Y | NULL |

### dbo.PRODUTO_LISTA_ITEMS  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PLI_ID | int |  | N | NULL |
| PLI_DESCR | nvarchar | -1 | N | NULL |
| PLI_PL_ID | int |  | N | NULL |
| PLI_SEQUENCIA | int |  | N | NULL |
| PLI_FP_ID | int |  | Y | NULL |
| PLI_FP_ID_CHK | int |  | N | NULL |
| PLI_CULPA_CHEFE | bit |  | N | NULL |
| PLI_MOLDE_REPARAR | bit |  | N | NULL |
| PLI_DESCR_EN | nvarchar | -1 | N | NULL |

### dbo.PRODUTO_MODELO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| M_ID | int |  | N | NULL |
| M_NOME | nvarchar | -1 | N | NULL |
| M_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.PRODUTO_NUMERO_POCOS  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| NP_ID | int |  | N | NULL |
| NP_NOME | nvarchar | -1 | N | NULL |
| NP_DESCRICAO | nvarchar | -1 | Y | NULL |
| NP_NUM | int |  | Y | NULL |

### dbo.PRODUTO_OPCOES  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| POP_P_ID | int |  | N | NULL |
| POP_P_P_ID | int |  | N | NULL |
| POP_CORES | bit |  | N | NULL |
| POP_TOPOS | bit |  | N | NULL |
| POP_LATERAIS | bit |  | N | NULL |
| POP_QUINAS | bit |  | N | NULL |
| POP_CASCO | bit |  | N | NULL |
| POP_GOLA | bit |  | N | NULL |
| POP_RISCA | bit |  | N | NULL |
| POP_EXTRA | bit |  | N | NULL |
| POP_CUSTO_EXTRA_OF | bit |  | N | NULL |

### dbo.PRODUTO_PROB_CAUSA_SOL  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PP_ID | int |  | N | NULL |
| PP_PCS_ID | int |  | N | NULL |
| PP_PCS_PCS_ID | int |  | Y | NULL |
| PP_DATA | smalldatetime |  | N | NULL |

### dbo.PRODUTO_TAMANHO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TAM_ID | int |  | N | NULL |
| TAM_NOME | nvarchar | -1 | N | NULL |
| TAM_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.PRODUTO_TIPO  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_ID | int |  | N | NULL |
| TP_NOME | nvarchar | -1 | N | NULL |
| TP_NOME_EN | nvarchar | -1 | N | NULL |
| TP_DESCRICAO | nvarchar | -1 | Y | NULL |
| TP_TP_ID | int |  | Y | NULL |
| TP_FP_ID | int |  | Y | NULL |
| TP_EDITAVEL | bit |  | N | NULL |
| TP_ENT_OWNER | int |  | Y | NULL |
| TP_ENT_OWNER_OBJ_OF | int |  | N | NULL |
| TP_ENT_OWNER_OBJ_VAL | float |  | N | NULL |
| TP_IMAGEM | nvarchar | 1024 | Y | NULL |

### dbo.PROVAS  (19 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRV_ID | int |  | N | NULL |
| PRV_NOME | nvarchar | -1 | N | NULL |
| PRV_DESCRICAO | nvarchar | -1 | N | NULL |
| PRV_PAIS_ID | int |  | N | NULL |
| PRV_CIDADE | nvarchar | -1 | N | NULL |
| PRV_DISCIPLINA | nvarchar | -1 | N | NULL |
| PRV_VALOR_BARCO | float |  | N | NULL |
| PRV_DATA_I | date |  | Y | NULL |
| PRV_DATA_F | date |  | Y | NULL |
| PRV_DATA_CHEGADA | date |  | Y | NULL |
| PRV_DATA_PARTIDA | date |  | Y | NULL |
| PRV_IMAGEM | nvarchar | -1 | Y | NULL |
| PRV_PUBLICO | bit |  | N | NULL |
| PRV_DATA_BOOKING | date |  | Y | NULL |
| PRV_DATA_BOOKING_F | date |  | Y | NULL |
| PRV_VALOR_BARCO_K2 | float |  | N | NULL |
| PRV_VALOR_BARCO_K4 | float |  | N | NULL |
| PRV_VALOR_PARACANOE | float |  | N | NULL |
| PRV_DATA_ELIMINADO | date |  | Y | NULL |

### dbo.PROVAS_BOOKING  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRVB_ID | int |  | N | NULL |
| PRVB_PRV_ID | int |  | N | NULL |
| PRVB_E_ID | int |  | N | NULL |
| PRVB_MODELO | nvarchar | -1 | N | NULL |
| PRVB_OF_ID | int |  | Y | NULL |
| PRVB_PBEST_ID | int |  | N | NULL |
| PRVB_EXTRAS | nvarchar | -1 | Y | NULL |
| PRVB_PRECO | decimal |  | N | NULL |
| PRVB_DATA_CHEGADA | date |  | Y | NULL |
| PRVB_ENTREGUE | bit |  | N | NULL |
| PRVB_RECEBIDO | bit |  | N | NULL |

### dbo.PROVAS_BOOKING_ESTADO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PBEST_ID | int |  | N | NULL |
| PBEST_NOME | nvarchar | -1 | N | NULL |

### dbo.PROVAS_FICHEIROS  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRVFX_ID | int |  | N | NULL |
| PRVFX_NOME | nvarchar | -1 | N | NULL |
| PRVFX_DESCRICAO | nvarchar | -1 | N | NULL |
| PRVFX_CAMINHO | nvarchar | -1 | Y | NULL |
| PRVFX_DATA | datetime |  | N | NULL |
| PRVFX_PRV_ID | int |  | N | NULL |
| PRVFX_E_ID | int |  | N | NULL |
| PRVFX_FACTURADO | bit |  | N | NULL |
| PRVFX_PAGO | bit |  | N | NULL |

### dbo.PROVAS_OF  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PRVOF_PRV_ID | int |  | N | NULL |
| PRVOF_OF_ID | int |  | N | NULL |
| PRVOF_PRECO | decimal |  | Y | NULL |

### dbo.PROVAS_PROVAS_BOOKING_ESTADO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| PBPEST_PEST_ID | int |  | N | NULL |
| PBPEST_PRVB_ID | int |  | N | NULL |
| PBPEST_DATA | date |  | N | NULL |

### dbo.ProdutoTipoAcessorio  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTipo | int |  | N | NULL |
| codProduto | int |  | N | NULL |

### dbo.Prova  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDProva | int |  | N | NULL |
| IDCompeticao | int |  | N | NULL |
| NomeProva | varchar | 150 | Y | NULL |
| Data | varchar | 20 | Y | NULL |
| Genero | varchar | 1 | Y | NULL |
| Tipologia | varchar | 5 | Y | NULL |
| Distancia | varchar | 45 | Y | NULL |
| Phase | varchar | 45 | Y | NULL |
| Filename | varchar | 500 | Y | NULL |

### dbo.PublicidadeAgentes  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codPub | int |  | N | NULL |
| titulo | varchar | 150 | Y | NULL |
| imagem | varchar | 150 | Y | NULL |
| link | varchar | 512 | Y | NULL |
| agentes | bit |  | Y | NULL |

### dbo.REPARACOES_PROVAS  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| REP_ID | int |  | N | NULL |
| REP_RECEBIDO | smalldatetime |  | N | NULL |
| REP_ENTREGA | smalldatetime |  | N | NULL |
| REP_ATLETA | nvarchar | -1 | N | NULL |
| REP_EQUIPA | nvarchar | -1 | N | NULL |
| REP_CONTACTO | nvarchar | -1 | N | NULL |
| REP_NOTAS | nvarchar | -1 | N | NULL |
| REP_E_ID_RESPONSAVEL | int |  | N | NULL |

### dbo.REP_OF_FP  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ROFFP_ID | int |  | N | NULL |
| ROFFP_REP_ID | int |  | N | NULL |
| ROFFP_FP_ID | int |  | N | NULL |
| ROFFP_OF_ID | int |  | Y | NULL |
| ROFFP_DATA_I | smalldatetime |  | Y | NULL |
| ROFFP_DATA_F | smalldatetime |  | Y | NULL |
| ROFFP_OBSERVACOES | nvarchar | -1 | N | NULL |
| ROFFP_PROBLEMAS | nvarchar | -1 | N | NULL |
| ROFFP_E_ID | int |  | Y | NULL |
| ROFFP_SEQUENCIA | int |  | N | NULL |

### dbo.RESINA_OFS  (23 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MOV_ID | int |  | N | NULL |
| MOV_DATA | smalldatetime |  | Y | NULL |
| MOV_DATASAIDA | smalldatetime |  | Y | NULL |
| MOV_QUANTIDADE | float |  | N | NULL |
| MOV_PRECOUNITARIO | float |  | N | NULL |
| MOV_PRECOVENDA | float |  | N | NULL |
| MOV_DESCONTO | float |  | N | NULL |
| MOV_OBSERVACOES | nvarchar | -1 | Y | NULL |
| MOV_PROBLEMA | nvarchar | -1 | Y | NULL |
| MOV_NUMUTIL | int |  | N | NULL |
| MOV_OF_ID | int |  | Y | NULL |
| MOV_E_ID | int |  | Y | NULL |
| MOV_P_ID | int |  | Y | NULL |
| MOV_TPMOV_ID | int |  | N | NULL |
| MOV_MOV_ID | int |  | Y | NULL |
| MOV_ARM_ID | int |  | Y | NULL |
| MOV_LM_ID | int |  | Y | NULL |
| MOV_SERVER | nvarchar | -1 | N | NULL |
| MOV_TR_ID | int |  | Y | NULL |
| MOV_PRODF_ID | int |  | Y | NULL |
| MOV_PL_ID | int |  | Y | NULL |
| MOV_QTD_BAL | float |  | N | NULL |
| MOV_DECK_PART | nvarchar | -1 | N | NULL |

### dbo.RH_DOC  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RHD_ID | int |  | N | NULL |
| RHD_TIPO_ID | int |  | Y | NULL |
| RHD_DATA_ALTERACAO | decimal |  | Y | NULL |
| RHD_TITULO | varchar | 250 | Y | NULL |
| RHD_FICHEIRO | varchar | 250 | Y | NULL |

### dbo.RH_FORMACAO  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RHF_ID | int |  | N | NULL |
| RHF_TITULO | varchar | 250 | Y | NULL |
| RHF_DESCRICAO | varchar | -1 | Y | NULL |
| RHF_DURACAO | varchar | 50 | Y | NULL |
| RHF_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| RHF_DATA_REALIZACAO | smalldatetime |  | Y | NULL |

### dbo.RH_PROBLEMA  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RHP_ID | int |  | N | NULL |
| RHP_IRREGULARIDADE | varchar | 4000 | Y | NULL |
| RHP_ACCAO | varchar | 4000 | Y | NULL |
| RHP_DATA_PREVISTA | smalldatetime |  | Y | NULL |
| RHP_DATA_RESOLUCAO | smalldatetime |  | Y | NULL |
| RHP_RESOLVIDO | bit |  | Y | NULL |

### dbo.RH_TIPO_DOC  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| RHTD_ID | int |  | N | NULL |
| RHTD_NOME | varchar | 50 | Y | NULL |

### dbo.Report_Table_20171114  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ﻿ID | varchar | 50 | Y | NULL |
| Date | varchar | 50 | Y | NULL |
| Temperatura  | varchar | 50 | Y | NULL |
| Humidade  | varchar | 50 | Y | NULL |

### dbo.RetornosFuncionario  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| Funcionario | int |  | Y | NULL |
| Fase | int |  | N | NULL |
| dataRep | smalldatetime |  | Y | NULL |
| rtns | int |  | Y | NULL |
| culpado | int |  | N | NULL |
| coefs | float |  | Y | NULL |

### dbo.SGIDI  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SGIDI_ID | int |  | N | NULL |
| SGIDI_DESCRICAO | nvarchar | -1 | N | NULL |
| SGIDI_DATA | smalldatetime |  | N | NULL |
| SGIDI_E_ID | int |  | N | NULL |
| SGIDI_SGIDITP_ID | int |  | N | NULL |
| SGIDI_SGIDI_ID | int |  | Y | NULL |
| SGIDI_IMAGEM | nvarchar | -1 | Y | NULL |

### dbo.SGIDI_FICHEIRO  (18 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SGIDIF_ID | int |  | N | NULL |
| SGIDIF_NOME | nvarchar | -1 | N | NULL |
| SGIDIF_DESCR | nvarchar | -1 | Y | NULL |
| SGIDIF_TIPO | nvarchar | -1 | N | NULL |
| SGIDIF_DATA | smalldatetime |  | N | NULL |
| SGIDIF_CRIADOR | int |  | N | NULL |
| SGIDIF_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| SGIDIF_ACTUALIZADOR | int |  | Y | NULL |
| SGIDIF_SGIDIP_ID | int |  | Y | NULL |
| SGIDIF_SGIDIF_ID | int |  | Y | NULL |
| SGIDIF_CAMINHO | nvarchar | -1 | N | NULL |
| SGIDIF_PROCAF_ID | int |  | Y | NULL |
| SGIDIF_PUBLICO | bit |  | N | NULL |
| SGIDIF_SGIDIFXCL_ID_TIPO | int |  | Y | NULL |
| SGIDIF_SGIDIFXCL_ID_TEMPO | int |  | Y | NULL |
| SGIDIF_SGIDIFXCL_ID_METODO | int |  | Y | NULL |
| SGIDIF_SGIDIFXCL_ID_REVISAO | int |  | Y | NULL |
| SGIDIF_E_ID | int |  | Y | NULL |

### dbo.SGIDI_FX_CLASSIFIC  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SGIDIFXCL_ID | int |  | N | NULL |
| SGIDIFXCL_DESCR | nvarchar | -1 | N | NULL |
| SGIDIFXCL_SEQUENCIA | int |  | N | NULL |
| SGIDIFXCL_SGIDIFXCL_ID | int |  | Y | NULL |

### dbo.SGIDI_PASTA  (13 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SGIDIP_ID | int |  | N | NULL |
| SGIDIP_NOME | nvarchar | -1 | N | NULL |
| SGIDIP_DESCR | nvarchar | -1 | Y | NULL |
| SGIDIP_DATA | smalldatetime |  | N | NULL |
| SGIDIP_CRIADOR | nvarchar | -1 | N | NULL |
| SGIDIP_DATA_ELIMINADO | smalldatetime |  | Y | NULL |
| SGIDIP_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| SGIDIP_SGIDIP_ID | int |  | Y | NULL |
| SGIDIP_SISTEMA | bit |  | N | NULL |
| SGIDIP_ID_ID | int |  | Y | NULL |
| SGIDIP_TR_ID | int |  | Y | NULL |
| SGIDIP_E_ID | int |  | Y | NULL |
| SGIDIP_PED_ID | int |  | Y | NULL |

### dbo.SGIDI_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| SGIDITP_ID | int |  | N | NULL |
| SGIDITP_DESCRICAO | nvarchar | -1 | N | NULL |

### dbo.SensoresLogin  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codLogin | int |  | N | NULL |
| username | varchar | 50 | Y | NULL |
| password | varchar | 50 | Y | NULL |
| activo | bit |  | N | NULL |

### dbo.SensoresLoginSessao  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codLogin | int |  | N | NULL |
| codTeste | int |  | N | NULL |

### dbo.SensoresPosicao  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codPosicao | int |  | N | NULL |
| aplicavel | varchar | 10 | Y | NULL |

### dbo.SensoresTeste  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTeste | int |  | N | NULL |
| atletas | varchar | 255 | Y | NULL |
| codBarco | int |  | Y | NULL |
| data | decimal |  | Y | NULL |
| obs | varchar | 8000 | Y | NULL |
| resumo | varchar | 8000 | Y | NULL |
| excel | varchar | 150 | Y | NULL |
| codPais | int |  | Y | NULL |
| distancia | varchar | 10 | Y | NULL |
| pitch | decimal |  | Y | NULL |
| roll | decimal |  | Y | NULL |

### dbo.SensoresTesteAtleta  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTeste | int |  | N | NULL |
| codAtleta | int |  | N | NULL |
| nome | varchar | 50 | Y | NULL |
| peso | int |  | Y | NULL |

### dbo.SensoresTesteSerie  (28 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTeste | int |  | N | NULL |
| codSerie | int |  | N | NULL |
| nome | varchar | 50 | Y | NULL |
| excel_original | varchar | 250 | Y | NULL |
| tempo_inicio | int |  | Y | NULL |
| tempo_fim | int |  | Y | NULL |
| excel_gerado | varchar | 250 | Y | NULL |
| csv_dartfish | varchar | 250 | Y | NULL |
| roll_average | decimal |  | Y | NULL |
| roll_amplitude | decimal |  | Y | NULL |
| bow | varchar | 5 | Y | NULL |
| pitch_left | decimal |  | Y | NULL |
| pitch_right | decimal |  | Y | NULL |
| tilt_pitch | decimal |  | Y | NULL |
| side | varchar | 8 | Y | NULL |
| tilt_amplitude | decimal |  | Y | NULL |
| heading_amplitude | decimal |  | Y | NULL |
| avg_accel | decimal |  | Y | NULL |
| avg_tp_rem | decimal |  | Y | NULL |
| rem_min | decimal |  | Y | NULL |
| avg_esq | decimal |  | Y | NULL |
| avg_dir | decimal |  | Y | NULL |
| video | varchar | 150 | Y | NULL |
| video_flv | varchar | 150 | Y | NULL |
| csv_original | varchar | 50 | Y | NULL |
| tipo_input | bit |  | Y | NULL |
| offset_pitch | decimal |  | Y | NULL |
| offset_roll | decimal |  | Y | NULL |

### dbo.SensoresTesteSeriePosicoes  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTeste | int |  | N | NULL |
| codAtleta | int |  | N | NULL |
| codSerie | int |  | N | NULL |
| banco | int |  | Y | NULL |
| altura | int |  | Y | NULL |
| finca_pes | int |  | Y | NULL |

### dbo.SensoresTesteSerieValores  (25 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTeste | int |  | N | NULL |
| codSerie | int |  | N | NULL |
| tempo | decimal |  | N | NULL |
| pitch | decimal |  | Y | NULL |
| roll | decimal |  | Y | NULL |
| heading | decimal |  | Y | NULL |
| acelx | decimal |  | Y | NULL |
| acely | decimal |  | Y | NULL |
| acelz | decimal |  | Y | NULL |
| medmax | decimal |  | Y | NULL |
| medmin | decimal |  | Y | NULL |
| maximos | decimal |  | Y | NULL |
| minimos | decimal |  | Y | NULL |
| med_mais_dvp | decimal |  | Y | NULL |
| med_menos_dvp | decimal |  | Y | NULL |
| roll_filtro | decimal |  | Y | NULL |
| max_roll | decimal |  | Y | NULL |
| min_roll | decimal |  | Y | NULL |
| max_heading | decimal |  | Y | NULL |
| min_heading | decimal |  | Y | NULL |
| heading_filtro | decimal |  | Y | NULL |
| max_acel | decimal |  | Y | NULL |
| tempo_rem | decimal |  | Y | NULL |
| acel_esq | decimal |  | Y | NULL |
| acel_dir | decimal |  | Y | NULL |

### dbo.SensoresTesteVideo  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| CodVideo | int |  | N | NULL |
| CodSessao | int |  | N | NULL |
| Titulo | varchar | 150 | Y | NULL |
| Video | varchar | 150 | Y | NULL |

### dbo.ShopCache  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codProduto | int |  | N | NULL |
| sku | varchar | 50 | Y | NULL |
| name | varchar | 250 | Y | NULL |
| status | int |  | Y | NULL |
| thumbnail | varchar | 150 | Y | NULL |
| url_path | varchar | 250 | Y | NULL |
| visibility | int |  | Y | NULL |

### dbo.TH  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TH_ID | int |  | N | NULL |
| TH_DATA | smalldatetime |  | N | NULL |
| TH_TEMP | float |  | N | NULL |
| TH_HUM | float |  | Y | NULL |
| TH_DATA_REG | smalldatetime |  | Y | NULL |
| TH_FASE | int |  | Y | NULL |
| TH_SONDA | int |  | N | NULL |
| TH_DATA_UPDT | smalldatetime |  | Y | NULL |

### dbo.TH_SCHED  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| THSCHED_ID | int |  | N | NULL |
| THSCHED_DESCR | nchar | 512 | Y | NULL |
| THSCHED_SUN | bit |  | N | NULL |
| THSCHED_MON | bit |  | N | NULL |
| THSCHED_TUE | bit |  | N | NULL |
| THSCHED_WED | bit |  | N | NULL |
| THSCHED_THU | bit |  | N | NULL |
| THSCHED_FRI | bit |  | N | NULL |
| THSCHED_SAT | bit |  | N | NULL |
| THSCHED_START | char | 10 | N | NULL |
| THSCHED_END | char | 10 | N | NULL |
| THSCHED_ACTIVE | bit |  | N | NULL |
| THSCHED_SONDA | int |  | N | NULL |
| THSCHED_MIN | int |  | Y | NULL |
| THSCHED_MAX | int |  | Y | NULL |

### dbo.TH_SONDA  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| THS_ID | int |  | N | NULL |
| THS_NOME | varchar | 150 | N | NULL |
| THS_ADDRESS | varchar | 50 | Y | NULL |
| THS_CHANNEL | int |  | Y | NULL |
| THS_ACTIVO | bit |  | Y | NULL |
| THS_ALARM_TS | bigint |  | Y | NULL |
| THS_CHART_FROM | nvarchar | 50 | Y | NULL |
| THS_CHART_UNTIL | nvarchar | 50 | Y | NULL |

### dbo.TRANSPORTE  (43 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TR_ID | int |  | N | NULL |
| TR_DEST_ID | int |  | Y | NULL |
| TR_TRTP_ID | int |  | Y | NULL |
| TR_E_ID | int |  | Y | NULL |
| TR_DATA_CRIACAO | smalldatetime |  | N | NULL |
| TR_DATA | date |  | Y | NULL |
| TR_DATA_REGRESSO | date |  | Y | NULL |
| TR_PAISES_ID | int |  | Y | NULL |
| TR_MORADA | nvarchar | -1 | N | NULL |
| TR_OBSERVACOES | nvarchar | -1 | N | NULL |
| TR_DESCRICAO | nvarchar | -1 | N | NULL |
| TR_TRANSPORTE_NOSSO | bit |  | N | NULL |
| TR_GOOGLE_NAO | bit |  | N | NULL |
| TR_CONTACTO_DESTINO | nvarchar | -1 | N | NULL |
| TR_TRACK_TIPO | nvarchar | -1 | Y | NULL |
| TR_TRACK_NR | nvarchar | -1 | Y | NULL |
| TR_DOCSENVIADOS | bit |  | Y | NULL |
| TR_PUBLICO | bit |  | N | NULL |
| TR_TRACK_LINK | nvarchar | -1 | Y | NULL |
| TR_CELESTE | nvarchar | -1 | Y | NULL |
| TR_DATA_ENTREGA_PREV | date |  | Y | NULL |
| TR_DATA_ENTREGA | date |  | Y | NULL |
| TR_TRACKER_DATA | date |  | Y | NULL |
| TR_TRACKER_ID | int |  | Y | NULL |
| TR_TRTP_ID_EMB | int |  | Y | NULL |
| TR_OPERADOR_CODIGO | int |  | Y | NULL |
| TR_PORTO_CODIGO | int |  | Y | NULL |
| TR_LATITUDE | decimal |  | Y | NULL |
| TR_LONGITUDE | decimal |  | Y | NULL |
| TR_COORD_ULT_UPD | datetime |  | Y | NULL |
| TR_ESTADO_COD | int |  | Y | NULL |
| TR_DATA_PREV_CHEG | decimal |  | Y | NULL |
| TR_HORA_PREV_CHEG | decimal |  | Y | NULL |
| TR_AUX_ORDER | int |  | Y | NULL |
| TR_LATITUDE_ORIG | decimal |  | Y | NULL |
| TR_LONGITUDE_ORIG | decimal |  | Y | NULL |
| TR_LATITUDE_DEST | decimal |  | Y | NULL |
| TR_LONGITUDE_DEST | decimal |  | Y | NULL |
| TR_VALOR_ESTIMADO | float |  | N | NULL |
| TR_OBS_CLIENTE | nvarchar | -1 | Y | NULL |
| TR_CO2 | float |  | N | NULL |
| TR_DISTANCIA | float |  | N | NULL |
| TR_QUARTOS | int |  | N | NULL |

### dbo.TRANSPORTE_VERIFICACAO  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRV_TR_ID | int |  | N | NULL |
| TRV_E_ID | int |  | N | NULL |
| TRV_RECEBIDO | smalldatetime |  | N | NULL |
| TRV_FEEDBACK | nvarchar | -1 | Y | NULL |

### dbo.TRANSP_DATAS  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRDT_ID | int |  | N | NULL |
| TRDT_TR_ID | int |  | N | NULL |
| TRDT_DATA_ACTUAL | date |  | N | NULL |
| TRDT_DATA_NOVA | date |  | N | NULL |
| TRDT_TRDTCL_ID | int |  | N | NULL |
| TRDT_OBSERVACOES | nvarchar | -1 | Y | NULL |
| TRDT_DATA_CRIACAO | smalldatetime |  | N | NULL |

### dbo.TRANSP_DATAS_CLASSIFICACAO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRDTCL_ID | int |  | N | NULL |
| TRDTCL_NOME | nvarchar | -1 | N | NULL |

### dbo.TRANSP_DESP  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRDESP_ID | int |  | N | NULL |
| TRDESP_TRDESPTP_ID | int |  | N | NULL |
| TRDESP_TR_ID | int |  | N | NULL |
| TRDESP_OBS | nvarchar | -1 | Y | NULL |
| TRDESP_QTD | int |  | N | NULL |
| TRDESP_VALOR | numeric |  | N | NULL |
| TRDESP_VALOR_ESTIMADO | numeric |  | N | NULL |

### dbo.TRANSP_DESP_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRDESPTP_ID | int |  | N | NULL |
| TRDESPTP_NOME | nvarchar | -1 | N | NULL |
| trdesptp_eliminado | smalldatetime |  | Y | NULL |

### dbo.TRANSP_DESTINO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DEST_ID | int |  | N | NULL |
| DEST_NOME | nvarchar | -1 | N | NULL |

### dbo.TRANSP_DOCS  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRDOC_DOCS_ID | int |  | N | NULL |
| TRDOC_TR_ID | int |  | N | NULL |
| TRDOC_DOCS_NOME | nvarchar | -1 | N | NULL |
| TRDOC_DOC_CAMINHO | nvarchar | -1 | Y | NULL |
| TRDOC_TRATADO | bit |  | N | NULL |
| TRDOC_OBSERVACOES | nvarchar | -1 | N | NULL |
| TRDOC_DOCNUM | nvarchar | -1 | N | NULL |
| TRDOC_DATA | smalldatetime |  | Y | NULL |

### dbo.TRANSP_DOCS_DEST_TIPO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DTD_DEST_ID | int |  | N | NULL |
| DTD_TRTP_ID | int |  | N | NULL |
| DTD_DOCS_ID | int |  | N | NULL |

### dbo.TRANSP_DOCS_STD  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| DOCS_ID | int |  | N | NULL |
| DOCS_NOME | nvarchar | -1 | N | NULL |
| DOCS_DESCRICAO | nvarchar | -1 | Y | NULL |

### dbo.TRANSP_ENTIDADE  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRE_ID | int |  | N | NULL |
| TRE_E_ID | int |  | N | NULL |
| TRE_TR_ID | int |  | N | NULL |
| TRE_DATA_IDA | smalldatetime |  | Y | NULL |
| TRE_DATA_VOLTA | smalldatetime |  | Y | NULL |
| TRE_VOO_IDA | nvarchar | -1 | Y | NULL |
| TRE_VOO_VOLTA | nvarchar | -1 | Y | NULL |
| TRE_IDA_CONF | bit |  | N | NULL |
| TRE_VOLTA_CONF | bit |  | N | NULL |
| TRE_NOITES | int |  | N | NULL |
| TRE_MARCADO | bit |  | N | NULL |
| TRE_PAGO | bit |  | N | NULL |
| TRE_TRTP_ID | int |  | Y | NULL |
| TRE_VALOR_ORCAMENTADO | float |  | N | NULL |
| TRE_VALOR_REAL | float |  | N | NULL |

### dbo.TRANSP_OF  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TROF_TR_ID | int |  | N | NULL |
| TROF_OF_ID | int |  | N | NULL |
| TROF_ENVIADO | bit |  | N | NULL |
| TROF_OBSERVACOES | nvarchar | -1 | Y | NULL |
| TROF_LEVA_PECAS | bit |  | N | NULL |
| TROF_DATA_CONFIRMACAO | date |  | Y | NULL |
| TROF_CONFIRMACAO_OBS | nvarchar | -1 | Y | NULL |
| TROF_DATA_CRIACAO | smalldatetime |  | N | NULL |
| TROF_COMPRIMENTO | float |  | N | NULL |
| TROF_LARGURA | float |  | N | NULL |
| TROF_ALTURA | float |  | N | NULL |

### dbo.TRANSP_OFS  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF | int |  | N | NULL |
| Modelo | nvarchar | -1 | N | NULL |
| Cores | nvarchar | -1 | Y | NULL |
| Estado | nvarchar | -1 | N | NULL |
| Cliente | nvarchar | -1 | N | NULL |
| TROF_TR_ID | int |  | N | NULL |

### dbo.TRANSP_SEMANA  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TR_ID | int |  | N | NULL |
| TR_DESCRICAO | nvarchar | -1 | N | NULL |

### dbo.TRANSP_TIPO  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRTP_ID | int |  | N | NULL |
| TRTP_NOME | nvarchar | -1 | N | NULL |
| TRTP_TRTP_ID | int |  | Y | NULL |
| TRTP_PESO_VOLUMETRICO | float |  | N | NULL |
| TRTP_APLICA_VOLUMETRICO | bit |  | N | NULL |
| TRTP_FACTOR_CO2 | float |  | N | NULL |
| TRTP_COMPRIMENTO | float |  | N | NULL |
| TRTP_LARGURA | float |  | N | NULL |
| TRTP_ALTURA | float |  | N | NULL |

### dbo.TRANSP_TRACKER  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRACKER_ID | int |  | N | NULL |
| TRACKER_NOME | nvarchar | -1 | N | NULL |
| TRACKER_ACTIVO | bit |  | N | NULL |

### dbo.TRANSP_VAL  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRVAL_VAL_ID | int |  | N | NULL |
| TRVAL_TR_ID | int |  | N | NULL |
| TRVAL_VALOR | float |  | N | NULL |

### dbo.TURNO  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TURN_ID | int |  | N | NULL |
| TURN_NOME | nvarchar | -1 | N | NULL |
| TURN_SEQUENCIA | int |  | N | NULL |

### dbo.Trackimo_Access  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codLog | int |  | N | NULL |
| date | datetime |  | Y | NULL |
| access_token | varchar | 500 | Y | NULL |
| refresh_token | varchar | 500 | Y | NULL |
| account_id | varchar | 200 | Y | NULL |

### dbo.Trackimo_Device  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| device_id | int |  | N | NULL |
| name | varchar | 200 | Y | NULL |
| lat | decimal |  | Y | NULL |
| lng | decimal |  | Y | NULL |
| time | int |  | Y | NULL |
| dataSync | datetime |  | Y | NULL |

### dbo.Trackimo_DeviceLocation  (14 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codHistorico | int |  | N | NULL |
| codEncomenda | int |  | Y | NULL |
| speed | int |  | Y | NULL |
| battery | int |  | Y | NULL |
| age | int |  | Y | NULL |
| gps | int |  | Y | NULL |
| location_id | int |  | Y | NULL |
| lat | decimal |  | Y | NULL |
| lng | decimal |  | Y | NULL |
| is_triangulated | int |  | Y | NULL |
| device_id | int |  | Y | NULL |
| time | int |  | Y | NULL |
| type | varchar | 10 | Y | NULL |
| dataObtencao | datetime |  | Y | NULL |

### dbo.TransporteDestino  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TRD_ID | int |  | N | NULL |
| TRD_TR_ID | int |  | N | NULL |
| TRD_E_ID | int |  | N | NULL |
| TRD_LATITUDE | decimal |  | N | NULL |
| TRD_LONGITUDE | decimal |  | N | NULL |
| TRD_CHEGOU | bit |  | N | NULL |
| TRD_DATACHEGADA | smalldatetime |  | Y | NULL |
| TRD_DATACONFIRMACAO | smalldatetime |  | Y | NULL |
| TRD_CONFIRMACAO_OBS | nvarchar | -1 | Y | NULL |

### dbo.TransporteLocalPesquisado  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| localPesquisado | varchar | 500 | N | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| lastSearch | datetime |  | Y | NULL |
| firstSearch | datetime |  | Y | NULL |

### dbo.TransporteLocalizacao  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomendaLocalizacao | int |  | N | NULL |
| codEncomenda | int |  | Y | NULL |
| dataEstado | datetime |  | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| codEncomendaPercurso | int |  | Y | NULL |
| ultUpdate | datetime |  | Y | NULL |

### dbo.TransporteNavio  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codBarco | int |  | N | NULL |
| nome | varchar | 50 | Y | NULL |
| url | varchar | 500 | Y | NULL |
| lastSearch | datetime |  | Y | NULL |
| firstSearch | datetime |  | Y | NULL |

### dbo.TransporteOperador  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codOperador | int |  | N | NULL |
| empresa | varchar | 50 | Y | NULL |
| ativo | bit |  | Y | NULL |

### dbo.TransportePercurso  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomendaPercurso | int |  | N | NULL |
| codEncomenda | int |  | Y | NULL |
| descricaoMov | varchar | 150 | Y | NULL |
| localizacao | varchar | 500 | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| transportador | varchar | 500 | Y | NULL |
| barco | bit |  | Y | NULL |
| numViagem | varchar | 50 | Y | NULL |
| data | decimal |  | N | NULL |
| hora | decimal |  | Y | NULL |
| efetivo | bit |  | Y | NULL |
| atual | bit |  | Y | NULL |
| auxOrder | int |  | Y | NULL |
| dataCriacao | datetime |  | Y | NULL |

### dbo.TransportePercursoHistorico  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomendaPercursoHistorico | int |  | N | NULL |
| codEncomenda | int |  | Y | NULL |
| data | datetime |  | Y | NULL |

### dbo.TransportePercursoHistoricoDetalhe  (15 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codEncomendaPercursoHistoricoDetalhe | int |  | N | NULL |
| codEncomendaPercursoHistorico | int |  | Y | NULL |
| codEncomendaPercurso | int |  | N | NULL |
| codEncomenda | int |  | Y | NULL |
| descricaoMov | varchar | 150 | Y | NULL |
| localizacao | varchar | 500 | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| transportador | varchar | 500 | Y | NULL |
| barco | bit |  | Y | NULL |
| numViagem | varchar | 50 | Y | NULL |
| data | decimal |  | N | NULL |
| hora | decimal |  | Y | NULL |
| efetivo | bit |  | Y | NULL |
| atual | bit |  | Y | NULL |

### dbo.TransportePorto  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codPorto | int |  | N | NULL |
| name | varchar | 50 | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| countryCode | varchar | 50 | Y | NULL |
| country | varchar | 50 | Y | NULL |

### dbo.TransporteSP  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTransporte | int |  | N | NULL |
| dataPartida | varchar | 50 | Y | NULL |
| tipoTransporte | varchar | 50 | Y | NULL |
| codOperador | int |  | Y | NULL |
| codPorto | int |  | Y | NULL |
| moradaDestino | varchar | 5000 | Y | NULL |
| latitude | float |  | Y | NULL |
| longitude | float |  | Y | NULL |
| refTipo | varchar | 50 | Y | NULL |
| referencia | varchar | 50 | Y | NULL |
| idTracker | int |  | Y | NULL |

### dbo.TransporteTmp_Percurso  (14 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codSeq | int |  | N | NULL |
| descricaoMov | varchar | 150 | Y | NULL |
| localizacao | varchar | 500 | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| transportador | varchar | 500 | Y | NULL |
| barco | bit |  | Y | NULL |
| numViagem | varchar | 50 | Y | NULL |
| data | decimal |  | Y | NULL |
| hora | decimal |  | Y | NULL |
| codEncomenda | int |  | Y | NULL |
| efetivo | bit |  | Y | NULL |
| atual | bit |  | Y | NULL |
| auxOrder | int |  | Y | NULL |

### dbo.UNIDADE  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| UNI_ID | int |  | N | NULL |
| UNI_NOME | nvarchar | 50 | N | NULL |

### dbo.USERS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| USE_ID | nvarchar | 50 | N | NULL |
| USE_PASSWORD | nvarchar | -1 | N | NULL |
| USE_TIPO | int |  | N | NULL |

### dbo.VALOR  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| VAL_ID | int |  | N | NULL |
| VAL_NOME | nvarchar | -1 | N | NULL |
| VAL_TPVAL_ID | int |  | N | NULL |

### dbo.VALOR_TIPO  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TPVAL_ID | int |  | N | NULL |
| TPVAL_NOME | nvarchar | -1 | N | NULL |

### dbo.VARIAVEIS  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| VAR_ID | int |  | N | NULL |
| VAR_DESCRICAO | nvarchar | -1 | N | NULL |
| VAR_VALOR | nvarchar | -1 | N | NULL |

### dbo.Velocidade  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| IDVelocidade | int |  | N | NULL |
| AtletaProvaID | int |  | N | NULL |
| Distancia | varchar | 10 | Y | NULL |
| Tempo | varchar | 10 | Y | NULL |
| Remadas | varchar | 10 | Y | NULL |
| velocidade | varchar | 10 | Y | NULL |

### dbo.VendaLoja  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| venda_id | int |  | N | NULL |
| v_data | decimal |  | Y | NULL |
| v_nome | varchar | 250 | Y | NULL |
| v_cliente | int |  | Y | NULL |
| v_despesa | bit |  | N | NULL |
| v_user | int |  | Y | NULL |

### dbo.VendaLojaProduto  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| venda_id | int |  | N | NULL |
| p_id | int |  | N | NULL |
| vp_qtd | int |  | Y | NULL |
| vp_mov_id | int |  | Y | NULL |
| tipo | int |  | Y | NULL |
| preco_venda | decimal |  | Y | NULL |
| obs | varchar | 2000 | Y | NULL |

### dbo.ZONA_GEOGRAFICA  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| ZG_ID | int |  | N | NULL |
| ZG_NOME | nvarchar | -1 | N | NULL |

### dbo.Z_PrevisaoPlano  (12 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF | int |  | N | NULL |
| Modelo | nvarchar | -1 | N | NULL |
| Cliente | nvarchar | -1 | N | NULL |
| Referencia | nvarchar | -1 | Y | NULL |
| Dia | int |  | N | NULL |
| Laminador | int |  | N | NULL |
| Turno | int |  | N | NULL |
| Molde | int |  | N | NULL |
| Dt_Trans | smalldatetime |  | N | NULL |
| Dt_Lam | smalldatetime |  | N | NULL |
| Dif | int |  | N | NULL |
| Cliente_id | int |  | Y | NULL |

### dbo.auxAnexos  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| aux_id | int |  | Y | NULL |
| titulo | varchar | 250 | Y | NULL |
| attach | varchar | 150 | Y | NULL |

### dbo.auxOrdemFabrico  (30 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| modelo | int |  | Y | NULL |
| cdeck | int |  | Y | NULL |
| ccasco | int |  | Y | NULL |
| banco_frente | int |  | Y | NULL |
| banco_tras | int |  | Y | NULL |
| fincapes_frente | int |  | Y | NULL |
| fincapes_back | int |  | Y | NULL |
| strap_frente | int |  | Y | NULL |
| strap_tras | int |  | Y | NULL |
| leme | int |  | Y | NULL |
| ref | varchar | 2000 | Y | NULL |
| obs | nvarchar | -1 | Y | NULL |
| of_id | int |  | Y | NULL |
| nBarcos | int |  | Y | NULL |
| codAgente | int |  | Y | NULL |
| cor_topo_fr | int |  | Y | NULL |
| cor_topo_tr | int |  | Y | NULL |
| cor_lateral_fr | int |  | Y | NULL |
| cor_lateral_tr | int |  | Y | NULL |
| cor_quinas | int |  | Y | NULL |
| cor_quinas_tr | int |  | Y | NULL |
| cor_gola | int |  | Y | NULL |
| color_designer | varchar | 250 | Y | NULL |
| cor_risca | int |  | Y | NULL |
| interior | int |  | Y | NULL |
| tampa_leme | int |  | Y | NULL |
| porta_numeros | int |  | Y | NULL |
| invoice | varchar | 2000 | Y | NULL |
| preco_venda | float |  | Y | NULL |

### dbo.aux_ValoresProd  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| tpId | int |  | Y | NULL |
| pId | int |  | Y | NULL |
| fpId | int |  | Y | NULL |
| seq | int |  | Y | NULL |
| valor | float |  | N | NULL |
| prodfId | int |  | Y | NULL |
| prodfCoefAct | float |  | Y | NULL |
| novoCoef | float |  | Y | NULL |

### dbo.aux_ValoresProducao  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| FaseId | int |  | Y | NULL |
| Pocos | nvarchar | -1 | Y | NULL |
| Tipo | nvarchar | -1 | Y | NULL |
| Palavras | nvarchar | -1 | Y | NULL |
| Retorno | bit |  | Y | NULL |
| Valor | float |  | N | NULL |

### dbo.country-codes2  (20 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| official_name_en | varchar | 52 | Y | NULL |
| ISO3166-1-Alpha-2 | varchar | 2 | Y | NULL |
| ISO3166-1-Alpha-3 | varchar | 3 | Y | NULL |
| ISO4217-currency_alphabetic_code | varchar | 7 | Y | NULL |
| ISO4217-currency_name | varchar | 29 | Y | NULL |
| CLDR display name | varchar | 50 | Y | NULL |
| Capital | varchar | 20 | Y | NULL |
| Continent | varchar | 2 | Y | NULL |
| Dial | varchar | 17 | Y | NULL |
| Geoname ID | int |  | Y | NULL |
| IOC | varchar | 3 | Y | NULL |
| Intermediate Region Code | smallint |  | Y | NULL |
| Intermediate Region Name | varchar | 15 | Y | NULL |
| Languages | varchar | 88 | Y | NULL |
| Region Code | smallint |  | Y | NULL |
| Region Name | varchar | 8 | Y | NULL |
| Sub-region Code | smallint |  | Y | NULL |
| Sub-region Name | varchar | 31 | Y | NULL |
| TLD | varchar | 3 | Y | NULL |
| IVA_Loja | bit |  | Y | NULL |

### dbo.exports  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| completed_at | datetime |  | Y | NULL |
| file_disk | nvarchar | 255 | N | NULL |
| file_name | nvarchar | 255 | Y | NULL |
| exporter | nvarchar | 255 | N | NULL |
| processed_rows | int |  | N | NULL |
| total_rows | int |  | N | NULL |
| successful_rows | int |  | N | NULL |
| user_id | int |  | N | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.failed_import_rows  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| data | nvarchar | -1 | N | NULL |
| import_id | bigint |  | N | NULL |
| validation_error | nvarchar | -1 | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.failed_jobs  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| uuid | nvarchar | 255 | N | NULL |
| connection | nvarchar | -1 | N | NULL |
| queue | nvarchar | -1 | N | NULL |
| payload | nvarchar | -1 | N | NULL |
| exception | nvarchar | -1 | N | NULL |
| failed_at | datetime |  | N | NULL |

### dbo.imports  (11 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| completed_at | datetime |  | Y | NULL |
| file_name | nvarchar | 255 | N | NULL |
| file_path | nvarchar | 255 | N | NULL |
| importer | nvarchar | 255 | N | NULL |
| processed_rows | int |  | N | NULL |
| total_rows | int |  | N | NULL |
| successful_rows | int |  | N | NULL |
| user_id | int |  | N | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.job_batches  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | nvarchar | 255 | N | NULL |
| name | nvarchar | 255 | N | NULL |
| total_jobs | int |  | N | NULL |
| pending_jobs | int |  | N | NULL |
| failed_jobs | int |  | N | NULL |
| failed_job_ids | nvarchar | -1 | N | NULL |
| options | nvarchar | -1 | Y | NULL |
| cancelled_at | int |  | Y | NULL |
| created_at | int |  | N | NULL |
| finished_at | int |  | Y | NULL |

### dbo.logs_web  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codLog | int |  | N | NULL |
| codLogin | int |  | Y | NULL |
| accao | varchar | 50 | Y | NULL |
| descricao | varchar | 100 | Y | NULL |
| IP | varchar | 50 | Y | NULL |
| data | datetime |  | Y | NULL |

### dbo.migrations  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| migration | nvarchar | 255 | N | NULL |
| batch | int |  | N | NULL |

### dbo.noticias_agentes  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| insider_id | int |  | N | NULL |
| titulo | varchar | 250 | Y | NULL |
| texto | varchar | 4000 | Y | NULL |
| data | decimal |  | Y | NULL |

### dbo.notifications  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | uniqueidentifier |  | N | NULL |
| type | nvarchar | 255 | N | NULL |
| notifiable_type | nvarchar | 255 | N | NULL |
| notifiable_id | bigint |  | N | NULL |
| data | nvarchar | -1 | N | NULL |
| read_at | datetime |  | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.of_Fases_ord  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| ofId | int |  | N | NULL |
| fpId | int |  | N | NULL |
| dtF | smalldatetime |  | Y | NULL |
| x | bigint |  | Y | NULL |

### dbo.of_Retornos_Estacionados  (7 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| Cliente | nvarchar | -1 | N | NULL |
| OF | int |  | N | NULL |
| Modelo | nvarchar | -1 | N | NULL |
| Fase | nvarchar | -1 | N | NULL |
| FaseSeq | int |  | N | NULL |
| Responsavel | nvarchar | -1 | N | NULL |
| Minutos | int |  | Y | NULL |

### dbo.personal_access_tokens  (10 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| tokenable_type | nvarchar | 255 | N | NULL |
| tokenable_id | bigint |  | N | NULL |
| name | nvarchar | 255 | N | NULL |
| token | nvarchar | 64 | N | NULL |
| abilities | nvarchar | -1 | Y | NULL |
| last_used_at | datetime |  | Y | NULL |
| expires_at | datetime |  | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.produto_stocks_por_armazem  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| Armazem_Id | int |  | Y | NULL |
| Armazem | nvarchar | -1 | Y | NULL |
| Stock | float |  | Y | NULL |

### dbo.rfid_cache  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| tag | nvarchar | 255 | N | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |
| deleted_at | datetime |  | Y | NULL |
| of_id | int |  | Y | NULL |

### dbo.shop_order_item  (22 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| entity_id | numeric |  | Y | NULL |
| increment_id | varchar | 32 | Y | NULL |
| status | varchar | 32 | Y | NULL |
| shipping_description | varchar | 255 | Y | NULL |
| shipping_method | varchar | 120 | Y | NULL |
| customer_id | numeric |  | Y | NULL |
| customer_firstname | varchar | 128 | Y | NULL |
| customer_lastname | varchar | 128 | Y | NULL |
| store_name | varchar | 32 | Y | NULL |
| created_at | datetime2 |  | Y | NULL |
| updated_at | datetime2 |  | Y | NULL |
| item_id | numeric |  | Y | NULL |
| created_at_item | datetime2 |  | Y | NULL |
| updated_at_item | datetime2 |  | Y | NULL |
| order_id | numeric |  | N | NULL |
| product_type | varchar | 255 | Y | NULL |
| sku | varchar | 255 | Y | NULL |
| name | varchar | 255 | Y | NULL |
| qty_ordered | numeric |  | Y | NULL |
| qty_shipped | numeric |  | Y | NULL |
| qty_invoiced | numeric |  | Y | NULL |
| price | numeric |  | N | NULL |

### dbo.sysdiagrams  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| name | nvarchar | 128 | N | NULL |
| principal_id | int |  | N | NULL |
| diagram_id | int |  | N | NULL |
| version | int |  | Y | NULL |
| definition | varbinary | -1 | Y | NULL |

### dbo.telescope_entries  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| sequence | bigint |  | N | NULL |
| uuid | uniqueidentifier |  | N | NULL |
| batch_id | uniqueidentifier |  | N | NULL |
| family_hash | nvarchar | 255 | Y | NULL |
| should_display_on_index | bit |  | N | NULL |
| type | nvarchar | 20 | N | NULL |
| content | nvarchar | -1 | N | NULL |
| created_at | datetime |  | Y | NULL |

### dbo.telescope_entries_tags  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| entry_uuid | uniqueidentifier |  | N | NULL |
| tag | nvarchar | 255 | N | NULL |

### dbo.telescope_monitoring  (1 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| tag | nvarchar | 255 | N | NULL |

### dbo.testes  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | int |  | N | NULL |
| dddd | datetime |  | Y | NULL |

### dbo.users_laravel  (8 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | bigint |  | N | NULL |
| name | nvarchar | 255 | N | NULL |
| email | nvarchar | 255 | N | NULL |
| email_verified_at | datetime |  | Y | NULL |
| password | nvarchar | 255 | N | NULL |
| remember_token | nvarchar | 100 | Y | NULL |
| created_at | datetime |  | Y | NULL |
| updated_at | datetime |  | Y | NULL |

### dbo.vAgente_Facturacao_Epoca_Actual  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AF_E_ID | int |  | N | NULL |
| valor_epoca | numeric |  | Y | NULL |

### dbo.vAgente_Faturacao  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| AF_E_ID | int |  | N | NULL |
| AF_ANO | int |  | Y | NULL |
| AF_TRIMESTRE | int |  | Y | NULL |
| AF_VALOR | numeric |  | Y | NULL |

### dbo.vCores  (4 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | Y | NULL |
| P_TP_ID | int |  | Y | NULL |
| ordenacao | int |  | N | NULL |

### dbo.vCoresAutocolante  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| id | varchar | 15 | N | NULL |
| cor | varchar | 11 | N | NULL |

### dbo.vModelosSite  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |

### dbo.vMovsPowerHouseNotShop  (40 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MOV_ID | int |  | N | NULL |
| MOV_DATA | smalldatetime |  | Y | NULL |
| MOV_DATASAIDA | smalldatetime |  | Y | NULL |
| MOV_QUANTIDADE | float |  | N | NULL |
| MOV_PRECOUNITARIO | float |  | N | NULL |
| MOV_PRECOVENDA | float |  | N | NULL |
| MOV_DESCONTO | float |  | N | NULL |
| MOV_OBSERVACOES | nvarchar | -1 | Y | NULL |
| MOV_PROBLEMA | nvarchar | -1 | Y | NULL |
| MOV_NUMUTIL | int |  | N | NULL |
| MOV_OF_ID | int |  | Y | NULL |
| MOV_E_ID | int |  | Y | NULL |
| MOV_P_ID | int |  | Y | NULL |
| MOV_TPMOV_ID | int |  | N | NULL |
| MOV_MOV_ID | int |  | Y | NULL |
| MOV_ARM_ID | int |  | Y | NULL |
| MOV_LM_ID | int |  | Y | NULL |
| MOV_SERVER | nvarchar | -1 | N | NULL |
| MOV_TR_ID | int |  | Y | NULL |
| MOV_PRODF_ID | int |  | Y | NULL |
| MOV_PL_ID | int |  | Y | NULL |
| MOV_QTD_BAL | float |  | N | NULL |
| MOV_DECK_PART | nvarchar | -1 | N | NULL |
| MOV_LOTE | nvarchar | -1 | Y | NULL |
| MOV_ACERTO | bit |  | N | NULL |
| MOV_ACESSORIO_ADICIONAL | bit |  | N | NULL |
| MOV_DEFEITUOSO | bit |  | N | NULL |
| MOV_SATISFEITO | bit |  | N | NULL |
| MOV_ID_PEDIDO | int |  | Y | NULL |
| MOV_ATRIB_ID | int |  | Y | NULL |
| MOV_SHOP_ORDER_ID | varchar | 50 | Y | NULL |
| MOV_SHOP_ORDER_ITEM_ID | int |  | Y | NULL |
| MOV_SHOP_UPDATED_AT | smalldatetime |  | Y | NULL |
| MOV_E_ID_RESPONSAVEL | int |  | Y | NULL |
| MOV_SHOP_SHIPPING | nvarchar | -1 | Y | NULL |
| MOV_SHOP_ENTITY_ID | int |  | Y | NULL |
| MOV_DATA_APROVADO | smalldatetime |  | Y | NULL |
| MOV_E_ID_APROVA | int |  | Y | NULL |
| MOV_ENVIA_ANEXO | bit |  | N | NULL |
| MOV_FP_ID | int |  | Y | NULL |

### dbo.vOF_Transporte  (67 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| OF_ID | int |  | N | NULL |
| OF_DATA | smalldatetime |  | N | NULL |
| OF_DATATRANSPORTE | smalldatetime |  | Y | NULL |
| OF_DATAENTREGA | smalldatetime |  | Y | NULL |
| OF_DATAPAGAMENTO | smalldatetime |  | Y | NULL |
| OF_DATAINICIO | smalldatetime |  | Y | NULL |
| OF_DATAFIM | smalldatetime |  | Y | NULL |
| OF_OBSERVACOES | nvarchar | -1 | Y | NULL |
| OF_PRECOCUSTO | float |  | N | NULL |
| OF_PRECOVENDA | float |  | N | NULL |
| OF_NOME | nvarchar | -1 | Y | NULL |
| OF_MORADAENTREGA | nvarchar | -1 | Y | NULL |
| OF_REFERENCIA | nvarchar | -1 | Y | NULL |
| OF_TELEFONE | nvarchar | -1 | Y | NULL |
| OF_EMAIL | nvarchar | -1 | Y | NULL |
| OF_TRANSPORTE | nvarchar | -1 | Y | NULL |
| OF_TRANSPORTEDOC | nvarchar | -1 | Y | NULL |
| OF_AUTOCOLANTE | nvarchar | -1 | N | NULL |
| OF_DESCONTO | float |  | N | NULL |
| OF_VALORPAGO | float |  | N | NULL |
| OF_COEFICIENTE | float |  | N | NULL |
| OF_PAGO | bit |  | N | NULL |
| OF_DECKPINTURA | bit |  | N | NULL |
| OF_CASCOPINTURA | bit |  | N | NULL |
| OF_SUPERVISAO | bit |  | N | NULL |
| OF_SUPERVISAOLAMINAGEM | bit |  | N | NULL |
| OF_SEQUENCIA | int |  | N | NULL |
| OF_OFTU_ID | int |  | Y | NULL |
| OF_TURN_ID | int |  | Y | NULL |
| OF_ENC_ID | int |  | Y | NULL |
| OF_P_ID | int |  | N | NULL |
| OF_E_ID | int |  | Y | NULL |
| OF_E_ID_ENC | int |  | Y | NULL |
| OF_P_ID_CDECK | int |  | Y | NULL |
| OF_P_ID_CCASCO | int |  | Y | NULL |
| OF_OF_ID_MLD | int |  | Y | NULL |
| OF_FP_ID | int |  | N | NULL |
| OF_TR_ID | int |  | Y | NULL |
| OF_MOLDE_ACESSORIO | bit |  | N | NULL |
| OF_CRIADOR | nvarchar | -1 | Y | NULL |
| OF_ACTUALIZADOR | nvarchar | -1 | Y | NULL |
| OF_DATAACTUALIZACAO | smalldatetime |  | Y | NULL |
| OF_P_ID_TOPO_FR | int |  | Y | NULL |
| OF_P_ID_TOPO_TR | int |  | Y | NULL |
| OF_P_ID_LATERAL_FR | int |  | Y | NULL |
| OF_P_ID_LATERAL_TR | int |  | Y | NULL |
| OF_P_ID_QUINAS | int |  | Y | NULL |
| OF_ARM_ID | int |  | N | NULL |
| OF_ARM_ID_LAM | int |  | N | NULL |
| OF_NUMUTIL | int |  | N | NULL |
| OF_CUSTOS_CACHE | float |  | Y | NULL |
| TR_ID | int |  | Y | NULL |
| TR_DEST_ID | int |  | Y | NULL |
| TR_TRTP_ID | int |  | Y | NULL |
| TR_E_ID | int |  | Y | NULL |
| TR_DATA_CRIACAO | smalldatetime |  | Y | NULL |
| TR_DATA | date |  | Y | NULL |
| TR_DATA_REGRESSO | date |  | Y | NULL |
| TR_PAISES_ID | int |  | Y | NULL |
| TR_MORADA | nvarchar | -1 | Y | NULL |
| TR_OBSERVACOES | nvarchar | -1 | Y | NULL |
| TR_DESCRICAO | nvarchar | -1 | Y | NULL |
| TR_TRANSPORTE_NOSSO | bit |  | Y | NULL |
| TR_GOOGLE_NAO | bit |  | Y | NULL |
| estado | int |  | N | NULL |
| transporte | nvarchar | -1 | Y | NULL |
| TR_PUBLICO | bit |  | Y | NULL |

### dbo.vPSD  (9 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| MOV_ID | int |  | N | NULL |
| MOV_DATA | smalldatetime |  | Y | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| P_PRECOVENDA | float |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| MOV_PRECOUNITARIO | float |  | N | NULL |
| MOV_QUANTIDADE | float |  | N | NULL |
| P_PRECOCUSTO | float |  | N | NULL |
| P_MACRO | nvarchar | -1 | N | NULL |

### dbo.vPecasEmFases  (6 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_NOME | nvarchar | -1 | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| Laminagem_Pecas | int |  | Y | NULL |
| Corte | int |  | Y | NULL |
| Armazem | int |  | Y | NULL |
| Armazem_2_Escolha | int |  | Y | NULL |

### dbo.vPecasLaminadas  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| TP_NOME | nvarchar | -1 | N | NULL |
| P_NOME | nvarchar | -1 | N | NULL |
| OF_FP_ID | int |  | N | NULL |
| OFFP_DATAFIM | smalldatetime |  | Y | NULL |
| OFFP_DATA_PREVISTA | smalldatetime |  | Y | NULL |

### dbo.vProdutosEN  (5 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| P_ID | int |  | N | NULL |
| P_NOME | nvarchar | -1 | Y | NULL |
| P_TP_ID | int |  | Y | NULL |
| P_LOJA | bit |  | N | NULL |
| P_DESCONTINUADO | bit |  | N | NULL |

### dbo.vSaldoCliente  (2 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| EPHC_E_ID | int |  | N | NULL |
| saldo | numeric |  | Y | NULL |

### dbo.vSubEntidades  (3 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| E_ID | int |  | N | NULL |
| E_NOME | nvarchar | -1 | N | NULL |
| e_master_id | int |  | N | NULL |

### dbo.vTrackingTransporte  (20 colunas)
| col | tipo | len | null | default |
|---|---|--:|:--:|---|
| codTransporte | int |  | N | NULL |
| dataPartida | date |  | Y | NULL |
| tipoTransporte | nvarchar | -1 | N | NULL |
| codOperador | int |  | Y | NULL |
| codPorto | int |  | Y | NULL |
| moradaDestino | nvarchar | -1 | Y | NULL |
| latitude | decimal |  | Y | NULL |
| longitude | decimal |  | Y | NULL |
| refTipo | nvarchar | -1 | Y | NULL |
| referencia | nvarchar | -1 | Y | NULL |
| idTracker | int |  | Y | NULL |
| codEstado | int |  | Y | NULL |
| latitudeDest | decimal |  | Y | NULL |
| longitudeDest | decimal |  | Y | NULL |
| TR_DESCRICAO | nvarchar | -1 | N | NULL |
| ETA | date |  | Y | NULL |
| lastUpdate | datetime |  | Y | NULL |
| PAISES_NOME | nvarchar | -1 | Y | NULL |
| dataEntrega | date |  | Y | NULL |
| trackLink | nvarchar | -1 | Y | NULL |

## 3. Relacoes (chaves estrangeiras)

| FK | tabela.coluna | -> | referencia |
|---|---|:--:|---|
| FK_AGENTE_FATURA_ENTIDADE | dbo.AGENTE_FATURA.AFT_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_AgenteEncomendaProduto_AgenteEncomenda | dbo.AgenteEncomendaProduto.codEncomenda | -> | dbo.AgenteEncomenda.codEncomenda |
| FK_AgenteEncomendaProduto_PRODUTO | dbo.AgenteEncomendaProduto.codProduto | -> | dbo.PRODUTO.P_ID |
| FK_ALARM_ENTIDADE | dbo.ALARM.ALARM_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ALARM_ENTIDADE1 | dbo.ALARM.ALARM_E_ID_REVISOR | -> | dbo.ENTIDADE.E_ID |
| FK_ALARM_ORDEMFABRICO | dbo.ALARM.ALARM_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_ALARM_PRODUTO | dbo.ALARM.ALARM_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_ALARM_TIPO_ENTIDADE_ALARM_TIPO_ENTIDADE | dbo.ALARM_TIPO_ENTIDADE.ATE_TALARM_ID | -> | dbo.ALARM_TIPO.TALARM_ID |
| FK_ALARM_TIPO_ENTIDADE_ENTIDADE | dbo.ALARM_TIPO_ENTIDADE.ATE_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ARMAZEM_ENTIDADE | dbo.ARMAZEM.ARM_E_ID_RESP | -> | dbo.ENTIDADE.E_ID |
| FK__AtletaPro__Atlet__0B7289DA | dbo.AtletaProva.AtletaID | -> | dbo.ENTIDADE.E_ID |
| FK__AtletaPro__Prova__0C66AE13 | dbo.AtletaProva.ProvaID | -> | dbo.Prova.IDProva |
| FK_ATRIB_ATRIB_ATRIBUTO | dbo.ATRIB_ATRIB.AA_ATRIB_ID | -> | dbo.ATRIBUTO.ATRIB_ID |
| FK_ATRIB_ATRIB_ATRIBUTO1 | dbo.ATRIB_ATRIB.AA_ATRIB_ATRIB_ID | -> | dbo.ATRIBUTO.ATRIB_ID |
| FK_AUDIT_AUDIT | dbo.AUDIT.AUD_AUD_ID | -> | dbo.AUDIT.AUD_ID |
| FK_AUDIT_AUDIT_TIPO | dbo.AUDIT.AUD_AUDT_ID | -> | dbo.AUDIT_TIPO.AUDT_ID |
| FK_AUDIT_ENT_AUDIT | dbo.AUDIT_ENT.AUDE_AUD_ID | -> | dbo.AUDIT.AUD_ID |
| FK_AUDIT_ENT_ENTIDADE | dbo.AUDIT_ENT.AUDE_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_AUDIT_TIPO_AUDIT_TIPO | dbo.AUDIT_TIPO.AUDT_AUDT_ID | -> | dbo.AUDIT_TIPO.AUDT_ID |
| FK_auxAnexos_auxOrdemFabrico | dbo.auxAnexos.aux_id | -> | dbo.auxOrdemFabrico.id |
| FK_AVALIACOES_ITEMS_ENTIDADE_OBS_TIPO | dbo.AVALIACOES_ITEMS.AITEM_EOBSTP_ID | -> | dbo.ENTIDADE_OBS_TIPO.EOBSTP_ID |
| FK_BOATCHOOSER_ANSWER_BOATCHOOSER_QUESTION | dbo.BOATCHOOSER_ANSWER.BCA_QUESTION_ID | -> | dbo.BOATCHOOSER_QUESTION.BCQ_ID |
| FK_BOATCHOOSER_ANSWER_PRODUTO_BOATCHOOSER_ANSWER | dbo.BOATCHOOSER_ANSWER_PRODUTO.BCAP_ANSWER_ID | -> | dbo.BOATCHOOSER_ANSWER.BCA_ID |
| FK_BOATCHOOSER_ANSWER_PRODUTO_PRODUTO | dbo.BOATCHOOSER_ANSWER_PRODUTO.BCAP_PRODUTO_ID | -> | dbo.PRODUTO.P_ID |
| FK_BOATCHOOSER_GROUPS_BOATCHOOSER_QUIZ | dbo.BOATCHOOSER_GROUPS.BCG_QUIZ_ID | -> | dbo.BOATCHOOSER_QUIZ.BCZ_ID |
| FK_BOATCHOOSER_QUESTION_BOATCHOOSER_GROUPS | dbo.BOATCHOOSER_QUESTION.BCQ_GROUP_ID | -> | dbo.BOATCHOOSER_GROUPS.BCG_ID |
| FK_CENTRO_ESTAGIO_CENTRO_ESTAGIO | dbo.CENTRO_ESTAGIO.CE_CE_ID | -> | dbo.CENTRO_ESTAGIO.CE_ID |
| FK_CENTRO_ESTAGIO_DESPESAS_CENTRO_ESTAGIO | dbo.CENTRO_ESTAGIO_DESPESAS.CED_CE_ID | -> | dbo.CENTRO_ESTAGIO.CE_ID |
| FK_CENTRO_MODELOS_QTD_CENTRO_RESERVA | dbo.CENTRO_MODELOS_QTD.CM_RES_ID | -> | dbo.CENTRO_RESERVA.RES_ID |
| FK_CENTRO_MODELOS_QTD_PRODUTO_MODELO | dbo.CENTRO_MODELOS_QTD.CM_M_ID | -> | dbo.PRODUTO_MODELO.M_ID |
| FK_CENTRO_MODELOS_QTD_PRODUTO_NUMERO_POCOS | dbo.CENTRO_MODELOS_QTD.CM_NP_ID | -> | dbo.PRODUTO_NUMERO_POCOS.NP_ID |
| FK_CENTRO_MODELOS_QTD_PRODUTO_TAMANHO | dbo.CENTRO_MODELOS_QTD.CM_TAM_ID | -> | dbo.PRODUTO_TAMANHO.TAM_ID |
| FK_CENTRO_RESERVA_CENTRO_ESTAGIO | dbo.CENTRO_RESERVA.RES_CE_ID | -> | dbo.CENTRO_ESTAGIO.CE_ID |
| FK_CENTRO_RESERVA_CENTRO_RESERVA_ESTADO | dbo.CENTRO_RESERVA.RES_TPCR_ID | -> | dbo.CENTRO_RESERVA_ESTADO.TPCR_ID |
| FK_CENTRO_RESERVA_ENTIDADE | dbo.CENTRO_RESERVA.RES_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_CENTRO_RESERVA_PAISES_SITE | dbo.CENTRO_RESERVA.RES_PAIS_ID | -> | dbo.PAISES_SITE.ID |
| FK_CENTRO_RESERVA_CHECKLIST_CENTRO_RESERVA | dbo.CENTRO_RESERVA_CHECKLIST.CRCHKL_RES_ID | -> | dbo.CENTRO_RESERVA.RES_ID |
| FK_CENTRO_RESERVA_CHECKLIST_CENTRO_RESERVA_CHEKLIST_ITEMS | dbo.CENTRO_RESERVA_CHECKLIST.CRCHKL_CRCHKLI_ID | -> | dbo.CENTRO_RESERVA_CHEKLIST_ITEMS.CRCHKLI_ID |
| FK_CENTRO_RESERVA_OFS_CENTRO_RESERVA | dbo.CENTRO_RESERVA_OFS.RO_RES_ID | -> | dbo.CENTRO_RESERVA.RES_ID |
| FK_CENTRO_RESERVA_OFS_ORDEMFABRICO | dbo.CENTRO_RESERVA_OFS.RO_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_CENTRO_RESERVA_QUARTOS_CENTRO_RESERVA | dbo.CENTRO_RESERVA_QUARTOS.CRQ_RES_ID | -> | dbo.CENTRO_RESERVA.RES_ID |
| FK_CENTRO_RESERVA_TRANSFER_CENTRO_RESERVA | dbo.CENTRO_RESERVA_TRANSFER.CRT_RES_ID | -> | dbo.CENTRO_RESERVA.RES_ID |
| FK_CENTRO_RESERVA_TRANSFER_CENTRO_RESERVA_TRANSFER_RESPONS | dbo.CENTRO_RESERVA_TRANSFER.CRT_CRTR_ID | -> | dbo.CENTRO_RESERVA_TRANSFER_RESPONS.CRTR_ID |
| FK_COMUNICACAO_ENTIDADE | dbo.COMUNICACAO.COM_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_COMUNICACAO_ANEXO_COMUNICACAO | dbo.COMUNICACAO_ANEXO.COMATCH_COM_ID | -> | dbo.COMUNICACAO.COM_ID |
| FK_COMUNICACAO_FASES_PRODUCAO_COMUNICACAO | dbo.COMUNICACAO_FASES_PRODUCAO.COMFP_COM_ID | -> | dbo.COMUNICACAO.COM_ID |
| FK_COMUNICACAO_FASES_PRODUCAO_ENTIDADE | dbo.COMUNICACAO_FASES_PRODUCAO.COMFP_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_COMUNICACAO_FASES_PRODUCAO_FASES_PRODUCAO | dbo.COMUNICACAO_FASES_PRODUCAO.COMFP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_COMUNICACAO_PRODUTO_TIPO_COMUNICACAO | dbo.COMUNICACAO_PRODUTO_TIPO.COMTP_COM_ID | -> | dbo.COMUNICACAO.COM_ID |
| FK_COMUNICACAO_PRODUTO_TIPO_PRODUTO_TIPO | dbo.COMUNICACAO_PRODUTO_TIPO.COMTP_TP_ID | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK_CORREIO_TARIFAS_CORREIO_ZONAS | dbo.CORREIO_TARIFAS.CT_ZONA_ID | -> | dbo.CORREIO_ZONAS.CZ_ID |
| FK_CORREIO_ZONA_PAIS_CORREIO_ZONAS | dbo.CORREIO_ZONA_PAIS.CZP_ZONA_ID | -> | dbo.CORREIO_ZONAS.CZ_ID |
| FK_CORREIO_ZONA_PAIS_PAISES_SITE | dbo.CORREIO_ZONA_PAIS.CZP_PAIS_ID | -> | dbo.PAISES_SITE.ID |
| FK_DOC_PRODUTO_TIPO_DOC | dbo.DOC_PRODUTO_TIPO.doc_doc_id | -> | dbo.DOC.id |
| FK_DOC_PRODUTO_TIPO_PRODUTO_TIPO | dbo.DOC_PRODUTO_TIPO.produto_tipo_tp_id | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK_DOURO_AULA_ENTIDADE_DOURO_AULA | dbo.DOURO_AULA_ENTIDADE.AULAE_AULA_ID | -> | dbo.DOURO_AULA.AULA_ID |
| FK_DOURO_AULA_ENTIDADE_ENTIDADE | dbo.DOURO_AULA_ENTIDADE.AULAE_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_DRAG_VELOCIDADE_DRAG_BARCO | dbo.DRAG_VELOCIDADE.DRAG_BARCO_ID | -> | dbo.DRAG_BARCO.BARCO_ID |
| FK_ENCOMENDA_ENCOMENDA_ESTADO | dbo.ENCOMENDA.ENC_EE_ID | -> | dbo.ENCOMENDA_ESTADO.EE_ID |
| FK_ENCOMENDA_ENTIDADE | dbo.ENCOMENDA.ENC_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENT_CONFIG_ATRIBUTO | dbo.ENT_CONFIG.ECONF_ATRIB_ID | -> | dbo.ATRIBUTO.ATRIB_ID |
| FK_ENT_CONFIG_ATRIBUTO1 | dbo.ENT_CONFIG.ECONF_ATRIB_ATRIB_ID | -> | dbo.ATRIBUTO.ATRIB_ID |
| FK_ENT_CONFIG_ENTIDADE | dbo.ENT_CONFIG.ECONF_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENT_CONFIG_PRODUTO | dbo.ENT_CONFIG.ECONF_P_ID_MODELO | -> | dbo.PRODUTO.P_ID |
| FK_ENT_CONFIG_PRODUTO1 | dbo.ENT_CONFIG.ECONF_P_ID_ACESSORIO | -> | dbo.PRODUTO.P_ID |
| FK_ENT_MOV_ENT_MOV_TIPO | dbo.ENT_MOV.MOVENT_MET_ID | -> | dbo.ENT_MOV_TIPO.MET_ID |
| FK_ENT_MOV_ENTIDADE | dbo.ENT_MOV.MOVENT_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENT_MOV_ENTIDADE1 | dbo.ENT_MOV.MOVENT_E_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENT_MOV_FASES_PRODUCAO | dbo.ENT_MOV.MOVENT_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_ENT_MOV_TIPO_ENT_MOV_TIPO | dbo.ENT_MOV_TIPO.MET_MET_ID | -> | dbo.ENT_MOV_TIPO.MET_ID |
| FK_ENT_TP_PROD_ENTIDADE | dbo.ENT_TP_PROD.ETP_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENT_TP_PROD_PRODUTO_TIPO | dbo.ENT_TP_PROD.ETP_TP_ID | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK_ENTIDADE_ENT_TIPO_VINCULO | dbo.ENTIDADE.E_TV_ID | -> | dbo.ENT_TIPO_VINCULO.TV_ID |
| FK_ENTIDADE_ENTIDADE | dbo.ENTIDADE.E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_ENTIDADE_TIPO | dbo.ENTIDADE.E_ENT_ID | -> | dbo.ENTIDADE_TIPO.ENT_ID |
| FK_ENTIDADE_EQUIPA | dbo.ENTIDADE.E_EQ_ID | -> | dbo.EQUIPA.EQ_ID |
| FK_ENTIDADE_ZONA_GEOGRAFICA | dbo.ENTIDADE.E_ZG_ID | -> | dbo.ZONA_GEOGRAFICA.ZG_ID |
| FK_ENTIDADE_DADOS_ENTIDADE | dbo.ENTIDADE_DADOS.EDADOS_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_DADOS_PAISES | dbo.ENTIDADE_DADOS.EDADOS_PAISES_ID | -> | dbo.PAISES.PAISES_ID |
| FK_ENTIDADE_EQUIPA_ENTIDADE | dbo.ENTIDADE_EQUIPA.EEQ_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_EQUIPA_EQUIPA | dbo.ENTIDADE_EQUIPA.EEQ_EQ_ID | -> | dbo.EQUIPA.EQ_ID |
| FK_ENTIDADE_FASE_ENTIDADE | dbo.ENTIDADE_FASE.EFP_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_FASE_FASES_PRODUCAO | dbo.ENTIDADE_FASE.EFP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_ENTIDADE_MORADA_ENTIDADE | dbo.ENTIDADE_MORADA.EM_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_MORADA_ENTIDADE_MORADA_TIPO | dbo.ENTIDADE_MORADA.EM_TIPO | -> | dbo.ENTIDADE_MORADA_TIPO.EMT_ID |
| FK_ENTIDADE_MORADA_PAISES | dbo.ENTIDADE_MORADA.EM_PAISES_ID | -> | dbo.PAISES_SITE.ID |
| FK_ENTIDADE_OBS_ENTIDADE | dbo.ENTIDADE_OBS.EOBS_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_OBS_ENTIDADE_OBS_TIPO | dbo.ENTIDADE_OBS.EOBS_EOBSTP_ID | -> | dbo.ENTIDADE_OBS_TIPO.EOBSTP_ID |
| FK_ENTIDADE_OBS_ITEM_ENTIDADE_OBS_ITEM | dbo.ENTIDADE_OBS_ITEM.EOBSITEM_EOBS_ID | -> | dbo.ENTIDADE_OBS.EOBS_ID |
| FK_ENTIDADE_OBS_TIPO_ENTIDADE_OBS_TIPO | dbo.ENTIDADE_OBS_TIPO.EOBSTP_ID_ID | -> | dbo.ENTIDADE_OBS_TIPO.EOBSTP_ID |
| FK_ENTIDADE_PHC_ENTIDADE | dbo.ENTIDADE_PHC.EPHC_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_PHC_FACT_ENTIDADE_PHC | dbo.ENTIDADE_PHC_FACT.EPHCF_EPHC_ID | -> | dbo.ENTIDADE_PHC.EPHC_ID |
| FK_ENTIDADE_PROVAS_ENTIDADE | dbo.ENTIDADE_PROVAS.EPRV_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_PROVAS_PROVAS | dbo.ENTIDADE_PROVAS.EPRV_PRV_ID | -> | dbo.PROVAS.PRV_ID |
| FK_ENTIDADE_SUB_ENTIDADE | dbo.ENTIDADE_SUB.e_master_id | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_SUB_ENTIDADE1 | dbo.ENTIDADE_SUB.e_sub_id | -> | dbo.ENTIDADE.E_ID |
| FK_ENTIDADE_TIPO_ENTIDADE_TIPO | dbo.ENTIDADE_TIPO.ENT_ENT_ID | -> | dbo.ENTIDADE_TIPO.ENT_ID |
| FK_ENTIDADE_TREINOS_ENTIDADE | dbo.ENTIDADE_TREINOS.ETR_E_ID | -> | dbo.ENTIDADE.E_ID |
| failed_import_rows_import_id_foreign | dbo.failed_import_rows.import_id | -> | dbo.imports.id |
| FK_FASES_PRODUCAO_FASES_PRODUCAO | dbo.FASES_PRODUCAO.FP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_FASES_PRODUCAO_PRODUTO | dbo.FASES_PRODUCAO.FP_P_ID | -> | dbo.PRODUTO.P_ID |
| fatura_entidade_id_foreign | dbo.FATURA.entidade_id | -> | dbo.ENTIDADE.E_ID |
| FK_FP_FP_FASES_PRODUCAO | dbo.FP_FP.FPFP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_FP_FP_FASES_PRODUCAO1 | dbo.FP_FP.FPFP_FP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_IDEIA_ENTIDADE | dbo.IDEIA.ID_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_ENTIDADE1 | dbo.IDEIA.ID_E_ID_COORDENADOR | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_IDEIA | dbo.IDEIA.ID_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_IDEIA_CLASSIFICACAO | dbo.IDEIA.ID_IDCL_ID_RELEV | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_IDEIA_CLASSIFICACAO1 | dbo.IDEIA.ID_IDCL_ID_PRIORI | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_IDEIA_CLASSIFICACAO2 | dbo.IDEIA.ID_IDCL_ID_FACIL | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_IDEIA_CLASSIFICACAO3 | dbo.IDEIA.ID_IDCL_ID_TIPO | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_IDEIA_CLASSIFICACAO4 | dbo.IDEIA.ID_IDCL_ID_GRAU | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_IDEIA_ESTADO | dbo.IDEIA.ID_IDEST_ID | -> | dbo.IDEIA_ESTADO.IDEST_ID |
| FK_IDEIA__CLASSIFIC_CHECK_IDEIA_CLASSIFICACAO | dbo.IDEIA_CLASSIFIC_CHECK.IDCLCHK_IDCL_ID | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_CLASSIFICACAO_IDEIA_CLASSIFICACAO | dbo.IDEIA_CLASSIFICACAO.IDCL_IDCL_ID | -> | dbo.IDEIA_CLASSIFICACAO.IDCL_ID |
| FK_IDEIA_COLAB_ENTIDADE | dbo.IDEIA_COLAB.IDCOL_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_COLAB_IDEIA | dbo.IDEIA_COLAB.IDCOL_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_COLAB_IDEIA_EVOL | dbo.IDEIA_COLAB.IDCOL_IDEV_ID | -> | dbo.IDEIA_EVOL.IDEV_ID |
| FK_IDEIA_COLAB_IDEIA_TPCOL | dbo.IDEIA_COLAB.IDCOL_TPCOL_ID | -> | dbo.IDEIA_TPCOL.TPCOL_ID |
| FK_IDEIA_DOC_ENTIDADE | dbo.IDEIA_DOC.IDDOC_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_DOC_IDEIA | dbo.IDEIA_DOC.IDDOC_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_DOC_IDEIA_DOC | dbo.IDEIA_DOC.IDDOC_IDDOC_ID | -> | dbo.IDEIA_DOC.IDDOC_ID |
| FK_IDEIA_ENTIDADE_ENTIDADE | dbo.IDEIA_ENTIDADE.IDENT_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_ENTIDADE_IDEIA | dbo.IDEIA_ENTIDADE.IDENT_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_ESTADO_IDEIA_ESTADO | dbo.IDEIA_ESTADO.IDEST_IDEST_ID | -> | dbo.IDEIA_ESTADO.IDEST_ID |
| FK_IDEIA_EVOL_IDEIA | dbo.IDEIA_EVOL.IDEV_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_EVOL_IDEIA_ESTADO | dbo.IDEIA_EVOL.IDEV_IDEST_ID | -> | dbo.IDEIA_ESTADO.IDEST_ID |
| FK_IDEIA_EVOL_IDEIA_EVOL | dbo.IDEIA_EVOL.IDEV_IDEV_ID | -> | dbo.IDEIA_EVOL.IDEV_ID |
| FK_IDEIA_REUNIAO_IDEIA | dbo.IDEIA_REUNIAO.IDR_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_IDEIA_TAREFA_ENTIDADE | dbo.IDEIA_TAREFA.IDTAR_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_IDEIA_TAREFA_IDEIA_EVOL | dbo.IDEIA_TAREFA.IDTAR_IDEV_ID | -> | dbo.IDEIA_EVOL.IDEV_ID |
| FK_IDEIA_TAREFA_IDEIA_TAREFA | dbo.IDEIA_TAREFA.IDTAR_IDTAR_ID | -> | dbo.IDEIA_TAREFA.IDTAR_ID |
| FK_INTERVALO_PRODUTO_TIPO | dbo.INTERVALO.INTERVALO_TP_ID | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK_IOT_SENSOR_IOT_SENSOR | dbo.IOT_SENSOR.SENSOR_TIPO_ID | -> | dbo.IOT_SENSOR_TIPO.ST_ID |
| FK_IOT_SENSOR_DATA_IOT_SENSOR | dbo.IOT_SENSOR_DATA.SD_SENSOR_ID | -> | dbo.IOT_SENSOR.SENSOR_ID |
| FK_KPI_KPI | dbo.KPI.KPI_KPI_ID | -> | dbo.KPI.KPI_ID |
| FK_KPI_OBJECTIVO_KPI | dbo.KPI_OBJECTIVO.KPIO_KPI_ID | -> | dbo.KPI.KPI_ID |
| FK_LISTA_LISTA_TIPO | dbo.LISTA.L_LTP_ID | -> | dbo.LISTA_TIPO.LTP_ID |
| FK_LISTA_COORDENADAS_LISTA | dbo.LISTA_COORDENADAS.LCOORD_L_ID | -> | dbo.LISTA.L_ID |
| FK_LISTA_MOVIMENTO_LISTA | dbo.LISTA_MOVIMENTO.LM_L_ID | -> | dbo.LISTA.L_ID |
| FK_LISTA_PRODUTO_LISTA | dbo.LISTA_PRODUTO.LP_L_ID | -> | dbo.LISTA.L_ID |
| FK_LISTA_PRODUTO_PRODUTO | dbo.LISTA_PRODUTO.LP_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_LISTA_TIPO_PRODUTO_LISTA_TIPO | dbo.LISTA_TIPO.LTP_ID | -> | dbo.LISTA_TIPO.LTP_ID |
| FK_MEDIDAS_PRODUTO_MODELO | dbo.MEDIDAS.MED_M_ID | -> | dbo.PRODUTO_MODELO.M_ID |
| FK_MEDIDAS_PRODUTO_NUMERO_POCOS | dbo.MEDIDAS.MED_NP_ID | -> | dbo.PRODUTO_NUMERO_POCOS.NP_ID |
| FK_MEDIDAS_PRODUTO_TAMANHO | dbo.MEDIDAS.MED_TAM_ID | -> | dbo.PRODUTO_TAMANHO.TAM_ID |
| FK_MOLDES_MOLDES_TIPO | dbo.MOLDES.MLD_MLDTP_ID | -> | dbo.MOLDES_TIPO.MLDTP_ID |
| FK_MOLDES_MOV_MOLDES | dbo.MOLDES_MOV.MLDU_MLD_ID | -> | dbo.MOLDES.MLD_ID |
| FK_MOVIMENTO_ENTIDADE | dbo.MOVIMENTO.MOV_E_ID_RESPONSAVEL | -> | dbo.ENTIDADE.E_ID |
| FK_MOVIMENTO_ENTIDADE1 | dbo.MOVIMENTO.MOV_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_MOVIMENTO_ENTIDADE2 | dbo.MOVIMENTO.MOV_E_ID_APROVA | -> | dbo.ENTIDADE.E_ID |
| FK_MOVIMENTO_FASES_PRODUCAO | dbo.MOVIMENTO.MOV_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_MOVIMENTO_MOVIMENTO | dbo.MOVIMENTO.MOV_MOV_ID | -> | dbo.MOVIMENTO.MOV_ID |
| FK_MOVIMENTO_ATTACH_MOVIMENTO | dbo.MOVIMENTO_ATTACH.MATCH_MOV_ID | -> | dbo.MOVIMENTO.MOV_ID |
| FK_OF_ATTACH_ATTACH_TIPO | dbo.OF_ATTACH.ATCH_TIPO | -> | dbo.ATTACH_TIPO.TP_ATCH_ID |
| FK_OF_ATTACH_FASES_PRODUCAO | dbo.OF_ATTACH.ATCH_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_OF_CHECKLIST_FASES_PRODUCAO | dbo.OF_CHECKLIST.OFCH_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_OF_CHECKLIST_FASES_PRODUCAO1 | dbo.OF_CHECKLIST.OFCH_FP_ID_CHK | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_OF_CHECKLIST_OF_FP | dbo.OF_CHECKLIST.OFCH_OFFP_ID | -> | dbo.OF_FP.OFFP_ID |
| FK_OF_CHECKLIST_ORDEMFABRICO | dbo.OF_CHECKLIST.OFCH_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_OF_ENTIDADE_ENTIDADE | dbo.OF_ENTIDADE.OFE_E_ID_ANTERIOR | -> | dbo.ENTIDADE.E_ID |
| FK_OF_ENTIDADE_ENTIDADE1 | dbo.OF_ENTIDADE.OFE_E_ID_RESPONSAVEL | -> | dbo.ENTIDADE.E_ID |
| FK_OF_ENTIDADE_ORDEMFABRICO | dbo.OF_ENTIDADE.OFE_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_OF_FP_FASES_PRODUCAO | dbo.OF_FP.OFFP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_OF_FP_OF_FP1 | dbo.OF_FP.OFFP_OFFP_ID_RETURN | -> | dbo.OF_FP.OFFP_ID |
| FK_OF_FP_OFFP_CL | dbo.OF_FP.OFFP_OFFPCL_ID | -> | dbo.OFFP_CL.OFFPCL_ID |
| FK_OF_FP_ORDEMFABRICO | dbo.OF_FP.OFFP_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_OF_FP_PRODUTO_CAMADA_TIPO | dbo.OF_FP.OFFP_TPCAM_ID | -> | dbo.PRODUTO_CAMADA_TIPO.TPCAM_ID |
| FK_OF_OF_TIPOUSO_OF_TIPOUSO | dbo.OF_OF_TIPOUSO.OFOFTU_OFTU_ID | -> | dbo.OF_TIPOUSO.OFTU_ID |
| FK_OF_OF_TIPOUSO_ORDEMFABRICO | dbo.OF_OF_TIPOUSO.OFOFTU_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_OF_RENTAL_PROVAS_ENTIDADE | dbo.OF_RENTAL_PROVAS.OFR_E_ID_ENTREGA | -> | dbo.ENTIDADE.E_ID |
| FK_OF_RENTAL_PROVAS_ENTIDADE1 | dbo.OF_RENTAL_PROVAS.OFR_E_ID_RECEBIDO | -> | dbo.ENTIDADE.E_ID |
| FK_OF_RENTAL_PROVAS_ORDEMFABRICO | dbo.OF_RENTAL_PROVAS.OFR_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_OF_VENDA_FASES_PRODUCAO | dbo.OF_VENDA.OFV_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_OF_VENDA_PAISES_SITE | dbo.OF_VENDA.OFV_PS_ID | -> | dbo.PAISES_SITE.ID |
| FK_OF_VENDA_PRODUTO | dbo.OF_VENDA.OFV_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_OFCH_LOCAL_PROBS_LOCAL | dbo.OFCH_LOCAL.OFPROBS_PROBSL_ID | -> | dbo.PROBS_LOCAL.PROBSL_ID |
| FK_OFFP_EQ_ENTIDADE | dbo.OFFP_EQ.OFFPEQ_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_OFFP_EQ_OF_FP | dbo.OFFP_EQ.OFFPEQ_OFFP_ID | -> | dbo.OF_FP.OFFP_ID |
| FK_OFFP_LINK_OF_FP | dbo.OFFP_LINK.OFFPL_OFFP_ID_PROX | -> | dbo.OF_FP.OFFP_ID |
| FK_OFFP_LINK_OF_FP1 | dbo.OFFP_LINK.OFFPL_OFFP_ID_ANT | -> | dbo.OF_FP.OFFP_ID |
| FK_OFFP_PROBLEMA_OF_FP | dbo.OFFP_PROBLEMA.OFFPPROB_OFFP_ID | -> | dbo.OF_FP.OFFP_ID |
| FK_OFFP_PROBLEMA_PROBS | dbo.OFFP_PROBLEMA.OFFPPROB_PROBS_ID | -> | dbo.PROBS.PROBS_ID |
| FK_OFFP_PROBLEMA_PROBS_LOCAL | dbo.OFFP_PROBLEMA.OFFPPROB_PROBSL_ID | -> | dbo.PROBS_LOCAL.PROBSL_ID |
| FK_ORDEMFABRICO_ARMAZEM | dbo.ORDEMFABRICO.OF_ARM_ID | -> | dbo.ARMAZEM.ARM_ID |
| FK_ORDEMFABRICO_ENCOMENDA | dbo.ORDEMFABRICO.OF_ENC_ID | -> | dbo.ENCOMENDA.ENC_ID |
| FK_ORDEMFABRICO_ENTIDADE | dbo.ORDEMFABRICO.OF_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_ORDEMFABRICO_ENTIDADE_MORADA | dbo.ORDEMFABRICO.OF_EM_ID | -> | dbo.ENTIDADE_MORADA.EM_ID |
| FK_ORDEMFABRICO_ENTIDADE1 | dbo.ORDEMFABRICO.OF_E_ID_ENC | -> | dbo.ENTIDADE.E_ID |
| FK_ORDEMFABRICO_FASES_PRODUCAO | dbo.ORDEMFABRICO.OF_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_ORDEMFABRICO_IOT_SENSOR | dbo.ORDEMFABRICO.OF_SENSOR_ID_VACUO | -> | dbo.IOT_SENSOR.SENSOR_ID |
| FK_ORDEMFABRICO_MOVIMENTO | dbo.ORDEMFABRICO.OF_MOV_ID | -> | dbo.MOVIMENTO.MOV_ID |
| FK_ORDEMFABRICO_OF_TIPOUSO | dbo.ORDEMFABRICO.OF_OFTU_ID | -> | dbo.OF_TIPOUSO.OFTU_ID |
| FK_ORDEMFABRICO_ORDEMFABRICO | dbo.ORDEMFABRICO.OF_OF_ID_MLD | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_ORDEMFABRICO_ORDEMFABRICO1 | dbo.ORDEMFABRICO.OF_OF_ID_MAE | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_ORDEMFABRICO_ORDEMFABRICO2 | dbo.ORDEMFABRICO.OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_ORDEMFABRICO_PRODUTO | dbo.ORDEMFABRICO.OF_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_ORDEMFABRICO_PRODUTO3 | dbo.ORDEMFABRICO.OF_P_ID_CDECK | -> | dbo.PRODUTO.P_ID |
| FK_ORDEMFABRICO_PRODUTO4 | dbo.ORDEMFABRICO.OF_P_ID_CCASCO | -> | dbo.PRODUTO.P_ID |
| FK_ORDEMFABRICO_TURNO | dbo.ORDEMFABRICO.OF_TURN_ID | -> | dbo.TURNO.TURN_ID |
| FK_PLANEAMENTO_DIARIO_TRANSPORTE | dbo.PLANEAMENTO_DIARIO.TransporteId | -> | dbo.TRANSPORTE.TR_ID |
| FK_PLANO_ENTIDADE | dbo.PLANO.PL_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PLANO_PRODUTO | dbo.PLANO.PL_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PLANO_PRODUTO_FASE | dbo.PLANO.PL_PRODF_ID | -> | dbo.PRODUTO_FASE.PRODF_ID |
| FK_PORTAO_ENTIDADE | dbo.PORTAO.PORTAO_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PROB_CAUSA_SOL_FASES_PRODUCAO | dbo.PROB_CAUSA_SOL.PCS_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_PROB_CAUSA_SOL_PROB_CAUSA_SOL_TIPO | dbo.PROB_CAUSA_SOL.PCS_TPPCS_ID | -> | dbo.PROB_CAUSA_SOL_TIPO.TPPCS_ID |
| FK_PROBS_PROBS | dbo.PROBS.PROBS_PROBS_ID | -> | dbo.PROBS.PROBS_ID |
| FK_PROC_AREA_PROC_AREA | dbo.PROC_AREA.PROC_PROC_ID | -> | dbo.PROC_AREA.PROC_ID |
| FK_PROC_AREA_PROC_CLASSIFIC | dbo.PROC_AREA.PROC_CLSP_ID_PERIOD | -> | dbo.PROC_CLASSIFIC.CLSP_ID |
| FK_PROC_AREA_PROC_CLASSIFIC1 | dbo.PROC_AREA.PROC_CLSP_ID_IMPORT | -> | dbo.PROC_CLASSIFIC.CLSP_ID |
| FK_PROC_AREA_PROC_TIPO | dbo.PROC_AREA.PROC_TPPROC_ID | -> | dbo.PROC_TIPO.TPPROC_ID |
| FK_PROC_AREA_ENT_ENTIDADE | dbo.PROC_AREA_ENT.PROCAE_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PROC_AREA_ENT_PROC_AREA | dbo.PROC_AREA_ENT.PROCAE_PROC_ID | -> | dbo.PROC_AREA.PROC_ID |
| FK_PROC_AREA_ENT_PROC_AREA_FONTE | dbo.PROC_AREA_ENT.PROCAE_PROCAF_ID | -> | dbo.PROC_AREA_FONTE.PROCAF_ID |
| FK_PROC_AREA_ENT_PROC_TIPO_ENT | dbo.PROC_AREA_ENT.PROCAE_PROCTPE_ID | -> | dbo.PROC_TIPO_ENT.PROCTPE_ID |
| FK_PROC_AREA_FONTE_ENTIDADE | dbo.PROC_AREA_FONTE.PROCAF_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PROC_AREA_FONTE_PROC_AREA | dbo.PROC_AREA_FONTE.PROCAF_PROC_ID | -> | dbo.PROC_AREA.PROC_ID |
| FK_PROC_AREA_FONTE_PROC_ARQUIVO | dbo.PROC_AREA_FONTE.PROCAF_PROCARQ_ID | -> | dbo.PROC_ARQUIVO.PROCARQ_ID |
| FK_PROC_AREA_FONTE_PROC_FONTE | dbo.PROC_AREA_FONTE.PROCAF_PROCFT_ID | -> | dbo.PROC_FONTE.PROCFT_ID |
| FK_PRODUTO_ENTIDADE | dbo.PRODUTO.P_E_ID_CRIADOR | -> | dbo.ENTIDADE.E_ID |
| FK_PRODUTO_PRODUTO | dbo.PRODUTO.P_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_RESPONSAVEL_ENCOMENDAS | dbo.PRODUTO.P_E_ID_RESP | -> | dbo.ENTIDADE.E_ID |
| FK_PRODUTO_ATTACH_ENTIDADE_OBS | dbo.PRODUTO_ATTACH.AT_EOBS_ID | -> | dbo.ENTIDADE_OBS.EOBS_ID |
| FK_PRODUTO_ATTACH_PRODUTO | dbo.PRODUTO_ATTACH.AT_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_ATTACH_PRODUTO_ATTACH_TIPO | dbo.PRODUTO_ATTACH.AT_ATT_ID | -> | dbo.PRODUTO_ATTACH_TIPO.ATT_ID |
| FK_PRODUTO_CAMADA_PRODUTO | dbo.PRODUTO_CAMADA.CAM_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_CAMADA_PRODUTO_CAMADA_TIPO | dbo.PRODUTO_CAMADA.CAM_TPCAM_ID | -> | dbo.PRODUTO_CAMADA_TIPO.TPCAM_ID |
| FK_PRODUTO_CAMADA_TIPO_PRODUTO_CAMADA_TIPO1 | dbo.PRODUTO_CAMADA_TIPO.TPCAM_TPCAM_ID_PAI | -> | dbo.PRODUTO_CAMADA_TIPO.TPCAM_ID |
| FK_PRODUTO_COEFICIENTE_PRODUTO | dbo.PRODUTO_COEFICIENTE.PCOEF_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_COMPONENTE_ATRIBUTO | dbo.PRODUTO_COMPONENTE.COMP_ATRIB_ID | -> | dbo.ATRIBUTO.ATRIB_ID |
| FK_PRODUTO_COMPONENTE_COMPONENTE_TIPO | dbo.PRODUTO_COMPONENTE.COMP_TPCOMP_ID | -> | dbo.COMPONENTE_TIPO.TPCOMP_ID |
| FK_PRODUTO_COMPONENTE_FASES_PRODUCAO | dbo.PRODUTO_COMPONENTE.COMP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_PRODUTO_COMPONENTE_LISTA | dbo.PRODUTO_COMPONENTE.COMP_L_ID | -> | dbo.LISTA.L_ID |
| FK_PRODUTO_COMPONENTE_PRODUTO | dbo.PRODUTO_COMPONENTE.COMP_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_COMPONENTE_PRODUTO1 | dbo.PRODUTO_COMPONENTE.COMP_P_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_ENTIDADE_ENTIDADE | dbo.PRODUTO_ENTIDADE.PF_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PRODUTO_ENTIDADE_PRODUTO | dbo.PRODUTO_ENTIDADE.PF_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_ENTIDADE_UNIDADE | dbo.PRODUTO_ENTIDADE.PF_UNI_ID | -> | dbo.UNIDADE.UNI_ID |
| FK_PRODUTO_ESTADO_PRODUTO_ESTADO | dbo.PRODUTO_ESTADO.EST_EST_ID | -> | dbo.PRODUTO_ESTADO.EST_ID |
| FK_PRODUTO_FASE_FASES_PRODUCAO | dbo.PRODUTO_FASE.PRODF_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_PRODUTO_FASE_PRODUTO | dbo.PRODUTO_FASE.PRODF_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_FASE_PRODUTO_CAMADA_TIPO | dbo.PRODUTO_FASE.PRODF_TPCAM_ID | -> | dbo.PRODUTO_CAMADA_TIPO.TPCAM_ID |
| FK_PRODUTO_FASE_PRODUTO_FASE | dbo.PRODUTO_FASE.PRODF_PRODF_ID | -> | dbo.PRODUTO_FASE.PRODF_ID |
| FK_PRODUTO_FASE_LINK_PRODUTO_FASE | dbo.PRODUTO_FASE_LINK.PRODFL_PRODF_ID_PROX | -> | dbo.PRODUTO_FASE.PRODF_ID |
| FK_PRODUTO_FASE_LINK_PRODUTO_FASE1 | dbo.PRODUTO_FASE_LINK.PRODFL_PRODF_ID_ANT | -> | dbo.PRODUTO_FASE.PRODF_ID |
| FK_PRODUTO_LISTA_ITEMS_PRODUTO_LISTA | dbo.PRODUTO_LISTA_ITEMS.PLI_PL_ID | -> | dbo.PRODUTO_LISTA.PL_ID |
| FK_PRODUTO_OPCOES_PRODUTO | dbo.PRODUTO_OPCOES.POP_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_OPCOES_PRODUTO1 | dbo.PRODUTO_OPCOES.POP_P_P_ID | -> | dbo.PRODUTO.P_ID |
| FK_PRODUTO_PROB_CAUSA_SOL_PROB_CAUSA_SOL | dbo.PRODUTO_PROB_CAUSA_SOL.PP_PCS_ID | -> | dbo.PROB_CAUSA_SOL.PCS_ID |
| FK_PRODUTO_PROB_CAUSA_SOL_PROB_CAUSA_SOL1 | dbo.PRODUTO_PROB_CAUSA_SOL.PP_PCS_PCS_ID | -> | dbo.PROB_CAUSA_SOL.PCS_ID |
| FK_PRODUTO_TIPO_ENTIDADE | dbo.PRODUTO_TIPO.TP_ENT_OWNER | -> | dbo.ENTIDADE.E_ID |
| FK_PRODUTO_TIPO_FASES_PRODUCAO | dbo.PRODUTO_TIPO.TP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_PRODUTO_TIPO_PRODUTO_TIPO | dbo.PRODUTO_TIPO.TP_TP_ID | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK_ProdutoTipoAcessorio_PRODUTO | dbo.ProdutoTipoAcessorio.codProduto | -> | dbo.PRODUTO.P_ID |
| FK_ProdutoTipoAcessorio_PRODUTO_TIPO | dbo.ProdutoTipoAcessorio.codTipo | -> | dbo.PRODUTO_TIPO.TP_ID |
| FK__Prova__IDCompeti__04C58C4B | dbo.Prova.IDCompeticao | -> | dbo.Competicao.IDCompeticao |
| FK_PROVAS_BOOKING_ENTIDADE | dbo.PROVAS_BOOKING.PRVB_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PROVAS_BOOKING_ORDEMFABRICO | dbo.PROVAS_BOOKING.PRVB_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_PROVAS_BOOKING_PROVAS | dbo.PROVAS_BOOKING.PRVB_PRV_ID | -> | dbo.PROVAS.PRV_ID |
| FK_PROVAS_BOOKING_PROVAS_BOOKING_ESTADO | dbo.PROVAS_BOOKING.PRVB_PBEST_ID | -> | dbo.PROVAS_BOOKING_ESTADO.PBEST_ID |
| FK_PROVAS_FICHEIROS_ENTIDADE | dbo.PROVAS_FICHEIROS.PRVFX_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_PROVAS_FICHEIROS_PROVAS | dbo.PROVAS_FICHEIROS.PRVFX_PRV_ID | -> | dbo.PROVAS.PRV_ID |
| FK_PROVAS_OF_ORDEMFABRICO | dbo.PROVAS_OF.PRVOF_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_PROVAS_OF_PROVAS | dbo.PROVAS_OF.PRVOF_PRV_ID | -> | dbo.PROVAS.PRV_ID |
| FK_PROVAS_PROVAS_ESTADO_PROVAS | dbo.PROVAS_PROVAS_BOOKING_ESTADO.PBPEST_PRVB_ID | -> | dbo.PROVAS_BOOKING.PRVB_ID |
| FK_PROVAS_PROVAS_ESTADO_PROVAS_ESTADO | dbo.PROVAS_PROVAS_BOOKING_ESTADO.PBPEST_PEST_ID | -> | dbo.PROVAS_BOOKING_ESTADO.PBEST_ID |
| FK_REP_OF_FP_FASES_PRODUCAO | dbo.REP_OF_FP.ROFFP_FP_ID | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_REP_OF_FP_REPARACOES_PROVAS | dbo.REP_OF_FP.ROFFP_REP_ID | -> | dbo.REPARACOES_PROVAS.REP_ID |
| FK_REPARACOES_PROVAS_ENTIDADE | dbo.REPARACOES_PROVAS.REP_E_ID_RESPONSAVEL | -> | dbo.ENTIDADE.E_ID |
| FK_RH_DOC_RH_TIPO_DOC | dbo.RH_DOC.RHD_TIPO_ID | -> | dbo.RH_TIPO_DOC.RHTD_ID |
| FK_SensoresLoginSessao_SensoresLogin | dbo.SensoresLoginSessao.codLogin | -> | dbo.SensoresLogin.codLogin |
| FK_SensoresLoginSessao_SensoresTeste | dbo.SensoresLoginSessao.codTeste | -> | dbo.SensoresTeste.codTeste |
| FK_SensoresTeste_PAISES | dbo.SensoresTeste.codPais | -> | dbo.PAISES.PAISES_ID |
| FK_SensoresTesteAtleta_SensoresTeste | dbo.SensoresTesteAtleta.codTeste | -> | dbo.SensoresTeste.codTeste |
| FK_SensoresTesteSerie_SensoresTeste | dbo.SensoresTesteSerie.codTeste | -> | dbo.SensoresTeste.codTeste |
| FK_SensoresTesteSeriePosicoes_SensoresTesteAtleta | dbo.SensoresTesteSeriePosicoes.codTeste | -> | dbo.SensoresTesteAtleta.codTeste |
| FK_SensoresTesteSeriePosicoes_SensoresTesteAtleta | dbo.SensoresTesteSeriePosicoes.codAtleta | -> | dbo.SensoresTesteAtleta.codAtleta |
| FK_SensoresTesteSeriePosicoes_SensoresTesteSerie | dbo.SensoresTesteSeriePosicoes.codTeste | -> | dbo.SensoresTesteSerie.codTeste |
| FK_SensoresTesteSeriePosicoes_SensoresTesteSerie | dbo.SensoresTesteSeriePosicoes.codSerie | -> | dbo.SensoresTesteSerie.codSerie |
| FK_SensoresTesteSerieValores_SensoresTesteSerie | dbo.SensoresTesteSerieValores.codTeste | -> | dbo.SensoresTesteSerie.codTeste |
| FK_SensoresTesteSerieValores_SensoresTesteSerie | dbo.SensoresTesteSerieValores.codSerie | -> | dbo.SensoresTesteSerie.codSerie |
| FK_SensoresTesteVideo_SensoresTeste | dbo.SensoresTesteVideo.CodSessao | -> | dbo.SensoresTeste.codTeste |
| FK_SGIDI_SGIDI | dbo.SGIDI.SGIDI_SGIDI_ID | -> | dbo.SGIDI.SGIDI_ID |
| FK_SGIDI_SGIDI_TIPO | dbo.SGIDI.SGIDI_SGIDITP_ID | -> | dbo.SGIDI_TIPO.SGIDITP_ID |
| FK_SGIDI_FICHEIRO_ENTIDADE | dbo.SGIDI_FICHEIRO.SGIDIF_CRIADOR | -> | dbo.ENTIDADE.E_ID |
| FK_SGIDI_FICHEIRO_ENTIDADE1 | dbo.SGIDI_FICHEIRO.SGIDIF_ACTUALIZADOR | -> | dbo.ENTIDADE.E_ID |
| FK_SGIDI_FICHEIRO_PROC_AREA_FONTE | dbo.SGIDI_FICHEIRO.SGIDIF_PROCAF_ID | -> | dbo.PROC_AREA_FONTE.PROCAF_ID |
| FK_SGIDI_FICHEIRO_SGIDI_FICHEIRO | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIF_ID | -> | dbo.SGIDI_FICHEIRO.SGIDIF_ID |
| FK_SGIDI_FICHEIRO_SGIDI_FX_CLASSIFIC | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIFXCL_ID_TIPO | -> | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_ID |
| FK_SGIDI_FICHEIRO_SGIDI_FX_CLASSIFIC1 | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIFXCL_ID_TEMPO | -> | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_ID |
| FK_SGIDI_FICHEIRO_SGIDI_FX_CLASSIFIC2 | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIFXCL_ID_METODO | -> | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_ID |
| FK_SGIDI_FICHEIRO_SGIDI_FX_CLASSIFIC3 | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIFXCL_ID_REVISAO | -> | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_ID |
| FK_SGIDI_FICHEIRO_SGIDI_PASTA | dbo.SGIDI_FICHEIRO.SGIDIF_SGIDIP_ID | -> | dbo.SGIDI_PASTA.SGIDIP_ID |
| FK_SGIDI_FX_CLASSIFIC_SGIDI_FX_CLASSIFIC | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_SGIDIFXCL_ID | -> | dbo.SGIDI_FX_CLASSIFIC.SGIDIFXCL_ID |
| FK_SGIDI_PASTA_ENTIDADE | dbo.SGIDI_PASTA.SGIDIP_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_SGIDI_PASTA_IDEIA | dbo.SGIDI_PASTA.SGIDIP_ID_ID | -> | dbo.IDEIA.ID_ID |
| FK_SGIDI_PASTA_PEDIDOS | dbo.SGIDI_PASTA.SGIDIP_PED_ID | -> | dbo.PEDIDOS.PED_ID |
| FK_SGIDI_PASTA_PEDIDOS | dbo.SGIDI_PASTA.SGIDIP_E_ID | -> | dbo.PEDIDOS.PED_E_ID |
| FK_SGIDI_PASTA_SGIDI_PASTA | dbo.SGIDI_PASTA.SGIDIP_SGIDIP_ID | -> | dbo.SGIDI_PASTA.SGIDIP_ID |
| FK_SGIDI_PASTA_TRANSPORTE | dbo.SGIDI_PASTA.SGIDIP_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| telescope_entries_tags_entry_uuid_foreign | dbo.telescope_entries_tags.entry_uuid | -> | dbo.telescope_entries.uuid |
| FK_TH_FASES_PRODUCAO | dbo.TH.TH_FASE | -> | dbo.FASES_PRODUCAO.FP_ID |
| FK_TH_TH_SONDA | dbo.TH.TH_SONDA | -> | dbo.TH_SONDA.THS_ID |
| FK_TH_SCHED_TH_SONDA | dbo.TH_SCHED.THSCHED_SONDA | -> | dbo.TH_SONDA.THS_ID |
| FK_TRANSP_DATAS_TRANSP_DATAS_CLASSIFICACAO | dbo.TRANSP_DATAS.TRDT_TRDTCL_ID | -> | dbo.TRANSP_DATAS_CLASSIFICACAO.TRDTCL_ID |
| FK_TRANSP_DATAS_TRANSPORTE | dbo.TRANSP_DATAS.TRDT_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_DESP_TRANSP_DESP_TIPO | dbo.TRANSP_DESP.TRDESP_TRDESPTP_ID | -> | dbo.TRANSP_DESP_TIPO.TRDESPTP_ID |
| FK_TRANSP_DESP_TRANSPORTE | dbo.TRANSP_DESP.TRDESP_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_DOCS_TRANSP_DOCS_STD | dbo.TRANSP_DOCS.TRDOC_DOCS_ID | -> | dbo.TRANSP_DOCS_STD.DOCS_ID |
| FK_TRANSP_DOCS_TRANSPORTE | dbo.TRANSP_DOCS.TRDOC_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_DOCS_DEST_TIPO_TRANSP_DESTINO | dbo.TRANSP_DOCS_DEST_TIPO.DTD_DEST_ID | -> | dbo.TRANSP_DESTINO.DEST_ID |
| FK_TRANSP_DOCS_DEST_TIPO_TRANSP_DOCS_STD | dbo.TRANSP_DOCS_DEST_TIPO.DTD_DOCS_ID | -> | dbo.TRANSP_DOCS_STD.DOCS_ID |
| FK_TRANSP_DOCS_DEST_TIPO_TRANSP_TIPO | dbo.TRANSP_DOCS_DEST_TIPO.DTD_TRTP_ID | -> | dbo.TRANSP_TIPO.TRTP_ID |
| FK_TRANSP_ENTIDADE_ENTIDADE | dbo.TRANSP_ENTIDADE.TRE_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_TRANSP_ENTIDADE_TRANSP_TIPO | dbo.TRANSP_ENTIDADE.TRE_TRTP_ID | -> | dbo.TRANSP_TIPO.TRTP_ID |
| FK_TRANSP_ENTIDADE_TRANSPORTE | dbo.TRANSP_ENTIDADE.TRE_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_OF_ORDEMFABRICO | dbo.TRANSP_OF.TROF_OF_ID | -> | dbo.ORDEMFABRICO.OF_ID |
| FK_TRANSP_OF_TRANSPORTE | dbo.TRANSP_OF.TROF_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_TIPO_TRANSP_TIPO | dbo.TRANSP_TIPO.TRTP_TRTP_ID | -> | dbo.TRANSP_TIPO.TRTP_ID |
| FK_TRANSP_VAL_TRANSPORTE | dbo.TRANSP_VAL.TRVAL_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_TRANSP_VAL_VALOR | dbo.TRANSP_VAL.TRVAL_VAL_ID | -> | dbo.VALOR.VAL_ID |
| FK_TRANSPORTE_ENTIDADE | dbo.TRANSPORTE.TR_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_TRANSPORTE_PAISES | dbo.TRANSPORTE.TR_PAISES_ID | -> | dbo.PAISES.PAISES_ID |
| FK_TRANSPORTE_TRANSP_DESTINO | dbo.TRANSPORTE.TR_DEST_ID | -> | dbo.TRANSP_DESTINO.DEST_ID |
| FK_TRANSPORTE_TRANSP_TIPO | dbo.TRANSPORTE.TR_TRTP_ID | -> | dbo.TRANSP_TIPO.TRTP_ID |
| FK_TRANSPORTE_TRANSP_TIPO1 | dbo.TRANSPORTE.TR_TRTP_ID_EMB | -> | dbo.TRANSP_TIPO.TRTP_ID |
| FK_TRANSPORTE_VERIFICACAO_ENTIDADE | dbo.TRANSPORTE_VERIFICACAO.TRV_E_ID | -> | dbo.ENTIDADE.E_ID |
| FK_TRANSPORTE_VERIFICACAO_TRANSPORTE | dbo.TRANSPORTE_VERIFICACAO.TRV_TR_ID | -> | dbo.TRANSPORTE.TR_ID |
| FK_VALOR_VALOR_TIPO | dbo.VALOR.VAL_TPVAL_ID | -> | dbo.VALOR_TIPO.TPVAL_ID |
| FK__Velocidad__Atlet__24FD51B3 | dbo.Velocidade.AtletaProvaID | -> | dbo.AtletaProva.IDAtletaProva |
| FK_VendaLojaProduto_PRODUTO | dbo.VendaLojaProduto.p_id | -> | dbo.PRODUTO.P_ID |
| FK_VendaLojaProduto_VendaLoja | dbo.VendaLojaProduto.venda_id | -> | dbo.VendaLoja.venda_id |

## 4. Indices

| tabela | indice | tipo | PK | unico | colunas |
|---|---|---|:--:|:--:|---|
| dbo.ACTUALIZACOES | PK_ACTUALIZACOES | CLUSTERED | Y | Y | ACT_ID |
| dbo.AGENTE_FATURA | PK_AGENTE_FATURA | CLUSTERED | Y | Y | AFT_E_ID, AFT_F_NO |
| dbo.AGENTE_FATURA | _dta_index_AGENTE_FATURA_7_94623380__K3 | NONCLUSTERED |  |  | AFT_CONTABILIZAR |
| dbo.AGENTE_FATURACAO | PK_AGENTE_FATURACAO | CLUSTERED | Y | Y | AF_ID |
| dbo.AGENTE_FATURACAO | _dta_index_AGENTE_FATURACAO_7_834102012__K2_K3_K4_K5 | NONCLUSTERED |  |  | AF_E_ID, AF_ANO, AF_TRIMESTRE, AF_VALOR |
| dbo.AGENTE_FATURACAO | _dta_index_AGENTE_FATURACAO_7_834102012__K3 | NONCLUSTERED |  |  | AF_ANO |
| dbo.AGENTE_FATURACAO | _dta_index_AGENTE_FATURACAO_7_834102012__K3_K2_K4_K5 | NONCLUSTERED |  |  | AF_ANO, AF_E_ID, AF_TRIMESTRE, AF_VALOR |
| dbo.AGENTE_FATURACAO | _dta_index_AGENTE_FATURACAO_7_834102012__K5_K3_K2_K4 | NONCLUSTERED |  |  | AF_VALOR, AF_ANO, AF_E_ID, AF_TRIMESTRE |
| dbo.AGENTE_FATURACAO | _dta_stat_834102012_3_2_4_5 | NONCLUSTERED |  |  | AF_ANO, AF_E_ID, AF_TRIMESTRE, AF_VALOR |
| dbo.AGENTE_FATURACAO | _dta_stat_834102012_5_3_2 | NONCLUSTERED |  |  | AF_VALOR, AF_ANO, AF_E_ID |
| dbo.AGENTE_FATURACAO_UPDATE | PK_AGENTE_FATURACAO_UPDATE | CLUSTERED | Y | Y | AFU_ID |
| dbo.AgenteEncomenda | PK_AgenteEncomenda | CLUSTERED | Y | Y | codEncomenda |
| dbo.AgenteEncomendaEstado | PK_AgenteEncomendaEstado | CLUSTERED | Y | Y | codEstado |
| dbo.AgenteEncomendaProduto | PK_AgenteEncomendaProduto | CLUSTERED | Y | Y | codEncomenda, codProduto |
| dbo.ALARM | PK_ALARM | CLUSTERED | Y | Y | ALARM_ID |
| dbo.ALARM | _dta_index_ALARM_7_254623950__K4 | NONCLUSTERED |  |  | ALARM_DISPENSADO |
| dbo.ALARM | _dta_index_ALARM_7_254623950__K5_K8_K3_1_2 | NONCLUSTERED |  |  | ALARM_ID, ALARM_DESCRICAO, ALARM_OF_ID, ALARM_TALARM_ID, ALARM_DATA |
| dbo.ALARM | _dta_index_ALARM_7_254623950__K5_K8_K3_2 | NONCLUSTERED |  |  | ALARM_DESCRICAO, ALARM_OF_ID, ALARM_TALARM_ID, ALARM_DATA |
| dbo.ALARM | _dta_stat_254623950_5_8_3 | NONCLUSTERED |  |  | ALARM_OF_ID, ALARM_TALARM_ID, ALARM_DATA |
| dbo.ALARM_TIPO | PK_ALARM_TIPO | CLUSTERED | Y | Y | TALARM_ID |
| dbo.ALARM_TIPO_ENTIDADE | PK_ALARM_TIPO_ENTIDADE | CLUSTERED | Y | Y | ATE_TALARM_ID, ATE_E_ID |
| dbo.ARMAZEM | PK_ARMAZEM | CLUSTERED | Y | Y | ARM_ID |
| dbo.ArtigosGrupos | PK_ArtigosGrupos | CLUSTERED | Y | Y | id_orig, id_virtual |
| dbo.AtletaProva | PK__AtletaPr__0DC7AE9163168F20 | CLUSTERED | Y | Y | IDAtletaProva |
| dbo.ATRIB_ATRIB | PK_ATRIB_ATRIB_1 | CLUSTERED | Y | Y | AA_ID |
| dbo.ATRIBUTO | PK_ATRIBUTOS | CLUSTERED | Y | Y | ATRIB_ID |
| dbo.ATTACH_TIPO | PK_ATTACH_TIPO | CLUSTERED | Y | Y | TP_ATCH_ID |
| dbo.AUDIT | PK_AUDIT | CLUSTERED | Y | Y | AUD_ID |
| dbo.AUDIT_TIPO | PK_AUDIT_TIPO | CLUSTERED | Y | Y | AUDT_ID |
| dbo.aux_ValoresProd | PK_aux_ValoresProd | CLUSTERED | Y | Y | id |
| dbo.aux_ValoresProd | _dta_index_aux_ValoresProd_7_716581641__K4 | NONCLUSTERED |  |  | pId |
| dbo.aux_ValoresProd | _dta_index_aux_ValoresProd_7_716581641__K4_6_8_13 | NONCLUSTERED |  |  | fpId, seq, novoCoef, pId |
| dbo.aux_ValoresProd | _dta_index_aux_ValoresProd_7_716581641__K6_K4_8_13 | NONCLUSTERED |  |  | seq, novoCoef, fpId, pId |
| dbo.aux_ValoresProd | _dta_stat_716581641_6_4 | NONCLUSTERED |  |  | fpId, pId |
| dbo.aux_ValoresProducao | PK_aux_ValoresProducao | CLUSTERED | Y | Y | id |
| dbo.auxAnexos | PK_auxAnexos | CLUSTERED | Y | Y | id |
| dbo.auxAnexos | _dta_index_auxAnexos_7_526624919__K2 | NONCLUSTERED |  |  | aux_id |
| dbo.AuxEstado | PK_AuxEstado | CLUSTERED | Y | Y | codEstado |
| dbo.auxOrdemFabrico | PK_auxOrdemFabrico | CLUSTERED | Y | Y | id |
| dbo.auxOrdemFabrico | _dta_index_auxOrdemFabrico_7_590625147__K21 | NONCLUSTERED |  |  | cor_quinas |
| dbo.AVALIACOES_ITEMS | PK_AVALIACOES_ITEMS | CLUSTERED | Y | Y | AITEM_ID |
| dbo.BOATCHOOSER_ANSWER | PK_BOATCHOOSER_ANSWER | CLUSTERED | Y | Y | BCA_ID |
| dbo.BOATCHOOSER_ANSWER | IX_BOATCHOOSER_ANSWER_QUESTION | NONCLUSTERED |  |  | BCA_QUESTION_ID |
| dbo.BOATCHOOSER_ANSWER_PRODUTO | PK_BOATCHOOSER_ANSWER_PRODUTO | CLUSTERED | Y | Y | BCAP_ANSWER_ID, BCAP_PRODUTO_ID |
| dbo.BOATCHOOSER_GROUPS | PK_BOATCHOOSER_GROUPS | CLUSTERED | Y | Y | BCG_ID |
| dbo.BOATCHOOSER_QUESTION | PK_BOATCHOOSER_QUESTION | CLUSTERED | Y | Y | BCQ_ID |
| dbo.BOATCHOOSER_QUIZ | PK_BOATCHOOSER_QUIZZ | CLUSTERED | Y | Y | BCZ_ID |
| dbo.CENTRO_ESTAGIO | PK_CENTRO_ESTAGIO | CLUSTERED | Y | Y | CE_ID |
| dbo.CENTRO_ESTAGIO_DESPESAS | PK_CENTRO_ESTAGIO_DESPESAS | CLUSTERED | Y | Y | CED_ID |
| dbo.CENTRO_MODELOS_QTD | PK_CENTRO_MODELOS_QTD | CLUSTERED | Y | Y | CM_ID |
| dbo.CENTRO_MODELOS_QTD | _dta_index_CENTRO_MODELOS_QTD_7_686625489__K3 | NONCLUSTERED |  |  | CM_NP_ID |
| dbo.CENTRO_RESERVA | PK_CENTRO_RESERVA | CLUSTERED | Y | Y | RES_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K1_K3_K2_13 | NONCLUSTERED |  |  | RES_EQUIPA, RES_ID, RES_CE_ID, RES_E_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K1_K3_K2_13_9987 | NONCLUSTERED |  |  | RES_EQUIPA, RES_ID, RES_CE_ID, RES_E_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K12 | NONCLUSTERED |  |  | RES_FACTURADO |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K2_3_13 | NONCLUSTERED |  |  | RES_CE_ID, RES_EQUIPA, RES_E_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K2_3_13_8066 | NONCLUSTERED |  |  | RES_CE_ID, RES_EQUIPA, RES_E_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K2_K1_3_13 | NONCLUSTERED |  |  | RES_CE_ID, RES_EQUIPA, RES_E_ID, RES_ID |
| dbo.CENTRO_RESERVA | _dta_index_CENTRO_RESERVA_7_718625603__K2_K1_3_13_4364 | NONCLUSTERED |  |  | RES_CE_ID, RES_EQUIPA, RES_E_ID, RES_ID |
| dbo.CENTRO_RESERVA | _dta_stat_718625603_1_3_2 | NONCLUSTERED |  |  | RES_ID, RES_CE_ID, RES_E_ID |
| dbo.CENTRO_RESERVA | _dta_stat_718625603_2_1 | NONCLUSTERED |  |  | RES_E_ID, RES_ID |
| dbo.CENTRO_RESERVA_CHECKLIST | PK_CENTRO_RESERVA_CHECKLIST | CLUSTERED | Y | Y | CRCHKL_CRCHKLI_ID, CRCHKL_RES_ID |
| dbo.CENTRO_RESERVA_CHECKLIST | _dta_index_CENTRO_RESERVA_CHECKLIST_7_750625717__K4 | NONCLUSTERED |  |  | CRCHKL_TRATADO |
| dbo.CENTRO_RESERVA_CHEKLIST_ITEMS | PK_CENTRO_RESERVA_CHEKLIST_ITEMS | CLUSTERED | Y | Y | CRCHKLI_ID |
| dbo.CENTRO_RESERVA_ESTADO | PK_CENTRO_RESERVA_ESTADO | CLUSTERED | Y | Y | TPCR_ID |
| dbo.CENTRO_RESERVA_OFS | PK_CENTRO_RESERVA_OFS | CLUSTERED | Y | Y | RO_RES_ID, RO_OF_ID |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K1_K2_K3_K4 | NONCLUSTERED |  |  | RO_RES_ID, RO_OF_ID, RO_DATA_INI, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K1_K2_K3_K4_8066 | NONCLUSTERED |  |  | RO_RES_ID, RO_OF_ID, RO_DATA_INI, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K2 | NONCLUSTERED |  |  | RO_OF_ID |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K2_K1_K3_K4 | NONCLUSTERED |  |  | RO_OF_ID, RO_RES_ID, RO_DATA_INI, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K2_K1_K3_K4_4364 | NONCLUSTERED |  |  | RO_OF_ID, RO_RES_ID, RO_DATA_INI, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K3_K2_K4_1 | NONCLUSTERED |  |  | RO_RES_ID, RO_DATA_INI, RO_OF_ID, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_index_CENTRO_RESERVA_OFS_7_846626059__K3_K2_K4_1_9987 | NONCLUSTERED |  |  | RO_RES_ID, RO_DATA_INI, RO_OF_ID, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_stat_846626059_2_1_3_4 | NONCLUSTERED |  |  | RO_OF_ID, RO_RES_ID, RO_DATA_INI, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_OFS | _dta_stat_846626059_3_2_4 | NONCLUSTERED |  |  | RO_DATA_INI, RO_OF_ID, RO_DATA_FIM |
| dbo.CENTRO_RESERVA_QUARTOS | PK_CENTRO_RESERVA_QUARTOS | CLUSTERED | Y | Y | CRQ_ID |
| dbo.CENTRO_RESERVA_QUARTOS | _dta_index_CENTRO_RESERVA_QUARTOS_7_878626173__K1 | NONCLUSTERED |  |  | CRQ_ID |
| dbo.CENTRO_RESERVA_TRANSFER | PK_CENTRO_RESERVA_TRANSFER | CLUSTERED | Y | Y | CRT_ID |
| dbo.CENTRO_RESERVA_TRANSFER | _dta_index_CENTRO_RESERVA_TRANSFER_7_910626287__K8 | NONCLUSTERED |  |  | CRT_TRATADO |
| dbo.CENTRO_RESERVA_TRANSFER_RESPONS | PK_CENTRO_RESERVA_TRANSFER_RESPONS | CLUSTERED | Y | Y | CRTR_ID |
| dbo.Competicao | PK__Competic__1074046B1209696A | CLUSTERED | Y | Y | IDCompeticao |
| dbo.COMPONENTE_TIPO | PK_COMPONENTE_TIPO | CLUSTERED | Y | Y | TPCOMP_ID |
| dbo.COMUNICACAO | PK_COMUNICACAO | CLUSTERED | Y | Y | COM_ID |
| dbo.COMUNICACAO_ANEXO | PK_COMUNICACAO_ANEXO | CLUSTERED | Y | Y | COMATCH_ID |
| dbo.CORREIO_FACT | PK_CORREIO_FACT | CLUSTERED | Y | Y | CORRF_ID |
| dbo.CORREIO_FACT | _dta_index_CORREIO_FACT_7_375008417__K1 | NONCLUSTERED |  |  | CORRF_ID |
| dbo.CORREIO_TARIFAS | PK_CORREIO_TARIFAS | CLUSTERED | Y | Y | CT_ID |
| dbo.CORREIO_ZONA_PAIS | PK_CORREIO_ZONA_PAIS | CLUSTERED | Y | Y | CZP_ZONA_ID, CZP_PAIS_ID |
| dbo.CORREIO_ZONAS | PK_CORREIO_ZONAS | CLUSTERED | Y | Y | CZ_ID |
| dbo.DIAS_FERIADOS_FERIAS | PK_DIAS_FERIADOS_FERIAS | CLUSTERED | Y | Y | DFF_ID |
| dbo.DIAS_TRABALHO | PK_DIAS_TRABALHO | CLUSTERED | Y | Y | DTRB_ID |
| dbo.DIAS_TRABALHO | _dta_index_DIAS_TRABALHO_7_1893581784__K1 | NONCLUSTERED |  |  | DTRB_ID |
| dbo.DIAS_TRABALHO | _dta_index_DIAS_TRABALHO_7_1893581784__K1_9987 | NONCLUSTERED |  |  | DTRB_ID |
| dbo.DIAS_TRABALHO | _dta_index_DIAS_TRABALHO_7_1893581784__K2 | NONCLUSTERED |  |  | DTRB_DATA |
| dbo.DIAS_TRABALHO | _dta_index_DIAS_TRABALHO_7_1893581784__K2_2441 | NONCLUSTERED |  |  | DTRB_DATA |
| dbo.DOC | PK_Doc | CLUSTERED | Y | Y | id |
| dbo.DOC_DESCRIPTION | PK_DOC_DESCRIPTION | CLUSTERED | Y | Y | id |
| dbo.DOC_PRODUTO_TIPO | PK_DOC_PRODUTO_TIPO | CLUSTERED | Y | Y | doc_doc_id, produto_tipo_tp_id |
| dbo.DOC_TITLE | PK_DOC_TITLE | CLUSTERED | Y | Y | id |
| dbo.DOC_TYPE | PK_DOC_TYPE | CLUSTERED | Y | Y | id |
| dbo.DOURO_AULA | PK_DOURO_AULA | CLUSTERED | Y | Y | AULA_ID |
| dbo.DOURO_AULA_MONITOR | PK_DOURO_AULA_MONITOR | CLUSTERED | Y | Y | AM_AULA_ID, AM_E_ID |
| dbo.DRAG_BARCO | PK_DRAG_BARCO | CLUSTERED | Y | Y | BARCO_ID |
| dbo.DRAG_VELOCIDADE | PK_DRAG_VELOCIDADE | CLUSTERED | Y | Y | DRAG_ID |
| dbo.ENCOMENDA | PK_ENCOMENDA | CLUSTERED | Y | Y | ENC_ID |
| dbo.ENCOMENDA_ESTADO | PK_ENCOMENDA_ESTADO | CLUSTERED | Y | Y | EE_ID |
| dbo.Encomenda_trk | PK_Encomenda_trk | CLUSTERED | Y | Y | codEncomenda |
| dbo.ENT_CONFIG | PK_ENT_CONFIG | CLUSTERED | Y | Y | ECONF_ID |
| dbo.ENT_ENT_PEDIDO_PROVISORIO | PK_ENT_ENT_PEDIDO_PROVISORIO | CLUSTERED | Y | Y | EEP_ID |
| dbo.ENT_MOV | PK_ENT_MOV | CLUSTERED | Y | Y | MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_6 | NONCLUSTERED |  |  | MOVENT_OBSERVACOES, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K2_K3_K4_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K2_K3_K4_K20_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K20_19 | NONCLUSTERED |  |  | MOVENT_E_E_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K20_19_4364 | NONCLUSTERED |  |  | MOVENT_E_E_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K20_6 | NONCLUSTERED |  |  | MOVENT_OBSERVACOES, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K20_K2_K3_K4_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_ID, MOVENT_FP_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K8_11 | NONCLUSTERED |  |  | MOVENT_CC, MOVENT_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K8_11_6960 | NONCLUSTERED |  |  | MOVENT_CC, MOVENT_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K8_K2_K3_K4_K20_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_ID, MOVENT_DATA_PAG, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K1_K8_K2_K3_K4_K20_5_11_8066 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_ID, MOVENT_DATA_PAG, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K16 | NONCLUSTERED |  |  | MOVENT_DESCONTA_LAMINADOR |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K16_9987 | NONCLUSTERED |  |  | MOVENT_DESCONTA_LAMINADOR |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K16_K2_K3_K4 | NONCLUSTERED |  |  | MOVENT_DESCONTA_LAMINADOR, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2 | NONCLUSTERED |  |  | MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_8066 | NONCLUSTERED |  |  | MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K1_K3_K4_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K1_K3_K4_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_MET_ID, MOVENT_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K20_K4_K3_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K20_K4_K3_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K20_K4_K3_5_19_8066 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K20_K4_K3_5_4364 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_4_5 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K1 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K1_1040 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K1_K4_K20_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K1_K4_K20_K8_5_11_5201 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K4 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K4_K1_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K4_K1_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K3_K4_K1_K20_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K20_K3_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K20_K3_5_19_4149 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_5_1912 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_K20_5_19_5201 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_K20_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K1_K20_K8_5_11_2533 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K20_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K2_K4_K3_K20_5_7022 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20 | NONCLUSTERED |  |  | MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_1_19 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_E_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_1_19_6497 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_E_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K2_K3_K4_K1_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_FP_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_4_5 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_4_5_1771 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_K4 | NONCLUSTERED |  |  | MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_K4_K1_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_K8_1_4_5_11 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_CC, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K2_K8_1_4_5_11_6497 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_CC, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K3_K4_K2_1_5_19 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K2_K3_K1_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2 | NONCLUSTERED |  |  | MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2_1_5_19 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2_5_19_6497 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K20_K4_K3_K2_5_4009 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_FP_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3 | NONCLUSTERED |  |  | MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_2608 | NONCLUSTERED |  |  | MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2_4864 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2_K8_11 | NONCLUSTERED |  |  | MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2_K8_11_1912 | NONCLUSTERED |  |  | MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2_K8_K4_K20_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID, MOVENT_DATA_PAG, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K2_K8_K4_K20_5_11_1410 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID, MOVENT_DATA_PAG, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K4_K2_K20_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K1_K4_K2_K20_K8_5_11_4364 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_1 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_1_4149 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_4_5 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_9850 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4_9987 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4_K1_K20_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4_K1_K20_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4_K20 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K2_K4_K20_K1_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_1_5 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_F, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K1_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K1_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K1_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K1_K20_5_19_1040 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K20_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K20_5_19_1912 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K3_K4_K2_K20_5_7241 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4 | NONCLUSTERED |  |  | MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_3 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_5737 | NONCLUSTERED |  |  | MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K2_K3_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K2_K3_5_4149 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K2_K3_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K2_K3_K20_5_19_9987 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_ID, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K3_2_5 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K1_K3_2_5_6 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_DATA_I, MOVENT_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K20_K3_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K20_K3_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K20_K3_5_19_5201 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K20_K3_5_9987 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K3 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K3_K1_K20_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K3_K20_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K2_K3_K20_5_8341 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_1_5 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_8953 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K1_5_6 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_OBSERVACOES, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K1_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K1_K20_5_19_8066 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K1_K20_K8_5_11 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K1_K20_K8_5_11_8258 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_CC, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K20 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K20_5 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K20_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K2_K20_5_1971 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K20_K2 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID, MOVENT_FP_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K4_K3_K20_K2_5_19 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_FP_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K8_1_11 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_CC, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K8_1_11_9987 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_CC, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K8D_K20_K3_K2_1_4_5_11 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_CC, MOVENT_DATA_PAG, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_index_ENT_MOV_7_1861581670__K8D_K20_K3_K2_1_4_5_11_2894 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_I, MOVENT_DATA_F, MOVENT_CC, MOVENT_DATA_PAG, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_1_20 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_1_20_2_3 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_FP_ID, MOVENT_MET_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_1_8_2 | NONCLUSTERED |  |  | MOVENT_ID, MOVENT_DATA_PAG, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_16_2_3_4 | NONCLUSTERED |  |  | MOVENT_DESCONTA_LAMINADOR, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_stat_1861581670_2_20 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_2_4_20_3 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_FP_ID, MOVENT_E_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_2_4_3_1_20_8 | NONCLUSTERED |  |  | MOVENT_MET_ID, MOVENT_DATA_I, MOVENT_E_ID, MOVENT_ID, MOVENT_FP_ID, MOVENT_DATA_PAG |
| dbo.ENT_MOV | _dta_stat_1861581670_20_3_2 | NONCLUSTERED |  |  | MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_20_4 | NONCLUSTERED |  |  | MOVENT_FP_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_stat_1861581670_3_1_2_8_4 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_ID, MOVENT_MET_ID, MOVENT_DATA_PAG, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_stat_1861581670_3_1_4 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | _dta_stat_1861581670_4_1_2 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_4_3_20 | NONCLUSTERED |  |  | MOVENT_DATA_I, MOVENT_E_ID, MOVENT_FP_ID |
| dbo.ENT_MOV | _dta_stat_1861581670_8_20_3_2 | NONCLUSTERED |  |  | MOVENT_DATA_PAG, MOVENT_FP_ID, MOVENT_E_ID, MOVENT_MET_ID |
| dbo.ENT_MOV | NonClusteredIndex-20191113-140924 | NONCLUSTERED |  |  | MOVENT_DATA_F, MOVENT_MET_ID, MOVENT_E_ID, MOVENT_DATA_I |
| dbo.ENT_MOV | NonClusteredIndex-20191119-102319 | NONCLUSTERED |  |  | MOVENT_E_ID, MOVENT_DATA_F, MOVENT_E_E_ID, MOVENT_FP_ID, MOVENT_MET_ID, MOVENT_DATA_I |
| dbo.ENT_MOV_TIPO | PK_ENT_MOV_TIPO | CLUSTERED | Y | Y | MET_ID |
| dbo.ENT_TIPO_VINCULO | PK_ENT_TIPO_VINCULO | CLUSTERED | Y | Y | TV_ID |
| dbo.ENT_TP_PROD | PK_ENT_TP_PROD | CLUSTERED | Y | Y | ETP_E_ID, ETP_TP_ID |
| dbo.ENT_TP_PROD | _dta_index_ENT_TP_PROD_7_1874105717__K1_K2_5 | NONCLUSTERED |  |  | ETP_BRAND_MANAGER, ETP_E_ID, ETP_TP_ID |
| dbo.ENT_TP_PROD | _dta_index_ENT_TP_PROD_7_1874105717__K2_K1_5 | NONCLUSTERED |  |  | ETP_BRAND_MANAGER, ETP_TP_ID, ETP_E_ID |
| dbo.ENT_TP_PROD | _dta_index_ENT_TP_PROD_7_1874105717__K5 | NONCLUSTERED |  |  | ETP_BRAND_MANAGER |
| dbo.ENTIDADE | PK_ENTIDADE | CLUSTERED | Y | Y | E_ID |
| dbo.ENTIDADE | _dta_index_ENTIDADE_7_1349579846__K1 | NONCLUSTERED |  |  | E_ID |
| dbo.ENTIDADE | NonClusteredIndex-20180227-111227 | NONCLUSTERED |  |  | E_ACTIVO, E_FP_ID |
| dbo.ENTIDADE_DADOS | PK_ENTIDADE_DADOS | CLUSTERED | Y | Y | EDADOS_ID |
| dbo.ENTIDADE_EQUIPA | PK_ENTIDADE_EQUIPA | CLUSTERED | Y | Y | EEQ_ID |
| dbo.ENTIDADE_FASE | PK_ENTIDADE_FASE | CLUSTERED | Y | Y | EFP_ID |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K2 | NONCLUSTERED |  |  | EFP_E_ID |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K2_K3_K9_K5 | NONCLUSTERED |  |  | EFP_E_ID, EFP_FP_ID, EFP_QUALIFICADO, EFP_DATAFIM |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K2_K3_K9_K5_9987 | NONCLUSTERED |  |  | EFP_E_ID, EFP_FP_ID, EFP_QUALIFICADO, EFP_DATAFIM |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K2_K9_3 | NONCLUSTERED |  |  | EFP_FP_ID, EFP_E_ID, EFP_QUALIFICADO |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K2_K9_K5_K3 | NONCLUSTERED |  |  | EFP_E_ID, EFP_QUALIFICADO, EFP_DATAFIM, EFP_FP_ID |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K3_K9_2_5 | NONCLUSTERED |  |  | EFP_E_ID, EFP_DATAFIM, EFP_FP_ID, EFP_QUALIFICADO |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K3_K9_K5_K2 | NONCLUSTERED |  |  | EFP_FP_ID, EFP_QUALIFICADO, EFP_DATAFIM, EFP_E_ID |
| dbo.ENTIDADE_FASE | _dta_index_ENTIDADE_FASE_7_706101556__K9 | NONCLUSTERED |  |  | EFP_QUALIFICADO |
| dbo.ENTIDADE_FASE | _dta_stat_706101556_2_3_9_5 | NONCLUSTERED |  |  | EFP_E_ID, EFP_FP_ID, EFP_QUALIFICADO, EFP_DATAFIM |
| dbo.ENTIDADE_FASE | _dta_stat_706101556_3_9 | NONCLUSTERED |  |  | EFP_FP_ID, EFP_QUALIFICADO |
| dbo.ENTIDADE_FASE | _dta_stat_706101556_3_9_5 | NONCLUSTERED |  |  | EFP_FP_ID, EFP_QUALIFICADO, EFP_DATAFIM |
| dbo.ENTIDADE_MORADA | PK_ENTIDADE_MORADA | CLUSTERED | Y | Y | EM_ID |
| dbo.ENTIDADE_MORADA | _dta_index_ENTIDADE_MORADA_7_1470628282__K1_3_4_9 | NONCLUSTERED |  |  | EM_CONTACTO, EM_MORADA, EM_TELEFONE, EM_ID |
| dbo.ENTIDADE_MORADA | _dta_index_ENTIDADE_MORADA_7_1470628282__K7 | NONCLUSTERED |  |  | EM_DEFAULT |
| dbo.ENTIDADE_MORADA | _dta_index_ENTIDADE_MORADA_7_1470628282__K7_3_4_9 | NONCLUSTERED |  |  | EM_CONTACTO, EM_MORADA, EM_TELEFONE, EM_DEFAULT |
| dbo.ENTIDADE_MORADA | _dta_index_ENTIDADE_MORADA_7_1470628282__K7_K1_3_4_9 | NONCLUSTERED |  |  | EM_CONTACTO, EM_MORADA, EM_TELEFONE, EM_DEFAULT, EM_ID |
| dbo.ENTIDADE_MORADA | _dta_stat_1470628282_7_1 | NONCLUSTERED |  |  | EM_DEFAULT, EM_ID |
| dbo.ENTIDADE_MORADA_TIPO | PK_ENTIDADE_MORADA_TIPO | CLUSTERED | Y | Y | EMT_ID |
| dbo.ENTIDADE_OBS | PK_ENTIDADE_OBS | CLUSTERED | Y | Y | EOBS_ID |
| dbo.ENTIDADE_OBS | _dta_index_ENTIDADE_OBS_7_1534628510__K9 | NONCLUSTERED |  |  | EOBS_CERTIFICADO |
| dbo.ENTIDADE_OBS | NonClusteredIndex-20191113-141032 | NONCLUSTERED |  |  | EOBS_E_ID, EOBS_EOBSTP_ID, EOBS_DATA |
| dbo.ENTIDADE_OBS_ITEM | PK_ENTIDADE_OBS_ITEM | CLUSTERED | Y | Y | EOBSITEM_ID |
| dbo.ENTIDADE_OBS_ITEM | _dta_index_ENTIDADE_OBS_ITEM_7_349960323__K5 | NONCLUSTERED |  |  | EOBSITEM_EOBS_ID |
| dbo.ENTIDADE_OBS_TIPO | PK_ENTIDADE_OBS_TIPO | CLUSTERED | Y | Y | EOBSTP_ID |
| dbo.ENTIDADE_PHC | PK_ENTIDADE_PHC | CLUSTERED | Y | Y | EPHC_ID |
| dbo.ENTIDADE_PHC_FACT | _dta_index_ENTIDADE_PHC_FACT_7_269960038__K4 | NONCLUSTERED |  |  | EPHCF_DIA |
| dbo.ENTIDADE_PHC_FACT | NonClusteredIndex-20191106-120356 | NONCLUSTERED |  |  | EPHCF_ANO, EPHCF_MES, EPHCF_TP_ID_DISCIP, EPHCF_FACTURADO, EPHCF_EPHC_ID |
| dbo.ENTIDADE_PONTOS | PK_ENTIDADE_PONTOS_1 | CLUSTERED | Y | Y | EP_ID |
| dbo.ENTIDADE_PONTOS | _dta_index_ENTIDADE_PONTOS_7_1598628738__K9 | NONCLUSTERED |  |  | EP_PREMIO |
| dbo.ENTIDADE_SUB | PK_ENTIDADE_SUB | CLUSTERED | Y | Y | e_master_id, e_sub_id |
| dbo.ENTIDADE_TIPO | PK_ENTIDADE_TIPO | CLUSTERED | Y | Y | ENT_ID |
| dbo.ENTIDADE_TREINOS | PK_ENTIDADE_TREINOS | CLUSTERED | Y | Y | ETR_ID |
| dbo.EQUIPA | PK_EQUIPA | CLUSTERED | Y | Y | EQ_ID |
| dbo.ESTACAO | PK_ESTACAO | CLUSTERED | Y | Y | EST_ID |
| dbo.EstadoOFAgente | PK_EstadoOFAgente | CLUSTERED | Y | Y | codEstado |
| dbo.exports | PK__exports__3213E83FCE178B17 | CLUSTERED | Y | Y | id |
| dbo.failed_import_rows | PK__failed_i__3213E83FECAF3EC7 | CLUSTERED | Y | Y | id |
| dbo.failed_jobs | PK__failed_j__3213E83F8474B4D4 | CLUSTERED | Y | Y | id |
| dbo.failed_jobs | failed_jobs_uuid_unique | NONCLUSTERED |  | Y | uuid |
| dbo.FASES_PRODUCAO | PK_FASES_PRODUCAO | CLUSTERED | Y | Y | FP_ID |
| dbo.FATURA | PK__FATURA__3213E83F73E7CD1E | CLUSTERED | Y | Y | fat_id |
| dbo.FP_FP | PK_FP_FP | CLUSTERED | Y | Y | FPFP_FP_ID, FPFP_FP_FP_ID |
| dbo.GASTOS_CACHE | PK_GASTOS_CACHE_1 | CLUSTERED | Y | Y | id_master |
| dbo.IDEIA | PK_IDEIA | CLUSTERED | Y | Y | ID_ID |
| dbo.IDEIA_CLASSIFICACAO | PK_IDEIA_CLASSIFICACAO | CLUSTERED | Y | Y | IDCL_ID |
| dbo.IDEIA_COLAB | PK_IDEIA_COLAB | CLUSTERED | Y | Y | IDCOL_ID |
| dbo.IDEIA_DOC | PK_IDEIA_DOC | CLUSTERED | Y | Y | IDDOC_ID |
| dbo.IDEIA_ENTIDADE | PK_IDEIA_ENTIDADE | CLUSTERED | Y | Y | IDENT_ID_ID, IDENT_E_ID |
| dbo.IDEIA_ESTADO | PK_IDEIA_ESTADO | CLUSTERED | Y | Y | IDEST_ID |
| dbo.IDEIA_EVOL | PK_IDEIA_EVOL | CLUSTERED | Y | Y | IDEV_ID |
| dbo.IDEIA_REUNIAO | PK_IDEIA_REUNIAO | CLUSTERED | Y | Y | IDR_ID |
| dbo.IDEIA_TAREFA | PK_IDEIA_TAREFA | CLUSTERED | Y | Y | IDTAR_ID |
| dbo.IDEIA_TAREFA | _dta_index_IDEIA_TAREFA_7_2062630391__K11 | NONCLUSTERED |  |  | IDTAR_DESVIO |
| dbo.IDEIA_TPCOL | PK_IDEIA_TPCOL | CLUSTERED | Y | Y | TPCOL_ID |
| dbo.IMPORT | PK_IMPORT | CLUSTERED | Y | Y | ID |
| dbo.IMPORT | _dta_index_IMPORT_7_2126630619__K1 | NONCLUSTERED |  |  | ID |
| dbo.imports | PK__imports__3213E83F9E18C121 | CLUSTERED | Y | Y | id |
| dbo.INTERVALO | PK_INTERVALO | CLUSTERED | Y | Y | INTERVALO_ID |
| dbo.IOT_SENSOR | PK_IOT_SENSOR | CLUSTERED | Y | Y | SENSOR_ID |
| dbo.IOT_SENSOR_ALARM | PK__IOT_SENS__693EA2A87C41190E | CLUSTERED | Y | Y | SA_ID |
| dbo.IOT_SENSOR_DATA | PK_IOT_SENSOR_DATA | CLUSTERED | Y | Y | SD_ID |
| dbo.IOT_SENSOR_DATA | IX_IOT_SENSOR_DATA_DATE | NONCLUSTERED |  |  | SD_DATE |
| dbo.IOT_SENSOR_DATA | IX_IOT_SENSOR_DATA_SENSOR | NONCLUSTERED |  |  | SD_SENSOR_ID |
| dbo.IOT_SENSOR_TIPO | PK_IOT_SENSOR_TIPO | CLUSTERED | Y | Y | ST_ID |
| dbo.job_batches | job_batches_id_primary | CLUSTERED | Y | Y | id |
| dbo.KPI | PK_KPI | CLUSTERED | Y | Y | KPI_ID |
| dbo.KPI_OBJECTIVO | PK_KPI_OBJECTIVO | CLUSTERED | Y | Y | KPIO_ID |
| dbo.LACAGEM | PK_LACAGEM | CLUSTERED | Y | Y | LAC_ID |
| dbo.LISTA | PK_LISTA | CLUSTERED | Y | Y | L_ID |
| dbo.LISTA_COORDENADAS | PK_LISTA_COORDENADAS | CLUSTERED | Y | Y | LCOORD_ID |
| dbo.LISTA_MOVIMENTO | PK_LISTA_MOVIMENTO | CLUSTERED | Y | Y | LM_ID |
| dbo.LISTA_PRODUTO | PK_LISTA_PRODUTO | CLUSTERED | Y | Y | LP_L_ID, LP_P_ID |
| dbo.LISTA_PRODUTO | _dta_index_LISTA_PRODUTO_7_1170103209__K13 | NONCLUSTERED |  |  | LP_EXTRA |
| dbo.LISTA_TIPO | PK_PRODUTO_LISTA_TIPO | CLUSTERED | Y | Y | LTP_ID |
| dbo.logs_web | PK_logs_web | CLUSTERED | Y | Y | codLog |
| dbo.logs_web | _dta_index_logs_web_7_171147655__K1 | NONCLUSTERED |  |  | codLog |
| dbo.MAILS | PK_MAILS | CLUSTERED | Y | Y | MAIL_ID |
| dbo.MEDIDAS | PK_MEDIDAS | CLUSTERED | Y | Y | MED_ID |
| dbo.Meeting | PK_Meeting | CLUSTERED | Y | Y | codConvidado |
| dbo.Meeting | _dta_index_Meeting_7_336056283__K15 | NONCLUSTERED |  |  | quarto_reservado |
| dbo.MeetingEstado | PK_MeetingEstado | CLUSTERED | Y | Y | codEstado |
| dbo.migrations | PK__migratio__3213E83F6C3139E9 | CLUSTERED | Y | Y | id |
| dbo.MOLDES | PK_MOLDES | CLUSTERED | Y | Y | MLD_ID |
| dbo.MOLDES_MOV | PK_MOLDES_MOV | CLUSTERED | Y | Y | MLDU_ID |
| dbo.MOLDES_MOV | _dta_index_MOLDES_MOV_7_363148339__K1 | NONCLUSTERED |  |  | MLDU_ID |
| dbo.MOLDES_TIPO | PK_MOLDES_TIPO | CLUSTERED | Y | Y | MLDTP_ID |
| dbo.MOVIMENTO | PK_MOVIMENTOS | CLUSTERED | Y | Y | MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1 | NONCLUSTERED |  |  | MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_13 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_13_1912 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_13_30 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_13_30_1912 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_13_31_35 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_16 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_2_4_8_12_13 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_E_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_6497 | NONCLUSTERED |  |  | MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_7_29 | NONCLUSTERED |  |  | MOV_DESCONTO, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13_4_15 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_MOV_ID, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13_K15 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K13_K30_K26_4_8_15 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_MOV_ID, MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K13_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K13_4_6_8_14_6497 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K13_K14_K2_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K13_K30_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K13_K30_K14_4_4864 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K4 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K4_K13_K14_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K26_K4_K13_K14_K12_K28_K31 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K11_K30_K26_K13_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_OF_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14_2 | NONCLUSTERED |  |  | MOV_DATA, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14_K2_K11_K26_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14_K28_K29_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14_K28_K29_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K13_K14_K28_K31_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29_K13_K16_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29_K13_K28_K26_4_5_8_31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29_K13_K28_K26_K15_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K14_K29_K13_K28_K26_K15_K16_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K19_K13_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K19_K13_K14_K28_K31_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K12_K34_2_3_4_5_8_13_14_16_22_25_27_28_31_32_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA_APROVADO, MOV_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_1912 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_4_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_4_14_8066 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_4_8576 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K14_K30_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_TPMOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K14_K30_K15_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_TPMOV_ID, MOV_ATRIB_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K15_4_22 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_4_6_8_14_8258 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_K30_4_8066 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_K30_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K26_K30_K14_4_2894 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K30 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K30_4_4364 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K11_K30_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K12_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K12_K14_K29_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K12_K19_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K12_K29_K16_K14_K28_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_4_16 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K12_K2_K3_K34_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K12_K28_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K12_K28_K31_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K12_K28_K31_K4 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K16_K2_K12_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K2_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K14_K2_K11_K26_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K15_K11_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K15_K11_K30_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_OF_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K15_K4_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K15_K4_6_30_4149 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K19_K12_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_TR_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K26_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K28_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K28_K26_K15_K12_K14_K29_K16_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K30_K11_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K30_K11_K15_K14_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K30_K11_K26_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K30_K11_K26_K14_4_6497 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K30_K11_K26_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K31_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_P_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K31_K12_K29_K14_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K31_K12_K29_K14_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K13_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ID, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K11 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K11_4_13 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K11_4_6_13_30 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_P_ID, MOV_ATRIB_ID, MOV_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K11_K30_K15_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ATRIB_ID, MOV_MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K13_K28_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_P_ID, MOV_SATISFEITO, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K2_4_5_8_13_34 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K2_K28_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K2_K28_K15_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K28_K2_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K28_K2_K15_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_DATA, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K12_K29_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K13_4_16 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K13_K2_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K15 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K15_K30_K11_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_TPMOV_ID, MOV_MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28_K12_K29 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28_K12_K29_K16_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28_K12_K29_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K28_K12_K29_K31_K13_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K29_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K14_K29_K12_K13_K15_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K13 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K13_K12_K14_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K13_K4_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K13_K4_6_30_8066 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K14_K13 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4_30_9987 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4_K13_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4_K13_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K15_K4_K13_6_30_4364 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K16 | NONCLUSTERED |  |  | MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K16_K12_K29_K14_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K16_K12_K29_K14_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K16_K13_K14_K28_K29_K12_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_ARM_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K19 | NONCLUSTERED |  |  | MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K19_K13_K12_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_TR_ID, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K19_K14_K16_K2_K13_K12_K34_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ID, MOV_TR_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K19_K28_K31_4_8_30 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_TR_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K2_3_5_6_7_8_12_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_6 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_6_8 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_6_8_4364 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_K15_K4_K13_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K26_K30_K11_K13_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_29_37 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_K13_K14_K12_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_K13_K14_K12_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_K31_K4 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K28_K31_K4_K13_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K12_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K12_K14_K16 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K12_K14_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K12_K14_K28_13_16_31_35 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K12_K16_K13_K14_K28_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ARM_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K14_16 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K14_K12_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K28_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_ID_PEDIDO, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K28_K14_K12_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K29_K28_K14_K12_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_TPMOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_1040 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_6 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K11_K13 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K11_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K11_K13_4_6497 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K11_K15_K14_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K13_K11 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K13_K11_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K13_K11_4_5201 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K13_K11_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K26_9987 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K26_K13_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K30_K26_K13_K14_4_5201 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K31_K28 | NONCLUSTERED |  |  | MOV_ID, MOV_SHOP_ORDER_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K31_K28_K13_K14_K2_K11_K26_K12_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K34_K12_2_3_4_5_8_13_14_16_22_25_27_28_31_32_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA_APROVADO, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K34_K12_2_3_4_5_8_13_14_16_22_25_27_28_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_DATA_APROVADO, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_6 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_6_1040 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K11_K26 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K11_K26_K13_K14_K12 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K11_K26_K13_K14_K12_K28_K31 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K12_K13_K31_K11_K26_K28_K2_K14_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ID, MOV_QUANTIDADE, MOV_E_ID, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_SATISFEITO, MOV_DATA, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K15 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K15_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K15_30_1771 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K15_6_13_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_P_ID, MOV_ATRIB_ID, MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K15_6_13_30_5201 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_P_ID, MOV_ATRIB_ID, MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K31_K28 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_SHOP_ORDER_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K1_K4_K31_K28_K13_K14 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11 | NONCLUSTERED |  |  | MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_13 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_13_30 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_13_30_8066 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_4_13 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_4_13_14 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_4_13_14_5201 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_1_4_13_30 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_6355 | NONCLUSTERED |  |  | MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_4364 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_2203 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_4_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_4_14_9987 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_4_5379 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K15_K30_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K26_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K26_4_6_8_14_1040 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K26_K30_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K26_K30_K14_4_6960 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K30 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K30_4_4149 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K13_K30_K26_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K15_K13 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K15_K13_K30_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_OF_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K26_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K30_K13 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_ATRIB_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K30_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K1_K30_K13_4_1912 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_1771 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1_K15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1_K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1_K15_4_22 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1_K15_4_22_1771 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K1_K26 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K15_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_MOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K26_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K30_K1_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K13_K30_K1_4_6_4149 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K14_K1_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_TPMOV_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K14_K1_K13_K30_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K14_K1_K13_K30_K15_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K14_K30_K1_K15_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_TPMOV_ID, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K15_K13_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_MOV_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_1_4_6_8_13_14 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_1_4_6_8_13_14_2533 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K13_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K13_4_6_8_14_1912 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K13_K14_K2_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K4 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K4_K13_K14_K12 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K1_K4_K13_K14_K12_K28_K31 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K14_K1_K13_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K14_K1_K13_K30_4_1410 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K30_K1_K13_4_6_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_TPMOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K26_K30_K1_K13_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K30_K1_K15_K14_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K11_K30_K1_K15_K14_K13_4_6_5492 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OF_ID, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12 | NONCLUSTERED |  |  | MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_4364 | NONCLUSTERED |  |  | MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14_K29 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14_K29_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14_K29_K13_K16_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14_K29_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K14_K29_K31_K13_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K15_K13_K14_K28_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_E_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K19_K13_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_E_ID, MOV_ID, MOV_TR_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K1_K34_2_3_4_5_8_13_14_16_22_25_27_28_31_32_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA_APROVADO, MOV_E_ID, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_1 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1_6478 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1_K2_K11_K26_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1_K28_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_SATISFEITO, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1_K28_K29_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K1_K28_K31_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K14_K2_K3_K1_K34_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_DATASAIDA, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K15_K1_K14_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K13_K32_K2_K4_K1_K11_K15_K19_K3_K20_K16_K29_K31_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_E_ID, MOV_P_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_1 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K1 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K1_K16_K2_K13_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K1_K16_K29_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K1_K19_K13_K2_3_4_5_6_7_8 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_TR_ID, MOV_P_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K1_K29_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K28_K1_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_E_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K13_K28_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K13_K28_K26_4_5_8_31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K13_K28_K26_K15_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K13_K28_K26_K15_2_4_5_8_31_9910 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K13_K28_K26_K15_K16_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K1_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K14_K29_K13_K15_K1_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K16_K29_K1_K13_K14_K28_K31_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K2_K14_K1_K13 | NONCLUSTERED |  |  | MOV_E_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K13_K14_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14_K13_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14_K28_13_16_31_35 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K1_K14_K31_K13_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K13_K14_K28_1_16_31 | NONCLUSTERED |  |  | MOV_ID, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_1 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_K1 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_K1_K13_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_K1_K13_28_4149 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_K1_K13_K28_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K14_K1_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K16_K1_K13_K14_K28_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K16_K31_K14_K28_1_13_35 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K29_K31_K14_K28_K16_1_13_35 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_SHOP_SHIPPING, MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K34 | NONCLUSTERED |  |  | MOV_E_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K34_K40 | NONCLUSTERED |  |  | MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_FP_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K12_K40_K34 | NONCLUSTERED |  |  | MOV_E_ID, MOV_FP_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13 | NONCLUSTERED |  |  | MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_1 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_1_4_15_22 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID, MOV_QTD_BAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_2894 | NONCLUSTERED |  |  | MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_8066 | NONCLUSTERED |  |  | MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K11_K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K12_K14_K29_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_P_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K12_K29_K16_K14_K28_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_P_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K14_K16_K2_K12_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_P_ID, MOV_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K11_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K11_4_22 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K12_K14_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K34_K14_K12_K28_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K4_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K15_K4_6_30_6497 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K19_K12_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_P_ID, MOV_ID, MOV_TR_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K28_K26_4_5_8_31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K28_K26_K12_K14_K29_4_5_8_31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K28_K26_K12_K14_K29_K15_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K28_K26_K12_K14_K29_K15_K16_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K30_K11_K15_K14_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_P_ID, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K30_K11_K26_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_P_ID, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K34_K14_K12_K2_4_5_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K34_K14_K12_K2_K28_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K34_K14_K12_K2_K28_K15_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K34_K14_K12_K2_K3_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K1_K34_K14_K12_K2_K3_4_5_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_1_4_15 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_1_4_15_22 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID, MOV_QTD_BAL, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_4_15 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_6497 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K15 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K15_4_22 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K15_K30_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K26 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K26_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K26_4_6_8_14_8066 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K26_K30_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K26_K30_K14_4_2533 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K30 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K30_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K11_K1_K30_4_8066 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K12_K14_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K12_K14_K1_K2_K11_K26_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K12_K2_K14_K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_E_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_4_8258 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_6960 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_2_3_4_5_6_7_8_12_16_24_25_27 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_LOTE, MOV_ACERTO, MOV_DEFEITUOSO, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_4_16 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ARM_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_K12 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_K12_K28_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_K12_K28_K29_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_K2_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K1_K2_K11_K26_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K11_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K11_K1_K26_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K11_K1_K26_K30_4_1040 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K11_K1_K30_K15_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_ATRIB_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_2 | NONCLUSTERED |  |  | MOV_DATA, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_K2_K3_K34_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_DATA, MOV_DATASAIDA, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_K28_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_K28_K31_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_K28_K31_K4 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K1_K28_K31_K4_8258 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K12_K28_K31_K1_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K15_K1_K12_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K16_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K11_K26_K12_K28_K31_K1_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_K1_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_K1_8_5492 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_K1_K11_K26_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_K1_K11_K26_K12_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K2_K4_K1_K11_K26_K12_K28_K31_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K28_K1_K29_K12_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K28_K1_K29_K12_K16_31_8341 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K28_K12_K1_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_3923 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_K1_K11_K26 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_K1_K11_K26_8337 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_K1_K11_K26_K12 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K4_K1_K11_K26_K12_K28_K31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K14_K5_1_2_3 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_DATASAIDA, MOV_P_ID, MOV_TPMOV_ID, MOV_PRECOUNITARIO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_1_2_4 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_MOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K1_2_4 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_P_ID, MOV_MOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K1_K12_K14_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K1_K16_K12_K14_K29_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K11_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_MOV_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K15_K16_K14_K29_K12_K28_K26_1_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K16_K14 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ARM_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K16_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ARM_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K26_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K26_K1_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K26_K1_K30_K11_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K26_K11_K1_4_8_15_30 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K28_K26_1_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K28_K26_K12_K14_K29_1_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K28_K26_K12_K14_K29_K15_1_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K28_K26_K12_K14_K29_K15_K16_1_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K2D_K4_K1_K11_K15_K12_K19_K3_K20_K16_K29_K31_K32_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_P_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K2D_K4_K1_K11_K15_K19_K3_K20_K16_K29_K31_K32_5_8_12_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_E_ID, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_P_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K30_K11_K1_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K31_K1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K31_K1_K12_K16_K29_K14_K28_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K32 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K32_K12_K2_K4_K1_K11_K15_K19_K3_K20_K16_K29_K31_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_P_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_E_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K13_K32_K2_K4_K1_K11_K15_K12_K19_K3_K20_K16_K29_K31_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_P_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14 | NONCLUSTERED |  |  | MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_9987 | NONCLUSTERED |  |  | MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K16_K2_K13_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K16_K29_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K29 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K29_K13_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K29_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K12_K29_K16_K28_K13_31_35_1973 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K13_K2_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K15 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K15_K30_K11_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_TPMOV_ID, MOV_ID, MOV_MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K16_K2_K13_K12_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K29_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K1_K29_K12_K16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K11_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K11_K1_K13 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K11_K1_K13_K30_K15_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_TPMOV_ID, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_4149 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K13 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K13_K2_K3_K34_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_P_ID, MOV_DATA, MOV_DATASAIDA, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K13_K28_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K29 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K29_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_ID_PEDIDO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K29_K13_K16_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K29_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K1_K29_K31_K13_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K13_K1_K34_K2_4_5_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_E_ID, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K13_K1_K34_K2_K28_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_E_ID, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K13_K1_K34_K2_K28_K15_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_E_ID, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K2_K3_K13_K1_K34_4_5_7_8_29 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K2_K3_K13_K1_K34_4_5_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K28_K13_K1_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K13_28 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K13_K16_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K13_K28_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K12_K29_K1_K31_K13_K16_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_2894 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_4_2533 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K1_2_3_4_5_6_7_8_12_16_24_25_27 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_LOTE, MOV_ACERTO, MOV_DEFEITUOSO, MOV_TPMOV_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K1_4_16 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ARM_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K1_K2_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_TPMOV_ID, MOV_P_ID, MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K1_K2_3_4_5_6_7_8_12_16_25_27_1912 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_TPMOV_ID, MOV_P_ID, MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K11_K1_K26_K30_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K11_K1_K26_K30_4_1771 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K12_K1_K28_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_P_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K12_K1_K28_K31_K19_2_4_8_30 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K12_K1_K34_K2_K28_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_P_ID, MOV_E_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K16_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K16_4_2894 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K16_K15_K1_K12_K29_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_ARM_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K2_K1_K11_K26_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_P_ID, MOV_DATA, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K13_K5_1_2_3 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_DATASAIDA, MOV_TPMOV_ID, MOV_P_ID, MOV_PRECOUNITARIO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K15_K1_K29_K12_K2_K13_K28_K32_3_4_5_8_31_34 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_MOV_ID, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_DATA, MOV_P_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K15_K1_K30_K11_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_TPMOV_ID, MOV_MOV_ID, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K16_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_ARM_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K16_K29_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K16_K29_K1_K28 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K16_K29_K1_K28_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K16_K29_K1_K28_K12_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K2_K16_K1_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_DATA, MOV_ARM_ID, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K2_K16_K1_K12_K13_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ARM_ID, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K2_K16_K1_K13_K12_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_1 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K1_K12_K16_K29_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K1_K12_K29_K16_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K1_K12_K29_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K12_K29_K16_K1_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K12_K29_K16_K1_K13_31_35_9850 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K28_K31_K12_K16_K29_K1_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12_2_3_4_5_8_13_15_16_28_31_32_34_35 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_E_ID_RESPONSAVEL, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12_K13_K28_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K12_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K16_K12_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K1_K16_K12_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K12_1 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K12_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K12_K1_K13_K15_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K12_K1_K13_K15_K16_K28_K26_2_4_5_8_31_8809 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K16_K1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K16_K1_K28 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K16_K1_K28_K12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K29_K16_K1_K28_K12_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K14_K34_K13_K12_K1_K2_K28_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_TPMOV_ID, MOV_E_ID_RESPONSAVEL, MOV_P_ID, MOV_E_ID, MOV_ID, MOV_DATA, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15 | NONCLUSTERED |  |  | MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_1240 | NONCLUSTERED |  |  | MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_4_8066 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K1_K13_K4_6_30 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_MOV_ID, MOV_ID, MOV_P_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K1_K13_K4_6_30_2533 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_MOV_ID, MOV_ID, MOV_P_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K1_K4_K13_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_MOV_ID, MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K11 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K11_K13_K1 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K11_K13_K1_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K11_K13_K1_4_22 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_QTD_BAL, MOV_MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K13_K1_K12_K14_K29_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_MOV_ID, MOV_P_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K13_K14_K12_K1_K28_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K13_K14_K12_K1_K28_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K30_K11_K1_K14_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K15_K30_K11_K1_K26_K13_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16 | NONCLUSTERED |  |  | MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K12_K14_K2 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K12_K14_K2_K13_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ARM_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_DATA, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K12_K29_K14_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ARM_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K12_K29_K14_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ARM_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K13_K12_K34_K19_K14_K2_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K1_K13_K14_K28_K29_K12_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K1 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K1_K2_K13_K12_K34_K19_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K13 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ARM_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K13_K15_K1_K12_K29_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ARM_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K29_K1 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K29_K1_K12_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K14_K29_K1_K12_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K29_K1_K14 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K29_K1_K14_K28 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K29_K1_K14_K28_K12 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K16_K29_K1_K14_K28_K12_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K19_1 | NONCLUSTERED |  |  | MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K19_1_2_4_8_12_13 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_E_ID, MOV_P_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K19_K1 | NONCLUSTERED |  |  | MOV_TR_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K19_K1_K13_K12_2_4_8 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_TR_ID, MOV_ID, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K19_K1_K14_K16_K2_K13_K12_K34_4_8_40 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_FP_ID, MOV_TR_ID, MOV_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2 | NONCLUSTERED |  |  | MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2_K14_K12_K3_1_4_5_7_8_29_34 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_TPMOV_ID, MOV_E_ID, MOV_DATASAIDA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2_K14_K12_K3_1_4_5_8_34 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_TPMOV_ID, MOV_E_ID, MOV_DATASAIDA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2_K14_K12_K3_K13_1_4_5_7_8_29_34 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_DESCONTO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_TPMOV_ID, MOV_E_ID, MOV_DATASAIDA, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_1_4_6 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_1_6 | NONCLUSTERED |  |  | MOV_ID, MOV_PRECOVENDA, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_1_6_8 | NONCLUSTERED |  |  | MOV_ID, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_1_6_8_9987 | NONCLUSTERED |  |  | MOV_ID, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_6980 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_4960 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_6 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_6_8 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_6_8_4149 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_8_30 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K11_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K11_K13 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K11_K13_4_6_8_14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K11_K13_4_6_8_14_1410 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K11_K13_4_8_15_30 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K13 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K13_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K13_K30_K11_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K30 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K30_1563 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K30_K11_K13_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K30_K11_K13_K14_4_4364 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K1_K30_K11_K13_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K11_K1_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K11_K13_K1_K15_K4_30 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K11_K14_K1_K13_K30_15 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K13_K14 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K13_K14_4364 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K13_K14_K2_K1_K11_K12_K28_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID, MOV_OF_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K30_K1_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K30_K1_K13_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K30_K1_K13_K11_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K26_K30_K1_K13_K11_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28 | NONCLUSTERED |  |  | MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_29_37 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_K13_K14_K12_K15_4_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_DATA_APROVADO, MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_K13_K14_K12_K15_K34_K2_4_5_8_29_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_ID_PEDIDO, MOV_DATA_APROVADO, MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_K29_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_K29_K14_K12_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K1_K29_K14_K12_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K12_K16_K29_K1_K14_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_SATISFEITO, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K12_K29_K16_K1_K14_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K13_K14_K2_K1_K11_K26_K12_K31_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K26_K13_1_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K26_K13_K1 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K26_K13_K1_K15_K12_K14_K29_K16_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K26_K13_K15_K14_K29_K12_K16_1_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K29_K1 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K29_K1_K13_K14_K12_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K31_K1_K19_4_8_30 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K31_K1_K4 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K28_K31_K1_K4_K13_K14 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29 | NONCLUSTERED |  |  | MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K1_K14_16 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K1_K14_K28_16 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K1_K14_K28_K12_16 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K1_K14_K28_K12_K13_16_31_35 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1_K13_K28_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1_K16_K28_K13_31_35_6980 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K12_K14_K1_K16_K28_K31_K13_35_7903 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K13_K15_K1_K12_K14_K16_K28_K26_2_4_5_8_31 | NONCLUSTERED |  |  | MOV_DATA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K1 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K1_K12_K16_K28_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K1_K12_K16_K28_K31_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K16_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K16_K28_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K16_K28_K12_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K14_K16_K28_K12_K31_K13_1_35 | NONCLUSTERED |  |  | MOV_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID, MOV_SATISFEITO, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K1_K14 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K1_K14_K28 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K1_K14_K28_K12 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K1_K14_K28_K12_K13_31_35 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K14_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K14_K28_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K14_K28_K12_1 | NONCLUSTERED |  |  | MOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K16_K14_K28_K12_K31_K13_1_35 | NONCLUSTERED |  |  | MOV_ID, MOV_SHOP_SHIPPING, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K28_1_31 | NONCLUSTERED |  |  | MOV_ID, MOV_SHOP_ORDER_ID, MOV_ID_PEDIDO, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K28_K1 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K29_K28_K1_K13_K14_K12_K16_31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID_PEDIDO, MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2D_K1_3_5_6_7_8_12_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_DATA, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2D_K1_K14_K12_4_5_8_13_34 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2D_K1_K14_K12_K28_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_DATA, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2D_K1_K14_K12_K28_K15_4_5_8_13_29_34_37 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_ID_PEDIDO, MOV_E_ID_RESPONSAVEL, MOV_DATA_APROVADO, MOV_DATA, MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K2D_K13_K14_K1_3_4_5_6_7_8_12_16_25_27 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_PRECOVENDA, MOV_DESCONTO, MOV_OBSERVACOES, MOV_E_ID, MOV_ARM_ID, MOV_ACERTO, MOV_DEFEITUOSO, MOV_DATA, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30 | NONCLUSTERED |  |  | MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_1912 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_6 | NONCLUSTERED |  |  | MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K11_K13 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K11_K13_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ATRIB_ID, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K11_K13_4_1040 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ATRIB_ID, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K11_K15_K14_K13_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K13_K11_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K13_K15_K11_K26_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K15_K13_K11_K14_4_6 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOVENDA, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K26_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K26_K13_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K26_K13_K11_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K1_K26_K13_K11_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K11_K1_K13 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_OF_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K26_K1 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K26_K1_1598 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K26_K1_K11_K13_K14_4 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K26_K1_K11_K13_K14_4_8258 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K30_K26_K1_K11_K13_K15_4_8 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_1_13_35 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_SHOP_SHIPPING, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K1 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K1_K13 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K1_K13_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_SHOP_ORDER_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K1_K13_K12_K16_K29_K14_K28_35 | NONCLUSTERED |  |  | MOV_SHOP_SHIPPING, MOV_SHOP_ORDER_ID, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K28_K1 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K31_K28_K1_K13_K14_K2_K11_K26_K12_K4_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K32 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K32_K13_K12_K2_K4_K1_K11_K15_K19_K3_K20_K16_K29_K31_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_SHOP_ORDER_ITEM_ID, MOV_P_ID, MOV_E_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K32_K13_K2_K4_K1_K11_K15_K12_K19_K3_K20_K16_K29_K31_5_8_14_22_25_28_34 | NONCLUSTERED |  |  | MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_TPMOV_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_SHOP_ORDER_ITEM_ID, MOV_P_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K34_K12_K1_2_3_4_5_8_13_14_16_22_25_27_28_31_32_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_DATA_APROVADO, MOV_E_ID_RESPONSAVEL, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K34_K12_K1_2_3_4_5_8_13_14_16_22_25_27_28_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_DATASAIDA, MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OBSERVACOES, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_QTD_BAL, MOV_ACERTO, MOV_DEFEITUOSO, MOV_SATISFEITO, MOV_DATA_APROVADO, MOV_E_ID_RESPONSAVEL, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4 | NONCLUSTERED |  |  | MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K14 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K14_K1 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K14_K1_K11_K26 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K14_K1_K11_K26_K12 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K14_K1_K11_K26_K12_K28_K31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K2_K14_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K2_K14_K1_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K2_K14_K1_K11_K26_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K2_K14_K1_K11_K26_K12_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K4_K13_K2_K14_K1_K11_K26_K12_K28_K31_8 | NONCLUSTERED |  |  | MOV_OBSERVACOES, MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K40_K34_K12 | NONCLUSTERED |  |  | MOV_FP_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_index_MOVIMENTO_7_1381579960__K40_K34_K12_9987 | NONCLUSTERED |  |  | MOV_FP_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_11_14_31 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_11_26_13_14_2_12_28_31 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_11_30 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_11_30_34 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_ATRIB_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_11_31 | NONCLUSTERED |  |  | MOV_ID, MOV_OF_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_11_30 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_13_14_28_31_19 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_13_2 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_P_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_14 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_19 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_19_13_14_28 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_TR_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_12_29_11_31 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_OF_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_11_14_30 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_TPMOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_11_26_15 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_12 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_14_12_2_3_34 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_DATASAIDA, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_14_12_28_31_4 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_14_2_11 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_15 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_15_4 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_19_12 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_TR_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_30_11_26_14 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_31_12_29 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_13_34_19 | NONCLUSTERED |  |  | MOV_ID, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_11 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_12_2_28_15 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_2_28_15 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_28_12_29_31_13_16 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_28_34_2_12_15 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_E_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_29_12_13_15_16_28 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_31 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_14_34_2_28_15 | NONCLUSTERED |  |  | MOV_ID, MOV_TPMOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_15_14_2 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_15_26_11 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_15_4 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_16_12_29_14_28_31 | NONCLUSTERED |  |  | MOV_ID, MOV_ARM_ID, MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_19 | NONCLUSTERED |  |  | MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_19_14_16_2_13_12 | NONCLUSTERED |  |  | MOV_ID, MOV_TR_ID, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_19_28_31 | NONCLUSTERED |  |  | MOV_ID, MOV_TR_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_2 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_2_19_13_12 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_TR_ID, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_2_29_12 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_ID_PEDIDO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_26_15_4_13 | NONCLUSTERED |  |  | MOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_28 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_28_13_14 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_28_15 | NONCLUSTERED |  |  | MOV_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_30_26_13_14 | NONCLUSTERED |  |  | MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_34 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_34_12_11_30 | NONCLUSTERED |  |  | MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_37_2 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA_APROVADO, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_4_11 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_4_12_13_31_11_26_28_2 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_E_ID, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_SATISFEITO, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_4_13 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_4_15_13_11 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_MOV_ID, MOV_P_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_1_4_31_28_13_14 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1_13_30 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1_14_13_31 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_TPMOV_ID, MOV_P_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1_15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1_16_31_14_28 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_1_22 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ID, MOV_QTD_BAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_13_26_15 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_13_30 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_14_26_30 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_14_30_1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_TPMOV_ID, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_2_1_12_29 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_DATA, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_26_1_4_13_14_12_28_31 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_26_14_1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_26_30_1 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_30_1_15_14_13 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_ATRIB_ID, MOV_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_11_31_2_1_12_29 | NONCLUSTERED |  |  | MOV_OF_ID, MOV_SHOP_ORDER_ID, MOV_DATA, MOV_ID, MOV_E_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_1_13_14_16 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_13_14_1_2_11 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_13_14_1_28_15_34 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_SATISFEITO, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_13_15 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_13_34_14_1_28 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_1_16_2_13_34_19 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID, MOV_DATA, MOV_P_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_1_19 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_1_37 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA_APROVADO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_19 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_TR_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_29_1_13_28 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_29_13_15 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_14_37_2 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_DATA_APROVADO, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_16_29_1_13_14_28 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_19_13_14_1_2 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TR_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_1_13 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_1_14_31_13 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_11_31_2 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_OF_ID, MOV_SHOP_ORDER_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_13_14_28 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_16_31_14 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_29_31_14_28 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_34_11 | NONCLUSTERED |  |  | MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_12_40 | NONCLUSTERED |  |  | MOV_E_ID, MOV_FP_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_11_16_14_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_OF_ID, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_11_26_15_4 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_QUANTIDADE |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_14_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_TPMOV_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_15_12_14 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_15_34_14_12 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_28_26_12_14_29 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_30 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_1_34_14 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_11_1_15_30_26 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_MOV_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_11_1_22 | NONCLUSTERED |  |  | MOV_P_ID, MOV_OF_ID, MOV_ID, MOV_QTD_BAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_12_1_15_34 | NONCLUSTERED |  |  | MOV_P_ID, MOV_E_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_12_1_34 | NONCLUSTERED |  |  | MOV_P_ID, MOV_E_ID, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_12_2 | NONCLUSTERED |  |  | MOV_P_ID, MOV_E_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_12_28_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_15_1 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_MOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_2_1_28_32_15 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ITEM_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_2_11_26_12_28_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_28_12 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_4_1_11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_14_5 | NONCLUSTERED |  |  | MOV_P_ID, MOV_TPMOV_ID, MOV_PRECOUNITARIO |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_15_1_16_12 | NONCLUSTERED |  |  | MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_ARM_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_15_16_14_29_12_28 | NONCLUSTERED |  |  | MOV_P_ID, MOV_MOV_ID, MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_16 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_2_4_1_11_15_19_3_20_16_29_31_32 | NONCLUSTERED |  |  | MOV_P_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_26_11 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ACESSORIO_ADICIONAL, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_28_26_12_14_29_15_16 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_30 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_30_11_15 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_30_26 | NONCLUSTERED |  |  | MOV_P_ID, MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_13_32_12_2_4_1_11_15_19_3_20_16_29_31 | NONCLUSTERED |  |  | MOV_P_ID, MOV_SHOP_ORDER_ITEM_ID, MOV_E_ID, MOV_DATA, MOV_QUANTIDADE, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_TR_ID, MOV_DATASAIDA, MOV_PRODF_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_1_12_16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_1_15_30 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_MOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_1_16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_1_29_12_15 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_12_1_15_2 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_ID, MOV_MOV_ID, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_12_13_1_34_2_28_15 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID, MOV_P_ID, MOV_ID, MOV_E_ID_RESPONSAVEL, MOV_DATA, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_13_12_1_28_15 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_P_ID, MOV_E_ID, MOV_ID, MOV_SATISFEITO, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_13_16_15_1_12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_P_ID, MOV_ARM_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_15_1_29 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_MOV_ID, MOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_2_16_1_13 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_DATA, MOV_ARM_ID, MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_2_29_12_1_15_13_28_32 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_DATA, MOV_ID_PEDIDO, MOV_E_ID, MOV_ID, MOV_MOV_ID, MOV_P_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ITEM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_28_1_12_16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_28_31_12_16 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID, MOV_E_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_29 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_30 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_31_28_1 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_14_34_28_13_12 | NONCLUSTERED |  |  | MOV_TPMOV_ID, MOV_E_ID_RESPONSAVEL, MOV_SATISFEITO, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_15_11_13 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_15_13 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_15_29_12_1 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_ID_PEDIDO, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_15_30_11_1_26 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_ATRIB_ID, MOV_OF_ID, MOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_15_30_13_14_1 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_ATRIB_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_1_13_12_34_19_14 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_TR_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_1_13_14_28_29 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_14_2_13_12 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_DATA, MOV_P_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_14_29_1 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_29_1_14_28 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | _dta_stat_1381579960_16_31_14_28_11 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_19_13 | NONCLUSTERED |  |  | MOV_TR_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_2_1_12_14_37 | NONCLUSTERED |  |  | MOV_DATA, MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_DATA_APROVADO |
| dbo.MOVIMENTO | _dta_stat_1381579960_2_1_14 | NONCLUSTERED |  |  | MOV_DATA, MOV_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_2_14_12_3_13 | NONCLUSTERED |  |  | MOV_DATA, MOV_TPMOV_ID, MOV_E_ID, MOV_DATASAIDA, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_2_19_13_14_12 | NONCLUSTERED |  |  | MOV_DATA, MOV_TR_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_22_11 | NONCLUSTERED |  |  | MOV_QTD_BAL, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_26_1_11_13 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_26_1_13_30_11 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_P_ID, MOV_ATRIB_ID, MOV_OF_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_26_13_14_2_1 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_26_15 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_26_30_1 | NONCLUSTERED |  |  | MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_28_12_16_29_1 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_28_13_14_2_1_11_26 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_28_26_13_1_15_12_14_29_16 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_ID, MOV_MOV_ID, MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_28_26_13_15_14_29 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ACESSORIO_ADICIONAL, MOV_P_ID, MOV_MOV_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | _dta_stat_1381579960_28_29_1_13_14 | NONCLUSTERED |  |  | MOV_SATISFEITO, MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_29_1_13_14 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_29_13_15_1_12 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_P_ID, MOV_MOV_ID, MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_29_16_14_28_12_31_13 | NONCLUSTERED |  |  | MOV_ID_PEDIDO, MOV_ARM_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_E_ID, MOV_SHOP_ORDER_ID, MOV_P_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_1 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_1_11_15_13_14_26 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_OF_ID, MOV_MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_1_13_15 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_P_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_1_34 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ID, MOV_E_ID_RESPONSAVEL |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_13_14_26 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_26_1_11_14 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_ID, MOV_OF_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_30_26_15_1_13_14 | NONCLUSTERED |  |  | MOV_ATRIB_ID, MOV_ACESSORIO_ADICIONAL, MOV_MOV_ID, MOV_ID, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_31_1_13_12_16_29_14 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_ID, MOV_P_ID, MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_31_12 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_E_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_31_14_28_11_1_13_16 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_TPMOV_ID, MOV_SATISFEITO, MOV_OF_ID, MOV_ID, MOV_P_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_31_28_1_13_14_2_11_26 | NONCLUSTERED |  |  | MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL |
| dbo.MOVIMENTO | _dta_stat_1381579960_34_11_30 | NONCLUSTERED |  |  | MOV_E_ID_RESPONSAVEL, MOV_OF_ID, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_34_12_1 | NONCLUSTERED |  |  | MOV_E_ID_RESPONSAVEL, MOV_E_ID, MOV_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_34_30 | NONCLUSTERED |  |  | MOV_E_ID_RESPONSAVEL, MOV_ATRIB_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_37_2 | NONCLUSTERED |  |  | MOV_DATA_APROVADO, MOV_DATA |
| dbo.MOVIMENTO | _dta_stat_1381579960_4_13_2_14_1_11_26_12_28_31 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID, MOV_ID, MOV_OF_ID, MOV_ACESSORIO_ADICIONAL, MOV_E_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO | _dta_stat_1381579960_40_34_12 | NONCLUSTERED |  |  | MOV_FP_ID, MOV_E_ID_RESPONSAVEL, MOV_E_ID |
| dbo.MOVIMENTO | 2021_10_18_09_10 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_TPMOV_ID, MOV_DATA, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | 2021_10_18_09_10_01 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ARM_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | 2021_10_18_09_10_02 | NONCLUSTERED |  |  | MOV_E_ID, MOV_ID_PEDIDO, MOV_TPMOV_ID, MOV_ARM_ID, MOV_DATA |
| dbo.MOVIMENTO | 2025_10_23_09_57 | NONCLUSTERED |  |  | MOV_ID, MOV_QUANTIDADE, MOV_OF_ID, MOV_TPMOV_ID, MOV_ACESSORIO_ADICIONAL, MOV_ATRIB_ID, MOV_FP_ID, MOV_P_ID |
| dbo.MOVIMENTO | 2025_12_11_09_57 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_ARM_ID, MOV_DATA, MOV_TPMOV_ID |
| dbo.MOVIMENTO | IX_MOVIMENTO | NONCLUSTERED |  |  | MOV_P_ID, MOV_DATA, MOV_QUANTIDADE, MOV_TPMOV_ID |
| dbo.MOVIMENTO | mov_20211026_1606 | NONCLUSTERED |  |  | MOV_ID, MOV_DATA, MOV_QUANTIDADE, MOV_OBSERVACOES, MOV_P_ID, MOV_SHOP_ORDER_ID, MOV_SATISFEITO, MOV_SHOP_ORDER_ITEM_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | Movimento_2026_01_09_14_49 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_PRECOUNITARIO, MOV_OF_ID, MOV_P_ID, MOV_DATA, MOV_TPMOV_ID |
| dbo.MOVIMENTO | NonCL_MovsOF | NONCLUSTERED |  |  | MOV_OF_ID, MOV_P_ID, MOV_QUANTIDADE, MOV_TPMOV_ID |
| dbo.MOVIMENTO | NonCL_MovsOF-20181025 | NONCLUSTERED |  |  | MOV_DATASAIDA, MOV_E_ID, MOV_E_ID_RESPONSAVEL, MOV_OBSERVACOES, MOV_PRECOUNITARIO, MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | NonCL_MovsOF-20181219 | NONCLUSTERED |  |  | MOV_P_ID, MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | NonCL_MovsOF-20181219(1) | NONCLUSTERED |  |  | MOV_P_ID, MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_ACERTO, MOV_DATA |
| dbo.MOVIMENTO | NonClusteredIndex-20160512-133855 | NONCLUSTERED |  |  | MOV_QTD_BAL, MOV_QUANTIDADE, MOV_OF_ID, MOV_DATA, MOV_P_ID, MOV_TPMOV_ID, MOV_MOV_ID, MOV_E_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20170613-090533 | NONCLUSTERED |  |  | MOV_ID, MOV_MOV_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20170613-114045 | NONCLUSTERED |  |  | MOV_MOV_ID, MOV_P_ID, MOV_PRECOUNITARIO, MOV_QUANTIDADE, MOV_OF_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20180123-102607 | NONCLUSTERED |  |  | MOV_TR_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20180126-114027 | NONCLUSTERED |  |  | MOV_E_ID, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA |
| dbo.MOVIMENTO | NonClusteredIndex-20180201-094629 | NONCLUSTERED |  |  | MOV_ARM_ID, MOV_P_ID, MOV_QUANTIDADE, MOV_TPMOV_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20180515-140251 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_OF_ID, MOV_P_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20180515-140509 | NONCLUSTERED |  |  | MOV_DATA, MOV_PRECOUNITARIO, MOV_DATASAIDA, MOV_P_ID, MOV_TPMOV_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20180515-165311 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_TPMOV_ID, MOV_MOV_ID, MOV_PRODF_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20190626-153016 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_ARM_ID |
| dbo.MOVIMENTO | NonClusteredIndex-20190626-153745 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_SATISFEITO |
| dbo.MOVIMENTO | NonClusteredIndex-20191001-154950 | NONCLUSTERED |  |  | MOV_E_ID, MOV_TPMOV_ID, MOV_ID_PEDIDO |
| dbo.MOVIMENTO | NonClusteredIndex-20200122-102633 | NONCLUSTERED |  |  | MOV_QUANTIDADE, MOV_P_ID, MOV_TPMOV_ID, MOV_DATA, MOV_SHOP_ORDER_ID |
| dbo.MOVIMENTO_ATTACH | PK_MOVIMENTO_ATACH | CLUSTERED | Y | Y | MATCH_ID |
| dbo.MOVIMENTO_TIPO | PK_MOVIMENTO_TIPO | CLUSTERED | Y | Y | TPMOV_ID |
| dbo.noticias_agentes | PK_insider | CLUSTERED | Y | Y | insider_id |
| dbo.notifications | notifications_id_primary | CLUSTERED | Y | Y | id |
| dbo.notifications | notifications_notifiable_type_notifiable_id_index | NONCLUSTERED |  |  | notifiable_type, notifiable_id |
| dbo.OF_ATTACH | PK_OF_ATTACH | CLUSTERED | Y | Y | ATCH_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K1 | NONCLUSTERED |  |  | ATCH_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4 | NONCLUSTERED |  |  | ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_1_2_3_5_6_7_8_9_10_11_12 | NONCLUSTERED |  |  | ATCH_ID, ATCH_NOME, ATCH_DESCRICAO, ATCH_IMAGE, ATCH_PUBLICO, ATCH_PRODUCAO, ATCH_TIPO, ATCH_ENVIADO_PROPRIETARIO, ATCH_ELIMINADO, ATCH_FP_ID, ATCH_DATA, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_1_2_3_5_6_7_8_9_10_11_12_9987 | NONCLUSTERED |  |  | ATCH_ID, ATCH_NOME, ATCH_DESCRICAO, ATCH_IMAGE, ATCH_PUBLICO, ATCH_PRODUCAO, ATCH_TIPO, ATCH_ENVIADO_PROPRIETARIO, ATCH_ELIMINADO, ATCH_FP_ID, ATCH_DATA, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_1_2_3_7_8 | NONCLUSTERED |  |  | ATCH_ID, ATCH_NOME, ATCH_DESCRICAO, ATCH_PRODUCAO, ATCH_TIPO, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_1_5 | NONCLUSTERED |  |  | ATCH_ID, ATCH_IMAGE, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_2_5 | NONCLUSTERED |  |  | ATCH_NOME, ATCH_IMAGE, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_4364 | NONCLUSTERED |  |  | ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_K8_1_2_3_5_6_7 | NONCLUSTERED |  |  | ATCH_ID, ATCH_NOME, ATCH_DESCRICAO, ATCH_IMAGE, ATCH_PUBLICO, ATCH_PRODUCAO, ATCH_OF_ID, ATCH_TIPO |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K4_K8_1_5 | NONCLUSTERED |  |  | ATCH_ID, ATCH_IMAGE, ATCH_OF_ID, ATCH_TIPO |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K8_K11 | NONCLUSTERED |  |  | ATCH_TIPO, ATCH_FP_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K8_K4_1_5 | NONCLUSTERED |  |  | ATCH_ID, ATCH_IMAGE, ATCH_TIPO, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K9 | NONCLUSTERED |  |  | ATCH_ENVIADO_PROPRIETARIO |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K9_9987 | NONCLUSTERED |  |  | ATCH_ENVIADO_PROPRIETARIO |
| dbo.OF_ATTACH | _dta_index_OF_ATTACH_7_523148909__K9_K4 | NONCLUSTERED |  |  | ATCH_ENVIADO_PROPRIETARIO, ATCH_OF_ID |
| dbo.OF_ATTACH | _dta_stat_523148909_4_8 | NONCLUSTERED |  |  | ATCH_OF_ID, ATCH_TIPO |
| dbo.OF_ATTACH | _dta_stat_523148909_8_11 | NONCLUSTERED |  |  | ATCH_TIPO, ATCH_FP_ID |
| dbo.OF_ATTACH | _dta_stat_523148909_9_4 | NONCLUSTERED |  |  | ATCH_ENVIADO_PROPRIETARIO, ATCH_OF_ID |
| dbo.OF_CHECKLIST | PK_OF_CHECKLIST | CLUSTERED | Y | Y | OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1 | NONCLUSTERED |  |  | OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_2_17 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_2_3_4_5_6_7_8_9_10_11_12_13_14_15_16_17_18 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_OF_ID, OFCH_SEQUENCIA, OFCH_FP_ID, OFCH_ESTADO, OFCH_DESCR_EN, OFCH_FP_ID_CHK, OFCH_OBSERVACOES, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_CULPA_CHEFE, OFCH_OFFP_ID, OFCH_MOLDE_REPARAR, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_2_9085 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_4149 | NONCLUSTERED |  |  | OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_8258 | NONCLUSTERED |  |  | OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K5_K8_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K5_K8_K7_K12_2_948 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K5_K8_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K5_K8_K7_K15_2_12_1040 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K8_K15_K7_K5_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K10_K8_K15_K7_K5_2_12_9987 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K17 | NONCLUSTERED |  |  | OFCH_ID, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K17_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K17_K10_K7_K8_K4_K3_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_ID, OFCH_OFFP_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K17_K6_2_7_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_ID, OFCH_OFFP_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K5 | NONCLUSTERED |  |  | OFCH_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K5_8 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K5_K17_K6_2_7_8_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_ID, OFCH_OF_ID, OFCH_OFFP_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K7 | NONCLUSTERED |  |  | OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K7_1771 | NONCLUSTERED |  |  | OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K7_K10_K5_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K7_K10_K5_K8_K15_2_12_6497 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K8_K3_K4_2_17 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OFFP_ID, OFCH_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K1_K8_K4_K3_K17_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_4149 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K5_K8_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K5_K8_K7_K15_2_12_1912 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K12_2_6540 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K12_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K12_K5_K8_2_4606 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K15_2_12_4149 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K5_K8_K15_12 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K5_K8_K15_12_4364 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K5_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K1_K7_K5_K8_K15_2_12_6221 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1_K5_K8_K7_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1_K5_K8_K7_2_3923 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1_K7_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K12_K1_K7_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K5_K1_K7_K8_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K5_K1_K7_K8_K12_2_5247 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K5_K1_K7_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K5_K1_K7_K8_K15_2_12_4364 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K7_K17_K5_K8_K4_K3_K1_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_OFFP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_2533 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_5 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_5_9850 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K1 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K1_K15_K7_K5_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_ID, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K1_K15_K7_K5_2_12_114 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_ID, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K5 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K10_K8_K5_8809 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12 | NONCLUSTERED |  |  | OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_9085 | NONCLUSTERED |  |  | OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_6544 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K10 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K10_5379 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K10_K5_K8_K7_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K10_K5_K8_K7_2_7337 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K7 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K7_2484 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K7_K10_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K1_K7_K10_K5_K8_2_6250 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K10_K1_K7_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K10_K1_K7_2_1828 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K10_K1_K7_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K10_K1_K7_K5_K8_2_3088 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K7_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K7_1_2_10_9910 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K7_K5_K8_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K12_K7_K5_K8_1_2_10_5734 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K15_K10_K1_K7_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K15_K10_K1_K7_2_12_1410 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17 | NONCLUSTERED |  |  | OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_1 | NONCLUSTERED |  |  | OFCH_ID, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K1 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K1_K10_K7_K8_K4_K3_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_OFFP_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K1_K6_2_7_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_OFFP_ID, OFCH_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K3_K4 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K3_K4_1_2 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K3_K4_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K3_K4_K10_K7_K1_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K4_K3 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K17_K8_K4_K3_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OFFP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K3 | NONCLUSTERED |  |  | OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K3_1912 | NONCLUSTERED |  |  | OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K3_K10_K7_K8_K4_K17_K1_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_VISTO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_OFFP_ID, OFCH_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K3_K8_K4_K17_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_VISTO, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K4 | NONCLUSTERED |  |  | OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K4_K10_K7_K8_K3_K17_K1_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_RESOLVIDO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_OFFP_ID, OFCH_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K4_K8_K3_K17_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_RESOLVIDO, OFCH_ESTADO, OFCH_VISTO, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5 | NONCLUSTERED |  |  | OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_8 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K17_K6_2_7_8_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_OF_ID, OFCH_ID, OFCH_OFFP_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8_100 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8_K10_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8_K10_K7_K12_2_3885 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8_K10_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K1_K8_K10_K7_K15_2_12_9987 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K10_K8 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K10_K8_4683 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K17_K1_K6_2_7_8_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_OF_ID, OFCH_OFFP_ID, OFCH_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K7_K8_K1 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K7_K8_K1_K10_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OF_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K7_K8_K1_K10_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_FP_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K1 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K1_K10_K15_K7_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K1_K10_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K1_K10_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K10 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K5_K8_K10_6960 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K6_K17_K1_2_7_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_SEQUENCIA, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K6_K5_K17_K1_2_7_8_12_13_14_15 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_JSON_DOTS, OFCH_DATA_VERIFICACAO, OFCH_DATA_ACTUALIZACAO, OFCH_SEQUENCIA, OFCH_OF_ID, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K1_K10_K5_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K1_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K1_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K1_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K12_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K12_K1_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_GRAVIDADE, OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K8_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K10_K5_K8_K1_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_1_2_10_3 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_K1_2735 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_K1_K10_K5_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K12_K1_K10_K5_K8_2_9429 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K1_K10_K8_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K12_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K12_K1_K10_K8_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_FP_ID, OFCH_OF_ID, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K8_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K8_K1_8526 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K8_K1_K10_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K5_K8_K1_K10_K15_2_12_8066 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K1_K10_K15_K5_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K12_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K12_1_2_10_6075 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K12_K5_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K7_K8_K12_K5_1_2_10_1623 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8 | NONCLUSTERED |  |  | OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_1 | NONCLUSTERED |  |  | OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_1_6960 | NONCLUSTERED |  |  | OFCH_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_4364 | NONCLUSTERED |  |  | OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_2166 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K10 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K10_8809 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K10_K15_K7_K5_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K10_K15_K7_K5_2_12_9850 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K10_K7_K17_K5_K15_K3_K4_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_OFFP_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_8310 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K15_K7_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K15_K7_2_12_6355 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K7_K12_2_4829 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K5_K10_K7_K15_2_12_5201 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7_4864 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7_K5 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7_K5_5201 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7_K5_K10_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K1_K7_K5_K10_K15_2_12_1912 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K10_K5 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K10_K5_8337 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K10_K5_K1_K7_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K10_K5_K1_K7_2_5282 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K7_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K7_1_2_10_4312 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K7_K5_1_2_10 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K12_K7_K5_1_2_10_9850 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_FP_ID_CHK, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K1_K7_K5_12 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K1_K7_K5_12_6960 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K1_K7_K5_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K1_K7_K5_2_12_9953 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K5_K1_K7_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K15_K10_K5_K1_K7_2_12_2533 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K17_K3_K4 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OFFP_ID, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K17_K3_K4_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_OFFP_ID, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K3_K4 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K3_K4_17 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K3_K4_K17 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K3_K4_K17_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K3_K4_K17_K10_K7_K1_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_OFFP_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K4_K3_K1_K10_K7_K17_K5_K15_2_12_16 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_CULPA_CHEFE, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_OFFP_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K4_K3_K17 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K4_K3_K17_K1_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OFFP_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1_6221 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1_K10_K7_K12_2 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1_K10_K7_K12_2_8576 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_ESTADO, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1_K10_K7_K15_2_12 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K1_K10_K7_K15_2_12_2894 | NONCLUSTERED |  |  | OFCH_DESCR, OFCH_GRAVIDADE, OFCH_ESTADO, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K10 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_index_OF_CHECKLIST_7_530100929__K8_K5_K10_4364 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_stat_530100929_1_10_8 | NONCLUSTERED |  |  | OFCH_ID, OFCH_FP_ID_CHK, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_1_8_3 | NONCLUSTERED |  |  | OFCH_ID, OFCH_ESTADO, OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_1_8_4 | NONCLUSTERED |  |  | OFCH_ID, OFCH_ESTADO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_10_1_7 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_10_1_7_5_8_15 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_10_12 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_stat_530100929_10_5_1_7 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_10_7_17_5_8_4_3 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_OFFP_ID, OFCH_OF_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_12_1_10_5_8 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_12_7_5_8 | NONCLUSTERED |  |  | OFCH_GRAVIDADE, OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_15_10_1_7 | NONCLUSTERED |  |  | OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_17_1_10_7_8_4 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_17_1_6 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_stat_530100929_17_8_3 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ESTADO, OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_17_8_4_3_1 | NONCLUSTERED |  |  | OFCH_OFFP_ID, OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_3_10_7_8_4 | NONCLUSTERED |  |  | OFCH_VISTO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO, OFCH_RESOLVIDO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_4_10_7_8 | NONCLUSTERED |  |  | OFCH_RESOLVIDO, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_1 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_1_17_6 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ID, OFCH_OFFP_ID, OFCH_SEQUENCIA |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_10 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_17 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_8_1_10_15 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_5_8_10 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_stat_530100929_6_17 | NONCLUSTERED |  |  | OFCH_SEQUENCIA, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_6_5_17 | NONCLUSTERED |  |  | OFCH_SEQUENCIA, OFCH_OF_ID, OFCH_OFFP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_10_5_1_15 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_10_5_12 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_10_5_8 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_12_1_10_5 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_ID, OFCH_FP_ID_CHK, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_5_1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_5_12_1 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_GRAVIDADE, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_5_8 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_8 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_7_8_1_10 | NONCLUSTERED |  |  | OFCH_FP_ID, OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_1 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_1_10_7_17_5_15_3 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_OFFP_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO, OFCH_VISTO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_1_7_5 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_ID, OFCH_FP_ID, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_12_10_5 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID_CHK, OFCH_OF_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_12_7 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_15_10_1_7 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_DATA_ACTUALIZACAO, OFCH_FP_ID_CHK, OFCH_ID, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_3_4_17_10_7_1_5_15 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_VISTO, OFCH_RESOLVIDO, OFCH_OFFP_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_ID, OFCH_OF_ID, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_4_3_1_10_7 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID |
| dbo.OF_CHECKLIST | _dta_stat_530100929_8_5_1_10_7_12 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_OF_ID, OFCH_ID, OFCH_FP_ID_CHK, OFCH_FP_ID, OFCH_GRAVIDADE |
| dbo.OF_CHECKLIST | 2025_11_06_13_40_00 | NONCLUSTERED |  |  | OFCH_FP_ID_CHK, OFCH_OF_ID, OFCH_ESTADO, OFCH_GRAVIDADE, OFCH_DATA_VERIFICACAO |
| dbo.OF_CHECKLIST | NonClusteredIndex-20170606-165600 | NONCLUSTERED |  |  | OFCH_OF_ID, OFCH_ESTADO |
| dbo.OF_CHECKLIST | NonClusteredIndex-20180111-143414 | NONCLUSTERED |  |  | OFCH_ESTADO, OFCH_RESOLVIDO, OFCH_VISTO, OFCH_OF_ID |
| dbo.OF_CHECKLIST | NonClusteredIndex-20190604-113538 | NONCLUSTERED |  |  | OFCH_CULPA_CHEFE, OFCH_FP_ID, OFCH_GRAVIDADE, OFCH_OF_ID, OFCH_ESTADO, OFCH_FP_ID_CHK, OFCH_DATA_ACTUALIZACAO |
| dbo.OF_CHECKLIST | NonClusteredIndex-20200212-104026 | NONCLUSTERED |  |  | OFCH_ID, OFCH_DESCR, OFCH_OFFP_ID |
| dbo.OF_ENTIDADE | PK_OF_ENTIDADE | CLUSTERED | Y | Y | OFE_ID |
| dbo.OF_ENTIDADE | _dta_index_OF_ENTIDADE_7_250483971__K2_K4_K3_5 | NONCLUSTERED |  |  | OFE_DATA, OFE_OF_ID, OFE_E_ID_ANTERIOR, OFE_OF_PRECOVENDA |
| dbo.OF_ENTIDADE | _dta_index_OF_ENTIDADE_7_250483971__K3_K2_4_5 | NONCLUSTERED |  |  | OFE_E_ID_ANTERIOR, OFE_DATA, OFE_OF_PRECOVENDA, OFE_OF_ID |
| dbo.OF_ENTIDADE | _dta_index_OF_ENTIDADE_7_250483971__K4_K2_K3_5 | NONCLUSTERED |  |  | OFE_DATA, OFE_E_ID_ANTERIOR, OFE_OF_ID, OFE_OF_PRECOVENDA |
| dbo.OF_ENTIDADE | _dta_index_OF_ENTIDADE_7_250483971__K5 | NONCLUSTERED |  |  | OFE_DATA |
| dbo.OF_ENTIDADE | _dta_stat_250483971_2_4_3 | NONCLUSTERED |  |  | OFE_OF_ID, OFE_E_ID_ANTERIOR, OFE_OF_PRECOVENDA |
| dbo.OF_ENTIDADE | _dta_stat_250483971_3_2 | NONCLUSTERED |  |  | OFE_OF_PRECOVENDA, OFE_OF_ID |
| dbo.OF_FP | PK_OF_FP | CLUSTERED | Y | Y | OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1 | NONCLUSTERED |  |  | OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_18 | NONCLUSTERED |  |  | OFFP_HORAS_REP, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_2_3_4_5_6_7_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_34_ | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_2_7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_3_6_7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_31 | NONCLUSTERED |  |  | OFFP_PROBS_DATA, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_38 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_4_5_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_35_36_38_39_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_43 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_8 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K17_K40_6_7_8_10_11_12_13 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_ID, OFFP_OFFPCL_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_3 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_7_5201 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_8066 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_6980 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_1040 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_34_1410 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46_K38_7_34_9850 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46_K6_K7_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K46_K6_K7_K38_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K7_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K7_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K37_K7_K6_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_DATAINICIO, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K38_K7_K37_K46 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K38_K7_K37_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K38_K7_K37_K46_K6_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K38_K7_K37_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K40_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K46_K37_7_34_38 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K46_K37_7_34_38_6960 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K6_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K6_K7_2533 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K7_K37_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K3_K7_K37_K6_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K34 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K34_K3_K7_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K34_K3_K7_K40_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_FP_ID, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K34_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K34_K7_K40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K37_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K37_K7_K39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K37_K7_K39_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K37_K7_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K7_K37_K39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K7_K37_K39_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K38_K3_K7_K37_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K40_K3_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K2_K7_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_2 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_2_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37_40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_TPCAM_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_2_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37_40_44 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_TPCAM_ID, OFFP_OF_ID_MLD, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_6497 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_43_44 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_5201 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_6_44 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID_MLD, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K34_6_7_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K34_K40_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K37_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K37_K7_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K37_K7_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K40_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K40_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K41_K44_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K41_K8 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K43_K41_K44_K40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K6_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K6_K7_1040 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K7_4_5_6_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K7_6_34_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_ORDEM, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K7_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K8 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K2_K8_4_5_6_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K34_K7_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K34_K7_K2_K40_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37_1912 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37_K2_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37_K2_K46_K38_7_34_5492 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37_K7_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K37_K7_K38_K2_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K38_16_37_39 | NONCLUSTERED |  |  | OFFP_SEQUENCIA, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K40_K2_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K40_K2_K41_K44_K43 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K40_K2_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_3071 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K2_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K2_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K2_K40_K44_K34_4_5_6_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K2_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K38_K37_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K38_K37_K2_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K38_K37_K2_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K3_K7_K38_K37_K2_K46_K6_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K34_K7_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K34_K7_K2_K40_K3_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K34D_2_7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K34D_K3_2_6_7_37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_ORDEM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K34D_K3_K40_2_6_7_37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_ORDEM, OFFP_FP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_9649 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_2 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_K2_5748 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_K2_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_K2_K46_K38_7_34_8066 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K37_K3_K2_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K16_39 | NONCLUSTERED |  |  | OFFP_COEFICIENTE, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K2_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K2_K3_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K2_K3_K37_K46_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_16_37_39 | NONCLUSTERED |  |  | OFFP_SEQUENCIA, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K2_K37_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K2_K37_K7_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K2_K7_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K37_K2_K46_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K37_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K37_K7_K2_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OF_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K37_K7_K39_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K3_K7_K37_K39_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K37_1653 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K37_K3_K2_K46_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K37_K3_K2_K46_7_34_9085 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K39_K2_K3_K7_K37_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37_8337 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37_K2_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37_K2_7_1912 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37_K2_K3_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K46_K37_K2_K3_7_5201 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K7_K37_K3_K2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K38_K7_K37_K3_K2_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K38_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_COEFICIENTE, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K38_K2_K3_K7_K37_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_COEFICIENTE, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K38_K2_K3_K7_K37_K6_4_5_4364 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_COEFICIENTE, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K6_K7_K3_K2_K37_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K6_K7_K3_K2_K37_K38_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K6_K7_K3_K37_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K7_K3_K2_K37_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K39_K7_K3_K2_K37_K38_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_4_5_8_10_11_12_13_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_6_7_34_37_39_41_44_46 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K17_6_7_8_10_11_12_13 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_ID, OFFP_TPCAM_ID, OFFP_OFFPCL_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K2_K3_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K2_K34_K3_K7_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K3_K2_K7_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K34D_K3_2_6_7_37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_TPCAM_ID, OFFP_ORDEM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K41_K43 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K41_K43_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K40_K41_K43_K3_K2_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K41_K3_K2_K44_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K41_K3_K2_K8 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K41_K40_K3_K2_K44_K43 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K41_K43_K2_K3_K44_K40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K43_K16_39_41 | NONCLUSTERED |  |  | OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_38 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_38_8809 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_K2_7_38 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_K2_7_38_8341 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_K2_K3_7_38 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K37_K2_K3_7_38_6221 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K7_K37_K3_2_38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K7_K37_K3_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K7_K37_K3_K6_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K46_K7_K37_K6_K3_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_9073 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K2_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K2_K3_K7_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K2_K3_K7_K37_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K2_K3_K7_K37_K38_K39_4_5_34_40_41_43_44 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ORDEM, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K2_K3_K7_K37_K38_K39_4_5_9850 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K7_K3_K2_K37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K6_K7_K3_K2_K37_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_4364 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_K3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_K3_K2_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_K3_K2_K43_K16_6_39_41 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_K37_K3_K2_K38 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K7_K37_K3_K2_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K8 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K8_4_5_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_34_35_36_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_DATA_ENTREGA, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K8_9953 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K1_K8_K3_K2_K41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K16_1_38_39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K16_K3_1_37_38_39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_SEQUENCIA, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K16_K3_K2_K7_1_37_38_39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_SEQUENCIA, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K17_K40_K1_6_7_8_10_11_12_13 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2 | NONCLUSTERED |  |  | OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_3 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_5201 | NONCLUSTERED |  |  | OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_7_1912 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_9085 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_9987 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K34_6_7_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K34_K40_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K40_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K40_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K41_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K41_K8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K44 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K44_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K46_K37_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K46_K37_K38_7_34_4683 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7_37 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7_K6 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K7_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K3_K8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K34_K40_K3_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_ID, OFFP_ORDEM, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K34_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K34_K7_K40_K3_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_OF_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K38_K3_K7_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_OF_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K44_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K44_K3_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K44_K3_K40_K41_K43 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K44_K3_K41_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K1_K44_K40_K3_K41_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_1_43_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_1_43_44_6497 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_6497 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_43_44 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_9987 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K34_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K34_K7_K40_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K41_K8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATA_PREVISTA, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K44 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K44_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K46_K37_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K46_K37_K38_7_34_9953 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K6_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K6_K7_4864 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K7_4_5_6_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K7_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K7_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K7_K38_K37_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K1_K8_4_5_6_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K17 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFPCL_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_5543 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_3923 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_41 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K46_K38_7_34_2894 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K7_K38_K6_K46 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K1_K7_K38_K6_K46_47_8484 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K6_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K6_K7_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K6_K7_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7_K1_K38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7_K1_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7D | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7D_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K37_K7D_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K44_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_OF_ID_MLD, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K44_K1_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_OF_ID_MLD, OFFP_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_1040 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K1_K7_K37_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K1_K7_K37_K46 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K7_1771 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K7_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K6_K7_K1_9987 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K1_1771 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K1_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K1_K41 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K1_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_1_9987 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_9987 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_K1_K38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_K1_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K3_K7_K37_K1_K6_K46 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34_1_3_6_7_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34_1_4364 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34_8066 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K34_K40_1_3_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_34_6497 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_K46_K38_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_K46_K38_34_3369 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_K46_K38_7_34_9910 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K37_K3_K1_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K40_K34_1_3_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K41_K3_K43_K44_K1_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K41_K3_K43_K44_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K41_K3_K43_K44_K40_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K1_K40_K41_K43 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K1_K41_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K1_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K41 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K44_K3_K41_K43_K1_K40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K46_K37_K3_K1_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K46_K37_K3_K1_K38_7_34_1040 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K6_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K6_K3_K1_K7_K37_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K6_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K6_K7_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K6_K7_K34_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K1_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K1_K3_K40_K44_K34_4_5_6_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K1_K40_K3_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K3_K1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K34_3_6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K37_K3_K1_K38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K2_K7_K37_K3_K1_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K20 | NONCLUSTERED |  |  | OFFP_PECAS |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K20_K1 | NONCLUSTERED |  |  | OFFP_PECAS, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3 | NONCLUSTERED |  |  | OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_1_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_1_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_8066 | NONCLUSTERED |  |  | OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_2 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_4149 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_8066 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_34_4864 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_8066 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_K46_K38_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_K46_K38_34_4364 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K37_K46_K38_7_34_5543 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K40_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K41_K8 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K44_K40_K41_K43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K7_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K2_K8 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K34_K7_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K34_K7_K2_K40_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K37_8526 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K37_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K37_K2_3928 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K38 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K38_16_37_39 | NONCLUSTERED |  |  | OFFP_SEQUENCIA, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K38_K2_K46_K37_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K38_K2_K46_K37_7_34_4149 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K44_K2_K7_K40_K34_4_5_6_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K7_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K1_K7_K2_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K17_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OFFPCL_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_1_6_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_1_6_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_41 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_43_44 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_6_44 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_7_8 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_PESO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_8 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_8341 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K37_8341 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K40_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K41_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44_7_8 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_PESO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44_K40_K41_K43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44_K41_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K44_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K46_K37_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K46_K37_K38_7_34_2533 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K6_K7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K6_K7_5201 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K7_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K7_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K7_K38_K37_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K7_K43_K16_6_39_41 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K7_K44_8 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K8 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K8_4_5_6_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K8_4864 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K1_K8_K41 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_PESO, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_1410 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_8258 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K46_K38_7_34_9987 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K7_K38_K6_K46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K1_K7_K6_K46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAFIM, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K7_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K7_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K7_K1_K38 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K7_K1_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K37_K7_K38_K1_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K40_K1_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K40_K1_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K44_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K44_K43_K41_K40_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K6_K7_K37_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K1_3928 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K1_4_5_6_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K1_6_34_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_ORDEM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K1_K43_K16_6_39_41 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K1_K38_K39 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K1_K38_K39_K6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K1_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K1_K6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K1_K6_K38_K39_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_DATAINICIO, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K38_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K7_K37_K38_K1_K6_K46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K2_K8_K1_4_5_6_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1_9987 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1_K2_K46_K38_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1_K2_K46_K38_7_34_8258 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K1_K2_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K2_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K7_K1_K38 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K7_K1_K38_K2_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K7_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K37_K7_K38_K1_K2_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K1_K44_K40_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K1_K8 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K40_K43_K44_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K2_K44_K43_K1_K40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K41_K40_K2_K1_K44_K43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K42_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_PLANEAMENTO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K6_K2_K1_K7_K37_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_1_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_1_2_6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_5439 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_K34_K40_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_K34_K40_6_37_6497 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K2_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K40_K2_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K6D | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K1_K6D_K2_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1_37 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1_K6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K1_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K37 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K37_1_8258 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K2_K37_4364 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K46_1227 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K46_47_9437 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K46_K6_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K2_K46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K1_K38_K39_K6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K2_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K2_1_9987 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K37_K6_K1_K2_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K7_K41_K1_K2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K8_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K3_K8_K2_K1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_PESO, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34 | NONCLUSTERED |  |  | OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_4364 | NONCLUSTERED |  |  | OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K1_K40_K3_K2_K7_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_ORDEM, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_1_3_6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ORDEM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_1_3_6_7_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_ORDEM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_1_9987 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_3_6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ORDEM, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K1 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K1_K40_K3_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ORDEM, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_1_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_K37_K6_K7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_K37_K6_K7_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_K7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K3_K7_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K40_1_3_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_ORDEM, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K6_K7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K6_K7_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K34_K2_K7_3_6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37 | NONCLUSTERED |  |  | OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_2533 | NONCLUSTERED |  |  | OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_812 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K2_K3_K7_K38_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K3_K2 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K3_K2_9910 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K3_K2_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K38 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K38_114 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K38_K3_K2_K46_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K1_K38_K3_K2_K46_7_34_1771 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_8258 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_K3 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_K3_4864 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_K3_K1 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_K3_K1_1771 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K2_K3_K7_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_1040 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1_2 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1_8066 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1_K2 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1_K2_6321 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K1_K2_K7_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_2533 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_7_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K1 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K1_6497 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K1_K7 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K6_K7_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K7_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K7_1_8066 | NONCLUSTERED |  |  | OFFP_ID, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K37_K3_K2_K7_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K1_K2_K3_K7_K37_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K1_K3_16_37_39 | NONCLUSTERED |  |  | OFFP_SEQUENCIA, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K1_K3_K2_K7_K37_K6_K46 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K1_K3_K2_K7_K37_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K1_K3_K2_K7_K37_K6_K46_47_2533 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_OFFP_ID_RETURN, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K38_K3_K2_K7_K1_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40 | NONCLUSTERED |  |  | OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_1_4_5_8_10_11_12_13_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_8809 | NONCLUSTERED |  |  | OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_4_5_8_10_11_12_13_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_6_7_34_37_39_41_44_46 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K17_6_7_8_10_11_12_13 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_TPCAM_ID, OFFP_ID, OFFP_OFFPCL_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K2_K3_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_TPCAM_ID, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K3 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K3_K2_K44_4_5_6_7_8_10_11_12_13_17_18_21_22_23_37 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_RETURN, OFFP_TPCAM_ID, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K3_K2_K7_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_TPCAM_ID, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K1_K41_K43 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K2_K1_K3_K34_4_5_6_7_8_10_11_12_13_37_38_39_41_44_46_47 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_PESO, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_COEFICIENTE_X, OFFP_RETORNO_GRAVE, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K2_K1_K44_K3_K41_K43 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K3_K2 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K3_K41_K2 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K3_K41_K2_K43_K44_K1 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K41_K1 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K41_K1_K3_K2_K44_K43 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K41_K1_K3_K2_K44_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K40_K41_K1_K43_K2_K3_K44 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TURN_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K3_K2_K8 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K3_K2_K44_K43 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K3_K2_K44_K43_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K43 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K43_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K43_K2_K3_K44 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K43_K3_K2_6_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K1_K40_K43_K3_K2_K44 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K40_K1_K43 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K43_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K43_K1_K40 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K43_K1_K40_K2_K3 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K41_K43_K2_K3_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K42 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K42_K1 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K42_K2_K1 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_1_40_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_1_7_40_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K1_K40_K41 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K1_K40_K41_K2_K3 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K16_1_3_6_7_39_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K16_1_39_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K16_K2_1_3_6_7_39_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_SEQUENCIA, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K3_1_40_41_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K3_K2_1_40_41_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K3_K2_1_6_7_40_41_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K3_K41_K2_K44_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K3_K41_K2_K44_40 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K41_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K41_K2_K3_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K44_K2_K1_K40_K41_K3 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K44_K2_K40_K41_K3 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K43_K44_K2_K40_K41_K3_K1 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K1_K3 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K1_K3_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K3_K1 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K3_K1_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K3_K41 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K2_K3_K41_K43_K1_K40 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K2_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K2_K1 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K2_K1_K43_K41_K40 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K41_K2 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K41_K2_K43_1_40 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K41_K2_K43_40 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K44_K3_K41_K2_K43_K1_K40 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K1 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K1_K3_K2 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K1_K3_K2_K6 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K1_K3_K2_K6_K7_K37_K38 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K1_K3_K2_K6_K7_K37_K38_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_COEFICIENTE_X, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38_3982 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38_K2_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38_K2_7_4288 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38_K2_K3_7 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K37_K1_K38_K2_K3_7_6478 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K7_K37_K3_K1_2_38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K7_K37_K3_K1_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K7_K37_K3_K1_K6_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K46_K7_K37_K6_K3_K1_2_38_47 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_RETORNO_GRAVE, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6 | NONCLUSTERED |  |  | OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_5201 | NONCLUSTERED |  |  | OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K3_K1 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3_1_8066 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3_8258 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3_K1 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K3_K1_4149 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K2_K7_K34_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_2 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_K2 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_K2_K1_K40_K42_41_43_44 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_PLANEAMENTO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_K2_K1_K7_K37_K38_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_K2_K42_K40_K1_41_43_44 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_PLANEAMENTO, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6_K3_K2_K7_K37_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_1_2_4_5_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAFIM, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_1_2_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_44 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_K2_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_K7_K1 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K6D_K3_K7_K1_K2_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7 | NONCLUSTERED |  |  | OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_8337 | NONCLUSTERED |  |  | OFFP_DATAFIM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_9987 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K2_K3_K38_K37_K39_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K2_K34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K2_K34_K40 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K3 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K3_K2 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K3_K2_8066 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K3_K2_K43_K16_6_39_41 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_DATAFIM, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K1_K40_K3_K2_K34_6_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K1_K3 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OF_ID, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K3_K1_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K3_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K34_3_6 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K34_3_6_4149 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K2_K6_K34_1_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K1 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_FP_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K1_K2_K37_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_DATAFIM, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K1_4_5_6_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_PESO, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_DATA_ENTREGA, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K1_6 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K1_K38_K16_37_39 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K1_K43_K16_6_39_41 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_COEFICIENTE, OFFP_DATA_PREVISTA, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K1_K6_4_5 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K37_1_4364 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K3_K2_K6_K37_K34_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_RETURN, OFFP_ORDEM |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K37_K3_K1_K2_K38 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K37_K3_K1_K2_K38_K6_K46_47 | NONCLUSTERED |  |  | OFFP_RETORNO_GRAVE, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAINICIO, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7_K41_K3_K40_K43_K44_K2_K1_4_5_6 | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7D_K2_K3_K37 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7D_K2_K3_K37_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7D_K2_K3_K37_34 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K7D_K2_K3_K37_K1 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_1 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_1_8526 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_K1 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_K1_114 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_K1_4_5_7_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_33_34_35_36_ | NONCLUSTERED |  |  | OFFP_PROBLEMAS, OFFP_OBSERVACOES, OFFP_DATAFIM, OFFP_NUMUTIL, OFFP_PESO_DECK_ANT, OFFP_PESO_DECK_DP, OFFP_PESO_CASCO_ANT, OFFP_PESO_CASCO_DP, OFFP_SERVER, OFFP_ARM_ID, OFFP_SEQUENCIA, OFFP_OFFPCL_ID, OFFP_HORAS_REP, OFFP_HORAS_REP_REAL, OFFP_PECAS, OFFP_CONTROLO, OFFP_TEMPERATURA, OFFP_HUMIDADE, OFFP_CONTROLO_CRIS, OFFP_EMAIL_CRIS, OFFP_PROBS_GOLA, OFFP_PROBS_INTERIOR, OFFP_PROBS_PINTURA, OFFP_PROBS_MOLDE, OFFP_PROBS_LAMINAGEM, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE, OFFP_PROBS_PINT_INOCENTE, OFFP_ORDEM, OFFP_PESO_HIST, OFFP_LINHA_AUX, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_PLANEAMENTO, OFFP_TURN_ID, OFFP_DATA_ENTREGA, OFFP_PESO, OFFP_ID |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_K1_K3_K2_K41 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_index_OF_FP_7_2101582525__K8_K41_K3_1_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_PESO, OFFP_DATA_PREVISTA, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_17 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFPCL_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_2_3_37_46_6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_COEFICIENTE_X, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_1_2_3_38_7_37_46 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_OFFP_ID_RETURN, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_stat_2101582525_1_2_34 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_1_2_34_3_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_ORDEM, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_2_38_3_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_3_2_43_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_TURN_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_1_3_41 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_1_3_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_1_34_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_1_38_16 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_stat_2101582525_1_38_3_2_7_16 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_stat_2101582525_1_38_3_37_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_1_38_3_7_37_39_6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_COEFICIENTE, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_1_38_39_2_3_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_1_38_46 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_stat_2101582525_1_39 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE |
| dbo.OF_FP | _dta_stat_2101582525_1_39_6_7_3_2_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_39_6_7_3_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_39_7_3_2_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_40_2_34 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_1_40_3_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_40_41_43_3 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_41_43_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATA_PREVISTA, OFFP_TURN_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_43_16 | NONCLUSTERED |  |  | OFFP_ID, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_stat_2101582525_1_44 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_1_46_37_2 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_1_46_7_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_46_7_37_6 | NONCLUSTERED |  |  | OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_1_6_3_34_37_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ORDEM, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_1_6_3_34_7 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_1_7_37 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAFIM, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_1_8 | NONCLUSTERED |  |  | OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_stat_2101582525_16_3_2_7 | NONCLUSTERED |  |  | OFFP_SEQUENCIA, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_17_40 | NONCLUSTERED |  |  | OFFP_OFFPCL_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_1_3_46_37_38 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_FP_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_2_1_34_7_40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_3_1_34_7_40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_3_1_8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_PESO |
| dbo.OF_FP | _dta_stat_2101582525_2_3_37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_2_3_37_1_6_8 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_ID, OFFP_DATAINICIO, OFFP_PESO |
| dbo.OF_FP | _dta_stat_2101582525_2_3_37_6 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_2_3_37_7_1_41 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_2_3_6_37_34_1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_RETURN, OFFP_ORDEM, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_3_7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_2_37 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_2_41 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_2_44_3_41_7_40 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_DATAFIM, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_44_3_7 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_2_44_7_1 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_46_37_3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_2_6_3_34 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_2_7_37_3 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_20_1 | NONCLUSTERED |  |  | OFFP_PECAS, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_1_34_7 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_3_1_38_2_46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_stat_2101582525_3_17_2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OFFPCL_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_2_1_44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_3_2_1_44_41 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_3_2_1_44_43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_2_1_7_43_16 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_TURN_ID, OFFP_SEQUENCIA |
| dbo.OF_FP | _dta_stat_2101582525_3_2_37_7_38 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_3_2_40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_2_42 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_PLANEAMENTO |
| dbo.OF_FP | _dta_stat_2101582525_3_2_44_43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_34 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_3_37_7_1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_41_2_40_43_44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_3_41_2_44_43_1_40 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID, OFFP_OF_ID_MLD, OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_41_7_1_40_43_44 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_3_41_7_2_40_43 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_DATAFIM, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_42_1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_PLANEAMENTO, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_7_1_2_41 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_3_7_37_1_2_46 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_ID, OFFP_OF_ID, OFFP_COEFICIENTE_X |
| dbo.OF_FP | _dta_stat_2101582525_3_7_37_6_1 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_3_8_2 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_PESO, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_34_1_40_3_2 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_34_2_3_37_6 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_34_2_3_7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_34_2_40 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_34_2_6 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_34_7 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_34_7_2_3_6 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_DATAFIM, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_37_1_46_3 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_37_1_46_6_3 | NONCLUSTERED |  |  | OFFP_RETURN, OFFP_ID, OFFP_COEFICIENTE_X, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_38_3_2_7 | NONCLUSTERED |  |  | OFFP_OFFP_ID_RETURN, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_40_1_17 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_ID, OFFP_OFFPCL_ID |
| dbo.OF_FP | _dta_stat_2101582525_40_1_3_2_44 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_40_2 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_40_2_1_44 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD |
| dbo.OF_FP | _dta_stat_2101582525_40_3_2_42 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_PLANEAMENTO |
| dbo.OF_FP | _dta_stat_2101582525_40_3_2_6_1 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_40_3_41 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_40_43_44_2_1_7_41_3 | NONCLUSTERED |  |  | OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID, OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_41_1_2_3_37 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_41_1_3_2_8 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO |
| dbo.OF_FP | _dta_stat_2101582525_41_1_40_3_2 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_41_1_40_43_2_3 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_41_3_7_37_2 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_DATAFIM, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_41_40_43_7 | NONCLUSTERED |  |  | OFFP_DATA_PREVISTA, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_42_1 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_42_2_1 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_42_40_1 | NONCLUSTERED |  |  | OFFP_PLANEAMENTO, OFFP_TPCAM_ID, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_1_40 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_16_2 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_SEQUENCIA, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_2_1_44_40_3 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID, OFFP_ID, OFFP_OF_ID_MLD, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_3_2 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_3_41_2 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_FP_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_41_2 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_DATA_PREVISTA, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_43_44_2_1_40_41 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_43_44_2_40_41 | NONCLUSTERED |  |  | OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_TPCAM_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_44_2_1 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_ID |
| dbo.OF_FP | _dta_stat_2101582525_44_2_3_1_7_40_34 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_OF_ID, OFFP_FP_ID, OFFP_ID, OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_44_3_41 | NONCLUSTERED |  |  | OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_DATA_PREVISTA |
| dbo.OF_FP | _dta_stat_2101582525_46_1_3_2_6_7_37_38 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_ID, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_RETURN, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_46_37_1_38_2 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_RETURN, OFFP_ID, OFFP_OFFP_ID_RETURN, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_46_7_37_3_1_6 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_ID, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_46_7_37_6_3 | NONCLUSTERED |  |  | OFFP_COEFICIENTE_X, OFFP_DATAFIM, OFFP_RETURN, OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_6_2_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_6_2_7_34 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_6_3 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_6_3_2_1_40_42 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_ID, OFFP_TPCAM_ID, OFFP_PLANEAMENTO |
| dbo.OF_FP | _dta_stat_2101582525_6_3_2_42_40 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_OF_ID, OFFP_PLANEAMENTO, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_6_3_34_37_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ORDEM, OFFP_RETURN, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_6_3_34_7 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_FP_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | _dta_stat_2101582525_6_40_1_2 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_TPCAM_ID, OFFP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_6_7_3_2_8_37 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_7_1_2_40 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_OF_ID, OFFP_TPCAM_ID |
| dbo.OF_FP | _dta_stat_2101582525_7_1_40_3_2 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_ID, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_7_3_2_6_37_34 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_DATAINICIO, OFFP_RETURN, OFFP_ORDEM |
| dbo.OF_FP | _dta_stat_2101582525_7_3_2_8_37 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_FP_ID, OFFP_OF_ID, OFFP_PESO, OFFP_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_7_37_3_38 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_RETURN, OFFP_FP_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | _dta_stat_2101582525_7_40_3 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_7_40_3_2 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_7_40_43 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_TPCAM_ID, OFFP_TURN_ID |
| dbo.OF_FP | _dta_stat_2101582525_7_41_3_40_43_44_2 | NONCLUSTERED |  |  | OFFP_DATAFIM, OFFP_DATA_PREVISTA, OFFP_FP_ID, OFFP_TPCAM_ID, OFFP_TURN_ID, OFFP_OF_ID_MLD, OFFP_OF_ID |
| dbo.OF_FP | _dta_stat_2101582525_8_1_2_3_37_7_6 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_RETURN, OFFP_DATAFIM, OFFP_DATAINICIO |
| dbo.OF_FP | _dta_stat_2101582525_8_1_3 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_ID, OFFP_FP_ID |
| dbo.OF_FP | _dta_stat_2101582525_8_41_3 | NONCLUSTERED |  |  | OFFP_PESO, OFFP_DATA_PREVISTA, OFFP_FP_ID |
| dbo.OF_FP | 2025_11_06_13_40_01 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_VALOR_CONTROL_1, OFFP_VALOR_CONTROL_2, OFFP_VALOR_CONTROL_3, OFFP_OF_ID |
| dbo.OF_FP | IX_OF_FP | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | IX_OF_FP_OFFP_DATAINICIO_OFFP_OF_ID_OFFP_FP_ID | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID, OFFP_FP_ID |
| dbo.OF_FP | NonClusteredIndex-20171114-103038 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ORDEM, OFFP_FP_ID |
| dbo.OF_FP | NonClusteredIndex-20171213-164141 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_ID, OFFP_OF_ID, OFFP_OFFP_ID_RETURN |
| dbo.OF_FP | NonClusteredIndex-20180126-111903 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_OFFPCL_ID, OFFP_FP_ID |
| dbo.OF_FP | NonClusteredIndex-20181204-104053 | NONCLUSTERED |  |  | OFFP_DATAINICIO, OFFP_OF_ID_MLD, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_FP | NonClusteredIndex-20190604-114035 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_FP_ID, OFFP_PROBS_DATA, OFFP_PROBS_LAM_INOCENTE |
| dbo.OF_FP | NonClusteredIndex-20190618-155507 | NONCLUSTERED |  |  | OFFP_OF_ID, OFFP_ORDEM, OFFP_DATAFIM |
| dbo.OF_FP | NonClusteredIndex-20190618-155617 | NONCLUSTERED |  |  | OFFP_ORDEM, OFFP_OF_ID, OFFP_DATAFIM |
| dbo.OF_FP | NonClusteredIndex-20190619-155619 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_DATAFIM, OFFP_ORDEM, OFFP_FP_ID, OFFP_RETURN |
| dbo.OF_FP | NonClusteredIndex-20190619-155620 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_RETURN |
| dbo.OF_FP | NonClusteredIndex-20191111-163400 | NONCLUSTERED |  |  | OFFP_FP_ID, OFFP_OF_ID_MLD, OFFP_DATAINICIO |
| dbo.OF_FP | NonClusteredIndex-20191119-102654 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_DATAFIM |
| dbo.OF_FP | NonClusteredIndex-20191119-103816 | NONCLUSTERED |  |  | OFFP_ID, OFFP_OF_ID, OFFP_RETURN, OFFP_OFFP_ID_RETURN, OFFP_COEFICIENTE, OFFP_FP_ID, OFFP_DATAFIM |
| dbo.OF_FP | OFFP_20211025_1049 | NONCLUSTERED |  |  | OFFP_ID, OFFP_FP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_OF_ID |
| dbo.OF_FP | OFFP_20211025_1050 | NONCLUSTERED |  |  | OFFP_ID, OFFP_DATAINICIO, OFFP_DATAFIM, OFFP_ORDEM, OFFP_RETURN, OFFP_FP_ID, OFFP_OF_ID |
| dbo.OF_LOTE | PK_OF_LOTE_1 | CLUSTERED | Y | Y | OFL_ID |
| dbo.OF_LOTE | _dta_index_OF_LOTE_7_555149023__K2 | NONCLUSTERED |  |  | OFL_OF_ID |
| dbo.OF_OF_TIPOUSO | PK_OF_OF_TIPOUSO_1 | CLUSTERED | Y | Y | OFOFTU_ID |
| dbo.OF_OF_TIPOUSO | _dta_index_OF_OF_TIPOUSO_7_587149137__K6 | NONCLUSTERED |  |  | OFOFTU_DATAPAGAMENTO |
| dbo.OF_PROPRIETARIO | PK_OF_PROPRIETARIO | CLUSTERED | Y | Y | OFPROP_OF_ID, OFPROP_E_ID |
| dbo.OF_RENTAL_PROVAS | PK_OF_RENTAL_PROVAS | CLUSTERED | Y | Y | OFR_OF_ID, OFR_BOOKING_ID |
| dbo.OF_TIPOUSO | PK_OF_TIPOUSO | CLUSTERED | Y | Y | OFTU_ID |
| dbo.OF_VENDA | PK_OF_VENDA | CLUSTERED | Y | Y | OFV_ID |
| dbo.OFCH_LOCAL | PK_OFCH_LOCAL | CLUSTERED | Y | Y | OFPROBS_OFCH_ID, OFPROBS_PROBSL_ID |
| dbo.OFCH_LOCAL | _dta_index_OFCH_LOCAL_7_619149251__K1_2 | NONCLUSTERED |  |  | OFPROBS_PROBSL_ID, OFPROBS_OFCH_ID |
| dbo.OFCH_LOCAL | _dta_index_OFCH_LOCAL_7_619149251__K2 | NONCLUSTERED |  |  | OFPROBS_PROBSL_ID |
| dbo.OFFP_CL | PK_OFFP_CL | CLUSTERED | Y | Y | OFFPCL_ID |
| dbo.OFFP_EQ | PK_OFFP_EQ | CLUSTERED | Y | Y | OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_2 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_2_9987 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2_1771 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2_3 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2_3_3426 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2_K3 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K2_K3_8809 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3_2 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3_2_2533 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3_4364 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3_K2 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K1_K3_K2_4149 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2 | NONCLUSTERED |  |  | OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_1 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_1_3 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_1_3_5150 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_1_4288 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_3982 | NONCLUSTERED |  |  | OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K1 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K1_3 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K1_3_2649 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K1_K3 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K1_K3_5201 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_OFFP_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3_1 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3_1_8066 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3_9085 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3_K1 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K2_K3_K1_9850 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3 | NONCLUSTERED |  |  | OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_1_2 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_1_2_8066 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_2 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_2_6221 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_6960 | NONCLUSTERED |  |  | OFFPEQ_CHEFE |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K1 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K1_2 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K1_2_4149 | NONCLUSTERED |  |  | OFFPEQ_E_ID, OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K1_6478 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K1_K2 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_OFFP_ID, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K2 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K2_1 | NONCLUSTERED |  |  | OFFPEQ_OFFP_ID, OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K2_3928 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K2_K1 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_EQ | _dta_index_OFFP_EQ_7_2099048__K3_K2_K1_4864 | NONCLUSTERED |  |  | OFFPEQ_CHEFE, OFFPEQ_E_ID, OFFPEQ_OFFP_ID |
| dbo.OFFP_GRAVIDADE | PK_OFFP_GRAVIDADE | CLUSTERED | Y | Y | OFFPGRAV_ID |
| dbo.OFFP_GRAVIDADES | PK_OFFP_GRAVIDADES | CLUSTERED | Y | Y | FPGRAV_OFFP_ID, FPGRAV_OFFPGRAV_ID |
| dbo.OFFP_PROBLEMA | PK_OFFP_PROBLEMA | CLUSTERED | Y | Y | OFFPPROB_PROBS_ID, OFFPPROB_OFFP_ID, OFFPPROB_PROBSL_ID |
| dbo.ORCAMENTO | PK__ORCAMENT__3213E83FC36BA2F1 | CLUSTERED | Y | Y | id |
| dbo.ORCAMENTO_PRODUTO | PK__ORCAMENT__3213E83FF8E1E2ED | CLUSTERED | Y | Y | id |
| dbo.ORDEMFABRICO | PK_ORDEMFABRICO | CLUSTERED | Y | Y | OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1 | NONCLUSTERED |  |  | OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_10_31_37 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_10_31_37_4364 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_10_4149 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_1040 | NONCLUSTERED |  |  | OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_13_31_33_37_38 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_2_3_4_5_6_7_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_ | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAENTREGA, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_DATAFIM, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_MORADAENTREGA, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_COEFICIENTE, OF_PAGO, OF_DECKPINTURA, OF_CASCOPINTURA, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_SEQUENCIA, OF_OFTU_ID, OF_TURN_ID, OF_ENC_ID, OF_P_ID, OF_E_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_OF_ID_MLD, OF_FP_ID, OF_TR_ID, OF_MOLDE_ACESSORIO, OF_CRIADOR, OF_ACTUALIZADOR, OF_DATAACTUALIZACAO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_NUMUTIL, OF_CUSTOS_CACHE, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_P_ID_HIST, OF_REVISTO, OF_PARAPINTARFORA, OF_PREPREG, OF_TR_ID_ULT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_P_ID_AUTOCOLANTE, OF_TAG_ID, OF_PRECOCUSTO_DT, OF_UPDT, OF_ACERTO_RESINA, OF_SEQUENCIA_UPD, OF_PINT_CLASS, OF_PFORA_CLASS, OF_LINHAACAB, OF_ARM_FIXO, OF_COEFICIENTE_EXTRA, OF_VERSAO_NOVA, OF_EM_ID, OF_EM_ID_FACTURACAO, OF_OF_ID_MAE, OF_MOV_ID, OF_PROMO_CODE, OF_DATA_PROMO_DEALER, OF_DATA_PROMO_CLIENT, OF_PESO_DECK, OF_PESO_CASCO, OF_FALTA_MASCARA, OF_FALTA_DOCS_CLIENTE, OF_PROMO_EMAIL, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_31_32_33_37_38_43_44_4_5201 | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_P_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_EM_ID, OF_EM_ID_FACTURACAO, OF_PROMO_CODE, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_31_32_33_37_38_43_44_45_46_ | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_P_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_EM_ID, OF_EM_ID_FACTURACAO, OF_PROMO_CODE, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_2_5_10_11_13_17_19_22_27_28_31_33_37_48_53_81 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_OFTU_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_EM_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_2_8_13_31_33_37_38_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_21_34_35_43_44_45_46_47_55 | NONCLUSTERED |  |  | OF_COEFICIENTE, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_21_77 | NONCLUSTERED |  |  | OF_COEFICIENTE, OF_LINHAACAB, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_31 | NONCLUSTERED |  |  | OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_31_33_34_35_37_43_44_45_46_47 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_31_5081 | NONCLUSTERED |  |  | OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_31_75_76_79 | NONCLUSTERED |  |  | OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_33 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_33_38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_37_50 | NONCLUSTERED |  |  | OF_FP_ID, OF_NUMUTIL, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_37_50_6497 | NONCLUSTERED |  |  | OF_FP_ID, OF_NUMUTIL, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_38 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_4364 | NONCLUSTERED |  |  | OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_48 | NONCLUSTERED |  |  | OF_ARM_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_7 | NONCLUSTERED |  |  | OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_7_8_11_13_26_31_33_37_57_60_65_73 | NONCLUSTERED |  |  | OF_DATAFIM, OF_OBSERVACOES, OF_NOME, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_75_76_79 | NONCLUSTERED |  |  | OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_11_13_26_31_33_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_E_ID_ENC, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_13_26_31_33_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_E_ID_ENC, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_25_31_33_37_43_44_45_46_47_50_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_25_31_33_37_43_44_45_46_47_50_55_56_73_4149 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_25_31_33_43_44_45_46_47_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID, OF_E_ID_ENC, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_25_31_33_43_44_45_46_47_55_56_73_1912 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID, OF_E_ID_ENC, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_31_33_37_38 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_31_33_37_38_9073 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_31_57 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_DESCONTA_PESO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_31_57_75_76_79 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_DESCONTA_PESO, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_33_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_TR_DATA_PREVISTA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_8_33_66_3923 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_TR_DATA_PREVISTA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_88_89 | NONCLUSTERED |  |  | OF_PESO_DECK, OF_PESO_CASCO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K2 | NONCLUSTERED |  |  | OF_ID, OF_DATA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K26_K49_11_31_33 | NONCLUSTERED |  |  | OF_NOME, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_SUPERVISAOLAMINAGEM, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K26_K49_31_33 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_ID, OF_SUPERVISAOLAMINAGEM, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K28_K31_K33_K37_K48_K81_2_5_10_11_13_17_19_22_27_53 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_FACT, OF_ID, OF_OFTU_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31 | NONCLUSTERED |  |  | OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_3982 | NONCLUSTERED |  |  | OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_57 | NONCLUSTERED |  |  | OF_DESCONTA_PESO, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_75_76_79 | NONCLUSTERED |  |  | OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_8_57 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_DESCONTA_PESO, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_8_57_75_76_79 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_DESCONTA_PESO, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_13_9953 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_1410 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_8_25_37_43_44_45_46_47_50_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K29_8_11_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K37_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K37_K38_K27_K60_8_34_35_1912 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K38 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K38_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_11 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K49_K26 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID_LAM, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K49_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID_LAM, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K75_K76_K79_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K33_K75_K76_K79_13_1623 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_11_88_89 | NONCLUSTERED |  |  | OF_NOME, OF_PESO_DECK, OF_PESO_CASCO, OF_ID, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_8258 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K33_2_6_10_11_13_19_53_62_64_9987 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K33_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K33_K38_8_5543 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K38 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K37_K38_K33_2_13 | NONCLUSTERED |  |  | OF_DATA, OF_REFERENCIA, OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K38_K33_K32_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_ID, OF_P_ID, OF_TR_ID, OF_E_ID_ENC, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K38_K37_K33_K32_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_ID, OF_P_ID, OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K49_K33_11_26 | NONCLUSTERED |  |  | OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_ID, OF_P_ID, OF_ARM_ID_LAM, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K49_K33_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID, OF_P_ID, OF_ARM_ID_LAM, OF_E_ID_ENC, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K7 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K7_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_P_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K7_K37 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K7_K37_508 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K81_K82_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_3_4864 | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_ID, OF_P_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K31_K81_K82_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_38_43_ | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_ID, OF_P_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_13_31_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_4288 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_8_66_1771 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K10 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_13_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_11_13_26_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_13_26_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_25_37_43_44_45_46_47_50_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_25_37_43_44_45_46_47_50_55_56_73_2533 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_25_43_44_45_46_47_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_8_25_43_44_45_46_47_55_56_73_114 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K29_8_11_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K29_8_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K32_K38_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37_K32_K38_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K37_K38_K27_K60_8_34_35_6960 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K38 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K38_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_11 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K75_K76_K79_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K75_K76_K79_13_8258 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K31_K75_K76_K79_8_13_37_38 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_2_6_10_11_13_19_53_62_64_1912 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_8_66_9910 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_K38 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K31_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K38_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K37_K38_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K38 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K38_K37_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K38_K37_K31_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K49_K31_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID, OF_E_ID_ENC, OF_ARM_ID_LAM, OF_P_ID, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K33_K7_K10 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_DATAFIM, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_31 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_31_5492 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_8_31_33_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_TR_DATA_PREVISTA, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_8_31_33_66_4864 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_TR_DATA_PREVISTA, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_8526 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_11 | NONCLUSTERED |  |  | OF_NOME, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_11_88_89 | NONCLUSTERED |  |  | OF_NOME, OF_PESO_DECK, OF_PESO_CASCO, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_9987 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_2_6_10_11_13_19_53_62_64_8809 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_8_66_1912 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_K38 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_K38_8_3923 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K33_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K31_K38 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33_K31_K38 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33_K31_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33_K31_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33_K31_K38_K27_K60_8_34_35_9429 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K33_K38_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K38_K31_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_ID, OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K38_K31_10_8066 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_ID, OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K54 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K60 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K7 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K37_K7_K31 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_9850 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K31_K33_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_TR_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_13_31_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_FP_ID, OF_ID, OF_TR_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K31 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K31_13_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K31_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K31_K37_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K31_K37_K27_K60_8_34_35_8258 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K33_K37_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_ID, OF_TR_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K37 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K37_K33_K31 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K38_K37_K33_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_11_31_33 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_31_33 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_2_8_13_31_33_37_38_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K31 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K31_K38_K33_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_SUPERVISAOPINTURA, OF_P_ID, OF_TR_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K33 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K33_K38_K31_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_SUPERVISAOPINTURA, OF_E_ID_ENC, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K37 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K38 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K54_K38_K31_K33_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_ID, OF_SUPERVISAOPINTURA, OF_TR_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K6_K29 | NONCLUSTERED |  |  | OF_ID, OF_DATAINICIO, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K60_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_1040 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_31 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_31_37 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K31 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K31_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K33_K10 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_E_ID_ENC, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K37 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K37_2555 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K37_31 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K37_K31 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K7_K37_K31_2679 | NONCLUSTERED |  |  | OF_ID, OF_DATAFIM, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K75_K76_K79 | NONCLUSTERED |  |  | OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K75_K76_K79_6497 | NONCLUSTERED |  |  | OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K75_K76_K79_K31_K33_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K1_K75_K76_K79_K31_K33_13_742 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K10_K1_33 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_PRECOVENDA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K10_K1_K7_33 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_PRECOVENDA, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K2_K1 | NONCLUSTERED |  |  | OF_DATA, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K22_K1_K31_K33_K32_2_5_10_11_13_17_28_37_38_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_TR_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_PAGO, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_E_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K27_K60D_K33_K31_K1_8_34_35_37_38 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K27_K60D_K33_K31_K1_8_34_35_37_38_114 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K27_K60D_K37_K1_8_31_33_34_35_38 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K28_K1_K31_K33_K37_K48_K81_2_5_10_11_13_17_19_22_27_53 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_FACT, OF_OFTU_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K29_K1_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_TURN_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K29_K1_8_11_31_33_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_TURN_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K29_K1_8_31_33_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_TURN_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K29_K1_K6 | NONCLUSTERED |  |  | OF_TURN_ID, OF_ID, OF_DATAINICIO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K30 | NONCLUSTERED |  |  | OF_ENC_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K30_K37 | NONCLUSTERED |  |  | OF_ENC_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31 | NONCLUSTERED |  |  | OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_1 | NONCLUSTERED |  |  | OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_1_2_6_10_11_13_19_37_53_62_64 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FP_ID, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_1_2_6_10_11_13_19_37_53_62_64_4364 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FP_ID, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_1_33 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_37_1912 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_8066 | NONCLUSTERED |  |  | OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_3369 | NONCLUSTERED |  |  | OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_57 | NONCLUSTERED |  |  | OF_DESCONTA_PESO, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_75_76_79 | NONCLUSTERED |  |  | OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_8_57_75_76_79 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_DESCONTA_PESO, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_8_11_13_26_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_8_25_37_43_44_45_46_47_50_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_8_25_37_43_44_45_46_47_50_55_56_73_6355 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K29_8_11_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K32_K38_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37_K32_K38_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K37_K38_K27_K60_8_34_35_5492 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K38 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K38_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K38_K37_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_11 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K49_11_26 | NONCLUSTERED |  |  | OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K49_26 | NONCLUSTERED |  |  | OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K75_K76_K79_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K33_K75_K76_K79_13_6221 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_ID, OF_E_ID_ENC, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_11 | NONCLUSTERED |  |  | OF_NOME, OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_4364 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K33_2_6_10_11_13_19_53_62_64_6497 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K33_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K33_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K33_K38_8_742 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K37_K38 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K38_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K49_K33_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_P_ID, OF_ID, OF_ARM_ID_LAM, OF_E_ID_ENC, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K54 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K54_K38_K33_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_P_ID, OF_ID, OF_SUPERVISAOPINTURA, OF_TR_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K7 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K7_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K7_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K7_K37_8086 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K81_K82_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_3_6497 | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_P_ID, OF_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K1_K81_K82_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_38_43_ | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_P_ID, OF_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K28_K1_K33_K37_K48_K81_2_5_10_11_13_17_19_22_27_53 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_FACT, OF_P_ID, OF_OFTU_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_1_2_6_10_11_13_19_37_53_62_64 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FP_ID, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_1_2_6_10_11_13_19_37_53_62_64_5201 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FP_ID, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_P_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_13_5201 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_4683 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_K37_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_K38_K37_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_K75_K76_K79_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K1_K75_K76_K79_13_9762 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K33_K37_1_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_1_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_11 | NONCLUSTERED |  |  | OF_NOME, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_11_88_89 | NONCLUSTERED |  |  | OF_NOME, OF_PESO_DECK, OF_PESO_CASCO, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_3928 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_8_66_6497 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_K38 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K33_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K1_K38 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K38_1 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K38_K1_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K38_K1_10_1040 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K37_K7_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K38_1_2_13_37 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_REFERENCIA, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K38_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K38_K37_1 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K49_K1_K33_11_26 | NONCLUSTERED |  |  | OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_ARM_ID_LAM, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K7 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K7_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K7_K37_K1 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K7_K37_K1_8917 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K81_K82_K1_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_3_4149 | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_P_ID, OF_EM_ID, OF_EM_ID_FACTURACAO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K81_K82_K1_2_3_5_6_8_9_10_11_13_14_15_16_17_18_19_20_22_25_26_28_30_32_33_37_38_43_ | NONCLUSTERED |  |  | OF_DATA, OF_DATATRANSPORTE, OF_DATAPAGAMENTO, OF_DATAINICIO, OF_OBSERVACOES, OF_PRECOCUSTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TELEFONE, OF_EMAIL, OF_TRANSPORTE, OF_TRANSPORTEDOC, OF_AUTOCOLANTE, OF_DESCONTO, OF_VALORPAGO, OF_PAGO, OF_SUPERVISAO, OF_SUPERVISAOLAMINAGEM, OF_OFTU_ID, OF_ENC_ID, OF_E_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_ARM_ID_LAM, OF_TRANSP, OF_FACT, OF_SUPERVISAOPINTURA, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_DESCONTA_PESO, OF_REVISTO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_LINHAACAB, OF_PROMO_CODE, OF_P_ID, OF_EM_ID, OF_EM_ID_FACTURACAO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K31_K83_1 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_OF_ID_MAE |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33 | NONCLUSTERED |  |  | OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_1 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_1_10_19_31 | NONCLUSTERED |  |  | OF_ID, OF_PRECOVENDA, OF_DESCONTO, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_1_1040 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_10_19_31 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_2894 | NONCLUSTERED |  |  | OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_2_8_13_31_37_38_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_8809 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K10 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_13_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_8_11_13_26_57_60_65_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_REFERENCIA, OF_SUPERVISAOLAMINAGEM, OF_DESCONTA_PESO, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_ACERTO_RESINA, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_8_25_37_43_44_45_46_47_50_55_56_73 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_8_25_37_43_44_45_46_47_50_55_56_73_4864 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_SUPERVISAO, OF_FP_ID, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_NUMUTIL, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_ACERTO_RESINA, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K29_8_11_34_35_43_44_45_46_47_48_55_56_60 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_ARM_ID, OF_P_ID_QUINAS_TR, OF_P_ID_GOLA, OF_PARAPINTARFORA, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K37_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K37_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K37_K38_8_114 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K37_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K37_K38_K27_K60_8_34_35_6478 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K38_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K38_K37_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K48_K34_K35_K56_K45_K46_K47_K55_K43_K44_K29_K60_8_11 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_NOME, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K75_K76_K79_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K31_K75_K76_K79_13_1040 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_2_6_10_11_13_19_53_62_64_4149 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_8_66_1410 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_K38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K31_K38_8_7027 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K38_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K37_K38_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K38_K31_13_37 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K38_K37_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_ID, OF_TR_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K49_K31_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_E_ID_ENC, OF_ID, OF_ARM_ID_LAM, OF_P_ID, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K54 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K54_K38_K31_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_E_ID_ENC, OF_ID, OF_SUPERVISAOPINTURA, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K1_K7_K10 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_DATAFIM, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K28_K1_K31_K37_K48_K81_2_5_10_11_13_17_19_22_27_53 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_FACT, OF_E_ID_ENC, OF_OFTU_ID, OF_ID, OF_P_ID, OF_FP_ID, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K1_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K1_K32_K38_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_P_ID, OF_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K1_K38_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_E_ID_ENC, OF_P_ID, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K32_K22_K1_2_5_10_11_13_17_28_37_38_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_TR_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_P_ID, OF_E_ID, OF_PAGO, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K1_K32_K38_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K1_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K1_K38_K27_K60_8_34_35_2533 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K37_K38_K1_K32_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_TR_ID, OF_ID, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K38_K1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K38_K1_K32_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_ID, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K31_K49_K1_11_26 | NONCLUSTERED |  |  | OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_E_ID_ENC, OF_P_ID, OF_ARM_ID_LAM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K32_K31_K1_K38_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_E_ID, OF_P_ID, OF_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K37_K1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K37_K1_K31_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_E_ID_ENC, OF_FP_ID, OF_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K37_K1_K31_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_E_ID_ENC, OF_FP_ID, OF_ID, OF_P_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K37_K31_K1_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K33_K37_K31_K1_2_6_10_11_13_19_53_62_64_114 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_E_ID_ENC, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37 | NONCLUSTERED |  |  | OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_1 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_1_11_31 | NONCLUSTERED |  |  | OF_ID, OF_NOME, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_1_13_31_33_38 | NONCLUSTERED |  |  | OF_ID, OF_REFERENCIA, OF_P_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_170 | NONCLUSTERED |  |  | OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_1973 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_31 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_31_1912 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_31_33_38 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_6_31_33_38 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_P_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K27_K60_8_31_33_34_35_38 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID, OF_E_ID_ENC, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_TR_ID, OF_FP_ID, OF_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_11 | NONCLUSTERED |  |  | OF_NOME, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_11_88_89 | NONCLUSTERED |  |  | OF_NOME, OF_PESO_DECK, OF_PESO_CASCO, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_6221 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_2_6_10_11_13_19_53_62_64_5543 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_8_66 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_8_66_5543 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_DATA_PREVISTA, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K32_K38_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K38 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K31_K33_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K31_K38 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K31_K38_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K31_K38_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K31_K38_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K31_K38_K27_K60_8_34_35_2166 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K33_K38_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K38 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K38_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K38_K31_K33_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_FP_ID, OF_ID, OF_TR_ID, OF_P_ID, OF_E_ID_ENC, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K54 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K60 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K7_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K1_K7_K31_4364 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K28_K1_K31_K33_K48_K81_2_5_10_11_13_17_19_22_27_53 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_DESCONTO, OF_PAGO, OF_SEQUENCIA, OF_FACT, OF_FP_ID, OF_OFTU_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K30 | NONCLUSTERED |  |  | OF_FP_ID, OF_ENC_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_11 | NONCLUSTERED |  |  | OF_NOME, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_2_6_10_11_13_19_53_62_64_9987 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_6497 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_K33_2_6_10_11_13_19_53_62_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_K33_2_6_10_11_13_19_53_62_64_8066 | NONCLUSTERED |  |  | OF_DATA, OF_DATAINICIO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_DESCONTO, OF_FACT, OF_TR_ID_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K31_K1_K38 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33 | NONCLUSTERED |  |  | OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K1 | NONCLUSTERED |  |  | OF_FP_ID, OF_E_ID_ENC, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K1_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K1_K31_K38_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K1_K38_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K31_K1_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K33_K32_K31_K1_K38_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_FP_ID, OF_E_ID_ENC, OF_E_ID, OF_P_ID, OF_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_1 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_K1 | NONCLUSTERED |  |  | OF_FP_ID, OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_K31_9987 | NONCLUSTERED |  |  | OF_FP_ID, OF_TR_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_K31_K1_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_FP_ID, OF_TR_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K38_K31_K1_10_5201 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_FP_ID, OF_TR_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K7_K1 | NONCLUSTERED |  |  | OF_FP_ID, OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K7_K1_31 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID, OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K37_K7_K1_K31 | NONCLUSTERED |  |  | OF_FP_ID, OF_DATAFIM, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38 | NONCLUSTERED |  |  | OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_3227 | NONCLUSTERED |  |  | OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_2894 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K31_K33_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_TR_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K31_K33_K54_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_TR_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K31_K37_K33_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_ID, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K31_K37_K33_8_3982 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_ID, OF_ID, OF_P_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K31 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K31_2_8_13_37_54_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_SUPERVISAOPINTURA, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K31_K37_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K31_K37_K27_K60_8_34_35_5201 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K37_10_19 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_DESCONTO, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K33_K37_K31_6 | NONCLUSTERED |  |  | OF_DATAINICIO, OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K31_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_TR_ID, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K31_K33_2_13 | NONCLUSTERED |  |  | OF_DATA, OF_REFERENCIA, OF_TR_ID, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K31_K33_8 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_ID, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K31_K33_8_9987 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_TR_ID, OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K33_K31 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K37_K33_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_TR_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K54 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K1_K54_K31_K33_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_TR_ID, OF_ID, OF_SUPERVISAOPINTURA, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K31_K37_K1_2_13 | NONCLUSTERED |  |  | OF_DATA, OF_REFERENCIA, OF_TR_ID, OF_P_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K33_K31 | NONCLUSTERED |  |  | OF_TR_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K33_K31_K1_K32_K22_2_5_10_11_13_17_28_37_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_FP_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_TR_ID, OF_E_ID_ENC, OF_P_ID, OF_ID, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K33_K31_K37 | NONCLUSTERED |  |  | OF_TR_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K33_K31_K37_K1_K32_K22_2_5_10_11_13_17_28_48_53_63_64 | NONCLUSTERED |  |  | OF_DATA, OF_DATAPAGAMENTO, OF_PRECOVENDA, OF_NOME, OF_REFERENCIA, OF_TRANSPORTEDOC, OF_OFTU_ID, OF_ARM_ID, OF_FACT, OF_TR_DESC_ULT, OF_TR_DATA_ULT, OF_TR_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_ID, OF_E_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_1 | NONCLUSTERED |  |  | OF_ID, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K1 | NONCLUSTERED |  |  | OF_TR_ID, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K1_K31 | NONCLUSTERED |  |  | OF_TR_ID, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K1_K31_K33_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_TR_ID, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K1_K31_K33_K27_K60_8_34_35 | NONCLUSTERED |  |  | OF_OBSERVACOES, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_TR_ID, OF_FP_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K31_K1_10 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_TR_ID, OF_FP_ID, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K33_K1_K31_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K38_K37_K33_K31_K1_13 | NONCLUSTERED |  |  | OF_REFERENCIA, OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_1_11_26_31_33 | NONCLUSTERED |  |  | OF_ID, OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_1_26_31_33 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOLAMINAGEM, OF_P_ID, OF_E_ID_ENC, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_K1_K31_K33_K26 | NONCLUSTERED |  |  | OF_ARM_ID_LAM, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_K1_K31_K33_K26_11 | NONCLUSTERED |  |  | OF_NOME, OF_ARM_ID_LAM, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_K31_K1_K33_11_26 | NONCLUSTERED |  |  | OF_NOME, OF_SUPERVISAOLAMINAGEM, OF_ARM_ID_LAM, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K49_K31_K1_K33_26 | NONCLUSTERED |  |  | OF_SUPERVISAOLAMINAGEM, OF_ARM_ID_LAM, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K54 | NONCLUSTERED |  |  | OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K54_K1_K37 | NONCLUSTERED |  |  | OF_SUPERVISAOPINTURA, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K54_K38_K1_K31_K33_2_8_13_37_60_65_66_67_68 | NONCLUSTERED |  |  | OF_DATA, OF_OBSERVACOES, OF_REFERENCIA, OF_FP_ID, OF_PARAPINTARFORA, OF_PARAALTERAR, OF_TR_DATA_PREVISTA, OF_PLANO_DATA_PREVISTA, OF_PLANO_TURNO_PREVISTO, OF_SUPERVISAOPINTURA, OF_TR_ID, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K60_K1_K37 | NONCLUSTERED |  |  | OF_PARAPINTARFORA, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7 | NONCLUSTERED |  |  | OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_1912 | NONCLUSTERED |  |  | OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K1 | NONCLUSTERED |  |  | OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K1_K31 | NONCLUSTERED |  |  | OF_DATAFIM, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K1_K31_37 | NONCLUSTERED |  |  | OF_FP_ID, OF_DATAFIM, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K1_K33_K10 | NONCLUSTERED |  |  | OF_DATAFIM, OF_ID, OF_E_ID_ENC, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K1_K37_K31 | NONCLUSTERED |  |  | OF_DATAFIM, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K31 | NONCLUSTERED |  |  | OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K31_K1 | NONCLUSTERED |  |  | OF_DATAFIM, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1 | NONCLUSTERED |  |  | OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1_31 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1_31_7281 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1_3369 | NONCLUSTERED |  |  | OF_DATAFIM, OF_FP_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1_K31 | NONCLUSTERED |  |  | OF_DATAFIM, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K7_K37_K1_K31_1410 | NONCLUSTERED |  |  | OF_DATAFIM, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K83_1_31 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_OF_ID_MAE |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K83_K31_1 | NONCLUSTERED |  |  | OF_ID, OF_OF_ID_MAE, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K91 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K91_4364 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K91_K1 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE, OF_ID |
| dbo.ORDEMFABRICO | _dta_index_ORDEMFABRICO_7_2021582240__K91_K1_K2 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE, OF_ID, OF_DATA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_2 | NONCLUSTERED |  |  | OF_ID, OF_DATA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_26_49 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOLAMINAGEM, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_28_31_33_37_48_81 | NONCLUSTERED |  |  | OF_ID, OF_OFTU_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_ARM_ID, OF_EM_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_31_33_37_38_27_60 | NONCLUSTERED |  |  | OF_ID, OF_P_ID, OF_E_ID_ENC, OF_FP_ID, OF_TR_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_33_31_37_32_38_22 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID, OF_FP_ID, OF_E_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_33_31_48_34_35_56_45_46_47_55_43_44_29_60 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_P_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_33_38_37 | NONCLUSTERED |  |  | OF_ID, OF_E_ID_ENC, OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_37_31_33 | NONCLUSTERED |  |  | OF_ID, OF_FP_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_48_34_35_56_45_46_47_55_43_44_29_60 | NONCLUSTERED |  |  | OF_ID, OF_ARM_ID, OF_P_ID_CDECK, OF_P_ID_CCASCO, OF_P_ID_GOLA, OF_P_ID_LATERAL_FR, OF_P_ID_LATERAL_TR, OF_P_ID_QUINAS, OF_P_ID_QUINAS_TR, OF_P_ID_TOPO_FR, OF_P_ID_TOPO_TR, OF_TURN_ID, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_54 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_54_37 | NONCLUSTERED |  |  | OF_ID, OF_SUPERVISAOPINTURA, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_6 | NONCLUSTERED |  |  | OF_ID, OF_DATAINICIO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_1_75_76_79_31_33 | NONCLUSTERED |  |  | OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS, OF_COEFICIENTE_EXTRA, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_10_1_7 | NONCLUSTERED |  |  | OF_PRECOVENDA, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_22_1_31_33 | NONCLUSTERED |  |  | OF_PAGO, OF_ID, OF_P_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_27_60_33_31_1 | NONCLUSTERED |  |  | OF_SEQUENCIA, OF_PARAPINTARFORA, OF_E_ID_ENC, OF_P_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_27_60_37 | NONCLUSTERED |  |  | OF_SEQUENCIA, OF_PARAPINTARFORA, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_29_1 | NONCLUSTERED |  |  | OF_TURN_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_29_1_6 | NONCLUSTERED |  |  | OF_TURN_ID, OF_ID, OF_DATAINICIO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_30_37 | NONCLUSTERED |  |  | OF_ENC_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_1_33_29 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_E_ID_ENC, OF_TURN_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_1_37_33_38 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_FP_ID, OF_E_ID_ENC, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_1_54 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_1_81_82 | NONCLUSTERED |  |  | OF_P_ID, OF_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_28 | NONCLUSTERED |  |  | OF_P_ID, OF_OFTU_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_33_1_75_76 | NONCLUSTERED |  |  | OF_P_ID, OF_E_ID_ENC, OF_ID, OF_PINT_CLASS, OF_PFORA_CLASS |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_37 | NONCLUSTERED |  |  | OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_7_37 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_81_82 | NONCLUSTERED |  |  | OF_P_ID, OF_EM_ID, OF_EM_ID_FACTURACAO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_31_83 | NONCLUSTERED |  |  | OF_P_ID, OF_OF_ID_MAE |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_1_10 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_1_37 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_1_49_31_26 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_ARM_ID_LAM, OF_P_ID, OF_SUPERVISAOLAMINAGEM |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_1_54_38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_SUPERVISAOPINTURA, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_1_7_10 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_DATAFIM, OF_PRECOVENDA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_28_1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_OFTU_ID, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_31_32_22_1 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_E_ID, OF_PAGO, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_31_37 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_31_38 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_31_49 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_P_ID, OF_ARM_ID_LAM |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_33_32_31_1_38_22 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_E_ID, OF_P_ID, OF_ID, OF_TR_ID, OF_PAGO |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_37_1_27_60 | NONCLUSTERED |  |  | OF_FP_ID, OF_ID, OF_SEQUENCIA, OF_PARAPINTARFORA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_37_28_1_31 | NONCLUSTERED |  |  | OF_FP_ID, OF_OFTU_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_37_33_32_31 | NONCLUSTERED |  |  | OF_FP_ID, OF_E_ID_ENC, OF_E_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_1_31_33_54 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_P_ID, OF_E_ID_ENC, OF_SUPERVISAOPINTURA |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_1_33_31 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_1_37_31 | NONCLUSTERED |  |  | OF_TR_ID, OF_ID, OF_FP_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_33 | NONCLUSTERED |  |  | OF_TR_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_37 | NONCLUSTERED |  |  | OF_TR_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_37_33 | NONCLUSTERED |  |  | OF_TR_ID, OF_FP_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_38_37_33_31 | NONCLUSTERED |  |  | OF_TR_ID, OF_FP_ID, OF_E_ID_ENC, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_49_1 | NONCLUSTERED |  |  | OF_ARM_ID_LAM, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_49_31_1_33 | NONCLUSTERED |  |  | OF_ARM_ID_LAM, OF_P_ID, OF_ID, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_54_38_1_31 | NONCLUSTERED |  |  | OF_SUPERVISAOPINTURA, OF_TR_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_60_1_37 | NONCLUSTERED |  |  | OF_PARAPINTARFORA, OF_ID, OF_FP_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_7_37_1_31 | NONCLUSTERED |  |  | OF_DATAFIM, OF_FP_ID, OF_ID, OF_P_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_91_1 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE, OF_ID |
| dbo.ORDEMFABRICO | _dta_stat_2021582240_91_1_2 | NONCLUSTERED |  |  | OF_FALTA_DOCS_CLIENTE, OF_ID, OF_DATA |
| dbo.ORDEMFABRICO | 20220304-135400 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_P_ID |
| dbo.ORDEMFABRICO | NonClusteredIndex-20161129-104240 | NONCLUSTERED |  |  | OF_P_ID, OF_DATAFIM, OF_ID |
| dbo.ORDEMFABRICO | NonClusteredIndex-20180123-102712 | NONCLUSTERED |  |  | OF_FP_ID, OF_P_ID, OF_TR_ID |
| dbo.ORDEMFABRICO | NonClusteredIndex-20180416-091629 | NONCLUSTERED |  |  | OF_DATA, OF_FP_ID, OF_ID, OF_P_ID, OF_P_ID_CCASCO, OF_P_ID_CDECK, OF_REFERENCIA, OF_E_ID_ENC |
| dbo.ORDEMFABRICO | NonClusteredIndex-20191106-115317 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_DATAFIM |
| dbo.ORDEMFABRICO | NonClusteredIndex-20191107-111947 | NONCLUSTERED |  |  | OF_E_ID_ENC, OF_ID, OF_DATAFIM, OF_P_ID |
| dbo.ORDEMFABRICO | NonClusteredIndex-20191111-163307 | NONCLUSTERED |  |  | OF_ID, OF_DATA, OF_NOME, OF_TRANSPORTEDOC, OF_P_ID, OF_ARM_ID, OF_NUMUTIL, OF_PREPREG, OF_ARM_FIXO, OF_FP_ID, OF_MOLDE_ACESSORIO |
| dbo.PAISES | PK_PAISES | CLUSTERED | Y | Y | PAISES_ID |
| dbo.PAISES_SITE | PK_PAISES_SITE | CLUSTERED | Y | Y | ID |
| dbo.PAISES_SITE | _dta_index_PAISES_SITE_7_1842105603__K11 | NONCLUSTERED |  |  | CONTINENT |
| dbo.PEDIDOS | PK_PEDIDOS | CLUSTERED | Y | Y | PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1 | NONCLUSTERED |  |  | PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_11_12 | NONCLUSTERED |  |  | PED_E_ID, PED_OF_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11 | NONCLUSTERED |  |  | PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_9 | NONCLUSTERED |  |  | PED_NOTAS, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_9987 | NONCLUSTERED |  |  | PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12 | NONCLUSTERED |  |  | PED_ID, PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12_1912 | NONCLUSTERED |  |  | PED_ID, PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12_2_5_9 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_ID, PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12_2_5_9_9987 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_ID, PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12_K2_5_9 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_ID, PED_E_ID, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K1_K11_K12_K2_5_9_6241 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_ID, PED_E_ID, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11 | NONCLUSTERED |  |  | PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_1 | NONCLUSTERED |  |  | PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_1_9 | NONCLUSTERED |  |  | PED_ID, PED_NOTAS, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_9987 | NONCLUSTERED |  |  | PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1 | NONCLUSTERED |  |  | PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_9 | NONCLUSTERED |  |  | PED_NOTAS, PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12 | NONCLUSTERED |  |  | PED_E_ID, PED_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12_2_5_9 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_E_ID, PED_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12_2_5_9_4683 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_E_ID, PED_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12_4364 | NONCLUSTERED |  |  | PED_E_ID, PED_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12_K2_5_9 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_E_ID, PED_ID, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K12_K2_5_9_4864 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_E_ID, PED_ID, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K2_5_9_12 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_E_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K1_K2_5_9_12_440 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_E_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K12 | NONCLUSTERED |  |  | PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K12_1_9 | NONCLUSTERED |  |  | PED_ID, PED_NOTAS, PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K12_9987 | NONCLUSTERED |  |  | PED_E_ID, PED_OF_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K11_K12_K1_K2_5_9 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_E_ID, PED_OF_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11 | NONCLUSTERED |  |  | PED_OF_ID, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11_2_5_9 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11_2_5_9_4364 | NONCLUSTERED |  |  | PED_DATA, PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11_8258 | NONCLUSTERED |  |  | PED_OF_ID, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11_K2_5_9 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_ID, PED_E_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K1_K11_K2_5_9_3928 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_ID, PED_E_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11 | NONCLUSTERED |  |  | PED_OF_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_1 | NONCLUSTERED |  |  | PED_ID, PED_OF_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_1_9 | NONCLUSTERED |  |  | PED_ID, PED_NOTAS, PED_OF_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_6497 | NONCLUSTERED |  |  | PED_OF_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_K1 | NONCLUSTERED |  |  | PED_OF_ID, PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_K1_9987 | NONCLUSTERED |  |  | PED_OF_ID, PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_K1_K2_5_9 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_E_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K12_K11_K1_K2_5_9_8809 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_E_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2_5_9_12 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2_5_9_12_4149 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2_K1_K11_5_9_12 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2_K1_K11_5_9_12_1410 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2D_K1_K11_5_9_12 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2D_K1_K11_5_9_12_5201 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2D_K11_K1_5_9_12 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K2D_K11_K1_5_9_12_4606 | NONCLUSTERED |  |  | PED_DATA_APROVADO, PED_NOTAS, PED_OF_ID, PED_DATA, PED_E_ID, PED_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K6 | NONCLUSTERED |  |  | PED_APROVADO |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K6_9987 | NONCLUSTERED |  |  | PED_APROVADO |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K6_K1_K11 | NONCLUSTERED |  |  | PED_APROVADO, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_index_PEDIDOS_7_1847013661__K6_K12 | NONCLUSTERED |  |  | PED_APROVADO, PED_OF_ID |
| dbo.PEDIDOS | _dta_stat_1847013661_11_12_1_2 | NONCLUSTERED |  |  | PED_E_ID, PED_OF_ID, PED_ID, PED_DATA |
| dbo.PEDIDOS | _dta_stat_1847013661_12_1 | NONCLUSTERED |  |  | PED_OF_ID, PED_ID |
| dbo.PEDIDOS | _dta_stat_1847013661_2_1_11 | NONCLUSTERED |  |  | PED_DATA, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_stat_1847013661_2_11 | NONCLUSTERED |  |  | PED_DATA, PED_E_ID |
| dbo.PEDIDOS | _dta_stat_1847013661_6_1_11 | NONCLUSTERED |  |  | PED_APROVADO, PED_ID, PED_E_ID |
| dbo.PEDIDOS | _dta_stat_1847013661_6_12 | NONCLUSTERED |  |  | PED_APROVADO, PED_OF_ID |
| dbo.PEDIDOS | NonClusteredIndex-20200218-102033 | NONCLUSTERED |  |  | PED_OF_ID |
| dbo.personal_access_tokens | PK__personal__3213E83F2037045B | CLUSTERED | Y | Y | id |
| dbo.personal_access_tokens | personal_access_tokens_token_unique | NONCLUSTERED |  | Y | token |
| dbo.personal_access_tokens | personal_access_tokens_tokenable_type_tokenable_id_index | NONCLUSTERED |  |  | tokenable_type, tokenable_id |
| dbo.PLANEAMENTO_DIARIO | PK_PLANEAMENTO_DIARIO | CLUSTERED | Y | Y | PlaneamentoDiarioId |
| dbo.PLANO | PK_PLANO | CLUSTERED | Y | Y | PL_ID |
| dbo.PLANO | _dta_index_PLANO_7_747149707__K12 | NONCLUSTERED |  |  | PL_COMPLETO |
| dbo.PONTOS | PK_PONTOS | CLUSTERED | Y | Y | PONTOS_ID |
| dbo.PORTAO | PK_PORTAO | CLUSTERED | Y | Y | PORTAO_ID |
| dbo.PORTAO | _dta_index_PORTAO_7_695009557__K1 | NONCLUSTERED |  |  | PORTAO_ID |
| dbo.PROB_CAUSA_SOL | PK_PROBLEMA | CLUSTERED | Y | Y | PCS_ID |
| dbo.PROB_CAUSA_SOL_TIPO | PK_PROB_CAUSA_SOL_TIPO | CLUSTERED | Y | Y | TPPCS_ID |
| dbo.PROBS | PK_PROBS | CLUSTERED | Y | Y | PROBS_ID |
| dbo.PROBS_CLASSIFICACAO | PK_PROBS_CLASSIFICACAO | CLUSTERED | Y | Y | CL_ID |
| dbo.PROBS_LOCAL | PK_PROBS_LOCAL | CLUSTERED | Y | Y | PROBSL_ID |
| dbo.PROC_AREA | PK_PROC_AREA | CLUSTERED | Y | Y | PROC_ID |
| dbo.PROC_AREA_ENT | PK_PROC_AREA_ENT_1 | CLUSTERED | Y | Y | PROCAE_ID |
| dbo.PROC_AREA_FONTE | PK_PROC_AREA_FONTE | CLUSTERED | Y | Y | PROCAF_ID |
| dbo.PROC_ARQUIVO | PK_PROC_ARQUIVO | CLUSTERED | Y | Y | PROCARQ_ID |
| dbo.PROC_CLASSIFIC | PK_PROC_CLASSIFIC | CLUSTERED | Y | Y | CLSP_ID |
| dbo.PROC_FONTE | PK_PROC_FONTE | CLUSTERED | Y | Y | PROCFT_ID |
| dbo.PROC_TIPO | PK_PROC_TIPO | CLUSTERED | Y | Y | TPPROC_ID |
| dbo.PROC_TIPO_ENT | PK_PROC_TIPO_ENT | CLUSTERED | Y | Y | PROCTPE_ID |
| dbo.PRODUTO | PK_PRODUTO | CLUSTERED | Y | Y | P_ID |
| dbo.PRODUTO | NonClusteredIndex-20170208-092736 | NONCLUSTERED |  |  | P_NOME, P_TP_ID, P_ID, P_ACTIVO, P_PCONT_ID, P_E_ID, P_TEM_STOCK, P_DESCONTINUADO, P_PL_ID, P_TP_ID_DISCIPLINA |
| dbo.PRODUTO | NonClusteredIndex-20191106-120240 | NONCLUSTERED |  |  | P_ID, P_TP_ID_DISCIPLINA |
| dbo.PRODUTO_ATTACH | PK_PRODUTO_ATTACH | CLUSTERED | Y | Y | AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_5 | NONCLUSTERED |  |  | AT_IMAGE, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_5_1912 | NONCLUSTERED |  |  | AT_IMAGE, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_K4 | NONCLUSTERED |  |  | AT_ID, AT_P_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_K4_5 | NONCLUSTERED |  |  | AT_IMAGE, AT_ID, AT_P_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_K4_5_4149 | NONCLUSTERED |  |  | AT_IMAGE, AT_ID, AT_P_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K1_K4_9987 | NONCLUSTERED |  |  | AT_ID, AT_P_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K4_K1 | NONCLUSTERED |  |  | AT_P_ID, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K4_K1_4364 | NONCLUSTERED |  |  | AT_P_ID, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K4_K1_5 | NONCLUSTERED |  |  | AT_IMAGE, AT_P_ID, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K4_K1_5_8066 | NONCLUSTERED |  |  | AT_IMAGE, AT_P_ID, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K4_K6_1_2_3 | NONCLUSTERED |  |  | AT_ID, AT_NOME, AT_DESCRICAO, AT_P_ID, AT_ATT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K6 | NONCLUSTERED |  |  | AT_ATT_ID |
| dbo.PRODUTO_ATTACH | _dta_index_PRODUTO_ATTACH_7_1227151417__K6_K4 | NONCLUSTERED |  |  | AT_ATT_ID, AT_P_ID |
| dbo.PRODUTO_ATTACH | _dta_stat_1227151417_4_1 | NONCLUSTERED |  |  | AT_P_ID, AT_ID |
| dbo.PRODUTO_ATTACH | _dta_stat_1227151417_4_6 | NONCLUSTERED |  |  | AT_P_ID, AT_ATT_ID |
| dbo.PRODUTO_ATTACH_TIPO | PK_PRODUTO_ATTACH_TIPO | CLUSTERED | Y | Y | ATT_ID |
| dbo.PRODUTO_CAMADA | PK_PRODUTO_CAMADA | CLUSTERED | Y | Y | CAM_ID |
| dbo.PRODUTO_CAMADA | _dta_index_PRODUTO_CAMADA_7_1291151645__K2 | NONCLUSTERED |  |  | CAM_P_ID |
| dbo.PRODUTO_CAMADA_TIPO | PK_PRODUTO_TIPO_CAMADA | CLUSTERED | Y | Y | TPCAM_ID |
| dbo.PRODUTO_COEFICIENTE | PK_PRODUTO_COEFICIENTE | CLUSTERED | Y | Y | PCOEF_ID |
| dbo.PRODUTO_COMPONENTE | PK_PRODUTO_COMPONENTE | CLUSTERED | Y | Y | COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1 | NONCLUSTERED |  |  | COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_2679 | NONCLUSTERED |  |  | COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3_14 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3_14_3426 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3_2894 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3_4 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_3_4_9987 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12 | NONCLUSTERED |  |  | COMP_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12_2_3_13_14 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12_2_3_13_14_9085 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12_K15_2_3_13_14 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12_K15_2_3_13_14_1771 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K12_K2_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_FP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13 | NONCLUSTERED |  |  | COMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13_K14_K5_K15_K3_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13_K3_K14_K15_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K13_K3_K14_K5_K15_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K14_K13_K3_K2_K15_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_100 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3_4364 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3_K14 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3_K14_3982 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3_K14_K13_K12_K2 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K15_K3_K14_K13_K12_K2_8917 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_8066 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K12_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_FP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K13_K14_K15_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K13_K5_K3_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K13_K5_K3_11_4364 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K13_K5_K3_K14_K15_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K13_K5_K3_K14_K15_11_1912 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_4_1040 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_4_5_8_12_13 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_4_5_8_12_13_4149 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_9085 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K3_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K5_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K5_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K5_K3_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K2_K5_K3_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_2894 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_4_4364 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_4_5_8_12_13 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_4_5_8_12_13_9987 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K12_K2 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K13_2_4_5_12 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FP_ID, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K13_K2_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K13_K2_K5_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K13_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_4_4149 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_4_5_8_12_13 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_4_5_8_12_13_8066 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_8066 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_K5 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_K5_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K2_K5_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_2_4 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_2_4_6980 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_K13_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K1_K3_K5_K2_4_9987 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12 | NONCLUSTERED |  |  | COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_2_3_13_14 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_2_3_13_14_4288 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_32 | NONCLUSTERED |  |  | COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K1 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K1_K2_K3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K1_K3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_7271 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K1_K3_K13_K2_K14 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K1_K3_K13_K2_K14_508 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K13 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K13_3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K13_K3_K2_K14_K1 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_P_P_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K13_K3_K2_K14_K1_9987 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_P_P_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K2_K3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K2_K3_2484 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K2_K3_K13_K14_K1 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K2_K3_K13_K14_K1_8526 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K13_K2_K14 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K13_K2_K14_9850 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K13_K2_K14_K1 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K13_K2_K14_K1_9762 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K14 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K14_5734 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K14_K13_K2_K1 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K15_K3_K14_K13_K2_K1_6355 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K12_K2_K1_K3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13 | NONCLUSTERED |  |  | COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_5201 | NONCLUSTERED |  |  | COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1_9987 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1_K14_K5_K15_K3_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1_K3 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K1_K3_K2_K14_K15_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K12_K15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K12_K15_4179 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K12_K15_K3_K2_K14_K1 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K12_K15_K3_K2_K14_K1_1783 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K1_K5_K15_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K1_K5_K15_K2_4_11_4149 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15_1040 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15_4_11_1410 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K14_K3_K5_K15_K2_K1_4_11_4864 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_2894 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14_4364 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14_K2_K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14_K3 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14_K3_4149 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K14_K3_K5_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K3 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K15_K3_K14_K5_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K2_K5_1_3_4 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K1_2_4_5_12 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K1_K5_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K1_K5_11_8066 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K1_K5_K14_K15_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K1_K5_K14_K15_11_8066 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K3_K2_K5_K1_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_1_3_4 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K1 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K1_K14_K15_K3_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ID, COMP_L_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K1_K2_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K14 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K13_K5_K15_K14_K3_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14 | NONCLUSTERED |  |  | COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K13_K15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K13_K15_8066 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K13_K15_K5_K3_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K13_K5 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K15_K3_K13 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K13 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K13_K15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K13_K15_9987 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K13_K15_K2_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K13_K15_K5_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K15_1410 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K15_K13 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K15_K13_9910 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K5_K13_K15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K3_K5_K13_K15_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K5 | NONCLUSTERED |  |  | COMP_L_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K14_K5_K13 | NONCLUSTERED |  |  | COMP_L_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15 | NONCLUSTERED |  |  | COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_3_13_14 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_3_13_14_9953 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_8341 | NONCLUSTERED |  |  | COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K1_K3_K14 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ID, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K1_K3_K14_5420 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ID, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13_2166 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13_K14_K3 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13_K14_K3_3369 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13_K14_K5_K3_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K13_K14_K5_K3_K2_K1_4_11_1771 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14_6478 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14_K3 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14_K3_4683 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14_K3_K13 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K14_K3_K13_1912 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K2_K1_K13_K14_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_ELIMINADO, COMP_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3_4288 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3_K13_K12_K2_K14_K1 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3_K13_K12_K2_K14_K1_3910 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3_K14_K13 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K15_K3_K14_K13_1771 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_1 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_1_3_4 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_1_3_4_1410 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_1_9987 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_3_4 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_4364 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K12_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID, COMP_FP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K13_K14_K15_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K13_K14_K5_K15_K3_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K13_K14_K5_K15_K3_4_11_6497 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_4_5_8_12_13 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_4_5_8_12_13_4364 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_4_5201 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_9850 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K3_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K5_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K5_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K5_K3_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K1_K5_K3_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K12_K1 | NONCLUSTERED |  |  | COMP_P_ID, COMP_FP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K12_K1_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_FP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K13_K15_K1_K14_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_6497 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K1 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K1_4_4364 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K12_K15 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K12_K15_K13_K14_K1 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K13_K14_K12_K15 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K13_K14_K12_K15_K1 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K4 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K4_K5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K5_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K5_K1_4_9987 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K3_K5_K4 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K4_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K4_K5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K4_K5_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K1_K3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K1_K3_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K1_K3_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K3_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K3_K4 | NONCLUSTERED |  |  | COMP_P_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K2_K5_K4 | NONCLUSTERED |  |  | COMP_P_ID, COMP_TPCOMP_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3 | NONCLUSTERED |  |  | COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_13_14 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_2 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_4288 | NONCLUSTERED |  |  | COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_2533 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_4_4864 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K12_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K13_K14_K5_K15_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K13_K2_K5_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K15_K13_K12_K2_K14 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2_4_5_8_12_13 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2_4_5_8_12_13_5201 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_FASE_FINAL, COMP_FP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2_4_8066 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K2_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K5_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K1_K5_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K15_K14_K5_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K1_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K1_K15_K12 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K12_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K12_K15_2649 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K12_K15_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K14_K12_K15_K1_6969 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K13_K2_K5_K1_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K1_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K1_K15_4828 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K1_K15_K13_K12_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K1_K15_K13_K12_K2_2533 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K12_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K12_K15_3928 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K12_K15_K13_K2_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K12_K15_K13_K2_K1_2555 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K13_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K13_K1_K2_K15_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_ID, COMP_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K13_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K13_K15_K5_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15_8258 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15_K1_1227 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K15_K13_6221 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K5_K1_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K5_K1_K13_K15_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K5_K13_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K14_K5_K13_K15_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K15_K14_K13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ELIMINADO, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_8341 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K13_K5_K1_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K4 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K5_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K2_K5_K4 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_P_ID, COMP_TPCOMP_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K1_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K1_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K1_K2_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K1_K2_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K13_K2_K1_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K2 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K2_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K3_K5_K2_K1_4_6355 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K4_2_3 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K4_K2_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K4_K2_K5_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K4_K5_K2 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K4_K5_K2_3 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5 | NONCLUSTERED |  |  | COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_1_3_11_13 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_1_3_4 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_1_3_4_13 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_13_14 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_3_4_11_13_14 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K13 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K13_K2_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K13_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K13_K3_K14_K15_K2_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K13_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K2 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K2_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K2_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K1_K3_K2_K13_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K14 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15_K14 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15_K14_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15_K14_K3_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K15_K3_K14_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K3_K1_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K3_K1_11_1912 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K3_K1_K14_K15_11 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K13_K3_K1_K14_K15_11_4364 | NONCLUSTERED |  |  | COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K14 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K14_K13 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3_4_11_9850 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3_9987 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3_K2_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K13_K14_K3_K2_K1_4_11_1040 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K2_K13_K14_K3_K1_4_11 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K15_K2_K13_K14_K3_K1_4_11_9085 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_1_3_4 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_1_3_4_11_13_14 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_1_3_4_13 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_K15_1_3_4_11_13_14 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_VALOR_EXTRA, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_K3_K4 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_P_ID, COMP_P_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K2_K4 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_P_ID, COMP_QUANTIDADE |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K3_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K3_K13_K2_K1_4_12 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_FP_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K5_K3_K2_K1_4 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_index_PRODUTO_COMPONENTE_7_2053582354__K8 | NONCLUSTERED |  |  | COMP_FASE_FINAL |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_12_15 | NONCLUSTERED |  |  | COMP_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_15_3_14_13_12_2 | NONCLUSTERED |  |  | COMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID, COMP_FP_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_2_13_5_3_14 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID, COMP_P_P_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_2_5 | NONCLUSTERED |  |  | COMP_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_3_12 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_1_3_2 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_12_15_1_3_13_2 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_12_15_2_3_13_14 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_12_15_3_14_13 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_L_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_12_2_1_3 | NONCLUSTERED |  |  | COMP_FP_ID, COMP_P_ID, COMP_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_1_14_5_15_3_2 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_1_3_2 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ID, COMP_P_P_ID, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_12_15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_14_3_5_15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_15 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_15_14_2_1 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_ELIMINADO, COMP_L_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_13_2_5 | NONCLUSTERED |  |  | COMP_ATRIB_ID, COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_13_15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_13_5 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ATRIB_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_3_13_15 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_3_13_15_2 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_14_3_5 | NONCLUSTERED |  |  | COMP_L_ID, COMP_P_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_15_2_1_13 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_ID, COMP_ID, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_15_3_13_12 | NONCLUSTERED |  |  | COMP_ELIMINADO, COMP_P_P_ID, COMP_ATRIB_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_1_13_14_5_15 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_13_15 | NONCLUSTERED |  |  | COMP_P_ID, COMP_ATRIB_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_3_12 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_3_4_5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_4_5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_2_5 | NONCLUSTERED |  |  | COMP_P_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_1_13_14_5 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_1_15_13 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_1_5 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ID, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_13_2_14_1_15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_13_2_14_12 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_ATRIB_ID, COMP_P_ID, COMP_L_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_14_1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_14_12 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_FP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_14_15 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_14_5_1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_L_ID, COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_3_5_2_1 | NONCLUSTERED |  |  | COMP_P_P_ID, COMP_TPCOMP_ID, COMP_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_4_5 | NONCLUSTERED |  |  | COMP_QUANTIDADE, COMP_TPCOMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_1 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_13_15_3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_ELIMINADO, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_13_3_1 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ATRIB_ID, COMP_P_P_ID, COMP_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_14 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_15_13_14 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_ATRIB_ID, COMP_L_ID |
| dbo.PRODUTO_COMPONENTE | _dta_stat_2053582354_5_15_2_13_14_3 | NONCLUSTERED |  |  | COMP_TPCOMP_ID, COMP_ELIMINADO, COMP_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_P_P_ID |
| dbo.PRODUTO_COMPONENTE | NonClusteredIndex-20180126-114231 | NONCLUSTERED |  |  | COMP_P_ID |
| dbo.PRODUTO_COMPONENTE | NonClusteredIndex-20241127-0945110 | NONCLUSTERED |  |  | COMP_P_ID, COMP_P_P_ID, COMP_ATRIB_ID, COMP_L_ID, COMP_FP_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | NonClusteredIndex-20241127-094931 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_COMPONENTE | NonClusteredIndex-20241127-095015 | NONCLUSTERED |  |  | COMP_ID, COMP_P_P_ID, COMP_L_ID, COMP_ELIMINADO |
| dbo.PRODUTO_CONTABILIDADE_TIPO | PK_PRODUTO_CONTABILIDADE_TIPO | CLUSTERED | Y | Y | PCONT_ID |
| dbo.PRODUTO_ENTIDADE | PK_PRODUTO_ENTIDADE | CLUSTERED | Y | Y | PF_P_ID, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1 | NONCLUSTERED |  |  | PF_P_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1_K2_3_4_5_6 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_P_ID, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1_K2_3_4_5_6_4364 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_P_ID, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1_K2_3_4_5_6_7_8_9 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_DESCRICAO, PF_UNI_ID, PF_CONVERSAO, PF_P_ID, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1_K2_6 | NONCLUSTERED |  |  | PF_CODIGO, PF_P_ID, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K1_K8_K2_K9_6_7 | NONCLUSTERED |  |  | PF_CODIGO, PF_DESCRICAO, PF_P_ID, PF_UNI_ID, PF_E_ID, PF_CONVERSAO |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_1_3_4_5_6_7_8_9 | NONCLUSTERED |  |  | PF_P_ID, PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_DESCRICAO, PF_UNI_ID, PF_CONVERSAO, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_1_6 | NONCLUSTERED |  |  | PF_P_ID, PF_CODIGO, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K1_3_4_5_6 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_E_ID, PF_P_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K1_3_4_5_6_7_8_9 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_DESCRICAO, PF_UNI_ID, PF_CONVERSAO, PF_E_ID, PF_P_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K1_3_4_5_6_9987 | NONCLUSTERED |  |  | PF_QTD_MIN_ENC, PF_PRECO, PF_OBSERVACOES, PF_CODIGO, PF_E_ID, PF_P_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K1_6 | NONCLUSTERED |  |  | PF_CODIGO, PF_E_ID, PF_P_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K1_K8_K9_6_7 | NONCLUSTERED |  |  | PF_CODIGO, PF_DESCRICAO, PF_E_ID, PF_P_ID, PF_UNI_ID, PF_CONVERSAO |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K2_K8_K1_K9_6 | NONCLUSTERED |  |  | PF_CODIGO, PF_E_ID, PF_UNI_ID, PF_P_ID, PF_CONVERSAO |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K9_K2_1_6_7_8 | NONCLUSTERED |  |  | PF_P_ID, PF_CODIGO, PF_DESCRICAO, PF_UNI_ID, PF_CONVERSAO, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_index_PRODUTO_ENTIDADE_7_1461580245__K9_K2_1_6_8 | NONCLUSTERED |  |  | PF_P_ID, PF_CODIGO, PF_UNI_ID, PF_CONVERSAO, PF_E_ID |
| dbo.PRODUTO_ENTIDADE | _dta_stat_1461580245_1_8 | NONCLUSTERED |  |  | PF_P_ID, PF_UNI_ID |
| dbo.PRODUTO_ENTIDADE | _dta_stat_1461580245_2_1_8_9 | NONCLUSTERED |  |  | PF_E_ID, PF_P_ID, PF_UNI_ID, PF_CONVERSAO |
| dbo.PRODUTO_ENTIDADE | _dta_stat_1461580245_9_2 | NONCLUSTERED |  |  | PF_CONVERSAO, PF_E_ID |
| dbo.PRODUTO_ESTADO | PK_PRODUTO_ESTADO | CLUSTERED | Y | Y | EST_ID |
| dbo.PRODUTO_FASE | PK_PRODUTO_FASE | CLUSTERED | Y | Y | PRODF_ID |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K18 | NONCLUSTERED |  |  | PRODF_PLANEAMENTO |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K2_K3_K12_K11_6 | NONCLUSTERED |  |  | PRODF_TEMPO, PRODF_P_ID, PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K2_K3_K12_K11_K6 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID, PRODF_TEMPO |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K2_K3_K5 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_FP_ID, PRODF_SEQUENCIA |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K3_K11_2_6 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_TEMPO, PRODF_FP_ID, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K3_K11_K12_2_6 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_TEMPO, PRODF_FP_ID, PRODF_PRODF_ID, PRODF_DATA_ELIMINADO |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K3_K12_K11_K2_6 | NONCLUSTERED |  |  | PRODF_TEMPO, PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID, PRODF_P_ID |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K3_K12_K11_K2_K6 | NONCLUSTERED |  |  | PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID, PRODF_P_ID, PRODF_TEMPO |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K6_K3_K11_2 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_TEMPO, PRODF_FP_ID, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_index_PRODUTO_FASE_7_1989582126__K6_K3_K11_K12_2 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_TEMPO, PRODF_FP_ID, PRODF_PRODF_ID, PRODF_DATA_ELIMINADO |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_2_3_12_11 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_2_3_5 | NONCLUSTERED |  |  | PRODF_P_ID, PRODF_FP_ID, PRODF_SEQUENCIA |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_3_11 | NONCLUSTERED |  |  | PRODF_FP_ID, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_3_12_11 | NONCLUSTERED |  |  | PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_3_12_11_2_6 | NONCLUSTERED |  |  | PRODF_FP_ID, PRODF_DATA_ELIMINADO, PRODF_PRODF_ID, PRODF_P_ID, PRODF_TEMPO |
| dbo.PRODUTO_FASE | _dta_stat_1989582126_6_3_11_12 | NONCLUSTERED |  |  | PRODF_TEMPO, PRODF_FP_ID, PRODF_PRODF_ID, PRODF_DATA_ELIMINADO |
| dbo.PRODUTO_FASE_LINK | PK_PRODUTO_FASE_LINK | CLUSTERED | Y | Y | PRODFL_PRODF_ID_PROX, PRODFL_PRODF_ID_ANT |
| dbo.PRODUTO_LISTA | PK_PRODUTO_LISTA | CLUSTERED | Y | Y | PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | PK_PRODUTO_LISTA_ITEMS | CLUSTERED | Y | Y | PLI_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3 | NONCLUSTERED |  |  | PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_2_4_5_6_7_8 | NONCLUSTERED |  |  | PLI_DESCR, PLI_SEQUENCIA, PLI_FP_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_MOLDE_REPARAR, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_2_6 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_8066 | NONCLUSTERED |  |  | PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K5_K6_2_7 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_PL_ID, PLI_FP_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K5_K6_2_7_1912 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_PL_ID, PLI_FP_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K6 | NONCLUSTERED |  |  | PLI_PL_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K6_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K6_2_4_5_7_8 | NONCLUSTERED |  |  | PLI_DESCR, PLI_SEQUENCIA, PLI_FP_ID, PLI_CULPA_CHEFE, PLI_MOLDE_REPARAR, PLI_PL_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K7 | NONCLUSTERED |  |  | PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K7_4120 | NONCLUSTERED |  |  | PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K7_K6_K5_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K3_K7_K6_K5_2_504 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5 | NONCLUSTERED |  |  | PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_4364 | NONCLUSTERED |  |  | PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K3_K6_2_7 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_PL_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K3_K6_2_7_8066 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_PL_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K6_K3_2_7 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K6_K7_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7 | NONCLUSTERED |  |  | PLI_FP_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7_2_3_6 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_FP_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7_2_3_6_7271 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_FP_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7_5543 | NONCLUSTERED |  |  | PLI_FP_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7_K6_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K5_K7_K6_K3_2_5492 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6 | NONCLUSTERED |  |  | PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_9987 | NONCLUSTERED |  |  | PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3 | NONCLUSTERED |  |  | PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_2_4_5_7_8 | NONCLUSTERED |  |  | PLI_DESCR, PLI_SEQUENCIA, PLI_FP_ID, PLI_CULPA_CHEFE, PLI_MOLDE_REPARAR, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_K7_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_K7_2_1240 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_K7_K5_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID, PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K3_K7_K5_2_506 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_PL_ID, PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K5_K3_2_7 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K5_K3_2_7_4149 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K5_K3_K7_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K5_K3_K7_2_4327 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K7 | NONCLUSTERED |  |  | PLI_FP_ID_CHK, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K7_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K7_K3_K5_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_PL_ID, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K7_K5_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K6_K7_K5_K3_2_8525 | NONCLUSTERED |  |  | PLI_DESCR, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_2_3_6 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_2_3_6_2894 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_6478 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K3 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K3_4864 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K3_K6_K5_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_PL_ID, PLI_FP_ID_CHK, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K3_K6_K5_2_440 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_PL_ID, PLI_FP_ID_CHK, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5_2_3_6 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5_2_3_6_2733 | NONCLUSTERED |  |  | PLI_DESCR, PLI_PL_ID, PLI_FP_ID_CHK, PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5_2386 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5_K6_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K5_K6_K3_2_1912 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_4504 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K3_2_786 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K3_K5_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K3_K5_2_114 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K5_K3_2 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K7_K6_K5_K3_2_8040 | NONCLUSTERED |  |  | PLI_DESCR, PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_index_PRODUTO_LISTA_ITEMS_7_1483152329__K8 | NONCLUSTERED |  |  | PLI_MOLDE_REPARAR |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_3_5 | NONCLUSTERED |  |  | PLI_PL_ID, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_3_7 | NONCLUSTERED |  |  | PLI_PL_ID, PLI_CULPA_CHEFE |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_6_3 | NONCLUSTERED |  |  | PLI_FP_ID_CHK, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_6_5_3 | NONCLUSTERED |  |  | PLI_FP_ID_CHK, PLI_FP_ID, PLI_PL_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_7_5 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_7_5_6 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID, PLI_FP_ID_CHK |
| dbo.PRODUTO_LISTA_ITEMS | _dta_stat_1483152329_7_6_3_5 | NONCLUSTERED |  |  | PLI_CULPA_CHEFE, PLI_FP_ID_CHK, PLI_PL_ID, PLI_FP_ID |
| dbo.PRODUTO_MODELO | PK_PRODUTO_MODELO | CLUSTERED | Y | Y | M_ID |
| dbo.PRODUTO_NUMERO_POCOS | PK_PRODUTO_NUMERO_POCOS | CLUSTERED | Y | Y | NP_ID |
| dbo.PRODUTO_OPCOES | PK_PRODUTO_OPCOES | CLUSTERED | Y | Y | POP_P_ID, POP_P_P_ID |
| dbo.PRODUTO_OPCOES | _dta_index_PRODUTO_OPCOES_7_1515152443__K11 | NONCLUSTERED |  |  | POP_CUSTO_EXTRA_OF |
| dbo.PRODUTO_PROB_CAUSA_SOL | PK_PRODUTO_PROB_CAUSA_SOL_1 | CLUSTERED | Y | Y | PP_ID |
| dbo.PRODUTO_TAMANHO | PK_PRODUTO_TAMANHO | CLUSTERED | Y | Y | TAM_ID |
| dbo.PRODUTO_TIPO | PK_PRODUTO_TIPO | CLUSTERED | Y | Y | TP_ID |
| dbo.ProdutoTipoAcessorio | PK_ProdutoTipoAcessorio | CLUSTERED | Y | Y | codTipo, codProduto |
| dbo.Prova | PK__Prova__7D311783E42A0B91 | CLUSTERED | Y | Y | IDProva |
| dbo.PROVAS | PK_PROVAS | CLUSTERED | Y | Y | PRV_ID |
| dbo.PROVAS_BOOKING | PK_PROVAS_BOOKING | CLUSTERED | Y | Y | PRVB_ID |
| dbo.PROVAS_BOOKING_ESTADO | PK_PROVAS_ESTADO | CLUSTERED | Y | Y | PBEST_ID |
| dbo.PROVAS_FICHEIROS | PK_PROVAS_FICHEIROS | CLUSTERED | Y | Y | PRVFX_ID |
| dbo.PROVAS_OF | PK_PROVAS_OF | CLUSTERED | Y | Y | PRVOF_PRV_ID, PRVOF_OF_ID |
| dbo.PublicidadeAgentes | PK_PublicidadeAgentes | CLUSTERED | Y | Y | codPub |
| dbo.REP_OF_FP | PK_REP_OF_FP | CLUSTERED | Y | Y | ROFFP_ID |
| dbo.REPARACOES_PROVAS | PK_REPARACOES_PROVAS | CLUSTERED | Y | Y | REP_ID |
| dbo.Report_Table_20171114 | _dta_index_Report_Table_20171114_7_1643152899__K3 | NONCLUSTERED |  |  | Temperatura  |
| dbo.rfid_cache | PK__rfid_cac__3213E83F81E9577F | CLUSTERED | Y | Y | id |
| dbo.RH_DOC | PK_RH_DOC | CLUSTERED | Y | Y | RHD_ID |
| dbo.RH_FORMACAO | PK_RH_FORMACAO | CLUSTERED | Y | Y | RHF_ID |
| dbo.RH_PROBLEMA | PK_RH_PROBLEMA | CLUSTERED | Y | Y | RHP_ID |
| dbo.RH_TIPO_DOC | PK_RH_TIPO_DOC | CLUSTERED | Y | Y | RHTD_ID |
| dbo.SensoresLogin | PK_SensoresLogin | CLUSTERED | Y | Y | codLogin |
| dbo.SensoresLoginSessao | PK_SensoresLoginSessao | CLUSTERED | Y | Y | codLogin, codTeste |
| dbo.SensoresPosicao | PK_SensoresPosicao | CLUSTERED | Y | Y | codPosicao |
| dbo.SensoresTeste | PK_SensoresTeste | CLUSTERED | Y | Y | codTeste |
| dbo.SensoresTesteAtleta | PK_SensoresTesteAtleta | CLUSTERED | Y | Y | codTeste, codAtleta |
| dbo.SensoresTesteSerie | PK_SensoresTesteSerie | CLUSTERED | Y | Y | codTeste, codSerie |
| dbo.SensoresTesteSerie | _dta_index_SensoresTesteSerie_7_1947153982__K26 | NONCLUSTERED |  |  | tipo_input |
| dbo.SensoresTesteSeriePosicoes | PK_SensoresTesteSeriePosicoes | CLUSTERED | Y | Y | codTeste, codAtleta, codSerie |
| dbo.SensoresTesteSerieValores | PK_SensoresTesteSerieValores | CLUSTERED | Y | Y | codTeste, codSerie, tempo |
| dbo.SensoresTesteSerieValores | _dta_index_SensoresTesteSerieValores_7_2011154210__K2 | NONCLUSTERED |  |  | codSerie |
| dbo.SensoresTesteVideo | PK_SensoresTesteVideo | CLUSTERED | Y | Y | CodVideo, CodSessao |
| dbo.SGIDI | PK_SGIDI | CLUSTERED | Y | Y | SGIDI_ID |
| dbo.SGIDI_FICHEIRO | PK_SGIDI_FICHEIRO | CLUSTERED | Y | Y | SGIDIF_ID |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K1_2_4_9_11 | NONCLUSTERED |  |  | SGIDIF_NOME, SGIDIF_TIPO, SGIDIF_SGIDIP_ID, SGIDIF_CAMINHO, SGIDIF_ID |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K1_K7_2_4_9_11 | NONCLUSTERED |  |  | SGIDIF_NOME, SGIDIF_TIPO, SGIDIF_SGIDIP_ID, SGIDIF_CAMINHO, SGIDIF_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K13 | NONCLUSTERED |  |  | SGIDIF_PUBLICO |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K18_K7_K9_1_2_3_4_5_10_11_13 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_NOME, SGIDIF_DESCR, SGIDIF_TIPO, SGIDIF_DATA, SGIDIF_SGIDIF_ID, SGIDIF_CAMINHO, SGIDIF_PUBLICO, SGIDIF_E_ID, SGIDIF_DATA_ELIMINADO, SGIDIF_SGIDIP_ID |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K7_K9_1_2_4_11 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_NOME, SGIDIF_TIPO, SGIDIF_CAMINHO, SGIDIF_DATA_ELIMINADO, SGIDIF_SGIDIP_ID |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K9_K18_K7_1_2_3_4_5_10_11_13 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_NOME, SGIDIF_DESCR, SGIDIF_TIPO, SGIDIF_DATA, SGIDIF_SGIDIF_ID, SGIDIF_CAMINHO, SGIDIF_PUBLICO, SGIDIF_SGIDIP_ID, SGIDIF_E_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K9_K7_1_2_3_4_5_10_11_13_18 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_NOME, SGIDIF_DESCR, SGIDIF_TIPO, SGIDIF_DATA, SGIDIF_SGIDIF_ID, SGIDIF_CAMINHO, SGIDIF_PUBLICO, SGIDIF_E_ID, SGIDIF_SGIDIP_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FICHEIRO | _dta_index_SGIDI_FICHEIRO_7_1986106116__K9_K7_1_2_4_11 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_NOME, SGIDIF_TIPO, SGIDIF_CAMINHO, SGIDIF_SGIDIP_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FICHEIRO | _dta_stat_1986106116_1_7 | NONCLUSTERED |  |  | SGIDIF_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FICHEIRO | _dta_stat_1986106116_18_7_9 | NONCLUSTERED |  |  | SGIDIF_E_ID, SGIDIF_DATA_ELIMINADO, SGIDIF_SGIDIP_ID |
| dbo.SGIDI_FICHEIRO | _dta_stat_1986106116_9_18 | NONCLUSTERED |  |  | SGIDIF_SGIDIP_ID, SGIDIF_E_ID |
| dbo.SGIDI_FICHEIRO | _dta_stat_1986106116_9_7 | NONCLUSTERED |  |  | SGIDIF_SGIDIP_ID, SGIDIF_DATA_ELIMINADO |
| dbo.SGIDI_FX_CLASSIFIC | PK_SGIDI_FX_CLASSIFIC | CLUSTERED | Y | Y | SGIDIFXCL_ID |
| dbo.SGIDI_PASTA | PK_SGIDI_PASTA | CLUSTERED | Y | Y | SGIDIP_ID |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K1_K11_K6_K8_2 | NONCLUSTERED |  |  | SGIDIP_NOME, SGIDIP_ID, SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO, SGIDIP_SGIDIP_ID |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K11_1_2_8_9 | NONCLUSTERED |  |  | SGIDIP_ID, SGIDIP_NOME, SGIDIP_SGIDIP_ID, SGIDIP_SISTEMA, SGIDIP_TR_ID |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K11_K6_1_2_8_9 | NONCLUSTERED |  |  | SGIDIP_ID, SGIDIP_NOME, SGIDIP_SGIDIP_ID, SGIDIP_SISTEMA, SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K11_K6_K1_K8_2 | NONCLUSTERED |  |  | SGIDIP_NOME, SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO, SGIDIP_ID, SGIDIP_SGIDIP_ID |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K8_K11_1_2 | NONCLUSTERED |  |  | SGIDIP_ID, SGIDIP_NOME, SGIDIP_SGIDIP_ID, SGIDIP_TR_ID |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K8_K11_K6_1_2 | NONCLUSTERED |  |  | SGIDIP_ID, SGIDIP_NOME, SGIDIP_SGIDIP_ID, SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO |
| dbo.SGIDI_PASTA | _dta_index_SGIDI_PASTA_7_1954106002__K9 | NONCLUSTERED |  |  | SGIDIP_SISTEMA |
| dbo.SGIDI_PASTA | _dta_stat_1954106002_1_11 | NONCLUSTERED |  |  | SGIDIP_ID, SGIDIP_TR_ID |
| dbo.SGIDI_PASTA | _dta_stat_1954106002_11_6 | NONCLUSTERED |  |  | SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO |
| dbo.SGIDI_PASTA | _dta_stat_1954106002_11_6_1_8 | NONCLUSTERED |  |  | SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO, SGIDIP_ID, SGIDIP_SGIDIP_ID |
| dbo.SGIDI_PASTA | _dta_stat_1954106002_8_11_6 | NONCLUSTERED |  |  | SGIDIP_SGIDIP_ID, SGIDIP_TR_ID, SGIDIP_DATA_ELIMINADO |
| dbo.SGIDI_TIPO | PK_SGIDI_TIPO | CLUSTERED | Y | Y | SGIDITP_ID |
| dbo.ShopCache | PK_ShopCache | CLUSTERED | Y | Y | codProduto |
| dbo.telescope_entries | PK__telescop__DA24123E31A5492E | CLUSTERED | Y | Y | sequence |
| dbo.telescope_entries | telescope_entries_batch_id_index | NONCLUSTERED |  |  | batch_id |
| dbo.telescope_entries | telescope_entries_created_at_index | NONCLUSTERED |  |  | created_at |
| dbo.telescope_entries | telescope_entries_family_hash_index | NONCLUSTERED |  |  | family_hash |
| dbo.telescope_entries | telescope_entries_type_should_display_on_index_index | NONCLUSTERED |  |  | type, should_display_on_index |
| dbo.telescope_entries | telescope_entries_uuid_unique | NONCLUSTERED |  | Y | uuid |
| dbo.telescope_entries_tags | telescope_entries_tags_entry_uuid_tag_index | NONCLUSTERED |  |  | entry_uuid, tag |
| dbo.telescope_entries_tags | telescope_entries_tags_tag_index | NONCLUSTERED |  |  | tag |
| dbo.testes | PK_testes | CLUSTERED | Y | Y | id |
| dbo.TH | PK_TH_1 | CLUSTERED | Y | Y | TH_ID |
| dbo.TH | IX_TH_DATA | NONCLUSTERED |  |  | TH_DATA |
| dbo.TH | IX_TH_DATA_SONDA | NONCLUSTERED |  | Y | TH_DATA, TH_SONDA |
| dbo.TH | IX_TH_SONDA | NONCLUSTERED |  |  | TH_SONDA |
| dbo.TH_SCHED | PK_TH_SCHED | CLUSTERED | Y | Y | THSCHED_ID |
| dbo.TH_SONDA | PK_TH_SONDA | CLUSTERED | Y | Y | THS_ID |
| dbo.Trackimo_Access | PK_Trackimo_Access | CLUSTERED | Y | Y | codLog |
| dbo.Trackimo_Access | _dta_index_Trackimo_Access_7_119671474__K1 | NONCLUSTERED |  |  | codLog |
| dbo.Trackimo_Device | PK_Trackimo_Device_20171010 | CLUSTERED | Y | Y | device_id |
| dbo.Trackimo_DeviceLocation | PK_Trackimo_DeviceLog | CLUSTERED | Y | Y | codHistorico |
| dbo.Trackimo_DeviceLocation | _dta_index_Trackimo_DeviceLocation_7_183671702__K6 | NONCLUSTERED |  |  | gps |
| dbo.TRANSP_DATAS | PK_TRANSP_DATAS | CLUSTERED | Y | Y | TRDT_ID |
| dbo.TRANSP_DATAS | _dta_index_TRANSP_DATAS_7_215671816__K4 | NONCLUSTERED |  |  | TRDT_DATA_NOVA |
| dbo.TRANSP_DATAS_CLASSIFICACAO | PK_TRANSP_DATAS_CLASSIFICACAO | CLUSTERED | Y | Y | TRDTCL_ID |
| dbo.TRANSP_DESP | PK_TRANSP_DESP | CLUSTERED | Y | Y | TRDESP_ID |
| dbo.TRANSP_DESP | _dta_index_TRANSP_DESP_7_279672044__K2_K3_1_4_5_6_7 | NONCLUSTERED |  |  | TRDESP_ID, TRDESP_OBS, TRDESP_QTD, TRDESP_VALOR, TRDESP_VALOR_ESTIMADO, TRDESP_TRDESPTP_ID, TRDESP_TR_ID |
| dbo.TRANSP_DESP | _dta_index_TRANSP_DESP_7_279672044__K3 | NONCLUSTERED |  |  | TRDESP_TR_ID |
| dbo.TRANSP_DESP | _dta_index_TRANSP_DESP_7_279672044__K3_K2_1_4_5_6_7 | NONCLUSTERED |  |  | TRDESP_ID, TRDESP_OBS, TRDESP_QTD, TRDESP_VALOR, TRDESP_VALOR_ESTIMADO, TRDESP_TR_ID, TRDESP_TRDESPTP_ID |
| dbo.TRANSP_DESP | _dta_stat_279672044_3_2 | NONCLUSTERED |  |  | TRDESP_TR_ID, TRDESP_TRDESPTP_ID |
| dbo.TRANSP_DESP_TIPO | PK_TRANSP_DESP_TIPO | CLUSTERED | Y | Y | TRDESPTP_ID |
| dbo.TRANSP_DESTINO | PK_TRANSP_DESTINO | CLUSTERED | Y | Y | DEST_ID |
| dbo.TRANSP_DOCS | PK_TRANSP_DOCS_1 | CLUSTERED | Y | Y | TRDOC_DOCS_ID, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_2_7 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCNUM, TRDOC_DOCS_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_2_7_5201 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCNUM, TRDOC_DOCS_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K2_7 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K2_7_6497 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K2_K5_7 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TR_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K2_K5_7_1912 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TR_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_2 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_2_1771 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_2_7 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_2_7_9987 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_K2 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_K2_2533 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_K2_7 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K1_K5_K2_7_4364 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_1_3_4_5_6_7_8 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_DOCS_NOME, TRDOC_DOC_CAMINHO, TRDOC_TRATADO, TRDOC_OBSERVACOES, TRDOC_DOCNUM, TRDOC_DATA, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_1_3_4_5_6_7_8_9987 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_DOCS_NOME, TRDOC_DOC_CAMINHO, TRDOC_TRATADO, TRDOC_OBSERVACOES, TRDOC_DOCNUM, TRDOC_DATA, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_7 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_TR_ID, TRDOC_DOCS_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_7_4149 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_TR_ID, TRDOC_DOCS_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_K5 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_K5_1040 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_K5_7 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K1_K5_7_8066 | NONCLUSTERED |  |  | TRDOC_DOCNUM, TRDOC_TR_ID, TRDOC_DOCS_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K5 | NONCLUSTERED |  |  | TRDOC_TR_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K2_K5_1 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TR_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K5 | NONCLUSTERED |  |  | TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K5_1_2 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TR_ID, TRDOC_TRATADO |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K5_K2 | NONCLUSTERED |  |  | TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_index_TRANSP_DOCS_7_375672386__K5_K2_1 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_stat_375672386_1_5_2 | NONCLUSTERED |  |  | TRDOC_DOCS_ID, TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS | _dta_stat_375672386_5_2 | NONCLUSTERED |  |  | TRDOC_TRATADO, TRDOC_TR_ID |
| dbo.TRANSP_DOCS_DEST_TIPO | PK_TRANSP_DOCS_DEST_TIPO | CLUSTERED | Y | Y | DTD_DEST_ID, DTD_TRTP_ID, DTD_DOCS_ID |
| dbo.TRANSP_DOCS_STD | PK_TRANSP_DOCS | CLUSTERED | Y | Y | DOCS_ID |
| dbo.TRANSP_ENTIDADE | PK_TRANSP_ENTIDADE | CLUSTERED | Y | Y | TRE_ID |
| dbo.TRANSP_ENTIDADE | _dta_index_TRANSP_ENTIDADE_7_471672728__K2_K3_1_4_5_6_7_8_9_10_11_12 | NONCLUSTERED |  |  | TRE_ID, TRE_DATA_IDA, TRE_DATA_VOLTA, TRE_VOO_IDA, TRE_VOO_VOLTA, TRE_IDA_CONF, TRE_VOLTA_CONF, TRE_NOITES, TRE_MARCADO, TRE_PAGO, TRE_E_ID, TRE_TR_ID |
| dbo.TRANSP_ENTIDADE | _dta_index_TRANSP_ENTIDADE_7_471672728__K3_K2_1_4_5_6_7_8_9_10_11_12 | NONCLUSTERED |  |  | TRE_ID, TRE_DATA_IDA, TRE_DATA_VOLTA, TRE_VOO_IDA, TRE_VOO_VOLTA, TRE_IDA_CONF, TRE_VOLTA_CONF, TRE_NOITES, TRE_MARCADO, TRE_PAGO, TRE_TR_ID, TRE_E_ID |
| dbo.TRANSP_ENTIDADE | _dta_index_TRANSP_ENTIDADE_7_471672728__K9 | NONCLUSTERED |  |  | TRE_VOLTA_CONF |
| dbo.TRANSP_ENTIDADE | _dta_stat_471672728_3_2 | NONCLUSTERED |  |  | TRE_TR_ID, TRE_E_ID |
| dbo.TRANSP_OF | PK_TRANSP_OF | CLUSTERED | Y | Y | TROF_TR_ID, TROF_OF_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_2 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_2_3_5 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_ENVIADO, TROF_LEVA_PECAS, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_2_9987 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_K2 | NONCLUSTERED |  |  | TROF_TR_ID, TROF_OF_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_K2_3_5 | NONCLUSTERED |  |  | TROF_ENVIADO, TROF_LEVA_PECAS, TROF_TR_ID, TROF_OF_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K1_K2_4364 | NONCLUSTERED |  |  | TROF_TR_ID, TROF_OF_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K2 | NONCLUSTERED |  |  | TROF_OF_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K2_K1 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K2_K1_3_5 | NONCLUSTERED |  |  | TROF_ENVIADO, TROF_LEVA_PECAS, TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K2_K1_K3 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_TR_ID, TROF_ENVIADO |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K2_K1_K3_9987 | NONCLUSTERED |  |  | TROF_OF_ID, TROF_TR_ID, TROF_ENVIADO |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K3 | NONCLUSTERED |  |  | TROF_ENVIADO |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K3_1 | NONCLUSTERED |  |  | TROF_TR_ID, TROF_ENVIADO |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K3_1_8066 | NONCLUSTERED |  |  | TROF_TR_ID, TROF_ENVIADO |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K3_K2_K1 | NONCLUSTERED |  |  | TROF_ENVIADO, TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_index_TRANSP_OF_7_258099960__K3_K2_K1_4364 | NONCLUSTERED |  |  | TROF_ENVIADO, TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_OF | _dta_stat_258099960_3_2_1 | NONCLUSTERED |  |  | TROF_ENVIADO, TROF_OF_ID, TROF_TR_ID |
| dbo.TRANSP_TIPO | PK_TRANSP_TIPO | CLUSTERED | Y | Y | TRTP_ID |
| dbo.TRANSP_TRACKER | PK_TRANSP_TRACKER | CLUSTERED | Y | Y | TRACKER_ID |
| dbo.TRANSP_VAL | PK_TRANSP_VAL | CLUSTERED | Y | Y | TRVAL_VAL_ID, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K1 | NONCLUSTERED |  |  | TRVAL_VAL_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K1_K2_3 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_VAL_ID, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K1_K2_3_9987 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_VAL_ID, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K2_1_3 | NONCLUSTERED |  |  | TRVAL_VAL_ID, TRVAL_VALOR, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K2_3 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K2_3_4364 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K2_K1_3 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_TR_ID, TRVAL_VAL_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K2_K1_3_9987 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_TR_ID, TRVAL_VAL_ID |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K3 | NONCLUSTERED |  |  | TRVAL_VALOR |
| dbo.TRANSP_VAL | _dta_index_TRANSP_VAL_7_503672842__K3_K1_K2 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_VAL_ID, TRVAL_TR_ID |
| dbo.TRANSP_VAL | _dta_stat_503672842_3_1_2 | NONCLUSTERED |  |  | TRVAL_VALOR, TRVAL_VAL_ID, TRVAL_TR_ID |
| dbo.TRANSPORTE | PK_TRANSPORTE | CLUSTERED | Y | Y | TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1 | NONCLUSTERED |  |  | TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_1912 | NONCLUSTERED |  |  | TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_6 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_6_11 | NONCLUSTERED |  |  | TR_DATA, TR_DESCRICAO, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_6_11_8066 | NONCLUSTERED |  |  | TR_DATA, TR_DESCRICAO, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_6_1771 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6 | NONCLUSTERED |  |  | TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6_11_18_22_24_31_37 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_PUBLICO, TR_DATA_ENTREGA, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6_2_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25 | NONCLUSTERED |  |  | TR_DEST_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6_2_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25_1040 | NONCLUSTERED |  |  | TR_DEST_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6_9987 | NONCLUSTERED |  |  | TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K3_K6_K22_11_18_24_31_37 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_PUBLICO, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_ID, TR_TRTP_ID, TR_DATA, TR_DATA_ENTREGA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6 | NONCLUSTERED |  |  | TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_11 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_11_9987 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_2_3_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25 | NONCLUSTERED |  |  | TR_DEST_ID, TR_TRTP_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_2_3_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25_5201 | NONCLUSTERED |  |  | TR_DEST_ID, TR_TRTP_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_3 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_3_11_18_22_24_31_37 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_DESCRICAO, TR_PUBLICO, TR_DATA_ENTREGA, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_3_8066 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_9987 | NONCLUSTERED |  |  | TR_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K22_K3_11_18_24_31_37 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_PUBLICO, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_ID, TR_DATA, TR_DATA_ENTREGA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K3 | NONCLUSTERED |  |  | TR_ID, TR_DATA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K3_1912 | NONCLUSTERED |  |  | TR_ID, TR_DATA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K3_2_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25 | NONCLUSTERED |  |  | TR_DEST_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_DATA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K3_2_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25_4364 | NONCLUSTERED |  |  | TR_DEST_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_ID, TR_DATA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K1_K6_K8_K3_K4 | NONCLUSTERED |  |  | TR_ID, TR_DATA, TR_PAISES_ID, TR_TRTP_ID, TR_E_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K12 | NONCLUSTERED |  |  | TR_TRANSPORTE_NOSSO |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K3_K6_1_2_4_5_7_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_ | NONCLUSTERED |  |  | TR_ID, TR_DEST_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_GOOGLE_NAO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_DOCSENVIADOS, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_OPERADOR_CODIGO, TR_PORTO_CODIGO, TR_LATITUDE, TR_LONGITUDE, TR_COORD_ULT_UPD, TR_ESTADO_COD, TR_DATA_PREV_CHEG, TR_HORA_PREV_CHEG, TR_AUX_ORDER, TR_LATITUDE_ORIG, TR_LONGITUDE_ORIG, TR_LATITUDE_DEST, TR_LONGITUDE_DEST, TR_VALOR_ESTIMADO, TR_OBS_CLIENTE, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6 | NONCLUSTERED |  |  | TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_1_3_4_8 | NONCLUSTERED |  |  | TR_ID, TR_TRTP_ID, TR_E_ID, TR_PAISES_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_11 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_5543 | NONCLUSTERED |  |  | TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K1 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K1_11 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K1_4149 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K1_8066 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K22_K1_K3_11_18_24_31_37 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_PUBLICO, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_DATA, TR_DATA_ENTREGA, TR_ID, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K3 | NONCLUSTERED |  |  | TR_DATA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6_K8_K1_K3_K4 | NONCLUSTERED |  |  | TR_DATA, TR_PAISES_ID, TR_ID, TR_TRTP_ID, TR_E_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_1_2_3_4_5_7_8_9_10_11_12_13_14_15_16_17_18_19_20_21_22_23_24_25_26_27_28_29_30_31_32_ | NONCLUSTERED |  |  | TR_ID, TR_DEST_ID, TR_TRTP_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_GOOGLE_NAO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_DOCSENVIADOS, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_OPERADOR_CODIGO, TR_PORTO_CODIGO, TR_LATITUDE, TR_LONGITUDE, TR_COORD_ULT_UPD, TR_ESTADO_COD, TR_DATA_PREV_CHEG, TR_HORA_PREV_CHEG, TR_AUX_ORDER, TR_LATITUDE_ORIG, TR_LONGITUDE_ORIG, TR_LATITUDE_DEST, TR_LONGITUDE_DEST, TR_VALOR_ESTIMADO, TR_OBS_CLIENTE, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_11 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_DATA |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_11 | NONCLUSTERED |  |  | TR_DESCRICAO, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_2_3_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25 | NONCLUSTERED |  |  | TR_DEST_ID, TR_TRTP_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_2_3_4_5_7_8_9_10_11_12_14_15_16_18_19_20_21_22_23_24_25_4149 | NONCLUSTERED |  |  | TR_DEST_ID, TR_TRTP_ID, TR_E_ID, TR_DATA_CRIACAO, TR_DATA_REGRESSO, TR_PAISES_ID, TR_MORADA, TR_OBSERVACOES, TR_DESCRICAO, TR_TRANSPORTE_NOSSO, TR_CONTACTO_DESTINO, TR_TRACK_TIPO, TR_TRACK_NR, TR_PUBLICO, TR_TRACK_LINK, TR_CELESTE, TR_DATA_ENTREGA_PREV, TR_DATA_ENTREGA, TR_TRACKER_DATA, TR_TRACKER_ID, TR_TRTP_ID_EMB, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_3 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_3_11_18_22_24_31_37 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_DESCRICAO, TR_PUBLICO, TR_DATA_ENTREGA, TR_TRACKER_ID, TR_ESTADO_COD, TR_LATITUDE_DEST, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K6D_K1_3_6497 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_index_TRANSPORTE_7_1957582012__K8_K1_K3_K4_K6 | NONCLUSTERED |  |  | TR_PAISES_ID, TR_ID, TR_TRTP_ID, TR_E_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_stat_1957582012_1_3_6 | NONCLUSTERED |  |  | TR_ID, TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_stat_1957582012_1_6_22_3 | NONCLUSTERED |  |  | TR_ID, TR_DATA, TR_DATA_ENTREGA, TR_TRTP_ID |
| dbo.TRANSPORTE | _dta_stat_1957582012_1_6_8_3_4 | NONCLUSTERED |  |  | TR_ID, TR_DATA, TR_PAISES_ID, TR_TRTP_ID, TR_E_ID |
| dbo.TRANSPORTE | _dta_stat_1957582012_3_6 | NONCLUSTERED |  |  | TR_TRTP_ID, TR_DATA |
| dbo.TRANSPORTE | _dta_stat_1957582012_6_1 | NONCLUSTERED |  |  | TR_DATA, TR_ID |
| dbo.TRANSPORTE | _dta_stat_1957582012_6_22 | NONCLUSTERED |  |  | TR_DATA, TR_DATA_ENTREGA |
| dbo.TRANSPORTE | _dta_stat_1957582012_6_8 | NONCLUSTERED |  |  | TR_DATA, TR_PAISES_ID |
| dbo.TRANSPORTE | _dta_stat_1957582012_8_1_3_4 | NONCLUSTERED |  |  | TR_PAISES_ID, TR_ID, TR_TRTP_ID, TR_E_ID |
| dbo.TRANSPORTE_VERIFICACAO | PK_TRANSPORTE_VERIFICACAO | CLUSTERED | Y | Y | TRV_TR_ID, TRV_E_ID |
| dbo.TransporteDestino | PK_TransporteDestino | CLUSTERED | Y | Y | TRD_ID |
| dbo.TransporteDestino | IX_TransporteDestino | NONCLUSTERED |  |  | TRD_TR_ID |
| dbo.TransporteLocalizacao | PK_EncomendaLocalizacao | CLUSTERED | Y | Y | codEncomendaLocalizacao |
| dbo.TransporteLocalizacao | _dta_index_TransporteLocalizacao_7_599673184__K6 | NONCLUSTERED |  |  | codEncomendaPercurso |
| dbo.TransporteLocalPesquisado | PK_LocalPesquisado | CLUSTERED | Y | Y | localPesquisado |
| dbo.TransporteNavio | PK_NAvio | CLUSTERED | Y | Y | codBarco |
| dbo.TransporteOperador | PK_Operador | CLUSTERED | Y | Y | codOperador |
| dbo.TransportePercurso | PK_EncomendaPercurso | CLUSTERED | Y | Y | codEncomendaPercurso |
| dbo.TransportePercurso | _dta_index_TransportePercurso_7_727673640__K8 | NONCLUSTERED |  |  | barco |
| dbo.TransportePercursoHistorico | PK_EncomendaPercursoHistorico | CLUSTERED | Y | Y | codEncomendaPercursoHistorico |
| dbo.TransportePercursoHistorico | _dta_index_TransportePercursoHistorico_7_759673754__K2 | NONCLUSTERED |  |  | codEncomenda |
| dbo.TransportePercursoHistoricoDetalhe | PK_EncomendaPercursoHistoricoDetalhe | CLUSTERED | Y | Y | codEncomendaPercursoHistoricoDetalhe |
| dbo.TransportePercursoHistoricoDetalhe | _dta_index_TransportePercursoHistoricoDetal_7_791673868__K10 | NONCLUSTERED |  |  | barco |
| dbo.TransportePorto | PK_Porto | CLUSTERED | Y | Y | codPorto |
| dbo.TransporteSP | PK_TransporteSP | CLUSTERED | Y | Y | codTransporte |
| dbo.TransporteTmp_Percurso | PK_tmp_EncomendaPercurso | CLUSTERED | Y | Y | codSeq |
| dbo.TURNO | PK_TURNO | CLUSTERED | Y | Y | TURN_ID |
| dbo.UNIDADE | PK_UNIDADE | CLUSTERED | Y | Y | UNI_ID |
| dbo.USERS | PK_USERS | CLUSTERED | Y | Y | USE_ID |
| dbo.users_laravel | PK__users_la__3213E83F463E8EA8 | CLUSTERED | Y | Y | id |
| dbo.users_laravel | users_laravel_email_unique | NONCLUSTERED |  | Y | email |
| dbo.VALOR | PK_VALORES | CLUSTERED | Y | Y | VAL_ID |
| dbo.VALOR_TIPO | PK_VALOR_TIPO | CLUSTERED | Y | Y | TPVAL_ID |
| dbo.VARIAVEIS | PK_VARIAVEIS | CLUSTERED | Y | Y | VAR_ID |
| dbo.Velocidade | PK__Velocida__CE2C1018F417FB5D | CLUSTERED | Y | Y | IDVelocidade |
| dbo.Velocidade | _dta_index_Velocidade_7_588581185__K2 | NONCLUSTERED |  |  | AtletaProvaID |
| dbo.VendaLoja | PK_VendaLoja | CLUSTERED | Y | Y | venda_id |
| dbo.VendaLojaProduto | PK_VendaLojaProduto | CLUSTERED | Y | Y | venda_id, p_id |
| dbo.Z_PrevisaoPlano | _dta_index_Z_PrevisaoPlano_7_1079674894__K6 | NONCLUSTERED |  |  | Laminador |
| dbo.ZONA_GEOGRAFICA | PK_ZONA_GEOGRAFICA | CLUSTERED | Y | Y | ZG_ID |

## 5. Liveness — ultima escrita por tabela

_MAX() da 'melhor' coluna de data de cada tabela. Mostra o que ainda esta vivo._

| schema.tabela | linhas | coluna de data | ultimo valor |
|---|--:|---|---|
| dbo.DIAS_TRABALHO | 15,637 | DTRB_DATA | 2078-06-06 00:00:00 |
| dbo.TRANSP_DOCS | 46,797 | TRDOC_DATA | 2048-06-29 00:00:00 |
| dbo.KPI_OBJECTIVO | 267 | KPIO_OBJECTIVO_DATA | 2032-12-31 |
| dbo.CENTRO_RESERVA_TRANSFER | 2,386 | CRT_DATA | 2029-01-28 17:30:00 |
| dbo.OF_FP | 2,629,039 | OFFP_DATAINICIO | 2026-12-19 08:59:00 |
| dbo.MOVIMENTO | 12,402,826 | MOV_DATASAIDA | 2026-10-02 00:00:00 |
| dbo.ORDEMFABRICO | 441,644 | OF_DATA | 2026-10-02 00:00:00 |
| dbo.PROVAS | 21 | PRV_DATA_PARTIDA | 2026-09-27 |
| dbo.FATURA | 1,013 | date_of_issue | 2026-09-12 |
| dbo.ENTIDADE | 8,947 | E_DATAENTRADA | 2026-09-03 00:00:00 |
| dbo.PROVAS_BOOKING | 800 | PRVB_DATA_CHEGADA | 2026-08-03 |
| dbo.ENT_MOV | 166,327 | MOVENT_DATA_F | 2026-06-30 17:00:00 |
| dbo.Z_PrevisaoPlano | 303 | Dt_Trans | 2026-06-26 00:00:00 |
| dbo.TRANSPORTE | 11,364 | TR_DATA | 2026-06-19 |
| dbo.TRANSP_DATAS | 3,017 | TRDT_DATA_NOVA | 2026-05-22 |
| dbo.IOT_SENSOR | 32 | SENSOR_LAST_SEEN | 2026-05-17 12:45:38.790000 |
| dbo.IOT_SENSOR_DATA | 3,637,617 | SD_DATE | 2026-05-17 12:45:38.770000 |
| dbo.telescope_entries | 2,471,772 | created_at | 2026-05-17 12:45:38 |
| dbo.TransportePercursoHistorico | 40,484 | data | 2026-05-17 12:20:37.593000 |
| dbo.PEDIDOS | 116,010 | PED_DATA | 2026-05-17 08:00:00 |
| dbo.AGENTE_FATURACAO_UPDATE | 841 | AFU_DATA | 2026-05-17 07:00:18.860000 |
| dbo.TRANSP_OF | 92,902 | TROF_DATA_CRIACAO | 2026-05-16 21:29:00 |
| dbo.rfid_cache | 2 | created_at | 2026-05-16 13:47:02.573000 |
| dbo.OF_CHECKLIST | 2,997,803 | OFCH_DATA_ACTUALIZACAO | 2026-05-16 09:29:00 |
| dbo.OF_ATTACH | 130,751 | ATCH_DATA | 2026-05-16 |
| dbo.SGIDI_FICHEIRO | 25,869 | SGIDIF_DATA | 2026-05-15 16:01:00 |
| dbo.SGIDI_PASTA | 7,495 | SGIDIP_DATA | 2026-05-15 16:01:00 |
| dbo.ALARM | 110,264 | ALARM_DATA | 2026-05-15 14:30:00 |
| dbo.PRODUTO | 14,025 | P_DATACRIACAO | 2026-05-15 13:48:00 |
| dbo.PRODUTO_COMPONENTE | 117,952 | COMP_DATA_ALT | 2026-05-15 10:34:00 |
| dbo.ENT_ENT_PEDIDO_PROVISORIO | 3 | EEP_DATA_CRIACAO | 2026-05-15 09:06:00 |
| dbo.PROVAS_FICHEIROS | 307 | PRVFX_DATA | 2026-05-14 16:38:47.530000 |
| dbo.OF_PROPRIETARIO | 3,826 | OFPROP_DATA | 2026-05-14 |
| dbo.COMUNICACAO | 100 | COM_DATA | 2026-05-14 |
| dbo.ENTIDADE_FASE | 1,270 | EFP_DATAINICIO | 2026-05-13 15:09:00 |
| dbo.REPARACOES_PROVAS | 2,028 | REP_RECEBIDO | 2026-05-13 00:00:00 |
| dbo.OF_ENTIDADE | 5,644 | OFE_DATA | 2026-05-13 |
| dbo.REP_OF_FP | 3,416 | ROFFP_DATA_I | 2026-05-10 05:54:00 |
| dbo.LISTA | 163 | L_DATA_CRIACAO | 2026-05-04 16:04:00 |
| dbo.DOC | 214 | created_at | 2026-05-04 15:34:00 |
| dbo.PRODUTO_FASE | 42,829 | PRODF_DATA | 2026-04-30 14:30:00 |
| dbo.CENTRO_RESERVA | 1,694 | RES_DATA_FIM | 2026-04-01 14:00:00 |
| dbo.CENTRO_RESERVA_QUARTOS | 3,550 | CRQ_DATA_SAI | 2026-04-01 00:00:00 |
| dbo.TRANSP_ENTIDADE | 2,003 | TRE_DATA_VOLTA | 2026-03-07 00:00:00 |
| dbo.OF_VENDA | 22 | OFV_DATA_SUBMETIDO | 2026-03-06 |
| dbo.CENTRO_RESERVA_OFS | 3,172 | RO_DATA_FIM | 2026-02-20 15:57:00 |
| dbo.OF_OF_TIPOUSO | 3,196 | OFOFTU_DATASAIDA | 2026-02-19 09:17:00 |
| dbo.ENTIDADE_MORADA | 952 | EM_DELETED | 2026-02-04 |
| dbo.ENTIDADE_OBS | 4,142 | EOBS_DATA | 2026-01-23 00:00:00 |
| dbo.ARMAZEM | 25 | ARM_DATA_CRIACAO | 2026-01-05 11:18:00 |
| dbo.exports | 27 | completed_at | 2025-08-05 10:05:03.810000 |
| dbo.users_laravel | 2 | created_at | 2025-07-11 14:37:21.820000 |
| dbo.ORCAMENTO | 2 | updated_at | 2025-07-10 11:12:55.447000 |
| dbo.CORREIO_FACT | 9,036 | CORRF_DATA_CRIACAO | 2025-07-07 11:47:00 |
| dbo.notifications | 25 | created_at | 2025-07-04 11:52:17.697000 |
| dbo.IDEIA_EVOL | 1,064 | IDEV_DATA_I | 2025-05-30 10:59:00 |
| dbo.IDEIA_DOC | 78 | IDDOC_DATA | 2025-05-30 10:18:00 |
| dbo.IDEIA | 325 | ID_DATA | 2025-05-30 10:12:00 |
| dbo.KPI | 115 | KPI_DATA | 2025-04-02 |
| dbo.TH | 586,376 | TH_DATA_REG | 2025-02-26 13:01:00 |
| dbo.IDEIA_TAREFA | 412 | IDTAR_DATA | 2025-02-03 13:32:00 |
| dbo.PRODUTO_LISTA | 26 | PL_DATA | 2024-10-02 13:44:00 |
| dbo.CENTRO_ESTAGIO_DESPESAS | 249 | CED_DATA | 2024-05-13 00:00:00 |
| dbo.IDEIA_COLAB | 209 | IDCOL_DATA | 2024-05-03 11:03:00 |
| dbo.PORTAO | 3,455 | PORTAO_DATA | 2024-03-20 07:52:00 |
| dbo.DOURO_AULA | 20 | AULA_DATA | 2023-10-19 15:57:00 |
| dbo.TransporteLocalizacao | 39,122 | ultUpdate | 2023-02-13 10:20:34.810000 |
| dbo.TransporteLocalPesquisado | 136 | lastSearch | 2023-02-13 10:20:34.750000 |
| dbo.IDEIA_CLASSIFIC_CHECK | 6 | IDCLCHK_DATAINICIO | 2023-02-10 |
| dbo.IDEIA_CLASSIFICACAO | 72 | IDCL_DATA | 2023-02-08 14:47:00 |
| dbo.TransportePercurso | 847 | dataCriacao | 2023-01-19 23:20:30.677000 |
| dbo.TransporteNavio | 247 | lastSearch | 2023-01-11 01:20:30.720000 |
| dbo.ENTIDADE_TREINOS | 401 | ETR_DATA | 2022-12-23 00:00:00 |
| dbo.DOURO_AULA_ENTIDADE | 4 | AULAE_DATA | 2022-10-28 |
| dbo.Trackimo_DeviceLocation | 5,173 | dataObtencao | 2022-08-08 10:23:51.273000 |
| dbo.Trackimo_Device | 30 | dataSync | 2022-08-08 10:23:51.273000 |
| dbo.Trackimo_Access | 20,313 | date | 2022-08-07 17:23:29.993000 |
| dbo.OF_RENTAL_PROVAS | 110 | OFR_DATA_ENTREGA | 2022-05-18 07:40:00 |
| dbo.Meeting | 123 | data_criacao | 2021-11-19 14:02:17.417000 |
| dbo.PLANEAMENTO_DIARIO | 64 | Dia | 2019-10-14 |
| dbo.TransporteDestino | 65 | TRD_DATACONFIRMACAO | 2019-01-15 17:17:00 |
| dbo.ENTIDADE_EQUIPA | 82 | EEQ_DATA_ENTRADA | 2018-09-21 09:32:00 |
| dbo.EQUIPA | 17 | EQ_DATA_CRIACAO | 2018-09-21 09:27:00 |
| dbo.ENCOMENDA | 410 | ENC_DATAENCOMENDA | 2018-03-20 00:00:00 |
| dbo.MOLDES_MOV | 3,673 | MLDU_DATA | 2017-10-31 00:00:00 |
| dbo.Encomenda_trk | 7 | ultUpdate | 2017-08-31 22:10:27.077000 |
| dbo.LISTA_MOVIMENTO | 5 | LM_DATA | 2017-05-12 13:54:00 |
| dbo.PRODUTO_COEFICIENTE | 15 | PCOEF_DATA | 2017-01-01 00:00:00 |
| dbo.ENTIDADE_DADOS | 1 | EDADOS_DATA | 2016-03-22 15:43:00 |
| dbo.IDEIA_ESTADO | 33 | IDEST_DATA | 2015-09-15 12:07:00 |
| dbo.ACTUALIZACOES | 2 | ACT_DATA | 2013-01-31 12:03:00 |
| dbo.IDEIA_REUNIAO | 3 | IDR_DATA | 2013-01-25 00:00:00 |
| dbo.FERIAS | 29 | DATA | 2012-12-31 00:00:00 |
| dbo.TRANSP_DESP_TIPO | 20 | trdesptp_eliminado | 2012-06-14 16:10:00 |
| dbo.PROC_AREA_FONTE | 72 | PROCAF_DATA | 2012-01-16 16:37:00 |
| dbo.AUDIT | 38 | AUD_DATACONCREAL | 2012-01-01 00:00:00 |
| dbo.CENTRO_RESERVA_CHEKLIST_ITEMS | 12 | CRCHKLI_ELIMINADO | 2011-11-07 09:11:00 |
| dbo.PROC_AREA | 74 | PROC_DATA | 2011-01-28 14:22:00 |
| dbo.SGIDI | 6 | SGIDI_DATA | 2010-12-02 12:27:00 |
| dbo.MOLDES | 91 | MLD_DATA | 2010-04-14 16:57:00 |
| dbo.LACAGEM | 86 | LAC_DATA_F | 2010-04-07 22:27:00 |
| dbo.PROB_CAUSA_SOL | 2 | PCS_DATACRIACAO | 2009-10-28 13:31:00 |
| dbo.RH_FORMACAO | 1 | RHF_DATA_PREVISTA | 1900-01-01 00:00:00 |
| dbo.testes | 1 | dddd | 1900-01-01 00:00:00 |

## 6. Profiling + amostras (tabelas de alto valor + 30 maiores)

### dbo.ENTIDADE_PHC_FACT
- linhas: **100,516**
- nulos por coluna (so colunas com >0% nulo):
  - EPHCF_EPHC_ID 33%, EPHCF_TP_ID_DISCIP 60%, EPHCF_TP_ID 14%

| EPHCF_EPHC_ID | EPHCF_ANO | EPHCF_MES | EPHCF_DIA | EPHCF_EPOCA | EPHCF_TP_ID_DISCIP | EPHCF_TP_ID | EPHCF_FACTURADO |
|---|---|---|---|---|---|---|---|
| NULL | 2022 | 6 | 3 | 2022 | NULL | NULL | 1139.35 |
| NULL | 2022 | 6 | 6 | 2022 | NULL | NULL | 154.47 |
| NULL | 2022 | 6 | 7 | 2022 | NULL | NULL | 1585.46 |

### dbo.IOT_SENSOR_DATA
- linhas: **3,637,624**
- nulos por coluna (so colunas com >0% nulo):
  - SD_POWER_1 14%, SD_POWER_2 29%, SD_POWER_3 29%, SD_CURRENT_1 65%, SD_CURRENT_2 65%, SD_CURRENT_3 65%, SD_TEMPERATURE 88%, SD_HUM 88%, SD_PRESSURE 100%

| SD_ID | SD_SENSOR_ID | SD_DATE | SD_POWER_1 | SD_POWER_2 | SD_POWER_3 | SD_CURRENT_1 | SD_CURRENT_2 | SD_CURRENT_3 | SD_TEMPERATURE | SD_HUM | SD_PRESSURE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 555201 | 12 | 2025-02-03 17:19:14.063000 | NULL | NULL | NULL | NULL | NULL | NULL | 23.2 | 35.2 | NULL |
| 555357 | 12 | 2025-02-03 18:10:26.157000 | NULL | NULL | NULL | NULL | NULL | NULL | 23.3 | 35.7 | NULL |
| 555507 | 12 | 2025-02-03 19:00:27.213000 | NULL | NULL | NULL | NULL | NULL | NULL | 23.6 | 35.3 | NULL |

### dbo.TH
- linhas: **586,376**
- nulos por coluna (so colunas com >0% nulo):
  - TH_HUM 0%, TH_FASE 61%, TH_DATA_UPDT 61%

| TH_ID | TH_DATA | TH_TEMP | TH_HUM | TH_DATA_REG | TH_FASE | TH_SONDA | TH_DATA_UPDT |
|---|---|---|---|---|---|---|---|
| 1 | 1900-01-01 00:00:00 | 22.66022940593781 | NULL | 1900-01-01 00:00:00 | NULL | 1 | NULL |
| 2 | 1900-01-01 00:00:00 | 22.579007849348887 | NULL | 1900-01-01 00:00:00 | NULL | 2 | NULL |
| 3 | 1900-01-01 00:00:00 | 22.309230542439796 | NULL | 1900-01-01 00:00:00 | NULL | 3 | NULL |

### dbo.ORDEMFABRICO
- linhas: **441,644**
- nulos por coluna (so colunas com >0% nulo):
  - OF_DATATRANSPORTE 97%, OF_DATAENTREGA 99%, OF_DATAPAGAMENTO 96%, OF_DATAINICIO 81%, OF_DATAFIM 71%, OF_OBSERVACOES 0%, OF_NOME 57%, OF_MORADAENTREGA 0%, OF_REFERENCIA 0%, OF_TELEFONE 83%, OF_EMAIL 83%, OF_TRANSPORTE 96%, OF_TRANSPORTEDOC 82%, OF_OFTU_ID 100%, OF_TURN_ID 92%, OF_ENC_ID 98%, OF_E_ID 99%, OF_P_ID_CDECK 91%, OF_P_ID_CCASCO 91%, OF_OF_ID_MLD 92%, OF_TR_ID 99%, OF_CRIADOR 6%, OF_ACTUALIZADOR 84%, OF_DATAACTUALIZACAO 84%, OF_P_ID_TOPO_FR 88%, OF_P_ID_TOPO_TR 88%, OF_P_ID_LATERAL_FR 88%, OF_P_ID_LATERAL_TR 88%, OF_P_ID_QUINAS 88%, OF_CUSTOS_CACHE 94%, OF_FACT 87%, OF_P_ID_QUINAS_TR 83%, OF_P_ID_GOLA 79%, OF_P_ID_HIST 9%, OF_TR_ID_ULT 82%, OF_TR_DESC_ULT 82%, OF_TR_DATA_ULT 82%, OF_TR_DATA_PREVISTA 97%, OF_PLANO_DATA_PREVISTA 92%, OF_PLANO_TURNO_PREVISTO 92%, OF_P_ID_AUTOCOLANTE 100%, OF_TAG_ID 99%, OF_SEQUENCIA_UPD 100%, OF_EM_ID 95%, OF_EM_ID_FACTURACAO 95%, OF_OF_ID_MAE 84%, OF_MOV_ID 100%, OF_PROMO_CODE 93%, OF_DATA_PROMO_DEALER 93%, OF_DATA_PROMO_CLIENT 100%, OF_PROMO_EMAIL 100%, OF_SENSOR_ID_VACUO 100%, OF_TAG_NFC 100%

| OF_ID | OF_DATA | OF_DATATRANSPORTE | OF_DATAENTREGA | OF_DATAPAGAMENTO | OF_DATAINICIO | OF_DATAFIM | OF_OBSERVACOES | OF_PRECOCUSTO | OF_PRECOVENDA | OF_NOME | OF_MORADAENTREGA | OF_REFERENCIA | OF_TELEFONE | OF_EMAIL | OF_TRANSPORTE | OF_TRANSPORTEDOC | OF_AUTOCOLANTE | OF_DESCONTO | OF_VALORPAGO | OF_COEFICIENTE | OF_PAGO | OF_DECKPINTURA | OF_CASCOPINTURA | OF_SUPERVISAO | OF_SUPERVISAOLAMINAGEM | OF_SEQUENCIA | OF_OFTU_ID | OF_TURN_ID | OF_ENC_ID | OF_P_ID | OF_E_ID | OF_E_ID_ENC | OF_P_ID_CDECK | OF_P_ID_CCASCO | OF_OF_ID_MLD | OF_FP_ID | OF_TR_ID | OF_MOLDE_ACESSORIO | OF_CRIADOR | OF_ACTUALIZADOR | OF_DATAACTUALIZACAO | OF_P_ID_TOPO_FR | OF_P_ID_TOPO_TR | OF_P_ID_LATERAL_FR | OF_P_ID_LATERAL_TR | OF_P_ID_QUINAS | OF_ARM_ID | OF_ARM_ID_LAM | OF_NUMUTIL | OF_CUSTOS_CACHE | OF_TRANSP | OF_FACT | OF_SUPERVISAOPINTURA | OF_P_ID_QUINAS_TR | OF_P_ID_GOLA | OF_DESCONTA_PESO | OF_P_ID_HIST | OF_REVISTO | OF_PARAPINTARFORA | OF_PREPREG | OF_TR_ID_ULT | OF_TR_DESC_ULT | OF_TR_DATA_ULT | OF_PARAALTERAR | OF_TR_DATA_PREVISTA | OF_PLANO_DATA_PREVISTA | OF_PLANO_TURNO_PREVISTO | OF_P_ID_AUTOCOLANTE | OF_TAG_ID | OF_PRECOCUSTO_DT | OF_UPDT | OF_ACERTO_RESINA | OF_SEQUENCIA_UPD | OF_PINT_CLASS | OF_PFORA_CLASS | OF_LINHAACAB | OF_ARM_FIXO | OF_COEFICIENTE_EXTRA | OF_VERSAO_NOVA | OF_EM_ID | OF_EM_ID_FACTURACAO | OF_OF_ID_MAE | OF_MOV_ID | OF_PROMO_CODE | OF_DATA_PROMO_DEALER | OF_DATA_PROMO_CLIENT | OF_PESO_DECK | OF_PESO_CASCO | OF_FALTA_MASCARA | OF_FALTA_DOCS_CLIENTE | OF_PROMO_EMAIL | OF_PRECOCUSTO_DT_INFLACIONADO | OF_FALTA_AUTOCOLANTE_NOME | OF_FALTA_PROTECCAO_PAGAIA | OF_FALTA_GARRAFA | OF_FALTA_PARAFUSOS | OF_FALTA_PESOS | OF_FALTA_TRACTION_PADS | OF_FALTA_FINCA_PES | OF_FALTA_BANCO | OF_FALTA_LEME | OF_FALTA_CAPA | OF_FALTA_TOALHA | OF_RAL_MAIN | OF_RAL_SEC | OF_DUREZA_DECK | OF_DUREZA_CASCO | OF_DUREZA_PROA | OF_SENSOR_ID_VACUO | OF_TAG_NFC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8888 | 2001-11-14 00:00:00 | 2002-06-25 00:00:00 | NULL | 2002-07-03 00:00:00 | NULL | 2002-05-24 00:00:00 |  | 0.0 | 0.0 |  |   | 10000001308 Box n º 1   32 x 32 x 20   2.100 kg  |   |   | Próprio |  |  | 0.0 | 0.0 | 0.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 40246 | 29776 | 19806 | 20579 | 20579 | NULL | 12 | NULL | False | NULL | MONTAGEM\Utilizador (20365 - Alexandre Pereira Costa) | 2026-03-11 11:27:00 | 20579 | 20579 | 20579 | 20579 | 20579 | 1 | 1 | 0 | NULL | False |  | False | 20579 | 20579 | False | NULL | False | False | False | 148 | Próprio | 2002-06-25 00:00:00 | False | NULL | NULL | NULL | NULL | NULL | 0.0 | False | 0.0 | NULL | 0 | 0 | 1 | False | 0.0 | True | NULL | NULL | NULL | NULL |  | 2021-06-25 | NULL | 0.0 | 0.0 | False | False | NULL | 0.0 | False | False | False | False | False | False | False | False | False | False | False |  |  | 0 | 0 | 0 | NULL | NULL |
| 8889 | 2001-11-14 16:02:00 | 2002-03-28 00:00:00 | NULL | 2002-01-10 00:00:00 | 2002-01-02 00:00:00 | 2002-01-10 00:00:00 | AW | 0.0 | 0.0 | NULL | England |  | NULL | NULL | Peter |  |  | 0.0 | 0.0 | 4.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 20415 | NULL | 19745 | 20579 | 20579 | 70082 | 12 | NULL | False | NULL | NULL | NULL | 20579 | 20579 | 20579 | 20579 | 20579 | 1 | 1 | 0 | NULL | False | NULL | False | 20579 | 20579 | False | NULL | False | False | False | 82 | peter | 2002-03-28 00:00:00 | False | NULL | NULL | NULL | NULL | NULL | 0.0 | False | 0.0 | NULL | 0 | 0 | 1 | False | 0.0 | True | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0.0 | 0.0 | False | False | NULL | 0.0 | False | False | False | False | False | False | False | False | False | False | False |  |  | 0 | 0 | 0 | NULL | NULL |
| 8893 | 2001-11-14 16:05:00 | 2002-03-05 00:00:00 | NULL | NULL | 2002-02-21 00:00:00 | 2002-03-04 00:00:00 | 70 Kg - Q H S | 0.0 | 0.0 | NULL | England |  | NULL | NULL | magnafrete - londres |  |  | 0.0 | 0.0 | 6.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 20406 | 25492 | 19745 | 20577 | 20579 | NULL | 12 | NULL | False | NULL | NULL | NULL | 20577 | 20577 | 20577 | 20577 | 20577 | 1 | 1 | 0 | NULL | False | NULL | False | 20577 | 20577 | False | NULL | False | False | False | 63 | magnafrete - londres | 2002-03-05 00:00:00 | False | NULL | NULL | NULL | NULL | NULL | 0.0 | False | 0.0 | NULL | 0 | 0 | 1 | False | 0.0 | True | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0.0 | 0.0 | False | False | NULL | 0.0 | False | False | False | False | False | False | False | False | False | False | False |  |  | 0 | 0 | 0 | NULL | NULL |

### dbo.produto_stocks_por_armazem
- linhas: **8,045**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| P_ID | Armazem_Id | Armazem | Stock |
|---|---|---|---|
| 33840 | 7 | Fábrica 3 (Fajozes) | -1.0 |
| 23830 | 7 | Fábrica 3 (Fajozes) | 0.0 |
| 34301 | 19 | CNC | 56.0 |

### dbo.vTrackingTransporte
- linhas: **1,654**
- nulos por coluna (so colunas com >0% nulo):
  - codOperador 93%, codPorto 94%, latitude 77%, longitude 77%, idTracker 78%, codEstado 5%, ETA 92%, lastUpdate 77%, dataEntrega 9%

| codTransporte | dataPartida | tipoTransporte | codOperador | codPorto | moradaDestino | latitude | longitude | refTipo | referencia | idTracker | codEstado | latitudeDest | longitudeDest | TR_DESCRICAO | ETA | lastUpdate | PAISES_NOME | dataEntrega | trackLink |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 13925 | 2017-05-12 | Camião | NULL | NULL |  | NULL | NULL |  |  | 1039338 | 3 | 0E-9 | 0E-9 | Bull - 1337 Sandvika - Norway X | NULL | NULL | Noruega  | 2017-05-22 | https://app.trackimo.com/public-map/#/map?token=rerh2p70jja89lg174rd4ljn80 |
| 15091 | 2017-11-17 | Barco | 4 | 320 |  | -34.900344307976 | -56.206360449765 | Container | MSCU9672928 | NULL | 2 | -34.900344308 | -56.206360450 | Mainter - Montevideo - Uruguai | 2022-01-11 | 2021-01-11 21:20:34 | Uruguai  | 2018-06-29 |  |
| 15176 | 2017-10-20 | Camião | NULL | NULL |  | 38.769137000000 | -9.137965000000 |  |  | 1041498 | 3 | 59.028612000 | 12.226943000 | Bootshaus - 666 91 Bengtsfors - Suecia   | NULL | 2017-11-09 10:36:36 | Suécia  | 2017-10-31 | https://app.trackimo.com/public-map/#/map?token=rs3g7es2nekkb2idsjjlbjl70v |

### dbo.vOF_Transporte
- linhas: **441,644**
- nulos por coluna (so colunas com >0% nulo):
  - OF_DATATRANSPORTE 97%, OF_DATAENTREGA 99%, OF_DATAPAGAMENTO 96%, OF_DATAINICIO 81%, OF_DATAFIM 71%, OF_OBSERVACOES 0%, OF_NOME 57%, OF_MORADAENTREGA 0%, OF_REFERENCIA 0%, OF_TELEFONE 83%, OF_EMAIL 83%, OF_TRANSPORTE 96%, OF_TRANSPORTEDOC 82%, OF_OFTU_ID 100%, OF_TURN_ID 92%, OF_ENC_ID 98%, OF_E_ID 99%, OF_P_ID_CDECK 91%, OF_P_ID_CCASCO 91%, OF_OF_ID_MLD 92%, OF_TR_ID 99%, OF_CRIADOR 6%, OF_ACTUALIZADOR 84%, OF_DATAACTUALIZACAO 84%, OF_P_ID_TOPO_FR 88%, OF_P_ID_TOPO_TR 88%, OF_P_ID_LATERAL_FR 88%, OF_P_ID_LATERAL_TR 88%, OF_P_ID_QUINAS 88%, OF_CUSTOS_CACHE 94%, TR_ID 81%, TR_DEST_ID 83%, TR_TRTP_ID 81%, TR_E_ID 85%, TR_DATA_CRIACAO 81%, TR_DATA 81%, TR_DATA_REGRESSO 100%, TR_PAISES_ID 83%, TR_MORADA 81%, TR_OBSERVACOES 81%, TR_DESCRICAO 81%, TR_TRANSPORTE_NOSSO 81%, TR_GOOGLE_NAO 81%, transporte 81%, TR_PUBLICO 81%

| OF_ID | OF_DATA | OF_DATATRANSPORTE | OF_DATAENTREGA | OF_DATAPAGAMENTO | OF_DATAINICIO | OF_DATAFIM | OF_OBSERVACOES | OF_PRECOCUSTO | OF_PRECOVENDA | OF_NOME | OF_MORADAENTREGA | OF_REFERENCIA | OF_TELEFONE | OF_EMAIL | OF_TRANSPORTE | OF_TRANSPORTEDOC | OF_AUTOCOLANTE | OF_DESCONTO | OF_VALORPAGO | OF_COEFICIENTE | OF_PAGO | OF_DECKPINTURA | OF_CASCOPINTURA | OF_SUPERVISAO | OF_SUPERVISAOLAMINAGEM | OF_SEQUENCIA | OF_OFTU_ID | OF_TURN_ID | OF_ENC_ID | OF_P_ID | OF_E_ID | OF_E_ID_ENC | OF_P_ID_CDECK | OF_P_ID_CCASCO | OF_OF_ID_MLD | OF_FP_ID | OF_TR_ID | OF_MOLDE_ACESSORIO | OF_CRIADOR | OF_ACTUALIZADOR | OF_DATAACTUALIZACAO | OF_P_ID_TOPO_FR | OF_P_ID_TOPO_TR | OF_P_ID_LATERAL_FR | OF_P_ID_LATERAL_TR | OF_P_ID_QUINAS | OF_ARM_ID | OF_ARM_ID_LAM | OF_NUMUTIL | OF_CUSTOS_CACHE | TR_ID | TR_DEST_ID | TR_TRTP_ID | TR_E_ID | TR_DATA_CRIACAO | TR_DATA | TR_DATA_REGRESSO | TR_PAISES_ID | TR_MORADA | TR_OBSERVACOES | TR_DESCRICAO | TR_TRANSPORTE_NOSSO | TR_GOOGLE_NAO | estado | transporte | TR_PUBLICO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8888 | 2001-11-14 00:00:00 | 2002-06-25 00:00:00 | NULL | 2002-07-03 00:00:00 | NULL | 2002-05-24 00:00:00 |  | 0.0 | 0.0 |  |   | 10000001308 Box n º 1   32 x 32 x 20   2.100 kg  |   |   | Próprio |  |  | 0.0 | 0.0 | 0.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 40246 | 29776 | 19806 | 20579 | 20579 | NULL | 12 | NULL | False | NULL | MONTAGEM\Utilizador (20365 - Alexandre Pereira Costa) | 2026-03-11 11:27:00 | 20579 | 20579 | 20579 | 20579 | 20579 | 1 | 1 | 0 | NULL | 148 | NULL | 4 | NULL | 2009-01-12 17:07:00 | 2002-06-25 | NULL | NULL |  |  | Próprio | False | False | 3 | 2002/06/25 / Próprio | True |
| 8889 | 2001-11-14 16:02:00 | 2002-03-28 00:00:00 | NULL | 2002-01-10 00:00:00 | 2002-01-02 00:00:00 | 2002-01-10 00:00:00 | AW | 0.0 | 0.0 | NULL | England |  | NULL | NULL | Peter |  |  | 0.0 | 0.0 | 4.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 20415 | NULL | 19745 | 20579 | 20579 | 70082 | 12 | NULL | False | NULL | NULL | NULL | 20579 | 20579 | 20579 | 20579 | 20579 | 1 | 1 | 0 | NULL | 82 | NULL | 4 | NULL | 2009-01-12 17:07:00 | 2002-03-28 | NULL | NULL |  |  | peter | False | False | 3 | 2002/03/28 / peter | True |
| 8893 | 2001-11-14 16:05:00 | 2002-03-05 00:00:00 | NULL | NULL | 2002-02-21 00:00:00 | 2002-03-04 00:00:00 | 70 Kg - Q H S | 0.0 | 0.0 | NULL | England |  | NULL | NULL | magnafrete - londres |  |  | 0.0 | 0.0 | 6.0 | True | False | False | False | False | 0 | NULL | NULL | NULL | 20406 | 25492 | 19745 | 20577 | 20579 | NULL | 12 | NULL | False | NULL | NULL | NULL | 20577 | 20577 | 20577 | 20577 | 20577 | 1 | 1 | 0 | NULL | 63 | NULL | 4 | NULL | 2009-01-12 17:07:00 | 2002-03-05 | NULL | NULL |  |  | magnafrete - londres | False | False | 3 | 2002/03/05 / magnafrete - londres | True |

### dbo.FuncionariosActivos
- linhas: **158**
- nulos por coluna (so colunas com >0% nulo):
  - E_EMAIL 1%

| E_ID | E_NOME | E_EMAIL |
|---|---|---|
| 20344 | Alexandre Nunes Abelheira | luisaxano@gmail.com                                                              |
| 20345 | Paulo Gomes Faria (Melro) |   |
| 20348 | João da Silva Alvão  |  |

### dbo.OF_PRODUTOS_V2
- linhas: **5,512**
- nulos por coluna (so colunas com >0% nulo):
  - p_l_id 67%, p_np_id 31%, p_m_id 50%, p_tam_id 49%

| p_tp_id | p_id | p_nome | p_l_id | p_np_id | p_m_id | p_tam_id | p_p_id | p_id_const | p_precocusto | p_precovenda |
|---|---|---|---|---|---|---|---|---|---|---|
| 84 | 20060 | K2 E (0) (descont.) | NULL | 2 | NULL | NULL | -1 | -1 | 5.4836800000000006 | 0.0 |
| 84 | 20061 | K4 G L80 (descont.) | NULL | 3 | NULL | NULL | -1 | -1 | -15.2887025 | 0.0 |
| 84 | 20062 | K4 SCS (descont.) | NULL | 3 | NULL | NULL | -1 | -1 | 19.2297304 | 0.0 |

### dbo.RetornosFuncionario
- linhas: **88,604**
- nulos por coluna (so colunas com >0% nulo):
  - Funcionario 1%, dataRep 0%

| Funcionario | Fase | dataRep | rtns | culpado | coefs |
|---|---|---|---|---|---|
| 23352 | 42 | 2023-05-08 16:28:00 | 1 | 0 | 1.0 |
| 24959 | 46 | 2024-06-18 06:13:00 | 1 | 0 | 1.375 |
| 20708 | 40 | 2019-11-28 13:08:00 | 1 | 0 | 0.75 |

### dbo.OF_ESTADOS
- linhas: **72**
- nulos por coluna (so colunas com >0% nulo):
  - FP_FP_ID 89%

| FP_ID | FP_NOME | FP_SEQUENCIA | FP_FP_ID | fp_pode_repetir |
|---|---|---|---|---|
| -1 |   | 0 | NULL | 1 |
| 1 | Laminagem | 10 | NULL | 1 |
| 2 | Cura | 11 | NULL | 1 |

### dbo.ENTIDADE
- linhas: **8,947**
- nulos por coluna (so colunas com >0% nulo):
  - E_GENERO 44%, E_DATANASCIMENTO 55%, E_CLUBE 42%, E_CONTACTO 70%, E_PAIS 10%, E_CIDADE 46%, E_MORADA 65%, E_CODIGOPOSTAL 47%, E_MORADAENTREGA 79%, E_TELEFONE 66%, E_EMAIL 4%, E_OBSERVACOES 46%, E_ZG_ID 100%, E_FOTO 95%, E_CONTRIBUINTE 91%, E_DATAENTRADA 13%, E_TV_ID 97%, E_EQ_ID 100%, E_P_ID_FP 74%, E_FP_POS 3%, E_P_ID_BANCO 85%, E_BANCO_POS 3%, E_P_ID_STRAP 74%, E_L_ID 96%, E_LOGIN 83%, E_GOOGLE_CALENDAR 100%, E_PHC_ID 99%, E_BENCH_CLASSE 99%, E_FACT_EPOCA 42%, E_FACT_TRIMESTRE 42%, E_DOURO_ID 100%, E_DOURO_SERVICO 100%, E_DOURO_VALIDADE 100%, E_PAIS_ID 83%, E_MODALIDADE 100%, E_FP_ID 96%, E_E_ID 100%, E_CARTAO_RFID 58%, E_SHOP_ID 97%, E_PREFERENCIA 84%, E_TEMPO_500 100%, E_TEMPO_1000 100%, E_URL 100%, E_TAGS 99%

| E_ID | E_NOME | E_GENERO | E_DATANASCIMENTO | E_PESOCORPORAL | E_CLUBE | E_NUMTREINOS | E_CONTACTO | E_PAIS | E_CIDADE | E_MORADA | E_CODIGOPOSTAL | E_MORADAENTREGA | E_TELEFONE | E_EMAIL | E_COMPETICAO | E_OBSERVACOES | E_PRAZOPAGAMENTO | E_TRANSPORTEPAGO | E_VISITA | E_HORAHOMEM | E_FAZENTREGA | E_PRAZOENTREGA | E_TOURING | E_SPRINT | E_EXPEDITIONS | E_MARATHON | E_ENT_ID | E_ZG_ID | E_ACTIVO | E_FOTO | E_CONTRIBUINTE | E_CUSTOHORA | E_DATAENTRADA | E_TV_ID | E_FALTA_DESC_HORAS | E_HORAS_A_DOBRAR | E_EQ_ID | E_P_ID_FP | E_FP_POS | E_P_ID_BANCO | E_BANCO_POS | E_P_ID_STRAP | E_L_ID | E_LOGIN | E_PASSWD | E_TIPO_UTIL | E_TAM_CALCADO | E_TAM_CALCA | E_TAM_CAMISOLA | E_TAM_FATO | E_GOOGLE_CALENDAR | E_PHC_ID | E_BENCH_CLASSE | E_FACT_EPOCA | E_FACT_TRIMESTRE | E_DOURO_ID | E_DOURO_SERVICO | E_DOURO_VALIDADE | E_DESCONTO | E_PAIS_ID | E_MODALIDADE | E_CHEFE | E_FP_ID | E_PRODUTIVIDADE | E_ACESSO_WEB | E_PRECO_NACIONAL | E_E_ID | E_NELO | E_TRANSPORTADOR | E_CARTAO_RFID | E_SHOP_ID | E_ISENCAO_HORARIO | E_ALTURA | E_CREDITO_PROMO | E_TAXA_IRS | E_BARCONUMERO | E_PAGAIANUMERO | E_BMI | E_TEMPO | E_GORDURA | E_FLEXOES | E_ABS | E_FUMADOR | E_PREFERENCIA | E_TEMPO_500 | E_TEMPO_1000 | E_CERTIFICADO_CO2 | E_URL | E_TAGS | E_RESULTADO | E_NIVEL | E_TESTES_PORTUGAL | E_RESPOSTA | E_CONTA_POC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | teste | NULL | NULL | 0.0 | NULL | 0 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | False | NULL | 0 | False | False | 0.0 | False | 0 | False | False | False | False | 42 | NULL | True | NULL | NULL | 0.0 | NULL | NULL | False | False | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |  | 3 |  |  |  |  | NULL | NULL | NULL | 0.00 | 0.00 | NULL | NULL | NULL | 0.0 | NULL | NULL | False | NULL | 0.0 | False | False | NULL | False | False | NULL | NULL | False | 0.0 | 0.0 | 0.0 |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | NULL | NULL | NULL | False | NULL | NULL | 0 | 0 | False | 0 |  |
| 19416 | Guy De Prins |  | 1979-12-16 00:00:00 | 66.0 | KCCM Mechelen | 9 |  | Belgium | 2800 Mechelen | Boetestraat 12 |  | Boetestraat 12 |  | guy@dpdruk.be | False | Selecção Belga | 0 | False | False | 0.0 | False | 0 | False | False | False | False | 17 | NULL | True | NULL | NULL | 0.0 | 2019-06-18 23:32:00 | NULL | False | False | NULL | NULL |  | NULL |  | NULL | NULL | 19416 |  | 3 |  |  |  |  | NULL | NULL | NULL | 0.00 | 0.00 | NULL | NULL | NULL | 0.0 | NULL | NULL | False | NULL | 0.0 | False | False | NULL | False | False | 0 | NULL | False | 0.0 | 0.0 | 0.0 |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | NULL | NULL | NULL | False | NULL | NULL | 0 | 0 | False | 0 |  |
| 19417 | Johan Dahl |  | NULL | 89.0 | River City Paddlers | 5 |  | USA | Folson, CA 95630 | 1301 Young Wo Cir |  | 1301 Young Wo Cir |  | paragongi@yahoo.com | False | Master Sueco a residir nos Eua | 0 | False | False | 0.0 | False | 0 | False | False | False | False | 17 | NULL | True | NULL | NULL | 0.0 | 2019-06-18 23:32:00 | NULL | False | False | NULL | NULL |  | NULL |  | NULL | NULL | 19417 |  | 3 |  |  |  |  | NULL | NULL | NULL | 0.00 | 0.00 | NULL | NULL | NULL | 0.0 | NULL | NULL | False | NULL | 0.0 | False | False | NULL | False | False | 0 | NULL | False | 0.0 | 0.0 | 0.0 |  |  | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | NULL | NULL | NULL | False | NULL | NULL | 0 | 0 | False | 0 |  |

### dbo.PRODUTO
- linhas: **14,025**
- nulos por coluna (so colunas com >0% nulo):
  - P_NOME_EN 26%, P_DESCRICAO 2%, P_MEDIDA 95%, P_IMAGEM 39%, P_NP_ID 69%, P_TAM_ID 77%, P_TP_ID 0%, P_M_ID 80%, P_P_ID 95%, P_PCONT_ID 27%, P_E_ID 68%, P_UNI_ID 27%, P_DESCRICAO_TECNICA 29%, P_CRIADOR 94%, P_ACTUALIZADOR 93%, P_DATAACTUALIZACAO 93%, P_CUSTO_CACHE 92%, P_PL_ID 85%, P_MODELO_COLORDESIGNER 96%, P_TP_ID_DISCIPLINA 87%, P_L_ID 87%, P_URL_IMG_PROD 100%, P_UNI_ID_MOVIMENTOS 28%, P_REF_UNIV 47%, P_COLOR 99%, P_3D 97%, P_ARM_ID 13%, P_ATRIB_ID_DESIGN 98%, P_EAN 93%, P_E_ID_RESP 68%, P_E_ID_CRIADOR 66%, P_DESCRICAO_EN 62%, P_PESOLAM_UPD 99%, P_PESOACAB_UPD 99%, P_QTDDECK_REAL_UPD 91%, P_QTDCASCO_REAL_UPD 91%, P_CO2_DATA_ALTERADO 94%

| P_ID | P_NOME | P_NOME_EN | P_DESCRICAO | P_PRECOCUSTO | P_PRECOVENDA | P_COEFICIENTE | P_STOCK | P_STOCKMIN | P_NECESSIDADES | P_CONVESAO | P_MEDIDA | P_PESOLAM | P_PESOACAB | P_MPLAMINAGEM | P_MODLAMINAGEM | P_MPACABAMENTO | P_MODACABAMENTO | P_QTDDECK | P_QTDCASCO | P_FABRICOINTERNO | P_QTDENCOMENDA | P_DATACRIACAO | P_IMAGEM | P_ACTIVO | P_NP_ID | P_TAM_ID | P_TP_ID | P_M_ID | P_P_ID | P_PCONT_ID | P_E_ID | P_PONTO_ENCOMENDA | P_UNI_ID | P_LOJA | P_DESCRICAO_TECNICA | P_TEM_STOCK | P_COD_PAUTAL | P_TEMPO_PREPARACAO | P_CRIADOR | P_ACTUALIZADOR | P_DATAACTUALIZACAO | P_TEMPO_SOLDA | P_TEMPO_MONTAGEM | P_QTDDECK_REAL | P_QTDCASCO_REAL | P_QTDDECK_REAL_TRANS | P_QTDCASCO_REAL_TRANS | P_PERC_TOPO_FR | P_PERC_TOPO_TR | P_PERC_LATERAL_FR | P_PERC_LATERAL_TR | P_PERC_QUINAS | P_PRECODEALER | P_FOLHA_ENC | P_DESCONTINUADO | P_CUSTO_CACHE | P_PL_ID | P_MODELO_COLORDESIGNER | P_DESENVOLVIMENTO | P_TP_ID_DISCIPLINA | P_PECAS_CICLO | P_CICLO_2PX | P_CICLO_TEMPO | P_CICLO_PRENSA | P_QTD_MONTAGEM | P_SET_TOPOS | P_SET_LATERAIS | P_SET_QUINAS | P_SET_CASCO | P_TEMPO_ESPERA | P_SET_GOLA | P_SET_RISCA | P_PRECO_TEMP | P_QTD_TOPOS | P_QTD_QUINAS | P_QTD_LATERAIS | P_L_ID | P_DIF_IDEAL_PA_D | P_DIF_IDEAL_PA_LX | P_DIF_IDEAL_LX_ACAB | P_MO | P_MP | P_MS | P_MERC | P_SERV | P_GGF | P_COMPRIMENTO | P_LARGURA | P_ALTURA | P_URL_IMG_PROD | P_RESINA_MIX | P_SAIDAS_AUTO | P_UNI_ID_MOVIMENTOS | P_UNI_MOV_FACTOR | P_PERC_QUINAS_TR | P_PERC_GOLA | P_STOCK_LINHA | P_QTD_RESINA | P_REF_UNIV | P_COLOR | P_3D | P_ARM_ID | P_NCORES | P_GERA_OF | P_ATRIB_ID_DESIGN | P_EAN | P_E_ID_RESP | P_E_ID_CRIADOR | P_DESCRICAO_EN | P_PESOLAM_UPD | P_PESOACAB_UPD | P_QTDDECK_REAL_UPD | P_QTDCASCO_REAL_UPD | P_PRECOVENDA_INTERNACIONAL | P_NUM_CICLOS_DIA | P_CO2 | P_PRECO_TEMP_INFLACIONADO | P_CO2_DATA_ALTERADO | P_CO2_OBSERVACOES | P_PESO_M2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20060 | K2 E (0) | NULL |  | 5.4836800000000006 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | True | 0.0 | 2006-08-08 00:00:00 | NULL | True | 2 | NULL | 84 | NULL | NULL | NULL | NULL | 0 | NULL | False | NULL | False |  | 0.0 | NULL | CRISTIANA\Guilherme | 2010-12-06 14:36:00 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | True | NULL | NULL | NULL | False | NULL | 0 | False | 0.0 | False | 0 | True | True | True | True | 0 | True | False | 0.0 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | NULL | False | 0 | NULL | 1.0 | 0.0 | 0.0 | False | 0.0 | NULL | NULL | NULL | 7 | 0 | False | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0.0 | 0 | 0.0 | 0.0 | NULL |  | 0.0 |
| 20061 | K4 G L80 | NULL |  | -15.2887025 | 0.0 | 0.0 | -73.0 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | True | 0.0 | 2019-06-18 23:44:00 | NULL | True | 3 | NULL | 84 | NULL | NULL | NULL | NULL | 0 | NULL | False | NULL | False |  | 0.0 | NULL | DESKTOP-VILF86V\luism | 2019-05-07 14:24:00 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | True | NULL | NULL | NULL | False | NULL | 0 | False | 0.0 | False | 0 | True | True | True | True | 0 | True | False | 594.91 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | NULL | False | 0 | NULL | 1.0 | 0.0 | 0.0 | False | 0.0 | NULL | NULL | NULL | 7 | 0 | False | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0.0 | 0 | 0.0 | 0.0 | NULL |  | 0.0 |
| 20062 | K4 SCS | NULL |  | 19.2297304 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | True | 0.0 | 2002-11-05 00:00:00 | NULL | True | 3 | NULL | 84 | NULL | NULL | NULL | NULL | 0 | NULL | False | NULL | False |  | 0.0 | NULL | NULL | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | False | True | NULL | NULL | NULL | False | NULL | 0 | False | 0.0 | False | 0 | True | True | True | True | 0 | True | False | 0.0 | 0.0 | 0.0 | 0.0 | NULL | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | NULL | False | 0 | NULL | 1.0 | 0.0 | 0.0 | False | 0.0 | NULL | NULL | NULL | 7 | 0 | False | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | 0.0 | 0 | 0.0 | 0.0 | NULL |  | 0.0 |

### dbo.MOVIMENTO
- linhas: **12,402,826**
- nulos por coluna (so colunas com >0% nulo):
  - MOV_DATA 0%, MOV_DATASAIDA 99%, MOV_OBSERVACOES 0%, MOV_PROBLEMA 97%, MOV_OF_ID 24%, MOV_E_ID 85%, MOV_P_ID 0%, MOV_MOV_ID 53%, MOV_ARM_ID 0%, MOV_LM_ID 100%, MOV_TR_ID 100%, MOV_PRODF_ID 100%, MOV_PL_ID 100%, MOV_LOTE 97%, MOV_ID_PEDIDO 89%, MOV_ATRIB_ID 93%, MOV_SHOP_ORDER_ID 97%, MOV_SHOP_ORDER_ITEM_ID 82%, MOV_SHOP_UPDATED_AT 100%, MOV_E_ID_RESPONSAVEL 84%, MOV_SHOP_SHIPPING 100%, MOV_SHOP_ENTITY_ID 100%, MOV_DATA_APROVADO 94%, MOV_E_ID_APROVA 99%, MOV_FP_ID 97%, MOV_OFFP_ID 100%

| MOV_ID | MOV_DATA | MOV_DATASAIDA | MOV_QUANTIDADE | MOV_PRECOUNITARIO | MOV_PRECOVENDA | MOV_DESCONTO | MOV_OBSERVACOES | MOV_PROBLEMA | MOV_NUMUTIL | MOV_OF_ID | MOV_E_ID | MOV_P_ID | MOV_TPMOV_ID | MOV_MOV_ID | MOV_ARM_ID | MOV_LM_ID | MOV_SERVER | MOV_TR_ID | MOV_PRODF_ID | MOV_PL_ID | MOV_QTD_BAL | MOV_DECK_PART | MOV_LOTE | MOV_ACERTO | MOV_ACESSORIO_ADICIONAL | MOV_DEFEITUOSO | MOV_SATISFEITO | MOV_ID_PEDIDO | MOV_ATRIB_ID | MOV_SHOP_ORDER_ID | MOV_SHOP_ORDER_ITEM_ID | MOV_SHOP_UPDATED_AT | MOV_E_ID_RESPONSAVEL | MOV_SHOP_SHIPPING | MOV_SHOP_ENTITY_ID | MOV_DATA_APROVADO | MOV_E_ID_APROVA | MOV_ENVIA_ANEXO | MOV_FP_ID | MOV_OFFP_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1155902 | 2002-01-10 00:00:00 | NULL | 1.0 | 0.0 | 0.0 | 0.0 | O.F. - 8889 | NULL | 0 | 8889 | NULL | 20083 | 2 | NULL | 1 | NULL | PROPRIET-B8D066\SQLEXPRESS | NULL | NULL | NULL | 0.0 |  | NULL | False | False | False | False | NULL | NULL | NULL | 0 | NULL | NULL | NULL | NULL | NULL | NULL | False | NULL | NULL |
| 1155903 | 2002-03-04 00:00:00 | NULL | 1.0 | 0.0 | 0.0 | 0.0 | O.F. - 8893 | NULL | 0 | 8893 | NULL | 20083 | 2 | NULL | 1 | NULL | PROPRIET-B8D066\SQLEXPRESS | NULL | NULL | NULL | 0.0 |  | NULL | False | False | False | False | NULL | NULL | NULL | 0 | NULL | NULL | NULL | NULL | NULL | NULL | False | NULL | NULL |
| 1155904 | 2001-12-31 00:00:00 | NULL | 1.0 | 0.0 | 0.0 | 0.0 | O.F. - 8895 | NULL | 0 | 8895 | NULL | 20083 | 2 | NULL | 1 | NULL | PROPRIET-B8D066\SQLEXPRESS | NULL | NULL | NULL | 0.0 |  | NULL | False | False | False | False | NULL | NULL | NULL | 0 | NULL | NULL | NULL | NULL | NULL | NULL | False | NULL | NULL |

### dbo.OF_CHECKLIST
- linhas: **2,997,803**
- nulos por coluna (so colunas com >0% nulo):
  - OFCH_FP_ID 0%, OFCH_ESTADO 68%, OFCH_OBSERVACOES 96%, OFCH_JSON_DOTS 96%, OFCH_DATA_VERIFICACAO 72%, OFCH_DATA_ACTUALIZACAO 72%, OFCH_OFFP_ID 0%, OFCH_OFFP_ID_CULPA 34%

| OFCH_ID | OFCH_DESCR | OFCH_VISTO | OFCH_RESOLVIDO | OFCH_OF_ID | OFCH_SEQUENCIA | OFCH_FP_ID | OFCH_ESTADO | OFCH_DESCR_EN | OFCH_FP_ID_CHK | OFCH_OBSERVACOES | OFCH_GRAVIDADE | OFCH_JSON_DOTS | OFCH_DATA_VERIFICACAO | OFCH_DATA_ACTUALIZACAO | OFCH_CULPA_CHEFE | OFCH_OFFP_ID | OFCH_MOLDE_REPARAR | OFCH_OFFP_ID_CULPA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1482047 | Interior | False | False | 43813 | 140 | 1 | 3 |  | 6 | NULL | 1 | NULL | 2018-01-12 09:30:00 | 2018-01-12 09:30:00 | True | 1474449 | False | NULL |
| 1482048 | Pintura | False | False | 43813 | 120 | 18 | 1 |  | 6 | NULL | 0 | NULL | 2018-01-12 09:30:00 | 2018-01-12 09:30:00 | True | 1474449 | False | NULL |
| 1482049 | Molde | False | False | 43813 | 110 | 18 | 3 |  | 6 | NULL | 1 | NULL | 2018-01-12 09:30:00 | 2018-01-12 09:30:00 | True | 1474449 | False | NULL |

### dbo.OF_FP
- linhas: **2,629,039**
- nulos por coluna (so colunas com >0% nulo):
  - OFFP_PROBLEMAS 33%, OFFP_OBSERVACOES 64%, OFFP_DATAINICIO 7%, OFFP_DATAFIM 21%, OFFP_ARM_ID 100%, OFFP_SEQUENCIA 0%, OFFP_OFFPCL_ID 100%, OFFP_PROBS_GOLA 100%, OFFP_PROBS_INTERIOR 100%, OFFP_PROBS_PINTURA 100%, OFFP_PROBS_MOLDE 100%, OFFP_PROBS_LAMINAGEM 100%, OFFP_PROBS_DATA 98%, OFFP_LINHA_AUX 100%, OFFP_OFFP_ID_RETURN 96%, OFFP_TPCAM_ID 100%, OFFP_DATA_PREVISTA 85%, OFFP_TURN_ID 97%, OFFP_OF_ID_MLD 95%, OFFP_DATA_ENTREGA 100%, OFFP_EMAIL 100%

| OFFP_ID | OFFP_OF_ID | OFFP_FP_ID | OFFP_PROBLEMAS | OFFP_OBSERVACOES | OFFP_DATAINICIO | OFFP_DATAFIM | OFFP_PESO | OFFP_NUMUTIL | OFFP_PESO_DECK_ANT | OFFP_PESO_DECK_DP | OFFP_PESO_CASCO_ANT | OFFP_PESO_CASCO_DP | OFFP_SERVER | OFFP_ARM_ID | OFFP_SEQUENCIA | OFFP_OFFPCL_ID | OFFP_HORAS_REP | OFFP_HORAS_REP_REAL | OFFP_PECAS | OFFP_CONTROLO | OFFP_TEMPERATURA | OFFP_HUMIDADE | OFFP_CONTROLO_CRIS | OFFP_EMAIL_CRIS | OFFP_PROBS_GOLA | OFFP_PROBS_INTERIOR | OFFP_PROBS_PINTURA | OFFP_PROBS_MOLDE | OFFP_PROBS_LAMINAGEM | OFFP_PROBS_DATA | OFFP_PROBS_LAM_INOCENTE | OFFP_PROBS_PINT_INOCENTE | OFFP_ORDEM | OFFP_PESO_HIST | OFFP_LINHA_AUX | OFFP_RETURN | OFFP_OFFP_ID_RETURN | OFFP_COEFICIENTE | OFFP_TPCAM_ID | OFFP_DATA_PREVISTA | OFFP_PLANEAMENTO | OFFP_TURN_ID | OFFP_OF_ID_MLD | OFFP_DATA_ENTREGA | OFFP_COEFICIENTE_X | OFFP_RETORNO_GRAVE | OFFP_EMAIL | OFFP_VALOR_FACT | OFFP_VALOR_CONTROL_1 | OFFP_VALOR_CONTROL_2 | OFFP_VALOR_CONTROL_3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 567 | 70000 | 11 | NULL | NULL | 2007-10-26 00:00:00 | 2007-10-26 00:00:00 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | PROPRIET-B8D066\SQLEXPRESS | NULL | 1900-01-08 00:00:00 | NULL | 0.0 | 0.0 | False | False | 0.0 | 0.0 | False | False | NULL | NULL | NULL | NULL | NULL | NULL | False | False | 1 |  | NULL | False | NULL | 0.0 | NULL | NULL | False | NULL | NULL | NULL | 0.0 | False | NULL | 0.0 | 0.0 | 0.0 | 0.0 |
| 568 | 70001 | 11 | NULL | NULL | 2007-11-02 00:00:00 | 2007-11-02 00:00:00 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | PROPRIET-B8D066\SQLEXPRESS | NULL | 1900-01-03 00:00:00 | NULL | 0.0 | 0.0 | False | False | 0.0 | 0.0 | False | False | NULL | NULL | NULL | NULL | NULL | NULL | False | False | 1 |  | NULL | False | NULL | 0.0 | NULL | NULL | False | NULL | NULL | NULL | 0.0 | False | NULL | 0.0 | 0.0 | 0.0 | 0.0 |
| 569 | 70002 | 11 | NULL | NULL | 2007-11-08 00:00:00 | 2007-11-08 00:00:00 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | PROPRIET-B8D066\SQLEXPRESS | NULL | 1900-01-05 00:00:00 | NULL | 0.0 | 0.0 | False | False | 0.0 | 0.0 | False | False | NULL | NULL | NULL | NULL | NULL | NULL | False | False | 1 |  | NULL | False | NULL | 0.0 | NULL | NULL | False | NULL | NULL | NULL | 0.0 | False | NULL | 0.0 | 0.0 | 0.0 | 0.0 |

### dbo.telescope_entries
- linhas: **2,471,935**
- nulos por coluna (so colunas com >0% nulo):
  - family_hash 100%

| sequence | uuid | batch_id | family_hash | should_display_on_index | type | content | created_at |
|---|---|---|---|---|---|---|---|
| 54424882 | A1C7E7DA-F2A0-453B-A7C2-A0ABBEB42F72 | A1C7E7E2-A4F5-4099-BECE-D9781C45CD20 | NULL | True | query | {"connection":"sqlsrv","driver":"sqlsrv","bindings":[],"sql":"select * from [OF_ | 2026-05-15 00:00:04 |
| 54424883 | A1C7E7DA-F97E-431A-BC37-37EEF065E680 | A1C7E7E2-A4F5-4099-BECE-D9781C45CD20 | NULL | True | model | {"action":"retrieved","model":"App\\Models\\FaseOrdemFabrico","count":133,"hostn | 2026-05-15 00:00:04 |
| 54424884 | A1C7E7DB-07FC-49E9-BDA5-5AFB32BA2BD8 | A1C7E7E2-A4F5-4099-BECE-D9781C45CD20 | NULL | True | query | {"connection":"sqlsrv","driver":"sqlsrv","bindings":[],"sql":"select top 1 * fro | 2026-05-15 00:00:04 |

### dbo.OFFP_EQ
- linhas: **1,412,103**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| OFFPEQ_OFFP_ID | OFFPEQ_E_ID | OFFPEQ_CHEFE |
|---|---|---|
| 747687 | 20350 | False |
| 749497 | 20356 | False |
| 750197 | 20345 | False |

### dbo.SensoresTesteSerieValores
- linhas: **639,548**
- nulos por coluna (so colunas com >0% nulo):
  - heading 0%, acelz 0%, medmax 100%, medmin 100%, maximos 99%, minimos 99%, med_mais_dvp 100%, med_menos_dvp 100%, roll_filtro 100%, max_roll 100%, min_roll 100%, max_heading 100%, min_heading 100%, heading_filtro 100%, max_acel 99%, tempo_rem 99%, acel_esq 99%, acel_dir 99%

| codTeste | codSerie | tempo | pitch | roll | heading | acelx | acely | acelz | medmax | medmin | maximos | minimos | med_mais_dvp | med_menos_dvp | roll_filtro | max_roll | min_roll | max_heading | min_heading | heading_filtro | max_acel | tempo_rem | acel_esq | acel_dir |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0E-8 | -0.4351357750 | 1.2068197190 | 0E-10 | 0.0611651170 | -0.2353344710 | -1.0679842230 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 1 | 2 | 0.01000000 | -0.3200571950 | 1.1983989350 | -0.0001091180 | 0.0219157510 | -0.2146335390 | -1.0730564590 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 1 | 2 | 0.02000000 | -0.1883380500 | 1.1919609690 | 0.0036664730 | -0.0303850570 | -0.1781978160 | -1.0715035200 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |

### dbo.telescope_entries_tags
- linhas: **187,907**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| entry_uuid | tag |
|---|---|
| A1C7E9EF-F948-4427-8F85-7F879E15DD86 | slow |
| A1C7E9F3-DE1C-4CE4-874B-C2C31605DE43 | slow |
| A1C7E9F7-10A1-4423-823B-7B592B5D8E94 | slow |

### dbo.ENT_MOV
- linhas: **166,327**
- nulos por coluna (so colunas com >0% nulo):
  - MOVENT_OBSERVACOES 4%, MOVENT_DATA_PAG 11%, MOVENT_ANO 100%, MOVENT_MES 100%, MOVENT_OF_ID 96%, MOVENT_E_E_ID 100%, MOVENT_FP_ID 97%

| MOVENT_ID | MOVENT_MET_ID | MOVENT_E_ID | MOVENT_DATA_I | MOVENT_DATA_F | MOVENT_OBSERVACOES | MOVENT_HORAS | MOVENT_DATA_PAG | MOVENT_VALOR_HORA | MOVENT_VALOR_PAGO | MOVENT_CC | MOVENT_PHC | MOVENT_ANO | MOVENT_MES | MOVENT_PROCESSADO | MOVENT_DESCONTA_LAMINADOR | MOVENT_OF_ID | MOVENT_VAI_PHC | MOVENT_E_E_ID | MOVENT_FP_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15357 | 7 | 20364 | 2009-06-01 08:00:00 | 2009-06-01 17:00:00 |  | 0.0 | 2010-02-05 00:00:00 | 6.93 | 0.0 | 0.0 | True | NULL | NULL | True | True | NULL | 0 | NULL | NULL |
| 15358 | 7 | 20369 | 2009-06-01 08:00:00 | 2009-06-01 17:00:00 |  | 0.0 | 2009-07-03 00:00:00 | 6.73 | 0.0 | 0.0 | True | NULL | NULL | True | True | NULL | 0 | NULL | NULL |
| 15359 | 8 | 20539 | 2009-06-01 08:00:00 | 2009-06-01 17:00:00 |  | 0.0 | 2009-07-03 00:00:00 | 2.6 | 0.0 | 0.0 | True | NULL | NULL | True | True | NULL | 0 | NULL | NULL |

### dbo.Velocidade
- linhas: **142,340**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| IDVelocidade | AtletaProvaID | Distancia | Tempo | Remadas | velocidade |
|---|---|---|---|---|---|
| 1 | 195 | 5 | 00:02.999 | 0 | 2.4 |
| 2 | 193 | 5 | 00:02.919 | 0 | 2.6 |
| 3 | 194 | 5 | 00:02.622 | 0 | 2.9 |

### dbo.OF_ATTACH
- linhas: **130,751**
- nulos por coluna (so colunas com >0% nulo):
  - ATCH_DESCRICAO 82%, ATCH_TIPO 1%, ATCH_ELIMINADO 100%, ATCH_FP_ID 96%

| ATCH_ID | ATCH_NOME | ATCH_DESCRICAO | ATCH_OF_ID | ATCH_IMAGE | ATCH_PUBLICO | ATCH_PRODUCAO | ATCH_TIPO | ATCH_ENVIADO_PROPRIETARIO | ATCH_ELIMINADO | ATCH_FP_ID | ATCH_DATA |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1868 | 11771.jpg |  | 11771 | 11771_11771.jpg | False | False | 1 | False | NULL | NULL | 2021-04-01 |
| 1869 | 11771_2.jpg |  | 11771 | 11771_11771_2.jpg | False | False | 1 | False | NULL | NULL | 2021-04-01 |
| 1870 | 15273.jpg |  | 15273 | \\server\Documents\imagens_BD\15273_15273.jpg | False | False | 1 | False | NULL | NULL | 2021-04-01 |

### dbo.PRODUTO_COMPONENTE
- linhas: **117,952**
- nulos por coluna (so colunas com >0% nulo):
  - COMP_P_ID 28%, COMP_OBS 100%, COMP_DATA_ALT 43%, COMP_FP_ID 20%, COMP_ATRIB_ID 60%, COMP_L_ID 72%, COMP_ELIMINADO 93%

| COMP_ID | COMP_P_ID | COMP_P_P_ID | COMP_QUANTIDADE | COMP_TPCOMP_ID | COMP_OBS | COMP_DATA_ALT | COMP_FASE_FINAL | COMP_CONFIGURAVEL | COMP_UNICO | COMP_VALOR_EXTRA | COMP_FP_ID | COMP_ATRIB_ID | COMP_L_ID | COMP_ELIMINADO | COMP_GESTOR_MARCA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | 21388 | 20799 | 0.171 | 2 | NULL | NULL | False | False | False | False | 6 | NULL | NULL | NULL | False |
| 4 | 21389 | 20448 | 0.4 | 2 | NULL | NULL | False | False | False | False | 1 | NULL | NULL | NULL | False |
| 5 | 21389 | 20459 | 0.4 | 2 | NULL | NULL | False | False | False | False | 1 | NULL | NULL | NULL | False |

### dbo.PEDIDOS
- linhas: **116,010**
- nulos por coluna (so colunas com >0% nulo):
  - PED_E_ID_RESPONSAVEL 67%, PED_E_ID_APROVADOR 100%, PED_DATA_APROVADO 90%, PED_EMAIL 36%, PED_CONTACTO 49%, PED_NOTAS 34%, PED_OF_ID 76%, PED_SHOP_ORDER_ID 91%, PED_PAGODATA 100%

| PED_ID | PED_DATA | PED_E_ID_RESPONSAVEL | PED_E_ID_APROVADOR | PED_DATA_APROVADO | PED_APROVADO | PED_EMAIL | PED_CONTACTO | PED_NOTAS | PED_PT | PED_E_ID | PED_OF_ID | PED_SHOP_ORDER_ID | PED_PRONTOPAGAMENTO | PED_PAGO | PED_PAGODATA | PED_PAGAR | PED_PRIORITARIO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2025-10-21 11:48:00 | 20683 | NULL | NULL | False | NUNO.VELOSO@NELO.EU | Sr. Edgar |  | True | 20213 | NULL | NULL | False | False | NULL | False | False |
| 0 | 2025-10-21 09:03:00 | 20683 | NULL | NULL | False | pedrofonseca@decatlo-compositos.com | Sr,Pedro Fonseca |  | True | 20225 | NULL | NULL | False | False | NULL | False | False |
| 0 | 2025-10-21 10:00:00 | 20683 | NULL | NULL | False | sandra.neves@plastirso.pt |  |  | True | 20304 | NULL | NULL | False | False | NULL | False | False |

### dbo.ALARM
- linhas: **110,264**
- nulos por coluna (so colunas com >0% nulo):
  - ALARM_OF_ID 9%, ALARM_P_ID 100%, ALARM_E_ID 100%, ALARM_FACT 92%, ALARM_REVISTO 100%, ALARM_E_ID_REVISOR 100%, ALARM_REVISOR_OBS 100%

| ALARM_ID | ALARM_DESCRICAO | ALARM_DATA | ALARM_DISPENSADO | ALARM_OF_ID | ALARM_P_ID | ALARM_E_ID | ALARM_TALARM_ID | ALARM_FACT | ALARM_REVISTO | ALARM_E_ID_REVISOR | ALARM_REVISOR_OBS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | *01-02-2008* | 2008-01-30 15:25:00 | True | 16765 | NULL | NULL | 2 | NULL | NULL | NULL | NULL |
| 2 | *01-02-2008* | 2008-01-30 15:25:00 | True | 16766 | NULL | NULL | 2 | NULL | NULL | NULL | NULL |
| 3 | *01-02-2008* | 2008-01-30 15:25:00 | True | 16767 | NULL | NULL | 2 | NULL | NULL | NULL | NULL |

### dbo.TRANSP_OF
- linhas: **92,902**
- nulos por coluna (so colunas com >0% nulo):
  - TROF_OBSERVACOES 100%, TROF_DATA_CONFIRMACAO 99%, TROF_CONFIRMACAO_OBS 100%

| TROF_TR_ID | TROF_OF_ID | TROF_ENVIADO | TROF_OBSERVACOES | TROF_LEVA_PECAS | TROF_DATA_CONFIRMACAO | TROF_CONFIRMACAO_OBS | TROF_DATA_CRIACAO | TROF_COMPRIMENTO | TROF_LARGURA | TROF_ALTURA |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 9465 | True | NULL | False | NULL | NULL | 2019-09-24 16:30:00 | 0.0 | 0.0 | 0.0 |
| 1 | 9466 | True | NULL | False | NULL | NULL | 2019-09-24 16:30:00 | 0.0 | 0.0 | 0.0 |
| 2 | 9501 | True | NULL | False | NULL | NULL | 2019-09-24 16:30:00 | 0.0 | 0.0 | 0.0 |

### dbo.TRANSP_VAL
- linhas: **76,054**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| TRVAL_VAL_ID | TRVAL_TR_ID | TRVAL_VALOR |
|---|---|---|
| 2 | 1 | 0.0 |
| 2 | 2 | 0.0 |
| 2 | 3 | 0.0 |

### dbo.OFCH_LOCAL
- linhas: **58,189**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| OFPROBS_OFCH_ID | OFPROBS_PROBSL_ID |
|---|---|
| 1670295 | 6 |
| 1670296 | 7 |
| 1670297 | 7 |

### dbo.TRANSP_DOCS
- linhas: **46,797**
- nulos por coluna (so colunas com >0% nulo):
  - TRDOC_DOC_CAMINHO 100%, TRDOC_DATA 36%

| TRDOC_DOCS_ID | TRDOC_TR_ID | TRDOC_DOCS_NOME | TRDOC_DOC_CAMINHO | TRDOC_TRATADO | TRDOC_OBSERVACOES | TRDOC_DOCNUM | TRDOC_DATA |
|---|---|---|---|---|---|---|---|
| 6 | 1 | Factura nossa | NULL | False |  |  | NULL |
| 6 | 2129 | Factura | NULL | True |  | 29005806 | 2009-01-08 00:00:00 |
| 6 | 2130 | Factura | NULL | True |  | 29005807 | 2009-01-09 00:00:00 |

### dbo.PRODUTO_FASE
- linhas: **42,829**
- nulos por coluna (so colunas com >0% nulo):
  - PRODF_P_ID 0%, PRODF_FP_ID 5%, PRODF_DESCRICAO 84%, PRODF_ACTUALIZADOR 84%, PRODF_DATAACTUALIZACAO 94%, PRODF_PRODF_ID 95%, PRODF_DATA_ELIMINADO 94%, PRODF_TPCAM_ID 100%

| PRODF_ID | PRODF_P_ID | PRODF_FP_ID | PRODF_DESCRICAO | PRODF_SEQUENCIA | PRODF_TEMPO | PRODF_DATA | PRODF_CRIADOR | PRODF_ACTUALIZADOR | PRODF_DATAACTUALIZACAO | PRODF_PRODF_ID | PRODF_DATA_ELIMINADO | PRODF_STOCK | PRODF_AUTOMATICA | PRODF_FABRICO | PRODF_COEFICIENTE | PRODF_TPCAM_ID | PRODF_PLANEAMENTO | PRODF_COEFICIENTE_X |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12063 | 20982 | NULL | 1 - Limpeza dos moldes.  | 1 | 0.0 | 2009-09-28 13:35:00 | CRISTIANA\Guilherme | CRISTIANA\Guilherme | 2009-10-17 00:36:00 | 13122 | NULL | 0.0 | False | True | 0.0 | NULL | False | 0.0 |
| 12064 | 20982 | NULL | 1 – Utilizar uma espátula flexível para limpar todos os resíduos de resina de to | 2 | 0.0 | 2009-09-28 13:59:00 | CRISTIANA\Guilherme | CRISTIANA\Guilherme | 2009-09-28 14:06:00 | 12063 | 2009-10-17 00:40:00 | 0.0 | False | True | 0.0 | NULL | False | 0.0 |
| 12065 | 20982 | 2 |  | 82 | 0.0 | 2009-09-28 13:59:00 | CRISTIANA\Guilherme |  | NULL | NULL | 2009-10-17 00:36:00 | 0.0 | False | True | 0.0 | NULL | False | 0.0 |

### dbo.TransportePercursoHistorico
- linhas: **40,484**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| codEncomendaPercursoHistorico | codEncomenda | data |
|---|---|---|
| 1 | 15177 | 2017-10-24 10:39:36.240000 |
| 2 | 15177 | 2017-10-24 10:55:34.500000 |
| 3 | 15177 | 2017-10-24 10:57:03.227000 |

### dbo.TransporteLocalizacao
- linhas: **39,122**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| codEncomendaLocalizacao | codEncomenda | dataEstado | latitude | longitude | codEncomendaPercurso | ultUpdate |
|---|---|---|---|---|---|---|
| 1 | 15132 | 2017-10-26 11:44:52.487000 | 41.192158862 | -8.685053228 | 32 | 2017-11-03 04:20:31.720000 |
| 3 | 15177 | 2017-10-26 12:38:57.070000 | 37.655338300 | 6.721782210 | 29 | 2017-10-26 12:38:57.070000 |
| 4 | 15177 | 2017-10-26 13:06:39.817000 | 37.663370000 | 6.937423000 | 29 | 2017-10-26 13:06:39.817000 |

### dbo.logs_web
- linhas: **30,105**
- nulos por coluna (so colunas com >0% nulo):
  - descricao 100%, data 100%

| codLog | codLogin | accao | descricao | IP | data |
|---|---|---|---|---|---|
| 1 | 20994 | Logoff | NULL | 192.168.0.105 | NULL |
| 2 | 20994 | Login form | NULL | 192.168.0.105 | NULL |
| 3 | 20994 | Login form | NULL | 192.168.0.105 | NULL |

### dbo.TransportePercursoHistoricoDetalhe
- linhas: **27,152**
- nulos por coluna (so colunas com >0% nulo):
  - descricaoMov 0%, localizacao 9%, latitude 10%, longitude 10%, transportador 12%, numViagem 16%, hora 91%

| codEncomendaPercursoHistoricoDetalhe | codEncomendaPercursoHistorico | codEncomendaPercurso | codEncomenda | descricaoMov | localizacao | latitude | longitude | transportador | barco | numViagem | data | hora | efetivo | atual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 7 | 31 | 15132 | Empty to Shipper | LEIXOES, 13, PT | 41.192158862 | -8.685053228 | NULL | False | NULL | 20171025 | 235959 | True | False |
| 2 | 7 | 32 | 15132 | Gate In Full | LEIXOES, 13, PT | 41.192158862 | -8.685053228 | NULL | False | NULL | 20171026 | 235959 | True | True |
| 3 | 8 | 33 | 15132 | Empty to Shipper | LEIXOES, 13, PT | 41.192158862 | -8.685053228 | NULL | False | NULL | 20171025 | 235959 | True | False |

### dbo.PRODUTO_OPCOES
- linhas: **26,292**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| POP_P_ID | POP_P_P_ID | POP_CORES | POP_TOPOS | POP_LATERAIS | POP_QUINAS | POP_CASCO | POP_GOLA | POP_RISCA | POP_EXTRA | POP_CUSTO_EXTRA_OF |
|---|---|---|---|---|---|---|---|---|---|---|
| 20155 | 20560 | False | False | False | False | False | False | False | True | True |
| 20155 | 20577 | True | True | True | True | True | True | False | True | False |
| 20155 | 20578 | True | True | True | True | True | True | False | True | False |

### dbo.SGIDI_FICHEIRO
- linhas: **25,869**
- nulos por coluna (so colunas com >0% nulo):
  - SGIDIF_DESCR 0%, SGIDIF_DATA_ELIMINADO 92%, SGIDIF_ACTUALIZADOR 93%, SGIDIF_SGIDIP_ID 0%, SGIDIF_SGIDIF_ID 100%, SGIDIF_PROCAF_ID 100%, SGIDIF_SGIDIFXCL_ID_TIPO 100%, SGIDIF_SGIDIFXCL_ID_TEMPO 100%, SGIDIF_SGIDIFXCL_ID_METODO 100%, SGIDIF_SGIDIFXCL_ID_REVISAO 100%, SGIDIF_E_ID 47%

| SGIDIF_ID | SGIDIF_NOME | SGIDIF_DESCR | SGIDIF_TIPO | SGIDIF_DATA | SGIDIF_CRIADOR | SGIDIF_DATA_ELIMINADO | SGIDIF_ACTUALIZADOR | SGIDIF_SGIDIP_ID | SGIDIF_SGIDIF_ID | SGIDIF_CAMINHO | SGIDIF_PROCAF_ID | SGIDIF_PUBLICO | SGIDIF_SGIDIFXCL_ID_TIPO | SGIDIF_SGIDIFXCL_ID_TEMPO | SGIDIF_SGIDIFXCL_ID_METODO | SGIDIF_SGIDIFXCL_ID_REVISAO | SGIDIF_E_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | BarcosCinfaes 1 |  | .xls | 2010-07-16 14:38:00 | 20597 | 2010-07-16 14:42:00 | 20597 | 26 | NULL | \\server\Documents\imagens_BD\SGIDI_Docs\12.xls | NULL | False | 6 | 8 | 15 | 17 | NULL |
| 13 | BarcosCinfaes 2 |  | .xls | 2010-07-16 14:39:00 | 20597 | 2010-07-16 14:42:00 | 20597 | 26 | NULL | \\server\Documents\imagens_BD\SGIDI_Docs\13.xls | NULL | False | 6 | 8 | 15 | 17 | NULL |
| 14 | Capas |  | .xls | 2010-07-16 14:47:00 | 20597 | NULL | 30253 | 29 | NULL | \\server\Documents\imagens_BD\SGIDI_Docs\14.xls | NULL | True | 7 | 8 | 15 | 17 | NULL |

### dbo.ENT_TP_PROD
- linhas: **22,832**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| ETP_E_ID | ETP_TP_ID | ETP_OBJ_OF | ETP_OBJ_VAL | ETP_BRAND_MANAGER |
|---|---|---|---|---|
| 19586 | 149 | 0 | 0.0 | False |
| 19586 | 151 | 0 | 0.0 | False |
| 19586 | 153 | 0 | 0.0 | False |

### dbo.Trackimo_Access
- linhas: **20,313**
- nulos por coluna (so colunas com >0% nulo):
  - _(nenhuma)_

| codLog | date | access_token | refresh_token | account_id |
|---|---|---|---|---|
| 1 | 2017-10-24 17:06:54.720000 | c4a03022-58e8-4495-8b5b-ee28d772dc2d | 9cc23aa5-f9db-4449-a90d-e0dc30e72c52 | 48481 |
| 2 | 2017-10-25 10:23:04.160000 | c4a03022-58e8-4495-8b5b-ee28d772dc2d | 9cc23aa5-f9db-4449-a90d-e0dc30e72c52 | 48481 |
| 3 | 2017-10-25 15:08:04.727000 | c4a03022-58e8-4495-8b5b-ee28d772dc2d | 9cc23aa5-f9db-4449-a90d-e0dc30e72c52 | 48481 |

