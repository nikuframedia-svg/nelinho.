"""Q.157.D — catálogo de measures gerado para o prompt do interpret.

O `cube_interpret.md` descreve à mão só ~14 dos 48 cubes do `MEASURE_REGISTRY`.
Quando o retrieval (Q.105.A) surge uma medida de um dos outros 34 cubes, o LLM
recebia-a no enum (constrained decoding) mas SEM bloco de catálogo a descrevê-la.

`render_catalog_block` gera esse bloco a partir do registry e o
`_filter_catalog_blocks` injecta-o para os cubes candidatos sem bloco curado.
"""

from __future__ import annotations

import re

from src.copilot.cube.interpret import PROMPT_PATH, _filter_catalog_blocks
from src.copilot.cube.measure_contract import (
    MEASURE_REGISTRY,
    render_catalog_block,
)

_REGISTRY_CUBES = sorted({name.split(".", 1)[0] for name in MEASURE_REGISTRY})


def test_render_catalog_block_lists_cube_measures() -> None:
    block = render_catalog_block("moldes")
    assert block.startswith("### Cube: `moldes`")
    assert "auto-gerado" in block
    # Todas as medidas do cube aparecem com o nome canónico.
    for name in MEASURE_REGISTRY:
        if name.split(".", 1)[0] == "moldes":
            assert f"`{name}`" in block


def test_render_catalog_block_empty_for_unknown_cube() -> None:
    assert render_catalog_block("cube_que_nao_existe") == ""


def test_every_registry_cube_renders_a_block() -> None:
    """Cobertura: os 48 cubes do registry produzem um bloco não-vazio — sem
    isto, um cube sem bloco curado nem gerado ficava mudo no prompt."""
    for cube in _REGISTRY_CUBES:
        block = render_catalog_block(cube)
        assert block and f"### Cube: `{cube}`" in block, f"cube {cube} sem bloco"


def test_filter_catalog_injects_generated_block_for_missing_cube() -> None:
    """`moldes` não tem bloco curado no .md → o filtro injecta o gerado."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    assert "### Cube: `moldes`" not in template, "pré-condição: moldes não curado"

    out = _filter_catalog_blocks(template, {"moldes"})
    assert "### Cube: `moldes`" in out
    assert "auto-gerado" in out


def test_filter_catalog_prefers_handwritten_block() -> None:
    """`qualidade` TEM bloco curado → usa-o (não o gerado)."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    out = _filter_catalog_blocks(template, {"qualidade"})
    qblock = re.search(
        r"### Cube: `qualidade`.*?(?=### Cube:|\Z)", out, re.DOTALL
    )
    assert qblock is not None
    assert "auto-gerado" not in qblock.group(0)


def test_filter_catalog_does_not_pollute_when_handwritten_present() -> None:
    """No-regressão: quando UMA candidata tem bloco curado (consumo_material),
    NÃO se injectam blocos gerados das outras candidatas (moldes) — o ruído de
    blocos tangenciais fazia o LLM abstain (test_synonyms_match_consumo)."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    out = _filter_catalog_blocks(template, {"consumo_material", "moldes"})
    assert "### Cube: `consumo_material`" in out
    assert "### Cube: `moldes`" not in out
    assert "auto-gerado" not in out
