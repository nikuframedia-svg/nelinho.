"""Q.133.A1 — corrida manual da calibração de durações.

Popula `plan.phase_duration_calibration` (p50/p95 por modelo,fase de of_fp) para
o tenant dev. O scheduler corre isto às 06:40 UTC; este script é para população
manual / demo / verificação.

Uso::

    $env:PYTHONPATH = "."
    .\\.venv\\Scripts\\python.exe scripts/q133_calibrate_durations.py
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from src.scheduling.jobs.phase_calibration_job import _phase_calibration_job

DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


def main() -> int:
    n = asyncio.run(_phase_calibration_job(DEV_TENANT))
    print(f"phase_duration_calibration: {n} pares (modelo, fase) calibrados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
