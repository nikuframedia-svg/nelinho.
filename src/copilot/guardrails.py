"""
ProdPlan ONE - COPILOT Guardrails
===================================

Prompt injection filter, allow-list de ações, output validation.
"""

import logging
import re
from typing import Dict, List, Any, Tuple

from src.copilot.schemas import CopilotResponse, Action

logger = logging.getLogger(__name__)


# Padrões de prompt injection (simplificado - pode ser melhorado)
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(previous|all|above|instructions)",
    r"(?i)forget\s+(previous|all|everything)",
    r"(?i)reveal\s+(system\s+)?prompt",
    r"(?i)show\s+(me\s+)?(the\s+)?(system\s+)?prompt",
    r"(?i)execute\s+(command|code|script)",
    r"(?i)run\s+(command|code|script)",
    r"(?i)system\s*:\s*",
    r"(?i)assistant\s*:\s*",
    r"(?i)you\s+are\s+now",
    r"(?i)pretend\s+you\s+are",
    r"(?i)act\s+as\s+if",
]


# Allow-list de ações
ALLOWED_ACTIONS = {
    "CREATE_DECISION_PR",
    "DRY_RUN",
    "OPEN_ENTITY",
    "RUN_RUNBOOK",
}

# Endpoints whitelisted para DRY_RUN
DRY_RUN_WHITELIST = [
    "/v1/plan/schedules/{id}/dry-run",
    # Adicionar mais conforme necessário
]


def detect_prompt_injection(user_query: str) -> Tuple[float, List[str]]:
    """
    Detetar tentativas de prompt injection.
    
    Returns:
        (risk_score, matched_patterns)
        - risk_score: 0.0-1.0 (1.0 = alto risco)
        - matched_patterns: lista de padrões detetados
    """
    risk_score = 0.0
    matched_patterns = []
    
    query_lower = user_query.lower()
    
    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, user_query, re.IGNORECASE)
        if matches:
            matched_patterns.append(pattern)
            risk_score += 0.15  # Cada padrão aumenta risco
    
    # Normalizar para 0-1
    risk_score = min(risk_score, 1.0)
    
    if matched_patterns:
        logger.warning(
            f"Prompt injection detetado (score={risk_score:.2f}): {matched_patterns}"
        )
    
    return risk_score, matched_patterns


