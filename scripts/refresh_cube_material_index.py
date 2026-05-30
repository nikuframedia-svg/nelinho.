"""Q.93.C / Q.93.E.B — construir o FAISS + BM25 index dos materiais distintos.

Lê `SELECT DISTINCT material FROM marts.v_consumo_material_dia` (com filtro
Q.93.E.A: activo + não-descontinuado + activos últimos 365d), embed cada
nome via Ollama (`nomic-embed-text`), e guarda:

    cube/data/material_index.npz       — {materials, embeddings, hash}
    cube/data/material_index.faiss     — IndexFlatIP (cosine via inner product)
    cube/data/material_index_bm25.pkl  — Q.93.E.B: BM25Okapi sobre tokens
                                          normalizados (lowercase + sem
                                          acentos + colapso s↔z)

Idempotente: se o hash SHA-256 da lista de materiais não mudou desde a última
corrida, skip — não re-embed. Útil para CI/dev. O BM25 é cheap (segundos)
mas é parte do mesmo build atómico.

Uso:
    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts/refresh_cube_material_index.py
"""
from __future__ import annotations

import asyncio
import hashlib
import pickle
import sys
import time

import asyncpg
import faiss  # type: ignore[import-untyped]
import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from src.copilot.cube.material_retrieval import (
    CUBE_DATA_DIR,
    EMBED_MODEL_DEFAULT,
    INDEX_BM25_PATH,
    INDEX_FAISS_PATH,
    INDEX_NPZ_PATH,
    normalize_tokens,
)
from src.copilot.ollama_client import OllamaClient
from src.shared.config import settings


def _hash_materials(materials: list[str]) -> str:
    hasher = hashlib.sha256()
    for m in materials:
        hasher.update(m.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _read_existing_hash() -> str | None:
    if not INDEX_NPZ_PATH.exists():
        return None
    try:
        archive = np.load(INDEX_NPZ_PATH, allow_pickle=False)
        return str(archive["hash"])
    except Exception:
        return None


async def fetch_distinct_materials() -> list[str]:
    """Lista distinta de materiais da view (ordem estável por nome).

    Q.93.E Etapa A: apertar o catálogo indexado a `activo + não-descontinuado +
    com pelo menos um movimento nos últimos 365 dias`. Sai de 1279 → ~928
    materiais. Reduz ruído no top-k do FAISS sem perder candidatos legítimos
    (gelcoat, acetona, cola, divinycell, espuma, tecido, manta, fibra,
    Catalizador P200/Norox, Catalizador Curox M302).
    """
    pg_dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(pg_dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT v.material
            FROM marts.v_consumo_material_dia v
            JOIN factory_raw.produto p ON p."P_NOME" = v.material
            WHERE v.material IS NOT NULL
              AND p."P_ACTIVO" = TRUE
              AND p."P_DESCONTINUADO" = FALSE
              AND v.data >= CURRENT_DATE - INTERVAL '365 days'
            ORDER BY v.material
            """
        )
    finally:
        await conn.close()
    return [r[0] for r in rows]


async def build_index(
    materials: list[str],
    embed_model: str = EMBED_MODEL_DEFAULT,
) -> tuple[np.ndarray, faiss.Index]:
    """Embed cada material e construir IndexFlatIP (L2-normalizado)."""
    ollama = OllamaClient()
    embeddings: list[list[float]] = []
    t0 = time.monotonic()
    for i, mat in enumerate(materials):
        emb = await ollama.embeddings(mat, model=embed_model)
        embeddings.append(emb)
        if (i + 1) % 50 == 0 or (i + 1) == len(materials):
            elapsed = time.monotonic() - t0
            rate = (i + 1) / max(elapsed, 0.01)
            eta = (len(materials) - (i + 1)) / max(rate, 0.01)
            print(
                f"  [{i + 1}/{len(materials)}] embed @ {rate:.1f}/s, "
                f"ETA {eta:.0f}s",
                flush=True,
            )

    arr = np.asarray(embeddings, dtype=np.float32)
    # L2-normalize (cosine via inner product no IndexFlatIP).
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr = arr / norms

    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    return arr, index


def build_bm25_index(materials: list[str]) -> BM25Okapi:
    """Q.93.E.B — construir BM25 sobre tokens normalizados dos nomes.

    Tokenização simétrica entre indexação e query (`normalize_tokens`):
    lowercase + sem acentos + colapso s↔z. Sem stop-words: nomes de
    material são frases curtas (3-8 tokens); remover qualquer token
    perde sinal.
    """
    corpus_tokens = [normalize_tokens(m) for m in materials]
    return BM25Okapi(corpus_tokens)


async def main() -> int:
    CUBE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("A ler materiais distintos de marts.v_consumo_material_dia...")
    materials = await fetch_distinct_materials()
    print(f"  {len(materials)} materiais distintos.")

    current_hash = _hash_materials(materials)
    existing_hash = _read_existing_hash()
    bm25_exists = INDEX_BM25_PATH.exists()
    if existing_hash == current_hash and bm25_exists:
        print(f"Index já actualizado (hash={current_hash[:12]}). Skip.")
        return 0

    if existing_hash == current_hash and not bm25_exists:
        # Hash não mudou mas BM25 falta (primeiro Q.93.E.B build sobre
        # índice Q.93.E.A pré-existente). Reconstruir só o BM25.
        print(f"Hash inalterado ({current_hash[:12]}) mas BM25 ausente — só rebuild BM25.")
        bm25 = build_bm25_index(materials)
        with INDEX_BM25_PATH.open("wb") as fh:
            pickle.dump(bm25, fh, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"OK — BM25 escrito: {INDEX_BM25_PATH.name}")
        return 0

    print(f"Hash actual={current_hash[:12]}, anterior={(existing_hash or 'none')[:12]}.")
    print(f"A embed via Ollama ({EMBED_MODEL_DEFAULT})...")
    arr, index = await build_index(materials)

    np.savez(
        INDEX_NPZ_PATH,
        materials=np.array(materials, dtype=object),
        embeddings=arr,
        hash=current_hash,
    )
    faiss.write_index(index, str(INDEX_FAISS_PATH))

    print("A construir BM25 (tokens normalizados)...")
    bm25 = build_bm25_index(materials)
    with INDEX_BM25_PATH.open("wb") as fh:
        pickle.dump(bm25, fh, protocol=pickle.HIGHEST_PROTOCOL)

    print(
        f"OK — index escrito: {INDEX_NPZ_PATH.name} ({arr.shape[0]}×{arr.shape[1]}) "
        f"+ {INDEX_FAISS_PATH.name} + {INDEX_BM25_PATH.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
