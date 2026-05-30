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

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from src.copilot.cube.client import CubeClient
from src.copilot.routers._common import dev_only
from src.copilot.cube.interpret import interpret
from src.copilot.cube.material_retrieval import MaterialIndex
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

        return AskCubeResponse(
            status="ok",
            narration=narration.text,
            query=payload,
            data=result.data,
            annotation=result.annotation,
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
