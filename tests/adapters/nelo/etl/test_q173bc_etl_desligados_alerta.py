"""Q.173.B/C — ETLs partidos desligados + alerta de falha de sync.

Q.173.B: os mirrors ``phase_history``/``worker_assignment`` consultavam
``dbo.FasesOf``/``dbo.WorkerAssignment`` — tabelas que só existem no
fake-ERP de teste — e falharam 100% das corridas em produção (9/9 'error',
auditoria 2026-06-11). Ficam fora do registo do sync até o Luis decidir
repontar para OF_FP/OFFP_EQ.

Q.173.C: uma corrida ETL falhada passa a criar um CopilotAlert WARN
(ETL_SYNC_FAILED), dedupado por mirror enquanto houver um ACTIVE — falha
de sync deixa de ser invisível.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.adapters.nelo.etl.runner import EtlRunResult
from src.adapters.nelo.etl.sync import (
    _alert_etl_failure,
    _load_mirror_modules,
)
from src.copilot.alerts.models import (
    CODE_ETL_SYNC_FAILED,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    CopilotAlert,
)

TENANT = uuid4()


def _failed(source: str = "stock") -> EtlRunResult:
    failed = EtlRunResult(source)
    failed.status = "error"
    failed.error = "ProgrammingError: Invalid object name 'dbo.FasesOf'"
    return failed


def test_q173b_mirrors_partidos_fora_do_registo() -> None:
    # Asserções ESTÁTICAS ao código-fonte (sem tocar no registo global nem
    # fazer importlib.reload — ambos poluem outros testes sob ordem
    # aleatória do pytest-randomly): o registo de mirrors é efeito de
    # import, por isso a fonte de verdade auditável é o próprio código.
    import inspect

    from src.adapters.nelo.etl import phase_history, worker_assignment

    loader_src = inspect.getsource(_load_mirror_modules)
    assert '"phase_history"' not in loader_src, (
        "phase_history voltou ao _load_mirror_modules — consulta dbo.FasesOf "
        "(só existe no fake-ERP); religar exige repontar para OF_FP "
        "(decisão do Luis pendente)"
    )
    assert '"worker_assignment"' not in loader_src, (
        "worker_assignment voltou ao _load_mirror_modules — consulta "
        "dbo.WorkerAssignment (só fake-ERP)"
    )
    # Os módulos desligados não podem registar-se no import (a linha
    # register_mirror tem de estar comentada/removida).
    for mod in (phase_history, worker_assignment):
        active_lines = [
            line for line in inspect.getsource(mod).splitlines()
            if line.strip().startswith("register_mirror(")
        ]
        assert active_lines == [], (
            f"{mod.__name__} regista-se no import — Q.173.B desligou-o"
        )
    # Os mirrors saudáveis continuam no loader.
    for vivo in ('"stock"', '"checklist"', '"material_master"',
                 '"purchase_orders"'):
        assert vivo in loader_src


@pytest.mark.asyncio
async def test_q173c_falha_cria_alerta(recording_session) -> None:
    await _alert_etl_failure(recording_session, TENANT, _failed())

    alerts = [o for o in recording_session.added if isinstance(o, CopilotAlert)]
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.code == CODE_ETL_SYNC_FAILED
    assert alert.severity == "WARN"
    assert alert.status == STATUS_ACTIVE
    assert alert.context["source"] == "stock"
    assert "dbo.FasesOf" in alert.context["error"]
    assert "desatualizados" in alert.message_pt  # PT-PT, mensagem honesta


@pytest.mark.asyncio
async def test_q173c_dedup_por_mirror_enquanto_active(recording_session) -> None:
    await _alert_etl_failure(recording_session, TENANT, _failed())
    await _alert_etl_failure(recording_session, TENANT, _failed())

    alerts = [o for o in recording_session.added if isinstance(o, CopilotAlert)]
    assert len(alerts) == 1, "segunda falha do MESMO mirror não duplica o alerta"

    # Mirror diferente → alerta próprio.
    await _alert_etl_failure(recording_session, TENANT, _failed("calendar"))
    alerts = [o for o in recording_session.added if isinstance(o, CopilotAlert)]
    assert len(alerts) == 2


@pytest.mark.asyncio
async def test_q173c_alerta_resolvido_reabre_vigilancia(recording_session) -> None:
    await _alert_etl_failure(recording_session, TENANT, _failed())
    alert = next(
        o for o in recording_session.added if isinstance(o, CopilotAlert)
    )
    alert.status = STATUS_RESOLVED  # operador resolveu; mirror volta a falhar

    await _alert_etl_failure(recording_session, TENANT, _failed())
    alerts = [o for o in recording_session.added if isinstance(o, CopilotAlert)]
    assert len(alerts) == 2, "falha após resolve cria alerta novo"
