"""
Tools API — Auto-generated Tool Registry
========================================

Endpoints to query and execute tools from the auto-generated registry.

Features:
- List all available tools
- Get tool details
- Execute tools (with validation)
- Get function schemas for LLM integration
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.copilot.tool_registry import (
    ToolRegistry,
    ToolCategory,
    get_tool_registry,
    get_tool_registry_sync,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tools", tags=["tools"])


# ============================================================================
# SCHEMAS
# ============================================================================

class ToolParameterResponse(BaseModel):
    """Tool parameter info."""
    
    name: str
    type: str
    data_type: str
    required: bool
    description: str
    default: Any = None
    enum: Optional[List[Any]] = None


class ToolResponse(BaseModel):
    """Tool info response."""
    
    id: str
    name: str
    description: str
    category: str
    method: str
    path: str
    parameters: List[ToolParameterResponse]
    tags: List[str]
    is_dangerous: bool
    requires_confirmation: bool


class ToolListResponse(BaseModel):
    """Response for tool list."""
    
    tools: List[ToolResponse]
    total: int
    categories: List[str]


class FunctionSchemaResponse(BaseModel):
    """Function schema for LLM."""
    
    name: str
    description: str
    parameters: Dict[str, Any]


class FunctionSchemasResponse(BaseModel):
    """Response for function schemas."""
    
    functions: List[FunctionSchemaResponse]
    total: int


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool."""
    
    tool_id: str = Field(..., description="ID of the tool to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""
    
    tool_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None


class ToolsSummaryResponse(BaseModel):
    """Summary of tools for system prompt."""
    
    summary: str
    version: str
    generated_at: str
    tools_count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "",
    response_model=ToolListResponse,
    summary="List available tools",
    description="List all tools auto-generated from the OpenAPI spec.",
)
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List available tools."""
    registry = get_tool_registry_sync()
    
    if registry is None:
        # Registry not loaded yet - load it
        registry = await get_tool_registry()
    
    # Parse category
    cat_filter = None
    if category:
        try:
            cat_filter = ToolCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category '{category}'. Valid: {[c.value for c in ToolCategory]}",
            )
    
    # Get tools
    tags = [tag] if tag else None
    tools = registry.list_tools(category=cat_filter, tags=tags)
    
    return ToolListResponse(
        tools=[
            ToolResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category.value,
                method=t.method,
                path=t.path,
                parameters=[
                    ToolParameterResponse(
                        name=p.name,
                        type=p.param_type,
                        data_type=p.data_type,
                        required=p.required,
                        description=p.description,
                        default=p.default,
                        enum=p.enum_values,
                    )
                    for p in t.parameters
                ],
                tags=t.tags,
                is_dangerous=t.is_dangerous,
                requires_confirmation=t.requires_confirmation,
            )
            for t in tools
        ],
        total=len(tools),
        categories=[c.value for c in ToolCategory],
    )


@router.get(
    "/functions",
    response_model=FunctionSchemasResponse,
    summary="Get function schemas for LLM",
    description="Get tools as function schemas compatible with OpenAI/Anthropic function calling.",
)
async def get_function_schemas(
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Get function schemas for LLM integration."""
    registry = get_tool_registry_sync()
    
    if registry is None:
        registry = await get_tool_registry()
    
    # Parse category
    cat_filter = None
    if category:
        try:
            cat_filter = ToolCategory(category)
        except ValueError:
            pass
    
    schemas = registry.get_function_schemas(category=cat_filter)
    
    return FunctionSchemasResponse(
        functions=[
            FunctionSchemaResponse(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in schemas
        ],
        total=len(schemas),
    )


@router.get(
    "/summary",
    response_model=ToolsSummaryResponse,
    summary="Get tools summary for system prompt",
    description="Get a text summary of available tools, suitable for LLM system prompt.",
)
async def get_tools_summary():
    """Get tools summary for system prompt."""
    registry = get_tool_registry_sync()
    
    if registry is None:
        registry = await get_tool_registry()
    
    return ToolsSummaryResponse(
        summary=registry.get_tools_summary(),
        version=registry.version,
        generated_at=registry.generated_at.isoformat(),
        tools_count=len(registry.tools),
    )


@router.get(
    "/{tool_id}",
    response_model=ToolResponse,
    summary="Get tool details",
    description="Get detailed information about a specific tool.",
)
async def get_tool(tool_id: str):
    """Get tool details."""
    registry = get_tool_registry_sync()
    
    if registry is None:
        registry = await get_tool_registry()
    
    tool = registry.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        category=tool.category.value,
        method=tool.method,
        path=tool.path,
        parameters=[
            ToolParameterResponse(
                name=p.name,
                type=p.param_type,
                data_type=p.data_type,
                required=p.required,
                description=p.description,
                default=p.default,
                enum=p.enum_values,
            )
            for p in tool.parameters
        ],
        tags=tool.tags,
        is_dangerous=tool.is_dangerous,
        requires_confirmation=tool.requires_confirmation,
    )


@router.post(
    "/execute",
    response_model=ToolExecuteResponse,
    summary="Execute a tool",
    description="""
    Execute a tool by calling the underlying API endpoint.
    
    **Warning**: This bypasses normal API routing. Use with caution.
    Dangerous tools will require explicit confirmation.
    """,
)
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool."""
    registry = get_tool_registry_sync()
    
    if registry is None:
        registry = await get_tool_registry()
    
    tool = registry.get_tool(request.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_id}' not found")
    
    # Execute
    try:
        result = await registry.execute_tool(request.tool_id, request.params)
        
        if isinstance(result, dict) and result.get("error"):
            return ToolExecuteResponse(
                tool_id=request.tool_id,
                success=False,
                error=result.get("message"),
            )
        
        return ToolExecuteResponse(
            tool_id=request.tool_id,
            success=True,
            result=result,
        )
    
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return ToolExecuteResponse(
            tool_id=request.tool_id,
            success=False,
            error=str(e),
        )


@router.post(
    "/reload",
    summary="Reload tool registry",
    description="Reload tools from the OpenAPI spec (useful after code changes).",
)
async def reload_registry():
    """Reload tool registry."""
    try:
        registry = await get_tool_registry()
        count = await registry.load_from_openapi()
        
        return {
            "success": True,
            "tools_loaded": count,
            "generated_at": registry.generated_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to reload registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))





