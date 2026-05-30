"""Q.93.E Etapa B — compilador de JSON Schema para constrained decoding.

O Ollama 0.5+ aceita um objecto JSON Schema no campo `format` da API
`/api/chat`. O llama.cpp por baixo aplica constrained decoding ao nível
do token — sequências que não bateriam o schema ficam fisicamente
impossíveis de gerar.

Aqui geramos o schema do `InterpretResult` dinamicamente a partir do
catálogo Cube `/meta`:

- `measures`, `dimensions`, `filter.member`, `timeDimension.dimension`
  ficam restritas ao **enum** dos nomes reais do catálogo. O LLM não
  pode emitir `consumo_material.custo` (medida inexistente).
- `filter.operator` enum dos operators permitidos (anti-soma-cega).
- `timeDimension.granularity` enum das granularidades válidas.
- `period_label` enum dos rótulos PT-PT conhecidos + null.

Regenera-se a cada inicialização do interpret (catálogo já vem cached em
process — custo zero). Quando o catálogo mudar (Cube Fase 1 com novos
cubes), o schema actualiza automaticamente na próxima request.

Defesa em profundidade: o `validate_against_catalog()` em
[query.py:94] continua a correr depois, para regras semânticas que o
enum schema NÃO captura (anti-soma-cega: filtro contains material exige
agrupamento por unidade_id).
"""
from __future__ import annotations

from typing import Any

from src.copilot.cube.client import CubeCatalog
from src.copilot.cube.query import (
    ALLOWED_FILTER_OPERATORS,
    ALLOWED_TIME_GRANULARITIES,
)


def _cube_query_schema(
    catalog: CubeCatalog,
    candidate_measure_names: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Schema do CubeQuery com enums vindos do catálogo Cube.

    Q.105.A: quando `candidate_measure_names` é fornecido, o enum `measures`
    fica filtrado para SÓ essas (resultado do retrieval BM25+FAISS). LLM
    constrained-decoded não pode emitir medida fora dessa lista. Quando
    `None` (back-compat), comportamento original (todas as medidas).
    """
    all_measure_names = sorted(catalog.all_measure_names())
    if candidate_measure_names is not None:
        # Q.105.A: filtrar enum measures às candidatas do retrieval.
        # Preservar ordem do retrieval mas só nomes que existem no catálogo
        # (proteção contra retrieval out-of-sync com Cube /meta).
        catalog_set = set(all_measure_names)
        measure_names = sorted(
            m for m in candidate_measure_names if m in catalog_set
        )
        if not measure_names:
            # Retrieval falhou em fornecer medidas válidas — cair para todas
            # (degrade > schema impossível). Caller deveria já ter abstido.
            measure_names = all_measure_names
    else:
        measure_names = all_measure_names

    dimension_names = sorted(catalog.all_dimension_names())
    time_dim_names = sorted(
        d for d in dimension_names
        if (spec := catalog.dimension(d)) is not None and spec.type == "time"
    )
    all_member_names = sorted(set(measure_names) | set(dimension_names))

    # Fallback defensivo: catálogo vazio em testes (FakeCatalog). Sem enum
    # válido, o llama.cpp rejeita qualquer string — pior que sem schema.
    # Nesse caso, devolvemos um schema mais permissivo (sem enums).
    if not measure_names:
        return {
            "type": "object",
            "additionalProperties": True,
        }

    filter_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "member": {"type": "string", "enum": all_member_names},
            "operator": {
                "type": "string",
                "enum": sorted(ALLOWED_FILTER_OPERATORS),
            },
            "values": {"type": "array"},
        },
        "required": ["member", "operator"],
    }

    time_dim_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "dimension": {"type": "string", "enum": time_dim_names or all_member_names},
            "dateRange": {
                "type": "array",
                "items": {"type": "string"},
            },
            "granularity": {
                "type": "string",
                "enum": sorted(ALLOWED_TIME_GRANULARITIES),
            },
        },
        "required": ["dimension"],
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "measures": {
                "type": "array",
                "items": {"type": "string", "enum": measure_names},
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string", "enum": dimension_names},
            },
            "filters": {"type": "array", "items": filter_schema},
            "timeDimensions": {"type": "array", "items": time_dim_schema},
            "order": {"type": "array"},
            "limit": {"type": ["integer", "null"]},
        },
    }


def compile_interpret_result_schema(
    catalog: CubeCatalog,
    period_labels: tuple[str, ...],
    candidate_measure_names: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Gera o JSON Schema completo do `InterpretResult` com enums do catálogo.

    `period_labels` deve vir de `interpret._KNOWN_PERIOD_LABELS` para que
    o LLM só possa emitir snake_case canónicos.

    Q.105.A: `candidate_measure_names` (opcional) filtra o enum `measures`
    para as candidatas do retrieval. Reduz alucinação do LLM ao constrangir
    a escolha às medidas relevantes para a pergunta.

    O schema é passado como `format=<schema>` ao Ollama. Quando o catálogo
    está vazio (testes com fakes), devolve schema permissivo — graceful
    degrade para o comportamento antigo (validação pós-LLM).
    """
    cube_query = _cube_query_schema(catalog, candidate_measure_names)

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "abstain": {"type": "boolean"},
            "reason": {"type": "string"},
            "period_label": {
                # JSON Schema permite enum com null + strings
                "enum": [None, *period_labels],
            },
            "query": {
                "anyOf": [
                    {"type": "null"},
                    cube_query,
                ]
            },
        },
        "required": ["abstain"],
    }
