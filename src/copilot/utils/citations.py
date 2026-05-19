"""
ProdPlan ONE - COPILOT Citations Utilities
===========================================

Geração e formatação de citations.
"""

import hashlib
import json
from typing import Dict, List, Any
from uuid import uuid4


def create_db_citation(
    table: str,
    query_hash: str,
    label: str,
    confidence: float = 0.95,
    trust_index: float = 0.88,
) -> Dict[str, Any]:
    """Criar citation de base de dados."""
    return {
        "source_type": "db",
        "ref": f"table:{table};query_hash:{query_hash}",
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_rag_citation(
    chunk_id: str,
    source_type: str,
    source_id: str,
    label: str,
    confidence: float = 0.85,
    trust_index: float = 0.80,
) -> Dict[str, Any]:
    """Criar citation de RAG chunk."""
    return {
        "source_type": "rag",
        "ref": f"chunk_id:{chunk_id};source_type:{source_type};source_id:{source_id}",
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_calculation_citation(
    calculation_type: str,
    inputs: Dict[str, Any],
    label: str,
    confidence: float = 0.90,
    trust_index: float = 0.85,
) -> Dict[str, Any]:
    """Criar citation de cálculo."""
    inputs_hash = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode()
    ).hexdigest()[:16]
    
    return {
        "source_type": "calculation",
        "ref": f"calc:{calculation_type};inputs_hash:{inputs_hash}",
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_tool_citation(
    tool_id: str,
    params: Dict[str, Any],
    label: str = None,
    confidence: float = 0.90,
    trust_index: float = 0.85,
) -> Dict[str, Any]:
    """Criar citation determinística para uma tool call do loop agêntico.

    Q.37.E — cada entrada do ``tool_log`` gera uma citation com
    ``source_type="calculation"`` e ``ref="tool:<id>;params_hash:<...>"``.
    O hash dos params é determinístico (sha256 de JSON ordenado), por
    isso a mesma tool call produz sempre a mesma citation — auditável e
    reproduzível.
    """
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return {
        "source_type": "calculation",
        "ref": f"tool:{tool_id};params_hash:{params_hash}",
        "label": label or f"Ferramenta: {tool_id}",
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_event_citation(
    event_type: str,
    event_id: str,
    label: str,
    confidence: float = 0.88,
    trust_index: float = 0.82,
) -> Dict[str, Any]:
    """Criar citation de evento."""
    return {
        "source_type": "event",
        "ref": f"event_type:{event_type};event_id:{event_id}",
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_recommendation_citation(
    recommendation_id: str,
    title: str,
    label: str = None,
    confidence: float = 0.75,
    trust_index: float = 0.70,
) -> Dict[str, Any]:
    """Criar citation de recomendação."""
    return {
        "source_type": "recommendation",
        "ref": f"rec:{recommendation_id}",
        "label": label or f"Recomendação: {title}",
        "confidence": confidence,
        "trust_index": trust_index,
    }


def create_system_data_citation(
    data_source: str,
    data_id: str,
    label: str,
    confidence: float = 0.90,
    trust_index: float = 0.85,
) -> Dict[str, Any]:
    """Criar citation de dados do sistema (KPIs, métricas, etc.)."""
    return {
        "source_type": "system_data",
        "ref": f"system:{data_source};id:{data_id}",
        "label": label,
        "confidence": confidence,
        "trust_index": trust_index,
    }

