"""Q.137 — replan CPO automático (planos aparecem sozinhos no grid).

O CPO só nascia a pedido (botão) ou por eventos Kafka (off). Este job corre no
APScheduler (in-process, leve) a cada 15 min e, quando o WIP de barcos mudou
(reativo ao sync do ERP), **enfileira** o `cpo_schedule_job` no Arq — o worker
(processo separado) corre o CPO pesado e persiste um **DRAFT** (Q.17: nunca
auto-LIVE; aprovação humana via write-gate). O grid `/overall` faz polling de
30s ao `/cpo/commits` → o DRAFT aparece sozinho.

Anti-spam: rate-limit (default 60 min) + deteção de mudança por watermark do
WIP-barco em `factory_raw.ordemfabrico` (o que o CPO realmente lê). 1ª corrida
(sem watermark) dispara sempre (plano inicial). Best-effort: Redis/worker em
baixo → log + skip, sem crashar o scheduler.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")
_DEFAULT_MIN_GAP_MIN = 60
# Q.161.B — o robô é um job de FUNDO (não-interativo): planeia TODOS os barcos em
# produção (plan_cap=0) com um time_limit generoso, ao contrário do botão
# "Replanear" interativo (200 ordens, <90s). Overrides em
# `planning.auto_replan_plan_cap` / `planning.auto_replan_time_limit_s`.
_DEFAULT_ROBOT_PLAN_CAP = 0          # 0 = todos os em-produção
_DEFAULT_ROBOT_TIME_LIMIT_S = 600.0  # 10 min (tecto do CPOScheduleRequest)

# Estado in-memory por tenant: (último enqueue, watermark do WIP nesse momento).
# Reset no restart é aceitável — apenas re-planeia 1× após rearranque.
_last_run: Dict[UUID, Tuple[datetime, Tuple[int, str]]] = {}

# Watermark barato do WIP-barco: nº de barcos em produção + max actualização.
# Q.158 — lê da MESMA view que o CPO scope (`_load_open_orders_db`) e o display:
# `factory_raw.v_of_em_producao` (regra EXATA da NELO — op aberta na fase atual).
# Substitui o critério antigo deck+casco + OF_DATAFIM IS NULL, que divergia do
# que o CPO realmente planeia. `n` = ≈1209 (nova+fila+reparações).
_WATERMARK_SQL = text(
    """
    SELECT count(*) AS n,
           COALESCE(max(ofb."OF_DATAACTUALIZACAO"), '') AS hw
    FROM factory_raw.v_of_em_producao v
    JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = v.of_id
    """
)


async def _resolve_tenants(tenant_ids: List[UUID]) -> List[UUID]:
    """Lista passada ou, se vazia, tenants activos da BD.

    Cai no tenant de DEV como ÚLTIMO recurso (descoberta falhou ou 0 activos).
    Em produção isto é um ERRO (job a correr sem tenant real), por isso fica
    logado a ERROR — nunca silencioso.
    """
    if tenant_ids:
        return list(tenant_ids)
    try:
        from src.core.models.tenant import TenantStatus
        from src.core.services.tenant_service import TenantService
        from src.shared.database import get_session_context

        async with get_session_context() as session:
            ts = TenantService(session)
            active = await ts.list_tenants(status=TenantStatus.ACTIVE, limit=1000)
            ids = [t.id for t in active]
        if ids:
            return ids
        logger.error(
            "auto_cpo_replan: 0 tenants activos na BD — fallback para o tenant "
            "de DEV (%s). Em produção isto NÃO devia acontecer.",
            _DEV_TENANT,
        )
    except (SQLAlchemyError, ImportError, AttributeError) as exc:
        logger.error(
            "auto_cpo_replan: descoberta de tenants falhou (%s) — fallback para o "
            "tenant de DEV (%s). Em produção isto NÃO devia acontecer.",
            exc, _DEV_TENANT,
        )
    return [_DEV_TENANT]


async def _wip_watermark(session) -> Optional[Tuple[int, str]]:
    """`(count, max_actualizacao)` do WIP-barco; None em falha (best-effort)."""
    try:
        row = (await session.execute(_WATERMARK_SQL)).first()
    except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente / outage
        logger.debug("auto_cpo_replan: watermark skip (%s)", exc)
        return None
    if row is None:
        return None
    return (int(row.n), str(row.hw))


async def _read_config(session, tenant_id: UUID) -> Tuple[bool, int, int, float]:
    """`(enabled, min_gap_min, plan_cap, time_limit_s)` de `planning.*`; defaults
    se indisponível. Q.161.B — plan_cap/time_limit do robô (job de fundo)."""
    try:
        from src.core.services.tenant_config_service import TenantConfigService

        planning = await TenantConfigService(session, tenant_id).get_category("planning")
        enabled = str(planning.get("auto_replan_enabled", "true")).lower() not in (
            "false", "0", "no",
        )
        gap = int(planning.get("auto_replan_min_gap_min", _DEFAULT_MIN_GAP_MIN))
        plan_cap = int(planning.get("auto_replan_plan_cap", _DEFAULT_ROBOT_PLAN_CAP))
        time_limit = float(
            planning.get("auto_replan_time_limit_s", _DEFAULT_ROBOT_TIME_LIMIT_S)
        )
        return enabled, max(1, gap), max(0, plan_cap), max(1.0, time_limit)
    except (SQLAlchemyError, ImportError, ValueError, AttributeError, TypeError):
        return (
            True, _DEFAULT_MIN_GAP_MIN,
            _DEFAULT_ROBOT_PLAN_CAP, _DEFAULT_ROBOT_TIME_LIMIT_S,
        )


async def _enqueue_cpo(
    tenant_id: UUID, watermark: Tuple[int, str],
    plan_cap: int = _DEFAULT_ROBOT_PLAN_CAP,
    time_limit_s: float = _DEFAULT_ROBOT_TIME_LIMIT_S,
) -> bool:
    """Enfileira `cpo_schedule_job` no Arq. Best-effort: Redis/arq down → False.

    Q.142.A — dedup determinístico via `_job_id`. Sob `uvicorn --workers 2` há 2
    schedulers in-process (1 por worker), cada um com o seu `_last_run`/watermark
    in-memory → ambos achavam que era "1ª corrida" e enfileiravam → 2 DRAFTs
    idênticos por ciclo. Como os 2 workers computam o MESMO watermark do MESMO
    WIP, geram o MESMO `_job_id` e o Arq coalesce para 1 só job (dentro de
    `keep_result=3600s` ≈ rate-limit de 60 min) → 1 só DRAFT. WIP muda → novo
    watermark → novo `_job_id` → novo plano.

    Usa-se `_job_id` e NÃO `with_advisory_lock` (o padrão de causal/dpo) porque
    este job é rápido — só enfileira; o lock session-level libertava-se em ms e
    não cobria ticks desfasados entre workers. O dedup tem de ser durável (Arq).
    """
    try:
        from arq.connections import RedisSettings, create_pool

        from src.plan.api.cpo import CPOScheduleRequest
        from src.shared.config import settings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    except (OSError, ConnectionError, RuntimeError, ImportError) as exc:
        logger.warning("auto_cpo_replan: Arq/Redis indisponível (%s); skip", exc)
        return False
    try:
        wm_sig = hashlib.sha256(
            f"{watermark[0]}|{watermark[1]}".encode("utf-8")
        ).hexdigest()[:16]
        job_id = f"auto_cpo:{tenant_id}:{wm_sig}"
        # Q.161.B — robô planeia TODOS os em-produção (plan_cap=0) com time_limit
        # de fundo (não-interativo). O grid /overall passa a mostrar a produção
        # real, não só as 200 mais urgentes.
        await redis.enqueue_job(
            "cpo_schedule_job",
            CPOScheduleRequest(
                plan_cap=plan_cap, time_limit_sec=time_limit_s,
            ).model_dump(mode="json"),
            str(tenant_id),
            "system",
            _job_id=job_id,
        )
    finally:
        await redis.close()
    return True


async def _auto_cpo_replan_global_job(tenant_ids: List[UUID]) -> None:
    """Por tenant: config-gate + rate-limit + deteção de mudança → enfileira CPO.

    Registado no scheduler core a cada 15 min. Best-effort por tenant."""
    from src.shared.database import get_session_context

    now = datetime.now(timezone.utc)
    tenants = await _resolve_tenants(tenant_ids)
    for tid in tenants:
        try:
            async with get_session_context() as session:
                enabled, gap_min, plan_cap, time_limit = await _read_config(
                    session, tid,
                )
                if not enabled:
                    continue
                last = _last_run.get(tid)
                if last is not None and (now - last[0]).total_seconds() < gap_min * 60:
                    continue  # rate-limit: ainda dentro do gap
                wm = await _wip_watermark(session)
            if wm is None or wm[0] == 0:
                continue  # sem barcos / sem dados → nada a planear
            if last is not None and wm == last[1]:
                continue  # WIP inalterado desde o último plano → não repetir
            if await _enqueue_cpo(tid, wm, plan_cap, time_limit):
                _last_run[tid] = (now, wm)
                logger.info(
                    "auto_cpo_replan: CPO enfileirado tenant=%s wip_barcos=%s "
                    "plan_cap=%s time_limit=%.0fs",
                    tid, wm[0], plan_cap, time_limit,
                )
        except (SQLAlchemyError, OSError, RuntimeError, ValueError, ImportError) as exc:
            logger.error(
                "auto_cpo_replan tenant=%s falhou: %s", tid, exc, exc_info=True,
            )
