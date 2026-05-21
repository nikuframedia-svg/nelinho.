"""
ProdPlan ONE - Twin: Hash / Audit / KPI extraction helpers
==========================================================

Q.67.6.B1 - extraido de `src/twin/service.py` (god-file 1192L). Funcoes
puras de hash + extraccao de KPIs + diff entre estados. Sem dependencias
de DB - operam sobre dicts e objectos `Scenario` em memoria.

Mantem a API publica do servico intacta: `TwinService` re-exporta estes
helpers como metodos (`svc._extract_value(...)`, etc.) para os
characterization tests Q.67.A1 continuarem verdes.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Optional

from .models import Scenario


def extract_value(item: Any) -> Optional[float]:
    """Extract numeric value from a KPI item.

    Q.54.I - devolve `None` para valores nao-finitos (`NaN`/`inf`) e
    para `bool` (que e subclasse de `int` mas nao e uma metrica). Sem
    esta guarda um `NaN` no estado contaminava silenciosamente todos
    os deltas a jusante.
    """
    if item is None:
        return None
    if isinstance(item, bool):
        return None
    if isinstance(item, (int, float)):
        return float(item) if math.isfinite(float(item)) else None
    if isinstance(item, dict):
        val = item.get("value")
        if (
            val is not None
            and not isinstance(val, bool)
            and isinstance(val, (int, float))
            and item.get("status") != "BLOCKED"
            and math.isfinite(float(val))
        ):
            return float(val)
    return None


def calculate_kpi_deltas(
    before: Dict[str, Any], after: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate delta summary between two states.

    Q.54.I - protegido contra resultados nao-finitos: se `after - before`
    der `inf`/`NaN` (overflow ou valores corrompidos no estado), a
    diferenca e descartada em vez de poluir o resumo com um numero que
    nenhum cliente sabe renderizar.
    """
    deltas: Dict[str, Any] = {}

    for key in set(before.keys()) | set(after.keys()):
        if key.startswith("_"):
            continue

        before_val = extract_value(before.get(key))
        after_val = extract_value(after.get(key))

        if before_val is not None and after_val is not None:
            change = after_val - before_val
            if math.isfinite(change):
                deltas[f"{key}_change"] = change

    return deltas


def calculate_state_hash(state: Dict[str, Any]) -> str:
    """Calculate hash for a state dictionary."""
    # Remove metadata fields that don't affect reproducibility
    clean_state = {
        k: v for k, v in state.items()
        if not k.startswith("_") and k not in ["generated_at", "computed_at"]
    }
    json_str = json.dumps(clean_state, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def calculate_scenario_hash(scenario: Scenario) -> str:
    """
    Calculate deterministic SHA256 hash for scenario reproducibility.

    This hash guarantees that:
    1. Same baseline + same deltas = same hash
    2. Same hash = reproducible simulation result
    3. Any change in baseline or deltas changes the hash

    The hash is computed from:
    - baseline_state (sorted JSON)
    - deltas (ordered by sequence, sorted JSON)
    """
    baseline_hash = calculate_state_hash(scenario.baseline_state)

    deltas_data = [
        {
            "sequence": d.sequence,
            "entity_type": d.entity_type,
            "entity_key": d.entity_key,
            "patch": d.patch,
        }
        for d in sorted(scenario.deltas, key=lambda d: d.sequence)
    ]
    deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
    deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()

    combined = f"{baseline_hash}|{deltas_hash}"
    scenario_hash = hashlib.sha256(combined.encode()).hexdigest()

    return scenario_hash


def calculate_result_hash(result: Dict[str, Any]) -> str:
    """Calculate hash for simulation result. Only hashes the 'after' state."""
    if "after" in result:
        return calculate_state_hash(result["after"])
    return ""


def get_audit_hashes(scenario: Scenario) -> Dict[str, str]:
    """
    Get all hashes for audit/reproducibility.

    Returns:
        Dict with baseline_hash, deltas_hash, scenario_hash, result_hash
        (both short and full forms) + algorithm + is_reproducible.
    """
    baseline_hash = calculate_state_hash(scenario.baseline_state)

    deltas_data = [
        {
            "sequence": d.sequence,
            "entity_type": d.entity_type,
            "entity_key": d.entity_key,
            "patch": d.patch,
        }
        for d in sorted(scenario.deltas, key=lambda d: d.sequence)
    ]
    deltas_json = json.dumps(deltas_data, sort_keys=True, default=str)
    deltas_hash = hashlib.sha256(deltas_json.encode()).hexdigest()

    scenario_hash = scenario.scenario_hash or calculate_scenario_hash(scenario)

    result_hash = ""
    if scenario.simulation_result:
        result_hash = calculate_result_hash(scenario.simulation_result)

    return {
        "baseline_hash": baseline_hash[:16],  # Short for display
        "baseline_hash_full": baseline_hash,
        "deltas_hash": deltas_hash[:16],
        "deltas_hash_full": deltas_hash,
        "scenario_hash": scenario_hash[:16],
        "scenario_hash_full": scenario_hash,
        "result_hash": result_hash[:16] if result_hash else None,
        "result_hash_full": result_hash if result_hash else None,
        "is_reproducible": True,
        "algorithm": "sha256",
    }
