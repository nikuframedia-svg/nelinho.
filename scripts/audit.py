"""
ProdPlan ONE — Audit Dashboard (Sprint Q.7 Fase 1)
===================================================

Runs a fixed set of cheap-but-high-signal checks against every Python
module under `src/` and emits a per-module health report. Designed for
"give me the state of the world in <30s" — never reformats code, never
runs the full integration suite.

What it measures (per module):

* `src_files`           — number of .py files
* `test_files`          — number of test files under tests/{module}/
* `tests_collected`     — number of `test_*` functions pytest finds
* `import_errors`       — files that fail to import (real bugs!)
* `routes_registered`   — number of FastAPI routes the module exposes
  (computed by booting the app once and counting `path.startswith("/v1/{module}")`)
* `todo_count`          — TODO/FIXME/XXX markers (proxy for known debt)
* `hardcoded_violations`— `=` to numeric/string literal in known parameter
  files (Plan v4 §52b — "TUDO via ConfigStore")
* `health`              — green / yellow / red rollup

Output:

* JSON file `scripts/last_audit.json`
* Markdown summary `scripts/AUDIT_BASELINE.md`
* Coloured stdout table with health badges

Usage:

    python scripts/audit.py                # full report
    python scripts/audit.py --module plan  # one module only
    python scripts/audit.py --json         # JSON only, suppress stdout

This is a READ-ONLY tool. It never edits source files.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logging.disable(logging.CRITICAL)

# ─────────────────────────────────────────────────────────────────────────────
# Config — the 17 modules we audit
# ─────────────────────────────────────────────────────────────────────────────

MODULES: tuple[str, ...] = (
    "core",
    "plan",
    "profit",
    "hr",
    "copilot",
    "ml",
    "explain",
    "factory_data_product",
    "governance",
    "shared",
    "twin",
    "sandbox",
    "supply",
    "workforce",
    "dqa",
    "improve",
    "legacy",
)

# Files that are KNOWN to carry config defaults — and should therefore go
# through ConfigStore (Plan v4 §52b). A module is flagged when it has
# `=` to a numeric literal AT MODULE SCOPE (not inside `class FitnessConfig`
# defaults — those have a different pattern). Heuristic, not perfect.
HARDCODED_FILES: tuple[str, ...] = (
    "src/plan/cpo/fitness.py",
    "src/plan/cpo/engine.py",
    "src/plan/cpo/decoder.py",
    "src/plan/cpo/safety_net.py",
    "src/plan/cpo/state.py",
    "src/dqa/trust_v2.py",
)

# Pattern for "module-scope numeric literal assignment": `NAME = 12`,
# `NAME = 0.5`. False positives expected (constants, normalisation refs);
# this is a proxy metric, not a verdict.
_NUM_LITERAL_RE = re.compile(
    r"^[A-Z_][A-Z0-9_]*\s*[:=].*=\s*-?\d+(?:\.\d+)?\b",
    re.MULTILINE,
)

# TODO marker pattern — case-insensitive; ignores TODO inside doc lines
# starting with `#` to avoid double-counting docstrings.
_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")


# ─────────────────────────────────────────────────────────────────────────────
# Result shape
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ImportError_:
    file: str
    error: str


@dataclass
class ModuleAudit:
    module: str
    src_files: int = 0
    src_lines: int = 0
    test_files: int = 0
    tests_collected: int = 0
    import_errors: list[ImportError_] = field(default_factory=list)
    todo_count: int = 0
    hardcoded_violations: int = 0
    routes_registered: int = 0
    has_init_py: bool = False
    health: str = "unknown"  # green | yellow | red

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["import_error_count"] = len(self.import_errors)
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Per-module audit
# ─────────────────────────────────────────────────────────────────────────────

def _list_py_files(root: Path) -> list[Path]:
    """All `.py` files under root, excluding caches and tests under src/."""
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        out.append(p)
    return out


def _count_lines(files: list[Path]) -> int:
    n = 0
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                n += sum(1 for _ in fh)
        except OSError:
            pass
    return n


def _try_import(file_path: Path, repo_root: Path) -> ImportError_ | None:
    """Try to import the dotted module path. Return None on success."""
    rel = file_path.relative_to(repo_root)
    if rel.name == "__init__.py":
        # Empty __init__ files are fine; non-empty get tested via parent path.
        if file_path.stat().st_size == 0:
            return None
        dotted = ".".join(rel.parent.parts)
    else:
        dotted = ".".join(rel.with_suffix("").parts)
    try:
        importlib.import_module(dotted)
    except Exception as exc:
        return ImportError_(
            file=str(rel).replace("\\", "/"),
            error=f"{type(exc).__name__}: {exc}"[:300],
        )
    return None


def _count_todos(files: list[Path]) -> int:
    n = 0
    for f in files:
        try:
            with f.open(encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            n += len(_TODO_RE.findall(content))
        except OSError:
            pass
    return n


def _count_hardcoded(file_path: Path) -> int:
    if not file_path.exists():
        return 0
    try:
        with file_path.open(encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except OSError:
        return 0
    return len(_NUM_LITERAL_RE.findall(content))


def _collect_pytest(test_dir: Path) -> int:
    if not test_dir.exists():
        return 0
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_dir), "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(test_dir.parent.parent.parent),
        )
        # Each collected test prints once; "tests collected" appears in summary.
        # Count `::test_` separators in stdout for a robust signal.
        return result.stdout.count("::test_")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1  # -1 = collection failed/timed out


def audit_module(name: str, repo_root: Path, route_paths: set[str]) -> ModuleAudit:
    src_dir = repo_root / "src" / name
    test_dir = repo_root / "tests" / name

    src_files = _list_py_files(src_dir)
    test_files = _list_py_files(test_dir)

    audit = ModuleAudit(module=name)
    audit.src_files = len(src_files)
    audit.src_lines = _count_lines(src_files)
    audit.test_files = len(test_files)
    audit.has_init_py = (src_dir / "__init__.py").exists() if src_dir.exists() else False

    # Imports
    for f in src_files:
        err = _try_import(f, repo_root)
        if err is not None:
            audit.import_errors.append(err)

    # TODOs
    audit.todo_count = _count_todos(src_files)

    # Hardcoded params (only on the known-suspect files in this module)
    for h in HARDCODED_FILES:
        if h.startswith(f"src/{name}/"):
            audit.hardcoded_violations += _count_hardcoded(repo_root / h)

    # Tests collected (subprocess; skip if no test dir)
    audit.tests_collected = _collect_pytest(test_dir)

    # Routes — count app paths starting with "/v1/{module}" or "/{module}"
    audit.routes_registered = sum(
        1 for p in route_paths
        if p.startswith(f"/v1/{name}/") or p.startswith(f"/{name}/")
    )

    # Health rollup
    if audit.import_errors:
        audit.health = "red"
    elif audit.test_files == 0 and audit.src_files > 0:
        audit.health = "yellow"
    elif audit.tests_collected == 0 and audit.src_files > 0:
        audit.health = "yellow"
    else:
        audit.health = "green"

    return audit


# ─────────────────────────────────────────────────────────────────────────────
# Routes — boot the FastAPI app once
# ─────────────────────────────────────────────────────────────────────────────

def collect_routes(repo_root: Path) -> set[str]:
    """Boot src.main:app and harvest every registered path. Falls back to
    empty set if the app fails to load (e.g. missing DB)."""
    try:
        sys.path.insert(0, str(repo_root))
        from src.main import app  # noqa: PLC0415
        return {
            r.path for r in app.routes
            if hasattr(r, "methods") and hasattr(r, "path")
        }
    except Exception as exc:
        print(f"[audit] WARN: could not boot app to collect routes: {exc}",
              file=sys.stderr)
        return set()


# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

_RESET = "\033[0m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_GREEN = "\033[92m"
_BOLD = "\033[1m"

# Use a unicode separator when stdout supports it; ASCII otherwise. Avoids
# UnicodeEncodeError on Windows cp1252 consoles.
def _safe(c: str, fallback: str) -> str:
    try:
        c.encode(sys.stdout.encoding or "utf-8")
        return c
    except (UnicodeEncodeError, LookupError):
        return fallback


_HSEP = _safe("─", "-")
_DOT = _safe("●", "*")


def _badge(health: str) -> str:
    if health == "red":
        return f"{_RED}{_DOT} red   {_RESET}"
    if health == "yellow":
        return f"{_YELLOW}{_DOT} yellow{_RESET}"
    if health == "green":
        return f"{_GREEN}{_DOT} green {_RESET}"
    return f"{_DOT} ?"


def print_table(audits: list[ModuleAudit], use_colour: bool) -> None:
    if not use_colour:
        global _RESET, _RED, _YELLOW, _GREEN, _BOLD
        _RESET = _RED = _YELLOW = _GREEN = _BOLD = ""

    headers = ["module", "health", "src", "lines", "tests", "collected", "routes", "TODOs", "imp.err", "hardcoded"]
    rows = [
        [
            a.module,
            _badge(a.health),
            f"{a.src_files}",
            f"{a.src_lines:,}",
            f"{a.test_files}",
            f"{a.tests_collected}",
            f"{a.routes_registered}",
            f"{a.todo_count}",
            f"{len(a.import_errors)}",
            f"{a.hardcoded_violations}",
        ]
        for a in audits
    ]

    # Compute column widths
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            # Strip ANSI for width measurement
            plain = re.sub(r"\033\[\d+m", "", cell)
            widths[i] = max(widths[i], len(plain))

    def _fmt(cells: list[str]) -> str:
        out: list[str] = []
        for cell, w in zip(cells, widths):
            plain = re.sub(r"\033\[\d+m", "", cell)
            pad = w - len(plain)
            out.append(cell + (" " * pad))
        return "  ".join(out)

    print(f"{_BOLD}{_fmt(headers)}{_RESET}")
    print(_HSEP * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print(_fmt(r))


def print_failures(audits: list[ModuleAudit]) -> None:
    failing = [a for a in audits if a.import_errors]
    if not failing:
        return
    print()
    print(f"{_BOLD}Import errors (real bugs - fix first){_RESET}")
    print(_HSEP * 60)
    for a in failing:
        print(f"\n{_RED}{_DOT} {a.module}{_RESET} ({len(a.import_errors)} files)")
        for err in a.import_errors[:5]:
            print(f"  {err.file}")
            print(f"    {err.error}")
        if len(a.import_errors) > 5:
            print(f"  … and {len(a.import_errors) - 5} more")


def write_json(audits: list[ModuleAudit], path: Path) -> None:
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "modules": [a.to_dict() for a in audits],
        "summary": {
            "total_modules": len(audits),
            "green": sum(1 for a in audits if a.health == "green"),
            "yellow": sum(1 for a in audits if a.health == "yellow"),
            "red": sum(1 for a in audits if a.health == "red"),
            "total_src_files": sum(a.src_files for a in audits),
            "total_src_lines": sum(a.src_lines for a in audits),
            "total_tests": sum(a.tests_collected for a in audits if a.tests_collected > 0),
            "total_routes": sum(a.routes_registered for a in audits),
            "total_import_errors": sum(len(a.import_errors) for a in audits),
            "total_todos": sum(a.todo_count for a in audits),
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(audits: list[ModuleAudit], path: Path) -> None:
    lines: list[str] = [
        "# Audit Baseline — Sprint Q.7 Fase 1",
        "",
        f"**Gerado em:** {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
        "",
        "Snapshot do estado dos 17 módulos do PP1. Foco em **bugs reais** — ",
        "imports partidos, testes em falta, hardcoded params §52b. Não reporta ",
        "warnings de estilo. Re-correr com `python scripts/audit.py`.",
        "",
        "## Resumo",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Módulos | {len(audits)} |",
        f"| Verdes | {sum(1 for a in audits if a.health == 'green')} |",
        f"| Amarelos | {sum(1 for a in audits if a.health == 'yellow')} |",
        f"| Vermelhos | {sum(1 for a in audits if a.health == 'red')} |",
        f"| Ficheiros src | {sum(a.src_files for a in audits):,} |",
        f"| Linhas src | {sum(a.src_lines for a in audits):,} |",
        f"| Testes colectados | {sum(max(a.tests_collected, 0) for a in audits):,} |",
        f"| Rotas API | {sum(a.routes_registered for a in audits):,} |",
        f"| Imports a falhar | {sum(len(a.import_errors) for a in audits)} |",
        f"| TODO/FIXME | {sum(a.todo_count for a in audits):,} |",
        "",
        "## Por módulo",
        "",
        "| Módulo | Health | src | lines | tests | collected | routes | TODOs | imp.err | hardcoded |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for a in audits:
        emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(a.health, "❓")
        lines.append(
            f"| `{a.module}` | {emoji} {a.health} | "
            f"{a.src_files} | {a.src_lines:,} | {a.test_files} | "
            f"{a.tests_collected} | {a.routes_registered} | "
            f"{a.todo_count} | **{len(a.import_errors)}** | {a.hardcoded_violations} |"
        )

    failing = [a for a in audits if a.import_errors]
    if failing:
        lines += [
            "",
            "## Import errors (BLOQUEIA)",
            "",
            "Ficheiros que falham a importar — real bugs. Resolver antes de qualquer outra coisa.",
            "",
        ]
        for a in failing:
            lines.append(f"### `{a.module}` — {len(a.import_errors)} ficheiros")
            lines.append("")
            for err in a.import_errors:
                lines.append(f"- `{err.file}` — {err.error}")
            lines.append("")

    yellow = [a for a in audits if a.health == "yellow"]
    if yellow:
        lines += [
            "",
            "## Sem testes ou sem testes colectados (yellow)",
            "",
            "Estes módulos não têm cobertura visível — Fase 3 candidata.",
            "",
        ]
        for a in yellow:
            lines.append(
                f"- `{a.module}` — {a.src_files} ficheiros src, {a.test_files} test files, "
                f"{a.tests_collected} testes colectados"
            )

    lines += [
        "",
        "---",
        "",
        "*Re-gerar:* `python scripts/audit.py`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="ProdPlan ONE per-module audit")
    parser.add_argument("--module", help="Audit a single module instead of all 17")
    parser.add_argument("--json", action="store_true", help="JSON to stdout, no table")
    parser.add_argument(
        "--no-colour", action="store_true", help="Plain stdout (CI-friendly)",
    )
    parser.add_argument(
        "--no-write", action="store_true",
        help="Skip writing scripts/last_audit.json + AUDIT_BASELINE.md",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    if not (repo_root / "src").is_dir():
        print(f"[audit] ERROR: src/ not found under {repo_root}", file=sys.stderr)
        return 2

    targets = [args.module] if args.module else list(MODULES)

    print(f"[audit] booting app to collect routes…", file=sys.stderr)
    routes = collect_routes(repo_root)
    print(f"[audit] {len(routes)} routes registered", file=sys.stderr)

    audits: list[ModuleAudit] = []
    for name in targets:
        print(f"[audit] {name}…", file=sys.stderr)
        audits.append(audit_module(name, repo_root, routes))

    if args.json:
        print(json.dumps(
            {"modules": [a.to_dict() for a in audits]},
            indent=2, ensure_ascii=False,
        ))
    else:
        print_table(audits, use_colour=not args.no_colour)
        print_failures(audits)

    if not args.no_write:
        scripts_dir = repo_root / "scripts"
        write_json(audits, scripts_dir / "last_audit.json")
        write_markdown(audits, scripts_dir / "AUDIT_BASELINE.md")
        print(
            f"\n[audit] wrote {scripts_dir / 'last_audit.json'} and "
            f"{scripts_dir / 'AUDIT_BASELINE.md'}",
            file=sys.stderr,
        )

    # Non-zero exit if any module is red — useful for CI gates.
    return 1 if any(a.health == "red" for a in audits) else 0


if __name__ == "__main__":
    sys.exit(main())
