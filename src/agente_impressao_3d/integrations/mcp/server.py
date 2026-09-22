"""Minimal MCP exposure of selected existing Tool Layer operations."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata

from agente_impressao_3d.tools.contracts import ToolDefinition
from agente_impressao_3d.tools.registry import (
    ToolServices,
    build_tools,
    default_tool_services,
    execute_tool,
)


TOOL_NAME = "get_cli_configuration"


class _ForwardingFuncMetadata(FuncMetadata):
    """Keep MCP call arguments intact until the Tool Layer validates them."""

    def validate_arguments(self, arguments_to_validate: dict[str, Any]) -> dict[str, Any]:
        return arguments_to_validate


def create_server(
    services: ToolServices | None = None,
    *,
    configuration_path: Path | None = None,
) -> MCPServer:
    """Create the one-tool MCP adapter backed by the existing Tool Layer."""
    tools = build_tools(services or default_tool_services(configuration_path))
    definition = tools[TOOL_NAME]
    server = MCPServer("agente-impressao-3d")

    @server.tool(name=definition.name, description=definition.description)
    def get_cli_configuration(**arguments: Any) -> dict[str, Any]:
        return execute_tool(tools, TOOL_NAME, arguments)

    _publish_tool_layer_schema(server, definition)
    return server


def run_stdio() -> None:
    """Run the minimal MCP server over stdio."""
    create_server().run(transport="stdio")


def _publish_tool_layer_schema(server: MCPServer, definition: ToolDefinition) -> None:
    """Publish the Tool Layer schema without letting MCP discard extra arguments.

    MCP 2.2 derives a ``**arguments`` parameter as a named field and a no-argument
    function silently drops unknown properties. Replacing the private registration
    metadata keeps raw properties available to the handler, where ``execute_tool``
    performs the project's existing validation, while exposing the exact Tool Layer
    schema to MCP clients.
    """
    tool = server._tool_manager._tools[definition.name]
    tool.parameters = deepcopy(definition.input_schema)
    tool.fn_metadata = _ForwardingFuncMetadata(
        arg_model=tool.fn_metadata.arg_model,
        output_schema=tool.fn_metadata.output_schema,
        output_model=tool.fn_metadata.output_model,
        wrap_output=tool.fn_metadata.wrap_output,
    )
