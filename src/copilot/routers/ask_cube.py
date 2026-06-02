"""Q.93.C — endpoints `/ask-cube` e `/ask-dev-cube` (Cube Fase 2).

Pipeline:
    pergunta_PT  →  interpret (LLM → CubeQuery)  →  validate vs catálogo
                 →  Cube REST /load  →  narrate (LLM → texto PT + guard).

Abdicação honesta em 3 pontos:
    1. JSON não passa validação contra catálogo → status="abstain".
    2. Cube devolve `data: []` → status="no_data".
    3. Guard de narração rejeita números não-payload → status="guard_failed",
       servimos a tabela crua + warning.

LLM nunca escreve SQL nem calcula. Reusa `OllamaClient` + `structured_call`
existentes; sem novo modelo. Routing congelado Q.84-92 fica intocado.
"""
from __future__ import annotations

import asyncio
import calendar
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.copilot.cube.client import CubeClient
from src.copilot.cube.measure_contract import (
    MEASURE_REGISTRY,
    list_measure_catalog,
    measure_display_unit,
)
from src.copilot.routers._common import dev_only
from src.copilot.cube.interpret import interpret, is_partial_current_month
from src.copilot.cube.material_retrieval import MaterialIndex
from src.copilot.cube.measure_retrieval import MeasureIndex
from src.copilot.cube.narrate import narrate_with_guard
from src.copilot.ollama_client import OllamaClient
from src.shared.auth.jwt_handler import UserContext, get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


# Q.93.D.bis Etapa A — gate determinístico de "resultado vasto".
# Acima deste threshold a narração não corre: a pergunta era demasiado vaga
# (sem filtro/período suficientes) e o LLM não consegue narrar honestamente
# centenas de linhas sem inventar (Q.93.D: q18 — 385 rows, ensaio de 80 linhas).
# Cortar aqui é determinístico e barato; o utilizador é convidado a refinar.
MAX_NARRATION_ROWS = 20


def _all_rows_effectively_empty(
    rows: list[dict[str, Any]], measures: list[str]
) -> bool:
    """Q.156.B (LLM-1) — uma linha só de measures todas-null == sem dados.

    O Cube devolve UMA linha de nulls (ex.: ``[{"qualidade.taxa_defeitos":
    None}]``) para uma medida-rácio sobre um slice vazio. Sintaticamente a
    lista é truthy (passa o ``if not result.data``), mas semanticamente é
    `no_data`. Um ``0.0`` real **não** conta como vazio (é um zero medido)."""
    if not rows:
        return True
    keys = measures or [k for r in rows for k in r]
    if not keys:
        return True
    return all(r.get(m) is None for r in rows for m in keys)


# ────────────────────────────── Schemas ──────────────────────────────


class AskCubeRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AskCubeResponse(BaseModel):
    status: Literal["ok", "abstain", "no_data", "guard_failed", "ambiguous"]
    narration: str | None = None
    query: dict[str, Any] | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    annotation: dict[str, Any] | None = None
    abstain_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ────────────────────────────── Pipeline ──────────────────────────────


