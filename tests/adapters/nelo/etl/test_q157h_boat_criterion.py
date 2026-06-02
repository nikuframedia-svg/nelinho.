"""Q.157.H — Critério barco NELO: lógica pura + integração com factory_raw.

Critério validado: is_boat = raiz de PRODUTO_TIPO (via TP_TP_ID) é Kayak
(TP_ID=1) AND ORDEMFABRICO.OF_ID < 10_000_000.

Testes de lógica pura (sem DB): verificam o algoritmo de subida hierárquica
com dados inline que espelham casos reais conhecidos.

Testes de integração (marcados `integration`): validam a view
factory_raw.v_of_is_boat no Postgres local. Requerem DB com dados espelhados
(q75 + q102.A + q157h).
"""

from __future__ import annotations

import pytest


# ── dados inline que espelham a hierarquia NELO real ─────────────────────────
#
# TP_ID → TP_TP_ID (None = raiz)
#   1  Kayak             None   (raiz)
#   2  Serralharia/Ac.   None   (raiz diferente)
# 255  Touring           1      (filho de Kayak)
# 259  Canoe Sprint      1      (filho de Kayak)
#   6  Canoe Sprint Ep.  259    (neto)
#   7  Canoe Sprint Pl.  259    (neto)
#   8  Touring Ep.       255    (neto)
# 331  Parcerias/DD Pag. 1      (filho de Kayak — MAS OF_ID >= 10M)
#  10  Banco             2      (filho de Serralharia)
# 400  Nacra (simplif.)  1      (filho de Kayak, catamarans)
#
_TIPO_PARENT: dict[int, int | None] = {
    1: None,
    2: None,
    255: 1,
    259: 1,
    6: 259,
    7: 259,
    8: 255,
    331: 1,
    10: 2,
    400: 1,
}


def _root_tp_id(tp_id: int, parent_map: dict[int, int | None]) -> int | None:
    """Sobe a hierarquia até à raiz. Espelha a lógica da CTE WITH RECURSIVE."""
    visited: set[int] = set()
    current = tp_id
    while True:
        if current in visited:
            return None  # ciclo — nunca deve acontecer nos dados NELO
        visited.add(current)
        parent = parent_map.get(current)
        if parent is None:
            return current
        current = parent


def is_boat(of_id: int, p_tp_id: int, parent_map: dict[int, int | None]) -> bool:
    """Critério Q.157.H em Python puro."""
    return _root_tp_id(p_tp_id, parent_map) == 1 and of_id < 10_000_000


# ── testes de lógica pura ─────────────────────────────────────────────────────


def test_root_kayak_is_itself():
    assert _root_tp_id(1, _TIPO_PARENT) == 1


def test_root_serralharia_is_itself():
    assert _root_tp_id(2, _TIPO_PARENT) == 2


def test_canoe_sprint_root_is_kayak():
    # TP_ID=6 → 259 → 1
    assert _root_tp_id(6, _TIPO_PARENT) == 1


def test_touring_root_is_kayak():
    # TP_ID=8 → 255 → 1
    assert _root_tp_id(8, _TIPO_PARENT) == 1


def test_banco_root_is_serralharia():
    # TP_ID=10 → 2 (não Kayak)
    assert _root_tp_id(10, _TIPO_PARENT) == 2


def test_nacra_root_is_kayak():
    # TP_ID=400 → 1
    assert _root_tp_id(400, _TIPO_PARENT) == 1


def test_pagaia_tp_root_is_kayak():
    # TP_ID=331 → 1 (raiz Kayak — MAS OF_ID exclui)
    assert _root_tp_id(331, _TIPO_PARENT) == 1


# ── is_boat casos concretos ───────────────────────────────────────────────────


