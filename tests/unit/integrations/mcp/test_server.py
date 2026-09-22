import asyncio
from pathlib import Path

import agente_impressao_3d.integrations.mcp.server as mcp_server
from agente_impressao_3d.tools.registry import (
    build_tools,
    default_tool_services,
    execute_tool,
)


def registry(tmp_path: Path):
    return build_tools(default_tool_services(tmp_path / "config.json"))


def test_exposes_only_get_cli_configuration_with_the_tool_layer_schema(
    tmp_path: Path,
) -> None:
    tools = registry(tmp_path)
    server = mcp_server.create_server(default_tool_services(tmp_path / "config.json"))

    exposed = asyncio.run(server.list_tools())

    assert [tool.name for tool in exposed] == ["get_cli_configuration"]
    assert exposed[0].input_schema == tools["get_cli_configuration"].input_schema
    assert exposed[0].input_schema == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def test_forwards_empty_arguments_to_the_existing_tool_layer(
    tmp_path: Path, monkeypatch
) -> None:
    tools = registry(tmp_path)
    execute_tool(
        tools,
        "set_default_printer_profile",
        {"profile_id": "bambu-lab-a1-mini"},
    )
    server = mcp_server.create_server(default_tool_services(tmp_path / "config.json"))
    calls: list[tuple[object, str, object]] = []
    original_execute_tool = mcp_server.execute_tool

    def spy(received_tools, name: str, arguments: object):
        calls.append((received_tools, name, arguments))
        return original_execute_tool(received_tools, name, arguments)

    monkeypatch.setattr(mcp_server, "execute_tool", spy)

    result = asyncio.run(server.call_tool("get_cli_configuration", {}))

    assert calls[0][1:] == ("get_cli_configuration", {})
    assert result.structured_content == {
        "ok": True,
        "result": {
            "schema_version": "1.0",
            "default_printer_profile": "bambu-lab-a1-mini",
        },
    }


def test_unexpected_arguments_reach_tool_layer_instead_of_being_discarded(
    tmp_path: Path,
) -> None:
    server = mcp_server.create_server(
        default_tool_services(tmp_path / "config.json")
    )

    result = asyncio.run(server.call_tool("get_cli_configuration", {"ignored": True}))

    assert result.structured_content == {
        "ok": False,
        "error": {
            "code": "INVALID_TOOL_ARGUMENTS",
            "message": "unexpected argument: ignored",
        },
    }


def test_preserves_tool_layer_configuration_error(tmp_path: Path) -> None:
    server = mcp_server.create_server(
        default_tool_services(tmp_path / "config.json")
    )

    result = asyncio.run(server.call_tool("get_cli_configuration", {}))

    assert result.structured_content == {
        "ok": False,
        "error": {
            "code": "CLI_CONFIGURATION_NOT_FOUND",
            "message": (
                "CLI configuration was not found. Run "
                "'agente-impressao-3d config init'."
            ),
        },
    }


def test_stdio_transport_dispatches_without_starting_a_permanent_server(
    tmp_path: Path, monkeypatch
) -> None:
    server = mcp_server.create_server(
        default_tool_services(tmp_path / "config.json")
    )
    started = False

    async def run_stdio_async() -> None:
        nonlocal started
        started = True

    monkeypatch.setattr(server, "run_stdio_async", run_stdio_async)

    server.run(transport="stdio")

    assert started is True
