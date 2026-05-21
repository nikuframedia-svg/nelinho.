"""
ProdPlan ONE - Copilot Tool Executor
=====================================

Enables the Copilot to call internal API tools (from the ToolRegistry)
and feed results back to the LLM for summarization.

Flow:
1. LLM receives context + user query
2. LLM outputs a tool_call JSON with tool_id and params
3. ToolExecutor validates, executes, and returns the result
4. Result is fed back to LLM for final answer synthesis

Safety:
- Max 3 tool calls per turn (prevents runaway loops)
- Only DATA_READ and ANALYSIS tools allowed by default
- Dangerous tools require explicit user confirmation
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from src.copilot.ollama_client import get_ollama_client
from src.copilot.tool_registry import ToolCategory, ToolRegistry, get_tool_registry_sync
from src.shared.config import settings

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS_PER_TURN = 3

ALLOWED_CATEGORIES = {
    ToolCategory.DATA_READ,
    ToolCategory.ANALYSIS,
    ToolCategory.SCENARIO,
}

# Prompt fragment injected when tools are available
TOOL_SYSTEM_PROMPT = """You have access to factory data tools. When the user asks about factory data
(backlog, WIP, bottlenecks, quality, schedules, inventory, KPIs), you SHOULD call a tool to get
real data instead of guessing.

To call a tool, respond with JSON:
{"tool_call": {"tool_id": "<tool_id>", "params": {<parameters>}}}

If you don't need a tool, respond with your normal answer JSON.

Available tools:
{tools_summary}
"""


class ToolExecutor:
    """
    Executes tool calls from the LLM and feeds results back.

    Usage:
        executor = ToolExecutor(registry)
        final_response, tool_log = await executor.execute_with_tools(
            user_query="qual é o backlog?",
            model=settings.model_for("tool_dispatch"),
            system_prompt="You are a factory advisor...",
            history=[...],
        )
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry_sync()

    async def execute_with_tools(
        self,
        user_query: str,
        model: str,
        system_prompt: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        format: Optional[str] = "json",
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Run the LLM with tool execution loop.

        Returns:
            (final_llm_response, tool_call_log)
        """
        tool_log: List[Dict[str, Any]] = []
        client = get_ollama_client()

        # If no registry loaded, skip tool execution
        if not self.registry or not self.registry.tools:
            response = await client.chat(
                prompt=user_query,
                model=model,
                format=format,
                history=history,
                system_prompt=system_prompt,
            )
            return response, tool_log

        # Inject tool descriptions into system prompt
        tools_summary = self.registry.get_tools_summary()
        augmented_system = system_prompt + "\n\n" + TOOL_SYSTEM_PROMPT.format(
            tools_summary=tools_summary
        )

        current_prompt = user_query
        current_history = list(history) if history else []

        # Sprint Q.12 Onda 4.5 — abort the tool loop when the LLM keeps
        # requesting the same broken thing. Without this we spent the
        # entire ``MAX_TOOL_CALLS_PER_TURN`` budget feeding the same
        # error back at the model only to watch it ask for the same
        # tool again. Track the last-seen "error fingerprint" and
        # break on repeat.
        last_error_signature: Optional[str] = None
        repeated_error_count = 0

        for iteration in range(MAX_TOOL_CALLS_PER_TURN + 1):
            response = await client.chat(
                prompt=current_prompt,
                model=model,
                format=format,
                history=current_history,
                system_prompt=augmented_system,
            )

            # Check if response contains a tool call
            tool_call = self._extract_tool_call(response)

            if tool_call is None:
                # No tool call — this is the final answer
                return response, tool_log

            if iteration >= MAX_TOOL_CALLS_PER_TURN:
                logger.warning(f"Tool call limit reached ({MAX_TOOL_CALLS_PER_TURN})")
                break

            tool_id = tool_call.get("tool_id", "")
            params = tool_call.get("params", {})

            # Validate tool exists and is allowed
            tool = self.registry.get_tool(tool_id)
            if not tool:
                logger.warning(f"LLM requested unknown tool: {tool_id}")
                tool_result = {"error": f"Tool '{tool_id}' not found"}
            elif tool.category not in ALLOWED_CATEGORIES:
                logger.warning(f"LLM requested blocked tool category: {tool.category}")
                tool_result = {"error": f"Tool '{tool_id}' not allowed (category: {tool.category.value})"}
            elif tool.is_dangerous:
                logger.warning(f"LLM requested dangerous tool: {tool_id}")
                tool_result = {"error": f"Tool '{tool_id}' requires user confirmation"}
            else:
                # Execute tool
                start = time.time()
                try:
                    tool_result = await self.registry.execute_tool(tool_id, params)
                except Exception as e:
                    logger.error(f"Tool execution failed: {tool_id}: {e}")
                    tool_result = {"error": str(e)}
                elapsed_ms = int((time.time() - start) * 1000)

                tool_log.append({
                    "iteration": iteration + 1,
                    "tool_id": tool_id,
                    "params": params,
                    "result_preview": str(tool_result)[:500],
                    "elapsed_ms": elapsed_ms,
                })

            # Sprint Q.12 Onda 4.5 — track repeated errors from the
            # same tool with the same params. Two iterations into the
            # same hole = stop digging.
            if isinstance(tool_result, dict) and "error" in tool_result:
                signature = f"{tool_id}|{json.dumps(params, sort_keys=True, default=str)}|{tool_result.get('error')}"
                if signature == last_error_signature:
                    repeated_error_count += 1
                    if repeated_error_count >= 1:
                        logger.warning(
                            "tool_executor: aborting after repeated identical "
                            "error (tool=%s, error=%s) — returning current "
                            "response instead of looping.",
                            tool_id, tool_result.get("error"),
                        )
                        return response, tool_log
                else:
                    last_error_signature = signature
                    repeated_error_count = 0

            # Feed tool result back to LLM
            result_text = json.dumps(tool_result, default=str)
            if len(result_text) > 4000:
                result_text = result_text[:4000] + "... (truncated)"

            current_history.append({"role": "assistant", "content": json.dumps({"tool_call": tool_call})})
            current_history.append({"role": "user", "content": f"Tool result for {tool_id}:\n{result_text}\n\nNow answer the original question using this data."})
            current_prompt = "Based on the tool result above, provide your final answer."

        # Fallback: return last response
        return response, tool_log

    def _extract_tool_call(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract tool_call from LLM response if present."""
        if isinstance(response, dict):
            if "tool_call" in response:
                tc = response["tool_call"]
                if isinstance(tc, dict) and "tool_id" in tc:
                    return tc

            # Check nested content
            content = response.get("content", "")
            if isinstance(content, str) and "tool_call" in content:
                try:
                    parsed = json.loads(content)
                    if "tool_call" in parsed:
                        return parsed["tool_call"]
                except (json.JSONDecodeError, TypeError):
                    pass

        return None
