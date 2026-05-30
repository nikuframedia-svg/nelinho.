"""MaterialIndex — top-k retrieval por embeddings sobre os ~1300 materiais.

A dimensão `material` da view tem ~1300 valores distintos — demasiados para
o LLM ver no prompt. Solução: indexar os nomes via embeddings (Ollama
`nomic-embed-text`) numa estrutura FAISS local (IndexFlatIP, vectores
L2-normalizados → cosine via inner product).

Q.93.E Etapa B: índice BM25 paralelo ao FAISS — vocabulary mismatch
(utilizador escreve "catalisador" mas catálogo tem "Catalizador";
"gelcoat" puro mas catálogo "GelCoat Crystic 65 PA"). O FAISS semântico
sozinho falha em palavras técnicas; BM25 sobre tokens normalizados
(lowercase + sem acentos + colapso s↔z) bate o nome exacto. Os top-k de
cada motor fundem-se via Reciprocal Rank Fusion (RRF, k=60).

O index é construído por `scripts/refresh_cube_material_index.py`. Aqui
fica só a leitura + busca lazy singleton.

Air-gapped: o `faiss-cpu` + `rank_bm25` correm 100% local. Os embeddings
vão a Ollama local. Sem cloud, sem internet em tempo de query.
"""
from __future__ import annotations

import logging
import pickle
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import faiss  # type: ignore[import-untyped]
import numpy as np
import yaml

from src.copilot.llm.base import LLMClient


log = logging.getLogger(__name__)

# Caminhos canónicos do index (relativo à raiz do repo).
CUBE_DATA_DIR = Path(__file__).resolve().parents[3] / "cube" / "data"
INDEX_NPZ_PATH = CUBE_DATA_DIR / "material_index.npz"
INDEX_FAISS_PATH = CUBE_DATA_DIR / "material_index.faiss"
INDEX_BM25_PATH = CUBE_DATA_DIR / "material_index_bm25.pkl"
ALIASES_PATH = CUBE_DATA_DIR / "material_aliases.yml"

# Modelo de embeddings — alinhado com .env (COPILOT_EMBEDDINGS_MODEL).
EMBED_MODEL_DEFAULT = "nomic-embed-text"

# Q.93.E — Reciprocal Rank Fusion: k=60 é o valor canónico da literatura
# (Cormack et al., 2009) — não precisa de afinação por dataset.
RRF_K = 60

# Q.93.E Etapa B — stop-words PT-PT que poluem o BM25 sobre nomes de
# material. Sem elas, queries como "O que foi consumido em divinycell?"
# pontuam alto materiais que apenas têm "em" no nome ("Cola em Spray",
# "Banco em foam"). Lista curta, conservadora — palavras de função puras.
PT_STOPWORDS = frozenset(
    {
        "a", "o", "as", "os", "um", "uma", "uns", "umas",
        "de", "do", "da", "dos", "das",
        "e", "em", "no", "na", "nos", "nas",
        "para", "por", "com", "sem", "sob", "sobre",
        "que", "se", "ou", "mas", "ao", "aos",
        "foi", "foram", "ser", "sido",
        "ja", "ainda", "muito", "pouco", "todo", "toda",
    }
)


def normalize_tokens(text: str) -> list[str]:
    """Tokenização PT-PT para BM25.

    Regras:
    - lowercase
    - remover acentos via Unicode NFD + drop combining marks ("peróxido"→"peroxido")
    - colapsar z↔s **só em tokens puramente alfabéticos com len>2**
      ("catalizador"→"catalisador", "fertilizante"→"fertilisante"). Resolve
      o vocabulary mismatch ortográfico que o FAISS semântico não capta —
      sem este passo a query "catalisador" jamais bateria os 4 materiais
      "Catalizador*" do catálogo.
    - **Q.93.E.A.2 reforço**: tokens com dígitos (EN 720, KP-9, PN80, M302)
      ou de len<=2 NÃO sofrem colapso. Códigos são sagrados; "EN 720" tem
      de continuar distinguível de "EN 721" após normalização.
    - split em [a-z0-9]+
    - drop stop-words PT-PT comuns (em/de/para/que/...) — sem elas o BM25
      sobre nomes curtos confunde-se com palavras de função.

    Aplicado TANTO ao corpus (indexação) como à query — simetria total.
    """
    nfd = unicodedata.normalize("NFD", text.lower())
    no_accent = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    tokens = re.findall(r"[a-z0-9]+", no_accent)
    out: list[str] = []
    for t in tokens:
        if t in PT_STOPWORDS:
            continue
        # Tokens com dígitos (EN720, KP9, M302, 720, pn80) ou curtos (en, m5)
        # ficam INTACTOS. Não aplicar colapso s↔z aqui — números são sagrados
        # e variantes de código como "EN 720" vs "EN 721" têm de divergir.
        if len(t) <= 2 or any(ch.isdigit() for ch in t):
            out.append(t)
            continue
        # Token alfa puro e len>2: aplica colapso s↔z entre vogais.
        # Cobre catali(z|s)ador, utili(z|s)ar, autori(z|s)ar.
        # NÃO toca em 'zona', 'azul' (z inicial ou pós-consoante).
        collapsed = re.sub(r"(?<=[aeiou])z(?=[aeiou])", "s", t)
        out.append(collapsed)
    return out


