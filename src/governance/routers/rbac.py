"""RBAC matrix viewer.

Q.67.6.B5 — split from the legacy ``src/governance/api.py``. Single endpoint
that returns the in-memory ``ROLE_PERMISSIONS`` matrix from
:mod:`src.shared.auth.rbac` (Sprint Q.18.N).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Governance"])


@router.get("/rbac/matrix")
async def get_rbac_matrix():
    """Devolve a matriz roles x permissions actual (Sprint Q.18.N)."""
    from src.shared.auth.rbac import ROLE_PERMISSIONS, Permission, Role

    return {
        "roles": [r.value for r in Role],
        "permissions": [p.value for p in Permission],
        "matrix": {
            role.value: sorted([p.value for p in perms])
            for role, perms in ROLE_PERMISSIONS.items()
        },
    }


__all__ = ["router"]
