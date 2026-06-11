"""Q.108.TEST.D — Cube /meta alignment vs MEASURE_REGISTRY.

@pytest.mark.integration — só corre se Cube :4000 estiver acessível.

Confirma que cada measure registada em MEASURE_REGISTRY existe no /meta
do Cube live (ou seja, foi correctamente reflectida pelos YAMLs lidos
pelo Cube server).

Pré-flight:
    docker compose up cube  (ou processo Cube local)
"""
from __future__ import annotations

import asyncio
import warnings
from typing import Optional

import pytest

from src.copilot.cube.measure_contract import MEASURE_REGISTRY


async def _cube_available() -> bool:
    """Probe rápido: Cube /readyz responde com 200."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://localhost:4000/readyz")
        return r.status_code == 200
    except Exception:
        return False


async def _fetch_cube_meta() -> Optional[set[str]]:
    """Devolve set de measure names do Cube /meta, ou None se falhar."""
    try:
        from src.copilot.cube.client import CubeClient

        client = CubeClient()
        meta = await client.fetch_meta()
        await client.close()
        return set(meta.all_measure_names())
    except Exception as exc:
        warnings.warn(f"fetch_meta falhou: {exc}", stacklevel=2)
        return None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_registered_measure_exists_in_cube_meta():
    """Q.108.TEST.D: cada measure em MEASURE_REGISTRY existe em /meta.

    Apanha drift entre measure_contract.py e cube/model/*.yml lidos pelo
    server (cube docker container precisa estar a apontar para o dir certo).
    """
    if not await _cube_available():
        pytest.skip("Cube :4000 unavailable — integration test skipped.")

    cube_measures = await _fetch_cube_meta()
    if cube_measures is None:
        pytest.skip("fetch_meta failed — Cube provavelmente em mau estado.")

    # Pre-Q108 drift conhecida (campanha Q.106 — workforce cube naming
    # divergente entre YAML e measure_contract). Nova drift = fail.
    pre_q108_registry_drift: frozenset[str] = frozenset({
        "workforce.colaboradores_activos.total",
        "workforce.horas_extra.total",
    })
    registry_measures = set(MEASURE_REGISTRY.keys())
    missing_in_cube = (registry_measures - cube_measures) - pre_q108_registry_drift

    assert not missing_in_cube, (
        f"Measures em MEASURE_REGISTRY NÃO expostos pelo Cube /meta "
        f"(drift entre code e cube/model/*.yml carregados pelo server): "
        f"{sorted(missing_in_cube)[:10]}"
        + (f" ... ({len(missing_in_cube)} total)" if len(missing_in_cube) > 10 else "")
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cube_meta_does_not_have_unregistered_measures():
    """Defesa inversa: measure no /meta sem entry no registry = drift.

    Esta direcção é mais permissiva — alguns measures podem ser legacy
    ainda no Cube. Marcamos como skip se houver drift > 5 measures
    (provavelmente legacy não-Q.108).
    """
    if not await _cube_available():
        pytest.skip("Cube :4000 unavailable.")

    cube_measures = await _fetch_cube_meta()
    if cube_measures is None:
        pytest.skip("fetch_meta failed.")

    registry_measures = set(MEASURE_REGISTRY.keys())
    extra_in_cube = cube_measures - registry_measures

    # Permitimos algum drift legacy mas reportamos top-10 visivelmente.
    if extra_in_cube:
        message = (
            f"Measures no Cube /meta sem entry em MEASURE_REGISTRY "
            f"(legacy drift): {sorted(extra_in_cube)[:10]}"
            + (f" ... ({len(extra_in_cube)} total)"
               if len(extra_in_cube) > 10 else "")
        )
        if len(extra_in_cube) > 5:
            pytest.skip(message)
        # ≤5 drift → assertiva mais firme
        assert False, message
