"""Domain contracts for consolidated deterministic printability analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .build_volume import BuildVolumeAnalysisResult
from .models import StlAnalysisResult
from .overhang import OverhangAnalysisConfiguration, OverhangAnalysisResult
from .scale_and_unit import ScaleAndUnitAnalysisResult, ScaleAndUnitConfiguration


@dataclass(frozen=True, slots=True)
class PrintabilityAnalysisConfiguration:
    """Configuration forwarded to the specialized analysis capabilities."""

    scale_and_unit: ScaleAndUnitConfiguration = field(
        default_factory=ScaleAndUnitConfiguration
    )
    overhang: OverhangAnalysisConfiguration = field(
        default_factory=OverhangAnalysisConfiguration
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_and_unit": self.scale_and_unit.to_dict(),
            "overhang": self.overhang.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PrintabilityAnalysisResult:
    """JSON-ready composition of specialized deterministic analysis results."""

    source_path: str
    configuration: PrintabilityAnalysisConfiguration
    stl_analysis: StlAnalysisResult
    scale_and_unit_analysis: ScaleAndUnitAnalysisResult
    build_volume_analysis: BuildVolumeAnalysisResult
    overhang_analysis: OverhangAnalysisResult
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "configuration": self.configuration.to_dict(),
            "analyses": {
                "stl": self.stl_analysis.to_dict(),
                "scale_and_unit": self.scale_and_unit_analysis.to_dict(),
                "build_volume": self.build_volume_analysis.to_dict(),
                "overhang": self.overhang_analysis.to_dict(),
            },
        }
