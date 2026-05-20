"""Q.61.16 — init_db deixa de fazer create_all em producao.

Antes: cada arranque do uvicorn chamava `Base.metadata.create_all`,
mascarando drift entre Alembic e os modelos SQLA (se um modelo novo
nao estivesse no alembic/env.py, create_all criava na mesma a tabela
e producao via `alembic upgrade head` deixava-a orfa).

Q.61.16: init_db apenas VERIFICA que ha uma revision Alembic aplicada;
crash early se nao. Caminho de teste/dev continua a usar create_all
via `init_db_create_all()`.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path


def _function_ast(module_path: Path, fn_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == fn_name:
                return node
    raise AssertionError(f"funcao {fn_name!r} nao encontrada em {module_path}")


def _references_attr(func_node, attr_name: str) -> bool:
    """True se a funcao referencia .<attr_name> no body — em call directa
    OU passado como callable (run_sync(Base.metadata.create_all))."""
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Attribute) and sub.attr == attr_name:
            return True
    return False


# alias historico para tests legiveis
_calls_attr = _references_attr


def _module_path() -> Path:
    import src.shared.database as db_mod
    return Path(inspect.getfile(db_mod))


def test_init_db_does_not_call_create_all():
    """Regression: init_db nao pode voltar a chamar Base.metadata.create_all.

    AST inspection ignora docstrings (mencao em texto e OK) — so falha
    se houver chamada real.
    """
    init_db = _function_ast(_module_path(), "init_db")
    assert not _calls_attr(init_db, "create_all"), (
        "Q.61.16 regression — init_db voltou a chamar create_all. "
        "Producao deve usar `alembic upgrade head`; use "
        "`init_db_create_all()` para tests/dev."
    )


def test_init_db_create_all_helper_exists_for_tests():
    """O helper `init_db_create_all` esta exposto para tests/fixtures."""
    from src.shared.database import init_db_create_all

    assert callable(init_db_create_all)


def test_init_db_create_all_actually_calls_create_all():
    """O helper certificado e o unico ponto valido para create_all."""
    helper = _function_ast(_module_path(), "init_db_create_all")
    assert _calls_attr(helper, "create_all"), (
        "init_db_create_all nao chama create_all — sem este helper, "
        "tests/fixtures ficam sem caminho rapido para schema setup."
    )


def test_only_init_db_create_all_uses_create_all_in_database_module():
    """Walk AST de src/shared/database.py: a unica funcao que chama
    `create_all` deve ser `init_db_create_all`."""
    module_path = _module_path()
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    fns_calling_create_all: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _calls_attr(node, "create_all"):
                fns_calling_create_all.append(node.name)
    assert fns_calling_create_all == ["init_db_create_all"], (
        f"Funcoes que chamam create_all em src/shared/database.py: "
        f"{fns_calling_create_all!r}. Esperado: ['init_db_create_all']."
    )
