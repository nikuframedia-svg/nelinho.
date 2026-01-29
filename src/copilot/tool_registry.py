"""
Tool Registry — Auto-generated from OpenAPI
============================================

Generates Copilot tools automatically from FastAPI OpenAPI spec.

Features:
- Parses OpenAPI spec from running app
- Creates Tool definitions for each endpoint
- Filters by allowed paths/methods
- Generates JSON schema for parameters
- Provides execution wrappers

This enables the LLM to call any API endpoint as a tool,
with proper parameter validation and documentation.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import httpx

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Categories of tools."""
    DATA_READ = "data_read"       # Read-only data access
    DATA_WRITE = "data_write"     # Data modification
    ANALYSIS = "analysis"         # Analysis/computation
    SCENARIO = "scenario"         # Scenario management
    DECISION = "decision"         # Decision/governance
    SYSTEM = "system"             # System management


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    
    name: str
    param_type: str  # "path", "query", "body"
    data_type: str   # "string", "integer", "boolean", "object", "array"
    required: bool = False
    description: str = ""
    default: Any = None
    enum_values: Optional[List[Any]] = None
    schema: Optional[Dict[str, Any]] = None


@dataclass
class Tool:
    """Tool definition generated from OpenAPI endpoint."""
    
    id: str
    name: str
    description: str
    category: ToolCategory
    
    # HTTP details
    method: str
    path: str
    
    # Parameters
    parameters: List[ToolParameter] = field(default_factory=list)
    request_body_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    requires_auth: bool = True
    is_dangerous: bool = False
    requires_confirmation: bool = False
    
    # Usage
    example_usage: Optional[str] = None
    rate_limit: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/LLM."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "method": self.method,
            "path": self.path,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.param_type,
                    "data_type": p.data_type,
                    "required": p.required,
                    "description": p.description,
                    "default": p.default,
                    "enum": p.enum_values,
                }
                for p in self.parameters
            ],
            "request_body_schema": self.request_body_schema,
            "response_schema": self.response_schema,
            "tags": self.tags,
            "requires_auth": self.requires_auth,
            "is_dangerous": self.is_dangerous,
            "requires_confirmation": self.requires_confirmation,
            "example_usage": self.example_usage,
        }
    
    def to_function_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI/Anthropic function schema format."""
        properties = {}
        required = []
        
        for param in self.parameters:
            param_schema = {
                "type": param.data_type,
                "description": param.description,
            }
            
            if param.enum_values:
                param_schema["enum"] = param.enum_values
            
            if param.default is not None:
                param_schema["default"] = param.default
            
            properties[param.name] = param_schema
            
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.id,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


# Path patterns for categorization
CATEGORY_PATTERNS = {
    ToolCategory.DATA_READ: [
        r"^GET /v1/factory/",
        r"^GET /v1/explain/",
        r"^GET /api/orders",
        r"^GET /api/errors",
    ],
    ToolCategory.DATA_WRITE: [
        r"^POST /v1/factory/ingest",
        r"^POST /v1/factory/activate",
        r"^POST /v1/factory/rollback",
    ],
    ToolCategory.ANALYSIS: [
        r"/semantic/queries/",
        r"/analyze",
        r"/quality",
    ],
    ToolCategory.SCENARIO: [
        r"/twin/",
        r"/sandbox/",
        r"/scenarios",
    ],
    ToolCategory.DECISION: [
        r"/decisions/",
        r"/approve",
        r"/execute",
        r"/runbooks/",
    ],
}

# Paths that should NOT be exposed as tools
BLOCKED_PATHS = {
    "/health",
    "/ready",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/api/internal",
}

# Dangerous operations requiring confirmation
DANGEROUS_PATTERNS = [
    r"^DELETE ",
    r"/rollback",
    r"/execute$",
    r"/approve$",
]


@dataclass
class ToolRegistry:
    """
    Registry of tools generated from OpenAPI spec.
    
    Usage:
        registry = ToolRegistry()
        await registry.load_from_openapi("http://localhost:8000")
        
        # Get all tools
        tools = registry.list_tools()
        
        # Get tools for LLM
        function_schemas = registry.get_function_schemas()
        
        # Execute a tool
        result = await registry.execute_tool("get_wip", {"phase_id": "CORTE"})
    """
    
    tools: Dict[str, Tool] = field(default_factory=dict)
    
    # Configuration
    base_url: str = "http://localhost:8000"
    allowed_categories: Set[ToolCategory] = field(default_factory=lambda: set(ToolCategory))
    
    # Metadata
    version: str = "1.0"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    openapi_hash: Optional[str] = None
    
    async def load_from_openapi(
        self,
        base_url: Optional[str] = None,
        openapi_spec: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Load tools from OpenAPI specification.
        
        Args:
            base_url: Base URL of the API (to fetch /openapi.json)
            openapi_spec: Pre-loaded OpenAPI spec (alternative to fetching)
        
        Returns:
            Number of tools loaded
        """
        if base_url:
            self.base_url = base_url
        
        # Fetch or use provided spec
        if openapi_spec is None:
            openapi_spec = await self._fetch_openapi()
        
        # Calculate hash for caching
        spec_json = json.dumps(openapi_spec, sort_keys=True)
        self.openapi_hash = hashlib.sha256(spec_json.encode()).hexdigest()[:16]
        
        # Parse paths
        paths = openapi_spec.get("paths", {})
        
        for path, path_item in paths.items():
            # Skip blocked paths
            if self._is_blocked(path):
                continue
            
            for method, operation in path_item.items():
                if method.upper() not in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    continue
                
                tool = self._create_tool(path, method.upper(), operation, openapi_spec)
                
                if tool:
                    self.tools[tool.id] = tool
        
        logger.info(f"Loaded {len(self.tools)} tools from OpenAPI spec")
        self.generated_at = datetime.now(timezone.utc)
        
        return len(self.tools)
    
    async def _fetch_openapi(self) -> Dict[str, Any]:
        """Fetch OpenAPI spec from the API."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/openapi.json")
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to fetch OpenAPI spec: {e}")
                raise
    
    def _is_blocked(self, path: str) -> bool:
        """Check if path should be blocked."""
        for blocked in BLOCKED_PATHS:
            if path.startswith(blocked) or path == blocked:
                return True
        return False
    
    def _create_tool(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> Optional[Tool]:
        """Create a Tool from an OpenAPI operation."""
        # Generate tool ID
        tool_id = self._generate_tool_id(path, method)
        
        # Get summary/description
        summary = operation.get("summary", "")
        description = operation.get("description", summary)
        
        if not description:
            description = f"{method} {path}"
        
        # Determine category
        category = self._categorize_tool(path, method)
        
        # Parse parameters
        parameters = self._parse_parameters(operation, spec)
        
        # Parse request body
        request_body_schema = None
        if "requestBody" in operation:
            request_body_schema = self._parse_request_body(operation["requestBody"], spec)
        
        # Parse response schema
        response_schema = None
        responses = operation.get("responses", {})
        if "200" in responses:
            response_schema = self._parse_response(responses["200"], spec)
        
        # Check if dangerous
        is_dangerous = self._is_dangerous(path, method)
        
        return Tool(
            id=tool_id,
            name=summary or tool_id,
            description=description,
            category=category,
            method=method,
            path=path,
            parameters=parameters,
            request_body_schema=request_body_schema,
            response_schema=response_schema,
            tags=operation.get("tags", []),
            requires_auth=bool(operation.get("security")),
            is_dangerous=is_dangerous,
            requires_confirmation=is_dangerous,
        )
    
    def _generate_tool_id(self, path: str, method: str) -> str:
        """Generate a unique tool ID from path and method."""
        # Clean path
        clean_path = path.replace("/v1/", "").replace("/api/", "")
        clean_path = re.sub(r"\{[^}]+\}", "", clean_path)  # Remove path params
        clean_path = clean_path.strip("/").replace("/", "_").replace("-", "_")
        
        # Combine with method
        prefix = method.lower()
        if method == "GET":
            prefix = "get"
        elif method == "POST":
            prefix = "create" if "ingest" not in path else "do"
        elif method == "PUT":
            prefix = "update"
        elif method == "DELETE":
            prefix = "delete"
        
        return f"{prefix}_{clean_path}".strip("_")
    
    def _categorize_tool(self, path: str, method: str) -> ToolCategory:
        """Determine tool category from path and method."""
        full_path = f"{method} {path}"
        
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, full_path):
                    return category
        
        # Default based on method
        if method == "GET":
            return ToolCategory.DATA_READ
        elif method in ["POST", "PUT", "PATCH"]:
            return ToolCategory.DATA_WRITE
        else:
            return ToolCategory.SYSTEM
    
    def _is_dangerous(self, path: str, method: str) -> bool:
        """Check if operation is dangerous."""
        full_path = f"{method} {path}"
        
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, full_path):
                return True
        
        return False
    
    def _parse_parameters(
        self,
        operation: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> List[ToolParameter]:
        """Parse operation parameters."""
        parameters = []
        
        for param in operation.get("parameters", []):
            param = self._resolve_ref(param, spec)
            
            schema = param.get("schema", {})
            schema = self._resolve_ref(schema, spec)
            
            parameters.append(ToolParameter(
                name=param.get("name", ""),
                param_type=param.get("in", "query"),
                data_type=schema.get("type", "string"),
                required=param.get("required", False),
                description=param.get("description", ""),
                default=schema.get("default"),
                enum_values=schema.get("enum"),
                schema=schema,
            ))
        
        return parameters
    
    def _parse_request_body(
        self,
        request_body: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Parse request body schema."""
        request_body = self._resolve_ref(request_body, spec)
        
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})
        
        return self._resolve_ref(schema, spec)
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Parse response schema."""
        response = self._resolve_ref(response, spec)
        
        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})
        
        return self._resolve_ref(schema, spec)
    
    def _resolve_ref(
        self,
        obj: Any,
        spec: Dict[str, Any],
    ) -> Any:
        """Resolve $ref in OpenAPI spec."""
        if not isinstance(obj, dict):
            return obj
        
        if "$ref" not in obj:
            return obj
        
        ref = obj["$ref"]
        if not ref.startswith("#/"):
            return obj
        
        # Parse reference path
        parts = ref[2:].split("/")
        current = spec
        
        for part in parts:
            if part in current:
                current = current[part]
            else:
                return obj
        
        return current
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Tool]:
        """List tools with optional filtering."""
        tools = list(self.tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        if tags:
            tools = [t for t in tools if any(tag in t.tags for tag in tags)]
        
        return tools
    
    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a specific tool by ID."""
        return self.tools.get(tool_id)
    
    def get_function_schemas(
        self,
        category: Optional[ToolCategory] = None,
    ) -> List[Dict[str, Any]]:
        """Get tools in function schema format (for LLM)."""
        tools = self.list_tools(category=category)
        return [t.to_function_schema() for t in tools]
    
    def get_tools_summary(self) -> str:
        """Get a text summary of available tools (for system prompt)."""
        lines = ["Available tools:"]
        
        for category in ToolCategory:
            cat_tools = self.list_tools(category=category)
            if cat_tools:
                lines.append(f"\n## {category.value.replace('_', ' ').title()}")
                for tool in cat_tools:
                    params = ", ".join(p.name for p in tool.parameters[:3])
                    if len(tool.parameters) > 3:
                        params += "..."
                    lines.append(f"- {tool.id}({params}): {tool.name}")
        
        return "\n".join(lines)
    
    async def execute_tool(
        self,
        tool_id: str,
        params: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool by calling the underlying API endpoint.
        
        Args:
            tool_id: ID of the tool to execute
            params: Parameters for the tool
            headers: Optional HTTP headers (e.g., auth)
        
        Returns:
            API response as dictionary
        """
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")
        
        if tool.requires_confirmation:
            logger.warning(f"Tool {tool_id} requires confirmation (is_dangerous=True)")
        
        # Build URL with path parameters
        url = self.base_url + tool.path
        for param in tool.parameters:
            if param.param_type == "path" and param.name in params:
                url = url.replace(f"{{{param.name}}}", str(params[param.name]))
        
        # Separate query params and body
        query_params = {}
        body = None
        
        for param in tool.parameters:
            if param.name in params:
                if param.param_type == "query":
                    query_params[param.name] = params[param.name]
        
        # If there's a request body schema, remaining params go to body
        if tool.request_body_schema:
            body_params = {k: v for k, v in params.items() if k not in query_params}
            if body_params:
                body = body_params
        
        # Execute request
        async with httpx.AsyncClient() as client:
            try:
                if tool.method == "GET":
                    response = await client.get(url, params=query_params, headers=headers)
                elif tool.method == "POST":
                    response = await client.post(url, params=query_params, json=body, headers=headers)
                elif tool.method == "PUT":
                    response = await client.put(url, params=query_params, json=body, headers=headers)
                elif tool.method == "DELETE":
                    response = await client.delete(url, params=query_params, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {tool.method}")
                
                response.raise_for_status()
                return response.json()
            
            except httpx.HTTPStatusError as e:
                return {
                    "error": True,
                    "status_code": e.response.status_code,
                    "message": str(e),
                }
            except Exception as e:
                return {
                    "error": True,
                    "message": str(e),
                }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary."""
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat(),
            "openapi_hash": self.openapi_hash,
            "tools_count": len(self.tools),
            "tools": {k: v.to_dict() for k, v in self.tools.items()},
        }


# Singleton instance
_registry: Optional[ToolRegistry] = None


async def get_tool_registry(base_url: str = "http://localhost:8000") -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    
    if _registry is None:
        _registry = ToolRegistry()
        await _registry.load_from_openapi(base_url)
    
    return _registry


def get_tool_registry_sync() -> Optional[ToolRegistry]:
    """Get the current tool registry (sync version, for checking if loaded)."""
    return _registry





