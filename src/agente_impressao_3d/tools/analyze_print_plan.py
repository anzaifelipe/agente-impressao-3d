"""Structured tool adapter for the complete deterministic Print Plan pipeline."""

from pathlib import Path
from typing import Any

from agente_impressao_3d.application.cli_configuration import GetCliConfiguration
from agente_impressao_3d.application.execute_print_plan_analysis import (
    ExecutePrintPlanAnalysis,
)
from agente_impressao_3d.application.get_printer_profile import GetPrinterProfile
from agente_impressao_3d.domain.orientation import OrientationAnalysisConfiguration
from agente_impressao_3d.domain.overhang import OverhangAnalysisConfiguration
from agente_impressao_3d.domain.print_recommendation import PrintRecommendationConfiguration
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration
from agente_impressao_3d.tools.contracts import ToolDefinition


def build_tool(
    execute_print_plan: ExecutePrintPlanAnalysis,
    get_printer_profile: GetPrinterProfile,
    get_cli_configuration: GetCliConfiguration,
) -> ToolDefinition:
    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        scale = ScaleAndUnitConfiguration(
            scale_factor=arguments.get("scale_factor", 1.0),
            physical_unit=arguments.get("physical_unit", "mm"),
        )
        overhang = OverhangAnalysisConfiguration(
            threshold_degrees=arguments.get("overhang_threshold", 45.0),
            batch_size=arguments.get("batch_size", 100_000),
        )
        profile_id = arguments.get("printer_profile")
        if profile_id is None:
            profile_id = get_cli_configuration.execute().default_printer_profile
        if profile_id is None:
            raise ValueError("no default printer profile is configured")
        orientation = OrientationAnalysisConfiguration(
            threshold_degrees=overhang.threshold_degrees,
            batch_size=overhang.batch_size,
            scale_and_unit=scale,
        )
        recommendation = PrintRecommendationConfiguration(
            maximum_recommended_overhang_area_percentage=arguments.get(
                "max_recommended_overhang"
            )
        )
        return execute_print_plan.execute(
            Path(arguments["path"]),
            get_printer_profile.execute(profile_id),
            scale,
            overhang,
            orientation,
            recommendation,
        ).to_dict()

    return ToolDefinition(
        name="analyze_print_plan",
        description="Runs the complete deterministic STL print-plan analysis.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "printer_profile": {"type": "string"},
                "scale_factor": {"type": "number"},
                "physical_unit": {"type": "string"},
                "overhang_threshold": {"type": "number"},
                "batch_size": {"type": "integer"},
                "max_recommended_overhang": {"type": "number"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=handler,
    )
