"""Q.161.B BUGFIX — os loaders de skills (Q.126.D) e do gate qualificado
(Q.158.B) comparavam `tenant_id` (coluna uuid) contra um parâmetro ligado por
`.bindparams(...=str(tenant_id))`. O asyncpg força o tipo VARCHAR no protocolo,
e `uuid = character varying` é inválido em PostgreSQL → a query rebenta e ABORTA
a transação do `FactoryState.load` inteiro (todos os loaders seguintes morrem com
"current transaction is aborted") → `open_orders = 0` → o CPO não planeia nada.

O fix é um CAST explícito (`CAST(:t AS uuid)`), que não depende da inferência de
tipo. Estes testes travam a regressão ao nível da SQL gerada (sem BD).
"""

from __future__ import annotations

from uuid import UUID

import pytest

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _Cap:
    """Captura a SQL gerada pelos loaders (sem BD)."""

    def __init__(self) -> None:
        self.sql = ""

    def mappings(self):
        return self

    def all(self):
        return []

    async def execute(self, stmt, params=None):
        self.sql = str(stmt)
        return self


@pytest.mark.asyncio
async def test_skills_loader_casts_tenant_to_uuid() -> None:
    from src.plan.cpo.state_loaders import _load_skills_db

    sess = _Cap()
    await _load_skills_db(sess, TENANT)
    assert "CAST(:tenant_id AS uuid)" in sess.sql, (
        "skills loader tem de fazer CAST do tenant_id p/ uuid (senão aborta a tx "
        "do load com uuid=varchar)"
    )
    # garante que a comparação crua sem cast desapareceu
    assert "tenant_id = :tenant_id" not in sess.sql


@pytest.mark.asyncio
async def test_qualified_gate_loader_casts_tenant_to_uuid() -> None:
    from src.plan.cpo.state_loaders import _load_qualified_db

    sess = _Cap()
    await _load_qualified_db(sess, TENANT)
    assert "CAST(:t AS uuid)" in sess.sql, (
        "qualified gate loader (Q.158.B) tem de fazer CAST do tenant p/ uuid"
    )
    assert "es.tenant_id = :t\n" not in sess.sql
