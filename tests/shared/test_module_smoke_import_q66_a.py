"""Q.66.A.2 — smoke import por módulo top-level.

Lesson Shopify Packwerk: um ficheiro pode passar lint estático (ruff, mypy)
mas crashar em runtime quando alguém o tenta importar isolado — NameError em
top-level, ImportError numa dependência opcional carregada eagerly, ciclo
de import só detectado no carregamento, side-effect a tentar abrir DB, etc.

Cada teste IMPORTA o módulo num subprocess fresh (sys.executable -c) para
isolar 100%. Não usa importlib.reload — não chega para módulos com
side-effects no import-time (gauges Prometheus, registos em logging, etc.)
e o sys.modules cache do test runner mascara crashes que aconteceriam num
worker fresh.

Cwd do subprocess = repo root para que `src.*` resolva via PYTHONPATH
implícito (pyproject.toml define `tool.setuptools.packages.find` em src/
mas em dev corremos com PYTHONPATH=repo-root).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"

# Lista snapshot dos módulos top-level em src/ (Q.66.A.2 baseline).
# Se um módulo for adicionado/removido, o teste `test_module_list_is_in_sync`
# falha e força a actualização manual desta constante.
MODULES = sorted([
    "src.adapters",
    "src.app",  # Q.67.6.C2 — extraído de src/main.py god-file (startup/lifespan/registries)
    "src.copilot",
    "src.core",
    "src.diagnostics",
    "src.dqa",
    "src.explain",
    "src.factory_data_product",
    "src.governance",
    "src.hr",
    "src.improve",
    "src.infrastructure",
    "src.ml",
    "src.observability",  # Q.66.E.3 — agent_actions endpoint
    "src.plan",
    "src.profit",
    "src.quality",
    "src.reports",
    "src.sandbox",
    "src.scheduling",  # Q.66.A.4 — extraído de src.shared.scheduler god-file
    "src.search",
    "src.shared",
    "src.supply",
    "src.twin",
    "src.workforce",
])


def _discover_actual_modules() -> list[str]:
    """Lista os pacotes top-level em src/ (dirs com __init__.py)."""
    out: list[str] = []
    if not SRC_DIR.is_dir():
        return out
    for entry in sorted(SRC_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_") or entry.name.startswith("."):
            continue
        if (entry / "__init__.py").is_file():
            out.append(f"src.{entry.name}")
    return out


def test_module_list_is_in_sync():
    """Garante que MODULES espelha o filesystem actual.

    Se este teste falhar, alguém adicionou/removeu um módulo top-level em
    src/ sem actualizar a constante MODULES neste ficheiro. Actualiza a
    constante e corre o smoke do módulo novo.
    """
    actual = _discover_actual_modules()
    assert actual == MODULES, (
        "Módulos top-level em src/ divergem da snapshot Q.66.A.2.\n"
        f"  Filesystem: {actual}\n"
        f"  MODULES:    {MODULES}\n"
        "Actualiza MODULES neste ficheiro e re-corre."
    )


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_isolated(module: str):
    """Importa <module> num subprocess fresh.

    Falha rápida se algo no import-time crasha (NameError em top-level,
    dependência opcional eagerly importada, ciclo, side-effect a abrir
    socket/DB, etc.). 30s timeout — import puro nunca devia chegar perto.
    """
    env = os.environ.copy()
    # PYTHONPATH = repo root garante que `import src.foo` resolve mesmo
    # quando o subprocess herda um cwd diferente do esperado.
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT}{os.pathsep}{existing_pp}" if existing_pp else str(REPO_ROOT)
    )

    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
        env=env,
    )

    assert result.returncode == 0, (
        f"Failed to import {module!r} in fresh subprocess "
        f"(rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
