"""Q.61.22 — lifespan paraleliza Redis/Kafka/tool_registry/YAML refresh.

AST inspection do lifespan (Q.67.6.C2 moveu de src/main.py para
src/app/startup.py via src/app/lifespan.py). A logica gather + degraded
ficou em src/app/startup.py:run_startup; src/app/lifespan.py apenas
wrap-a num asynccontextmanager. Inspecciona-se ambos para cobrir o
invariante completo.

  * usa `asyncio.gather` para paralelizar subsistemas
  * mantem `init_db` ANTES (e dep de schema; nao paraleliza)
  * usa `return_exceptions=True` para nao crashar startup se um cair
  * popula `app.state.degraded_subsystems` para health endpoint expor
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path


def _module_source() -> str:
    """Source de src/app/startup.py (onde o gather + degraded vive
    após Q.67.6.C2 decomp). Fallback para src/main.py para compat."""
    try:
        import src.app.startup as startup_mod
        return Path(inspect.getfile(startup_mod)).read_text(encoding="utf-8")
    except ImportError:
        import src.main as main_mod
        return Path(inspect.getfile(main_mod)).read_text(encoding="utf-8")


def _lifespan_node() -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Localiza a função que contém o asyncio.gather invariante.
    Pós Q.67.6.C2 é `run_startup` em src/app/startup.py; pre era
    `lifespan` em src/main.py.
    """
    tree = ast.parse(_module_source())
    for target_name in ("run_startup", "lifespan"):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == target_name:
                    return node
    raise AssertionError(
        "Q.67.6.C2 invariant: nem run_startup (src/app/startup.py) nem "
        "lifespan (src/main.py) encontrados — alguém quebrou a decomp."
    )


def _calls(func_node, full_name: str) -> int:
    """Conta chamadas a `obj.attr(...)` ou `name(...)` no body."""
    count = 0
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            try:
                src = ast.unparse(sub.func)
            except Exception:
                continue
            if src == full_name or src.endswith("." + full_name.split(".")[-1]):
                if full_name in src or full_name.split(".")[-1] == src:
                    count += 1
    return count


def test_lifespan_uses_asyncio_gather():
    """Regression: lifespan tem de paralelizar com asyncio.gather."""
    node = _lifespan_node()
    found = False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            try:
                src = ast.unparse(sub.func)
            except Exception:
                continue
            if src == "asyncio.gather":
                found = True
                break
    assert found, (
        "Q.61.22 regression: lifespan deixou de usar asyncio.gather. "
        "Voltou ao padrao sequencial — startup volta a ser ~50s."
    )


def test_lifespan_calls_gather_with_return_exceptions():
    """gather precisa de return_exceptions=True para nao tombar tudo
    se um subsistema cair (modo degraded explicito)."""
    node = _lifespan_node()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            try:
                src = ast.unparse(sub.func)
            except Exception:
                continue
            if src == "asyncio.gather":
                kwargs = {kw.arg: kw for kw in sub.keywords}
                assert "return_exceptions" in kwargs, (
                    "asyncio.gather sem return_exceptions — uma falha "
                    "rebenta TODO o startup. Q.61.22 quer modo degraded."
                )
                val = kwargs["return_exceptions"].value
                assert isinstance(val, ast.Constant) and val.value is True, (
                    "return_exceptions deve ser literal True"
                )
                return
    raise AssertionError("asyncio.gather nao encontrado no lifespan")


def test_lifespan_calls_init_db_before_gather():
    """init_db continua a ser primeiro (deps de schema)."""
    node = _lifespan_node()
    init_db_lineno: int | None = None
    gather_lineno: int | None = None
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            try:
                src = ast.unparse(sub.func)
            except Exception:
                continue
            if src == "init_db" and init_db_lineno is None:
                init_db_lineno = sub.lineno
            elif src == "asyncio.gather" and gather_lineno is None:
                gather_lineno = sub.lineno

    assert init_db_lineno is not None, "init_db() nao chamado no lifespan"
    assert gather_lineno is not None, "asyncio.gather nao chamado no lifespan"
    assert init_db_lineno < gather_lineno, (
        f"init_db tem de ser ANTES de asyncio.gather (deps de schema). "
        f"init_db linha {init_db_lineno}, gather linha {gather_lineno}."
    )


def test_lifespan_tracks_degraded_subsystems():
    """app.state.degraded_subsystems exposto para health endpoint."""
    source = _module_source()
    assert "degraded_subsystems" in source, (
        "lifespan deixou de exportar degraded_subsystems — health "
        "endpoint nao tem como mostrar 'kafka offline mas app vivo'."
    )
    assert "app.state.degraded_subsystems" in source, (
        "degraded_subsystems tem de estar em app.state para o health "
        "endpoint ler."
    )
