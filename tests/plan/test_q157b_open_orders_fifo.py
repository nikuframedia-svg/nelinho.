"""Q.157.B (corrigido) — selecção das ordens abertas a planear.

Correcção de uma medição errada: a data-alvo NÃO é ~nula. Foi medida na
população errada (todas as OFs abertas, 99% acessórios → 0.5%). Nos BARCOS
reais (boats_only, em produção) a data planeada é **95% preenchida, 53% futura**
(``OF_PLANO_DATA_PREVISTA`` 95%; COALESCE 53% futura; ``OF_DATAENTREGA`` 0%).

Por isso a selecção é: **barcos com prazo planeado FUTURO primeiro** (por prazo
asc = mais urgente), depois os restantes (sem prazo futuro / data-lixo no
passado) **FIFO por antiguidade de criação** (``OF_DATA``). A data-alvo continua
a sair como ``due_date`` para o backward-scheduling.

Captura o SQL gerado (sem BD) e trava o invariante de ordenação.
"""

from __future__ import annotations

from uuid import UUID

import pytest

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _CaptureResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _CaptureSession:
    """Captura o SQL gerado por `_load_open_orders_db` (sem BD)."""

    def __init__(self) -> None:
        self.sql_text = ""

    async def execute(self, stmt, params=None):
        self.sql_text = str(stmt)
        return _CaptureResult()


async def _captured_sql(scope: str = "boats_only") -> str:
    from src.plan.cpo.state import _load_open_orders_db

    sess = _CaptureSession()
    await _load_open_orders_db(sess, TENANT, scope=scope)
    return sess.sql_text


@pytest.mark.asyncio
async def test_future_planned_date_boats_are_prioritised() -> None:
    """Barcos com prazo planeado FUTURO vêm primeiro: o ORDER BY usa a data-alvo
    filtrada a `> now()` (53% dos barcos têm-na)."""
    sql = await _captured_sql()
    order_by = sql[sql.index("ORDER BY"):]
    assert "data_entrega_prevista" in order_by, "deve ordenar pela data-alvo futura"
    assert "now()" in order_by, "tem de filtrar a prazo FUTURO (> now())"
    assert "::timestamp" in order_by, "compara a data-alvo como timestamp, não texto"


@pytest.mark.asyncio
async def test_fallback_is_fifo_by_creation_age() -> None:
    """Quem não tem prazo futuro cai em FIFO por antiguidade de criação (OF_DATA)."""
    sql = await _captured_sql()
    order_by = sql[sql.index("ORDER BY"):]
    assert '"OF_DATA"' in order_by or "of_data_sort" in order_by
    # O sort naïve antigo (data-alvo NULLS LAST, sem filtro futuro) era o bug.
    assert "data_entrega_prevista NULLS LAST" not in sql


@pytest.mark.asyncio
async def test_due_date_coalesce_still_exposed() -> None:
    """A data-alvo real (COALESCE) continua a sair como due_date para o
    backward-scheduling honrar os ~53% dos barcos com prazo futuro."""
    sql = await _captured_sql()
    assert "data_entrega_prevista" in sql
    assert "OF_PLANO_DATA_PREVISTA" in sql  # a fonte 95% preenchida nos barcos


@pytest.mark.asyncio
async def test_empty_dates_nullif_guarded() -> None:
    """O COALESCE usa NULLIF(...,'') — senão um '' vazio rebenta o ::timestamp
    do ORDER BY (e a função engole o erro devolvendo [] — 0 ordens)."""
    sql = await _captured_sql()
    assert 'NULLIF(ofb."OF_PLANO_DATA_PREVISTA"' in sql


@pytest.mark.asyncio
async def test_em_producao_rule_replaces_staleness() -> None:
    """Q.158 — o scope passa a usar a regra EXATA da NELO de "em produção":
    a OF tem de ter cliente de encomenda (`OF_E_ID_ENC` → entidade) E uma
    operação POR TERMINAR na FASE ATUAL (`OFFP_FP_ID` = `OF_FP_ID`, com
    `OFFP_DATAFIM` NULL). Substitui o filtro de staleness `OF_DATAFIM IS NULL`
    (a NELO ignora-o; o EXISTS é o gate)."""
    sql = await _captured_sql()
    # A regra canónica está presente: cliente + operação aberta na fase atual.
    assert "factory_raw.entidade" in sql, "INNER JOIN ao cliente de encomenda"
    assert "OF_E_ID_ENC" in sql, "correlaciona a OF com o cliente"
    assert "factory_raw.of_fp" in sql, "EXISTS contra of_fp (operação)"
    assert "OFFP_FP_ID" in sql, "operação tem de ser da FASE ATUAL"
    assert "EXISTS" in sql, "a regra é um EXISTS (CROSS APPLY da NELO)"
    # O filtro de staleness por OF_DATAFIM da ORDEMFABRICO desapareceu.
    assert 'ofb."OF_DATAFIM" IS NULL' not in sql, (
        "a regra da NELO ignora OF_DATAFIM — o EXISTS trata"
    )


@pytest.mark.asyncio
async def test_staleness_off_by_default_no_predicate() -> None:
    """Q.158 — staleness é guarda OPCIONAL (default OFF): sem passar
    `staleness_months`, o predicado de vida-recente NÃO entra na SQL (o EXISTS
    da regra em-produção já exclui zombies)."""
    sql = await _captured_sql()
    # O predicado de staleness usa make_interval(months => :staleness_months).
    assert "make_interval" not in sql, "staleness off por defeito → sem predicado"
