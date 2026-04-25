"""Per-module deep audit. Used by Q.7 Fase 3 to enumerate every
import, route, and surface of one module."""
import importlib
import glob
import os
import sys
import logging

# Ensure repo root is on sys.path before any src.* import
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

logging.disable(logging.CRITICAL)

target = sys.argv[1] if len(sys.argv) > 1 else "plan"
root = f"src/{target}"
files = [f for f in sorted(glob.glob(f"{root}/**/*.py", recursive=True))
         if "__pycache__" not in f]

print(f"=== {target}: {len(files)} files ===\n")

# Imports
errors: list[tuple[str, str]] = []
for f in files:
    rel = f.replace(os.sep, "/").replace(".py", "").replace("/", ".")
    if rel.endswith(".__init__"):
        rel = rel[: -len(".__init__")]
    try:
        importlib.import_module(rel)
    except Exception as e:
        errors.append((f, f"{type(e).__name__}: {str(e)[:200]}"))
print(f"[imports] {len(files) - len(errors)}/{len(files)} OK")
for f, e in errors:
    print(f"  ERR  {f}\n       {e}")

# Routes from this module
print()
from src.main import app
mod_routes = []
for r in app.routes:
    if not hasattr(r, "path") or not hasattr(r, "methods"):
        continue
    if f"/{target}/" in r.path or r.path.startswith(f"/v1/{target}"):
        mod_routes.append((sorted(r.methods), r.path))
print(f"[routes] {len(mod_routes)} registered for /{target}")
for methods, path in mod_routes:
    print(f"  {methods}  {path}")

# Reverse imports — who else imports from this module?
print()
import re
ref_pat = re.compile(rf"from src\.{target}[\.\s]|import src\.{target}\b")
referrers: dict[str, int] = {}
for f in glob.glob("src/**/*.py", recursive=True):
    if f"/{target}/" in f.replace(os.sep, "/"):
        continue
    if "__pycache__" in f:
        continue
    try:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if ref_pat.search(line):
                    other_mod = f.replace(os.sep, "/").split("src/")[1].split("/")[0]
                    referrers[other_mod] = referrers.get(other_mod, 0) + 1
                    break
    except OSError:
        pass
print(f"[referrers] {len(referrers)} other modules import src.{target}.*:")
for m, n in sorted(referrers.items(), key=lambda kv: -kv[1]):
    print(f"  {m}  ({n} files)")

# Outgoing imports — what does this module pull from elsewhere?
print()
out_imports: dict[str, int] = {}
import_pat = re.compile(r"from src\.([a-z_][a-z0-9_]*)")
for f in files:
    try:
        with open(f, encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        for m in import_pat.finditer(content):
            other = m.group(1)
            if other != target:
                out_imports[other] = out_imports.get(other, 0) + 1
    except OSError:
        pass
print(f"[outgoing] src.{target}.* imports from {len(out_imports)} other src.* modules:")
for m, n in sorted(out_imports.items(), key=lambda kv: -kv[1]):
    print(f"  src.{m}  ({n} import lines)")

print()
print(f"=== Done. Failed imports: {len(errors)} ===")
sys.exit(1 if errors else 0)
