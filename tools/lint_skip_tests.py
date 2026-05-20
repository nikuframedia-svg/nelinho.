#!/usr/bin/env python3
"""Q.66.C.1 — bloqueia @pytest.mark.skip / .xfail sem GH issue link.

Test-cheating pattern (Stella Laurenzo, Test Double): agente AI quer
fazer test passar e, em vez de fixar o code, adiciona `@pytest.mark.skip`.
Esta script falha CI se encontrar `skip` / `skipif` / `xfail` SEM
comentario `GH #NNN` (ou `#NNN`) no mesmo line ou nos 2 lines acima.

Uso:
    python tools/lint_skip_tests.py                # default: tests/
    python tools/lint_skip_tests.py tests/ src/    # paths custom
    python tools/lint_skip_tests.py --baseline N   # tolera N violacoes

Sai com codigo 1 se violacoes > baseline; 0 caso contrario.

Nao trata `pytest.skip(...)` runtime inline dentro do corpo do teste —
esses sao normalmente env-conditional skips legitimos (ex: APScheduler
nao instalado). So decoradores aparecem como anti-padrao agente.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

GH_ISSUE_RX = re.compile(r"(GH|#)\s*\d+", re.IGNORECASE)
SKIP_DECORATORS = {"skip", "skipif", "xfail"}


def _is_pytest_mark_skip(node: ast.expr) -> str | None:
    """Devolve o nome ('skip'/'skipif'/'xfail') se for `pytest.mark.X`.

    Aceita tanto `@pytest.mark.skip` (Attribute) como
    `@pytest.mark.skip(reason=...)` (Call). Devolve None caso contrario.
    """
    target = node.func if isinstance(node, ast.Call) else node
    if not isinstance(target, ast.Attribute):
        return None
    if target.attr not in SKIP_DECORATORS:
        return None
    # target.value deve ser `pytest.mark`
    parent = target.value
    if not isinstance(parent, ast.Attribute) or parent.attr != "mark":
        return None
    root = parent.value
    if not isinstance(root, ast.Name) or root.id != "pytest":
        return None
    return target.attr


def _has_gh_issue_nearby(source_lines: list[str], lineno: int) -> bool:
    """Verifica se ha 'GH #NNN' ou '#NNN' no line do decorador ou nos 2 acima.

    `lineno` e 1-based (formato AST). Aceita o proprio reason="GH #123" se
    for um Call — tambem inspeccionamos a fonte.
    """
    # Janela: 2 lines antes + line do decorador + ate 3 lines abaixo (Call
    # multiline com reason="..." espalhado).
    start = max(0, lineno - 3)
    end = min(len(source_lines), lineno + 3)
    window = "\n".join(source_lines[start:end])
    return bool(GH_ISSUE_RX.search(window))


def scan_file(path: Path) -> list[tuple[Path, int, str]]:
    """Devolve lista de (path, lineno, decorator_name) sem GH issue link."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    source_lines = source.splitlines()
    violations: list[tuple[Path, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for deco in node.decorator_list:
            name = _is_pytest_mark_skip(deco)
            if name is None:
                continue
            if _has_gh_issue_nearby(source_lines, deco.lineno):
                continue
            violations.append((path, deco.lineno, name))
    return violations


def iter_python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=["tests"],
        help="Ficheiros ou directorios a varrer (default: tests/).",
    )
    parser.add_argument(
        "--baseline",
        type=int,
        default=0,
        help="Numero de violacoes toleradas (gate sobe se este numero crescer).",
    )
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths]
    files = iter_python_files(paths)
    all_violations: list[tuple[Path, int, str]] = []
    for f in files:
        all_violations.extend(scan_file(f))

    if all_violations:
        print(
            f"[lint-skip-tests] {len(all_violations)} violacao(oes) encontradas "
            f"(baseline tolerado: {args.baseline}):",
            file=sys.stderr,
        )
        for path, lineno, name in all_violations:
            print(
                f"  {path}:{lineno}: @pytest.mark.{name} sem 'GH #NNN' no "
                f"comment ao lado (mesmo line ou ate 2 acima).",
                file=sys.stderr,
            )

    if len(all_violations) > args.baseline:
        print(
            f"[lint-skip-tests] FAIL: {len(all_violations)} > baseline "
            f"{args.baseline}. Fix os tests ou adiciona '# GH #NNN' com "
            f"issue link ao decorador.",
            file=sys.stderr,
        )
        return 1

    if all_violations:
        print(
            f"[lint-skip-tests] OK (dentro do baseline {args.baseline}).",
            file=sys.stderr,
        )
    else:
        print("[lint-skip-tests] OK: zero @pytest.mark.skip/.xfail sem GH issue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
