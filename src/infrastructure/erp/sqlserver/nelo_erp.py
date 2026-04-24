"""
ProdPlan ONE — Nelo ERP Adapter (SQL Server, read-only)
=========================================================

Wraps the Nelo factory ERP running on a separate LAN server. Every
method reads — no writes, no DDL, no stored-procs with side effects.
The rest of the system stays on the curated Excel ingest until the
adapter proves itself; shadow mode (§shadow_mode below) exists so we
can compare the live ERP's answers to the baked-in dataset before
switching production over.

Target SQL Server tables (per `PP1_NELO_Blueprint_v2.0.md` §14):

    OrdensFabrico                    27.911 rows
    FasesOrdemFabrico               529.450
    FuncionariosFaseOrdemFabrico    423.769
    OrdemFabricoErros                89.836
    Funcionarios                        301  (122 active in 2024)
    FuncionariosFasesAptos              902  (skill matrix)
    Fases                                71  (41 active)
    Moldes                              510  (397 in production)
    Modelos                             899
    FasesStandardModelos             15.445  (routing templates — has CoeficienteX)

The adapter exposes one fetch method per table we actually consume.
Queries are bounded (explicit TOP / WHERE) so a misconfigured client
can't DoS the ERP. Every method accepts a `limit` kwarg so a CLI caller
can tune for exploration without editing code.

Wiring:
    from src.shared.config import settings
    from src.infrastructure.erp.sqlserver import NeloERPAdapter

    if settings.sqlserver_enabled:
        adapter = NeloERPAdapter.from_settings(settings)
        healthy = await adapter.health_check()
        if healthy:
            standards = await adapter.fetch_standard_times(limit=1000)
            ...
        await adapter.close()
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


class NeloERPError(RuntimeError):
    """Raised for any adapter-side failure (driver missing, query blew up,
    transient network issue). Callers treat this as "ERP unavailable" and
    fall back to the curated dataset.
    """


class NeloERPAdapter:
    """Read-only view over the Nelo ERP SQL Server.

    Construct via `from_settings(...)` in production or pass an explicit
    `engine` in tests. The adapter keeps one `AsyncEngine` alive between
    calls (connection pooled); call `close()` on shutdown.
    """

    def __init__(self, engine: AsyncEngine, *, query_timeout_s: int = 30) -> None:
        self._engine = engine
        self._query_timeout_s = max(1, int(query_timeout_s))

    # ─── Construction ─────────────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: Any) -> "NeloERPAdapter":
        """Build the adapter from the app's `Settings` instance.

        Raises `NeloERPError` if the URL is missing — callers should
        check `settings.sqlserver_enabled` before calling this.
        """
        url = getattr(settings, "sqlserver_url", None)
        if not url:
            raise NeloERPError(
                "settings.sqlserver_url is not set — cannot build the "
                "Nelo ERP adapter. Populate /etc/prodplan/env with the "
                "mssql+aioodbc://... connection string."
            )
        try:
            engine = create_async_engine(
                url,
                pool_size=getattr(settings, "sqlserver_pool_size", 5),
                pool_pre_ping=True,
                pool_recycle=1800,  # reconnect every 30 min
                isolation_level="READ COMMITTED",
                echo=False,
            )
        except Exception as exc:  # pragma: no cover — driver wiring issue
            raise NeloERPError(f"failed to build async engine: {exc}") from exc

        return cls(
            engine,
            query_timeout_s=getattr(settings, "sqlserver_query_timeout_s", 30),
        )

    async def close(self) -> None:
        """Dispose of the underlying engine + its connection pool."""
        await self._engine.dispose()

    # ─── Diagnostics ─────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Return True when a trivial `SELECT 1` round-trips. Any
        exception bubbles up as False so monitoring can flip the
        ERP-unavailable flag without breaking scheduled runs.
        """
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 AS one"))
                value = result.scalar()
                return value == 1
        except Exception as exc:
            logger.warning("Nelo ERP health check failed: %s", exc)
            return False

    # ─── Fetch methods — one per table consumed ──────────────────────

    async def fetch_orders(
        self,
        *,
        since: Optional[date] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Recent production orders (`OrdensFabrico`).

        * `since` filters by `Of_DataCriacao >= since` — defaults to "all".
        * `limit` caps the result; pass a larger value for bulk refresh.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if since is not None:
            where = "WHERE Of_DataCriacao >= :since"
            params["since"] = since

        sql = f"""
            SELECT TOP (:limit)
                Of_Id              AS of_id,
                Of_Numero          AS numero,
                Of_ProdutoId       AS produto_id,
                Of_ModeloId        AS modelo_id,
                Of_Estado          AS estado,
                Of_DataCriacao     AS data_criacao,
                Of_DataEntregaPrevista AS data_entrega_prevista,
                Of_DataTransporte  AS data_transporte
            FROM OrdensFabrico
            {where}
            ORDER BY Of_DataCriacao DESC
        """
        return await self._fetch(sql, params)

    async def fetch_workers(
        self,
        *,
        active_only: bool = True,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Workers (`Funcionarios`). When `active_only=True`, filter to
        rows the ERP flagged as active — though historical analysis in
        2024 shows only ~122 of the 129 "active" records actually logged
        work, so callers may need to cross-check via `fetch_activity`.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if active_only:
            where = "WHERE Func_Activo = 1"

        sql = f"""
            SELECT TOP (:limit)
                Func_Id                AS func_id,
                Func_Nome              AS nome,
                Func_Activo            AS activo,
                Func_CustoHora         AS custo_hora,
                Func_DataAdmissao      AS data_admissao
            FROM Funcionarios
            {where}
            ORDER BY Func_Nome
        """
        return await self._fetch(sql, params)

    async def fetch_skill_matrix(
        self,
        *,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Approved (worker, phase) pairs from `FuncionariosFasesAptos`.
        The blueprint's 902-row dataset; populates `FactoryState.skill_matrix`.
        """
        sql = """
            SELECT TOP (:limit)
                FFA_FuncionarioId AS funcionario_id,
                FFA_FaseId        AS fase_id,
                FFA_Apto          AS apto
            FROM FuncionariosFasesAptos
            WHERE FFA_Apto = 1
            ORDER BY FFA_FaseId, FFA_FuncionarioId
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_standard_times(
        self,
        *,
        limit: int = 20000,
    ) -> List[Dict[str, Any]]:
        """`FasesStandardModelos` — routing templates + standard times
        per (product, phase).

        The `coeficiente_x` column is returned verbatim. Consumer is the
        profit module (`PhaseBonusPayout`) — it's money (€ bonus), NOT
        time (Sprint A CX confirmed with the Nelo CEO).
        """
        sql = """
            SELECT TOP (:limit)
                ProdutoFase_ProdutoId    AS produto_id,
                ProdutoFase_FaseId       AS fase_id,
                ProdutoFase_Sequencia    AS sequencia,
                ProdutoFase_Coeficiente  AS coeficiente,
                ProdutoFase_CoeficienteX AS coeficiente_x
            FROM FasesStandardModelos
            ORDER BY ProdutoFase_ProdutoId, ProdutoFase_Sequencia
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_molds(
        self,
        *,
        in_production_only: bool = True,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """`Moldes` catalog. The real ERP has no maintenance columns —
        H2 (maintenance threshold) is still an unconfirmed hypothesis.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if in_production_only:
            where = "WHERE Molde_Estado = 'Em Producao'"

        sql = f"""
            SELECT TOP (:limit)
                Molde_Id              AS molde_id,
                Molde_Nome            AS nome,
                Molde_Estado          AS estado,
                Molde_ModeloId        AS modelo_id,
                Molde_NumeroPocosId   AS numero_pocos,
                Molde_TamanhoId       AS tamanho_id
            FROM Moldes
            {where}
            ORDER BY Molde_Nome
        """
        return await self._fetch(sql, params)

    async def fetch_phases_catalog(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        """`Fases` — the 71 phases catalog (41 active in 2024)."""
        sql = """
            SELECT TOP (:limit)
                Fase_Id        AS fase_id,
                Fase_Nome      AS nome,
                Fase_Activo    AS activo,
                Fase_Sequencia AS sequencia
            FROM Fases
            ORDER BY Fase_Sequencia, Fase_Nome
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_errors(
        self,
        *,
        since: Optional[date] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """`OrdemFabricoErros` — quality incidents with the "causer" chef
        and the detecting phase. 89 836 rows in the historical dataset;
        callers SHOULD pass `since` to avoid full-table scans.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if since is not None:
            where = "WHERE Erro_DataRegisto >= :since"
            params["since"] = since

        sql = f"""
            SELECT TOP (:limit)
                Erro_Id              AS erro_id,
                Erro_OfId            AS of_id,
                Erro_FaseOfCulpada   AS fase_culpada_id,
                Erro_FaseOfAvaliacao AS fase_avaliacao_id,
                Erro_Descricao       AS descricao,
                OFCH_GRAVIDADE       AS gravidade,
                Erro_DataRegisto     AS data_registo,
                Erro_ChefeId         AS chefe_id
            FROM OrdemFabricoErros
            {where}
            ORDER BY Erro_DataRegisto DESC
        """
        return await self._fetch(sql, params)

    # ─── Internals ───────────────────────────────────────────────────

    async def _fetch(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run a read-only query and hydrate each row to a plain dict."""
        try:
            async with self._engine.connect() as conn:
                stmt = text(sql).execution_options(
                    timeout=self._query_timeout_s,
                )
                result = await conn.execute(stmt, params or {})
                rows = result.mappings().all()
                return [dict(row) for row in rows]
        except NeloERPError:
            raise
        except Exception as exc:
            logger.error("Nelo ERP query failed: %s", exc)
            raise NeloERPError(f"query failed: {exc}") from exc


# ─── Shadow-mode helper ─────────────────────────────────────────────


async def compare_shadow(
    live: List[Dict[str, Any]],
    curated: List[Dict[str, Any]],
    *,
    key: str,
) -> Dict[str, Any]:
    """Lightweight reconciliation helper — returns the keys present in
    one dataset but not the other plus the count on each side.

    Used during the shadow-mode rollout to answer "is the live ERP
    saying the same thing the curated Excel said?". Not exhaustive (no
    column-by-column diff) — just enough to raise an alarm if the two
    diverge in shape.
    """
    live_keys = {row.get(key) for row in live if key in row}
    curated_keys = {row.get(key) for row in curated if key in row}
    return {
        "live_count": len(live),
        "curated_count": len(curated),
        "only_in_live": sorted(live_keys - curated_keys, key=str),
        "only_in_curated": sorted(curated_keys - live_keys, key=str),
        "match_count": len(live_keys & curated_keys),
        "compared_at": datetime.utcnow().isoformat(),
    }
