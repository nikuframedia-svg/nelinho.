"""
Configuration and parameters for Factory Data Product.

All business rules, thresholds, and Trust Index values are defined here.
Based on analysis of Folha_IA_extra.xlsx (10 sheets, ~1.1M rows).
"""

from pathlib import Path
from typing import Dict

# =============================================================================
# Paths
# =============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CURATED_DIR = DATA_DIR / "curated"

# =============================================================================
# Business Parameters
# =============================================================================

# Mold occupancy assumption for conflict detection
MOLD_OCCUPANCY_HOURS = 12

# Working hours per day (theoretical capacity calculation)
WORKING_HOURS_PER_DAY = 8

# =============================================================================
# Expected Volumetry (for sanity checks) - From Folha_IA_extra.xlsx
# =============================================================================

# Onda 3.1 — values verified directly against Folha_IA_extra.xlsx (see
# `python -c "import openpyxl; …"` audit, 2026-05-02). Previous correction
# notes that lived inline have been moved to the changelog.
EXPECTED_VOLUMES = {
    "OrdensFabrico": {"min": 25000, "max": 30000, "expected": 27911},
    "FasesOrdemFabrico": {"min": 500000, "max": 560000, "expected": 529450},
    "FuncionariosFaseOrdemFabrico": {"min": 400000, "max": 450000, "expected": 423769},
    "OrdemFabricoErros": {"min": 80000, "max": 95000, "expected": 89836},
    "Funcionarios": {"min": 280, "max": 350, "expected": 301},
    "Moldes": {"min": 450, "max": 550, "expected": 510},
    "Fases": {"min": 60, "max": 80, "expected": 71},
    "Modelos": {"min": 800, "max": 1000, "expected": 899},
    "FasesStandardModelos": {"min": 14000, "max": 17000, "expected": 15445},
    "FuncionariosFasesAptos": {"min": 800, "max": 1000, "expected": 902},
}

# =============================================================================
# Trust Index by Segment (0-100)
# Based on data quality analysis of Folha_IA_extra.xlsx
# =============================================================================

TRUST_INDEX: Dict[str, int] = {
    # Dimensions (Master Data)
    "Erros": 92,  # Stable semantics, good for BI
    "Fases": 85,  # Solid structure, theoretical capacity
    "OrdensFabrico": 82,  # Good for WIP/lead time
    "Funcionarios": 75,  # ValorHora issues (zeros/outliers)
    "Moldes": 70,  # Incomplete state dictionary
    "Modelos": 75,  # Assumed similar to Funcionarios
    
    # Transactional (Facts)
    "FasesOrdemFabrico_structure": 80,  # Good relational mesh
    "FasesOrdemFabrico_HorasPrevistas": 58,  # 56.6% zeros (critical!)
    "FasesOrdemFabrico_DataPrevista": 35,  # Only 4.8% coverage
    "FasesOrdemFabrico_Tempos": 62,  # Many zero durations
    "FasesStandardModelos": 60,  # Duplicates, zeros
    "FuncionariosFaseOrdemFabrico": 55,  # No real hours
    "FuncionariosFasesAptos": 55,  # Assumed similar
    "OrdemFabricoErros": 67,  # 41.5% missing FaseOfCulpada
}

# =============================================================================
# Data Quality Thresholds
# =============================================================================

# ValorHora outlier detection
VALOR_HORA_MIN = 1.0  # Below this is considered invalid
VALOR_HORA_MAX_PERCENTILE = 99  # Above this percentile is outlier

# Trust Index thresholds
TRUST_THRESHOLD_BLOCK = 0.50  # Below this, block metric
TRUST_THRESHOLD_WARNING = 0.70  # Below this, show warning
TRUST_THRESHOLD_OK = 0.85  # Above this, metric is reliable

# =============================================================================
# Phases that are NOT production (administrative)
# =============================================================================

NON_PRODUCTION_PHASES = [
    "Entregue",
    "Armazém",
    "Expedição",
    "Facturado",
]

# =============================================================================
# Column Mappings (expected columns per sheet)
# =============================================================================

SHEET_COLUMNS = {
    "OrdensFabrico": [
        "OrdemFabricoId",
        "DataCriacao",
        "DataAcabamento",
        "DataTransporte",
        "Modelo",
        "Estado",
    ],
    "FasesOrdemFabrico": [
        "FaseOfId",
        "OrdemFabricoId",
        "FaseId",
        "FaseOf_HorasPrevistas",
        "FaseOf_DataPrevista",
        "FaseOf_Inicio",
        "FaseOf_Fim",
        "MoldeOfId",
    ],
    "Funcionarios": [
        "FuncionarioId",
        "FuncionarioNome",
        "FuncionarioAtivo",
        "FuncionarioValorHora",
    ],
    "Fases": [
        "FaseId",
        "FaseNome",
        "Fase_Producao",
        "Fase_NumeroFuncionarios",
        "Fase_CapacidadeHorasDia",
    ],
    "Moldes": [
        "MoldeId",
        "MoldeNome",
        "NumeroPocos",
        "Modelo",
        "Tamanho",
        "MoldeEstado",
    ],
}

# =============================================================================
# Semantic Labels (for UI disclaimers)
# =============================================================================

SEMANTIC_LABELS = {
    "cost": "custo teórico estimado (sem horas reais por funcionário)",
    "capacity": "capacidade teórica parametrizada (sem paragens/turnos)",
    "planning": "datas previstas parciais (cobertura limitada)",
    "bottleneck": "gargalo provável (TOC com dados disponíveis)",
    "mold_conflict": "conflito potencial (assumindo ocupação de 12h)",
    "wip": "WIP teórico (ordens sem DataAcabamento)",
    "lead_time": "lead time observado (DataCriacao → DataAcabamento)",
    "quality": "análise de qualidade (erros registados)",
    "skills": "risco de competências (funcionários aptos activos)",
}

# =============================================================================
# Blocked Metrics (cannot be calculated with current data)
# =============================================================================

BLOCKED_METRICS = {
    "oee_real": {
        "reason": "Não existem dados de paragens/máquinas",
        "required_data": ["machine_downtime", "planned_production_time"],
    },
    "availability_oee": {
        "reason": "Não existem dados de paragens/máquinas",
        "required_data": ["machine_downtime", "planned_production_time"],
    },
    "otd_official": {
        "reason": "Não existe promessa comercial inequívoca (due date)",
        "required_data": ["promised_delivery_date"],
    },
    "productivity_individual_real": {
        "reason": "Não existem horas reais por funcionário",
        "required_data": ["actual_labor_hours_per_employee"],
    },
    "cost_real_per_order": {
        "reason": "Não existem horas reais por funcionário",
        "required_data": ["actual_labor_hours_per_employee"],
    },
    "capacity_real_per_day": {
        "reason": "Não existem dados de turnos/paragens",
        "required_data": ["shift_calendar", "machine_downtime"],
    },
    "mold_conflict_confirmed": {
        "reason": "DataPrevista tem apenas 4.8% de cobertura",
        "required_data": ["complete_scheduled_dates"],
    },
}

# =============================================================================
# Allowed Metrics (can be calculated with current data)
# =============================================================================

ALLOWED_METRICS = [
    "wip_theoretical",
    "backlog_theoretical_hours",
    "backlog_theoretical_days",
    "bottleneck_ranking",
    "lead_time_observed",
    "quality_error_count",
    "quality_error_by_type",
    "quality_error_by_phase",
    "mold_conflict_potential",
    "skills_risk_by_phase",
    "cost_theoretical_estimated",
    "capacity_theoretical_per_phase",
]

