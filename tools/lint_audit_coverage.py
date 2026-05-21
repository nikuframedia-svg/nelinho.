"""Q.66.B.2 - lint audit coverage.

Audit invariant 7 (CLAUDE.md): cada state mutation deve ter
`audit_change()` (ou equivalente) em +-5 linhas. Hoje so 2 callsites
em 115k LOC chamam `audit_change` — o resto e disciplina humana frágil.
Este lint troca a disciplina por enforcement: falha CI se um service
file faz INSERT/UPDATE/DELETE sem audit em +-5 linhas.

Estratégia (AST walk):
  * INSERT  → `<x>.add(<EntityCls>(...))`, qualquer atributo (self.db, session, db).
  * UPDATE  → `<x>.execute(update(<Table>)...)`.
  * DELETE  → `<x>.execute(delete(<Table>)...)`.
  * Audit OK → chamada a `audit_change`, `record_rule_firing` ou
    `audit_log` (Name ou Attribute) em [line-5 .. line+5].

Excepcoes (nao contam como violation):
  * Path comeca por `tests/`.
  * EntityClass em EXEMPT_CLASSES (o pipeline de auditoria propriamente
    dito — nao se audita o audit).
  * Comentario `# noqa: audit_coverage` na mesma linha ou na anterior.

Drift-gate semantics: imprime count actual; modo standalone exit 0.
O `scripts/lint_drift_gate.py` re-corre este lint e enforce o teto
contra `scripts/lint_baseline.json:Q66_B2_audit_coverage_violations`.

Uso:
    python tools/lint_audit_coverage.py                  # default src/
    python tools/lint_audit_coverage.py --verbose        # imprime cada violation
    python tools/lint_audit_coverage.py src/governance/  # path especifico
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Funcoes que satisfazem o invariant (qualquer uma destas em +-5 linhas).
AUDIT_FUNCTIONS = {"audit_change", "record_rule_firing", "audit_log"}

# Classes cujo INSERT NAO precisa de audit_change — sao o pipeline de
# auditoria/eventos em si. Auditar isto seria recursao infinita.
EXEMPT_CLASSES = {
    "AuditLog",
    "EventOutbox",
    "EventDLQ",
    "TenantRuleRevision",
    "RuleFiring",
    # Audit-trail revisions sao elas proprias forma de audit:
    "DecisionRevision",
    "ScheduleCommitRevision",
    "RuleRevision",
    "ApprovalRevision",
}

# Restringimos o lint a paths de services — modulos com mutacao de
# estado autoritativa. Excluimos api/, models/, schemas/, tools/, tests/.
SERVICE_PATH_PREFIXES = (
    "src/governance/",
    "src/plan/services/",
    "src/workforce/",
    "src/profit/services/",
    "src/quality/services/",
    "src/supply/services/",
    "src/copilot/",
)

# Subpaths a saltar mesmo dentro dos prefixes acima (LLM client wrappers,
# read-only diagnostics, etc).
SKIP_SUBSTRINGS = (
    "/tests/",
    "/__pycache__/",
)

WINDOW_LINES = 5


def _is_exempt_class_name(name: str) -> bool:
    """True se a classe instanciada e parte do pipeline de auditoria."""
    if name in EXEMPT_CLASSES:
        return True
    # Convencao: qualquer modelo cujo nome contenha "Audit" ou termine
    # em "Revision" e considerado audit-trail e nao precisa audit_change.
    if "Audit" in name or name.endswith("Revision"):
        return True
    return False


def _extract_call_name(node: ast.expr) -> str | None:
    """Devolve o nome curto de uma `Call.func`: `update` para
    `update(Table)`, `add` para `self.db.add`, `audit_change` para
    `audit_change(...)` ou `gov.audit_change(...)`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _first_constructed_class(call: ast.Call) -> str | None:
    """Para `<x>.add(EntityCls(...))` devolve "EntityCls". Se o argumento
    nao for `Call(Name)`, devolve None — caller decide se ignora."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Call):
        func = first.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    return None


def _build_name_to_class_map(tree: ast.AST) -> dict[str, str]:
    """Constroi {var_name: ClassName} a partir de assignments
    `var = ClassName(...)` em todo o ficheiro. Aproximacao "ultima
    atribuicao ganha" — suficiente para o caso comum
    `decision_run = DecisionRun(...); session.add(decision_run)`.
    Nao tenta resolver scopes per-funcao (over-engineering para o
    sinal que queremos)."""
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        # `x = Call(...)`  ou  `x: T = Call(...)`
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        cls_name: str | None = None
        if isinstance(value.func, ast.Name):
            cls_name = value.func.id
        elif isinstance(value.func, ast.Attribute):
            cls_name = value.func.attr
        if cls_name is None:
            continue
        # Heuristica: so consideramos classes (PascalCase). Filtra
        # builtins/funcoes (lowercase), str(), dict(), uuid4(), etc.
        if not cls_name[:1].isupper():
            continue
        for tgt in targets:
            if isinstance(tgt, ast.Name):
                mapping[tgt.id] = cls_name
    return mapping


def _has_audit_in_window(
    lines: set[int], start: int, end: int
) -> bool:
    """True se algum lineno em [start, end] esta em `lines` (linhas com
    audit_change/record_rule_firing/audit_log)."""
    return any(start <= ln <= end for ln in lines)


def _collect_audit_call_lines(tree: ast.AST) -> set[int]:
    """Linenos onde aparece `audit_change(...)` (ou equivalentes), seja
    `Name(audit_change)` ou `Attribute(.audit_change)`."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _extract_call_name(node.func)
        if name in AUDIT_FUNCTIONS:
            found.add(node.lineno)
            # Marca tambem +-1 linhas para tolerar formatting multilinha
            # (await audit_change(\n  ...\n)).
            found.add(node.lineno - 1)
            found.add(node.lineno + 1)
    return found


