"""Q.93.C — testes do pipeline `/ask-cube` (Cube Fase 2).

Testes unitários (offline, sem Cube/Ollama) + casos LIVE marcados que
exigem o stack todo a correr. Em CI sem Docker, os LIVE serão skip via
`pytest -m "not live"`.

Casos cobertos:
    1. anchor end-to-end (LIVE)
    2. armadilha da unidade (LIVE)
    3. sinónimos (LIVE)
    4. fora-catálogo (offline com fake LLM)
    5. resultado vazio (LIVE)
    6. guard rejeita alucinação (offline)
    7. validador anti-soma-cega (unit puro)
"""
from __future__ import annotations

import httpx
import pytest

from src.copilot.cube.client import CubeCatalog, CubeResult
from src.copilot.cube.narrate import guard_numbers
from src.copilot.cube.query import CubeQuery, validate_against_catalog


# ────────────────────────────── Helpers ──────────────────────────────


class _NoMeasureIndex:
    """Stub de MeasureIndex que força o degrade Q.104 (todas as medidas no
    enum) — torna os testes offline herméticos ao artefacto de runtime
    `cube/data/measure_index.*`. Sem isto, o measure-retrieval real tentaria
    embeddings via o FakeOllama (que não os simula) e o interpret abster-se-ia
    com "nenhuma medida bate". O degrade é o estado de CI (índice gitignored).
    """

    def load(self) -> None:
        from src.copilot.cube.measure_retrieval import MeasureIndexNotBuilt

        raise MeasureIndexNotBuilt("degrade Q.104 (teste hermético)")

    async def top_k_hybrid(self, *args, **kwargs):  # pragma: no cover - defensivo
        from src.copilot.cube.measure_retrieval import MeasureIndexNotBuilt

        raise MeasureIndexNotBuilt("degrade Q.104 (teste hermético)")


def _fake_catalog() -> CubeCatalog:
    return CubeCatalog.model_validate(
        {
            "cubes": [
                {
                    "name": "consumo_material",
                    "measures": [
                        {"name": "consumo_material.consumo", "type": "number"},
                        {"name": "consumo_material.n_movimentos", "type": "number"},
                    ],
                    "dimensions": [
                        {"name": "consumo_material.data", "type": "time"},
                        {"name": "consumo_material.material", "type": "string"},
                        {"name": "consumo_material.unidade_id", "type": "number"},
                    ],
                }
            ]
        }
    )


class FakeOllama:
    """Mock de OllamaClient para testes offline.

    `chat_responses` é consumido FIFO. `embeddings_response` é fixo.
    """

    def __init__(
        self,
        chat_responses: list[str] | None = None,
        embedding: list[float] | None = None,
    ) -> None:
        self._chat_responses = list(chat_responses or [])
        self._embedding = embedding or [0.1] * 768

    async def chat(self, prompt, model, format=None, history=None, system_prompt=None):
        if not self._chat_responses:
            raise RuntimeError("FakeOllama: chat_responses esgotada")
        next_resp = self._chat_responses.pop(0)
        return {"content": next_resp}

    async def embeddings(self, text, model):
        return list(self._embedding)

    async def health_check(self) -> bool:
        return True

    def reset_circuit_breaker(self) -> None:
        pass


def _live_stack_available() -> bool:
    """Cube REST UP em :4000 + Ollama UP em :11434 + index FAISS no disco."""
    try:
        ok = httpx.get("http://localhost:4000/readyz", timeout=2.0).status_code == 200
        ok &= httpx.get("http://localhost:11434/api/tags", timeout=2.0).status_code == 200
        from src.copilot.cube.material_retrieval import INDEX_NPZ_PATH
        ok &= INDEX_NPZ_PATH.exists()
        return ok
    except Exception:
        return False


requires_live = pytest.mark.skipif(
    not _live_stack_available(),
    reason="LIVE stack (Cube + Ollama + FAISS index) não disponível",
)


