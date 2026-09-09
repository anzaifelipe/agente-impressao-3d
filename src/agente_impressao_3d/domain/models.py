"""Domain data models with no dependency on geometry libraries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WarningSeverity(StrEnum):
    """Severity assigned to a non-fatal analysis finding."""

    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Vector3:
    """A three-dimensional coordinate or measurement."""

    x: float
    y: float
    z: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounding box expressed in the STL coordinate space."""

    minimum: Vector3
    maximum: Vector3

    @property
    def dimensions(self) -> Vector3:
        return Vector3(
            x=self.maximum.x - self.minimum.x,
            y=self.maximum.y - self.minimum.y,
            z=self.maximum.z - self.minimum.z,
        )

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "minimum": self.minimum.to_dict(),
            "maximum": self.maximum.to_dict(),
            "dimensions": self.dimensions.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Volume:
    """Volume and whether it is reliable for the analyzed mesh."""

    cubic_units: float | None
    reliable: bool

    def __post_init__(self) -> None:
        if self.reliable != (self.cubic_units is not None):
            raise ValueError("A reliable volume must have a value, and vice versa.")

    def to_dict(self) -> dict[str, float | bool | None]:
        return {"cubic_units": self.cubic_units, "reliable": self.reliable}


@dataclass(frozen=True, slots=True)
class GeometryFacts:
    """Measurements derived directly from mesh geometry."""

    triangle_count: int
    bounding_box: BoundingBox
    watertight: bool
    volume: Volume

    def to_dict(self) -> dict[str, Any]:
        return {
            "triangle_count": self.triangle_count,
            "bounding_box": self.bounding_box.to_dict(),
            "watertight": self.watertight,
            "volume": self.volume.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AnalysisAssumptions:
    """Interpretations required because STL itself omits this metadata."""

    coordinate_unit: str = "mm"
    coordinate_unit_source: str = "application_default; STL does not formally declare units"

    def to_dict(self) -> dict[str, str]:
        return {
            "coordinate_unit": self.coordinate_unit,
            "coordinate_unit_source": self.coordinate_unit_source,
        }


@dataclass(frozen=True, slots=True)
class AnalysisWarning:
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass(frozen=True, slots=True)
class MeshInspection:
    """Adapter output before application-level assumptions are attached."""

    facts: GeometryFacts
    warnings: tuple[AnalysisWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class StlAnalysisResult:
    """Structured contract intended for future CLI, API, and agent tools."""

    source_path: str
    facts: GeometryFacts
    assumptions: AnalysisAssumptions
    warnings: tuple[AnalysisWarning, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "facts": self.facts.to_dict(),
            "assumptions": self.assumptions.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
