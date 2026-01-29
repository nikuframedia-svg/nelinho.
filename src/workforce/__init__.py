"""
Workforce Operations System - Backend Module
=============================================

This module implements the Workforce Operations System:
- Dependency graph generation
- Cascade impact analysis
- What-If simulation
- Training recommendations
- Scenario comparison

All based on real data from:
- FuncionariosFasesAptos (902 records)
- Funcionarios (301 employees)
- Fases (71 phases)
- FasesOrdemFabrico (backlog data)
"""

from .api import router as workforce_router

__all__ = ["workforce_router"]