async def _process(
    question: str,
    *,
    cube: CubeClient | None = None,
    ollama: OllamaClient | None = None,
    material_index: MaterialIndex | None = None,
    measure_index: MeasureIndex | None = None,
) -> AskCubeResponse:
    # Cliente novo por request: evita partilhar pool httpx entre event loops
    # (importante para testes pytest-asyncio, que criam loop por teste).
    # Em produção FastAPI o lifecycle do loop é mais estável, mas o
    # overhead de criar TCP por request é desprezável (Cube + Ollama locais).
    owns_cube = cube is None
    owns_ollama = ollama is None
    cube = cube or CubeClient()
    ollama = ollama or OllamaClient()
    material_index = material_index or MaterialIndex.get()

    try:
        # 1. Catálogo /meta (chamada local rápida; sem cache).
        catalog = await cube.fetch_meta()

        # 2. Interpret NL → CubeQuery (com retrieval de materiais + validação).
        interp = await interpret(
            question=question,
            catalog=catalog,
            material_index=material_index,
            ollama=ollama,
            measure_index=measure_index,
        )
        if interp.abstain or interp.query is None:
            return AskCubeResponse(
                status="abstain",
                abstain_reason=interp.reason or "Não percebi a pergunta.",
            )

        # 3. Executar contra Cube REST /load.
        payload = interp.query.to_cube_payload()
        try:
            result = await cube.load(payload)
        except Exception as exc:  # network / Cube down / 4xx
            logger.exception("Cube /load falhou para query=%s", payload)
            return AskCubeResponse(
                status="abstain",
                abstain_reason=f"Cube /load falhou: {type(exc).__name__}",
                query=payload,
            )

        # 4. Resultado vazio = honesto, sem narração inventada.
        if not result.data:
            return AskCubeResponse(
                status="no_data",
                narration="Não há dados para esses filtros.",
                query=payload,
                data=[],
                annotation=result.annotation,
            )

        # 4.1. Q.156.B (LLM-1) — linha(s) só de measures todas-null também é
        # `no_data` (o Cube devolve [{measure: null}] para um rácio sobre slice
        # vazio). Sem isto, "OFs fechadas hoje" → status="ok" + narração de 0.
        if _all_rows_effectively_empty(result.data, interp.query.measures):
            return AskCubeResponse(
                status="no_data",
                narration="Não há dados para esses filtros.",
                query=payload,
                data=[],
                annotation=result.annotation,
            )

        # 4.5. Resultado vasto = pergunta vaga, não tentamos narrar.
        if len(result.data) > MAX_NARRATION_ROWS:
            return AskCubeResponse(
                status="ambiguous",
                narration=(
                    f"Resultado vasto ({len(result.data)} combinações). "
                    "Especifica material e/ou período."
                ),
                query=payload,
                data=result.data[:10],
                annotation=result.annotation,
                warnings=[
                    f"resultado truncado a 10 linhas; pergunta é vaga "
                    f"(>{MAX_NARRATION_ROWS} rows)"
                ],
            )

        # 5. Narração com guards (números + contexto Q.93.E.C.2).
        narration = await narrate_with_guard(result, ollama)
        if not narration.ok:
            warnings: list[str] = []
            if narration.unsupported_numbers:
                warnings.append(
                    "guard de narração rejeitou números fora do payload: "
                    + ", ".join(f"{n:g}" for n in narration.unsupported_numbers)
                )
            if narration.context_violations:
                warnings.append(
                    "guard de narração rejeitou contexto: "
                    + "; ".join(narration.context_violations)
                )
            return AskCubeResponse(
                status="guard_failed",
                narration=None,
                query=payload,
                data=result.data,
                annotation=result.annotation,
                warnings=warnings,
            )

        # Q.156.B (LLM-4) — se o período resolvido é o mês em curso e ainda
        # não acabou, os dados são parciais: avisar honestamente.
        warnings_out: list[str] = []
        if interp.query.time_dimensions and is_partial_current_month(
            interp.query.time_dimensions[0].date_range, date.today()
        ):
            warnings_out.append("Mês em curso — dados parciais até hoje.")

        return AskCubeResponse(
            status="ok",
            narration=narration.text,
            query=payload,
            data=result.data,
            annotation=result.annotation,
            warnings=warnings_out,
        )
    finally:
        if owns_cube:
            await cube.close()
        if owns_ollama:
            await ollama.close()


# ────────────────────────────── Endpoints ──────────────────────────────


@router.post(
    "/ask-cube",
    response_model=AskCubeResponse,
    status_code=status.HTTP_200_OK,
)
async def ask_cube(
    request: AskCubeRequest,
    user: UserContext = Depends(get_current_user),
) -> AskCubeResponse:
    """Q.93.C — pergunta PT-PT → Cube REST → narração PT-PT (com auth)."""
    return await _process(request.question)


