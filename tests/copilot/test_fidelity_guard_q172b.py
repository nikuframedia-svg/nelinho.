"""Q.172.B — fidelity guard com cobertura por tokens distintivos.

O guard exigia que o filtro de material fosse EXACTAMENTE o top-1 do
retrieval — materiais vizinhos do catálogo ('Resina Lavesan EN 720' vs
'Mistura Epoxy Lavesan EN 720') empatam no índice e o copiloto abstinha
em perguntas legítimas. A relaxação aceita filtros nomeados NA PERGUNTA;
o reviewer apanhou o furo da 1ª versão (EN 480 passava numa pergunta
sobre EN 720 porque números de 3 chars ficavam fora do regex) — agora
TODOS os números do valor filtrado têm de aparecer na pergunta.
"""
from __future__ import annotations

from src.copilot.cube.measure_contract import assert_question_coverage
from src.copilot.cube.query import CubeFilter, CubeQuery

_Q = "Quanto consumimos de Resina Lavesan EN 720 em Abril de 2026?"


def _query_filtering(material: str) -> CubeQuery:
    return CubeQuery(
        measures=["consumo_material.consumo"],
        dimensions=["consumo_material.unidade_id"],
        filters=[CubeFilter(
            member="consumo_material.material",
            operator="equals",
            values=[material],
        )],
    )


def test_sinonimo_do_catalogo_nomeado_na_pergunta_passa():
    """top-1 do retrieval é OUTRO material, mas a query filtra o material
    que a pergunta nomeia → fidelidade OK (era o falso-positivo)."""
    violations = assert_question_coverage(
        _query_filtering("Resina Lavesan EN 720"),
        material_mencionado="Prepreg 400 (42% resina)",  # top-1 errado
        question=_Q,
    )
    assert violations == []


def test_variante_numerica_diferente_e_recusada():
    """Caso adversarial do reviewer: EN 480 NÃO pode passar numa pergunta
    sobre EN 720 — o número é a parte distintiva da variante."""
    violations = assert_question_coverage(
        _query_filtering("Resina Lavesan EN 480"),
        material_mencionado="Prepreg 400 (42% resina)",
        question=_Q,
    )
    assert violations, "filtrar a variante errada tem de abster"


def test_material_sem_relacao_e_recusado():
    violations = assert_question_coverage(
        _query_filtering("Gelcoat ISO NPG"),
        material_mencionado="Resina Lavesan EN 720",
        question=_Q,
    )
    assert violations


def test_mistura_vizinha_com_numero_extra_e_recusada():
    """'Mistura ... L31/DL' partilha 'lavesan' e '720' mas traz '31' que a
    pergunta não menciona → é outro produto, recusa."""
    violations = assert_question_coverage(
        _query_filtering("Mistura Epoxy Lavesan EN 720 + L31/DL"),
        material_mencionado="Prepreg 400 (42% resina)",
        question=_Q,
    )
    assert violations


def test_sem_question_mantem_comportamento_antigo():
    """question=None (callers antigos) → só o match com material_mencionado."""
    violations = assert_question_coverage(
        _query_filtering("Resina Lavesan EN 720"),
        material_mencionado="Resina Lavesan EN 720",
    )
    assert violations == []


def test_substring_numerica_e_recusada():
    """Reviewer 2ª volta: 'EN 72' não pode casar com 'EN 720' por substring
    — números exigem word-boundary."""
    violations = assert_question_coverage(
        _query_filtering("Resina Lavesan EN 72"),
        material_mencionado="Prepreg 400 (42% resina)",
        question=_Q,
    )
    assert violations, "'72' não é '720' — variante diferente tem de abster"


def test_valor_sem_numeros_nao_passa_por_um_token_generico():
    """Reviewer 2ª volta: valor SEM números não pode passar vacuamente só
    por partilhar 1 token ('lavesan') — exige maioria dos tokens alfa."""
    violations = assert_question_coverage(
        _query_filtering("Gelcoat Lavesan Azul"),
        material_mencionado="Prepreg 400 (42% resina)",
        question=_Q,
    )
    assert violations
