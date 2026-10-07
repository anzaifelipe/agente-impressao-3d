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
from agente_impressao_3d.domain.surface_quality import SurfaceQualityConfiguration
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
        surface_quality = SurfaceQualityConfiguration(
            nozzle_diameter=arguments.get("nozzle_diameter", 0.4),
            minimum_layer_height=arguments.get("minimum_layer_height", 0.08),
            maximum_layer_height=arguments.get("maximum_layer_height", 0.28),
            target_normal_step=arguments.get("target_normal_step", 0.075),
            target_geometric_error=arguments.get("target_geometric_error", 0.001),
            spatial_cell_size=arguments.get("spatial_cell_size", 2.0),
            maximum_spatial_cells=arguments.get("maximum_spatial_cells", 2_000_000),
            region_merge_distance=arguments.get("region_merge_distance", 4.0),
            region_merge_severity_ratio=arguments.get("region_merge_severity_ratio", 2.0),
            region_count=arguments.get("surface_region_count", 8),
            batch_size=overhang.batch_size,
            scale_and_unit=scale,
        )
        return execute_print_plan.execute(
            Path(arguments["path"]),
            get_printer_profile.execute(profile_id),
            scale,
            overhang,
            orientation,
            recommendation,
            surface_quality,
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
                "nozzle_diameter": {"type": "number"},
                "minimum_layer_height": {"type": "number"},
                "maximum_layer_height": {"type": "number"},
                "target_normal_step": {"type": "number"},
                "target_geometric_error": {"type": "number"},
                "spatial_cell_size": {"type": "number"},
                "maximum_spatial_cells": {"type": "integer"},
                "region_merge_distance": {"type": "number"},
                "region_merge_severity_ratio": {"type": "number"},
                "surface_region_count": {"type": "integer"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=handler,
    )
