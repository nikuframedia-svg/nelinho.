"""NL → CubeQuery via LLM structured output.

Pipeline:
    pergunta_PT → top-k materiais (FAISS) → prompt LLM → JSON validado
    contra catálogo → CubeQuery executável ou abstain honesto.

O LLM nunca escreve SQL nem calcula. Usa `structured_call` do módulo
`src.copilot.llm.structured` para garantir JSON Pydantic-válido com
retries baseados em validation errors (já existente, reutilizado).
"""
from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

log = logging.getLogger(__name__)

from pydantic import BaseModel, ConfigDict, Field

from src.copilot.cube.client import CubeCatalog
from src.copilot.cube.material_retrieval import (
    AliasApplied,
    AmbiguousHit,
    MaterialIndex,
    apply_aliases,
)
from src.copilot.cube.measure_retrieval import (
    MeasureIndex,
    MeasureIndexNotBuilt,
)
from src.copilot.cube.measure_contract import (
    MEASURE_REGISTRY,
    assert_question_coverage,
    extract_mentioned_fase,
    extract_mentioned_material,
    is_accumulated_request,
    is_causal_question,
    is_derived_measure_request,
    is_period_mismatch,
    is_unsupported_concept_request,
    render_catalog_block,
    resolve_question_period,
)
from src.copilot.cube.query import (
    CubeFilter,
    CubeQuery,
    CubeTimeDimension,
    validate_against_catalog,
)
from src.copilot.cube.schema_compiler import compile_interpret_result_schema
from src.copilot.llm.base import LLMClient
from src.copilot.llm.structured import (
    StructuredCallError,
    StructuredValidationError,
    structured_call,
)
from src.copilot.cube.periods import resolve_periodo
from src.shared.time import local_today


PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "cube_interpret.md"
)
# Q.R restauração — modelo do interpret precisa de respeitar constrained
# decoding (format=<JSON Schema>) para nunca emitir measure/dimension fora
# do enum do catálogo. Medido no Ollama 0.24.0 desta máquina: `gemma4:e4b`
# respeita o schema (mede certo), `qwen3.5:9b` ignora-o (inventa measures,
# devolve lixo). qwen3.5:9b fica para tool-calling/narração (texto livre).
# Override por env sem editar código.
import os as _os

DEFAULT_MODEL = _os.environ.get("CUBE_INTERPRET_MODEL", "gemma4:e4b")
TOP_K_MATERIALS = 10
# Q.105.A — retrieval de medida: K=5 candidatas no prompt + threshold de
# abstain. Calibração em sanity (15 medidas, RRF k=60): top-1 score real
# fica em 0.032-0.033; threshold 0.02 distingue match (>0.025) de noise
# (<0.02) sem rejeitar perguntas legítimas.
TOP_K_MEASURES = 5
MEASURE_RETRIEVAL_THRESHOLD = 0.02


class InterpretResult(BaseModel):
    """Estrutura JSON que o LLM tem de devolver."""

    model_config = ConfigDict(extra="ignore")

    abstain: bool = False
    reason: str = ""
    query: CubeQuery | None = None
    # Q.93.D.bis Etapa B — rótulo de período relativo. O LLM identifica QUAL
    # expressão usámos ("ontem"/"esta_semana"/...); o CÓDIGO resolve o range
    # exacto via _resolve_period_label. "LLM propõe, código decide."
    period_label: str | None = None


# Q.93.D.bis Etapa B — mapa de rótulos PT-PT (snake_case) para dateRange Cube.
# Reutiliza resolve_periodo() de slot_filler.py para tudo o que ela já cobre;
# adiciona "ontem"/"hoje" (não cobertos lá ainda).
#
# Cube interpreta dateRange como inclusivo nos dois extremos. resolve_periodo
# devolve [start, end_exclusive) — converte-se subtraindo 1 dia.
_KNOWN_PERIOD_LABELS: tuple[str, ...] = (
    "ontem",
    "hoje",
    "esta_semana",
    "semana_passada",
    "mes_passado",
    "este_mes",
    "este_ano",
    "ano_passado",
    # Q.93.E.C.3 — idiomas adicionais PT-PT (datas determinísticas).
    "inicio_do_mes",
    "fim_do_mes",
    "primeiro_trimestre",
    "segundo_trimestre",
    "terceiro_trimestre",
    "quarto_trimestre",
    "trimestre_atual",
    "ano_ate_hoje",
)


def _last_day_of_month(year: int, month: int) -> _dt.date:
    """Último dia do mês (28/29/30/31 conforme calendário)."""
    if month == 12:
        next_first = _dt.date(year + 1, 1, 1)
    else:
        next_first = _dt.date(year, month + 1, 1)
    return next_first - _dt.timedelta(days=1)


