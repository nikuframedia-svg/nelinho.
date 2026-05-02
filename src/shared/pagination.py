"""Sprint Q.9 (3.2) — pagination guard for list endpoints.

Endpoints that return collections accept ``limit`` / ``offset`` query
params. Without a hard cap they can be abused (or accidentally
dragged into memory) — call ``validate_pagination`` early in the
endpoint to enforce ``1 <= limit <= MAX_LIMIT`` and ``offset >= 0``.

The helper raises an HTTP 400 with a descriptive message; the
``MAX_LIMIT`` sentinel is exposed so individual endpoints can opt
into a tighter cap (e.g. heavy aggregations).
"""

from __future__ import annotations

from fastapi import HTTPException, status

MAX_LIMIT = 100


def validate_pagination(
    limit: int,
    offset: int,
    *,
    max_limit: int = MAX_LIMIT,
) -> None:
    """Raise ``HTTPException(400)`` when limit/offset are outside the
    allowed range. ``max_limit`` defaults to 100."""
    if limit < 1 or limit > max_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"limit must be between 1 and {max_limit}",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must be >= 0",
        )