def _has_noqa_audit(source_lines: list[str], lineno: int) -> bool:
    """True se ha `# noqa: audit_coverage` na linha ou na anterior."""
    needle = "noqa: audit_coverage"
    # source_lines e 0-indexed; lineno e 1-indexed.
    idx = lineno - 1
    for cand in (idx, idx - 1):
        if 0 <= cand < len(source_lines):
            if needle in source_lines[cand]:
                return True
    return False


def _classify_call(
    call: ast.Call, name_to_class: dict[str, str]
) -> tuple[str, str] | None:
    """Devolve (action, entity_name) se este Call e uma state mutation
    detectavel, senao None.

    action ∈ {"INSERT", "UPDATE", "DELETE"}.
    entity_name e o nome da classe (INSERT) ou da Table (UPDATE/DELETE).
    """
    name = _extract_call_name(call.func)

    # INSERT: ".add(EntityCls(...))" ou ".add(var_que_foi_EntityCls(...))"
    if name == "add":
        cls_name = _first_constructed_class(call)
        if cls_name is None and call.args:
            # `.add(existing_var)` — tentar resolver via name map.
            first = call.args[0]
            if isinstance(first, ast.Name):
                cls_name = name_to_class.get(first.id)
        if cls_name is None:
            return None
        # Filtra builtins/funcoes (str, uuid4, list, dict…) — so PascalCase
        # ORM classes contam. Evita falsos positivos com `set.add(str(...))`
        # ou `sigs.add(_triplet_signature(...))`.
        if not cls_name[:1].isupper():
            return None
        if _is_exempt_class_name(cls_name):
            return None
        return ("INSERT", cls_name)

    # UPDATE/DELETE: ".execute(update(Table)...)" / "delete(Table)...".
    if name == "execute":
        if not call.args:
            return None
        first = call.args[0]
        # `update(Table).values(...).where(...)` — chain. O outermost
        # Call e o `.where(...)`; precisamos descer ate ao base
        # update()/delete() Call.
        cur: ast.AST = first
        depth = 0
        while isinstance(cur, ast.Call) and depth < 8:
            inner_name = _extract_call_name(cur.func)
            if inner_name in {"update", "delete"}:
                tbl = _first_constructed_class(cur) or "<unknown>"
                if _is_exempt_class_name(tbl):
                    return None
                return (inner_name.upper(), tbl)
            # Desce: se chain ".values()" -> func e Attribute, value e
            # outro Call (o update(...)). Esse value vive em func.value.
            if isinstance(cur.func, ast.Attribute):
                cur = cur.func.value
                depth += 1
                continue
            break

    return None