def is_partial_current_month(
    date_range: list[str] | None, today: _dt.date
) -> bool:
    """Q.156.B (LLM-4) — True sse `date_range` == [1º, último] do mês de
    `today` E `today` ainda não chegou ao último dia (mês em curso → os
    dados são parciais e o consumidor deve ser avisado)."""
    if not date_range or len(date_range) != 2:
        return False
    try:
        start = _dt.date.fromisoformat(str(date_range[0])[:10])
        end = _dt.date.fromisoformat(str(date_range[1])[:10])
    except (ValueError, TypeError):
        return False
    first = today.replace(day=1)
    last = _last_day_of_month(today.year, today.month)
    return start == first and end == last and today < last


def _filter_value_to_daterange(value: object) -> tuple[str, str] | None:
    """Converte um valor de filtro "YYYY-MM" ou "YYYY-MM-DD" num dateRange
    inclusivo. Fallback quando a pergunta não dá período determinístico.
    Devolve None se não for parseável (não tenta adivinhar)."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    try:
        if len(s) == 7 and s[4] == "-":  # YYYY-MM
            year, month = int(s[:4]), int(s[5:7])
            start = _dt.date(year, month, 1)
            return start.isoformat(), _last_day_of_month(year, month).isoformat()
        if len(s) == 10 and s[4] == "-" and s[7] == "-":  # YYYY-MM-DD
            d = _dt.date.fromisoformat(s)
            return d.isoformat(), d.isoformat()
    except ValueError:
        return None
    return None


def _quarter_range(year: int, quarter: int) -> tuple[_dt.date, _dt.date]:
    """Retorna (start, end) inclusive do trimestre 1-4 do ano dado."""
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = _dt.date(year, start_month, 1)
    end = _last_day_of_month(year, end_month)
    return start, end


def _resolve_period_label(
    label: str, today: _dt.date
) -> tuple[str, str] | None:
    """Resolve rótulo PT-PT para (start_iso, end_iso) Cube-inclusive.

    Devolve None se label desconhecido — caller deixa o LLM tratar.

    Q.93.E.C.3 — datas determinísticas para idiomas PT-PT adicionais
    (inicio_do_mes, fim_do_mes, trimestres, ano_ate_hoje). O LLM identifica
    a expressão e atribui o snake_case; o código calcula o range exacto.
    """
    if label == "ontem":
        d = today - _dt.timedelta(days=1)
        return d.isoformat(), d.isoformat()
    if label == "hoje":
        return today.isoformat(), today.isoformat()

    # Q.93.E.C.3 — idiomas adicionais determinísticos.
    if label == "inicio_do_mes":
        # Convenção pragmática: primeiros 7 dias do mês corrente
        # (1 a 7). Suficientemente apertado para a maior parte das
        # perguntas tipo "Quanto se gastou no início do mês?".
        start = today.replace(day=1)
        end = start + _dt.timedelta(days=6)
        return start.isoformat(), end.isoformat()
    if label == "fim_do_mes":
        # Últimos 7 dias do mês corrente.
        last_day = _last_day_of_month(today.year, today.month)
        start = last_day - _dt.timedelta(days=6)
        return start.isoformat(), last_day.isoformat()
    if label == "primeiro_trimestre":
        start, end = _quarter_range(today.year, 1)
        return start.isoformat(), end.isoformat()
    if label == "segundo_trimestre":
        start, end = _quarter_range(today.year, 2)
        return start.isoformat(), end.isoformat()
    if label == "terceiro_trimestre":
        start, end = _quarter_range(today.year, 3)
        return start.isoformat(), end.isoformat()
    if label == "quarto_trimestre":
        start, end = _quarter_range(today.year, 4)
        return start.isoformat(), end.isoformat()
    if label == "trimestre_atual":
        q = (today.month - 1) // 3 + 1
        start, end = _quarter_range(today.year, q)
        return start.isoformat(), end.isoformat()
    if label == "ano_ate_hoje":
        start = _dt.date(today.year, 1, 1)
        return start.isoformat(), today.isoformat()

    # Reutilizar resolve_periodo() do slot_filler para rótulos conhecidos.
    text_map = {
        "esta_semana": "esta semana",
        "semana_passada": "semana passada",
        "mes_passado": "último mês",
        "este_mes": "este mês",
        "este_ano": "este ano",
        "ano_passado": "ano passado",
    }
    text = text_map.get(label)
    if text is None:
        return None
    now = _dt.datetime.combine(today, _dt.time.min)
    res = resolve_periodo(text, now=now)
    if res is None:
        return None
    start, end_exclusive, _desc = res
    end_inclusive = (end_exclusive - _dt.timedelta(days=1)).date()
    return start.date().isoformat(), end_inclusive.isoformat()


def _last_month_range(today: _dt.date) -> tuple[str, str]:
    """Devolve (start, end) ISO do mês anterior — utility para o prompt."""
    first_this = today.replace(day=1)
    last_prev = first_this - _dt.timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


def _format_aliases_block(applied: list[AliasApplied]) -> str:
    """Q.93.E.A.4 — bloco quando o utilizador usou termo coloquial que tem
    mapeamento inequívoco para a forma canónica do catálogo. Diz ao LLM
    para usar o termo CANÓNICO no `filter.values`, não a forma coloquial.
    """
    if not applied:
        return ""
    lines = [
        "## Termos canónicos do catálogo NELO",
        "",
        "O utilizador usou um ou mais termos coloquiais que têm forma "
        "CANÓNICA conhecida no catálogo NELO. Para o filter `contains` "
        "bater, **usa o termo CANÓNICO** (à direita) em `filter.values`, "
        "não a forma coloquial:",
        "",
    ]
    for a in applied:
        lines.append(f"- `\"{a.de}\"` → usa `\"{a.para}\"` no filter.")
    lines += [
        "",
        "Exemplo: pergunta menciona \"catalisador peróxido\" mas o catálogo "
        "NELO usa só \"Catalizador\" (todos os catalizadores são peróxidos "
        "para laminagem de poliéster). Usa `contains:\"catalizador\"` para "
        "apanhar todos. Mantém ambas as dimensões `material`+`unidade_id` "
        "no GROUP BY (anti-soma-cega).",
    ]
    return "\n".join(lines)


def _format_ambiguous_block(hits: list[AmbiguousHit]) -> str:
    """Q.93.E.A.4 — bloco no prompt quando o utilizador usou termos
    coloquiais largos. Se vazio, devolve string vazia (não aparece)."""
    if not hits:
        return ""
    lines = [
        "## Termos coloquiais ambíguos detectados",
        "",
        "Esta pergunta usa termos LARGOS que mapeiam a múltiplos materiais "
        "em UNIDADES DIFERENTES no catálogo NELO. Somar entre unidades = "
        "ERRO SILENCIOSO sagrado. **Tens de ABSTAIN** com sugestões para o "
        "utilizador escolher.",
        "",
    ]
    for h in hits:
        sugs = ", ".join(h.sugestoes) if h.sugestoes else "(múltiplas variantes)"
        lines.append(f"- **\"{h.termo}\"** — variantes: {sugs}.")
    lines += [
        "",
        "ABSTAIN com `reason` que liste as variantes e peça precisão. Exemplo:",
        "```json",
        "{\"abstain\": true, \"reason\": \"A categoria 'fibra de vidro' tem "
        "variantes em unidades diferentes — qual queres? Tecido Vidro (m²), "
        "Fibra unidirecional (kg) ou Quadriaxial Vidro (kg)?\", \"query\": null}",
        "```",
        "NÃO inventes filtros nem materiais. NUNCA somes m² + kg.",
    ]
    return "\n".join(lines)


def _filter_catalog_blocks(template: str, candidate_cubes: set[str]) -> str:
    """Q.105.A — manter só os blocos `### Cube: X` das candidatas.

    Parses `cube_interpret.md` blocos catálogo (linhas começando por
    `### Cube: \`nome\``) e remove os que NÃO aparecem em
    `candidate_cubes`. Mantém o cabeçalho `## Catálogo Cube` e todos os
    blocos antes/depois (regras inquebráveis, exemplos).

    Se `candidate_cubes` vazio, devolve o template original (degrade
    para comportamento Q.104).
    """
    if not candidate_cubes:
        return template

    # Encontrar limites: do primeiro "### Cube:" até `## Operators permitidos`
    # (próxima secção). Substituir o trecho por só os blocos das candidatas.
    import re as _re
    start_match = _re.search(r"^### Cube: `", template, _re.MULTILINE)
    end_match = _re.search(r"^## Operators permitidos", template, _re.MULTILINE)
    if not start_match or not end_match:
        return template  # template sem estrutura esperada — não tocar

    catalog_section = template[start_match.start():end_match.start()]
    # Split em blocos "### Cube: `name`"
    blocks = _re.split(r"(?m)^### Cube: ", catalog_section)
    # blocks[0] está vazio ou contém texto antes do primeiro "### Cube:"
    kept_blocks: list[str] = []
    for block in blocks[1:]:
        # Extrair nome do cube: primeira linha entre backticks.
        name_match = _re.match(r"`([^`]+)`", block)
        if not name_match:
            continue
        cube_name = name_match.group(1)
        if cube_name in candidate_cubes:
            kept_blocks.append("### Cube: " + block)

    if not kept_blocks:
        # Q.157.D — NENHUMA candidata tem bloco curado no .md (34 de 48 cubes
        # não têm). Em vez de degradar para o template inteiro (14 blocos
        # irrelevantes), gera os blocos das candidatas a partir do
        # MEASURE_REGISTRY — assim o LLM tem descrição + dimensões da medida que
        # o retrieval surgiu. SÓ neste caso: quando ALGUMA candidata já tem
        # bloco curado, mantemos só esse(s); acrescentar blocos gerados
        # tangenciais polui o prompt e faz o LLM abstain (regressão medida em
        # test_synonyms_match_consumo).
        generated = [
            g for g in (render_catalog_block(c) for c in sorted(candidate_cubes))
            if g
        ]
        if not generated:
            return template
        kept_blocks = generated

    new_catalog_section = "\n".join(kept_blocks)
    return template[:start_match.start()] + new_catalog_section + template[end_match.start():]


def _filter_few_shots(template: str, candidate_cubes: set[str]) -> str:
    """Q.105.A — manter só os exemplos few-shot relevantes.

    Parses `## Exemplos` secção, divide em blocos `**Pergunta:** ...` e
    mantém só os que referenciam medidas/cubes das candidatas. Mantém
    SEMPRE os exemplos puros de abstain (que não geram query — guardam
    regras inquebráveis tipo "preço por kg" → abstain).

    Se `candidate_cubes` vazio, devolve template original.
    """
    if not candidate_cubes:
        return template

    import re as _re
    start_match = _re.search(r"^## Exemplos\s*$", template, _re.MULTILINE)
    end_match = _re.search(r"^## Tu agora\s*$", template, _re.MULTILINE)
    if not start_match or not end_match:
        return template

    examples_section = template[start_match.end():end_match.start()]
    # Split em "**Pergunta:**"
    blocks = _re.split(r"(?m)^\*\*Pergunta:\*\* ", examples_section)
    # blocks[0] é o intro/lead da secção (linhas antes do primeiro Pergunta)
    intro = blocks[0]
    kept_blocks: list[str] = []
    for block in blocks[1:]:
        # Manter exemplos de abstain "puros" (regras inquebráveis):
        # query null + abstain true. Heurística: se o bloco contém
        # `"abstain": true` E não menciona nenhum dos 10 cubes em backticks,
        # é regra inquebrável (guardar).
        contains_query = '"query"' in block
        mentions_cube = any(c in block for c in candidate_cubes)
        is_pure_abstain = '"abstain": true' in block and '"query": null' in block

        if mentions_cube or (is_pure_abstain and not contains_query):
            kept_blocks.append("**Pergunta:** " + block)

    new_examples = intro + "".join(kept_blocks)
    return (
        template[:start_match.end()]
        + "\n"
        + new_examples
        + template[end_match.start():]
    )


def _build_system_prompt(
    top_materials: list[tuple[str, float]],
    today: _dt.date,
    ambiguous_hits: list[AmbiguousHit] | None = None,
    aliases_applied: list[AliasApplied] | None = None,
    candidate_cubes: set[str] | None = None,
) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    # Q.105.A — filtragem dinâmica do template: só blocos catálogo + few-shots
    # das candidatas do retrieval. Quando candidate_cubes vazio (None), comportamento
    # Q.104 inteiro (degrade gracioso para testes que não têm retrieval).
    if candidate_cubes:
        template = _filter_catalog_blocks(template, candidate_cubes)
        template = _filter_few_shots(template, candidate_cubes)

    lines = [f"- `{name}` (similaridade {score:.2f})" for name, score in top_materials]
    materials_block = "\n".join(lines) if lines else "(nenhum match relevante)"
    last_start, last_end = _last_month_range(today)
    ambiguous_block = _format_ambiguous_block(ambiguous_hits or [])
    aliases_block = _format_aliases_block(aliases_applied or [])
    extra_blocks = "\n\n".join(b for b in (aliases_block, ambiguous_block) if b)
    return (
        template
        .replace("{TOP_MATERIALS}", materials_block)
        .replace("{AMBIGUOUS_TERMS_BLOCK}", extra_blocks)
        .replace("{TODAY}", today.isoformat())
        .replace("{LAST_MONTH_START}", last_start)
        .replace("{LAST_MONTH_END}", last_end)
    )


# Q.95.2 — detecção de medida derivada inexistente vive no `measure_contract`
# (importada acima como `is_derived_measure_request`). A defesa primária
# continua a ser o prompt [cube_interpret.md regra 6]; esta é a rede pós-LLM.


async def interpret(
    question: str,
    catalog: CubeCatalog,
    material_index: MaterialIndex,
    ollama: LLMClient,
    model: str = DEFAULT_MODEL,
    today: _dt.date | None = None,
    measure_index: MeasureIndex | None = None,
) -> InterpretResult:
    """Pergunta PT-PT → InterpretResult (com query CubeQuery ou abstain).

    Se o LLM produzir um JSON sintacticamente válido mas que falha o
    validador contra o catálogo, coage para `abstain` com a primeira
    violação como `reason` — não confiamos no LLM para auto-corrigir em
    casos de desalinhamento semântico (e.g. somar unidades).
    """
    if today is None:
        today = local_today()

    # Q.95.2 — rede pós-pergunta contra medida derivada inexistente (delega
    # ao `measure_contract`). Defesa primária está no prompt regra 6.
    derived_match = is_derived_measure_request(question)
    if derived_match is not None:
        return InterpretResult(
            abstain=True,
            reason=(
                f"a pergunta pede uma medida derivada (\"{derived_match.strip()}\") "
                "que não existe no catálogo Cube. As medidas reais são: "
                "consumo (quantidade), custo (€), n_movimentos, taxa_defeitos "
                "(fracção 0-1). Preço unitário, médias, rácios e taxas "
                "derivadas têm de ser calculados a partir destas — o "
                "copiloto não os faz."
            ),
            query=None,
        )

    # Q.96 — rede pós-pergunta contra causalidade. Cube responde "quanto/qual",
    # nunca "porquê". Defesa primária está no prompt regra 7.
    causal_match = is_causal_question(question)
    if causal_match is not None:
        return InterpretResult(
            abstain=True,
            reason=(
                f"a pergunta é causal (\"{causal_match.strip()}\") — o Cube "
                "responde 'quanto/qual', não 'porquê'. Para análise causal "
                "usa `/v1/copilot/ask` com intent diagnostic (NELO_DAG). "
                "Posso devolver números (consumo, custo, taxa_defeitos, "
                "n_movimentos) mas não causas-raiz."
            ),
            query=None,
        )

    # Q.97 FIX 3 — rede pré-LLM contra conceito industrial sem medida
    # registada (refugo/scrap/rework/rejeitado). Refugo (scrap descartado)
    # ≠ defeito (recuperável) — não mapear silenciosamente para
    # `qualidade.defeitos`. Defesa primária está no prompt regra 8.
    concept_match = is_unsupported_concept_request(question)
    if concept_match is not None:
        return InterpretResult(
            abstain=True,
            reason=(
                f"a pergunta refere {concept_match.strip()!r} — não tenho "
                "medida registada para esse conceito industrial. Refugo / "
                "scrap / rework são semanticamente distintos de defeitos "
                "(`qualidade.taxa_defeitos` cobre só checks com gravidade "
                "≥ 1, não peças descartadas). Para defeitos pergunta "
                "explícita por 'defeitos' ou 'taxa de defeitos'."
            ),
            query=None,
        )

    # Q.93.E Etapa B — retrieval híbrido FAISS + BM25 via RRF.
    # Q.93.E.A.4 — `apply_aliases()` detecta termos ambíguos (categorias
    # largas com variantes em unidades diferentes) para sinalizar ao LLM
    # que tem de abstain com sugestões. A substituição de aliases
    # inequívocos é feita DENTRO de `top_k_hybrid` para o retrieval.
    alias_info = apply_aliases(question)
    _top_fn = getattr(material_index, "top_k_hybrid", material_index.top_k)
    top_materials = await _top_fn(question, ollama=ollama, k=TOP_K_MATERIALS)

    # Q.105.A — retrieval de MEDIDA (paralelo ao de material). Top-K=5
    # candidatas filtradas; só essas entram no prompt + schema enum.
    # Degrade gracioso: se measure_index não disponível ou índice não
    # construído, segue Q.104 (todas as medidas).
    top_measures: list[tuple[str, float]] = []
    candidate_cubes: set[str] = set()
    candidate_measure_names: tuple[str, ...] | None = None

    _midx = measure_index or MeasureIndex.get()
    try:
        _midx.load()
        top_measures = await _midx.top_k_hybrid(
            question, ollama=ollama, k=TOP_K_MEASURES
        )
        # Guard "retrieval falhou" → abstain honesto. Sem candidata acima
        # do threshold significa que nenhuma medida do catálogo bate a
        # pergunta — abster antes de chamar o LLM evita que ele "escolha
        # à força" entre candidatas inadequadas.
        if not top_measures or top_measures[0][1] < MEASURE_RETRIEVAL_THRESHOLD:
            return InterpretResult(
                abstain=True,
                reason=(
                    "nenhuma medida do catálogo bate suficientemente bem a "
                    "pergunta — clarifica o que queres saber. Medidas "
                    "disponíveis cobrem: consumo/custo de matéria-prima, "
                    "qualidade (defeitos), produção (OFs em curso/expedidas), "
                    "facturação comercial, cura em estufa, atrasos de "
                    "transporte."
                ),
                query=None,
            )
        candidate_cubes = {m.split(".")[0] for m, _ in top_measures}
        candidate_measure_names = tuple(m for m, _ in top_measures)
    except MeasureIndexNotBuilt:
        # Índice ainda não construído. Degrade Q.104 (todas as medidas).
        candidate_cubes = set()
        candidate_measure_names = None
    except Exception:
        # Índice corrompido, Ollama offline, shape mismatch — degrade Q.104.
        log.exception("measure index falhou; degrade para todas as medidas")
        candidate_cubes = set()
        candidate_measure_names = None

    system_prompt = _build_system_prompt(
        top_materials,
        today,
        ambiguous_hits=alias_info.ambiguous_hits,
        aliases_applied=alias_info.aliases_applied,
        candidate_cubes=candidate_cubes,
    )

    # Q.93.E Etapa B — JSON Schema dinâmico com enums do catálogo Cube.
    # llama.cpp aplica constrained decoding ao nível do token. O LLM fica
    # fisicamente incapaz de emitir medidas/dimensões/period_label fora
    # do enum. Defesa em profundidade — validate_against_catalog continua.
    # Q.105.A — enum measures filtrado às candidatas do retrieval.
    interpret_schema = compile_interpret_result_schema(
        catalog,
        period_labels=_KNOWN_PERIOD_LABELS,
        candidate_measure_names=candidate_measure_names,
    )
    try:
        result = await structured_call(
            ollama,
            response_model=InterpretResult,
            messages=[{"role": "user", "content": question}],
            model=model,
            system_prompt=system_prompt,
            max_retries=2,
            format_override=interpret_schema,
        )
    except (StructuredCallError, StructuredValidationError) as exc:
        return InterpretResult(
            abstain=True,
            reason=f"LLM falhou a produzir JSON válido: {exc}",
            query=None,
        )

    if result.abstain or result.query is None:
        return result

    violations = validate_against_catalog(result.query, catalog)
    if violations:
        return InterpretResult(
            abstain=True,
            reason=f"JSON não passa validação contra catálogo: {violations[0]}",
            query=None,
        )

    # Q.97b FIX A — datas determinísticas SEMPRE quando a pergunta permite.
    # Tira ao LLM o poder de errar "Maio" → "Abril". Resolve_question_period
    # apanha meses absolutos PT-PT ("Maio", "Maio de 2026", YYYY-MM) +
    # relativos ("último mês", "este mês", …); recusa-se em intervalos
    # abertos ("Maio até hoje") e códigos de produto. Quando há range
    # determinístico, sobrepõe o dateRange ANTES do override do
    # period_label (Q.93.D.bis), que fica como fallback para casos não
    # cobertos pelo helper.
    # Q.R FIX datas — uma dimensão de tempo (DATE no Postgres) NUNCA deve
    # aparecer como filtro `contains`/`equals`: o Cube gera `date ~~* text`
    # (400) ou um `IN list` de 2 datas (subset errado, qd01). As datas
    # pertencem a timeDimensions/dateRange. Modelos pequenos (gemma4:e4b)
    # erram isto de forma não-determinística (o anchor consumo chegou a
    # produzir `consumo_material.data contains ["2024-04"]`). Saneamento:
    #   1. detectar filtros cujo member é dimensão do tipo `time` (via catálogo);
    #   2. sintetizar uma timeDimension para cada um sem correspondência
    #      (dateRange determinístico da pergunta; fallback ao valor do filtro);
    #   3. remover TODOS os filtros sobre dimensões de tempo (já cobertos).
    det_range = resolve_question_period(question, today)
    time_filter_members = {
        f.member for f in result.query.filters
        if (ds := catalog.dimension(f.member)) is not None and ds.type == "time"
    }
    if time_filter_members:
        existing_td = {td.dimension for td in result.query.time_dimensions}
        for member in sorted(time_filter_members):
            if member in existing_td:
                continue
            rng = det_range
            if rng is None:
                for f in result.query.filters:
                    if f.member != member:
                        continue
                    for v in f.values:
                        rng = _filter_value_to_daterange(v)
                        if rng is not None:
                            break
                    if rng is not None:
                        break
            if rng is not None:
                result.query.time_dimensions.append(
                    CubeTimeDimension(dimension=member, dateRange=list(rng))
                )
        result.query.filters = [
            f for f in result.query.filters
            if f.member not in time_filter_members
        ]

    # Q.97b FIX A / Q.93.D.bis — datas determinísticas SEMPRE quando a pergunta
    # permite: tira ao LLM o poder de errar "Maio"→"Abril" ou "2026"→"2024".
    if det_range is not None and result.query.time_dimensions:
        result.query.time_dimensions[0].date_range = list(det_range)

    # Q.108.F — remover filter redundante em coluna .data quando a mesma coluna
    # já está em timeDimensions (caso `equals [start,end]` → `IN list`, qd01).
    if result.query.time_dimensions and result.query.filters:
        td_data_members = {
            td.dimension for td in result.query.time_dimensions
            if td.date_range
        }
        result.query.filters = [
            f for f in result.query.filters
            if not (f.member in td_data_members
                    and f.operator in {"equals", "inDateRange", "contains", "notContains"})
        ]

    # Q.108.F FIX A fase — injecção determinística do filter fase quando a
    # pergunta menciona fase canónica (Laminagem/Pintura/Corte/Acabamento/…)
    # e a query do LLM omite o filtro. Fecha qd01 (família qd04 estendida
    # de material → fase).
    fase_mencionada = extract_mentioned_fase(question)
    if fase_mencionada is not None:
        # Só injectar se: (a) measure suporta dim fase E (b) query ainda
        # não filtra fase.
        any_measure_supports_fase = any(
            (spec := MEASURE_REGISTRY.get(m)) is not None
            and "fase" in spec.dimensions_supported
            for m in result.query.measures
        )
        already_has_fase_filter = any(
            f.member.endswith(".fase") for f in result.query.filters
        )
        already_has_fase_dim = any(
            d.endswith(".fase") for d in result.query.dimensions
        )
        if (
            any_measure_supports_fase
            and not already_has_fase_filter
            and not already_has_fase_dim
            and result.query.measures
        ):
            # Cube namespace = prefixo da 1ª measure (e.g. "qualidade.taxa_defeitos"
            # → "qualidade").
            cube_ns = result.query.measures[0].split(".", 1)[0]
            result.query.filters.append(
                CubeFilter(
                    member=f"{cube_ns}.fase",
                    operator="contains",
                    values=[fase_mencionada],
                )
            )

    # Q.R FIX A material — injecção determinística do filter material quando a
    # pergunta menciona um material canónico (via pattern explícito ou top-1
    # do retrieval híbrido) e a query do LLM o omite. Espelha o FIX A fase:
    # modelos locais pequenos (gemma4:e4b) respeitam o enum de measures mas
    # falham a montar o filtro material + agrupamento por unidade_id. Sem isto
    # o guard de cobertura (Q.97b FIX B) abstém numa pergunta respondível.
    # "LLM propõe, código decide". Anti-soma-cega: força dims [material,
    # unidade_id] para nunca somar unidades incompatíveis (kg + unidade).
    material_mencionado = extract_mentioned_material(question, top_materials)
    # Só injectar com evidência FORTE do material: o nome completo como
    # substring, ou ≥2 tokens significativos (≥4 chars) do nome presentes na
    # pergunta. Evita forçar um material específico quando a pergunta usa um
    # termo largo/ambíguo ("quanto de resina?") — nesse caso o fluxo segue e o
    # guard de cobertura abstém com pedido de clarificação (anti-soma-cega).
    if material_mencionado is not None:
        _q_low = question.lower()
        _mat_low = material_mencionado.lower()
        _strong_material = _mat_low in _q_low or sum(
            1 for _tok in _mat_low.split() if len(_tok) >= 4 and _tok in _q_low
        ) >= 2
    else:
        _strong_material = False
    if material_mencionado is not None and _strong_material and result.query.measures:
        any_measure_supports_material = any(
            (spec := MEASURE_REGISTRY.get(m)) is not None
            and "material" in spec.dimensions_supported
            for m in result.query.measures
        )
        # O filtro canónico já está presente? (o LLM por vezes filtra material
        # mas com um valor genérico adivinhado — "resina" — em vez do nome
        # canónico que o retrieval resolveu — "Resina Lavesan EN 720".)
        canonical_filtered = any(
            f.member.endswith(".material")
            and f.operator == "contains"
            and material_mencionado in (f.values or [])
            for f in result.query.filters
        )
        if any_measure_supports_material and not canonical_filtered:
            cube_ns = result.query.measures[0].split(".", 1)[0]
            # Descartar quaisquer filtros de material não-canónicos do LLM e
            # injectar o canónico do retrieval/pattern.
            result.query.filters = [
                f for f in result.query.filters
                if not f.member.endswith(".material")
            ]
            result.query.filters.append(
                CubeFilter(
                    member=f"{cube_ns}.material",
                    operator="contains",
                    values=[material_mencionado],
                )
            )
            # Anti-soma-cega: garantir agrupamento por material + unidade_id.
            for dim_suffix in ("material", "unidade_id"):
                dim = f"{cube_ns}.{dim_suffix}"
                if dim not in result.query.dimensions:
                    result.query.dimensions.append(dim)

    # Q.108.F FIX A acumulado — remoção determinística da timeDimension
    # quando a pergunta pede TOTAL acumulado/histórico e NÃO há período
    # explícito. Fecha fd01 (família Q.97b mas em sentido oposto). O Cube
    # REST rejeita timeDimension com dateRange vazio (HTTPStatusError) —
    # remover a timeDimension inteira é o caminho honesto.
    if (
        is_accumulated_request(question)
        and det_range is None
        and result.query.time_dimensions
    ):
        result.query.time_dimensions = []

    # Q.93.D.bis Etapa B — fallback: o LLM identificou um rótulo de período
    # relativo conhecido que o `resolve_question_period` não apanhou.
    # Mantido para coverage de rótulos sem mês explícito na pergunta.
    # Q.108.F: pular fallback se a pergunta pede acumulado (LLM pode
    # alucinar period_label="este_ano" em "facturação acumulada" e o
    # fallback REPOR o dateRange que o FIX A acumulado acabou de limpar).
    if (
        result.period_label
        and result.query.time_dimensions
        and result.period_label in _KNOWN_PERIOD_LABELS
        and not is_accumulated_request(question)
    ):
        override = _resolve_period_label(result.period_label, today)
        if override is not None:
            # Q.97b: só sobrepor se ainda não foi sobreposto pelo FIX A
            # determinístico (verificar consistência primeiro). Se FIX A
            # já actuou, o dateRange é fonte-de-verdade.
            det_was_applied = (
                resolve_question_period(question, today) is not None
            )
            if not det_was_applied:
                result.query.time_dimensions[0].date_range = list(override)

    # Q.97 FIX 1 (rede pós-injeção) — concordância pergunta↔payload temporal.
    # Após FIX A do Q.97b o dateRange está determinístico para a maioria dos
    # casos; este check fica como rede silenciosa contra casos residuais
    # (ex.: intervalos abertos onde FIX A se abstém e o LLM erra).
    period_violation = is_period_mismatch(question, result.query, today)
    if period_violation is not None:
        return InterpretResult(
            abstain=True,
            reason=(
                "discordância de período entre pergunta e query: "
                f"{period_violation}"
            ),
            query=None,
        )

    # Q.97b FIX B — guard de cobertura: entidades MENCIONADAS na pergunta
    # têm de estar honradas na query (fidelidade output↔input). Fecha qd04:
    # "defeitos do material X" + query que ignora material → abstain
    # ("medida não se decompõe por material").
    material_mencionado = extract_mentioned_material(question, top_materials)
    # Q.108.F: fase_mencionada (já extraída no FIX A acima; re-uso para coerência).
    coverage_violations = assert_question_coverage(
        result.query,
        material_mencionado=material_mencionado,
        fase_mencionada=fase_mencionada,
        question=question,
    )
    if coverage_violations:
        return InterpretResult(
            abstain=True,
            reason=(
                "fidelidade comprometida: " + coverage_violations[0]
            ),
            query=None,
        )

    # Q.93.D.bis Etapa C.1 — REVERTIDO. O validador pós-LLM "valor TEM de bater
    # top-k" causou 4 regressões (q02/q04/q07/q10 — gelcoat/acetona/cola/divinycell).
    # Causa raiz: o FAISS retorna top-10 pobre para muitas perguntas comuns
    # (ver agent_docs/q93_d_bis_retrieval_diagnose.txt), portanto a validação
    # rejeita materiais legítimos que NÃO aparecem no top-10. O problema é do
    # retrieval, não do LLM. Fica como bloqueador estrutural para Q.93.E.
    return result
