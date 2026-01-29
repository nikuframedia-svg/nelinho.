"""
ProdPlan ONE - COPILOT Hashing Utilities
=========================================

SHA-256 hashing for prompts and responses (audit).
"""

import hashlib
from typing import Any, Dict


def sha256_hash(data: str) -> str:
    """Calculate SHA-256 hash of string data."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_dict(data: Dict[str, Any]) -> str:
    """Calculate SHA-256 hash of dictionary (JSON-serialized)."""
    import json
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return sha256_hash(json_str)


