"""Q.171.A — lock_by_id emite SELECT ... FOR UPDATE.

A aprovação DRAFT→LIVE era read-check-write SEM lock (TOCTOU): dois
aprovadores em paralelo promoviam ambos. Este teste trava a emissão do
FOR UPDATE — uma regressão no ORM que o perdesse passaria despercebida
(o lock só se exercita de verdade contra a BD).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.plan.cpo.commits import CommitsService
from tests.conftest import TEST_TENANT_ID


class _CaptureSession:
    def __init__(self) -> None:
        self.sql = ""

    async def execute(self, stmt):
        self.sql = str(stmt)

        class _R:
            @staticmethod
            def scalar_one_or_none():
                return None

        return _R()


@pytest.mark.asyncio
async def test_lock_by_id_emits_for_update():
    sess = _CaptureSession()
    svc = CommitsService(sess, TEST_TENANT_ID)
    out = await svc.lock_by_id(uuid4())
    assert out is None
    assert "FOR UPDATE" in sess.sql.upper(), (
        "o lock TOCTOU da aprovação exige SELECT ... FOR UPDATE"
    )
