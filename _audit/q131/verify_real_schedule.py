"""Q.131.B — verificacao AO VIVO (read-only) do CPO sobre dados reais.

Prova o que o Q.126 nunca correu: FactoryState.load() integrado contra a BD
viva resolve ordens reais (WIP de factory_raw, keyspace OF_P_ID) com rotas e
duracoes REAIS (source=history_db), nao o template 2x sintetico.

    .venv\\Scripts\\python.exe _audit\\q131\\verify_real_schedule.py

Escreve _audit/q131/verify_real_schedule.json (ASCII). Nao escreve na BD.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from src.plan.cpo.state import FactoryState  # noqa: E402
from src.plan.services.routing_resolver import RoutingResolver  # noqa: E402

DSN = "postgresql+asyncpg://prodplan:prodplan@localhost:5432/prodplan_one"
TENANT = UUID("00000000-0000-0000-0000-000000000001")
OUT = Path("_audit/q131/verify_real_schedule.json")


async def main() -> None:
    eng = create_async_engine(DSN)
    out: dict = {}
    async with AsyncSession(eng) as s:
        # --- entrada real: o mesmo load() que o scheduler usa ---
        state = await FactoryState.load(session=s, tenant_id=TENANT)

        out["loaded_ok"] = bool(state.loaded_ok)
        out["load_error"] = state.load_error
        out["n_open_orders"] = len(state.open_orders)
        out["n_models_with_route"] = len(state.historical_routes_by_model)
        out["n_models_with_mold"] = len(state.molds_by_model)
        out["n_phases_with_skills"] = len(state.skill_matrix)
        out["n_duration_pairs"] = len(state.historical_durations)

        # medianas reais das fases calibradas (fonte de verdade dos numeros)
        by_fase = state.historical_durations_by_fase
        out["fase_medians"] = {
            "1_laminagem": by_fase.get("1"),
            "2_cura": by_fase.get("2"),
            "18_pintura": by_fase.get("18"),
            "5_pintura_acab": by_fase.get("5"),
        }

        # --- overlap de keyspace: as ordens reais casam com routing/molds? ---
        order_models = [str(o.get("modelo_id") or "") for o in state.open_orders]
        route_keys = set(state.historical_routes_by_model.keys())
        mold_keys = set(state.molds_by_model.keys())
        n = len(order_models) or 1
        in_route = sum(1 for m in order_models if m in route_keys)
        in_mold = sum(1 for m in order_models if m in mold_keys)
        out["orders_with_real_route"] = in_route
        out["orders_with_real_route_pct"] = round(100.0 * in_route / n, 1)
        out["orders_with_mold"] = in_mold
        out["orders_with_mold_pct"] = round(100.0 * in_mold / n, 1)
        out["sample_open_orders"] = state.open_orders[:5]

        # --- resolver as ordens reais e medir a fonte das duracoes ---
        resolver = RoutingResolver(state)
        ops = resolver.resolve_many(state.open_orders)
        out["n_operations_resolved"] = len(ops)
        out["fallback_fraction"] = round(resolver.fallback_fraction, 4)
        out["engine_unavailable"] = bool(resolver.engine_unavailable)

        # source por operacao (via o RoutingRow -> nao exposto no op; reconta
        # resolvendo a 1a ordem com rastreio das rows)
        src_counter: Counter = Counter()
        for o in state.open_orders:
            rows = []
            oid = str(o.get("of_id") or "")
            mid = str(o.get("modelo_id") or "")
            rows = (
                resolver._history_for_order(oid)
                or resolver._history_for_model(mid)
                or resolver._history_for_model_db(mid)
                or resolver._standard_template(mid)
            )
            for r in rows:
                src_counter[r.source] += 1
        out["source_distribution"] = dict(src_counter)

        # amostra de rota real (1o modelo com >=3 fases)
        sample = next(
            (m for m, st in state.historical_routes_by_model.items() if len(st) >= 3),
            None,
        )
        if sample is not None:
            out["sample_model"] = sample
            out["sample_route"] = [
                {"fase": st["fase_nome"], "seq": st["sequence"],
                 "dur_h": round(float(st["duration_hours"]), 3)}
                for st in state.historical_routes_by_model[sample][:8]
            ]

    await eng.dispose()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(out, indent=2, default=str, ensure_ascii=True),
        encoding="utf-8",
    )
    # resumo legivel
    print("=== Q.131.B verificacao AO VIVO ===")
    print(f"loaded_ok            : {out['loaded_ok']}")
    print(f"open_orders (WIP)    : {out['n_open_orders']}")
    print(f"models with route    : {out['n_models_with_route']}")
    print(f"orders w/ real route : {out['orders_with_real_route']} "
          f"({out['orders_with_real_route_pct']}%)")
    print(f"orders w/ mold       : {out['orders_with_mold']} "
          f"({out['orders_with_mold_pct']}%)")
    print(f"operations resolved  : {out['n_operations_resolved']}")
    print(f"fallback_fraction    : {out['fallback_fraction']}")
    print(f"source_distribution  : {out['source_distribution']}")
    print(f"fase_medians         : {out['fase_medians']}")
    print("WROTE", OUT)


if __name__ == "__main__":
    asyncio.run(main())
