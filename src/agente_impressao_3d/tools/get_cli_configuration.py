"""Tool adapter for retrieving the persistent CLI configuration."""

from typing import Any

from agente_impressao_3d.application.cli_configuration import GetCliConfiguration
from agente_impressao_3d.tools.contracts import ToolDefinition


def build_tool(use_case: GetCliConfiguration) -> ToolDefinition:
    def handler(_: dict[str, Any]) -> dict[str, Any]:
        return use_case.execute().to_dict()

    return ToolDefinition(
        name="get_cli_configuration",
        description="Gets the current persistent CLI configuration.",
        input_schema={
            "type": "object", "properties": {}, "required": [],
            "additionalProperties": False,
        },
        handler=handler,
    )
