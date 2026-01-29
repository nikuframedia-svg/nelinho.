# Data Contracts — Factory Data Product

**Versão:** 1.0.0  
**Gerado:** 2026-01-27

---

## 1. Visão Geral

Este documento define os contratos de dados para o Factory Data Product. Todos os dados que entram ou saem do sistema devem cumprir estes contratos.

### 1.1 Princípios

1. **Semântica Explícita**: Todo campo tem significado documentado
2. **Tipagem Forte**: Validação em runtime via Pydantic
3. **Versionamento**: Contratos versionados com compatibilidade N/N-1
4. **Explicabilidade**: Todo valor calculado tem explicação

### 1.2 Ficheiros

| Ficheiro | Descrição |
|----------|-----------|
| `/contracts/raw_v1.0.0.json` | JSON Schema para camada RAW |
| `/contracts/api_v1.0.0.json` | JSON Schema para API responses |
| `/factory_data_product/contracts/ontology.py` | Ontologia base |
| `/factory_data_product/contracts/raw.py` | Contratos RAW (Pydantic) |
| `/factory_data_product/contracts/curated.py` | Contratos CURATED |
| `/factory_data_product/contracts/semantic.py` | Contratos SEMANTIC |
| `/factory_data_product/contracts/api.py` | Contratos API |
| `/factory_data_product/contracts/validators.py` | Validadores |

---

## 2. Ontologia

### 2.1 Entity IDs

**REGRA DURA**: IDs são sempre `string`, NUNCA `float`.

```python
# ERRADO
of_id = 12345.0  # Float com .0

# CORRECTO
of_id = "12345"  # String
```

**Validação**: IDs que terminam em `.0` são rejeitados ou convertidos.

### 2.2 Timestamps

**REGRA DURA**: Timestamps devem ter timezone. Naive timestamps são convertidos para UTC.

```python
from datetime import datetime, timezone

# ERRADO
dt = datetime(2026, 1, 27, 10, 30)  # Naive

# CORRECTO
dt = datetime(2026, 1, 27, 10, 30, tzinfo=timezone.utc)
```

**Formato**: ISO 8601 com timezone (`2026-01-27T10:30:00+00:00`)

### 2.3 Unidades

**REGRA**: Valores numéricos devem ter unidade explícita.

| Unidade | Código | Exemplo |
|---------|--------|---------|
| Horas | `hours` | `{"value": 8.5, "unit": "hours"}` |
| Minutos | `minutes` | `{"value": 510, "unit": "minutes"}` |
| Euros | `EUR` | `{"value": 15.50, "unit": "EUR"}` |
| Percentagem | `pct` | `{"value": 85.2, "unit": "pct"}` |
| Peças | `pcs` | `{"value": 100, "unit": "pcs"}` |
| Dias | `days` | `{"value": 5.5, "unit": "days"}` |

### 2.4 Semantic Nulls

**CONCEITO**: Em alguns campos, `0` não significa "zero" mas sim "desconhecido/não aplicável".

| Campo | Significado de 0 | Tratar como NULL |
|-------|------------------|------------------|
| `fase_of_horas_previstas` | não planeado/desconhecido | SIM (excepto fases administrativas) |
| `produto_fase_horas_previstas` | fase não existe para produto | SIM |
| `funcionario_valor_hora` | valor não definido | SIM (inválido para custos) |
| `fase_capacidade_horas_dia` | fase sem capacidade | SIM (excepto administrativas) |

**Excepções**: Fases administrativas (Armazém, Entregue, Expedição) podem ter valores 0 legítimos.

```python
from factory_data_product.contracts.ontology import SemanticNull

# Verificar se é semantic null
value = SemanticNull.process("fase_of_horas_previstas", 0, fase_nome="Laminagem")
# Retorna: None (porque 0 é semantic null para Laminagem)

value = SemanticNull.process("fase_of_horas_previstas", 0, fase_nome="Armazém")
# Retorna: 0 (porque Armazém é excepção)
```

---

## 3. Contratos por Fronteira

### 3.1 Excel → RAW

**Propósito**: Preservar dados originais do Excel com validação mínima.

#### RawOrdemFabrico

```python
class RawOrdemFabrico(ContractBase):
    of_id: str                           # OBRIGATÓRIO
    of_data_criacao: Optional[datetime]
    of_data_acabamento: Optional[datetime]  # NULL = aberta
    of_data_transporte: Optional[datetime]
    of_produto_id: Optional[str]
    of_fase_id: Optional[str]
    of_estado: Optional[str]
```

#### RawFaseOrdemFabrico

```python
class RawFaseOrdemFabrico(ContractBase):
    fase_of_id: str                      # OBRIGATÓRIO
    fase_of_of_id: str                   # OBRIGATÓRIO (FK)
    fase_of_inicio: Optional[datetime]
    fase_of_fim: Optional[datetime]
    fase_of_data_prevista: Optional[datetime]  # Só 4.8% preenchido
    fase_of_horas_previstas: Optional[float]   # CRÍTICO: 56.6% zeros
    # ... mais campos
```