@router.post(
    "/ask-dev-cube",
    response_model=AskCubeResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def ask_cube_dev(request: AskCubeRequest) -> AskCubeResponse:
    """Q.93.C — `/ask-dev-cube` (sem auth, dev-only). Mesmo pipeline."""
    return await _process(request.question)


# ────────────────────────── Dashboard de KPIs (Q.R) ──────────────────────────
# A página de KPIs (/llm) deixa de usar o caminho legacy `/v1/profit/kpis/*`
# (quase vazio) e passa a mostrar as MEASURES REAIS do Cube. Este endpoint corre
# um conjunto CURADO e DETERMINÍSTICO de CubeQueries (sem LLM) em paralelo e
# devolve cards (valor actual) + séries para gráficos. Cada query degrada de
# forma honesta: se o mart não estiver populado, o card/gráfico vem `no_data`.


@dataclass(frozen=True)
class _CardSpec:
    key: str
    label: str
    unit: str          # "", "%", "€"
    measure: str       # ex: "producao_ofs_em_curso.total"
    period: str        # "none" (agregado) | "month" (mês corrente)


@dataclass(frozen=True)
class _ChartSpec:
    key: str
    label: str
    kind: str          # "line" | "bar"
    measure: str
    group: str         # "month:<dim.data>" | "dim:<dim>"


# Cards: indicadores reais de operações com dados do NELO (OFs em curso, taxa de
# defeitos, faturação, consumo, backlog, lead time, expedições).
_CARD_SPECS: tuple[_CardSpec, ...] = (
    _CardSpec("ofs_produzidas_hoje", "OFs produzidas hoje", "", "producao_ofs_fechadas_dia.total", "today"),
    _CardSpec("ofs_em_curso", "OFs em curso", "", "producao_ofs_em_curso.total", "none"),
    _CardSpec("taxa_defeitos", "Taxa de defeitos", "%", "qualidade.taxa_defeitos", "none"),
    _CardSpec("facturacao_mes", "Faturação (mês)", "€", "comercial_facturacao.total", "month"),
    _CardSpec("consumo_custo_mes", "Custo de consumo (mês)", "€", "consumo_material.custo", "month"),
    _CardSpec("backlog", "Backlog", "", "planeamento_backlog.total", "none"),
    _CardSpec("lead_time_p50", "Lead time mediano (P50)", "", "producao_lead_time_of.lead_time_p50", "none"),
    _CardSpec("ofs_expedidas_mes", "OFs expedidas (mês)", "", "logistica_ofs_expedidas.total", "month"),
)

# Gráficos: séries temporais (mês) e por fase.
_CHART_SPECS: tuple[_ChartSpec, ...] = (
    _ChartSpec("facturacao_mensal", "Faturação por mês", "line",
               "comercial_facturacao_mom.facturado_eur", "month:comercial_facturacao_mom.data"),
    _ChartSpec("ofs_por_fase", "OFs por fase", "bar",
               "producao_ofs_por_fase.total", "dim:producao_ofs_por_fase.fase"),
    _ChartSpec("defeitos_por_fase", "Taxa de defeitos por fase", "bar",
               "qualidade.taxa_defeitos", "dim:qualidade.fase"),
    _ChartSpec("consumo_mensal", "Consumo de material por mês", "line",
               "consumo_material.consumo", "month:consumo_material.data"),
)


class DashboardCard(BaseModel):
    key: str
    label: str
    unit: str
    value: float | None
    status: Literal["ok", "no_data", "error"]


class DashboardSeriesPoint(BaseModel):
    x: str
    y: float | None


class DashboardChart(BaseModel):
    key: str
    label: str
    kind: Literal["line", "bar"]
    series: list[DashboardSeriesPoint] = Field(default_factory=list)
    status: Literal["ok", "no_data", "error"]


class DashboardResponse(BaseModel):
    cards: list[DashboardCard] = Field(default_factory=list)
    charts: list[DashboardChart] = Field(default_factory=list)


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _current_month_range(today: date) -> tuple[str, str]:
    last = calendar.monthrange(today.year, today.month)[1]
    return today.replace(day=1).isoformat(), today.replace(day=last).isoformat()


def _last_12_months_range(today: date) -> tuple[str, str]:
    y, m = today.year, today.month - 11
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1).isoformat(), today.isoformat()


