# Níveis de operadores NELO (escala 1–3, 1 é o melhor)

Documento de referência para o Copilot Nelinho responder a perguntas sobre o
nível de cada operador e que barcos lhe podem ser atribuídos. Pré-ingerido em
RAG via `POST /api/copilot/rag/ingest` com `source_type=operator_levels`.

## Como o nível é calculado

O nível **global** de um operador é **derivado automaticamente** do quality
score Laplace que o sistema já calcula em
`src/workforce/employee_extras_service.py` a partir do histórico de
operações + retrabalhos. Fórmula:

```
defects + α      onde α = 1.0 (Laplace prior)
─────────────
operations + β   onde β = 10.0 (prior weight)
```

O score resultante está em `[1.0, 10.0]` e é bucketizado:

| Quality score | Nível derivado | Etiqueta       |
|---------------|----------------|----------------|
| ≥ 8.0         | **1**          | Top            |
| 5.0 – 7.9     | **2**          | Médio          |
| < 5.0         | **3**          | Em formação    |

**1 é melhor que 3.** Operador nível 1 é o mais experiente (menos defeitos
por operação executada). Operador nível 3 está em formação e precisa de
supervisão.

## Que barcos pode fazer cada nível

Os barcos NELO têm preço e exigência técnica crescente:

- **Recreio** — entrada, peças standard
- **K1 standard** — competição base
- **K2 / K2x** — competição média (sandwich)
- **K1 elite** — competição top (sandwich complexo, layups exigentes)
- **K4** — quad, peça mais cara e mais difícil

Atribuições recomendadas:

| Nível | Barcos recomendados                                | Notas |
|-------|----------------------------------------------------|-------|
| 1     | K1 elite, K4, K1 standard, K2, Recreio (todos)     | Pode mentorar nível 2/3 |
| 2     | K2, K1 standard, Recreio                           | Apto K1 elite supervisionado por nível 1 |
| 3     | Recreio (supervisionado por nível 1 ou 2)          | Em formação activa |

## Polivalência — nível por fase

O nível **per-fase** é independente do nível global e está armazenado em
`SkillMatrixRow.nivel` (campo curado vindo do ERP, override possível via
`PATCH /v1/workforce/employees/{id}/skills`).

**Mesmo operador pode ter níveis diferentes em fases diferentes.** Exemplo:

- Operador "João Silva" tem quality score global 7.5 → nível **2** global.
- Em **Laminagem** o seu skill matrix mostra `nivel=1` (executou 200+ operações
  com defeito muito baixo).
- Em **Pintura** mostra `nivel=3` (executou apenas 15 operações, defeitos altos).

Quando o Copilot for perguntado *"posso atribuir o João Silva à pintura do K1
elite?"*, deve cruzar o nível global (2) com o nível per-fase de Pintura (3) e
**recusar** — recomendar pintor de nível 1 ou 2 *nessa fase*.

## Como o LLM deve responder

Quando o frontend envia `entity_type="employee"` + `entity_id` ao endpoint
`POST /api/copilot/ask`, o backend injecta um bloco `employee_context` no
prompt com:

```json
{
  "employee_id": "uuid",
  "quality_score": 7.5,
  "derived_level": 2,
  "level_label": "Médio",
  "level_description": "Quality score 5.0–7.9. Faz K2 standard + K1 standard...",
  "recommended_boats": ["K2", "K1 standard", "Recreio"],
  "skills_apt": ["Laminagem", "Acabamento", "..."]
}
```

O LLM deve:

1. **Citar o nível derivado** explicitamente — "Nível 2 (Médio)" — e o quality
   score que o sustenta.
2. **Recomendar barcos da lista `recommended_boats`** sem inventar outros.
3. **Avisar quando o pedido excede o nível** ("o K1 elite requer nível 1 ou
   nível 2 supervisionado por nível 1").
4. **Cruzar com a `skills_apt`** quando a pergunta menciona uma fase
   específica.
5. **Nunca inventar quality score, nível ou skill** — se não vem em
   `employee_context`, pedir ao utilizador para clicar primeiro num operador.

## Como manualmente alterar o nível

O nível global é derivado e **não é editável manualmente** (vem dos defeitos
reais). Se Luis quer ajustar:

- **Para alterar o nível global**: usar `PATCH /v1/workforce/employees/{id}/quality-score`
  com novo score [1, 10] e razão (≥10 chars). Drop um `PreferenceRule` Camada 1.
- **Para alterar nível per-fase**: usar `PATCH /v1/workforce/employees/{id}/skills`
  com `{phase_id, can_do, nivel: 1-5, reason}`. *Nota: o per-fase mantém-se
  na escala 1-5 (legacy curated); a UI bucketiza para 1-3 quando apresenta o
  nível global.*
