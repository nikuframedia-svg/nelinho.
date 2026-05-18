"""Sprint Q.49.A (F12) — validação ambiental da cura, lógica pura.

A cura é química. Este serviço cruza operações de cura/desmolde já
executadas com as leituras reais de temperatura/humidade da tabela ERP
`TH`, e sinaliza as que decorreram fora do intervalo aceitável.

Cobre:
* operação dentro do intervalo → conforme
* temperatura baixa / alta → fora_range com mensagem PT-PT
* humidade fora do intervalo → fora_range
* operação sem leituras na janela → sem_leituras (sem inventar conformidade)
* operação sem janela temporal completa → sem_leituras
* conformity_pct ignora as operações sem leituras no denominador
* conformity_pct é None quando nenhuma operação tem leituras
* intervalo configurável por tenant é respeitado
* conversores tolerantes a duck-typing dos schemas do adapter ERP
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.plan.services.curing_validation_service import (
    CuringOperation,
    EnvironmentRange,
    SensorReading,
    curing_operations_from_rows,
    sensor_readings_from_rows,
    validate_curing_window,
)

T0 = datetime(2026, 5, 18, 8, 0, 0)


def _op(opid="op1", woid="1001", phase="CURA", start=T0, dur_h=15.0):
    return CuringOperation(
        operation_id=opid,
        work_order_id=woid,
        phase_code=phase,
        start_at=start,
        end_at=None if start is None else start + timedelta(hours=dur_h),
    )


def _reading(offset_h, temp, hum=50.0):
    return SensorReading(
        measured_at=T0 + timedelta(hours=offset_h),
        temperature=temp,
        humidity=hum,
    )


def test_operation_within_range_is_conforme():
    result = validate_curing_window(
        [_op()],
        [_reading(1, 22.0, 50.0), _reading(8, 23.5, 55.0)],
    )
    assert result.operations_total == 1
    v = result.verdicts[0]
    assert v.status == "conforme"
    assert v.reading_count == 2
    assert v.breaches == []
    assert result.conformity_pct == 100.0


def test_low_temperature_is_fora_range():
    result = validate_curing_window([_op()], [_reading(2, 14.0, 50.0)])
    v = result.verdicts[0]
    assert v.status == "fora_range"
    assert v.temp_min_observed == 14.0
    assert any("temperatura" in b and "abaixo" in b for b in v.breaches)
    assert result.fora_range_total == 1
    assert result.conformity_pct == 0.0


def test_high_temperature_is_fora_range():
    result = validate_curing_window([_op()], [_reading(3, 31.0, 50.0)])
    v = result.verdicts[0]
    assert v.status == "fora_range"
    assert any("temperatura" in b and "acima" in b for b in v.breaches)


def test_humidity_out_of_range_is_fora_range():
    result = validate_curing_window(
        [_op()],
        [_reading(1, 22.0, 25.0), _reading(5, 22.0, 85.0)],
    )
    v = result.verdicts[0]
    assert v.status == "fora_range"
    assert v.humidity_min_observed == 25.0
    assert v.humidity_max_observed == 85.0
    assert any("humidade" in b and "abaixo" in b for b in v.breaches)
    assert any("humidade" in b and "acima" in b for b in v.breaches)


def test_operation_without_readings_is_sem_leituras():
    """Sem leituras na janela não se afirma conformidade nem incumprimento."""
    # leitura existe mas fora da janela [T0, T0+15h]
    result = validate_curing_window([_op()], [_reading(40, 22.0, 50.0)])
    v = result.verdicts[0]
    assert v.status == "sem_leituras"
    assert v.reading_count == 0
    assert v.breaches == []


def test_operation_without_time_window_is_sem_leituras():
    op = CuringOperation(
        operation_id="op9", work_order_id="9", phase_code="CURA",
        start_at=None, end_at=None,
    )
    result = validate_curing_window([op], [_reading(1, 22.0)])
    assert result.verdicts[0].status == "sem_leituras"


def test_conformity_pct_ignores_operations_without_readings():
    """O denominador é só as operações COM leituras — sem inventar."""
    result = validate_curing_window(
        [
            _op(opid="a", start=T0),                       # conforme
            _op(opid="b", start=T0 + timedelta(hours=100)),  # sem leituras
        ],
        [_reading(2, 22.0, 50.0)],
    )
    assert result.conforme_total == 1
    assert result.sem_leituras_total == 1
    # 1 conforme / 1 avaliada = 100 %, a 'b' não conta
    assert result.conformity_pct == 100.0


def test_conformity_pct_is_none_when_no_operation_has_readings():
    result = validate_curing_window([_op()], [])
    assert result.conformity_pct is None
    assert result.sem_leituras_total == 1


def test_custom_environment_range_is_respected():
    """Range apertado do tenant transforma uma operação conforme em fora_range."""
    strict = EnvironmentRange(
        temp_min_c=21.0, temp_max_c=23.0,
        humidity_min_pct=40.0, humidity_max_pct=60.0,
    )
    result = validate_curing_window(
        [_op()],
        [_reading(1, 24.0, 50.0)],  # 24 °C: ok no default, fora no strict
        environment_range=strict,
    )
    assert result.verdicts[0].status == "fora_range"
    assert result.environment_range.temp_max_c == 23.0


def test_curing_operations_from_rows_filters_by_phase():
    """Só operações de cura/desmolde passam o filtro; fase normalizada."""

    class _Row:
        def __init__(self, opid, woid, phase, start, end):
            self.operation_id = opid
            self.work_order_id = woid
            self.phase_name = phase
            self.start_at = start
            self.end_at = end

    rows = [
        _Row(1, 1001, "Cura", T0, T0 + timedelta(hours=15)),
        _Row(2, 1001, "Laminagem", T0, T0 + timedelta(hours=4)),
        _Row(3, 1002, "Desmolde", T0, T0 + timedelta(hours=1)),
    ]
    ops = curing_operations_from_rows(rows)
    assert {o.phase_code for o in ops} == {"CURA", "DESMOLDE"}
    assert len(ops) == 2
    assert ops[0].operation_id == "1"


def test_sensor_readings_from_rows_skips_incomplete():
    class _Row:
        def __init__(self, measured_at, temperature, humidity=None):
            self.measured_at = measured_at
            self.temperature = temperature
            self.humidity = humidity
            self.phase_id = None

    rows = [
        _Row(T0, 22.0, 50.0),
        _Row(None, 22.0, 50.0),   # sem timestamp — ignorada
        _Row(T0, None, 50.0),     # sem temperatura — ignorada
    ]
    readings = sensor_readings_from_rows(rows)
    assert len(readings) == 1
    assert readings[0].temperature == 22.0
