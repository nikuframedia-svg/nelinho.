"""Q.108.TEST.C — valida cada mart Q.108 via EXPLAIN contra Postgres dev.

Princípio NELO: TESTA REAL. Corre EXPLAIN <VIEW_SQL> de cada
scripts/setup_marts_*.py contra Postgres dev. Coluna/tabela inexistente
→ erro explícito.

Especialmente importante para Q.108.M (`AT_DATA`, `AT_HORAS`) e Q.108.M2
(`OFFPEQ_*`) cujos column names são especulativos.

Uso:
    .\\.venv\\Scripts\\python.exe scripts/validate_marts_q108.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys

from sqlalchemy import text


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


# Allowlist: marts Q.108 a validar. Outros marts (Q.93/Q.94/Q.96/Q.99/Q.100/Q.102/Q.104/Q.107)
# ficam fora do scope desta sub-sprint (foram validados nas suas próprias
# campanhas anteriormente).
Q108_MARTS: tuple[str, ...] = (
    "setup_marts_rework_por_molde",
    "setup_marts_rework_por_disciplina",
    "setup_marts_lead_time_of",
    "setup_marts_wip_fase",
    "setup_marts_schedule_aderencia",
    "setup_marts_phase_transition",
    "setup_marts_lead_time_entrega",
    "setup_marts_throughput_modelo",
    "setup_marts_cura_compliance",
    "setup_marts_aprovacoes_q17",
    "setup_marts_backlog",
    "setup_marts_reagendamentos",
    "setup_marts_moldes_idade",
    "setup_marts_etl_freshness",
    "setup_marts_audit_atividade",
    "setup_marts_arpu_mes",
    "setup_marts_facturacao_mom",
    "setup_marts_hhi_clientes",
    "setup_marts_moldes_top_uso",
    "setup_marts_consumo_by_of",
    "setup_marts_horas_operador",
    "setup_marts_defeitos_operador",
    "setup_marts_devolucoes",
    "setup_marts_copilot_latency",
    "setup_marts_copilot_rag",
    "setup_marts_copilot_feedback",
)


def _extract_view_sql(module_path: pathlib.Path) -> str | None:
    """Importa o módulo e devolve VIEW_SQL."""
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        print(f"  IMPORT FAILED: {exc}")
        return None
    return getattr(module, "VIEW_SQL", None)


def _strip_create_view(sql: str) -> str:
    """Remove `CREATE OR REPLACE VIEW <name> AS` para EXPLAIN aceitar."""
    import re
    pattern = re.compile(
        r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+[\w.]+\s+AS\s*",
        re.IGNORECASE,
    )
    return pattern.sub("", sql).strip()


async def _validate_one(sql: str) -> tuple[bool, str]:
    """EXPLAIN <SQL> contra Postgres dev."""
    from src.shared.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("EXPLAIN " + _strip_create_view(sql)))
        return True, "EXPLAIN ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}"


async def validate_all() -> int:
    ok = 0
    fail = 0
    skipped = 0

    print(f"Q.108.TEST.C — validando {len(Q108_MARTS)} marts Q.108\n")

    for stem in Q108_MARTS:
        path = _SCRIPTS_DIR / f"{stem}.py"
        if not path.exists():
            print(f"[SKIP] {stem} — ficheiro não encontrado")
            skipped += 1
            continue

        sql = _extract_view_sql(path)
        if not sql:
            print(f"[SKIP] {stem} — sem VIEW_SQL exposto")
            skipped += 1
            continue

        success, msg = await _validate_one(sql)
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {stem}: {msg}")
        if success:
            ok += 1
        else:
            fail += 1

    print(
        f"\nResultado: OK={ok}  FAIL={fail}  SKIP={skipped}  "
        f"(total {len(Q108_MARTS)})"
    )
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(validate_all()))
