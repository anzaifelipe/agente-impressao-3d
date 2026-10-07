"""Structured adapter for the standalone deterministic surface-quality capability."""

from pathlib import Path
from typing import Any

from agente_impressao_3d.application.analyze_surface_quality import AnalyzeSurfaceQuality
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration
from agente_impressao_3d.domain.surface_quality import SurfaceQualityConfiguration
from agente_impressao_3d.tools.contracts import ToolDefinition


def build_tool(analyzer: AnalyzeSurfaceQuality) -> ToolDefinition:
    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        config = SurfaceQualityConfiguration(
            nozzle_diameter=arguments.get("nozzle_diameter", 0.4),
            minimum_layer_height=arguments.get("minimum_layer_height", 0.08),
            maximum_layer_height=arguments.get("maximum_layer_height", 0.28),
            target_normal_step=arguments.get("target_normal_step", 0.075),
            target_geometric_error=arguments.get("target_geometric_error", 0.001),
            spatial_cell_size=arguments.get("spatial_cell_size", 2.0),
            maximum_spatial_cells=arguments.get("maximum_spatial_cells", 2_000_000),
            region_merge_distance=arguments.get("region_merge_distance", 4.0),
            region_merge_severity_ratio=arguments.get("region_merge_severity_ratio", 2.0),
            region_count=arguments.get("region_count", 8),
            batch_size=arguments.get("batch_size", 100_000),
            scale_and_unit=ScaleAndUnitConfiguration(
                scale_factor=arguments.get("scale_factor", 1.0),
                physical_unit=arguments.get("physical_unit", "mm"),
            ),
        )
        return analyzer.execute(Path(arguments["path"]), config).to_dict()

    return ToolDefinition(
        name="analyze_surface_quality",
        description="Analyzes FDM stair-stepping risk using deterministic triangle-orientation proxies.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"}, "nozzle_diameter": {"type": "number"},
                "minimum_layer_height": {"type": "number"}, "maximum_layer_height": {"type": "number"},
                "target_normal_step": {"type": "number"}, "region_count": {"type": "integer"},
                "target_geometric_error": {"type": "number"}, "spatial_cell_size": {"type": "number"},
                "maximum_spatial_cells": {"type": "integer"},
                "region_merge_distance": {"type": "number"}, "region_merge_severity_ratio": {"type": "number"},
                "batch_size": {"type": "integer"}, "scale_factor": {"type": "number"},
                "physical_unit": {"type": "string"},
            },
            "required": ["path"], "additionalProperties": False,
        }, handler=handler,
    )
