"""Q.157.A.1 — aplica decisões REAIS na landing /decisoes.

A página mostrava 3 cartões SEED hardcoded persistidos em ``shared.decision_runs``
(escritos por ``seed_nelo_demo.py:upsert_suggestions`` numa corrida antiga). Este
one-off:
  1. purga SÓ esses 3 (por título-seed exato, status PROPOSED) — ``purge_fake_suggestions``;
  2. corre ``_auto_propose_signals_job`` uma vez → gera decisões PROPOSED reais de
     sinais do plano (saúde de molde + risco OTD).

O backend (mesmo stale) serve já o novo conteúdo da BD via ``GET /v1/decisions``.

Run:
    PYTHONPATH=. ./.venv/Scripts/python.exe scripts/q157_apply_real_decisions.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib
from uuid import UUID

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _load_seed_module():
    """Carrega scripts/seed_nelo_demo.py (não é package) p/ reusar o purge."""
    path = pathlib.Path(__file__).resolve().parent / "seed_nelo_demo.py"
    spec = importlib.util.spec_from_file_location("seed_nelo_demo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main() -> None:
    from src.scheduling.jobs.auto_propose_signals_job import _auto_propose_signals_job
    from src.shared.auth.tenant_context import tenant_scope
    from src.shared.database import async_session_factory
    from src.shared.models.governance import DecisionStatus, SharedDecisionRun
    from sqlalchemy import func, select

    seed = _load_seed_module()

    # 1. Purga os 3 fakes-seed + as decisões de MOLDE (fora de âmbito, Q.157.F).
    from sqlalchemy import delete

    with tenant_scope(DEV_TENANT):
        async with async_session_factory() as session:
            removed = await seed.purge_fake_suggestions(session)
            mold = await session.execute(
                delete(SharedDecisionRun).where(
                    SharedDecisionRun.tenant_id == DEV_TENANT,
                    SharedDecisionRun.status == DecisionStatus.PROPOSED.value,
                    SharedDecisionRun.action_type == "MOLD_MAINTENANCE",
                )
            )
            await session.commit()
    print(
        f">> purgadas {removed} seed (fake) + {mold.rowcount or 0} molde "
        "(fora de âmbito) PROPOSED"
    )

    # 2. Gera as reais (o job envolve tenant_scope por tenant internamente).
    await _auto_propose_signals_job([DEV_TENANT])

    # 3. Conta o que ficou PROPOSED.
    with tenant_scope(DEV_TENANT):
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(SharedDecisionRun.action_type, func.count())
                    .where(
                        SharedDecisionRun.tenant_id == DEV_TENANT,
                        SharedDecisionRun.status == DecisionStatus.PROPOSED.value,
                    )
                    .group_by(SharedDecisionRun.action_type)
                )
            ).all()
    print(">> PROPOSED agora por action_type:")
    for action_type, n in rows:
        print(f"   {action_type}: {n}")
    if not rows:
        print("   (vazio honesto — sem sinais reais para propor)")


if __name__ == "__main__":
    asyncio.run(main())
