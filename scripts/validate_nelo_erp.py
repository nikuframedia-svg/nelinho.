"""Q.25.A/B — validar a ligação viva ao ERP NELO MAR-KAYAKS.

READ-ONLY. Liga via o adapter configurado (`settings.sqlserver_url`) e
exercita cada função de query do `services.py` com limites apertados,
reportando contagens, tempo e a primeira linha de amostra. Apanha erros por
função — uma falha não aborta as outras.

NÃO tem segredos: lê tudo de `settings` / `.env`. É um artefacto do Q.25.

Uso:
    $env:PYTHONPATH = "c:/Users/User/nelinho"
    .\.venv\Scripts\python.exe scripts/validate_nelo_erp.py
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta

from src.adapters.nelo import services


async def _probe(name: str, coro) -> bool:
    """Corre uma query, mede, reporta. Devolve True se OK."""
    t0 = time.perf_counter()
    try:
        res = await coro
        dt = (time.perf_counter() - t0) * 1000
        if isinstance(res, list):
            n, sample = len(res), (res[0] if res else None)
        else:
            n, sample = res, None
        print(f"  OK   {name:36s} {dt:8.0f}ms  -> {n}")
        if sample is not None:
            print(f"       amostra: {repr(sample)[:150]}")
        return True
    except Exception as e:  # noqa: BLE001 — validador: queremos ver tudo
        dt = (time.perf_counter() - t0) * 1000
        print(f"  FALHA {name:35s} {dt:8.0f}ms  {type(e).__name__}: {str(e)[:150]}")
        return False


async def main() -> None:
    from src.shared.config import settings

    print("=== Q.25 — validacao da ligacao ao ERP NELO ===")
    print(f"sqlserver_enabled = {settings.sqlserver_enabled}")
    url = settings.sqlserver_url or ""
    # nunca imprimir a password — so o host/db
    safe = url.split("@")[-1] if "@" in url else url
    print(f"destino           = ...@{safe}")
    print()

    if not settings.sqlserver_enabled:
        print("sqlserver_enabled=False — nada a validar. Aborta.")
        return

    results: list[bool] = []
    results.append(await _probe("health_check", services.health_check()))
    results.append(await _probe("count_open_orders", services.count_open_orders()))
    results.append(await _probe("list_open_orders(3)", services.list_open_orders(limit=3)))
    results.append(await _probe("list_recent_movements(3)", services.list_recent_movements(limit=3)))
    results.append(await _probe("list_current_schedule(3)", services.list_current_schedule(limit=3)))
    results.append(await _probe("list_phases", services.list_phases()))
    results.append(await _probe("list_molds", services.list_molds()))
    results.append(await _probe("list_entity_phases", services.list_entity_phases()))
    results.append(await _probe("top_products_by_orders(3)", services.top_products_by_orders(limit=3)))
    results.append(await _probe("count_movements_last_n_days(30)", services.count_movements_last_n_days(30)))
    results.append(await _probe("list_products(5)", services.list_products(limit=5)))
    results.append(await _probe("list_entities(5)", services.list_entities(limit=5)))

    d_to = date.today()
    d_from = d_to - timedelta(days=30)
    results.append(await _probe("list_operations(30d)", services.list_operations(date_from=d_from, date_to=d_to)))

    # routing/bom precisam de um product_id real — vai buscar um
    try:
        prods = await services.list_products(limit=1)
        if prods:
            pid = prods[0].product_id
            results.append(await _probe(f"get_routing({pid})", services.get_routing(pid)))
            results.append(await _probe(f"get_bom({pid})", services.get_bom(pid)))
    except Exception as e:  # noqa: BLE001
        print(f"  (routing/bom saltados: {type(e).__name__}: {e})")

    await services.close_engine()

    ok = sum(results)
    print()
    print(f"=== {ok}/{len(results)} funcoes OK ===")
    if ok != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
