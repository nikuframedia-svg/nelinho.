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
DRIFT_RULES = ["BLE001"]


def count_violations(rule: str) -> int:
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

    current = {rule: count_violations(rule) for rule in DRIFT_RULES}
    baseline = load_baseline()

    if args.update:
        save_baseline(current)
        print(f"baseline actualizado: {BASELINE_FILE}")
        for rule, n in sorted(current.items()):
            print(f"  {rule}: {n}")
        return 0

    failures = []
    for rule in DRIFT_RULES:
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
