"""Single-step deterministic intent-to-tool orchestration."""

from dataclasses import dataclass
from typing import Any

from agente_impressao_3d.orchestration.contracts import (
    OrchestrationRequest,
    OrchestrationResult,
)
from agente_impressao_3d.tools.contracts import ToolDefinition
from agente_impressao_3d.tools.registry import execute_tool


ACTION_TO_TOOL: dict[str, str] = {
    "list_printer_profiles": "list_printer_profiles",
    "get_configuration": "get_cli_configuration",
    "set_default_printer_profile": "set_default_printer_profile",
    "analyze_model": "analyze_print_plan",
}


@dataclass(frozen=True, slots=True)
class DeterministicOrchestrator:
    """Maps exactly one declared action to exactly one Tool Layer execution."""

    tools: dict[str, ToolDefinition]

    def execute(self, request: OrchestrationRequest) -> OrchestrationResult:
        tool_name = ACTION_TO_TOOL.get(request.action)
        if tool_name is None:
            return OrchestrationResult(
                ok=False,
                action=request.action,
                error={
                    "code": "UNKNOWN_ACTION",
                    "message": f"Unknown orchestration action: {request.action}",
                },
            )

        observation = execute_tool(self.tools, tool_name, dict(request.arguments))
        if observation["ok"]:
            return OrchestrationResult(
                ok=True,
                action=request.action,
                tool=tool_name,
                result=observation["result"],
            )
        return OrchestrationResult(
            ok=False,
            action=request.action,
            tool=tool_name,
            error=observation["error"],
        )
