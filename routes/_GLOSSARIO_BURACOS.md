# Glossário de vocabulário — Q.78 / SubB2.3

> **Estado:** 2026-05-24 — campanha LLM→SQL accuracy chegou ao **vocabulário
> fechado sem dependência do analista NELO**. Os 2 buracos residuais da SubB2.2
> (filtro de Reservas + nomes de 4 unidades) foram resolvidos por investigação
> contra dados na SubB2.3 (sem reunião humana).

---

## 1. Vocabulário CONFIRMADO (documentado no ERP)

### MOVIMENTO_TIPO (15 valores — fonte: tabela `MOVIMENTO_TIPO`)

```
TPMOV_ID  TPMOV_NOME
       1  Entrada                                  ← 1× por OF terminada
       2  Saida                                    ← stockagem, NÃO consumo de OF
   ★  4  Reserva                                   ← PLANEAMENTO, não consumo (ver §3)
       5  Reparação
       6  Notas
       7  Entrada "Em produção"
       8  Saida "Em produção"
       9  Pedidos a fornecedor
      10  Saida de armazem para produção
   ★ 11  Saída como componente (não conta para stock)  ← CONSUMO DE OF
      12  Pedidos internos                         ← stockagem
      13  Saída como componente substituto temporariamente
      14  xx
      15  Planeamento de peças
      16  Planeamento de peças: Entradas
```

**TPMOV=11 é o filtro canónico de consumo de produção** (CONFIRMADO §3).

### PRODUTO_CONTABILIDADE_TIPO (10 valores)

```
PCONT_ID  PCONT_NOME              n_produtos (espelho)
   ★ 1  Matéria Prima            5.913       ← filtro canónico de matéria-prima
       2  Matéria Subsidiária        460     ← consumíveis 3M (lixas/fitas/ceras)
       3  Serviços                   304
       4  Mão de Obra                 35
       5  Mercadorias                826
       6  Produto Acabado              0
       7  Equipamento Segurança      110
       8  Outros                       0
       9  Produto Intermédio       2.624
      10  G.G. Fabrico                 1
```

### **UNIDADE (22 valores — fonte autoritária descoberta SubB2.3)**

Tabela `UNIDADE` no ERP NELO, descoberta procurando `sys.tables LIKE '%UNI%'`.
**Vocabulário completo das unidades, sem inferência:**

```
UNI_ID  UNI_NOME    UI label (PT humanizado)
     1  Mts         metros
     2  Mts²        m²
     3  Placa       placas
     4  Chapa       chapas
     5  Conjunto    conjunto
     6  Euro        €
     7  Kg          kg
     8  Gr          gr             ← descoberto SubB2.3 (não estava antes)
     9  Lata        lata           ← descoberto SubB2.3
    10  Ltr         litros
    11  Par         pares
    12  Unid        unidades
    13  Tubo        tubos
    14  Hora        horas
    15  Mts³        m³             ← descoberto SubB2.3
    16  Rolo        rolos          ← confirmado (era hipótese Q.78)
    17  Caixa       caixa          ← confirmado (era hipótese Q.78)
    18  Bidão       bidão          ← Q.78 hipótese era "tambor" — semântica idêntica
    19  Saco        sacos          ← descoberto SubB2.3
    20  Bobine      bobines        ← descoberto SubB2.3
    21  Cone        cones          ← descoberto SubB2.3
    22  KWh         kWh            ← confirmado (era hipótese Q.78)
```

**Inferências Q.78 validadas:** 16=rolos ✓, 17=caixa ✓, 22=kWh ✓, 18=tambor
≈ bidão (semântica idêntica), 5=pack ≈ conjunto (semântica idêntica).

A tabela `UNIDADE` **NÃO está espelhada** em `factory_raw` — adicionar
no próximo sprint de espelhamento (ver §5).

### OFFP_GRAVIDADE (5 valores + flag PARAR)

