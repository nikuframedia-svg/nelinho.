"""
ProdPlan ONE — Nelo ERP Adapter (SQL Server, read-only)
=========================================================

Wraps the Nelo factory ERP running on a separate LAN server. Every
method reads — no writes, no DDL, no stored-procs with side effects.

Q.20 decision: the adapter targets the **``vw_pp1_*`` views**, not the
raw ERP tables. The real ERP schema (``OF_FP``, ``PRODUTO``,
``ENTIDADE``, …) is messy and unstable; IT NELO applies
``agent_docs/views_pp1.sql`` once to create a stable, snake_case
contract that this adapter consumes. If a raw table is renamed, only
the view changes — the adapter stays put.

Views consumed (see ``agent_docs/views_pp1.sql`` for the DDL):

    vw_pp1_produto              products master
    vw_pp1_produto_fase         routing structure (product × phase × seq)
    vw_pp1_fases_producao       phase catalogue
    vw_pp1_entidade             workers / operators
    vw_pp1_entidade_fase        skill matrix (worker × phase)
    vw_pp1_produto_componente   BOM (parent × component)
    vw_pp1_moldes               mold catalogue (ERP side — ~91 rows)
    vw_pp1_of_fp                operation history (start/end timestamps)
    vw_pp1_offp_probs           quality incidents
    vw_pp1_of_checklist         checklist results

Queries are bounded (explicit ``TOP`` / ``WHERE``) so a misconfigured
client can't DoS the ERP. Every method accepts a ``limit`` kwarg.

Wiring::

    from src.shared.config import settings
    from src.infrastructure.erp.sqlserver import NeloERPAdapter

    if settings.sqlserver_enabled:
        adapter = NeloERPAdapter.from_settings(settings)
        if await adapter.health_check():
            products = await adapter.fetch_products(limit=2000)
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
    transient network issue). Callers treat this as "ERP unavailable".
    """