async def _run_card(cube: CubeClient, spec: _CardSpec, today: date) -> DashboardCard:
    payload: dict[str, Any] = {"measures": [spec.measure]}
    if spec.period == "month":
        start, end = _current_month_range(today)
        dim = f"{spec.measure.split('.', 1)[0]}.data"
        payload["timeDimensions"] = [{"dimension": dim, "dateRange": [start, end]}]
    elif spec.period == "today":
        dim = f"{spec.measure.split('.', 1)[0]}.data"
        payload["timeDimensions"] = [
            {"dimension": dim, "dateRange": [today.isoformat(), today.isoformat()]}
        ]
    try:
        result = await cube.load(payload)
        if not result.data:
            return DashboardCard(key=spec.key, label=spec.label, unit=spec.unit,
                                 value=None, status="no_data")
        value = _safe_float(result.data[0].get(spec.measure))
        return DashboardCard(key=spec.key, label=spec.label, unit=spec.unit,
                             value=value, status="ok" if value is not None else "no_data")
    except Exception:
        logger.warning("dashboard card %s falhou", spec.key, exc_info=True)
        return DashboardCard(key=spec.key, label=spec.label, unit=spec.unit,
                             value=None, status="error")


async def _run_chart(cube: CubeClient, spec: _ChartSpec, today: date) -> DashboardChart:
    mode, ref = spec.group.split(":", 1)
    payload: dict[str, Any] = {"measures": [spec.measure]}
    if mode == "month":
        start, end = _last_12_months_range(today)
        payload["timeDimensions"] = [
            {"dimension": ref, "dateRange": [start, end], "granularity": "month"}
        ]
        payload["order"] = [[ref, "asc"]]
    else:  # dim
        payload["dimensions"] = [ref]
        payload["order"] = [[spec.measure, "desc"]]
        payload["limit"] = 20
    try:
        result = await cube.load(payload)
        series: list[DashboardSeriesPoint] = []
        for row in result.data:
            if mode == "month":
                raw_x = row.get(f"{ref}.month") or row.get(ref)
                x = str(raw_x)[:7] if raw_x else "—"
            else:
                x = str(row.get(ref) or "—")
            series.append(DashboardSeriesPoint(x=x, y=_safe_float(row.get(spec.measure))))
        return DashboardChart(key=spec.key, label=spec.label, kind=spec.kind,
                              series=series, status="ok" if series else "no_data")
    except Exception:
        logger.warning("dashboard chart %s falhou", spec.key, exc_info=True)
        return DashboardChart(key=spec.key, label=spec.label, kind=spec.kind,
                              series=[], status="error")


