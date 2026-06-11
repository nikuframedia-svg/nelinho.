r"""Q.173.AM — Golden NL→Cube query suite.

10 perguntas reais PT-PT → query Cube ESPERADA. Exercita o interpret() real
com Ollama LIVE. Marcados para skip automático quando Ollama não responde.

Asserções: measures + (opcionalmente) filtros e período escolhidos —
NÃO ao texto da narração (não-determinístico).

Se o interpret escolher mal uma pergunta → BUG real: a asserção falha
e o diagnóstico deve ir para o cube_interpret.md (ciclo previsto).

Uso:
    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\.venv\Scripts\python.exe -m pytest tests/copilot/test_golden_cube_queries_q173am.py -v
    # ou sem stack:
    .\.venv\Scripts\python.exe -m pytest tests/copilot/test_golden_cube_queries_q173am.py -v -m "not live"
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import pytest

from src.copilot.cube.client import CubeCatalog, CubeClient
from src.copilot.cube.interpret import interpret
from src.copilot.cube.material_retrieval import INDEX_NPZ_PATH, MaterialIndex
from src.copilot.cube.measure_retrieval import MeasureIndex, MEASURE_INDEX_NPZ_PATH
from src.copilot.ollama_client import OllamaClient


# ────────────────────────────── Detecção de stack ──────────────────────────────


def _ollama_available() -> bool:
    """Ollama UP em :11434 + índice FAISS no disco."""
    try:
        ok = httpx.get("http://localhost:11434/api/tags", timeout=2.0).status_code == 200
        ok &= MEASURE_INDEX_NPZ_PATH.exists()
        ok &= INDEX_NPZ_PATH.exists()
        return ok
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama (:11434) ou FAISS index não disponível — skip live",
)


def _fake_catalog() -> CubeCatalog:
    """Catálogo mínimo offline — os live tests chamam o Cube real."""
    return CubeCatalog(cubes=[], measures=[], dimensions=[])


# ────────────────────────────── Golden cases ──────────────────────────────


@dataclass
class GoldenCase:
    """Um caso golden NL→Cube.

    measures_expected: subset de measures que devem aparecer na query.
    abstain_expected: True se a resposta DEVE ser abstain (perguntas fora do catálogo).
    filter_member: se especificado, pelo menos um filtro deve ter este member.
    """
    qid: int
    question: str
    measures_expected: list[str] = field(default_factory=list)
    abstain_expected: bool = False
    filter_member: str | None = None
    # Período esperado: "hoje" | "mes_passado" | "este_ano" | None (qualquer)
    period_label: str | None = None


GOLDEN_CASES: list[GoldenCase] = [
    # 1. Faturação mês — comercial_facturacao.total com período
    GoldenCase(
        qid=1,
        question="Qual foi a faturação em Abril de 2026?",
        measures_expected=["comercial_facturacao.total"],
        period_label=None,  # período absoluto — não usa period_label
    ),
    # 2. OFs fechadas hoje — producao_ofs_fechadas_dia.total
    GoldenCase(
        qid=2,
        question="Quantas OFs foram produzidas hoje?",
        measures_expected=["producao_ofs_fechadas_dia.total"],
        period_label="hoje",
    ),
    # 3. Taxa de defeitos — qualidade.taxa_defeitos
    GoldenCase(
        qid=3,
        question="Qual a taxa de defeitos na laminagem em Março de 2026?",
        measures_expected=["qualidade.taxa_defeitos"],
    ),
    # 4. Lead time mediano — producao_lead_time_of.lead_time_p50
    GoldenCase(
        qid=4,
        question="Qual o lead time mediano das OFs fechadas no mês passado?",
        measures_expected=["producao_lead_time_of.lead_time_p50"],
        period_label="mes_passado",
    ),
    # 5. OFs abertas (critério ERP) — producao_ofs_em_curso.total
    GoldenCase(
        qid=5,
        question="Quantas OFs abertas temos agora no sistema?",
        measures_expected=["producao_ofs_em_curso.total"],
    ),
    # 6. Consumo de material — consumo_material.consumo
    GoldenCase(
        qid=6,
        question="Quanto de Resina consumimos em Abril de 2026?",
        measures_expected=["consumo_material.consumo"],
        filter_member="consumo_material.material",
    ),
    # 7. Transportes — logistica_ofs_expedidas.total ou logistica_transportes.total
    GoldenCase(
        qid=7,
        question="Quantas OFs foram expedidas em 2024?",
        measures_expected=["logistica_ofs_expedidas.total"],
    ),
    # 8. Workforce — workforce_colaboradores.total ou workforce.colaboradores_activos.total
    GoldenCase(
        qid=8,
        question="Quantos colaboradores activos temos este mês?",
        measures_expected=["workforce_colaboradores.total"],
        period_label="este_mes",
    ),
    # 9. Top clientes — comercial_top_clientes.total
    GoldenCase(
        qid=9,
        question="Quais os 5 maiores clientes em 2024?",
        measures_expected=["comercial_top_clientes.total"],
        filter_member=None,  # limit pode ser na order, não em filter
    ),
    # 10. Throughput por modelo — producao_throughput_modelo.total
    GoldenCase(
        qid=10,
        question="Qual o throughput semanal por modelo em 2026?",
        measures_expected=["producao_throughput_modelo.total"],
    ),
    # 11. OFs em produção critério NELO — deve abstain (view não no Cube)
    GoldenCase(
        qid=11,
        question="Quantos barcos estão em produção pelo critério da NELO (operação aberta)?",
        # O critério NELO usa factory_raw.v_of_em_producao que não tem cube
        # → deve abstain OU retornar producao_ofs_em_curso.total (critério ERP)
        # Aceitamos qualquer uma das duas (o interpret pode escolher o ERP como aproximação)
        measures_expected=[],  # qualquer resultado é válido — o que importa é não inventar cube
        abstain_expected=False,  # pode ou não abstrair
    ),
    # 12. Porquê — deve abstain (causal)
    GoldenCase(
        qid=12,
        question="Porque é que a taxa de defeitos subiu na pintura em Maio?",
        measures_expected=[],
        abstain_expected=True,
    ),
]


# ────────────────────────────── Fixtures e helpers ──────────────────────────────


async def _run_interpret(case: GoldenCase) -> tuple[bool, list[str], str | None, str | None]:
    """Corre interpret() real para o caso e devolve (abstain, measures, period_label, reason)."""
    ollama = OllamaClient()
    cube_client = CubeClient()
    mat_index = MaterialIndex.get()
    meas_index = MeasureIndex.get()
    try:
        catalog = await cube_client.fetch_meta()
        result = await interpret(
            question=case.question,
            catalog=catalog,
            material_index=mat_index,
            ollama=ollama,
            measure_index=meas_index,
        )
        measures = result.query.measures if result.query else []
        return result.abstain, measures, result.period_label, result.reason
    finally:
        await ollama.close()
        await cube_client.close()


# ────────────────────────────── Testes LIVE ──────────────────────────────


@requires_ollama
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[f"q{c.qid}" for c in GOLDEN_CASES])
async def test_golden_nl_to_cube(case: GoldenCase) -> None:
    """Pergunta PT → interpret() → measures/filtros esperados.

    Falha se o interpret escolher a measure errada (bug real do pipeline).
    Não falha se abstiver de forma correcta quando abstain_expected=True.
    """
    abstain, measures, period_label_got, reason = await _run_interpret(case)

    if case.abstain_expected:
        assert abstain, (
            f"Q{case.qid}: esperava abstain para pergunta causal/fora-catálogo "
            f"mas got measures={measures!r}, period_label={period_label_got!r}"
        )
        return

    # Para casos não-causal: o interpret não deve abstrair e deve incluir as measures esperadas.
    if case.measures_expected:
        assert not abstain, (
            f"Q{case.qid}: interpret absteve quando não devia. Reason: {reason!r}. "
            f"Medidas esperadas: {case.measures_expected}. "
            "Verifica o bloco correspondente em cube_interpret.md."
        )
        for m in case.measures_expected:
            assert m in measures, (
                f"Q{case.qid}: measure esperada {m!r} ausente. "
                f"Measures escolhidas: {measures!r}. "
                f"Reason: {reason!r}. "
                "Verifica os synonyms e o bloco do cube em cube_interpret.md."
            )

    if case.period_label is not None:
        assert period_label_got == case.period_label, (
            f"Q{case.qid}: period_label={period_label_got!r} mas esperava {case.period_label!r}. "
            "Verifica a regra 3 do cube_interpret.md."
        )


# ────────────────────────────── Testes offline (sem Ollama) ──────────────────────────────


def test_golden_cases_completeness() -> None:
    """Verifica que temos pelo menos 10 casos golden definidos."""
    non_abstain = [c for c in GOLDEN_CASES if not c.abstain_expected]
    assert len(non_abstain) >= 10, (
        f"Preciso de ≥10 casos com measures esperadas, tenho {len(non_abstain)}"
    )


def test_all_expected_measures_exist_in_registry() -> None:
    """Todas as measures nos casos golden existem no MEASURE_REGISTRY."""
    from src.copilot.cube.measure_contract import MEASURE_REGISTRY
    for case in GOLDEN_CASES:
        for m in case.measures_expected:
            assert m in MEASURE_REGISTRY, (
                f"Q{case.qid}: medida {m!r} não existe no MEASURE_REGISTRY. "
                "Actualiza o golden case ou o MEASURE_REGISTRY."
            )


def test_no_duplicate_qids() -> None:
    """Todos os qid dos casos golden são únicos."""
    qids = [c.qid for c in GOLDEN_CASES]
    assert len(qids) == len(set(qids)), "qid duplicado nos golden cases"
