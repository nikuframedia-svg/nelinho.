"""Q.68.3.5 — lint custom: standalone FakeSession class definitions.

Conta `class _FakeSession:` / `class FakeSession:` standalone em tests/
(NÃO subclasses do canónico). Drift gate baseline=4 — 4 outliers
documentados:
  1. tests/copilot/test_copilot_api_characterization_q66_d.py — Q.66 outlier
  2. tests/improve/test_adoption_signal_q13d.py — 80L SQL introspection inline
  3. tests/reports/conftest.py — LEGACY canónico paralelo com 67 dependentes
  4. tests/core/test_activity_recent_fallback_q54e.py — _SqlFakeSession inline

NOVO ficheiro NÃO pode adicionar standalone — tem de subclassificar
o canónico (FakeSession em tests/conftest.py). Q.68.3.2 estendeu o
canónico com get(), register_entity(), queue_batch(), flags
raise_on_*.

Saída em stdout: 1 linha por violação, exit 0 sempre (gate usa count).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# Excluir o canónico legítimo. tests/conftest.py contém a definição
# canónica (FakeSession + FakeRuleSession); essas não contam.
CANONICAL_FILE = TESTS_DIR / "conftest.py"

# Match `class FakeSession:` ou `class _FakeSession:` ou `class _SqlFakeSession:`
# etc. SEM parêntese de subclasse (i.e. NÃO `class _X(FakeSession):`).
# Captura também `class _FakeSession(object):` como standalone (não herda
# do canónico).
STANDALONE_RE = re.compile(
    r"^\s*class\s+(\w*FakeSession\w*)\s*(?:\((?!FakeSession|FakeRuleSession)|:)",
    re.MULTILINE,
)


def find_standalone_definitions() -> list[tuple[Path, int, str]]:
    """Devolve lista (path, line_no, class_name) de standalone defs."""
    violations: list[tuple[Path, int, str]] = []
    for py in TESTS_DIR.rglob("*.py"):
        if py == CANONICAL_FILE:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in STANDALONE_RE.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            class_name = match.group(1)
            violations.append((py.relative_to(REPO_ROOT), line_no, class_name))
    return violations


def main() -> int:
    violations = find_standalone_definitions()
    for path, line, name in violations:
        print(f"{path}:{line}: {name}")
    # Linha final no formato esperado pelo drift gate.
    print(f"Q.68.3.5 fakesession local definitions violations: {len(violations)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
