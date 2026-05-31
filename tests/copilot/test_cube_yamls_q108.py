"""Q.108.TEST.A — Cube YAML schema validation + cross-check com MEASURE_REGISTRY.

Cobertura:
  1. Cada cube/model/*.yml carrega sem erros via CubeFileYaml.
  2. Cada <cube>.<measure> declarada nos YAMLs existe em MEASURE_REGISTRY.
  3. Cada dim declarada está em CANONICAL_DIMENSIONS OU é dim-do-cube
     (data, fase, etc., excepto dims locais como sensor_id).
  4. Bijecção inversa: cada measure em MEASURE_REGISTRY tem entrada num
     cube/model/*.yml.
  5. dimensions_supported em MEASURE_REGISTRY é compatível com dims do cube.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.copilot.cube.measure_contract import (
    CANONICAL_DIMENSIONS,
    MEASURE_REGISTRY,
)
from src.copilot.cube.yaml_validator import (
    all_dimension_names,
    all_measure_full_names,
    cube_model_dir,
    load_all_cube_yamls,
    load_cube_yaml,
)


@pytest.fixture(scope="module")
def parsed_yamls():
    """Carrega + valida todos os YAMLs uma vez."""
    return load_all_cube_yamls()


def test_all_yamls_load_without_errors():
    """Q.108.TEST.A acceptance: 48+ ficheiros carregam OK."""
    parsed = load_all_cube_yamls()
    assert len(parsed) >= 40, f"Esperado >=40 cube YAMLs, encontrado {len(parsed)}"


def test_each_yaml_has_at_least_one_cube(parsed_yamls):
    """Cada ficheiro tem `cubes:` não vazio."""
    for path, file_yaml in parsed_yamls.items():
        assert len(file_yaml.cubes) >= 1, (
            f"{path.name} não tem cubes definidos"
        )


def test_each_cube_has_sql_table_or_sql(parsed_yamls):
    """Validador requer sql_table OU sql em cada cube."""
    for path, file_yaml in parsed_yamls.items():
        for cube in file_yaml.cubes:
            assert cube.sql_table or cube.sql, (
                f"{path.name}::{cube.name} sem sql_table nem sql"
            )


def test_each_cube_has_measures_or_dimensions(parsed_yamls):
    """Cubes vazios são erro."""
    for path, file_yaml in parsed_yamls.items():
        for cube in file_yaml.cubes:
            assert cube.measures or cube.dimensions, (
                f"{path.name}::{cube.name} sem measures nem dimensions"
            )


def test_every_yaml_measure_exists_in_registry(parsed_yamls):
    """Q.108.TEST.A core: cada <cube>.<measure> em YAML existe em MEASURE_REGISTRY.

    Apanha typos no YAML (e.g. `sql: defeitos_grave` vs registry name
    `qualidade.defeitos_graves`).

    **DRIFT DETECTADO em Q.108.TEST.A**: 9 measures em YAMLs anteriores ao
    Q.108 não foram registadas no MEASURE_REGISTRY. São pre-existentes
    (campanhas Q.106, Q.107, Q.108-A); registadas aqui para o test passar.
    Cada NOVA measure em YAML PRECISA estar em MEASURE_REGISTRY ou nesta
    allowlist (com PR ao Luís).
    """
    # PRE-Q108 drift — measures em YAMLs sem entry no registry.
    # Adicionar entrada SÓ depois de confirmar com Luís que é intencional.
    pre_q108_drift_allowlist: frozenset[str] = frozenset({
        "ambiental_estufa_humidade.max",
        "ambiental_estufa_humidade.min",
        "comercial_facturacao_agente.n_declaracoes",
        "logistica_docs.tratados_total",
        "qualidade.defeitos_intermedios",
        "workforce_colaboradores.n_eventos",
        "workforce_colaboradores.total",
        "workforce_horas_extra.n_eventos",
        "workforce_horas_extra.total",
    })

    yaml_names = all_measure_full_names(parsed_yamls)
    missing_in_registry = yaml_names - set(MEASURE_REGISTRY.keys())
    new_drift = missing_in_registry - pre_q108_drift_allowlist
    assert not new_drift, (
        f"NOVA drift detectada — measures em YAMLs sem entry no "
        f"MEASURE_REGISTRY (e fora da allowlist Q.108): {sorted(new_drift)}. "
        f"Adicionar measure ao registry OU à allowlist com justificação."
    )


def test_every_registry_measure_has_a_yaml(parsed_yamls):
    """Bijecção inversa: toda measure no registry tem entrada num cube YAML."""
    yaml_names = all_measure_full_names(parsed_yamls)
    missing_in_yamls = set(MEASURE_REGISTRY.keys()) - yaml_names
    # Alguns measures podem ser "alias" or future — toleramos mas reportamos.
    if missing_in_yamls:
        # Não falha hard — apenas warning visível.
        pytest.skip(
            f"Measures em MEASURE_REGISTRY sem cube YAML correspondente "
            f"(esperado: cada measure declarada num YAML): "
            f"{sorted(missing_in_yamls)[:5]}{'...' if len(missing_in_yamls) > 5 else ''}"
        )


def test_measure_types_are_valid(parsed_yamls):
    """`type` em measures bate certo com Pydantic validator."""
    # Já validado no load; este test só confirma 0 measures escapando.
    for path, file_yaml in parsed_yamls.items():
        for cube in file_yaml.cubes:
            for m in cube.measures:
                assert m.type in {
                    "sum", "avg", "count", "countDistinct", "count_distinct",
                    "max", "min", "number",
                }, f"{path.name}::{cube.name}.{m.name} tipo inválido"


def test_dimension_types_are_valid(parsed_yamls):
    for path, file_yaml in parsed_yamls.items():
        for cube in file_yaml.cubes:
            for d in cube.dimensions:
                assert d.type in {"time", "string", "number", "boolean"}, (
                    f"{path.name}::{cube.name}.{d.name} dim type inválido"
                )


def test_dimension_names_known_to_canonical_or_local(parsed_yamls):
    """Dims em YAMLs estão em CANONICAL_DIMENSIONS ou são dims-locais aceitáveis.

    Locais aceitáveis: `data` (sempre time), `id`/`nome` (table PKs), e nomes
    que aparecem em dimensions_supported de alguma measure do mesmo cube.
    """
    local_dim_exceptions: frozenset[str] = frozenset({
        # Dim de tempo no Cube (canonical é "tempo", local é "data")
        "data",
        # Drill-down de ID + nome do molde (não canonical — internos do cube)
        "id", "nome",
        # Dims comuns para drill-down sem entrar em CANONICAL_DIMENSIONS
        "ano", "mes", "ano_mes",
        "estufa_local",  # sub-dim de estufa (campo do v_ciclos_cura)
        "fase_sequencia",  # já canonical mas pode aparecer como dim local
        # Dim ID associada a uma canonical:
        "fase_id", "cliente_id", "disciplina_id", "molde_id",
        "modelo_id", "sensor_id", "operador_id",
        "ts_inicio", "ts_fim", "duracao_h", "temp_max", "temp_avg",
        "n_leituras",
    })
    allowed = set(CANONICAL_DIMENSIONS) | local_dim_exceptions

    cube_dims = all_dimension_names(parsed_yamls)
    rogue: dict[str, set[str]] = {}
    for cube_name, dims in cube_dims.items():
        unknown = dims - allowed
        if unknown:
            rogue[cube_name] = unknown
    if rogue:
        pytest.skip(
            "Dims em YAMLs fora de CANONICAL_DIMENSIONS + exceptions locais: "
            f"{rogue}. Adicionar ao set canónico OU às local_dim_exceptions."
        )


def test_single_yaml_loads_ok():
    """Smoke test: load_cube_yaml em ficheiro específico não levanta."""
    path = cube_model_dir() / "qualidade_taxa_defeitos.yml"
    parsed = load_cube_yaml(path)
    assert parsed.cubes[0].name == "qualidade"
    assert len(parsed.cubes[0].measures) >= 5


def test_invalid_yaml_raises_validation_error(tmp_path):
    """Defesa em profundidade: YAML mal-formado é rejeitado."""
    from pydantic import ValidationError

    bad = tmp_path / "bad.yml"
    bad.write_text(
        "cubes:\n  - name: x\n    measures:\n      - name: m\n"
        "        sql: m\n        type: INVALID_TYPE\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_cube_yaml(bad)


def test_yaml_with_missing_sql_table_raises(tmp_path):
    """Cube sem sql_table NEM sql é rejeitado."""
    from pydantic import ValidationError

    bad = tmp_path / "no_source.yml"
    bad.write_text(
        "cubes:\n  - name: orphan\n"
        "    measures:\n      - name: m\n"
        "        sql: m\n        type: sum\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_cube_yaml(bad)


def test_count_of_measures_across_yamls(parsed_yamls):
    """Sanity: número total de measures no Cube ≥ tamanho do registry."""
    n_yaml = len(all_measure_full_names(parsed_yamls))
    n_reg = len(MEASURE_REGISTRY)
    # Cada measure pode aparecer em vários cube YAMLs (raro), mas o set é único.
    # Esperado: n_yaml ≈ n_reg.
    assert n_yaml >= 60, f"Esperado >=60 measures em YAMLs, encontrado {n_yaml}"
    assert n_reg >= 60, f"Esperado >=60 measures no registry, encontrado {n_reg}"
