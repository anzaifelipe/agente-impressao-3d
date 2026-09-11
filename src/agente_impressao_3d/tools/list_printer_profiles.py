"""Tool adapter for listing application-managed printer profiles."""

from typing import Any

from agente_impressao_3d.application.list_printer_profiles import ListPrinterProfiles
from agente_impressao_3d.tools.contracts import ToolDefinition


def build_tool(use_case: ListPrinterProfiles) -> ToolDefinition:
    def handler(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "profiles": [
                {"profile_id": entry.profile_id, **entry.profile.to_dict()}
                for entry in use_case.execute()
            ]
        }

    return ToolDefinition(
        name="list_printer_profiles",
        description="Lists the deterministic reusable printer profiles.",
        input_schema={
            "type": "object", "properties": {}, "required": [],
            "additionalProperties": False,
        },
        handler=handler,
    )
