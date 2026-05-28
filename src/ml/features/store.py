"""
ProdPlan ONE — FeatureStore unificado (Q.115.U)
================================================

Features partilhadas entre os 6 modelos ML:
  Duration, QualityRisk, OTDRisk, Surrogate, SequenceMining, ThroughputForecast.

Abordagem: registo de extractors por nome + lookup lazy com cache 5 min.
NÃO substitui os extractors existentes — apenas wraps.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Literal, Optional
from uuid import UUID

import pandas as pd
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

EntityType = Literal["operation", "phase", "worker", "boat"]

# Extractor: callable assíncrono ou síncrono que recebe (entity_ids, db, tenant_id)
# e devolve pd.DataFrame com coluna "entity_id" + features solicitadas.
FeatureExtractorFn = Callable[..., Any]


class FeatureMeta(BaseModel):
    name: str
    entity_type: EntityType
    description: str = ""


# ------------------------------------------------------------------
# Registo global
# ------------------------------------------------------------------

_REGISTRY: dict[str, tuple[EntityType, FeatureExtractorFn, FeatureMeta]] = {}
_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}  # key → (ts, df)
_CACHE_TTL: float = 300.0  # 5 minutos


def _cache_key(entity_type: str, entity_ids: list[str], feature_names: list[str]) -> str:
    return f"{entity_type}|{','.join(sorted(entity_ids))}|{','.join(sorted(feature_names))}"


class FeatureStore:
    """
    Lookup de features por entidade. Cache in-process 5 min.

    Uso:
        store = FeatureStore(db)
        df = await store.get_features("phase", ["fase_1", "fase_2"], ["historical_error_rate"])
    """

    def __init__(self, db: AsyncSession, tenant_id: Optional[UUID] = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def get_features(
        self,
        entity_type: EntityType,
        entity_ids: list[str],
        feature_names: list[str],
    ) -> pd.DataFrame:
        """
        Devolve DataFrame com colunas [entity_id] + feature_names.
        Erro claro se feature_names contém nomes desconhecidos.
        """
        unknown = [n for n in feature_names if n not in _REGISTRY]
        if unknown:
            raise KeyError(
                f"Features desconhecidas no FeatureStore: {unknown}. "
                f"Disponíveis: {list(_REGISTRY.keys())}"
            )

        # Filtra apenas extractors do entity_type pedido
        relevant = [n for n in feature_names if _REGISTRY[n][0] == entity_type]
        if not relevant:
            raise KeyError(
                f"Nenhuma feature de tipo '{entity_type}' entre: {feature_names}"
            )

        cache_k = _cache_key(entity_type, entity_ids, relevant)
        now = time.monotonic()
        if cache_k in _CACHE:
            ts, cached_df = _CACHE[cache_k]
            if now - ts < _CACHE_TTL:
                return cached_df

        frames: list[pd.DataFrame] = []
        for feat_name in relevant:
            _, extractor_fn, _ = _REGISTRY[feat_name]
            try:
                if asyncio.iscoroutinefunction(extractor_fn):
                    df = await extractor_fn(entity_ids, self.db, self.tenant_id)
                else:
                    df = extractor_fn(entity_ids, self.db, self.tenant_id)

                if df is None or df.empty:
                    df = pd.DataFrame({"entity_id": entity_ids, feat_name: [None] * len(entity_ids)})
                elif feat_name not in df.columns:
                    df[feat_name] = None

                frames.append(df[["entity_id", feat_name]].copy())
            except Exception as exc:
                logger.warning("FeatureStore: extractor '%s' falhou: %s", feat_name, exc)
                frames.append(
                    pd.DataFrame({"entity_id": entity_ids, feat_name: [None] * len(entity_ids)})
                )

        # Merge todos os frames pelo entity_id
        if not frames:
            return pd.DataFrame({"entity_id": entity_ids})

        result = frames[0]
        for f in frames[1:]:
            result = result.merge(f, on="entity_id", how="outer")

        _CACHE[cache_k] = (now, result)
        return result

    @classmethod
    def register_extractor(
        cls,
        feature_name: str,
        entity_type: EntityType,
        extractor: FeatureExtractorFn,
        description: str = "",
    ) -> None:
        """Regista um extractor para um nome de feature."""
        meta = FeatureMeta(name=feature_name, entity_type=entity_type, description=description)
        _REGISTRY[feature_name] = (entity_type, extractor, meta)
        logger.debug("FeatureStore: registado '%s' (%s)", feature_name, entity_type)

    @classmethod
    def list_features(cls) -> list[FeatureMeta]:
        """Lista todas as features registadas."""
        return [meta for _, _, meta in _REGISTRY.values()]

    @classmethod
    def clear_cache(cls) -> None:
        """Limpa cache (útil em testes)."""
        _CACHE.clear()


# ------------------------------------------------------------------
# Wrap dos 4 extractors existentes (Q.115.U)
# ------------------------------------------------------------------

def _wrap_order_features(entity_ids: list[str], db: Any, tenant_id: Any) -> pd.DataFrame:
    """Wrap síncrono do OrderFeatures para o FeatureStore."""
    from src.ml.feature_engineering.extractors import OrderFeatures

    extractor = OrderFeatures(tenant_id=tenant_id or UUID(int=0))
    rows = []
    for oid in entity_ids:
        feats = extractor.extract({"of_id": oid, "modelo_id": "", "quantidade": None})
        feats["entity_id"] = oid
        rows.append(feats)
    return pd.DataFrame(rows)


def _wrap_phase_features(entity_ids: list[str], db: Any, tenant_id: Any) -> pd.DataFrame:
    """Wrap síncrono do PhaseFeatures para o FeatureStore."""
    from src.ml.feature_engineering.extractors import PhaseFeatures

    extractor = PhaseFeatures(tenant_id=tenant_id or UUID(int=0))
    rows = []
    for fid in entity_ids:
        feats = extractor.extract({"of_id": "", "fase_id": fid, "modelo_id": ""})
        feats["entity_id"] = fid
        rows.append(feats)
    return pd.DataFrame(rows)


def _wrap_worker_features(entity_ids: list[str], db: Any, tenant_id: Any) -> pd.DataFrame:
    """Wrap síncrono do WorkerFeatures para o FeatureStore."""
    from src.ml.feature_engineering.extractors import WorkerFeatures

    extractor = WorkerFeatures(tenant_id=tenant_id or UUID(int=0))
    rows = []
    for wid in entity_ids:
        feats = extractor.extract(wid)
        feats["entity_id"] = wid
        rows.append(feats)
    return pd.DataFrame(rows)


def _wrap_mold_features(entity_ids: list[str], db: Any, tenant_id: Any) -> pd.DataFrame:
    """Wrap síncrono do MoldFeatures para o FeatureStore."""
    from src.ml.feature_engineering.extractors import MoldFeatures

    extractor = MoldFeatures(tenant_id=tenant_id or UUID(int=0))
    rows = []
    for mid in entity_ids:
        feats = extractor.extract(mid)
        feats["entity_id"] = mid
        rows.append(feats)
    return pd.DataFrame(rows)


# Registo automático ao importar o módulo
FeatureStore.register_extractor(
    "of_id", "operation", _wrap_order_features, "ID da OF (OrderFeatures)"
)
FeatureStore.register_extractor(
    "historical_error_rate", "phase", _wrap_phase_features,
    "Taxa histórica de erro por fase (PhaseFeatures)"
)
FeatureStore.register_extractor(
    "n_fases_aptos", "worker", _wrap_worker_features,
    "Número de fases em que o operador está apto (WorkerFeatures)"
)
FeatureStore.register_extractor(
    "uses_total", "boat", _wrap_mold_features,
    "Total de usos do molde (MoldFeatures)"
)
