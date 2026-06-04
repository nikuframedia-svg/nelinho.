"""Q.159 — `MasterDataService.list_employees(active_only=True)` restringe à regra
EXATA de "operador ativo" via `factory_raw.v_active_operators` (~107), com
FALLBACK honesto para `status=ACTIVE` quando a view falta (dev sem sync) — nunca
devolve vazio silencioso.

Captura o SQL compilado (sem BD) e trava:
  - view presente → filtra por `employee_code IN (...)` (os codes da view);
  - view ausente  → filtra por `status = ACTIVE` (fallback), nunca lista crua;
  - `active_only=False` (default) → sem qualquer dos dois (back-compat).
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.core.services.master_data_service import MasterDataService

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _Result:
    """Resultado mínimo: `.scalars().all()` para a query ORM; iterável p/ codes."""

    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return []

    def __iter__(self):
        return iter(self._rows)


class _Row:
    def __init__(self, code):
        self.code = code


class _CaptureSession:
    """Captura o SQL gerado por list_employees, simulando a view de operadores."""

    def __init__(self, view_exists, codes=None):
        self._view_exists = view_exists
        self._codes = codes or []
        self.statements: list[str] = []

    async def scalar(self, stmt, *args, **kwargs):
        # information_schema.views → existência da view.
        return self._view_exists

    async def execute(self, stmt, *args, **kwargs):
        sql = str(stmt)
        self.statements.append(sql)
        if "v_active_operators" in sql:
            return _Result(rows=[_Row(c) for c in self._codes])
        return _Result()


@pytest.mark.asyncio
async def test_active_only_filters_by_view_codes():
    sess = _CaptureSession(view_exists=1, codes=["7", "9"])
    svc = MasterDataService(sess, TENANT)
    await svc.list_employees(active_only=True)
    final = sess.statements[-1]  # a query ORM dos employees
    assert "employee_code IN" in final, "filtra pelos codes da v_active_operators"
    assert "status" not in final.split("WHERE")[-1] or "employee_code IN" in final


@pytest.mark.asyncio
async def test_active_only_falls_back_to_status_active_when_view_missing():
    sess = _CaptureSession(view_exists=None)
    svc = MasterDataService(sess, TENANT)
    await svc.list_employees(active_only=True)
    final = sess.statements[-1]
    assert "employees.status" in final, "fallback honesto para status=ACTIVE"
    assert "employee_code IN" not in final, "sem codes (view ausente)"


@pytest.mark.asyncio
async def test_default_is_backcompat_no_active_filter():
    sess = _CaptureSession(view_exists=1, codes=["7"])
    svc = MasterDataService(sess, TENANT)
    await svc.list_employees()  # active_only=False (default)
    final = sess.statements[-1]
    assert "employee_code IN" not in final
    # sem o filtro de status forçado (só o tenant) — comportamento original.
    assert "v_active_operators" not in " ".join(sess.statements)
