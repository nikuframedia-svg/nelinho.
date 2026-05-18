"""Q.38.B — sincronizar os ~510 moldes do Excel para `plan.mold`.

CLI fino: lê a folha `Moldes` de `Folha_IA_extra.xlsx` e faz upsert
idempotente em `plan.mold`. Os ~91 moldes do ERP `MOLDES` vêm pelo
mirror `molds` (`sync_nelo_erp.py --only molds`); este caminho traz os
restantes ~419 que só vivem no Excel.

Pré-requisitos:
  * o Postgres do ProdPlan ONE acessível (`bootstrap_dev_full.py` correu);
  * o ficheiro `Folha_IA_extra.xlsx` na raiz do repo (ou passar `--file`).

Uso::

    .\\.venv\\Scripts\\python.exe scripts\\sync_excel_molds.py
    .\\.venv\\Scripts\\python.exe scripts\\sync_excel_molds.py --file caminho\\para\\Folha.xlsx
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
_DEFAULT_EXCEL = Path(__file__).resolve().parent.parent / "Folha_IA_extra.xlsx"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sync_excel_molds",
        description="Sincronizar os ~510 moldes do Excel para plan.mold.",
    )
    parser.add_argument(
        "--file", metavar="PATH", default=str(_DEFAULT_EXCEL),
        help="Caminho do Folha_IA_extra.xlsx (default: raiz do repo).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    excel_path = Path(args.file)
    if not excel_path.exists():
        print(f"[FAIL] ficheiro Excel não encontrado: {excel_path}")
        return 1

    from src.factory_data_product.etl.molds_sync import sync_molds_from_excel
    from src.shared.database import async_session_factory

    print(f"sync_excel_molds — {excel_path}")
    try:
        async with async_session_factory() as session:
            result = await sync_molds_from_excel(
                session=session, tenant_id=DEV_TENANT_ID, file_path=excel_path,
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — top-level reporter
        print(f"[FAIL] sync abortado: {type(exc).__name__}: {exc}")
        return 1

    print(
        f"  [{result.status}] read={result.rows_read} "
        f"ins={result.rows_inserted} upd={result.rows_updated} "
        f"skip={result.rows_skipped}"
    )
    if result.status != "ok":
        print(f"  erro: {result.error}")
        return 1
    print("[OK] plan.mold sincronizado a partir do Excel.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
