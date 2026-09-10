"""Domain contracts for deterministic principal-axis orientation analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sin
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .models import AnalysisWarning, Vector3
from .printer_profile import PrinterProfile
from .scale_and_unit import ScaleAndUnitConfiguration


@dataclass(frozen=True, slots=True)
class TriangleGeometryBatch:
    """Triangle vertices held only for the duration of one vectorized batch."""

    vertices: NDArray[np.float64]

    def __post_init__(self) -> None:
        if self.vertices.ndim != 3 or self.vertices.shape[1:] != (3, 3):
            raise ValueError("Triangle vertices must have shape (N, 3, 3).")

    @property
    def face_count(self) -> int:
        return int(self.vertices.shape[0])


@dataclass(frozen=True, slots=True)
class Orientation:
    """A canonical build direction and its fixed printer-axis permutation."""

    name: str
    build_direction: Vector3
    dimension_axis_order: tuple[int, int, int]

    def to_dict(self) -> dict[str, Any]:
        axis_names = ("x", "y", "z")
        return {
            "name": self.name,
            "build_direction": self.build_direction.to_dict(),
            "dimension_axis_order": [axis_names[index] for index in self.dimension_axis_order],
        }


PRINCIPAL_ORIENTATIONS: tuple[Orientation, ...] = (
    Orientation("positive_x", Vector3(1.0, 0.0, 0.0), (2, 1, 0)),
    Orientation("negative_x", Vector3(-1.0, 0.0, 0.0), (2, 1, 0)),
    Orientation("positive_y", Vector3(0.0, 1.0, 0.0), (0, 2, 1)),
    Orientation("negative_y", Vector3(0.0, -1.0, 0.0), (0, 2, 1)),
    Orientation("positive_z", Vector3(0.0, 0.0, 1.0), (0, 1, 2)),
    Orientation("negative_z", Vector3(0.0, 0.0, -1.0), (0, 1, 2)),
)


@dataclass(frozen=True, slots=True)
class OrientationAnalysisConfiguration:
    """Explicit controls for six deterministic principal-axis candidates."""

    threshold_degrees: float = 45.0
    batch_size: int = 100_000
    bed_contact_tolerance_physical: float = 0.01
    scale_and_unit: ScaleAndUnitConfiguration = field(
        default_factory=ScaleAndUnitConfiguration
    )

    def __post_init__(self) -> None:
        if not isfinite(self.threshold_degrees) or not 0.0 <= self.threshold_degrees <= 90.0:
            raise ValueError("threshold_degrees must be finite and between 0 and 90.")
        if self.batch_size < 1:
            raise ValueError("batch_size must be greater than zero.")
        if (
            not isfinite(self.bed_contact_tolerance_physical)
            or self.bed_contact_tolerance_physical < 0.0
        ):
            raise ValueError("bed_contact_tolerance_physical must be finite and non-negative.")

    @property
    def normal_dot_limit(self) -> float:
        return -sin(np.deg2rad(self.threshold_degrees))

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_degrees": self.threshold_degrees,
            "batch_size": self.batch_size,
            "bed_contact_tolerance_physical": self.bed_contact_tolerance_physical,
            "scale_and_unit": self.scale_and_unit.to_dict(),
            "orientation_convention": {
                "candidates": [orientation.to_dict() for orientation in PRINCIPAL_ORIENTATIONS],
                "build_direction_definition": "direction from build plate toward positive print Z, expressed in model coordinates",
                "overhang_condition": (
                    "dot(face_normal, build_direction) < 0 and "
                    "dot(face_normal, build_direction) <= -sin(threshold_degrees)"
                ),
                "boundary_inclusive": True,
            },
        }


@dataclass(frozen=True, slots=True)
class OrientationAnalysisAssumptions:
    """Explicit limitations of this deterministic orientation analysis."""

    model_orientation_candidates: str = "six principal axis orientations"
    automatic_arbitrary_rotation: str = "not performed"
    bed_contact_area: str = (
        "estimated from downward-facing geometry whose three vertices are within "
        "the configured tolerance of the model minimum build coordinate"
    )
    normal_orientation: str = (
        "derived from triangle winding and not automatically repaired"
    )

    def to_dict(self) -> dict[str, str]:
        return {
            "model_orientation_candidates": self.model_orientation_candidates,
            "automatic_arbitrary_rotation": self.automatic_arbitrary_rotation,
            "bed_contact_area": self.bed_contact_area,
            "normal_orientation": self.normal_orientation,
        }


@dataclass(frozen=True, slots=True)
class OrientationAnalysisFacts:
    total_face_count: int
    degenerate_face_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total_face_count": self.total_face_count,
            "degenerate_face_count": self.degenerate_face_count,
        }


@dataclass(frozen=True, slots=True)
class OrientationFacts:
    observed_dimensions: Vector3
    physical_dimensions: Vector3
    print_height: float
    fits: bool
    fits_x: bool
    fits_y: bool
    fits_z: bool
    remaining_space: Vector3
    overflow: Vector3
    total_face_count: int
    overhang_face_count: int
    total_surface_area_square_units: float
    overhang_surface_area_square_units: float
    overhang_area_percentage: float | None
    estimated_build_plate_contact_area_square_units: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_dimensions": self.observed_dimensions.to_dict(),
            "physical_dimensions": self.physical_dimensions.to_dict(),
            "print_height": self.print_height,
            "fits": self.fits,
            "fits_x": self.fits_x,
            "fits_y": self.fits_y,
            "fits_z": self.fits_z,
            "remaining_space": self.remaining_space.to_dict(),
            "overflow": self.overflow.to_dict(),
            "total_face_count": self.total_face_count,
            "overhang_face_count": self.overhang_face_count,
            "total_surface_area_square_units": self.total_surface_area_square_units,
            "overhang_surface_area_square_units": self.overhang_surface_area_square_units,
            "overhang_area_percentage": self.overhang_area_percentage,
            "estimated_build_plate_contact_area_square_units": (
                self.estimated_build_plate_contact_area_square_units
            ),
        }


@dataclass(frozen=True, slots=True)
class OrientationCandidateResult:
    orientation: Orientation
    facts: OrientationFacts
    warnings: tuple[AnalysisWarning, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "orientation": self.orientation.to_dict(),
            "facts": self.facts.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


@dataclass(frozen=True, slots=True)
class OrientationAnalysisResult:
    """JSON-ready analysis of the six fixed principal-axis orientations."""

    source_path: str
    printer_profile: PrinterProfile
    configuration: OrientationAnalysisConfiguration
    assumptions: OrientationAnalysisAssumptions
    facts: OrientationAnalysisFacts
    candidates: tuple[OrientationCandidateResult, ...]
    ordered_orientation_names: tuple[str, ...]
    recommended_orientation_name: str
    warnings: tuple[AnalysisWarning, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "printer_profile": self.printer_profile.to_dict(),
            "configuration": self.configuration.to_dict(),
            "assumptions": self.assumptions.to_dict(),
            "facts": self.facts.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "ordered_orientation_names": list(self.ordered_orientation_names),
            "recommended_orientation_name": self.recommended_orientation_name,
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
