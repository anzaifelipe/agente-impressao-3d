"""Tool adapter for updating the persistent default printer profile."""

from typing import Any

from agente_impressao_3d.application.cli_configuration import SetDefaultPrinterProfile
from agente_impressao_3d.tools.contracts import ToolDefinition


def build_tool(use_case: SetDefaultPrinterProfile) -> ToolDefinition:
    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        return use_case.execute(arguments["profile_id"]).to_dict()

    return ToolDefinition(
        name="set_default_printer_profile",
        description="Sets the persistent default printer profile after validation.",
        input_schema={
            "type": "object",
            "properties": {"profile_id": {"type": "string"}},
            "required": ["profile_id"],
            "additionalProperties": False,
        },
        handler=handler,
    )