class NeloERPAdapter:
    """Read-only view over the Nelo ERP SQL Server.

    Construct via ``from_settings(...)`` in production or pass an explicit
    ``engine`` in tests. The adapter keeps one ``AsyncEngine`` alive
    between calls (connection pooled); call ``close()`` on shutdown.
    """

    def __init__(self, engine: AsyncEngine, *, query_timeout_s: int = 30) -> None:
        self._engine = engine
        self._query_timeout_s = max(1, int(query_timeout_s))

    # ─── Construction ─────────────────────────────────────────────────

    @classmethod
    def from_settings(cls, settings: Any) -> "NeloERPAdapter":
        """Build the adapter from the app's ``Settings`` instance.

        Raises ``NeloERPError`` if the URL is missing — callers should
        check ``settings.sqlserver_enabled`` before calling this.
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
        """Return True when a trivial ``SELECT 1`` round-trips."""
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 AS one"))
                return result.scalar() == 1
        except Exception as exc:
            logger.warning("Nelo ERP health check failed: %s", exc)
            return False

    async def view_available(self, view_name: str) -> bool:
        """Return True when ``SELECT TOP 1`` from a ``vw_pp1_*`` view works.

        Used by the sync runbook to confirm IT NELO has applied
        ``views_pp1.sql``. ``view_name`` is validated against a whitelist
        so this can never become an injection vector.
        """
        if view_name not in _KNOWN_VIEWS:
            raise NeloERPError(f"unknown view: {view_name!r}")
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text(f"SELECT TOP 1 1 FROM {view_name}"))
                return True
        except Exception as exc:
            logger.warning("Nelo ERP view %s unavailable: %s", view_name, exc)
            return False

    # ─── Fetch methods — one per view consumed ───────────────────────

    async def fetch_products(self, *, limit: int = 5000) -> List[Dict[str, Any]]:
        """``vw_pp1_produto`` — products master (Q.20.B → core.products)."""
        sql = """
            SELECT TOP (:limit)
                product_id, product_code, product_name,
                product_type_raw, modelo_id, active
            FROM vw_pp1_produto
            ORDER BY product_code
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_product_phases(
        self, *, limit: int = 30000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_produto_fase`` — routing structure (Q.20.B).

        ``coeficiente_x`` is returned verbatim — it is money (€ bonus),
        NOT time. The ETL must NEVER treat it as a duration.
        """
        sql = """
            SELECT TOP (:limit)
                product_id, fase_id, sequencia,
                requires_mold, coeficiente, coeficiente_x
            FROM vw_pp1_produto_fase
            ORDER BY product_id, sequencia
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_phases(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        """``vw_pp1_fases_producao`` — phase catalogue (41 active of 71)."""
        sql = """
            SELECT TOP (:limit)
                fase_id, fase_nome, fase_sequencia, fase_activo
            FROM vw_pp1_fases_producao
            ORDER BY fase_sequencia, fase_nome
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_workers(
        self, *, active_only: bool = True, limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_entidade`` — workers / operators (Q.20.B → core.employees)."""
        where = "WHERE activo = 1" if active_only else ""
        sql = f"""
            SELECT TOP (:limit)
                entidade_id, nome, activo, custo_hora, data_admissao
            FROM vw_pp1_entidade
            {where}
            ORDER BY nome
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_employee_phases(
        self, *, limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_entidade_fase`` — skill matrix (Q.20.D, ~1269 rows)."""
        sql = """
            SELECT TOP (:limit)
                entidade_id, fase_id, apto, nivel
            FROM vw_pp1_entidade_fase
            WHERE apto = 1
            ORDER BY fase_id, entidade_id
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_components(
        self, *, limit: int = 30000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_produto_componente`` — BOM rows (Q.20.B → core.bom_items)."""
        sql = """
            SELECT TOP (:limit)
                produto_id, componente_id, quantidade, unidade, sequencia
            FROM vw_pp1_produto_componente
            ORDER BY produto_id, sequencia
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_molds(self, *, limit: int = 1000) -> List[Dict[str, Any]]:
        """``vw_pp1_moldes`` — ERP-side mold catalogue (~91 rows).

        The 510 production molds live in Excel; this view only carries the
        subset the ERP knows about. Used by Q.20.C as a reconcile cross-check.
        """
        sql = """
            SELECT TOP (:limit)
                molde_id, molde_nome, estado, modelo_id,
                numero_pocos, tamanho_id
            FROM vw_pp1_moldes
            ORDER BY molde_nome
        """
        return await self._fetch(sql, {"limit": int(limit)})

    async def fetch_operations(
        self,
        *,
        since: Optional[date] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_of_fp`` — operation history (Q.20.F time mining).

        2.6M rows in the full dataset — callers MUST batch via ``since``
        / ``limit``. ``duracao_horas`` is the cleaned ERP-side span; the
        ETL recomputes from ``fase_of_inicio``/``fase_of_fim`` and never
        trusts standard coefficients.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if since is not None:
            where = "WHERE fase_of_inicio >= :since"
            params["since"] = since
        sql = f"""
            SELECT TOP (:limit)
                of_id, produto_id, modelo_id, fase_id, entidade_id,
                fase_of_inicio, fase_of_fim, duracao_horas
            FROM vw_pp1_of_fp
            {where}
            ORDER BY fase_of_inicio
        """
        return await self._fetch(sql, params)

    async def fetch_quality_problems(
        self,
        *,
        since: Optional[date] = None,
        limit: int = 20000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_offp_probs`` — quality incidents (Q.20.E).

        ~90k rows historical — callers SHOULD pass ``since`` for
        incremental imports.
        """
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if since is not None:
            where = "WHERE data_registo >= :since"
            params["since"] = since
        sql = f"""
            SELECT TOP (:limit)
                prob_id, of_id, fase_culpada_id, fase_avaliacao_id,
                descricao, gravidade, data_registo,
                chefe_id, entidade_culpada_id, modelo_id
            FROM vw_pp1_offp_probs
            {where}
            ORDER BY data_registo
        """
        return await self._fetch(sql, params)

    async def fetch_checklists(
        self,
        *,
        since: Optional[date] = None,
        limit: int = 20000,
    ) -> List[Dict[str, Any]]:
        """``vw_pp1_of_checklist`` — checklist results (Q.20.E)."""
        params: Dict[str, Any] = {"limit": int(limit)}
        where = ""
        if since is not None:
            where = "WHERE data_registo >= :since"
            params["since"] = since
        sql = f"""
            SELECT TOP (:limit)
                checklist_id, of_id, fase_id, item,
                resultado, data_registo
            FROM vw_pp1_of_checklist
            {where}
            ORDER BY data_registo
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


# Whitelist for `view_available` — never let a caller probe arbitrary SQL.
_KNOWN_VIEWS = frozenset({
    "vw_pp1_produto",
    "vw_pp1_produto_fase",
    "vw_pp1_fases_producao",
    "vw_pp1_entidade",
    "vw_pp1_entidade_fase",
    "vw_pp1_produto_componente",
    "vw_pp1_moldes",
    "vw_pp1_of_fp",
    "vw_pp1_offp_probs",
    "vw_pp1_of_checklist",
})


# ─── Shadow / reconcile helper ──────────────────────────────────────


async def compare_shadow(
    live: List[Dict[str, Any]],
    curated: List[Dict[str, Any]],
    *,
    key: str,
) -> Dict[str, Any]:
    """Lightweight reconciliation helper — returns the keys present in
    one dataset but not the other plus the count on each side.

    Q.20 reuses this for the operational-vs-curated reconcile: after an
    ETL mirror runs, callers diff what the ERP says against what the
    curated Excel layer holds and log/alert on divergence. Not
    exhaustive (no column-by-column diff) — just enough to flag a
    shape mismatch.
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