Documentado no ERP; não usado nas rotas SubB2.3 (relevante para futuro domínio
qualidade).

### Outras lookup tables descobertas

`PRODUTO_ESTADO` (7), `MOLDES_TIPO` (14), `IOT_SENSOR_TIPO` (7), `ALARM_TIPO`
(6), `ENT_MOV_TIPO` (15), `ENCOMENDA_ESTADO` (3), `PRODUTO_CAMADA_TIPO` (12),
`COMPONENTE_TIPO` (4), `OF_TIPOUSO` (3). Inventário completo em
`agent_docs/q78_views_catalogo.md` §2.

### FASES_PRODUCAO (71 valores — Q.79)

Vocabulário CENTRAL do domínio produção. Lista completa em
`agent_docs/q79_producao_catalogo.md` §3. Fluxo fabricar kayak:

```
seq 0-9:   Pendente / CAD / CAM / Preparação CNC / CNC / Preparação Molde / Pintura
seq 10:    Laminagem (+ peças/Infusão/Double Dutch)
seq 11:    Cura
seq 12:    Desmolde
seq 13:    Corte (+ peças)
seq 14:    Colagem Barcos / Colagem Peças
seq 15-29: Colagem Golas / Pintura Acabamento / Lixagem / Acabamento 1-3 / QA
─────────── fronteira ────  seq >= 30 = pós-produção ───
seq 30:    Armazem
seq 36:    Embalado
seq 37:    Entregue
seq 38-50: Reparações / Em Uso / Para Abate / Lixo / Abatido / Manutenção / outros
```

**`ORDEMFABRICO.OF_FP_ID` é a fase actual da OF** (estado oficial NELO,
CONFIRMADO Q.79). 370K das 443K OFs estão em fase 12 (Entregue) — explica
porque `OF_DATAFIM IS NULL` falhava como critério de "OF activa": a NELO não
fecha OF_DATAFIM mesmo após entrega.

### OF_TIPOUSO (3 valores — Q.78)

`ORDEMFABRICO.OF_OFTU_ID` → OF_TIPOUSO:
- 1 = 2ª Escolha (defeito menor, vendido com desconto)
- 2 = Teste/Stock
- 59 = Cedidos a atletas/eventos

**LIMITAÇÃO factory_raw**: 99.996% NULL no espelho. Só 4 OFs preenchidas.

---

## 2. Factor de conversão `P_UNI_MOV_FACTOR`

98.5% têm `=1`. 1.5% têm conversão real (ex.: Resina Lavesan factor=0.00417 →
1 movimento = 1/240 da unidade base, sugerindo bidão de 240kg).

**Aplicar sempre** `MOV_QUANTIDADE * COALESCE(P_UNI_MOV_FACTOR, 1)`.

---

## 3. Filtro canónico de "consumo de produção" — RESOLVIDO SubB2.3

### Critério: `MOV_TPMOV_ID = 11` (estrito, sem Reservas)

**Evidência acumulada:**

| Fonte | Resultado |
|---|---|
| 4 OFs terminadas Abril 2026 (amostra) | Cada uma 10-20 movs `TPMOV=11` + 1× `TPMOV=1` |
| Movs com `MOV_OF_ID NOT NULL` | **55.6% têm `TPMOV=11`** (dominante) |
| Movs sem OF_ID | TPMOV=2/12 dominam → confirma `IN(2,12)` = stockagem |

### Reservas (TPMOV=4) NÃO incluídas — porquê (SubB2.3)

Investigação contra dados resolveu sem analista:

1. **Distribuição por estado da OF (Abril 2026):**
   - **25.170 reservas em OFs em curso** (planeamento futuro)
   - **1.933 em OFs terminadas** (residuais, ratio 13:1)
2. **Sequência temporal**: 10/10 amostras mostram **Reserva → Componente com
   1-3 meses entre as duas**. Fluxo: planear → consumir.
