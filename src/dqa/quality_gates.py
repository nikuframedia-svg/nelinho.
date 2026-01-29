"""
ProdPlan ONE - Quality Gates Middleware
========================================

FastAPI middleware to enforce TrustIndex gates on critical endpoints.
Blocks requests with TrustIndex < 0.70 (HTTP 422).
"""

import json
import logging
from typing import Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .trust_index import TrustIndexCalculator

logger = logging.getLogger(__name__)


# Default configuration for critical endpoints
CRITICAL_ENDPOINTS_CONFIG = {
    "/v1/plan/replan": {
        "required_fields": {"order_ids": list},
        "valid_ranges": {},
    },
    "/v1/plan/commit": {
        "required_fields": {"schedule_id": str},
        "valid_ranges": {},
    },
    "/v1/supply/forecast": {
        "required_fields": {"sku_id": str},
        "valid_ranges": {"periods_ahead": (1, 365)},
    },
}


class QualityGateMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce TrustIndex gates.
    
    Intercepts critical endpoints and blocks requests with TrustIndex < 0.70.
    
    Args:
        app: FastAPI application
        trust_index_calculator: Optional TrustIndexCalculator (will create default if None)
        critical_endpoints: Dict of endpoint -> config (required_fields, valid_ranges)
    """
    
    def __init__(
        self,
        app,
        trust_index_calculator: TrustIndexCalculator = None,
        critical_endpoints: dict = None,
    ):
        super().__init__(app)
        self.trust_index_calculator = trust_index_calculator
        self.critical_endpoints = critical_endpoints or CRITICAL_ENDPOINTS_CONFIG
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through quality gates.
        
        Only applies to critical endpoints configured in self.critical_endpoints.
        """
        # Only apply to critical endpoints
        if request.url.path not in self.critical_endpoints:
            return await call_next(request)
        
        # Only check POST/PUT/PATCH methods
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)
        
        # Get endpoint config
        endpoint_config = self.critical_endpoints.get(request.url.path)
        if not endpoint_config:
            return await call_next(request)
        
        # Read request body
        try:
            body = await request.body()
            
            if not body:
                # Empty body - skip check
                return await call_next(request)
            
            # Parse JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                # Not JSON - skip check
                return await call_next(request)
            
            # Get or create calculator
            if not self.trust_index_calculator:
                calculator = TrustIndexCalculator(
                    required_fields=endpoint_config.get("required_fields", {}),
                    valid_ranges=endpoint_config.get("valid_ranges", {}),
                    sla_latency_seconds=60,
                )
            else:
                calculator = self.trust_index_calculator
            
            # Calculate TrustIndex
            trust_result = calculator.calculate(entity=data, latency_ms=0)
            trust_index = trust_result["trust_index"]
            
            # Gate: block if insufficient quality
            if trust_index < 0.70:
                logger.warning(
                    f"Quality gate blocked: {request.url.path} - "
                    f"TrustIndex {trust_index:.3f} < 0.70. Issues: {trust_result['issues']}"
                )
                
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "data_quality_insufficient",
                        "trust_index": trust_index,
                        "components": trust_result["components"],
                        "issues": trust_result["issues"],
                        "suggestion": "Please review and correct data quality issues",
                    },
                )
            
            # Pass through - attach TrustIndex to request state
            request.state.trust_index = trust_index
            request.state.quality_assessment = trust_result
            
            # Recreate request with body (body was consumed)
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
        
        except HTTPException:
            # Re-raise HTTP exceptions (quality gate blocking)
            raise
        except Exception as e:
            # Log error but don't block request
            logger.error(f"Quality gate middleware error: {e}", exc_info=True)
            # Continue without quality check
        
        return await call_next(request)










