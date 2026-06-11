"""Q.173.AJ — runner idempotente de todos os scripts setup_marts_*.py.

Descobre automaticamente todos os scripts `scripts/setup_marts_*.py` (excepto
a si próprio) e corre cada um pela ordem de nome. Idempotente: cada script usa
CREATE OR REPLACE VIEW, por isso é seguro correr N vezes.

Uso:
    python scripts/setup_marts_all.py            # corre tudo
    python scripts/setup_marts_all.py --dry-run  # só lista, não corre

Deploy:
    Correr após `alembic upgrade head` e antes de iniciar o Cube container.
    Também é chamado por `scripts/bootstrap_dev_full.py` (best-effort).

Invariante #8: cada script falha limpo se a source está vazia — a view fica
criada mas com 0 linhas. Não fabricamos dados.
"""
from __future__ import annotations

import argparse
import importlib.util
import asyncio
import sys
import time
from pathlib import Path

# scripts/ dir e raiz do repo no sys.path
SCRIPTS_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPTS_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _discover_scripts() -> list[Path]:
    """Descobre setup_marts_*.py excluindo este ficheiro, ordenados por nome."""
    me = Path(__file__).resolve()
    scripts = sorted(
        p for p in SCRIPTS_DIR.glob("setup_marts_*.py")
        if p.resolve() != me
    )
    return scripts


async def _run_script(script_path: Path) -> tuple[str, bool, str]:
    """Corre o `setup()` de um script. Devolve (nome, ok, mensagem)."""
    name = script_path.stem
    spec = importlib.util.spec_from_file_location(name, script_path)
    if spec is None or spec.loader is None:
        return name, False, "importlib falhou a carregar o spec"
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    except Exception as exc:
        return name, False, f"import error: {exc}"

    setup_fn = getattr(mod, "setup", None)
    if setup_fn is None:
        return name, False, "sem funcao setup()"

    try:
        rc = await setup_fn()
        ok = rc == 0 if rc is not None else True
        return name, ok, "" if ok else f"setup() devolveu {rc}"
    except Exception as exc:
        return name, False, str(exc)


async def main(dry_run: bool = False) -> int:
    scripts = _discover_scripts()
    print(f"setup_marts_all: {len(scripts)} scripts encontrados.")

    if dry_run:
        for s in scripts:
            print(f"  [dry-run] {s.name}")
        return 0

    results: list[tuple[str, bool, str]] = []
    t0 = time.monotonic()
    for script in scripts:
        print(f"  -> {script.name} ...", flush=True)
        t1 = time.monotonic()
        name, ok, msg = await _run_script(script)
        elapsed = time.monotonic() - t1
        status = "OK" if ok else "FAIL"
        suffix = f"  ({msg})" if msg else ""
        print(f"     [{status}] {elapsed:.1f}s{suffix}")
        results.append((name, ok, msg))

    total = time.monotonic() - t0
    ok_count = sum(1 for _, ok, _ in results if ok)
    fail_count = len(results) - ok_count
    print(f"\nsetup_marts_all: {ok_count}/{len(results)} OK, {fail_count} FAIL ({total:.1f}s total)")

    if fail_count:
        print("\nFalharam:")
        for name, ok, msg in results:
            if not ok:
                print(f"  {name}: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corre todos os setup_marts_*.py")
    parser.add_argument("--dry-run", action="store_true", help="Lista scripts sem correr")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
