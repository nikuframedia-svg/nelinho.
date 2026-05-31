"""Q.105.A — construir o FAISS + BM25 index das MEDIDAS do contrato.

Lê o `MEASURE_REGISTRY` (15 entradas Q.105.A), embed o texto
`description + ' | ' + ', '.join(synonyms)` de cada medida via Ollama
(`nomic-embed-text`), e guarda:

    cube/data/measure_index.npz       — {measures, embeddings, hash}
    cube/data/measure_index.faiss     — IndexFlatIP (cosine via inner product)
    cube/data/measure_index_bm25.pkl  — BM25Okapi sobre tokens normalizados
                                        (mesma tokenização que materiais)

Idempotente: hash SHA-256 sobre (name + description + synonyms) de cada
medida. Se hash não mudou, skip.

Air-gapped (FAISS local, Ollama local).

Uso::

    $env:PYTHONPATH = "C:\\Users\\User\\nelinho"
    .\\.venv\\Scripts\\python.exe scripts/refresh_cube_measure_index.py
"""
from __future__ import annotations

import asyncio
import hashlib
import pickle
import sys
import time

import faiss  # type: ignore[import-untyped]
import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from src.copilot.cube.material_retrieval import (
    EMBED_MODEL_DEFAULT,
    normalize_tokens,
)
from src.copilot.cube.measure_contract import MEASURE_REGISTRY
from src.copilot.cube.measure_retrieval import (
    CUBE_DATA_DIR,
    MEASURE_INDEX_BM25_PATH,
    MEASURE_INDEX_FAISS_PATH,
    MEASURE_INDEX_NPZ_PATH,
)
from src.copilot.ollama_client import OllamaClient


def _measure_text(name: str) -> str:
    """Texto que vai ser embedded + indexado para BM25.

    Junta: nome + description + synonyms. O `name` (e.g.
    'consumo_material.consumo') garante que perguntas que mencionem
    explicitamente `comercial_facturacao` continuam a bater. A
    description + synonyms dão a cobertura semântica natural.
    """
    spec = MEASURE_REGISTRY[name]
    parts = [name, spec.description, " ".join(spec.synonyms)]
    return " | ".join(p for p in parts if p).strip()


def _hash_measures(measures: list[str]) -> str:
    hasher = hashlib.sha256()
    for m in measures:
        hasher.update(m.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(_measure_text(m).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _read_existing_hash() -> str | None:
    if not MEASURE_INDEX_NPZ_PATH.exists():
        return None
    try:
        archive = np.load(MEASURE_INDEX_NPZ_PATH, allow_pickle=False)
        return str(archive["hash"])
    except Exception:
        return None


async def build_index(
    measures: list[str],
    embed_model: str = EMBED_MODEL_DEFAULT,
) -> tuple[np.ndarray, faiss.Index]:
    """Embed cada medida (texto = name + description + synonyms)."""
    ollama = OllamaClient()
    embeddings: list[list[float]] = []
    t0 = time.monotonic()
    for i, name in enumerate(measures):
        text = _measure_text(name)
        emb = await ollama.embeddings(text, model=embed_model)
        embeddings.append(emb)
        elapsed = time.monotonic() - t0
        print(
            f"  [{i + 1}/{len(measures)}] {name:<45} "
            f"({elapsed:.1f}s)",
            flush=True,
        )

    arr = np.asarray(embeddings, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr = arr / norms

    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    return arr, index


def build_bm25_index(measures: list[str]) -> BM25Okapi:
    """BM25 sobre tokens normalizados do texto (name+desc+synonyms)."""
    corpus_tokens = [normalize_tokens(_measure_text(m)) for m in measures]
    return BM25Okapi(corpus_tokens)


async def main() -> int:
    CUBE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    measures = sorted(MEASURE_REGISTRY.keys())
    print(f"A indexar {len(measures)} medidas do MEASURE_REGISTRY...")

    current_hash = _hash_measures(measures)
    existing_hash = _read_existing_hash()
    bm25_exists = MEASURE_INDEX_BM25_PATH.exists()
    if existing_hash == current_hash and bm25_exists:
        print(f"Índice já actualizado (hash={current_hash[:12]}). Skip.")
        return 0

    print(f"Hash actual={current_hash[:12]}, anterior={(existing_hash or 'none')[:12]}.")
    print(f"A embed via Ollama ({EMBED_MODEL_DEFAULT})...")
    arr, index = await build_index(measures)

    np.savez(
        MEASURE_INDEX_NPZ_PATH,
        measures=np.array(measures, dtype=object),
        embeddings=arr,
        hash=current_hash,
    )
    faiss.write_index(index, str(MEASURE_INDEX_FAISS_PATH))

    print("A construir BM25...")
    bm25 = build_bm25_index(measures)
    with MEASURE_INDEX_BM25_PATH.open("wb") as fh:
        pickle.dump(bm25, fh, protocol=pickle.HIGHEST_PROTOCOL)

    print(
        f"OK — índice escrito: {MEASURE_INDEX_NPZ_PATH.name} ({arr.shape[0]}×{arr.shape[1]}) "
        f"+ {MEASURE_INDEX_FAISS_PATH.name} + {MEASURE_INDEX_BM25_PATH.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
