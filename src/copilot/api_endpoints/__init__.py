"""
Copilot API Endpoints Module
============================

API endpoints for copilot functionality:
- Runbooks execution with dry-run
- Tool Registry from OpenAPI
"""

from src.copilot.api_endpoints.runbooks_api import router as runbooks_router
from src.copilot.api_endpoints.tools_api import router as tools_router

__all__ = ["runbooks_router", "tools_router"]

