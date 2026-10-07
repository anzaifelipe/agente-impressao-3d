from pathlib import Path

from agente_impressao_3d.tools.registry import (
    build_tools,
    default_tool_services,
    execute_tool,
)


def tools(tmp_path: Path):
    return build_tools(default_tool_services(tmp_path / "config.json"))


def test_tools_expose_explicit_metadata_and_minimal_schemas(tmp_path: Path) -> None:
    registry = tools(tmp_path)

    assert set(registry) == {
        "list_printer_profiles",
        "get_cli_configuration",
        "set_default_printer_profile",
        "analyze_print_plan",
        "analyze_surface_quality",
    }
    for name, tool in registry.items():
        assert tool.name == name
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.input_schema["additionalProperties"] is False
        assert callable(tool.handler)
    assert registry["analyze_print_plan"].input_schema["required"] == ["path"]


def test_lists_profiles_and_sets_then_gets_configuration(tmp_path: Path) -> None:
    registry = tools(tmp_path)

    listed = execute_tool(registry, "list_printer_profiles", {})
    updated = execute_tool(
        registry,
        "set_default_printer_profile",
        {"profile_id": "bambu-lab-a1-mini"},
    )
    retrieved = execute_tool(registry, "get_cli_configuration", {})

    assert listed == {
        "ok": True,
        "result": {
            "profiles": [
                {
                    "profile_id": "bambu-lab-a1-mini",
                    "manufacturer": "Bambu Lab",
                    "model": "A1 Mini",
                    "build_volume": {"x": 180.0, "y": 180.0, "z": 180.0},
                    "build_volume_unit": "mm",
                }
            ]
        },
    }
    assert updated["ok"] is True
    assert retrieved == {
        "ok": True,
        "result": {"schema_version": "1.0", "default_printer_profile": "bambu-lab-a1-mini"},
    }


def test_adapts_known_tool_and_application_errors(tmp_path: Path) -> None:
    registry = tools(tmp_path)

    configuration_missing = execute_tool(registry, "get_cli_configuration", {})
    assert configuration_missing == {
        "ok": False,
        "error": {
            "code": "CLI_CONFIGURATION_NOT_FOUND",
            "message": (
                "CLI configuration was not found. Run "
                "'agente-impressao-3d config init'."
            ),
        },
    }
    assert execute_tool(registry, "missing", {}) == {
        "ok": False,
        "error": {"code": "TOOL_NOT_FOUND", "message": "tool not found: missing"},
    }
    assert execute_tool(registry, "set_default_printer_profile", {}) == {
        "ok": False,
        "error": {"code": "INVALID_TOOL_ARGUMENTS", "message": "missing required argument: profile_id"},
    }
    assert execute_tool(
        registry, "list_printer_profiles", {"ignored": True}
    ) == {
        "ok": False,
        "error": {"code": "INVALID_TOOL_ARGUMENTS", "message": "unexpected argument: ignored"},
    }
    unknown = execute_tool(
        registry, "set_default_printer_profile", {"profile_id": "missing"}
    )
    assert unknown["ok"] is False
    assert unknown["error"]["code"] == "UNKNOWN_PRINTER_PROFILE"


def test_analyzes_existing_fixture_through_application_pipeline(tmp_path: Path) -> None:
    registry = tools(tmp_path)
    fixture = Path("tests/fixtures/cube_ascii.stl")

    result = execute_tool(
        registry,
        "analyze_print_plan",
        {
            "path": str(fixture),
            "printer_profile": "bambu-lab-a1-mini",
            "scale_factor": 1.0,
            "physical_unit": "mm",
            "overhang_threshold": 45.0,
            "batch_size": 10,
            "max_recommended_overhang": 25.0,
        },
    )

    assert result["ok"] is True
    assert result["result"]["source"]["path"] == str(fixture)
    assert set(result["result"]["analyses"]) == {
        "stl", "scale_and_unit", "build_volume", "overhang", "orientation",
        "print_recommendation",
        "surface_quality",
    }


def test_analyzes_surface_quality_with_nozzle_limits(tmp_path: Path) -> None:
    result = execute_tool(
        tools(tmp_path), "analyze_surface_quality", {
            "path": "tests/fixtures/cube_ascii.stl", "minimum_layer_height": 0.10,
            "maximum_layer_height": 0.16, "batch_size": 10,
        }
    )

    assert result["ok"] is True
    assert result["result"]["configuration"]["allowed_layer_heights"] == [0.16, 0.12, 0.1]
