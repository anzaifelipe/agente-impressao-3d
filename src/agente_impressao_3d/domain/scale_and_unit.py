"""Pure domain contracts for explicit STL scale and unit interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .models import Vector3


@dataclass(frozen=True, slots=True)
class ScaleAndUnitConfiguration:
    """Caller-provided interpretation of model-coordinate dimensions."""

    scale_factor: float = 1.0
    physical_unit: str = "mm"

    def __post_init__(self) -> None:
        if not isfinite(self.scale_factor) or self.scale_factor <= 0.0:
            raise ValueError("scale_factor must be finite and greater than zero.")
        if not self.physical_unit.strip():
            raise ValueError("physical_unit must not be empty.")

    def to_dict(self) -> dict[str, float | str]:
        return {
            "scale_factor": self.scale_factor,
            "physical_unit": self.physical_unit,
        }


@dataclass(frozen=True, slots=True)
class ScaleAndUnitFacts:
    """Observed model dimensions and their explicitly scaled interpretation."""

    observed_dimensions: Vector3
    physical_dimensions: Vector3

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "observed_dimensions": self.observed_dimensions.to_dict(),
            "physical_dimensions": self.physical_dimensions.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ScaleAndUnitAnalysisResult:
    """JSON-ready result of applying a declared scale and physical unit."""

    source_path: str
    facts: ScaleAndUnitFacts
    configuration: ScaleAndUnitConfiguration
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "facts": self.facts.to_dict(),
            "configuration": self.configuration.to_dict(),
        }
