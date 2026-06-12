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
    """Captura o SQL (e os params) gerados por `_load_open_orders_db` (sem BD)."""

    def __init__(self) -> None:
        self.sql_text = ""
        self.params: dict = {}

    async def execute(self, stmt, params=None):
        self.sql_text = str(stmt)
        self.params = params or {}
        return _CaptureResult()


async def _captured_sql(scope: str = "boats_only") -> str:
    from src.plan.cpo.state import _load_open_orders_db

    sess = _CaptureSession()
    await _load_open_orders_db(sess, TENANT, scope=scope)
    return sess.sql_text


async def _captured(plan_cap=None, scope: str = "boats_only") -> _CaptureSession:
    """Devolve a sessão capturada (sql_text + params), para testar o cap."""
    from src.plan.cpo.state import _load_open_orders_db

    sess = _CaptureSession()
    await _load_open_orders_db(sess, TENANT, scope=scope, plan_cap=plan_cap)
    return sess


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


# =============================================================================
# Q.161.A — reparações no horizonte + cap por contexto
# =============================================================================


@pytest.mark.asyncio
async def test_repairs_prioritised_before_limit_q161() -> None:
    """Q.161.A — reparações (fase {14,76,77}) entram no ORDER BY ANTES do LIMIT,
    como PRIMEIRA chave (`repair_rank`). Sem isto, as reparações — prazo passado/
    ausente, criação antiga — caíam sempre abaixo do cap e nunca eram planeadas."""
    sql = await _captured_sql()
    # rindex: a cláusula ORDER BY real (a 1ª ocorrência "ORDER BY" está num
    # comentário do inner SELECT — "...o ::timestamp do ORDER BY rebenta").
    order_by = sql[sql.rindex("ORDER BY"):]
    assert "repair_rank" in order_by, "a prioridade de reparação entra no ORDER BY"
    # repair_rank vem ANTES da prioridade de prazo futuro (é a 1ª chave).
    assert order_by.index("repair_rank") < order_by.index("data_entrega_prevista"), (
        "reparação tem de ordenar ANTES do prazo (senão cai abaixo do LIMIT)"
    )
    # Os ids de fase de reparação (DRY com REPAIR_PHASE_IDS) estão no CASE.
    from src.plan.cpo.state import REPAIR_PHASE_IDS
    for fid in REPAIR_PHASE_IDS:
        assert fid in sql, f"id de fase de reparação {fid} no CASE repair_rank"


@pytest.mark.asyncio
async def test_plan_cap_default_is_interactive_horizon_q161() -> None:
    """Q.161.A — sem `plan_cap`, o horizonte é o interativo (200)."""
    from src.plan.cpo.state_loaders import _OPEN_ORDERS_PLAN_CAP

    sess = await _captured(plan_cap=None)
    assert _OPEN_ORDERS_PLAN_CAP == 200
    assert sess.params["plan_cap"] == _OPEN_ORDERS_PLAN_CAP


@pytest.mark.asyncio
async def test_plan_cap_zero_means_all_in_production_q161() -> None:
    """Q.161.A — `plan_cap <= 0` = TODOS os em-produção (tecto de segurança da GA)
    — o que o robô de fundo usa para planear os ~825/1209, não só 200."""
    from src.plan.cpo.state_loaders import _OPEN_ORDERS_HARD_CAP

    sess = await _captured(plan_cap=0)
    assert sess.params["plan_cap"] == _OPEN_ORDERS_HARD_CAP
    assert _OPEN_ORDERS_HARD_CAP >= 1209, "o tecto cobre o pool em-produção real"


@pytest.mark.asyncio
async def test_plan_cap_explicit_value_clamped_q161() -> None:
    """Q.161.A — `plan_cap > 0` é respeitado e fica abaixo do tecto."""
    from src.plan.cpo.state_loaders import _OPEN_ORDERS_HARD_CAP

    sess = await _captured(plan_cap=900)
    assert sess.params["plan_cap"] == 900
    sess2 = await _captured(plan_cap=999999)
    assert sess2.params["plan_cap"] == _OPEN_ORDERS_HARD_CAP, "clamp ao tecto"


# ───────────────────── Q.174.F0.5 — exclusão de clientes ─────────────────────


@pytest.mark.asyncio
async def test_cliente_fabrica_excluido_por_defeito_q174():
    """Canónico: Planeamento_Previsão exclui SEMPRE o Cliente Fábrica
    (e_id=19747) da seleção de barcos a planear (corpo lido live 2026-06-12).
    Sem config, o default replica-o."""
    sql = await _captured_sql()
    assert '"OF_E_ID_ENC" NOT IN (19747)' in sql


@pytest.mark.asyncio
async def test_excluded_client_ids_configuravel_q174():
    """`planning.excluded_client_ids` substitui o default (e ordena)."""
    from src.plan.cpo.state import _load_open_orders_db

    sess = _CaptureSession()
    await _load_open_orders_db(
        sess, TENANT, excluded_client_ids=frozenset({111, 19747}),
    )
    assert '"OF_E_ID_ENC" NOT IN (111, 19747)' in sess.sql_text


@pytest.mark.asyncio
async def test_excluded_client_ids_vazio_desliga_q174():
    """Vazio EXPLÍCITO ⇒ sem predicado (opt-out consciente, não default)."""
    from src.plan.cpo.state import _load_open_orders_db

    sess = _CaptureSession()
    await _load_open_orders_db(sess, TENANT, excluded_client_ids=frozenset())
    assert "NOT IN" not in sess.sql_text
