"""Q.67.2.D — Verifica/garante presença do `Folha_IA_extra.xlsx`.

O workbook (~57 MB, 1.1M linhas, fonte original NELO) deixou de ser tracked
no git em Q.67.2.D para acelerar clones. Vive em ``data/external/`` (ver
``.gitignore``). Este script é o único ponto canónico para descobrir onde
colocar o ficheiro e para validar que a cópia local é a esperada.

Comportamento:

* Se ``data/external/Folha_IA_extra.xlsx`` existe → calcula SHA256 e compara
  com :data:`EXPECTED_SHA256`. Imprime ``OK`` (rc=0) ou ``MISMATCH`` (rc=2).
* Se ausente → imprime instruções claras (rc=1). Não há download automático
  porque não existe URL público — é dump de ERP on-prem.

Uso (sempre via ``.venv``):

    .venv\\Scripts\\python.exe scripts/fetch_folha_ia.py

Outros scripts/tests importam :func:`ensure_folha_ia` ou :data:`FOLHA_IA_PATH`
em vez de hard-codarem o caminho. Quando o sha known-good muda (novo dump da
NELO), atualizar :data:`EXPECTED_SHA256` neste ficheiro — single source of
truth.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLHA_IA_PATH = REPO_ROOT / "data" / "external" / "Folha_IA_extra.xlsx"

# SHA256 known-good (Q.67.2.D, dump NELO 2024-2025, 57 MB).
EXPECTED_SHA256 = "385963418468c45aac9cdd68bff3865bfd16d797f12f8de1eee3f22dfdea3836"

_INSTRUCTIONS = f"""Folha_IA_extra.xlsx não está em {FOLHA_IA_PATH}.

  Como obter:
    - Cópia local NELO: pedir ao Luis ou copiar do share interno.
    - Não há URL público; este ficheiro é dump on-prem do ERP da NELO.

  Onde pôr:
    {FOLHA_IA_PATH}

  SHA256 esperado:
    {EXPECTED_SHA256}

  Depois corre novamente:
    .venv\\Scripts\\python.exe scripts/fetch_folha_ia.py
"""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_folha_ia(*, raise_on_missing: bool = False) -> Path:
    """Garante que :data:`FOLHA_IA_PATH` existe e tem o SHA esperado.

    Retorna o caminho absoluto. Levanta :class:`FileNotFoundError` se
    ``raise_on_missing`` e o ficheiro não estiver presente. Levanta
    :class:`ValueError` se o sha não bater certo.
    """
    if not FOLHA_IA_PATH.exists():
        if raise_on_missing:
            raise FileNotFoundError(_INSTRUCTIONS)
        return FOLHA_IA_PATH
    digest = _sha256(FOLHA_IA_PATH)
    if digest != EXPECTED_SHA256:
        raise ValueError(
            f"Folha_IA_extra.xlsx SHA mismatch.\n"
            f"  esperado: {EXPECTED_SHA256}\n"
            f"  obtido:   {digest}\n"
            f"  caminho:  {FOLHA_IA_PATH}\n"
            "Confirma que a cópia local é o dump correcto da NELO."
        )
    return FOLHA_IA_PATH


def main(argv: list[str] | None = None) -> int:
    if not FOLHA_IA_PATH.exists():
        sys.stdout.write(_INSTRUCTIONS)
        return 1
    digest = _sha256(FOLHA_IA_PATH)
    if digest != EXPECTED_SHA256:
        sys.stdout.write(
            "MISMATCH Folha_IA_extra.xlsx\n"
            f"  esperado: {EXPECTED_SHA256}\n"
            f"  obtido:   {digest}\n"
            f"  caminho:  {FOLHA_IA_PATH}\n"
            "Confirma que a cópia local é o dump correcto da NELO.\n"
        )
        return 2
    sha_short = digest[:12]
    size_mb = FOLHA_IA_PATH.stat().st_size / (1024 * 1024)
    sys.stdout.write(
        f"OK Folha_IA_extra.xlsx ({size_mb:.1f} MB, sha256={sha_short}...)\n"
        f"   {FOLHA_IA_PATH}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
