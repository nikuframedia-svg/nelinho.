"""Sprint Q.15.0 — diagnostic tools package.

Q.67.4.B added :mod:`schema_introspection` — live DB schema discovery
that the copilot LLM can call (list tables / describe table).
"""

from .schema_introspection import describe_table, list_database_tables

__all__ = [
    "describe_table",
    "list_database_tables",
]
