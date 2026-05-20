#!/usr/bin/env python3
"""Q.66.C.2 — bloqueia src/X + tests/X no mesmo commit (test-cheating defence).

Test-cheating pattern (Anthropic post-mortem, Stella Laurenzo): agente AI
ajusta `src/foo.py` E `tests/foo_test.py` no mesmo commit, deixando o
test a "passar" mesmo quando o behaviour real mudou. O test foi
co-evoluido para acomodar o bug — perdeu o seu papel de specification
independente.

Uso (pre-commit, recebe staged files):
    python tools/lint_src_tests_coupling.py <file1> <file2> ...

Exit 1 se:
    - ha pelo menos 1 ficheiro `src/<modulo>/...` E pelo menos 1 ficheiro
      `tests/<modulo>/...` no mesmo commit (match por top-level modulo).
    - E NAO existe flag env `ALLOW_TEST_COEVOLUTION=1`.

Excepcoes (nao conta como violation):
    - `tests/conftest.py` em qualquer nivel — fixtures partilhadas, nao
      testam behaviour especifico.
    - `__init__.py` (vazios, nao mudam behaviour).
    - Flag env `ALLOW_TEST_COEVOLUTION=1` para TDD legitimo
      (RED-GREEN-REFACTOR onde src+test sobem juntos no mesmo commit).

Nao temos acesso ao commit message no pre-commit hook standard
(pre-commit framework so passa staged files), logo a flag env e o
escape hatch deliberado.
"""

from __future__ import annotations

import os
import sys
from pathlib import PurePosixPath


def _normalize(path: str) -> str:
    """Normaliza path para forward slashes (cross-platform)."""
    return str(PurePosixPath(path.replace("\\", "/")))


def _is_excepted(path: str) -> bool:
    """Conftest.py e __init__.py nao contam para o check."""
    name = path.rsplit("/", 1)[-1]
    return name in {"conftest.py", "__init__.py"}


def _top_module(path: str, prefix: str) -> str | None:
    """Extrai o top-level module de `src/X/...` ou `tests/X/...`.

    `src/foo/bar.py` -> "foo". `src/foo.py` (top-level) -> "foo".
    `tests/foo/test_bar.py` -> "foo". `tests/test_foo.py` -> "foo"
    (strip prefixo `test_` para emparelhar com src).
    """
    if not path.startswith(prefix):
        return None
    rel = path[len(prefix):]
    parts = rel.split("/", 1)
    if not parts or not parts[0]:
        return None
    head = parts[0]
    if len(parts) == 1:
        # Ficheiro top-level: tira `.py` e prefixo `test_` (para tests/).
        if head.endswith(".py"):
            head = head[:-3]
        if prefix == "tests/" and head.startswith("test_"):
            head = head[len("test_"):]
    return head


def main(staged_files: list[str]) -> int:
    if os.environ.get("ALLOW_TEST_COEVOLUTION") == "1":
        return 0

    src_modules: dict[str, list[str]] = {}
    test_modules: dict[str, list[str]] = {}

    for raw in staged_files:
        if not raw.endswith(".py"):
            continue
        path = _normalize(raw)
        if _is_excepted(path):
            continue
        src_mod = _top_module(path, "src/")
        if src_mod is not None:
            src_modules.setdefault(src_mod, []).append(path)
            continue
        test_mod = _top_module(path, "tests/")
        if test_mod is not None:
            test_modules.setdefault(test_mod, []).append(path)

    if not src_modules or not test_modules:
        return 0  # so src/ ou so tests/ — OK.

    # Match por top-level module: src/governance/ e tests/governance/ batem.
    overlap = sorted(set(src_modules) & set(test_modules))
    if not overlap:
        return 0

    print(
        "[lint-src-tests-coupling] ERROR: src/ + tests/ tocados no mesmo "
        "commit — possivel test-cheating (agente AI co-evolui o test "
        "para acomodar bug no src).",
        file=sys.stderr,
    )
    for module in overlap:
        print(f"  modulo '{module}':", file=sys.stderr)
        for s in sorted(src_modules[module]):
            print(f"    src  {s}", file=sys.stderr)
        for t in sorted(test_modules[module]):
            print(f"    test {t}", file=sys.stderr)
    print(
        "\nSe isto e TDD legitimo (RED-GREEN-REFACTOR), exporta a flag:\n"
        "  $env:ALLOW_TEST_COEVOLUTION='1'; git commit ...\n"
        "(ou ALLOW_TEST_COEVOLUTION=1 git commit ... em bash)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
