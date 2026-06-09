"""Q.167.I — guard de fidelidade do copiloto não confunde a palavra comum
"produção" com o material 'Gel generico, só para efeitos de custos de produção'.

Antes: a estratégia 2 (retrieval) extraía o token "produção" do nome do material
e fazia substring na pergunta → QUALQUER pergunta com "produção" abstinha por
falso-match de material. Agora os termos genéricos de domínio são filtrados.
"""

from src.copilot.cube.measure_contract import (
    _discriminative_material_tokens,
    extract_mentioned_material,
)

_GEL = "Gel generico, só para efeitos de custos de produção"


def test_discriminative_tokens_drops_generic_terms():
    # Nome só com termos genéricos (generico/efeitos/custos/produção) e "gel"
    # (3 chars, abaixo do limiar) → nenhum token distintivo.
    assert _discriminative_material_tokens(_GEL) == []


def test_discriminative_tokens_keeps_real_material_words():
    toks = _discriminative_material_tokens("Resina epoxy SR8100")
    assert "resina" in toks
    assert "epoxy" in toks


def test_producao_question_does_not_flag_gel_material():
    """A regressão: top-1 é o gel (score alto) mas a pergunta é sobre
    produção por disciplina — não deve detectar material nenhum."""
    out = extract_mentioned_material(
        "produção por disciplina por mês",
        top_materials=[(_GEL, 0.9)],
    )
    assert out is None


def test_real_material_still_detected():
    """Não-regressão: um material real continua a ser detectado quando o seu
    token distintivo aparece na pergunta."""
    out = extract_mentioned_material(
        "consumo de resina epoxy este mês",
        top_materials=[("Resina epoxy SR8100", 0.9)],
    )
    assert out == "Resina epoxy SR8100"
