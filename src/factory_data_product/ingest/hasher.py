"""
Hashing Utilities — Contrato 010
================================

SHA256 hashing for:
- File content
- Individual rows
- Business keys
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class FileHasher:
    """
    Calculate SHA256 hash of a file.
    
    Used for:
    - Idempotency checks (same file = skip)
    - Audit trail
    """
    
    @staticmethod
    def hash_file(file_path: Path, chunk_size: int = 8192) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to file
            chunk_size: Read chunk size
        
        Returns:
            SHA256 hex digest (64 chars)
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """
        Calculate SHA256 hash of bytes.
        
        Args:
            data: Raw bytes
        
        Returns:
            SHA256 hex digest
        """
        return hashlib.sha256(data).hexdigest()


class RowHasher:
    """
    Calculate hashes for individual data rows.
    
    Used for:
    - Deduplication within ingestion
    - Audit trail per row
    """
    
    @staticmethod
    def hash_row(payload: Dict[str, Any]) -> str:
        """
        Calculate SHA256 hash of a row payload.
        
        The payload is serialized to JSON with sorted keys
        for deterministic hashing.
        
        Args:
            payload: Row data as dict
        
        Returns:
            SHA256 hex digest
        """
        # Normalize: sort keys, handle None, convert numbers
        normalized = RowHasher._normalize_for_hash(payload)
        json_str = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    
    @staticmethod
    def hash_business_key(key_fields: List[str], payload: Dict[str, Any]) -> Optional[str]:
        """
        Calculate SHA256 hash of business key fields.
        
        Args:
            key_fields: List of field names that form the business key
            payload: Row data as dict
        
        Returns:
            SHA256 hex digest, or None if any key field is missing
        """
        key_values = {}
        
        for field in key_fields:
            value = payload.get(field)
            if value is None or value == "":
                return None  # Can't form business key
            key_values[field] = value
        
        return RowHasher.hash_row(key_values)
    
    @staticmethod
    def _normalize_for_hash(data: Any) -> Any:
        """
        Normalize data for deterministic hashing.
        
        - None → null
        - Numbers → strings with consistent format
        - Dates → ISO format strings
        """
        if data is None:
            return None
        elif isinstance(data, dict):
            return {k: RowHasher._normalize_for_hash(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [RowHasher._normalize_for_hash(v) for v in data]
        elif isinstance(data, float):
            # Handle NaN and Inf
            if data != data:  # NaN check
                return None
            return str(data)
        elif isinstance(data, (int, bool)):
            return data
        else:
            return str(data)


