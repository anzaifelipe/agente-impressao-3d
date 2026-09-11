"""Explicit registry and executor for the first deterministic tool layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agente_impressao_3d.application.analyze_build_volume import AnalyzeBuildVolume
from agente_impressao_3d.application.analyze_orientation import AnalyzeOrientation
from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.application.analyze_print_plan import AnalyzePrintPlan
from agente_impressao_3d.application.analyze_print_recommendation import AnalyzePrintRecommendation
from agente_impressao_3d.application.analyze_scale_and_unit import AnalyzeScaleAndUnit
from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.application.cli_configuration import (
    CliConfigurationNotFoundError,
    GetCliConfiguration,
    SetDefaultPrinterProfile,
    UnknownDefaultPrinterProfileError,
)
from agente_impressao_3d.application.execute_print_plan_analysis import ExecutePrintPlanAnalysis
from agente_impressao_3d.application.get_printer_profile import (
    GetPrinterProfile,
    UnknownPrinterProfileError,
)
from agente_impressao_3d.application.list_printer_profiles import ListPrinterProfiles
from agente_impressao_3d.infrastructure.built_in_printer_profiles import BuiltInPrinterProfileReader
from agente_impressao_3d.infrastructure.json_cli_configuration_store import (
    JsonCliConfigurationStore,
    default_cli_configuration_path,
)
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import TrimeshFaceMetricsReader
from agente_impressao_3d.infrastructure.trimesh_inspector import TrimeshMeshInspector
from agente_impressao_3d.infrastructure.trimesh_triangle_geometry_reader import TrimeshTriangleGeometryReader
from agente_impressao_3d.tools.analyze_print_plan import build_tool as analyze_print_plan_tool
from agente_impressao_3d.tools.contracts import ToolDefinition
from agente_impressao_3d.tools.get_cli_configuration import build_tool as get_configuration_tool
from agente_impressao_3d.tools.list_printer_profiles import build_tool as list_profiles_tool
from agente_impressao_3d.tools.set_default_printer_profile import build_tool as set_default_tool


@dataclass(frozen=True, slots=True)
class ToolServices:
    list_printer_profiles: ListPrinterProfiles
    get_cli_configuration: GetCliConfiguration
    set_default_printer_profile: SetDefaultPrinterProfile
    get_printer_profile: GetPrinterProfile
    execute_print_plan_analysis: ExecutePrintPlanAnalysis


def default_tool_services(
    configuration_path: Path | None = None,
) -> ToolServices:
    """Compose real application use cases without involving the CLI adapter."""
    profile_reader = BuiltInPrinterProfileReader()
    store = JsonCliConfigurationStore(configuration_path or default_cli_configuration_path())
    return ToolServices(
        list_printer_profiles=ListPrinterProfiles(profile_reader),
        get_cli_configuration=GetCliConfiguration(store),
        set_default_printer_profile=SetDefaultPrinterProfile(store, profile_reader),
        get_printer_profile=GetPrinterProfile(profile_reader),
        execute_print_plan_analysis=ExecutePrintPlanAnalysis(
            AnalyzeStl(TrimeshMeshInspector()),
            AnalyzeScaleAndUnit(),
            AnalyzeBuildVolume(),
            AnalyzeOverhang(TrimeshFaceMetricsReader()),
            AnalyzeOrientation(TrimeshTriangleGeometryReader()),
            AnalyzePrintRecommendation(),
            AnalyzePrintPlan(),
        ),
    )


def build_tools(services: ToolServices) -> dict[str, ToolDefinition]:
    """Return the small, static set of agent-facing tools."""
    definitions = (
        list_profiles_tool(services.list_printer_profiles),
        get_configuration_tool(services.get_cli_configuration),
        set_default_tool(services.set_default_printer_profile),
        analyze_print_plan_tool(
            services.execute_print_plan_analysis,
            services.get_printer_profile,
            services.get_cli_configuration,
        ),
    )
    return {definition.name: definition for definition in definitions}


def execute_tool(
    tools: dict[str, ToolDefinition], name: str, arguments: object
) -> dict[str, Any]:
    """Execute one named tool with minimal schema validation and typed errors."""
    definition = tools.get(name)
    if definition is None:
        return _error("TOOL_NOT_FOUND", f"tool not found: {name}")
    validation_error = _validate_arguments(definition.input_schema, arguments)
    if validation_error is not None:
        return _error("INVALID_TOOL_ARGUMENTS", validation_error)
    try:
        return {"ok": True, "result": definition.handler(arguments)}
    except (UnknownPrinterProfileError, UnknownDefaultPrinterProfileError) as error:
        return _error("UNKNOWN_PRINTER_PROFILE", str(error))
    except CliConfigurationNotFoundError as error:
        return _error("CLI_CONFIGURATION_NOT_FOUND", str(error))
    except OSError as error:
        return _error("STL_FILE_ERROR", str(error))
    except ValueError as error:
        return _error("APPLICATION_ERROR", str(error))


def _validate_arguments(schema: dict[str, Any], arguments: object) -> str | None:
    if not isinstance(arguments, dict):
        return "tool arguments must be an object"
    properties = schema["properties"]
    for name in schema["required"]:
        if name not in arguments:
            return f"missing required argument: {name}"
    if schema.get("additionalProperties") is False:
        unexpected = set(arguments) - set(properties)
        if unexpected:
            return f"unexpected argument: {sorted(unexpected)[0]}"
    for name, value in arguments.items():
        expected_type = properties[name]["type"]
        if not _matches_type(value, expected_type):
            return f"argument '{name}' must be a {expected_type}"
    return None


def _matches_type(value: object, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}
