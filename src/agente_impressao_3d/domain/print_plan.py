"""Immutable composition contract for a complete deterministic print plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .build_volume import BuildVolumeAnalysisResult
from .models import StlAnalysisResult
from .orientation import OrientationAnalysisResult
from .print_recommendation import PrintRecommendationResult
from .scale_and_unit import ScaleAndUnitAnalysisResult


@dataclass(frozen=True, slots=True)
class PrintPlanAnalysisResult:
    """JSON-ready envelope that preserves specialized analysis results intact."""

    stl_analysis: StlAnalysisResult
    scale_and_unit_analysis: ScaleAndUnitAnalysisResult
    build_volume_analysis: BuildVolumeAnalysisResult
    orientation_analysis: OrientationAnalysisResult
    print_recommendation_analysis: PrintRecommendationResult
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.stl_analysis.source_path, "format": "stl"},
            "analyses": {
                "stl": self.stl_analysis.to_dict(),
                "scale_and_unit": self.scale_and_unit_analysis.to_dict(),
                "build_volume": self.build_volume_analysis.to_dict(),
                "orientation": self.orientation_analysis.to_dict(),
                "print_recommendation": self.print_recommendation_analysis.to_dict(),
            },
        }
