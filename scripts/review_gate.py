#!/usr/bin/env python3
"""Gate de revisao automatizavel (Q.60.D).

Corre as seccoes do gate `nelinho-review` que NAO precisam de julgamento
humano. Exit 1 se alguma falha, 0 se tudo limpo.

Hoje cobre:
- Seccao 6 — vocabulario PT-PT (nada de PT-BR em codigo user-facing).

Nao cobre aqui (vivem noutros passos do CI, de proposito):
- Seccao 3 ZERO MOCKS  -> `npm run lint:mocks` (regra ESLint AST, Q.60.A).
- Seccao 7 typecheck   -> `npx tsc -b --noEmit` (job frontend).
- Seccao 2 suite verde -> `pytest tests/` (job test).
"""
import re
import sys
from pathlib import Path

# (regex, sugestao) — termos PT-BR a apanhar. Ver CLAUDE.md "always-true #2".
# `\b` no inicio evita falsos positivos como "prestacao" conter "estacao".
PT_BR_SLIPS = [
    (r"\busu[áa]rio", "utilizador"),
    (r"\bvoc[êe]\b", "tu"),
    (r"\bcaminh[ãõ]", "camião"),
    (r"\bregistro", "registo"),
    (r"\bgerenciar|\bgerenciamento", "gerir / gestão"),
    (r"\bestaç(?:ão|ões)", "fase"),
]

SEARCH_ROOTS = ["frontend/src", "src/copilot/prompts"]
EXTS = {".ts", ".tsx", ".py", ".md", ".txt"}

violations: list[tuple[Path, int, str, str, str]] = []
for root in SEARCH_ROOTS:
    base = Path(root)
    if not base.exists():
        continue
    for fpath in base.rglob("*"):
        if not fpath.is_file() or fpath.suffix not in EXTS:
            continue
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(lines, 1):
            for pattern, suggestion in PT_BR_SLIPS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(
                        (fpath, n, pattern, suggestion, line.strip()[:100])
                    )

if violations:
    print(f"GATE DE REVISAO — {len(violations)} desvio(s) PT-BR -> PT-PT:\n")
    for fpath, n, pattern, suggestion, snippet in violations:
        print(f"  {fpath}:{n}  /{pattern}/  -> usar '{suggestion}'")
        print(f"      {snippet}")
    print("\nPT-PT, nao PT-BR (CLAUDE.md always-true #2). Corrigir antes de merge.")
    sys.exit(1)

print("Gate de revisao: vocabulario PT-PT OK.")
sys.exit(0)
