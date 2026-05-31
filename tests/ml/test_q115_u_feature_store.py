"""
Q.115.U — testes FeatureStore unificado
=========================================

≥4 testes:
1. register_extractor + get_features round-trip
2. Cache hit (mesma query 2x → 1 DB call)
3. list_features devolve ≥4 (extractors migrados)
4. Features unknown → erro claro
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock
from uuid import UUID


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _make_fake_db():
    db = MagicMock()
    db.execute = AsyncMock()
    return db


# ------------------------------------------------------------------
# Testes
# ------------------------------------------------------------------

class TestFeatureStore:
    def setup_method(self):
        """Limpa cache antes de cada teste."""
        from src.ml.features.store import FeatureStore
        FeatureStore.clear_cache()

    def test_list_features_retorna_minimo_4(self):
        """Deve ter pelo menos 4 features registadas (os 4 extractors migrados)."""
        from src.ml.features.store import FeatureStore
        features = FeatureStore.list_features()
        assert len(features) >= 4, (
            f"Esperado >=4 features, got {len(features)}: {[f.name for f in features]}"
        )

    @pytest.mark.asyncio
    async def test_feature_desconhecida_lanca_keyerror(self):
        """Feature desconhecida deve lançar KeyError com mensagem clara."""
        from src.ml.features.store import FeatureStore
        store = FeatureStore(db=_make_fake_db(), tenant_id=TENANT)

        with pytest.raises(KeyError, match="desconhec"):
            await store.get_features("phase", ["fase_1"], ["feature_que_nao_existe_xyz"])

    @pytest.mark.asyncio
    async def test_register_extractor_round_trip(self):
        """Registar extractor custom + get_features devolve DataFrame correcto."""
        from src.ml.features.store import FeatureStore

        call_count = {"n": 0}

        def my_extractor(entity_ids, db, tenant_id):
            call_count["n"] += 1
            return pd.DataFrame({
                "entity_id": entity_ids,
                "my_custom_feat_q115u": [42.0] * len(entity_ids),
            })

        FeatureStore.register_extractor(
            "my_custom_feat_q115u", "operation", my_extractor, "feature de teste"
        )
        FeatureStore.clear_cache()

        store = FeatureStore(db=_make_fake_db(), tenant_id=TENANT)
        df = await store.get_features("operation", ["OF-001", "OF-002"], ["my_custom_feat_q115u"])

        assert "my_custom_feat_q115u" in df.columns
        assert list(df["my_custom_feat_q115u"]) == [42.0, 42.0]
        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_cache_hit_evita_segundo_db_call(self):
        """Segunda chamada idêntica usa cache — extractor chamado apenas 1x."""
        from src.ml.features.store import FeatureStore

        call_count = {"n": 0}

        def counting_extractor(entity_ids, db, tenant_id):
            call_count["n"] += 1
            return pd.DataFrame({
                "entity_id": entity_ids,
                "cached_feat_q115u": [1.0] * len(entity_ids),
            })

        FeatureStore.register_extractor(
            "cached_feat_q115u", "worker", counting_extractor, "feature com cache"
        )
        FeatureStore.clear_cache()

        store = FeatureStore(db=_make_fake_db(), tenant_id=TENANT)
        await store.get_features("worker", ["W-1"], ["cached_feat_q115u"])
        await store.get_features("worker", ["W-1"], ["cached_feat_q115u"])

        assert call_count["n"] == 1, (
            f"Extractor chamado {call_count['n']}x — esperado 1x (cache hit)"
        )

    @pytest.mark.asyncio
    async def test_feature_tipo_errado_lanca_keyerror(self):
        """Pedir feature 'phase' para entity_type='worker' → KeyError."""
        from src.ml.features.store import FeatureStore
        store = FeatureStore(db=_make_fake_db(), tenant_id=TENANT)

        # historical_error_rate é entity_type=phase, não worker
        with pytest.raises(KeyError):
            await store.get_features("worker", ["W-1"], ["historical_error_rate"])