@router.get(
    "/cube/dashboard-dev",
    response_model=DashboardResponse,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def cube_dashboard_dev() -> DashboardResponse:
    """Q.R — dashboard de KPIs reais do Cube (dev-only, sem LLM, sem auth).

    Corre cards + gráficos curados em paralelo contra o Cube REST. Reusa
    `CubeClient` (queries determinísticas). Degrada por item quando um mart
    ainda não está populado.
    """
    today = date.today()
    cube = CubeClient()
    try:
        results = await asyncio.gather(
            *[_run_card(cube, s, today) for s in _CARD_SPECS],
            *[_run_chart(cube, s, today) for s in _CHART_SPECS],
        )
    finally:
        await cube.close()
    n_cards = len(_CARD_SPECS)
    return DashboardResponse(
        cards=list(results[:n_cards]),
        charts=list(results[n_cards:]),
    )


# ────────────────── Picker de KPIs — catálogo + cards ad-hoc ──────────────────
# O dashboard acima é CURADO (7 cards fixos). Estes dois endpoints abrem o
# semantic layer inteiro: `measures-dev` lista TODAS as measures registadas no
# contrato (para o menu "Adicionar indicador"); `measure-cards-dev` corre as
# que o utilizador escolher, reusando o mesmo `_run_card` do dashboard. Lista
# fechada: só measures do MEASURE_REGISTRY são aceites (nunca SQL/medida livre).

# Limite defensivo de cards por pedido — o picker não pede mais que isto.
MAX_MEASURE_CARDS = 60


class MeasureCatalogEntry(BaseModel):
    name: str
    label: str
    unit: str           # "", "%", "€"
    domain: str
    dimensions: list[str] = Field(default_factory=list)
    supports_period: bool


class MeasureCatalogResponse(BaseModel):
    measures: list[MeasureCatalogEntry] = Field(default_factory=list)


class MeasureCardRequestItem(BaseModel):
    measure: str
    period: Literal["none", "month"] = "none"


class MeasureCardsRequest(BaseModel):
    items: list[MeasureCardRequestItem] = Field(default_factory=list)


class MeasureCardsResponse(BaseModel):
    cards: list[DashboardCard] = Field(default_factory=list)


@router.get(
    "/cube/measures-dev",
    response_model=MeasureCatalogResponse,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def cube_measures_dev() -> MeasureCatalogResponse:
    """Catálogo das measures do Cube para o picker de KPIs (dev-only, sem LLM).

    Lê só o `MEASURE_REGISTRY` (contrato) — sem round-trip ao Cube. A página de
    KPIs usa isto para encher o menu "Adicionar indicador" com TODAS as measures
    registadas, não só o conjunto curado do dashboard.
    """
    return MeasureCatalogResponse(
        measures=[MeasureCatalogEntry(**m) for m in list_measure_catalog()]
    )


def _coerce_card_specs(items: list[MeasureCardRequestItem]) -> list[_CardSpec]:
    """Valida o pedido do picker e constrói `_CardSpec` transientes.

    - Rejeita measures fora do `MEASURE_REGISTRY` (lista fechada) com 422.
    - `period="month"` só passa se a measure suportar `tempo`; senão cai para
      "none" (evita uma timeDimension inválida num cube sem `.data`).
    - Dedup por measure (um card por medida), preservando a ordem de escolha.
    - Unidade de apresentação via `measure_display_unit` (igual ao catálogo) →
      card coerente com o `formatValue` do frontend.
    """
    specs: list[_CardSpec] = []
    seen: set[str] = set()
    for item in items:
        spec_def = MEASURE_REGISTRY.get(item.measure)
        if spec_def is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"measure desconhecida no contrato: {item.measure}",
            )
        if item.measure in seen:
            continue
        seen.add(item.measure)
        supports_period = "tempo" in spec_def.dimensions_supported
        period = "month" if (item.period == "month" and supports_period) else "none"
        specs.append(
            _CardSpec(
                key=item.measure,
                label=spec_def.description or item.measure,
                unit=measure_display_unit(item.measure),
                measure=item.measure,
                period=period,
            )
        )
    return specs


@router.post(
    "/cube/measure-cards-dev",
    response_model=MeasureCardsResponse,
    include_in_schema=False,
    dependencies=[Depends(dev_only)],
)
async def cube_measure_cards_dev(request: MeasureCardsRequest) -> MeasureCardsResponse:
    """Valores actuais das measures escolhidas no picker (dev-only, sem LLM).

    Reutiliza o `_run_card` do dashboard: cada item vira um `_CardSpec` e corre
    em paralelo contra o Cube REST. Degrada por item (`no_data`/`error`) tal
    como o dashboard. NUNCA soma cross-measure — cada card é uma measure
    agregada pelo Cube na sua própria query.
    """
    specs = _coerce_card_specs(request.items[:MAX_MEASURE_CARDS])
    if not specs:
        return MeasureCardsResponse(cards=[])
    today = date.today()
    cube = CubeClient()
    try:
        cards = await asyncio.gather(*[_run_card(cube, s, today) for s in specs])
    finally:
        await cube.close()
    return MeasureCardsResponse(cards=list(cards))
