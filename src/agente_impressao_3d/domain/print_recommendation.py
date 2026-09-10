"""Pure, explainable contracts for deterministic print recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Any

from .models import AnalysisWarning
from .orientation import OrientationCandidateResult


class PrintRecommendationStatus(StrEnum):
    RECOMMENDED = "recommended"
    PRINTABLE_WITH_WARNINGS = "printable_with_warnings"
    NOT_RECOMMENDED = "not_recommended"
    NOT_FIT = "not_fit"


class RecommendationReasonCode(StrEnum):
    MODEL_FITS_BUILD_VOLUME = "model_fits_build_volume"
    MODEL_DOES_NOT_FIT_BUILD_VOLUME = "model_does_not_fit_build_volume"
    BEST_ORIENTATION_SELECTED = "best_orientation_selected"
    OVERHANG_EXCEEDS_RECOMMENDED_THRESHOLD = (
        "overhang_exceeds_recommended_threshold"
    )
    EMPTY_MESH = "empty_mesh"
    NO_VALID_ORIENTATION = "no_valid_orientation"
    ZERO_TOTAL_SURFACE_AREA = "zero_total_surface_area"


@dataclass(frozen=True, slots=True)
class PrintRecommendationConfiguration:
    """Explicit policies applied to already computed deterministic facts."""

    maximum_recommended_overhang_area_percentage: float | None = None

    def __post_init__(self) -> None:
        value = self.maximum_recommended_overhang_area_percentage
        if value is not None and (
            not isfinite(value) or not 0.0 <= value <= 100.0
        ):
            raise ValueError(
                "maximum_recommended_overhang_area_percentage must be finite and between 0 and 100."
            )

    def to_dict(self) -> dict[str, float | None]:
        return {
            "maximum_recommended_overhang_area_percentage": (
                self.maximum_recommended_overhang_area_percentage
            )
        }


@dataclass(frozen=True, slots=True)
class RecommendationReason:
    code: RecommendationReasonCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class RecommendationWarning:
    """An existing analysis warning plus its source result."""

    origin: str
    warning: AnalysisWarning

    def to_dict(self) -> dict[str, str]:
        return {"origin": self.origin, **self.warning.to_dict()}


@dataclass(frozen=True, slots=True)
class PrintRecommendationResult:
    """JSON-ready decision that does not recalculate any geometric facts."""

    source_path: str
    status: PrintRecommendationStatus
    configuration: PrintRecommendationConfiguration
    recommended_candidate: OrientationCandidateResult | None
    reasons: tuple[RecommendationReason, ...]
    warnings: tuple[RecommendationWarning, ...]
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        candidate = self.recommended_candidate
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "status": self.status.value,
            "recommended_orientation": candidate.orientation.name if candidate else None,
            "recommended_candidate": candidate.to_dict() if candidate else None,
            "configuration": self.configuration.to_dict(),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
