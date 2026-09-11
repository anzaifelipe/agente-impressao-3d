"""Compact immutable contracts for presenting an existing print plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Vector3


@dataclass(frozen=True, slots=True)
class PrintPlanSummaryFacts:
    """Important facts extracted from precomputed print-plan analyses."""

    physical_dimensions: Vector3
    physical_unit: str
    fits_build_volume: bool | None
    recommended_orientation: str | None
    print_height: float | None
    overhang_area_percentage: float | None
    recommendation_status: str
    warning_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "physical_dimensions": self.physical_dimensions.to_dict(),
            "physical_unit": self.physical_unit,
            "fits_build_volume": self.fits_build_volume,
            "recommended_orientation": self.recommended_orientation,
            "print_height": self.print_height,
            "overhang_area_percentage": self.overhang_area_percentage,
            "recommendation_status": self.recommendation_status,
            "warning_count": self.warning_count,
        }


@dataclass(frozen=True, slots=True)
class PrintPlanSummaryWarning:
    """An existing warning together with its explicit producing analysis."""

    code: str
    message: str
    severity: str
    origin: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "origin": self.origin,
        }


@dataclass(frozen=True, slots=True)
class PrintPlanSummaryResult:
    """JSON-friendly presentation model; it does not replace the print plan."""

    source_path: str
    facts: PrintPlanSummaryFacts
    warnings: tuple[PrintPlanSummaryWarning, ...]
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "facts": self.facts.to_dict(),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