def rrf_fuse(
    list_a: list[tuple[str, float]],
    list_b: list[tuple[str, float]],
    k_const: int = RRF_K,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion de duas listas ranqueadas (nome, score).

    `score` no output é o RRF score (soma de 1/(k+rank)); não comparável
    aos scores originais de cada motor. Apenas a ordem importa.

    Materiais que aparecem em AMBAS as listas ficam melhor classificados —
    é exactamente o que se quer: confluência entre semântico (FAISS) e
    lexical (BM25) indica candidato robusto.
    """
    scores: dict[str, float] = {}
    for rank, (name, _) in enumerate(list_a, 1):
        scores[name] = scores.get(name, 0.0) + 1.0 / (k_const + rank)
    for rank, (name, _) in enumerate(list_b, 1):
        scores[name] = scores.get(name, 0.0) + 1.0 / (k_const + rank)
    return sorted(scores.items(), key=lambda x: -x[1])


# ────────────────────────────── Q.93.E.A.4 — aliases ──────────────────────────────


@dataclass(slots=True)
class AmbiguousHit:
    """Termo coloquial detectado na query que mapeia a múltiplos materiais
    em unidades diferentes (categoria larga). LLM deve ABSTAIN com sugestões."""

    termo: str
    sugestoes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AliasApplied:
    """Substituição inequívoca que ocorreu. O caller mostra ao LLM para
    o LLM usar o termo canónico no filter, não a forma coloquial."""

    de: str  # "catalisador peróxido"
    para: str  # "catalizador"


@dataclass(slots=True)
class AliasResult:
    """Resultado de `apply_aliases()`. `query` é o texto após substituições
    inequívocas; `aliases_applied` lista as substituições; `ambiguous_hits`
    é a lista de termos largos detectados."""

    query: str
    aliases_applied: list[AliasApplied] = field(default_factory=list)
    ambiguous_hits: list[AmbiguousHit] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load_aliases_yaml() -> dict:
    """Carrega `cube/data/material_aliases.yml`. Cache process-wide."""
    if not ALIASES_PATH.exists():
        return {}
    with ALIASES_PATH.open("rb") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def apply_aliases(text: str) -> AliasResult:
    """Aplica aliases inequívocos à query + detecta termos ambíguos.

    - Aliases inequívocos: substituídos longest-first (case-insensitive).
      Ex: "catalisador peróxido" → "catalizador". Aplicado à query que vai
      ao BM25 + FAISS embed.
    - Ambíguos: detectados mas NÃO traduzidos. O caller (interpret.py)
      injecta as sugestões no prompt para o LLM abdicar.

    A query original do utilizador é preservada para a narração; o
    `AliasResult.query` é só usado para retrieval.
    """
    aliases_cfg = _load_aliases_yaml()
    aliases = aliases_cfg.get("aliases") or {}
    ambiguous = aliases_cfg.get("ambiguous") or []

    # Substituições longest-first para preferir o mais específico
    # ("catalisador peróxido" antes de "catalisador" só por si).
    out = text.lower()
    aliases_applied: list[AliasApplied] = []
    for src in sorted(aliases.keys(), key=len, reverse=True):
        dst = aliases[src]
        if not isinstance(dst, str):
            continue
        if src.lower() in out:
            aliases_applied.append(AliasApplied(de=src, para=dst))
            # Case-insensitive replace (re.escape evita meta-chars no src).
            out = re.sub(re.escape(src.lower()), dst.lower(), out)

    # Detecção de termos ambíguos (não muta a query).
    hits: list[AmbiguousHit] = []
    text_low = text.lower()
    for entry in ambiguous:
        if isinstance(entry, dict):
            termo = entry.get("termo")
            sugestoes = entry.get("sugestoes") or []
        elif isinstance(entry, str):
            termo = entry
            sugestoes = []
        else:
            continue
        if not isinstance(termo, str) or not termo:
            continue
        if termo.lower() in text_low:
            hits.append(
                AmbiguousHit(
                    termo=termo,
                    sugestoes=[str(s) for s in sugestoes if isinstance(s, str)],
                )
            )

    return AliasResult(
        query=out,
        aliases_applied=aliases_applied,
        ambiguous_hits=hits,
    )


class MaterialIndexNotBuilt(RuntimeError):
    """Levantada quando o index não existe ainda — utilizador tem de correr o script."""


class MaterialIndex:
    """FAISS index dos materiais.

    A instância é singleton process-wide (carregamento do .npz/.faiss feito
    uma vez), mas NÃO guarda referência ao OllamaClient — o cliente é
    passado em cada chamada a `top_k()`. Razão: o httpx pool do OllamaClient
    está atado ao event loop; em testes pytest-asyncio, o loop é recriado
    por teste e um cliente cached fica morto.
    """

    _instance: "MaterialIndex | None" = None
    _lock = threading.Lock()

    def __init__(self, embed_model: str = EMBED_MODEL_DEFAULT) -> None:
        self.embed_model = embed_model
        self._materials: np.ndarray | None = None  # array[str]
        self._index: faiss.Index | None = None
        self._hash: str | None = None
        self._loaded: bool = False
        # Q.93.E Etapa B — BM25 paralelo. None se o pickle não existe ainda
        # (gracefully degrade para top_k() puro FAISS).
        self._bm25: object | None = None  # BM25Okapi

    @classmethod
    def get(cls, embed_model: str = EMBED_MODEL_DEFAULT) -> "MaterialIndex":
        """Singleton process-wide do index (FAISS + materiais), sem OllamaClient."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = MaterialIndex(embed_model=embed_model)
            return cls._instance

    def load(self) -> None:
        """Carrega .npz + .faiss do disco. Idempotente."""
        if self._loaded:
            return
        if not INDEX_NPZ_PATH.exists() or not INDEX_FAISS_PATH.exists():
            raise MaterialIndexNotBuilt(
                f"Index FAISS não encontrado em {INDEX_NPZ_PATH} / "
                f"{INDEX_FAISS_PATH}. Corre primeiro:\n"
                f"    python scripts/refresh_cube_material_index.py"
            )
        # allow_pickle=True porque os nomes de material são guardados como
        # numpy object array (strings de tamanho variável). O ficheiro é
        # produzido pelo nosso script `refresh_cube_material_index.py` no
        # mesmo host — não é input externo, sem risco de unpickling hostil.
        archive = np.load(INDEX_NPZ_PATH, allow_pickle=True)
        self._materials = archive["materials"]
        self._hash = str(archive["hash"])
        self._index = faiss.read_index(str(INDEX_FAISS_PATH))
        # Q.93.E Etapa B — BM25 paralelo. Optional: se não existe, fica None
        # e top_k_hybrid() degrada gracefully para FAISS-only.
        if INDEX_BM25_PATH.exists():
            with INDEX_BM25_PATH.open("rb") as fh:
                self._bm25 = pickle.load(fh)
        self._loaded = True
        log.info(
            "MaterialIndex loaded: %d materials, hash=%s, bm25=%s",
            len(self._materials),
            self._hash[:12],
            "yes" if self._bm25 is not None else "no",
        )

    @property
    def hash(self) -> str:
        if not self._loaded:
            self.load()
        assert self._hash is not None
        return self._hash

    @property
    def n_materials(self) -> int:
        if not self._loaded:
            self.load()
        assert self._materials is not None
        return len(self._materials)

    async def top_k(
        self,
        query_text: str,
        ollama: LLMClient,
        k: int = 10,
    ) -> list[tuple[str, float]]:
        """Embed a pergunta e devolve os top-k materiais mais próximos (cosine).

        `ollama` é passado a cada chamada (não cached) para evitar httpx-pool
        atado a event loop morto entre testes pytest-asyncio.

        Devolve `[(nome_material, score_cosine), ...]` ordenado desc.
        """
        if not self._loaded:
            self.load()
        assert self._materials is not None
        assert self._index is not None

        emb = await ollama.embeddings(query_text, model=self.embed_model)
        vec = np.asarray(emb, dtype=np.float32).reshape(1, -1)
        # L2-normalize (necessário para cosine via inner product).
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        vec = vec / norm

        scores, indices = self._index.search(vec, k)
        out: list[tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:  # FAISS devolve -1 se pediu mais k do que items
                continue
            out.append((str(self._materials[int(idx)]), float(score)))
        return out

    def _bm25_top_k(self, query_text: str, k: int) -> list[tuple[str, float]]:
        """BM25 top-k sobre os nomes de material (tokens normalizados).

        Q.93.E Etapa B — complementa o FAISS semântico para vocabulary
        mismatch ortográfico (catalisador↔catalizador) e palavra-chave
        exacta (gelcoat, divinycell). Síncrono: BM25 é só dicionário em RAM.
        """
        assert self._materials is not None
        if self._bm25 is None:
            return []
        query_tokens = normalize_tokens(query_text)
        if not query_tokens:
            return []
        # rank_bm25.BM25Okapi.get_scores devolve np.ndarray paralelo aos docs.
        scores = self._bm25.get_scores(query_tokens)  # type: ignore[attr-defined]
        # Top-k por índice. Filtra score>0 (sem token em comum → score=0).
        order = np.argsort(scores)[::-1][:k]
        return [
            (str(self._materials[int(i)]), float(scores[int(i)]))
            for i in order
            if scores[int(i)] > 0.0
        ]

    async def top_k_hybrid(
        self,
        query_text: str,
        ollama: LLMClient,
        k: int = 10,
        k_each: int = 20,
    ) -> list[tuple[str, float]]:
        """Q.93.E Etapa B — top-k híbrido FAISS + BM25 via RRF.

        - **Q.93.E.A.4**: aplica aliases inequívocos à query ANTES do
          retrieval (e.g. "catalisador peróxido" → "catalizador"). Materiais
          do catálogo continuam com os nomes originais — só a query é
          normalizada para procurar.
        - FAISS top-k_each: captura semântica.
        - BM25 top-k_each: captura palavra exacta + ortografia normalizada
          (gelcoat, acetona, divinycell, catalisador→catalizador).
        - RRF fusion (k=60): premia candidatos que aparecem em ambos.
        - Devolve top-k final ordenado por RRF score desc.

        Se BM25 não está carregado (índice antigo Q.93.D), degrada para
        FAISS-only (`top_k()`).

        Mantém o contrato `[(material, score), ...]` esperado por
        [interpret.py:146]. Termos ambíguos detectados ficam EXPOSTOS via
        `apply_aliases()` separado — o caller `interpret.py` chama-o para
        ler `ambiguous_hits` e adicionar ao prompt.
        """
        # Q.93.E.A.4 — query expandida (substituições inequívocas só).
        # Ambiguous hits são lidos pelo caller (interpret.py) via
        # apply_aliases() directo.
        alias_result = apply_aliases(query_text)
        effective_query = alias_result.query

        # Q.R restauração — o índice FAISS embute os NOMES CRUS (capitalizados)
        # do catálogo e `nomic-embed-text` é case-sensitive. `apply_aliases`
        # devolve a query em lowercase (correcto para o ramo BM25, simétrico
        # com os tokens normalizados do corpus) — mas passar esse lowercase ao
        # FAISS quebra a simetria de caso e despromove o match exacto (medido:
        # "Resina Lavesan EN 720" caía de rank 1 → rank 17). O FAISS recebe a
        # query com o caso original; o BM25 recebe a normalizada.
        if self._bm25 is None:
            # Graceful degrade — Q.93.D-style sem BM25.
            return await self.top_k(query_text, ollama=ollama, k=k)

        faiss_results = await self.top_k(query_text, ollama=ollama, k=k_each)
        bm25_results = self._bm25_top_k(effective_query, k=k_each)
        return rrf_fuse(faiss_results, bm25_results, k_const=RRF_K)[:k]
