"""
Services layer for Factory Data Product.

Provides business logic and semantic queries on curated data.
"""

from .semantic_queries_inmemory import SemanticQueriesInMemory, get_semantic_service

__all__ = ["SemanticQueriesInMemory", "get_semantic_service"]