### 3.2 RAW → CURATED

**Propósito**: Aplicar transformações, semantic nulls, e campos derivados.

#### Campos Derivados Principais

| Campo | Derivação | Fonte |
|-------|-----------|-------|
| `horas_previstas_final` | `fase_of_horas_previstas > 0 ? fase : standard` | Fase ou Standard |
| `horas_previstas_source` | `'fase'` ou `'standard'` | Lógica de derivação |
| `is_phase_open` | `fase_of_fim IS NULL` | Calculado |
| `duration_hours` | `(fim - inicio).total_hours()` | Calculado |
| `is_event_marker` | `duration_hours == 0` | Calculado |
| `lead_time_days` | `(acabamento - criacao).days` | Calculado |

#### Lógica de HorasPrevistas_Final

```sql
-- SQL equivalente
CASE
    WHEN fase_of_horas_previstas > 0 THEN fase_of_horas_previstas
    WHEN standard_horas > 0 THEN standard_horas
    ELSE NULL
END
```

### 3.3 CURATED → SEMANTIC

**Propósito**: Views de negócio com explicabilidade.

| View | Descrição | Trust Index |
|------|-----------|-------------|
| WIP | Work In Progress | 80 |
| Backlog | Carga por fase | 58 |
| Bottlenecks | Gargalos prováveis | 58 |
| Quality | Análise de erros | 67 |
| MoldConflicts | Conflitos de molde | 35 |
| SkillsRisk | Risco de competências | 55 |

### 3.4 API Responses

**REGRA**: Todas as respostas incluem `ExplainableValue`.

#### ExplainableValue

```python
class ExplainableValue(BaseModel):
    value: Any                    # Valor calculado
    unit: Optional[Unit]          # Unidade
    explain: str                  # Explicação (OBRIGATÓRIO)
    formula: Optional[str]        # Fórmula usada
    qualifier: Qualifier          # real/theoretical/estimated/blocked
    trust_index: int              # 0-100 (OBRIGATÓRIO)
    citations: List[Citation]     # Fontes dos dados
    warnings: List[str]           # Avisos
    limitations: List[str]        # Limitações
    blocked: bool                 # True se cálculo bloqueado
    blocked_reason: Optional[str] # Razão do bloqueio
```

#### Exemplo de Resposta

```json
{
  "kpi_name": "Backlog Hours",
  "kpi_id": "backlog_hours",
  "value": {
    "value": 1250.5,
    "unit": "hours",
    "explain": "Soma de horas previstas de fases abertas",
    "formula": "SUM(horas_previstas_final) WHERE is_phase_open",
    "qualifier": "theoretical",
    "trust_index": 58,
    "warnings": ["56.6% das horas imputadas por standard"],
    "limitations": ["Não considera multitarefa", "Capacidade é teórica"]
  },
  "status": "available",
  "trust_check_passed": true
}
```

---

## 4. Validação

### 4.1 Schema Validation

```python
from factory_data_product.contracts.validators import SchemaValidator
from factory_data_product.contracts.raw import RawOrdemFabrico

data = {"of_id": "12345", "of_data_criacao": "2026-01-27T10:00:00Z"}
obj, result = SchemaValidator.validate(data, RawOrdemFabrico)

if result.is_valid:
    print(f"Válido: {obj}")
else:
    print(f"Erros: {result.errors}")
```

### 4.2 Constraint Validation

```python
from factory_data_product.contracts.validators import ConstraintValidator

result = ValidationResult(is_valid=True, contract_version="1.0.0")

# Validar range
ConstraintValidator.validate_range("funcionario_valor_hora", 500, result)

# Validar volumetria
ConstraintValidator.validate_volumetry("ordens_fabrico", 28000, result)

# Validar FK lógica
ConstraintValidator.validate_fk_logical(
    child_ids=["1", "2", "3"],
    parent_ids={"1", "2"},  # "3" é órfão
    child_field="fase_of_of_id",
    parent_field="of_id",
    result=result
)
```

### 4.3 Trust Validation

```python
from factory_data_product.contracts.validators import TrustValidator

# Verificar se segmento tem trust suficiente
passed, blocked = TrustValidator.check_trust(
    segment="fases_ordem_fabrico_horas",
    minimum_required=60
)

if not passed:
    print(f"Bloqueado: {blocked.message}")
```

### 4.4 Ingestão Completa

```python
from factory_data_product.contracts.validators import validate_raw_data

data = {
    "ordens_fabrico": [...],
    "fases_ordem_fabrico": [...],
    # ...
}

result = validate_raw_data(data)

if result.is_valid:
    print("Dados válidos para ingestão")
else:
    print(f"{len(result.errors)} erros encontrados")
    for error in result.errors[:5]:
        print(f"  - {error.field}: {error.message}")
```

