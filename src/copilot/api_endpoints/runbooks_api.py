"""
Runbook API Endpoints — P2 Enterprise Feature
==============================================

Endpoints for runbook execution with dry-run support.

Features:
- List available runbooks
- Execute runbook in DRY_RUN, PREVIEW, or EXECUTE mode
- Get execution history
- Rollback executed runbooks
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.copilot.runbooks import (
    RunbookEngineV2,
    ExecutionMode,
    RunbookExecution,
    get_runbook_engine_v2,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/runbooks", tags=["runbooks"])


# ============================================================================
# SCHEMAS
# ============================================================================

class RunbookInfo(BaseModel):
    """Runbook information."""
    
    name: str
    title: str
    description: str
    steps_count: int
    triggers: List[str]


class RunbookListResponse(BaseModel):
    """Response for runbook list."""
    
    runbooks: List[RunbookInfo]
    total: int


class RunbookExecuteRequest(BaseModel):
    """Request to execute a runbook."""
    
    runbook_name: str = Field(..., description="Name of the runbook to execute")
    mode: str = Field(
        "dry_run",
        description="Execution mode: dry_run, preview, or execute",
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Input context variables for the runbook",
    )


class StepResultResponse(BaseModel):
    """Step execution result."""
    
    step_id: str
    name: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    skipped_reason: Optional[str] = None
    action_result: Optional[Dict[str, Any]] = None


class RunbookExecutionResponse(BaseModel):
    """Response for runbook execution."""
    
    execution_id: str
    runbook_name: str
    mode: str
    success: bool
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: float
    
    steps: List[StepResultResponse]
    
    # Impact summary
    total_estimated_impact: Dict[str, Any]
    affected_kpis: List[str]
    affected_entities: List[str]
    
    # Rollback
    rollback_token: Optional[str] = None
    is_reversible: bool = True
    
    # Errors
    errors: List[str]
    warnings: List[str]


class ExecutionListResponse(BaseModel):
    """Response for execution list."""
    
    executions: List[Dict[str, Any]]
    total: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "",
    response_model=RunbookListResponse,
    summary="List available runbooks",
    description="List all available runbooks with their metadata.",
)
async def list_runbooks():
    """List available runbooks."""
    engine = get_runbook_engine_v2()
    runbooks = engine.list_runbooks()
    
    return RunbookListResponse(
        runbooks=[
            RunbookInfo(
                name=rb["name"],
                title=rb["title"],
                description=rb["description"],
                steps_count=rb["steps_count"],
                triggers=rb.get("triggers", []),
            )
            for rb in runbooks
        ],
        total=len(runbooks),
    )


@router.post(
    "/execute",
    response_model=RunbookExecutionResponse,
    summary="Execute a runbook",
    description="""
    Execute a runbook in the specified mode.
    
    Modes:
    - **dry_run**: Simulate all steps without side effects. Shows estimated impacts.
    - **preview**: Like dry_run but with more detailed impact analysis.
    - **execute**: Actually perform the actions (requires approval for sensitive actions).
    
    The dry_run mode is safe to call repeatedly and shows what would happen
    if the runbook were executed for real.
    """,
)
async def execute_runbook(request: RunbookExecuteRequest):
    """Execute a runbook."""
    engine = get_runbook_engine_v2()
    
    # Parse execution mode
    try:
        mode = ExecutionMode(request.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{request.mode}'. Must be one of: dry_run, preview, execute",
        )
    
    # Check if runbook exists
    try:
        engine.load_runbook(request.runbook_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Runbook '{request.runbook_name}' not found",
        )
    
    # Execute
    execution = await engine.execute(
        runbook_name=request.runbook_name,
        mode=mode,
        context=request.context,
    )
    
    # Convert to response
    return RunbookExecutionResponse(
        execution_id=str(execution.execution_id),
        runbook_name=execution.runbook_name,
        mode=execution.mode.value,
        success=execution.success,
        started_at=execution.started_at.isoformat(),
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        duration_ms=execution.duration_ms,
        steps=[
            StepResultResponse(
                step_id=s.step_id,
                name=s.name,
                status=s.status.value,
                started_at=s.started_at.isoformat() if s.started_at else None,
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                skipped_reason=s.skipped_reason,
                action_result={
                    "success": s.action_result.success,
                    "output": s.action_result.output,
                    "estimated_impact": s.action_result.estimated_impact,
                    "affected_entities": s.action_result.affected_entities,
                } if s.action_result else None,
            )
            for s in execution.steps
        ],
        total_estimated_impact=execution.total_estimated_impact,
        affected_kpis=list(execution.affected_kpis),
        affected_entities=execution.affected_entities,
        rollback_token=execution.rollback_token,
        is_reversible=execution.is_reversible,
        errors=execution.errors,
        warnings=execution.warnings,
    )


@router.get(
    "/executions",
    response_model=ExecutionListResponse,
    summary="List recent executions",
    description="List recent runbook executions with their results.",
)
async def list_executions(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of executions to return"),
):
    """List recent runbook executions."""
    engine = get_runbook_engine_v2()
    executions = engine.list_executions(limit=limit)
    
    return ExecutionListResponse(
        executions=executions,
        total=len(executions),
    )


@router.get(
    "/executions/{execution_id}",
    response_model=RunbookExecutionResponse,
    summary="Get execution details",
    description="Get detailed information about a specific runbook execution.",
)
async def get_execution(execution_id: str):
    """Get execution details."""
    engine = get_runbook_engine_v2()
    
    try:
        uid = UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution ID")
    
    execution = engine.get_execution(uid)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Convert to response (same as execute)
    return RunbookExecutionResponse(
        execution_id=str(execution.execution_id),
        runbook_name=execution.runbook_name,
        mode=execution.mode.value,
        success=execution.success,
        started_at=execution.started_at.isoformat(),
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        duration_ms=execution.duration_ms,
        steps=[
            StepResultResponse(
                step_id=s.step_id,
                name=s.name,
                status=s.status.value,
                started_at=s.started_at.isoformat() if s.started_at else None,
                completed_at=s.completed_at.isoformat() if s.completed_at else None,
                skipped_reason=s.skipped_reason,
                action_result={
                    "success": s.action_result.success,
                    "output": s.action_result.output,
                    "estimated_impact": s.action_result.estimated_impact,
                    "affected_entities": s.action_result.affected_entities,
                } if s.action_result else None,
            )
            for s in execution.steps
        ],
        total_estimated_impact=execution.total_estimated_impact,
        affected_kpis=list(execution.affected_kpis),
        affected_entities=execution.affected_entities,
        rollback_token=execution.rollback_token,
        is_reversible=execution.is_reversible,
        errors=execution.errors,
        warnings=execution.warnings,
    )


@router.post(
    "/{runbook_name}/dry-run",
    response_model=RunbookExecutionResponse,
    summary="Dry-run a runbook",
    description="""
    Execute a runbook in dry-run mode (shortcut endpoint).
    
    This is equivalent to calling POST /execute with mode='dry_run'.
    Safe to call repeatedly - no side effects.
    """,
)
async def dry_run_runbook(
    runbook_name: str,
    context: Optional[Dict[str, Any]] = None,
):
    """Dry-run a runbook."""
    request = RunbookExecuteRequest(
        runbook_name=runbook_name,
        mode="dry_run",
        context=context,
    )
    return await execute_runbook(request)