# ────────────────────────────── 7. Validador anti-soma-cega (unit puro) ──────────────────────────────


def test_validate_against_catalog_blocks_blind_sum():
    """filter `contains` em material SEM dimensions=[material, unidade_id] = violação."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=[],  # sem agrupamento → soma cega
        filters=[
            {
                "member": "consumo_material.material",
                "operator": "contains",
                "values": ["resina"],
            }
        ],
    )
    violations = validate_against_catalog(q, catalog)
    assert any("anti-soma-cega" not in v for v in violations)  # mensagem em PT
    assert any("unidades diferentes" in v for v in violations)


def test_validate_against_catalog_allows_equals_without_grouping():
    """filter `equals` exacto não exige agrupamento (universo já fechado)."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        filters=[
            {
                "member": "consumo_material.material",
                "operator": "equals",
                "values": ["Resina Lavesan EN 720"],
            }
        ],
    )
    assert validate_against_catalog(q, catalog) == []


def test_validate_against_catalog_unknown_measure():
    catalog = _fake_catalog()
    q = CubeQuery(measures=["consumo_material.oee"])
    violations = validate_against_catalog(q, catalog)
    assert any("oee" in v for v in violations)


def test_validate_against_catalog_contains_with_grouping_passes():
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=[
            "consumo_material.material",
            "consumo_material.unidade_id",
        ],
        filters=[
            {
                "member": "consumo_material.material",
                "operator": "contains",
                "values": ["resina"],
            }
        ],
    )
    assert validate_against_catalog(q, catalog) == []


# ────────────────────────────── Q.95.1 — anti-soma-cega geral (filters=[] / sem equals) ──────────────────────────────


def test_q95_1_blocks_blind_sum_without_filter():
    """Q.95.1 c03: measure=consumo, dims=[], filters=[] → soma cega sobre todas
    as unidades. Tem de violar (anti-soma-cega geral, não só `contains`)."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=[],
        filters=[],
        time_dimensions=[
            {"dimension": "consumo_material.data",
             "dateRange": ["2026-04-01", "2026-04-30"]}
        ],
    )
    violations = validate_against_catalog(q, catalog)
    assert violations, (
        "esperado violação anti-soma-cega para filters=[] sem unidade_id"
    )
    assert any("soma cega" in v.lower() or "unidade física" in v.lower()
               for v in violations)


def test_q95_1_allows_equals_material_without_unidade_id():
    """Q.95.1 c01: filter equals material + dims=[] + measure=consumo → ACCEPT.
    Material único = unidade única implícita (assumpção histórica preservada)."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=[],
        filters=[
            {"member": "consumo_material.material",
             "operator": "equals",
             "values": ["Resina Lavesan EN 720"]}
        ],
    )
    assert validate_against_catalog(q, catalog) == []