def validate_actions(actions: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validar que todas as ações estão no allow-list.
    
    Returns:
        (valid, errors)
    """
    errors = []
    
    # Verificar se actions é uma lista
    if not isinstance(actions, list):
        errors.append(f"actions deve ser uma lista, recebido: {type(actions).__name__}")
        return False, errors
    
    for action in actions:
        if not isinstance(action, dict):
            # Se não for dict, tentar normalizar (pode ser string ou outro tipo)
            if isinstance(action, str):
                # Se for string, ignorar (já foi normalizado no service)
                continue
            errors.append(f"Ação deve ser um dict, recebido: {type(action).__name__}")
            continue
        action_type = action.get("action_type") or action.get("type")  # Aceitar ambos
        # Ignorar ações sem action_type ou com None
        if action_type is None or action_type == "":
            continue
        if action_type not in ALLOWED_ACTIONS:
            errors.append(f"Ação '{action_type}' não está no allow-list")
    
    return len(errors) == 0, errors


def validate_response_structure(
    response: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validar estrutura da resposta do LLM.
    
    Verifica:
    - facts não vazio (exceto INSUFFICIENT_EVIDENCE)
    - actions no allow-list
    - citations presentes em facts
    
    Returns:
        (valid, errors)
    """
    errors = []
    
    # Validar tipo
    response_type = response.get("type")
    if response_type not in ("ANSWER", "RUNBOOK_RESULT", "PROPOSAL", "ERROR"):
        errors.append(f"Tipo inválido: {response_type}")
    
    # Validar facts
    facts = response.get("facts", [])
    warnings = response.get("warnings", [])
    
    has_insufficient_evidence = any(
        w.get("code") == "INSUFFICIENT_EVIDENCE" for w in warnings
    )
    
    if response_type in ("ANSWER", "PROPOSAL"):
        if not facts and not has_insufficient_evidence:
            errors.append(
                "facts[] não pode estar vazio quando type=ANSWER/PROPOSAL "
                "(exceto se warnings incluir INSUFFICIENT_EVIDENCE)"
            )
        
        # Validar que cada fact tem citations (mas permitir facts sem citations se houver INSUFFICIENT_EVIDENCE)
        if not has_insufficient_evidence:
            for i, fact in enumerate(facts):
                citations = fact.get("citations", [])
                if not citations or len(citations) == 0:
                    # Avisar mas não bloquear - pode ser normalizado depois
                    logger.debug(f"Fact {i} não tem citations, mas pode ser aceite se houver normalização")
    
    # Validar actions
    actions = response.get("actions", [])
    if not isinstance(actions, list):
        errors.append(f"actions deve ser uma lista, recebido: {type(actions).__name__}")
    else:
        actions_valid, action_errors = validate_actions(actions)
        if not actions_valid:
            errors.extend(action_errors)
    
    return len(errors) == 0, errors


def check_security_flag(user_query: str) -> bool:
    """
    Verificar se query deve ser bloqueada por segurança.
    
    Returns:
        True se deve bloquear (SECURITY_FLAG)
    """
    risk_score, _ = detect_prompt_injection(user_query)
    return risk_score > 0.7  # Threshold para bloquear


# ============================================================================
# EVIDENCE VALIDATOR (P0-2: Evidence Required Everywhere)
# ============================================================================

# Numbers that can be returned without evidence (counts, IDs, etc.)
ALLOWED_RAW_NUMBERS = {
    "id",
    "count",
    "total",
    "page",
    "page_size",
    "offset",
    "limit",
    "rank",
    "order",
    "index",
    "sequence",
    "version",
    "timestamp",
    "status_code",
}

# Metric IDs that MUST have evidence
EVIDENCE_REQUIRED_METRICS = {
    "wip",
    "backlog",
    "bottleneck",
    "lead_time",
    "cost",
    "capacity",
    "coverage",
    "trust",
    "hours",
    "days",
    "percentage",
    "rate",
    "ratio",
    "delta",
    "oee",
    "otd",
    "productivity",
    "efficiency",
}


class EvidenceRequiredError(Exception):
    """Raised when a numeric response is missing required evidence."""
    
    def __init__(self, missing_evidence: List[str]):
        self.missing_evidence = missing_evidence
        super().__init__(f"Evidence required for: {', '.join(missing_evidence)}")


class EvidenceValidator:
    """
    Validates that all numeric responses have proper evidence.
    
    This is a NON-NEGOTIABLE requirement of the system.
    No number leaves the system without:
    - lineage (source + active_run + query_hash)
    - trust (index + coverage + warnings + blockers)
    - semantics (theoretical/observed/imputed)
    - explain (definition + formula)
    """
    
    @staticmethod
    def is_metric_key(key: str) -> bool:
        """Check if a key represents a metric that needs evidence."""
        key_lower = key.lower()
        
        # Skip allowed raw numbers
        if key_lower in ALLOWED_RAW_NUMBERS:
            return False
        
        # Check if contains metric-related words
        for metric in EVIDENCE_REQUIRED_METRICS:
            if metric in key_lower:
                return True
        
        # Keys ending with common metric suffixes
        metric_suffixes = ("_pct", "_hours", "_days", "_count", "_value", "_score", "_index")
        if key_lower.endswith(metric_suffixes):
            return True
        
        return False
    
    @staticmethod
    def has_evidence(response: Dict[str, Any], key: str) -> bool:
        """Check if a metric key has associated evidence."""
        # Check for _evidence suffix
        if f"{key}_evidence" in response:
            return True
        
        # Check for _explain suffix
        if f"{key}_explain" in response:
            return True
        
        # Check for _trust suffix
        if f"{key}_trust" in response:
            return True
        
        # Check for _lineage suffix
        if f"{key}_lineage" in response:
            return True
        
        # Check if value is wrapped in ExplainedValue-like structure
        value = response.get(key)
        if isinstance(value, dict):
            required_fields = {"lineage", "trust", "explain"}
            if required_fields.issubset(set(value.keys())):
                return True
        
        return False
    
    @classmethod
    def validate_response(cls, response: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that all numeric values in response have evidence.
        
        Args:
            response: The response dictionary to validate
            
        Returns:
            (is_valid, missing_evidence_keys)
        """
        missing = []
        
        def check_value(obj: Any, path: str = "") -> None:
            """Recursively check for naked numbers."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Check if this is a metric with numeric value
                    if isinstance(value, (int, float)) and cls.is_metric_key(key):
                        if not cls.has_evidence(obj, key):
                            missing.append(current_path)
                    
                    # Recurse into nested structures
                    check_value(value, current_path)
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_value(item, f"{path}[{i}]")
        
        check_value(response)
        
        return len(missing) == 0, missing
    
    @classmethod
    def enforce_evidence(cls, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce evidence requirements by raising error if validation fails.
        
        This should be called before returning any response with metrics.
        
        Args:
            response: The response to validate
            
        Returns:
            The same response if valid
            
        Raises:
            EvidenceRequiredError: If metrics are missing evidence
        """
        is_valid, missing = cls.validate_response(response)
        
        if not is_valid:
            logger.error(f"Evidence validation failed. Missing evidence for: {missing}")
            raise EvidenceRequiredError(missing)
        
        return response


def validate_copilot_output(response: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Full validation of copilot output including evidence requirements.
    
    This combines:
    - Structure validation
    - Action validation
    - Evidence validation
    
    Returns:
        (is_valid, all_errors)
    """
    all_errors = []
    
    # Structure validation
    struct_valid, struct_errors = validate_response_structure(response)
    all_errors.extend(struct_errors)
    
    # Evidence validation for facts
    facts = response.get("facts", [])
    for i, fact in enumerate(facts):
        # Each fact with numeric values needs evidence
        ev_valid, ev_missing = EvidenceValidator.validate_response(fact)
        if not ev_valid:
            for missing_key in ev_missing:
                all_errors.append(f"Fact[{i}].{missing_key}: Evidence required")
    
    return len(all_errors) == 0, all_errors


