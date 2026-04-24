"""Nelo ERP adapter (SQL Server). Read-only by contract.

The Nelo factory's ERP lives on a separate server on the shop-floor LAN.
`NeloERPAdapter` is the only place in the codebase that knows its schema.
Callers receive plain dicts; swapping the ERP vendor later touches only
this package.

Read-only isn't enforced at the driver level — that's the DBA's job
(create a SQL Server login with SELECT on the relevant tables, nothing
else). This module simply never emits INSERT/UPDATE/DELETE.
"""

from .nelo_erp import NeloERPAdapter, NeloERPError

__all__ = ["NeloERPAdapter", "NeloERPError"]