def test_q95_1_allows_no_filter_with_unidade_id_grouping():
    """Q.95.1: filters=[] mas com unidade_id em dims → ACCEPT.
    O Cube vai separar por unidade — sem soma cega."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=["consumo_material.unidade_id"],
        filters=[],
    )
    assert validate_against_catalog(q, catalog) == []


def test_q95_1_contains_with_grouping_still_passes():
    """Q.95.1 c08: contains + dims=[material, unidade_id] continua a passar.
    Regression guard — Q.95.1 não pode partir o caso histórico."""
    catalog = _fake_catalog()
    q = CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=[
            "consumo_material.material",
            "consumo_material.unidade_id",
        ],
        filters=[
            {"member": "consumo_material.material",
             "operator": "contains",
             "values": ["resina"]}
        ],
    )
    assert validate_against_catalog(q, catalog) == []


# ────────────────────────────── Q.95.1 — medida derivada inexistente (c07) ──────────────────────────────


def test_q95_1_detect_derived_measure_preco_por_kg():
    """Q.95.1 c07: 'preço por kg' bate o detector de medidas derivadas."""
    from src.copilot.cube.measure_contract import (
        is_derived_measure_request as _detect_derived_measure_request,
    )

    assert _detect_derived_measure_request(
        "Qual o preço por kg da Resina Lavesan EN 720?"
    ) is not None


def test_q95_1_detect_derived_measure_racio():
    from src.copilot.cube.measure_contract import (
        is_derived_measure_request as _detect_derived_measure_request,
    )

    assert _detect_derived_measure_request(
        "Qual o rácio custo/consumo da Acetona?"
    ) is not None


def test_q95_1_detect_derived_measure_quanto_sai_cada_kg():
    from src.copilot.cube.measure_contract import (
        is_derived_measure_request as _detect_derived_measure_request,
    )

    assert _detect_derived_measure_request(
        "Quanto sai cada kg de Resina Lavesan EN 720?"
    ) is not None


def test_q95_1_detect_derived_measure_does_not_fire_on_legitimate():
    """Regression guard: 'custo total', 'custo de X', 'consumo' legítimos
    NÃO podem bater o detector (falsos positivos quebrariam c01/c02/c08)."""
    from src.copilot.cube.measure_contract import (
        is_derived_measure_request as _detect_derived_measure_request,
    )

    assert _detect_derived_measure_request(
        "Quanto custou a Resina Lavesan EN 720 em Abril?"
    ) is None
    assert _detect_derived_measure_request(
        "Custo total de matéria-prima em Abril?"
    ) is None
    assert _detect_derived_measure_request(
        "Quanto consumimos de catalisador peróxido em Abril?"
    ) is None
    assert _detect_derived_measure_request(
        "Quanto gastámos de Resina Lavesan EN 720 em Abril?"
    ) is None


@pytest.mark.asyncio
async def test_q95_1_interpret_abstains_on_preco_por_kg():
    """Q.95.1 c07 end-to-end (offline): pergunta com 'preço por kg' faz
    interpret() abstain ANTES de chamar o LLM. O FakeOllama nunca é tocado
    (chat_responses vazia confirmaria, mas a defesa corre primeiro)."""
    from src.copilot.cube.interpret import interpret

    fake = FakeOllama(chat_responses=[])  # vazia: se for chamada, RuntimeError

    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return []

        async def top_k_hybrid(self, q, ollama, k=10):
            return []

    result = await interpret(
        "Qual o preço por kg da Resina Lavesan EN 720?",
        catalog=_fake_catalog(),
        material_index=StubIndex(),  # type: ignore[arg-type]
        ollama=fake,  # type: ignore[arg-type]
    )
    assert result.abstain is True
    assert result.query is None
    assert "derivada" in result.reason.lower() or "preço" in result.reason.lower()


# ────────────────────────────── 10. Q.93.D.bis Etapa C.1 — REVERTIDO (validador material) ──────────────────────────────
# A Etapa C.1 (validador "valor de filter material TEM de bater top-k") foi REVERTIDA
# após causar 4 regressões na medição (q02 gelcoat / q04 acetona / q07 cola / q10 divinycell).
# Causa raiz: o retrieval FAISS retorna top-10 pobre para perguntas comuns — rejeita
# materiais legítimos por causa de top-k fraco, não por má escolha do LLM.
# Ver agent_docs/q93_d_bis_placar.md (Etapa C) e q93_d_bis_retrieval_diagnose.txt.


# ────────────────────────────── 9. Q.93.D.bis Etapa B — period_label sobrepõe dateRange ──────────────────────────────


@pytest.mark.asyncio
async def test_interpret_overrides_daterange_for_known_period_label():
    """Q.93.D.bis Etapa B: LLM devolve period_label='ontem' com dateRange errado;
    código sobrepõe pelo dia anterior real (today=2026-05-26 → 2026-05-25).
    """
    import datetime as _dt

    from src.copilot.cube.interpret import interpret

    fake = FakeOllama(
        chat_responses=[
            '{"abstain": false, "reason": "", "period_label": "ontem", '
            '"query": {"measures": ["consumo_material.consumo"], '
            '"dimensions": ["consumo_material.material", "consumo_material.unidade_id"], '
            '"filters": [], '
            '"timeDimensions": [{"dimension": "consumo_material.data", '
            '"dateRange": ["2026-05-26", "2026-05-26"]}], '  # LLM "errou" — hoje em vez de ontem
            '"order": []}}'
        ]
    )

    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return [("fake", 0.5)]

    today = _dt.date(2026, 5, 26)
    result = await interpret(
        "Quanto consumimos ontem?",
        catalog=_fake_catalog(),
        material_index=StubIndex(),  # type: ignore[arg-type]
        ollama=fake,  # type: ignore[arg-type]
        today=today,
        measure_index=_NoMeasureIndex(),  # hermético: degrade Q.104 (sem disco)
    )
    assert result.abstain is False
    assert result.query is not None
    assert result.period_label == "ontem"
    td = result.query.time_dimensions[0]
    assert td.date_range == ["2026-05-25", "2026-05-25"], (
        f"esperado override para [2026-05-25, 2026-05-25], got {td.date_range}"
    )


@pytest.mark.asyncio
async def test_interpret_keeps_daterange_when_no_period_label():
    """Q.93.D.bis Etapa B: sem period_label, o dateRange do LLM passa intacto."""
    import datetime as _dt

    from src.copilot.cube.interpret import interpret

    fake = FakeOllama(
        chat_responses=[
            '{"abstain": false, "reason": "", '
            '"query": {"measures": ["consumo_material.consumo"], '
            '"dimensions": ["consumo_material.unidade_id"], '
            '"filters": [{"member": "consumo_material.material", '
            '"operator": "equals", "values": ["Resina Lavesan EN 720"]}], '
            '"timeDimensions": [{"dimension": "consumo_material.data", '
            '"dateRange": ["2026-03-01", "2026-03-31"]}], '
            '"order": []}}'
        ]
    )

    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return [("Resina Lavesan EN 720", 0.95)]

    today = _dt.date(2026, 5, 26)
    result = await interpret(
        "Quanto consumimos de Resina Lavesan EN 720 em Março de 2026?",
        catalog=_fake_catalog(),
        material_index=StubIndex(),  # type: ignore[arg-type]
        ollama=fake,  # type: ignore[arg-type]
        today=today,
        measure_index=_NoMeasureIndex(),  # hermético: degrade Q.104 (sem disco)
    )
    assert result.abstain is False
    assert result.query is not None
    assert result.period_label is None
    td = result.query.time_dimensions[0]
    # dateRange do LLM tem de ficar intacto.
    assert td.date_range == ["2026-03-01", "2026-03-31"]


@pytest.mark.asyncio
async def test_interpret_keeps_daterange_for_unknown_period_label():
    """Q.93.D.bis Etapa B: period_label fora da whitelist → dateRange do LLM intacto."""
    import datetime as _dt

    from src.copilot.cube.interpret import interpret

    fake = FakeOllama(
        chat_responses=[
            '{"abstain": false, "reason": "", "period_label": "amanha", '
            '"query": {"measures": ["consumo_material.consumo"], '
            '"dimensions": ["consumo_material.material", "consumo_material.unidade_id"], '
            '"filters": [], '
            '"timeDimensions": [{"dimension": "consumo_material.data", '
            '"dateRange": ["2026-05-01", "2026-05-05"]}], '
            '"order": []}}'
        ]
    )

    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return [("fake", 0.5)]

    today = _dt.date(2026, 5, 26)
    result = await interpret(
        "Quanto se gastou no início do mês?",
        catalog=_fake_catalog(),
        material_index=StubIndex(),  # type: ignore[arg-type]
        ollama=fake,  # type: ignore[arg-type]
        today=today,
    )
    assert result.query is not None
    td = result.query.time_dimensions[0]
    # "amanha" não está na whitelist; dateRange do LLM passa intacto.
    assert td.date_range == ["2026-05-01", "2026-05-05"]


def test_resolve_period_label_known_and_unknown():
    """Unit puro: _resolve_period_label devolve range correcto para conhecidos
    e None para desconhecidos.
    """
    import datetime as _dt

    from src.copilot.cube.interpret import _resolve_period_label

    today = _dt.date(2026, 5, 26)  # terça-feira

    # Ontem.
    assert _resolve_period_label("ontem", today) == ("2026-05-25", "2026-05-25")
    # Hoje.
    assert _resolve_period_label("hoje", today) == ("2026-05-26", "2026-05-26")
    # Mês passado (Abril 2026): 2026-04-01 a 2026-04-30.
    assert _resolve_period_label("mes_passado", today) == ("2026-04-01", "2026-04-30")
    # Esta semana (terça → 2026-05-25..2026-05-31): _resolve devolve a semana toda.
    start, end = _resolve_period_label("esta_semana", today)
    assert start == "2026-05-25"  # segunda-feira da semana corrente
    assert end == "2026-05-31"    # domingo (end_exclusivo - 1 dia)
    # inicio_do_mes (Q.93.E.C.3): primeiros 7 dias do mês corrente.
    assert _resolve_period_label("inicio_do_mes", today) == ("2026-05-01", "2026-05-07")
    # Desconhecido (fora da whitelist).
    assert _resolve_period_label("amanha", today) is None
    assert _resolve_period_label("qualquer_coisa_invalida", today) is None


# ────────────────────────────── 8. Q.93.D.bis Etapa A — gate "ambiguous" (>20 rows) ──────────────────────────────


@pytest.mark.asyncio
async def test_ambiguous_when_data_exceeds_threshold():
    """Q.93.D.bis Etapa A: Cube devolve >MAX_NARRATION_ROWS → status="ambiguous",
    narração não é chamada, data truncado a 10 linhas, warning explícito.
    """
    from src.copilot.routers.ask_cube import MAX_NARRATION_ROWS, _process

    n_rows = MAX_NARRATION_ROWS + 5
    fake_rows = [
        {
            "consumo_material.material": f"Material {i}",
            "consumo_material.unidade_id": 12.0,
            "consumo_material.consumo": float(i),
        }
        for i in range(n_rows)
    ]

    class FakeCube:
        async def fetch_meta(self):
            return _fake_catalog()

        async def load(self, payload):
            return CubeResult.model_validate(
                {"data": fake_rows, "annotation": {}, "query": payload}
            )

        async def close(self):
            pass

    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return [("Material 0", 0.9)]

    # InterpretResult devolvido pelo FakeOllama: query sem material — só dimensões.
    fake_llm = FakeOllama(
        chat_responses=[
            '{"abstain": false, "reason": "", "query": {'
            '"measures": ["consumo_material.consumo"], '
            '"dimensions": ["consumo_material.material", "consumo_material.unidade_id"], '
            '"filters": [], '
            '"timeDimensions": [{"dimension": "consumo_material.data", '
            '"dateRange": ["2026-05-01", "2026-05-26"]}], '
            '"order": []}}'
        ]
    )

    # StubMeasureIndex: score > MEASURE_RETRIEVAL_THRESHOLD (0.02) para que
    # o interpret não faça abstain antes de chegar ao LLM. O FakeOllama tem
    # exactamente 1 chat_response — se o StubMeasureIndex devolver score
    # fraco, o interpret abstém antes de chamar o LLM e o teste falha.
    class StubMeasureIndex:
        def load(self) -> None:
            pass

        async def top_k_hybrid(self, q, ollama, k=5):
            return [("consumo_material.consumo", 0.9)]

    resp = await _process(
        "Como está o consumo?",
        cube=FakeCube(),  # type: ignore[arg-type]
        ollama=fake_llm,  # type: ignore[arg-type]
        material_index=StubIndex(),  # type: ignore[arg-type]
        measure_index=StubMeasureIndex(),  # type: ignore[arg-type]
    )

    assert resp.status == "ambiguous", f"got {resp.status} (warnings={resp.warnings})"
    assert len(resp.data) == 10, f"data devia ter 10 linhas (truncado), got {len(resp.data)}"
    assert resp.warnings, "warnings não pode estar vazio"
    assert "truncado" in resp.warnings[0].lower()
    assert resp.narration is not None and str(n_rows) in resp.narration


def test_max_narration_rows_constant_present():
    """Guard: o threshold tem de existir como constante (não pode ser hard-coded inline)."""
    from src.copilot.routers.ask_cube import MAX_NARRATION_ROWS

    assert isinstance(MAX_NARRATION_ROWS, int)
    assert MAX_NARRATION_ROWS > 0


# ────────────────────────────── 6. Guard rejeita alucinação (offline) ──────────────────────────────


def test_guard_rejects_unsupported_number():
    """Payload tem 4.7236; texto inventa 50 → guard rejeita."""
    result = CubeResult.model_validate(
        {
            "data": [{"consumo_material.consumo": 4.7236}],
            "annotation": {},
            "query": {},
        }
    )
    text = "Consumimos 50 tambores este mês."  # 50 não está no payload
    ok, unsupported = guard_numbers(text, result)
    assert not ok
    assert 50.0 in unsupported


def test_guard_accepts_rounded_number():
    """Payload tem 4.7236; texto diz 4.72 → guard aceita (delta < 1%)."""
    result = CubeResult.model_validate(
        {
            "data": [{"consumo_material.consumo": 4.7236}],
            "annotation": {},
            "query": {},
        }
    )
    text = "Consumimos 4.72 unidades."
    ok, unsupported = guard_numbers(text, result)
    assert ok, f"esperado ok=True, mas unsupported={unsupported}"


def test_guard_accepts_numbers_inside_material_names():
    """`Resina Lavesan EN 720` no nome do material → "720" no texto é OK."""
    result = CubeResult.model_validate(
        {
            "data": [
                {
                    "consumo_material.material": "Resina Lavesan EN 720",
                    "consumo_material.consumo": 4.72,
                }
            ],
            "annotation": {},
            "query": {},
        }
    )
    text = "Consumimos 4.72 unidades de Resina Lavesan EN 720."
    ok, unsupported = guard_numbers(text, result)
    assert ok, f"esperado ok=True, mas unsupported={unsupported}"


def test_guard_accepts_numbers_in_filter_values():
    """Quando o material está só no filter (não em dimensions), o nome ainda
    conta como contexto e o '720' é suportado."""
    result = CubeResult.model_validate(
        {
            "data": [
                {
                    "consumo_material.unidade_id": 18.0,
                    "consumo_material.consumo": 4.72,
                }
            ],
            "annotation": {},
            "query": {
                "filters": [
                    {
                        "member": "consumo_material.material",
                        "operator": "equals",
                        "values": ["Resina Lavesan EN 720"],
                    }
                ]
            },
        }
    )
    text = "Consumimos 4.72 unidades de Resina Lavesan EN 720 (unidade 18)."
    ok, unsupported = guard_numbers(text, result)
    assert ok, f"esperado ok=True, mas unsupported={unsupported}"


# ────────────────────────────── 4. Fora-catálogo (offline) ──────────────────────────────


@pytest.mark.asyncio
async def test_interpret_abstains_for_out_of_catalog_question():
    """LLM (fake) devolve abstain — interpret deve passar tal qual."""
    from src.copilot.cube.interpret import interpret
    from src.copilot.cube.material_retrieval import MaterialIndex

    # FakeOllama devolve um JSON com abstain=true.
    fake = FakeOllama(
        chat_responses=[
            '{"abstain": true, "reason": "OEE não está no catálogo.", "query": null}'
        ]
    )

    # MaterialIndex precisa de embeddings — vamos passar um stub que devolve
    # um vector fixo e index vazio (1 elemento mocked).
    class StubIndex:
        async def top_k(self, q, ollama, k=10):
            return [("fake-material", 0.5)]

    result = await interpret(
        "Qual o OEE da máquina 3 esta semana?",
        catalog=_fake_catalog(),
        material_index=StubIndex(),  # type: ignore[arg-type]
        ollama=fake,  # type: ignore[arg-type]
    )
    assert result.abstain is True
    assert result.query is None
    assert "catálogo" in result.reason.lower() or "oee" in result.reason.lower()


# ────────────────────────────── 1, 2, 3, 5. LIVE end-to-end ──────────────────────────────


@requires_live
@pytest.mark.asyncio
async def test_anchor_end_to_end_returns_4_724():
    """Anchor: 'Resina Lavesan EN 720 em Abril 2026' → narração com 4.72(4)."""
    from src.copilot.routers.ask_cube import _process

    resp = await _process("Quanto consumimos de Resina Lavesan EN 720 em Abril de 2026?")
    assert resp.status == "ok", f"esperado ok, got {resp.status}: {resp.warnings}"
    assert resp.narration is not None
    # Aceita "4.724" ou "4.72" (arredondamento).
    assert "4.72" in resp.narration, (
        f"narração não menciona 4.72: {resp.narration!r}"
    )
    # data tem 1 linha com unidade_id=18.
    assert len(resp.data) >= 1
    assert any(int(row.get("consumo_material.unidade_id", -1)) == 18 for row in resp.data)


@requires_live
@pytest.mark.asyncio
async def test_unit_trap_does_not_blind_sum():
    """'quanto de resina?' → NUNCA o número ~2413 (soma cega das 9 linhas)."""
    from src.copilot.routers.ask_cube import _process

    resp = await _process("Quanto de resina gastámos em Abril de 2026?")
    # Aceita ok ou guard_failed (guard pode rejeitar uma narração imperfeita
    # do LLM em ambíguos — desde que NÃO devolva soma cega ~2413).
    assert resp.status in {"ok", "guard_failed", "abstain"}
    # Múltiplas linhas separadas por (material, unidade_id) — não soma cega.
    if resp.data:
        # Cube devolveu múltiplas linhas (a query incluiu dimensions=[material, unidade_id]).
        assert len(resp.data) >= 2, (
            f"esperado múltiplas linhas (anti-soma-cega), got {len(resp.data)}"
        )
    # Se houve narração, NÃO pode conter "2413" (a soma cega proibida).
    if resp.narration:
        assert "2413" not in resp.narration
        assert "2.413" not in resp.narration


@requires_live
@pytest.mark.asyncio
async def test_synonyms_match_consumo():
    """'Saiu para produção' = 'consumimos' = 'gastámos' — todos chegam à mesma medida."""
    from src.copilot.routers.ask_cube import _process

    resp = await _process(
        "Saiu para produção quanto de Resina Lavesan EN 720 em Abril de 2026?"
    )
    assert resp.status == "ok"
    assert resp.narration is not None
    assert "4.72" in resp.narration


@requires_live
@pytest.mark.asyncio
async def test_no_data_for_year_1900():
    """Período sem consumo → status=no_data + narração honesta."""
    from src.copilot.routers.ask_cube import _process

    resp = await _process(
        "Quanto consumimos de Resina Lavesan EN 720 em 1900?"
    )
    assert resp.status == "no_data"
    assert resp.narration is not None
    assert "não há dados" in resp.narration.lower()


@requires_live
@pytest.mark.asyncio
async def test_q93_d_bis_ambiguous_for_vague_question():
    """Q.93.D.bis Etapa A LIVE: 'Como está o consumo?' (q18 da Q.93.D) tem de
    devolver status="ambiguous", não inventar narração nem somar 385 linhas.
    """
    from src.copilot.routers.ask_cube import _process

    resp = await _process("Como está o consumo?")
    # O bug original era status="ok" com data=385 rows + narração de 80 linhas.
    # Honesto: ambiguous (gate >20), abstain (interpret recusa) ou no_data (LLM
    # interpretou "hoje" e Cube devolveu vazio). NÃO aceita "ok" gigante.
    assert resp.status in {"ambiguous", "abstain", "no_data"}, (
        f"esperado ambiguous|abstain|no_data, got {resp.status}: "
        f"data_len={len(resp.data)}  warnings={resp.warnings}"
    )
    # Em nenhum caso pode haver narração gigante (>500 chars = poluição).
    if resp.narration:
        assert len(resp.narration) < 500, (
            f"narração demasiado longa ({len(resp.narration)} chars) "
            "— bug do ensaio Q.93.D q18"
        )
    if resp.status == "ambiguous":
        assert len(resp.data) <= 10, f"data devia estar truncado, got {len(resp.data)}"
        assert resp.warnings, "warnings tinha de estar presente"


# ────────────────────── Q.156.B (LLM-1) — no_data para linha all-null ──────────────────────


def test_all_rows_effectively_empty_single_null_measure_row():
    """Q.156.B (LLM-1): [{measure: null}] é semanticamente no_data — o Cube
    devolve uma linha de nulls para um rácio sobre slice vazio."""
    from src.copilot.routers.ask_cube import _all_rows_effectively_empty

    rows = [{"qualidade.taxa_defeitos": None}]
    assert _all_rows_effectively_empty(rows, ["qualidade.taxa_defeitos"]) is True


def test_all_rows_not_empty_when_one_value_present():
    """Uma linha com valor real → NÃO é vazio (mesmo havendo nulls noutra)."""
    from src.copilot.routers.ask_cube import _all_rows_effectively_empty

    rows = [
        {"qualidade.taxa_defeitos": None},
        {"qualidade.taxa_defeitos": 0.062},
    ]
    assert _all_rows_effectively_empty(rows, ["qualidade.taxa_defeitos"]) is False


def test_all_rows_zero_is_not_empty():
    """Um `0.0` medido NÃO é vazio (é um zero real, não ausência de dados)."""
    from src.copilot.routers.ask_cube import _all_rows_effectively_empty

    rows = [{"ofs.fechadas_dia": 0.0}]
    assert _all_rows_effectively_empty(rows, ["ofs.fechadas_dia"]) is False


def test_all_rows_empty_for_empty_list():
    from src.copilot.routers.ask_cube import _all_rows_effectively_empty

    assert _all_rows_effectively_empty([], ["m"]) is True


# ────────────────────── Q.156.B (LLM-4) — aviso de mês em curso ──────────────────────


def test_partial_current_month_true_mid_month():
    """Range == mês de `today` e ainda não chegou ao fim → parcial."""
    import datetime as dt

    from src.copilot.cube.interpret import is_partial_current_month

    assert is_partial_current_month(
        ["2026-06-01", "2026-06-30"], dt.date(2026, 6, 2)
    ) is True


def test_partial_current_month_false_on_last_day():
    """No último dia do mês os dados já são completos (sem aviso)."""
    import datetime as dt

    from src.copilot.cube.interpret import is_partial_current_month

    assert is_partial_current_month(
        ["2026-06-01", "2026-06-30"], dt.date(2026, 6, 30)
    ) is False


def test_partial_current_month_false_for_past_month():
    """Mês passado fechado → sem aviso de parcialidade."""
    import datetime as dt

    from src.copilot.cube.interpret import is_partial_current_month

    assert is_partial_current_month(
        ["2026-05-01", "2026-05-31"], dt.date(2026, 6, 2)
    ) is False


def test_partial_current_month_false_for_empty_or_malformed_range():
    import datetime as dt

    from src.copilot.cube.interpret import is_partial_current_month

    assert is_partial_current_month([], dt.date(2026, 6, 2)) is False
    assert is_partial_current_month(None, dt.date(2026, 6, 2)) is False
    assert is_partial_current_month(["lixo"], dt.date(2026, 6, 2)) is False
