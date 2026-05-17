"""External system adapters (read-only).

Each sub-package exposes SQLAlchemy models + service helpers for an external
data source (NELO ERP `MAR-KAYAKS`, etc.). All models are READ-ONLY — they
must never be used to write back to source systems.
"""
