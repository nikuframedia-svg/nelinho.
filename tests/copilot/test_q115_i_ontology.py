"""
Q.115.I — testes da ontologia formal (entities.py)

Cada teste lê como spec independente (DAMP).
"""

import json

import pytest

from src.copilot.ontology.entities import (
    ENTITIES,
    RELATIONS,
    Entity,
    EntityCategory,
    Relation,
    RelationKind,
    export_json,
    find_entity,
    relations_from,
    relations_to,
)


# ─── Counts ──────────────────────────────────────────────────────────────────

def test_entities_count_at_least_30():
    assert len(ENTITIES) >= 30, f"só {len(ENTITIES)} entidades; mínimo 30"


def test_relations_count_at_least_20():
    assert len(RELATIONS) >= 20, f"só {len(RELATIONS)} relações; mínimo 20"


# ─── Unicidade ───────────────────────────────────────────────────────────────

def test_all_entities_have_unique_names():
    names = [e.name for e in ENTITIES]
    duplicates = [n for n in names if names.count(n) > 1]
    assert not duplicates, f"nomes duplicados: {set(duplicates)}"


# ─── Integridade referencial ──────────────────────────────────────────────────

def test_all_relations_reference_existing_entities():
    entity_names = {e.name for e in ENTITIES}
    for r in RELATIONS:
        assert r.source in entity_names, (
            f"Relation source {r.source!r} não existe em ENTITIES"
        )
        # target pode ser self-referencial (phase→phase); ainda tem de existir
        assert r.target in entity_names, (
            f"Relation target {r.target!r} não existe em ENTITIES"
        )


# ─── find_entity ─────────────────────────────────────────────────────────────

def test_find_entity_happy_path():
    e = find_entity("of")
    assert e is not None
    assert e.name == "of"
    assert e.category == EntityCategory.PROCESS


def test_find_entity_missing_returns_none():
    assert find_entity("nao_existe_xyz") is None


# ─── relations_from ───────────────────────────────────────────────────────────

def test_relations_from_of_at_least_3():
    rels = relations_from("of")
    # OF → phase (has_a), OF → product (belongs_to), OF → client (belongs_to)
    assert len(rels) >= 3, f"só {len(rels)} relações de 'of'; esperado ≥3"


def test_relations_from_returns_correct_sources():
    for r in relations_from("operator"):
        assert r.source == "operator"


# ─── relations_to ─────────────────────────────────────────────────────────────

def test_relations_to_rework_entry_at_least_2():
    rels = relations_to("rework_entry")
    # operation → produces → rework_entry
    # kpi_defect_rate → measures → rework_entry
    assert len(rels) >= 2, f"só {len(rels)} relações para 'rework_entry'; esperado ≥2"


def test_relations_to_returns_correct_targets():
    for r in relations_to("phase"):
        assert r.target == "phase"


# ─── export_json ─────────────────────────────────────────────────────────────

def test_export_json_structure():
    data = export_json()
    assert "schema_version" in data
    assert data["schema_version"] == "q115.i.1"
    assert "entities" in data
    assert "relations" in data
    assert isinstance(data["entities"], list)
    assert isinstance(data["relations"], list)


def test_export_json_serializable():
    data = export_json()
    # Deve serializar sem erro (sem objectos Python não-serializáveis)
    serialised = json.dumps(data)
    parsed = json.loads(serialised)
    assert parsed["entity_count"] == len(ENTITIES)
    assert parsed["relation_count"] == len(RELATIONS)


def test_export_json_entity_fields():
    data = export_json()
    first = data["entities"][0]
    assert "name" in first
    assert "category" in first
    assert "source_path" in first
    assert "description_pt" in first
