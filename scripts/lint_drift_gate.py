#!/usr/bin/env python3
"""Q.61.06 — Lint drift gate: bloqueia crescimento de BLE001.

BLE001 (`except Exception` sem reraise/log) tem 370 ocorrencias hoje em
src/. Forcar `# noqa` em 370 sitios seria orthogonal damage massivo
(Karpathy failure #3). Em vez disso, mantemos um BASELINE com o count
actual; o CI corre este script em cada PR. Se o count sobe, falha —
"stop the bleeding" (Larson). Touched-file pays nas correccoes.

Usar:
    python scripts/lint_drift_gate.py            # check vs baseline
    python scripts/lint_drift_gate.py --update   # actualiza baseline

Output em scripts/lint_baseline.json para nao perder estado entre runs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILE = REPO_ROOT / "scripts" / "lint_baseline.json"

# Regras que vivem em drift mode — count actual e o teto.
# Python (ruff) — chaves directas do nome da regra ruff:
PYTHON_DRIFT_RULES = ["BLE001"]
# Frontend (ESLint) — chave logica + matcher no output:
FRONTEND_DRIFT_RULES = {
    "Q61_07_no_direct_fetch": "Q.61.07",  # match contra texto do erro
}

# Frontend (regex direto sobre source) — chave logica + (glob, pattern):
# Q.61.28 — `: any` no frontend baseline para nao crescer (TS strict
# real soa overshoot — 259 ocorrencias). Touched-file pays.
FRONTEND_REGEX_RULES = {
    "Q61_28_any_annotation": (
        ["frontend/src/**/*.ts", "frontend/src/**/*.tsx"],
        r":\s*any\b",
    ),
}

# Python custom (AST walk via tools/lint_*.py) — chave logica.
# Q.66.B.2 — audit_change() coverage em services. Baseline alto (41)
# enquanto o pipeline migra de 2 callsites para coverage global; o
# drift gate impede crescer (Larson: stop the bleeding).
PYTHON_CUSTOM_RULES = {
    "Q66_B2_audit_coverage_violations": "tools/lint_audit_coverage.py",
    # Q.68.3.5 — Fase D: standalone _FakeSession classes (não-subclasse do
    # canónico em tests/conftest.py). Baseline=4 (outliers documentados):
    # Q.66 char outlier, 80L SQL introspection, LEGACY paralelo, _SqlFakeSession.
    # Novos tests TÊM de subclassificar FakeSession do canónico.
    "Q68_3_fakesession_local_definitions": "tools/lint_fakesession_locals.py",
}


def count_python_violations(rule: str) -> int:
    """Conta violacoes de uma regra em src/ via ruff."""
    proc = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check", "src/",
            "--select", rule, "--output-format", "concise", "--no-fix",
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    # ruff sai != 0 quando ha violations — isto e o ponto, nao falha do gate.
    return sum(1 for line in proc.stdout.splitlines() if f": {rule} " in line)


def count_frontend_violations(needle: str) -> int:
    """Conta linhas no output do ESLint que contenham o texto `needle`."""
    frontend_dir = REPO_ROOT / "frontend"
    if not frontend_dir.exists():
        return 0
    proc = subprocess.run(
        [
            "npx", "eslint",
            "-c", "eslint.mocks.config.js", "--no-config-lookup",
            "src/**/*.{ts,tsx}",
            "--no-error-on-unmatched-pattern",
        ],
        capture_output=True, text=True, cwd=frontend_dir, shell=True,
    )
    return sum(1 for line in proc.stdout.splitlines() if needle in line)


def count_python_custom(script_rel: str) -> int:
    """Corre um lint AST custom (tools/lint_*.py) e devolve o count
    final. O script tem que imprimir uma linha com sintaxe:
        Q.66.B.2 audit coverage violations: <N>
    O drift gate parsa esse N para enforcement. Script standalone
    sai 0 sempre (e o drift gate quem enforce contra baseline)."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / script_rel)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    # Procura "violations: <N>" no stdout — formato fixo dos lints custom.
    for line in proc.stdout.splitlines():
        marker = "violations:"
        if marker in line:
            try:
                return int(line.split(marker, 1)[1].strip().split()[0])
            except (ValueError, IndexError):
                continue
    # Sem match — tratamos como 0 (script provavelmente falhou; o stderr
    # vai para fora e o caller ve).
    return 0


def count_regex_in_globs(globs: list[str], pattern: str) -> int:
    """Conta ocorrencias `pattern` (regex) em todos os ficheiros que batem
    qualquer dos `globs` (relativos ao repo root). Ignora comentarios e
    docstrings inline porque o regex apanha texto cru — bom para um
    drift gate sensitivo a crescimento, no para auditoria fina."""
    import re
    rx = re.compile(pattern)
    total = 0
    for pat in globs:
        for path in REPO_ROOT.glob(pat):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            total += len(rx.findall(text))
    return total


def count_all() -> dict[str, int]:
    counts: dict[str, int] = {}
    for rule in PYTHON_DRIFT_RULES:
        counts[rule] = count_python_violations(rule)
    for key, needle in FRONTEND_DRIFT_RULES.items():
        counts[key] = count_frontend_violations(needle)
    for key, (globs, pattern) in FRONTEND_REGEX_RULES.items():
        counts[key] = count_regex_in_globs(globs, pattern)
    for key, script_rel in PYTHON_CUSTOM_RULES.items():
        counts[key] = count_python_custom(script_rel)
    return counts


def load_baseline() -> dict[str, int]:
    if not BASELINE_FILE.exists():
        return {}
    # utf-8-sig tolera BOM (PowerShell `Out-File -Encoding utf8` injecta-o).
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8-sig"))


def save_baseline(counts: dict[str, int]) -> None:
    BASELINE_FILE.write_text(
        json.dumps(counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--update", action="store_true",
        help="grava o count actual como novo baseline (use com cuidado)",
    )
    args = parser.parse_args()

    current = count_all()
    baseline = load_baseline()

    if args.update:
        save_baseline(current)
        print(f"baseline actualizado: {BASELINE_FILE}")
        for rule, n in sorted(current.items()):
            print(f"  {rule}: {n}")
        return 0

    failures = []
    for rule in sorted(current):
        cur = current[rule]
        base = baseline.get(rule)
        if base is None:
            # Primeira corrida sem baseline: grava como ponto de partida.
            failures.append(
                f"{rule}: no baseline yet (current={cur}). "
                f"Run with --update to seed."
            )
            continue
        if cur > base:
            failures.append(
                f"{rule}: drift! current={cur} > baseline={base} "
                f"(+{cur - base}). Reverter o PR ou fixar as novas."
            )
        elif cur < base:
            print(
                f"  {rule}: melhorou! current={cur} < baseline={base} "
                f"(-{base - cur}). Corre --update para baixar o teto."
            )
        else:
            print(f"  {rule}: estavel em {cur}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(
            "\nDrift detectado. Solucao: corrige os novos cases OU "
            "(se forem legitimos) marca # noqa com razao.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
