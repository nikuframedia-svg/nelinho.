"""Q.157.A — repoint de `load_phase_histories` / `load_throughput_ts`.

`plan.fases_of_history` está vazia neste deployment (0 linhas), por isso o
SequenceMining e o ThroughputForecast ficavam sem dados (fallback também
vazio). O repoint Q.157.A lê a fonte primária de `factory_raw.of_fp` (ERP
vivo, ~538k execuções de fase) — mesmo padrão que o Q.150 usou nos jobs de
afinidade.

Estes testes travam o repoint: o SQL primário tem de atacar `factory_raw.of_fp`
e NÃO `plan.fases_of_history`, e a forma do DataFrame mantém-se. DAMP — cada
teste lê como spec, sem parsing real de SQL (capturamos o texto do statement).
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any
from uuid import UUID

from src.ml.models_domain.training_data import (
    load_phase_histories,
    load_throughput_ts,
)

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _Mappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Mappings:
        return _Mappings(self._rows)


class _RecordingSession:
    """Devolve `rows` e guarda o texto de cada statement executado."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.statements: list[str] = []

    async def execute(self, stmt: Any, params: Any = None) -> _Result:
        self.statements.append(str(stmt))
        return _Result(self._rows)


def test_load_phase_histories_reads_factory_raw_of_fp() -> None:
    rows = [
        {"of_id": "11699", "phase_code": "12", "phase_order": 1},
        {"of_id": "11993", "phase_code": "14", "phase_order": 1},
        {"of_id": "11993", "phase_code": "9", "phase_order": 2},
    ]
    sess = _RecordingSession(rows)
    df = asyncio.run(load_phase_histories(sess, TENANT, limit=10))

    sql = sess.statements[0].lower()
    assert "factory_raw.of_fp" in sql, "primário tem de ler factory_raw.of_fp"
    assert "fases_of_history" not in sql, "não pode ler a tabela vazia"
    # Primário devolveu linhas → não cai no fallback (1 só statement).
    assert len(sess.statements) == 1
    assert list(df.columns) == ["of_id", "phase_code", "phase_order"]
    assert len(df) == 3


def test_load_throughput_ts_reads_factory_raw_of_fp() -> None:
    rows = [
        {"date": date(2024, 5, 31), "boat_id": "29056", "ops_concluidas": 2},
        {"date": date(2024, 6, 1), "boat_id": "29106", "ops_concluidas": 5},
    ]
    sess = _RecordingSession(rows)
    df = asyncio.run(load_throughput_ts(sess, TENANT, limit=10))

    sql = sess.statements[0].lower()
    assert "factory_raw.of_fp" in sql
    assert "fases_of_history" not in sql
    assert len(sess.statements) == 1
    assert {"date", "boat_id", "ops_concluidas"} <= set(df.columns)
    assert len(df) == 2


def test_load_phase_histories_falls_back_when_factory_raw_empty() -> None:
    """Sem linhas em factory_raw.of_fp, cai no fallback factory_curated
    (2º statement) — o fallback nunca foi removido."""
    sess = _RecordingSession([])  # ambos os queries devolvem vazio
    df = asyncio.run(load_phase_histories(sess, TENANT, limit=10))

    assert len(sess.statements) == 2, "primário vazio → executa o fallback"
    assert "factory_raw.of_fp" in sess.statements[0].lower()
    assert "order_phase" in sess.statements[1].lower()
    assert list(df.columns) == ["of_id", "phase_code", "phase_order"]
    assert len(df) == 0