3. **Pares (OF, Produto) em OFs terminadas:**
   - 95.9% têm só Componente (sem Reserva)
   - 0.4% têm ambos
   - 3.6% têm só Reserva (órfãs — não chegaram a consumo)
4. **Impacto no ranking se incluir**:
   - "Pintura (MIX)" entra no top com 1.170 kg só com reservas (zero consumo
     real em Abril) — distorção clara.
   - Mistura Epoxy Lavesan: 1.371 → 1.969 (+43%, inclui reservas para Maio+).

**Conclusão**: `MOV_TPMOV_ID = 11` mede consumo realizado. Para perguntas
"quanto está RESERVADO para próximos meses", criar rota separada com
TPMOV=4 (não fizemos ainda, futuro se necessário).

---

## 4. Histórico de hipóteses (trail forense)

### Filtro de consumo
- **SubB1 (intuição)**: `TPMOV=11` ✓
- **SubB2.1 (errado)**: `IN(2,12)` da `vMovsPowerHouseNotShop` — refutada Q.78
- **SubB2.2 (reversão)**: `TPMOV=11` como HIPÓTESE FORTE
- **SubB2.3 (FECHADO)**: `TPMOV=11` CONFIRMADO; Reservas resolvidas por análise
  contra dados, sem analista.

### Classificação de matéria-prima
- **SubB1 (errado)**: `P_TP_ID <> 90`
- **SubB2.1 (correcto)**: `P_PCONT_ID = 1` (CONFIRMADO via ERP)

### Unidades de medida
- **SubB2 (parcial)**: 11 inferidas via cruzamento P_MEDIDA
- **Q.78 SubB3-prep (hipóteses)**: +5 inferidas (16, 17, 18, 5, 22)
- **SubB2.3 (FECHADO)**: 22 unidades oficiais da tabela `UNIDADE` do ERP
  (validou as 5 hipóteses Q.78 + revelou 6 novas: Gr, Lata, Mts³, Saco,
  Bobine, Cone).

---

## 5. Buracos de espelhamento Q.75 (próximo sprint)

Tabelas-lookup descobertas durante a campanha mas **não espelhadas** em
`factory_raw`. Próximo sprint de espelhamento (Q.79?) considerar:

- `UNIDADE` (22) ← **nova prioridade** (SubB2.3) — permite remover hardcode
  dos nomes em `units.py` e ler directo
- `MOVIMENTO_TIPO` (15) ← permite remover hardcode `tpmov_consumo: 11`
- `PRODUTO_CONTABILIDADE_TIPO` (10) ← idem para `pcont_materia_prima: 1`
- `OFFP_GRAVIDADE` (5), `PRODUTO_ESTADO` (7), `MOLDES_TIPO` (14)
- `IOT_SENSOR_TIPO` (7), `ALARM_TIPO` (6), `ENT_MOV_TIPO` (15)
- `ENCOMENDA_ESTADO` (3), `PRODUTO_CAMADA_TIPO` (12), `COMPONENTE_TIPO` (4)
- `OF_TIPOUSO` (3), `CENTRO_RESERVA_ESTADO` (4)

Total: **14 tabelas ~140 rows**. Mirror trivial.

---

## 6. Estado pós-SubB2.3

**Buracos residuais para o analista NELO**: **ZERO** sobre o domínio
"materiais". A campanha fechou todas as hipóteses por investigação contra
dados. A sessão de analista que estava prevista (10 min) não é mais necessária.

**Próximo domínio (produção)**: usar critério `OF activa = OF_DATAFIM NULL AND
EXISTS(fase aberta)` já descoberto na Q.78 §5 — também sem dependência humana.

---

*Documento mantido pela campanha LLM→SQL accuracy. Trail forense em
`agent_docs/q78_views_catalogo.md` (SubB3-prep) e
`agent_docs/q78_investigacao_buracos.md` (SubB3-investigação).*