---

## 5. Respostas de Erro (422)

**REGRA**: Qualquer payload inválido gera HTTP 422 com detalhes.

### 5.1 Estrutura do Erro

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed: 2 error(s)",
  "details": [
    {
      "field": "of_id",
      "message": "field required",
      "code": "PYDANTIC_MISSING"
    },
    {
      "field": "of_data_criacao",
      "message": "invalid datetime format",
      "code": "PYDANTIC_DATETIME_PARSING"
    }
  ],
  "contract_version": "1.0.0",
  "timestamp": "2026-01-27T10:30:00Z"
}
```

### 5.2 Códigos de Erro

| Código | Descrição |
|--------|-----------|
| `VALIDATION_ERROR` | Erro de validação de schema |
| `CONTRACT_VIOLATION` | Violação de contrato |
| `INSUFFICIENT_DATA` | Dados insuficientes para cálculo |
| `TRUST_TOO_LOW` | Trust Index abaixo do mínimo |
| `CALCULATION_BLOCKED` | Cálculo bloqueado por regras |

---

## 6. Versionamento

### 6.1 Formato

```
MAJOR.MINOR.PATCH

MAJOR: Breaking changes (incompatível)
MINOR: Novos campos opcionais (compatível)
PATCH: Bug fixes (compatível)
```

### 6.2 Compatibilidade

**REGRA**: N/N-1 compatibility (2 releases).

- Versão 1.0.0 é compatível com 1.1.0
- Versão 1.0.0 **NÃO** é compatível com 2.0.0
- Breaking changes requerem migration

### 6.3 Migration

Para breaking changes:

1. Criar nova versão do schema
2. Manter versão anterior por 2 releases
3. Documentar breaking changes
4. Providenciar migration script

---

## 7. Trust Index por Segmento

| Segmento | Score | Justificação |
|----------|-------|--------------|
| `erros_catalogo` | 92 | Semântica estável |
| `fases_dimensao` | 85 | Estrutura sólida |
| `ordens_fabrico` | 82 | Boa base para WIP |
| `funcionarios_dimensao` | 75 | ValorHora com zeros |
| `moldes_dimensao` | 70 | Estados sem dicionário |
| `qualidade_transacional` | 67 | 41.5% sem fase culpada |
| `fases_ordem_fabrico_tempos` | 62 | Muitas durações 0 |
| `standards_produto_fase` | 60 | Duplicados por chave |
| `fases_ordem_fabrico_horas` | 58 | 56.6% zeros |
| `funcionarios_fase_ponte` | 55 | Não dá horas reais |
| `fases_ordem_fabrico_data_prevista` | 35 | Só 4.8% preenchido |

---

## 8. KPIs e Bloqueios

### 8.1 KPIs Bloqueados

| KPI | Estado | Razão |
|-----|--------|-------|
| OEE | **NÃO USÁVEL** | Availability incorrecta, sem dados de máquina |
| OTD | **NÃO USÁVEL** | Não existe due_date |
| Produtividade Individual | **NÃO USÁVEL** | Não há horas reais por funcionário |

### 8.2 Regra de Bloqueio

**REGRA DURA**: Nenhum serviço calcula KPI se dados insuficientes.

```python
from factory_data_product.contracts.api import KPIResponse

# KPI bloqueado por dados insuficientes
response = KPIResponse.not_usable(
    kpi_name="OEE",
    kpi_id="oee",
    reason="Availability definition is incorrect. OEE requires machine downtime data.",
    trust_index=0
)

print(response.status)  # "not_applicable"
print(response.value.blocked)  # True
```

---

## 9. Uso no Código

### 9.1 Validar Dados de Ingestão

```python
from factory_data_product.contracts import validate_raw_data

result = validate_raw_data(excel_data)
if not result.is_valid:
    raise ValidationError(result.errors)
```

### 9.2 Criar Resposta de KPI

```python
from factory_data_product.contracts import KPIResponse, ExplainableValue

kpi = KPIResponse(
    kpi_name="WIP Orders",
    kpi_id="wip_orders",
    value=ExplainableValue.theoretical(
        value=150,
        explain="Ordens abertas (data_acabamento IS NULL)",
        trust_index=82,
        unit=Unit.PIECES
    )
)
```

### 9.3 Verificar Trust Antes de Cálculo

```python
from factory_data_product.contracts import validate_for_kpi, BlockedResponse

passed, blocked = validate_for_kpi(
    kpi_id="backlog_hours",
    segments=["fases_ordem_fabrico_horas", "standards_produto_fase"]
)

if not passed:
    return blocked  # Retorna BlockedResponse
```

---

**FIM DO DOCUMENTO DE DATA CONTRACTS**


