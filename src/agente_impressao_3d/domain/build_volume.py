"""Pure domain contracts for current-orientation build-volume analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import AnalysisWarning, Vector3
from .printer_profile import PrinterProfile


@dataclass(frozen=True, slots=True)
class BuildVolumeAnalysisAssumptions:
    """Declared limits of the initial build-volume analysis."""

    model_orientation: str = "as_provided"
    automatic_rotation: str = "not performed"
    comparison_method: str = "axis-aligned physical dimensions compared to build volume"

    def to_dict(self) -> dict[str, str]:
        return {
            "model_orientation": self.model_orientation,
            "automatic_rotation": self.automatic_rotation,
            "comparison_method": self.comparison_method,
        }


@dataclass(frozen=True, slots=True)
class BuildVolumeFacts:
    """Per-axis fit facts derived from already interpreted physical dimensions."""

    physical_dimensions: Vector3
    fits: bool
    fits_x: bool
    fits_y: bool
    fits_z: bool
    remaining_space: Vector3
    overflow: Vector3

    def to_dict(self) -> dict[str, Any]:
        return {
            "physical_dimensions": self.physical_dimensions.to_dict(),
            "fits": self.fits,
            "fits_x": self.fits_x,
            "fits_y": self.fits_y,
            "fits_z": self.fits_z,
            "remaining_space": self.remaining_space.to_dict(),
            "overflow": self.overflow.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BuildVolumeAnalysisResult:
    """JSON-ready result of comparing a part against a printer profile."""

    source_path: str
    printer_profile: PrinterProfile
    facts: BuildVolumeFacts
    assumptions: BuildVolumeAnalysisAssumptions
    warnings: tuple[AnalysisWarning, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "printer_profile": self.printer_profile.to_dict(),
            "facts": self.facts.to_dict(),
            "assumptions": self.assumptions.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
