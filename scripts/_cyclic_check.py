"""Sprint Q.7 Fase 3 — cyclic import detector for src.* modules.

Builds a directed graph of `from src.X` imports between top-level modules
under src/ and reports any cycles. False positives can happen with
TYPE_CHECKING imports — those are filtered out."""

import re
import sys
from collections import defaultdict
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
ROOT = _root / "src"

if not ROOT.is_dir():
    print(f"src/ not found at {ROOT}", file=sys.stderr)
    sys.exit(2)

# Top-level module names (immediate children of src/)
modules = [d.name for d in ROOT.iterdir() if d.is_dir() and (d / "__init__.py").exists()]

import_pat = re.compile(r"^\s*from\s+src\.([a-z_][a-z0-9_]*)", re.MULTILINE)
typecheck_pat = re.compile(r"if\s+TYPE_CHECKING\s*:", re.MULTILINE)

graph: dict[str, set[str]] = defaultdict(set)

for mod in modules:
    mod_dir = ROOT / mod
    for py in mod_dir.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Strip TYPE_CHECKING blocks — heuristic; we drop everything between
        # the marker and the next dedent (a blank line followed by non-indent).
        # Imperfect but good enough for cycle detection.
        stripped = re.sub(
            r"if\s+TYPE_CHECKING\s*:\s*\n((?:[ \t]+.*\n)*)",
            "",
            text,
        )
        for m in import_pat.finditer(stripped):
            target = m.group(1)
            if target != mod:  # skip self-imports
                graph[mod].add(target)


def find_cycles() -> list[list[str]]:
    visited: dict[str, int] = {}  # 0=unvisited, 1=on-stack, 2=done
    cycles: list[list[str]] = []
    stack: list[str] = []

    def dfs(node: str) -> None:
        visited[node] = 1
        stack.append(node)
        for nb in graph.get(node, []):
            state = visited.get(nb, 0)
            if state == 1:
                # Found cycle — extract from stack
                idx = stack.index(nb)
                cycles.append(stack[idx:] + [nb])
            elif state == 0:
                dfs(nb)
        stack.pop()
        visited[node] = 2

    for node in sorted(modules):
        if visited.get(node, 0) == 0:
            dfs(node)
    return cycles


cycles = find_cycles()
print(f"=== Module-level cyclic-import check ===\n")
print(f"Modules examined: {len(modules)}")
print(f"Edges (X -> Y means src.X imports from src.Y): {sum(len(v) for v in graph.values())}")
print()
if not cycles:
    print("[OK] No cyclic imports between top-level src.* modules.")
    sys.exit(0)
print(f"[X] {len(cycles)} cyclic chain(s) detected:")
for c in cycles:
    print("  " + " -> ".join(c))
sys.exit(1)
