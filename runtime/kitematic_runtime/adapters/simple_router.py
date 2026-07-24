"""SimpleIntentRouter — maps Intent → ExecutionPath via ToolRegistry.

Uses ToolRegistry pattern matching to find the appropriate tool for an intent.
Deterministic: raises OrchestrationError on ambiguity or no match.
"""

from __future__ import annotations

from runtime.kitematic_runtime.exceptions import OrchestrationError
from runtime.kitematic_runtime.runtime import ExecutionPath, Intent, IntentRouter
from runtime.kitematic_runtime.tool_registry import ToolRegistry


class SimpleIntentRouter(IntentRouter):
    """Concrete adapter: ABI IntentRouter → ToolRegistry.

    Translates:
      - route_intent(Intent) → ExecutionPath(tool, adapter, parameters)

    Strategy:
      - Match intent.action against registered tools via ToolRegistry
      - Exact match preferred over pattern match
      - Ambiguity or no match raises OrchestrationError
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry

    async def route_intent(self, intent: Intent) -> ExecutionPath:
        """Route an intent to the correct execution path.

        Raises OrchestrationError if:
          - No tool matches the intent action
          - Multiple tools match with ambiguity
        """
        # 1. Try exact tool_id match first
        exact = self._registry.get(intent.action)
        if exact is not None:
            return ExecutionPath(
                tool=exact.tool_id,
                adapter=exact.mcp_server,
                parameters=intent.parameters,
            )

        # 2. Try pattern match
        matches = self._registry.match_pattern(intent.action)

        if len(matches) == 0:
            raise OrchestrationError(
                f"No tool found for action '{intent.action}'"
            )

        if len(matches) > 1:
            tool_ids = [t.tool_id for t in matches]
            raise OrchestrationError(
                f"Ambiguous action '{intent.action}' matches multiple tools: {tool_ids}"
            )

        # 3. Single match
        tool = matches[0]
        return ExecutionPath(
            tool=tool.tool_id,
            adapter=tool.mcp_server,
            parameters=intent.parameters,
        )