def find_violations_in_file(path: Path) -> list[tuple[int, str, str]]:
    """Devolve [(lineno, action, entity_name), ...] para cada violation
    no ficheiro."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    audit_lines = _collect_audit_call_lines(tree)
    name_to_class = _build_name_to_class_map(tree)
    source_lines = source.splitlines()
    violations: list[tuple[int, str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        cls = _classify_call(node, name_to_class)
        if cls is None:
            continue
        action, entity = cls
        lineno = node.lineno

        if _has_noqa_audit(source_lines, lineno):
            continue

        window_lo = lineno - WINDOW_LINES
        window_hi = lineno + WINDOW_LINES
        if _has_audit_in_window(audit_lines, window_lo, window_hi):
            continue

        violations.append((lineno, action, entity))

    return violations


def _iter_service_files(root: Path) -> list[Path]:
    """Devolve todos os .py em SERVICE_PATH_PREFIXES, exclui SKIP."""
    out: list[Path] = []
    for prefix in SERVICE_PATH_PREFIXES:
        base = root / prefix
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if any(skip in f"/{rel}" for skip in SKIP_SUBSTRINGS):
                continue
            out.append(path)
    return sorted(out)


def find_all_violations(
    root: Path, scope_paths: list[Path] | None = None
) -> list[tuple[Path, int, str, str]]:
    """Walk dos service files e devolve lista plana de violations."""
    if scope_paths:
        files: list[Path] = []
        for p in scope_paths:
            if p.is_file() and p.suffix == ".py":
                files.append(p)
            elif p.is_dir():
                files.extend(sorted(p.rglob("*.py")))
    else:
        files = _iter_service_files(root)

    all_v: list[tuple[Path, int, str, str]] = []
    for path in files:
        for lineno, action, entity in find_violations_in_file(path):
            all_v.append((path, lineno, action, entity))
    return all_v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "paths", nargs="*", default=[],
        help="paths (defaults to SERVICE_PATH_PREFIXES no repo)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="imprime cada violation, nao so o count",
    )
    parser.add_argument(
        "--top", type=int, default=5,
        help="top-N ficheiros com mais violations (default 5)",
    )
    args = parser.parse_args(argv)

    scope = [Path(p).resolve() for p in args.paths] if args.paths else None
    violations = find_all_violations(REPO_ROOT, scope)

    if args.verbose:
        for path, lineno, action, entity in violations:
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"{rel}:{lineno}: {action} {entity} sem audit_change em +-{WINDOW_LINES} linhas")

    # Top-N por ficheiro.
    per_file: dict[Path, int] = {}
    for path, _, _, _ in violations:
        per_file[path] = per_file.get(path, 0) + 1
    top = sorted(per_file.items(), key=lambda kv: kv[1], reverse=True)[: args.top]

    print(f"\nQ.66.B.2 audit coverage violations: {len(violations)}")
    if top:
        print(f"Top {len(top)} ficheiros:")
        for path, n in top:
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"  {n:>4}  {rel}")

    # Standalone exit 0 sempre — o drift gate (lint_drift_gate.py) e
    # quem enforce contra o baseline.
    return 0


if __name__ == "__main__":
    sys.exit(main())