@pytest.mark.parametrize("of_id,tp_id,expected", [
    # K1 kayak normal — barco
    (12345, 6, True),
    # C1 canoa — filho directo de Kayak em ramo diferente — barco
    (99999, 8, True),
    # Nacra — barco
    (500000, 400, True),
    # Pagaia com OF_ID normal (< 10M) — barco? NÃO — OF_ID real >= 10M
    # Este caso não existe na fábrica, mas valida que só OF_ID exclui:
    # (99, 331, True)  ← se existisse, seria barco (raiz=1, OF<10M)
    # Pagaia real (OF_ID >= 10M) — NÃO é barco
    (10_000_001, 331, False),
    (15_000_000, 331, False),
    # Banco (serralharia) — NÃO é barco
    (12345, 10, False),
    # OF_ID >= 10M qualquer tipo — NÃO é barco
    (10_000_000, 6, False),
    (12_345_678, 8, False),
])
def test_is_boat_parametrized(of_id: int, tp_id: int, expected: bool):
    assert is_boat(of_id, tp_id, _TIPO_PARENT) is expected


def test_of_id_boundary_exclusive():
    """OF_ID = 9_999_999 é barco; 10_000_000 não é."""
    assert is_boat(9_999_999, 6, _TIPO_PARENT) is True
    assert is_boat(10_000_000, 6, _TIPO_PARENT) is False


# ── testes de integração (Postgres real) ─────────────────────────────────────


@pytest.mark.integration
def test_view_exists_in_factory_raw():
    """factory_raw.v_of_is_boat existe após q157h setup."""
    import asyncio
    import sys
    sys.path.insert(0, "C:/Users/User/nelinho")
    import asyncpg
    from src.shared.config import settings

    async def _run():
        pg_dsn = settings.database_url.replace("+asyncpg", "")
        conn = await asyncpg.connect(pg_dsn)
        try:
            exists = await conn.fetchval(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.views"
                "  WHERE table_schema = 'factory_raw'"
                "  AND table_name = 'v_of_is_boat'"
                ")"
            )
            return exists
        finally:
            await conn.close()

    result = asyncio.run(_run())
    assert result, "factory_raw.v_of_is_boat nao existe — corre q157h_setup_boat_criterion_view.py"


@pytest.mark.integration
def test_view_boats_open_count_plausible():
    """Barcos em aberto (OF_DATAFIM vazio) estão dentro de limites plausíveis.

    A view cobre todas as OFs na janela de 2 anos (abertas + fechadas); por
    isso filtramos OF_DATAFIM aqui. A fábrica tem ~1121 OFs barco abertas em
    prod (2026-06-02); o espelho local pode variar (janela diferente).
    """
    import asyncio
    import sys
    sys.path.insert(0, "C:/Users/User/nelinho")
    import asyncpg
    from src.shared.config import settings

    async def _run():
        pg_dsn = settings.database_url.replace("+asyncpg", "")
        conn = await asyncpg.connect(pg_dsn)
        try:
            boats_open = await conn.fetchval(
                "SELECT COUNT(*) FROM factory_raw.v_of_is_boat v"
                " JOIN factory_raw.ordemfabrico of_ ON of_.\"OF_ID\" = v.of_id"
                " WHERE v.is_boat"
                "   AND (of_.\"OF_DATAFIM\" IS NULL OR of_.\"OF_DATAFIM\" = '')"
            )
            return int(boats_open)
        finally:
            await conn.close()

    count = asyncio.run(_run())
    # espelho local tem janela 2 anos: esperamos entre 100 e 3000 barcos abertos
    assert count > 100, f"Poucos barcos abertos: {count} — espelho stale?"
    assert count < 3000, f"Demasiados barcos abertos: {count} — critério errado?"


@pytest.mark.integration
def test_view_pagaias_never_boat():
    """TP_ID=331 (DD Pagaias) — is_boat NUNCA true (OF_ID >= 10M na fábrica)."""
    import asyncio
    import sys
    sys.path.insert(0, "C:/Users/User/nelinho")
    import asyncpg
    from src.shared.config import settings

    async def _run():
        pg_dsn = settings.database_url.replace("+asyncpg", "")
        conn = await asyncpg.connect(pg_dsn)
        try:
            pagaia_boats = await conn.fetchval(
                "SELECT COUNT(*) FROM factory_raw.v_of_is_boat "
                "WHERE p_tp_id = 331 AND is_boat"
            )
            return int(pagaia_boats)
        finally:
            await conn.close()

    result = asyncio.run(_run())
    assert result == 0, (
        f"Pagaias (TP_ID=331) classificadas como barco: {result} — "
        "critério OF_ID < 10M nao esta a funcionar"
    )
