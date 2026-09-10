"""Pure contracts for deterministic overhang analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import sin
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .models import AnalysisWarning, Vector3


@dataclass(frozen=True, slots=True)
class FaceMetricsBatch:
    """Vectorized per-face measurements, held only for one processing batch."""

    normal_z: NDArray[np.float64]
    area: NDArray[np.float64]

    def __post_init__(self) -> None:
        if self.normal_z.ndim != 1 or self.area.ndim != 1:
            raise ValueError("Face metric arrays must be one-dimensional.")
        if self.normal_z.shape != self.area.shape:
            raise ValueError("Face metric arrays must have matching shapes.")

    @property
    def face_count(self) -> int:
        return int(self.normal_z.size)


@dataclass(frozen=True, slots=True)
class OverhangAnalysisConfiguration:
    """Explicit, fixed-frame configuration for overhang classification."""

    threshold_degrees: float = 45.0
    batch_size: int = 100_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold_degrees <= 90.0:
            raise ValueError("threshold_degrees must be between 0 and 90.")
        if self.batch_size < 1:
            raise ValueError("batch_size must be greater than zero.")

    @property
    def normal_z_limit(self) -> float:
        """Inclusive normal-Z threshold equivalent to the documented angle rule."""
        return -sin(np.deg2rad(self.threshold_degrees))

    def to_dict(self) -> dict[str, Any]:
        return {
            "build_direction": Vector3(0.0, 0.0, 1.0).to_dict(),
            "threshold_degrees": self.threshold_degrees,
            "batch_size": self.batch_size,
            "angle_convention": {
                "theta_definition": (
                    "acos(clamp(dot(face_normal, build_direction), -1, 1))"
                ),
                "overhang_condition": (
                    "dot(face_normal, build_direction) < 0 and "
                    "theta >= 90 degrees + threshold_degrees"
                ),
                "boundary_inclusive": True,
                "optimized_equivalent": "normal_z < 0 and normal_z <= -sin(threshold_degrees)",
            },
        }


@dataclass(frozen=True, slots=True)
class OverhangAnalysisAssumptions:
    """Interpretations not encoded by the STL format or verified in version one."""

    coordinate_unit: str = "mm"
    coordinate_unit_source: str = "application_default; STL does not formally declare units"
    model_orientation: str = "as_provided"
    face_normal_source: str = "geometric normal derived from triangle vertex winding"
    outward_normal_orientation: str = "assumed, not verified or corrected"
    topology_validation: str = "not performed by overhang analysis v1"

    def to_dict(self) -> dict[str, str]:
        return {
            "coordinate_unit": self.coordinate_unit,
            "coordinate_unit_source": self.coordinate_unit_source,
            "model_orientation": self.model_orientation,
            "face_normal_source": self.face_normal_source,
            "outward_normal_orientation": self.outward_normal_orientation,
            "topology_validation": self.topology_validation,
        }


@dataclass(frozen=True, slots=True)
class OverhangFacts:
    total_face_count: int
    overhang_face_count: int
    total_surface_area_square_units: float
    overhang_surface_area_square_units: float
    overhang_area_percentage: float | None

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            "total_face_count": self.total_face_count,
            "overhang_face_count": self.overhang_face_count,
            "total_surface_area_square_units": self.total_surface_area_square_units,
            "overhang_surface_area_square_units": self.overhang_surface_area_square_units,
            "overhang_area_percentage": self.overhang_area_percentage,
        }


@dataclass(frozen=True, slots=True)
class OverhangAnalysisResult:
    """Compact, JSON-ready result for future API or agent-tool use."""

    source_path: str
    facts: OverhangFacts
    configuration: OverhangAnalysisConfiguration
    assumptions: OverhangAnalysisAssumptions
    warnings: tuple[AnalysisWarning, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "facts": self.facts.to_dict(),
            "configuration": self.configuration.to_dict(),
            "assumptions": self.assumptions.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
