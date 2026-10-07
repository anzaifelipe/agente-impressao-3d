"""Pure, deterministic contracts for FDM surface-quality analysis.

The model intentionally describes a *facet-orientation proxy*, not reconstructed
curvature.  STL triangles do not retain the CAD surface that produced them, and
the domain must not depend on a mesh-processing library to infer one.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from .models import AnalysisWarning, BoundingBox, Vector3
from .scale_and_unit import ScaleAndUnitConfiguration


@dataclass(frozen=True, slots=True)
class SurfaceQualityConfiguration:
    """Controls the reproducible layer-height policy for a nozzle/profile."""

    nozzle_diameter: float = 0.4
    minimum_layer_height: float = 0.08
    maximum_layer_height: float = 0.28
    candidate_layer_heights: tuple[float, ...] = (0.16, 0.12, 0.10, 0.08)
    target_normal_step: float = 0.075
    target_geometric_error: float = 0.001
    spatial_cell_size: float = 2.0
    maximum_spatial_cells: int = 2_000_000
    region_merge_distance: float = 4.0
    region_merge_severity_ratio: float = 2.0
    horizontal_tolerance_degrees: float = 5.0
    vertical_tolerance_degrees: float = 5.0
    region_count: int = 8
    batch_size: int = 100_000
    scale_and_unit: ScaleAndUnitConfiguration = ScaleAndUnitConfiguration()

    def __post_init__(self) -> None:
        numeric = (
            ("nozzle_diameter", self.nozzle_diameter),
            ("minimum_layer_height", self.minimum_layer_height),
            ("maximum_layer_height", self.maximum_layer_height),
            ("target_normal_step", self.target_normal_step),
            ("target_geometric_error", self.target_geometric_error),
            ("spatial_cell_size", self.spatial_cell_size),
            ("region_merge_distance", self.region_merge_distance),
            ("region_merge_severity_ratio", self.region_merge_severity_ratio),
        )
        for name, value in numeric:
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and greater than zero.")
        if self.minimum_layer_height > self.maximum_layer_height:
            raise ValueError("minimum_layer_height must not exceed maximum_layer_height.")
        if self.maximum_layer_height > self.nozzle_diameter:
            raise ValueError("maximum_layer_height must not exceed nozzle_diameter.")
        if not self.candidate_layer_heights:
            raise ValueError("candidate_layer_heights must not be empty.")
        if any(not isfinite(value) or value <= 0.0 for value in self.candidate_layer_heights):
            raise ValueError("candidate_layer_heights must be finite and greater than zero.")
        if not 0.0 <= self.horizontal_tolerance_degrees < 90.0:
            raise ValueError("horizontal_tolerance_degrees must be between 0 and 90.")
        if not 0.0 <= self.vertical_tolerance_degrees < 90.0:
            raise ValueError("vertical_tolerance_degrees must be between 0 and 90.")
        if self.region_count < 1 or self.batch_size < 1 or self.maximum_spatial_cells < 1:
            raise ValueError("region_count, batch_size and maximum_spatial_cells must be greater than zero.")

    @property
    def allowed_layer_heights(self) -> tuple[float, ...]:
        return tuple(
            height for height in self.candidate_layer_heights
            if self.minimum_layer_height <= height <= self.maximum_layer_height
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nozzle_diameter": self.nozzle_diameter,
            "minimum_layer_height": self.minimum_layer_height,
            "maximum_layer_height": self.maximum_layer_height,
            "candidate_layer_heights": list(self.candidate_layer_heights),
            "allowed_layer_heights": list(self.allowed_layer_heights),
            "target_normal_step": self.target_normal_step,
            "target_geometric_error": self.target_geometric_error,
            "spatial_cell_size": self.spatial_cell_size,
            "maximum_spatial_cells": self.maximum_spatial_cells,
            "region_merge_distance": self.region_merge_distance,
            "region_merge_severity_ratio": self.region_merge_severity_ratio,
            "horizontal_tolerance_degrees": self.horizontal_tolerance_degrees,
            "vertical_tolerance_degrees": self.vertical_tolerance_degrees,
            "region_count": self.region_count,
            "batch_size": self.batch_size,
            "scale_and_unit": self.scale_and_unit.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SurfaceQualityRegion:
    """A fixed Z-band, not a semantic or topological mesh component."""

    index: int
    z_min: float
    z_max: float
    face_count: int
    inclined_surface_area: float
    inclination_normal_z_p90: float | None
    inclination_normal_z_standard_deviation: float | None
    recommended_layer_height: float
    estimated_normal_step: float
    critical: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "z_min": self.z_min,
            "z_max": self.z_max,
            "face_count": self.face_count,
            "inclined_surface_area": self.inclined_surface_area,
            "inclination_normal_z_p90": self.inclination_normal_z_p90,
            "inclination_normal_z_standard_deviation": self.inclination_normal_z_standard_deviation,
            "recommended_layer_height": self.recommended_layer_height,
            "estimated_normal_step": self.estimated_normal_step,
            "critical": self.critical,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class CriticalSurfaceRegion:
    """A connected component of critical faces sharing at least one edge."""

    index: int
    face_count: int
    affected_surface_area: float
    bounds: BoundingBox
    inclination_normal_z_p90: float
    recommended_layer_height: float
    estimated_normal_step: float
    severity: float
    fallback_band_indices: tuple[int, ...]
    rationale: str
    risk_by_layer: tuple[tuple[float, float, float], ...] = ()
    curvature_z_proxy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "face_count": self.face_count,
            "affected_surface_area": self.affected_surface_area,
            "bounds": self.bounds.to_dict(),
            "inclination_normal_z_p90": self.inclination_normal_z_p90,
            "recommended_layer_height": self.recommended_layer_height,
            "estimated_normal_step": self.estimated_normal_step,
            "severity": self.severity,
            "fallback_band_indices": list(self.fallback_band_indices),
            "rationale": self.rationale,
            "curvature_z_proxy": self.curvature_z_proxy,
            "risk_by_layer": {
                f"risk_{height:.2f}": {"risk": risk, "estimated_geometric_error": error}
                for height, risk, error in self.risk_by_layer
            },
        }


@dataclass(frozen=True, slots=True)
class SurfaceQualityCostBenefit:
    """Layer-equivalent estimate for variable layer height over critical Z spans."""

    fine_layer_height: float | None
    model_height: float
    critical_z_height: float
    critical_z_intervals: tuple[tuple[float, float], ...]
    estimated_adaptive_layer_equivalents: float | None
    estimated_full_fine_layer_equivalents: float | None
    estimated_layer_equivalent_savings: float | None
    estimated_layer_equivalent_savings_percentage: float | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fine_layer_height": self.fine_layer_height,
            "model_height": self.model_height,
            "critical_z_height": self.critical_z_height,
            "critical_z_intervals": [
                {"z_min": lower, "z_max": upper}
                for lower, upper in self.critical_z_intervals
            ],
            "estimated_adaptive_layer_equivalents": self.estimated_adaptive_layer_equivalents,
            "estimated_full_fine_layer_equivalents": self.estimated_full_fine_layer_equivalents,
            "estimated_layer_equivalent_savings": self.estimated_layer_equivalent_savings,
            "estimated_layer_equivalent_savings_percentage": self.estimated_layer_equivalent_savings_percentage,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ConsolidatedSurfaceRegion:
    """V3.1 derived automation region made from nearby compatible V3 patches."""

    index: int
    original_patch_indices: tuple[int, ...]
    bounds: BoundingBox
    affected_surface_area: float
    severity_maximum: float
    severity_average: float
    recommended_layer_height: float
    estimated_geometric_error_maximum: float
    estimated_geometric_error_average: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "original_patch_count": len(self.original_patch_indices),
            "original_patch_indices": list(self.original_patch_indices),
            "bounds": self.bounds.to_dict(),
            "z_min": self.bounds.minimum.z,
            "z_max": self.bounds.maximum.z,
            "affected_surface_area": self.affected_surface_area,
            "severity_maximum": self.severity_maximum,
            "severity_average": self.severity_average,
            "recommended_layer_height": self.recommended_layer_height,
            "estimated_geometric_error_maximum": self.estimated_geometric_error_maximum,
            "estimated_geometric_error_average": self.estimated_geometric_error_average,
        }


@dataclass(frozen=True, slots=True)
class SurfaceQualityFacts:
    total_face_count: int
    valid_face_count: int
    inclined_face_count: int
    inclined_surface_area: float
    recommended_base_layer_height: float
    critical_region_count: int
    spatial_critical_region_count: int

    def to_dict(self) -> dict[str, int | float]:
        return {
            "total_face_count": self.total_face_count,
            "valid_face_count": self.valid_face_count,
            "inclined_face_count": self.inclined_face_count,
            "inclined_surface_area": self.inclined_surface_area,
            "recommended_base_layer_height": self.recommended_base_layer_height,
            "critical_region_count": self.critical_region_count,
            "spatial_critical_region_count": self.spatial_critical_region_count,
        }


@dataclass(frozen=True, slots=True)
class SurfaceQualityAssumptions:
    geometric_metric: str = (
        "Primary v3 metric: estimated_geometric_error = curvature_z_proxy * "
        "layer_height^2 / 8. curvature_z_proxy is inferred from area-weighted "
        "variation of normal_z within compact spatial cells; it is a local build-Z "
        "curvature proxy, not exact CAD curvature."
    )
    metric: str = (
        "For inclined facets, estimated_normal_step = layer_height * abs(normal_z). "
        "It is a layer-quantization proxy, not an exact visual-error or curvature measurement."
    )
    region_definition: str = (
        "Fallback regions are equal-height build-Z bands classified by triangle centroid; "
        "they are not semantic features or connected surface patches."
    )
    spatial_region_definition: str = (
        "Critical regions are connected components of adjacent high-severity spatial cells. "
        "Cells are grouped by proximity and compatible normal-Z characteristics; no mesh-edge map is built."
    )
    curvature_proxy: str = (
        "Within each Z band, the area-weighted standard deviation of abs(normal_z) on "
        "inclined faces is reported as an orientation-variation proxy, not curvature."
    )

    def to_dict(self) -> dict[str, str]:
        return {
            "metric": self.metric,
            "geometric_metric": self.geometric_metric,
            "region_definition": self.region_definition,
            "spatial_region_definition": self.spatial_region_definition,
            "curvature_proxy": self.curvature_proxy,
        }


@dataclass(frozen=True, slots=True)
class SurfaceQualityAnalysisResult:
    source_path: str
    configuration: SurfaceQualityConfiguration
    assumptions: SurfaceQualityAssumptions
    facts: SurfaceQualityFacts
    regions: tuple[SurfaceQualityRegion, ...]
    critical_regions: tuple[CriticalSurfaceRegion, ...] = ()
    consolidated_regions: tuple[ConsolidatedSurfaceRegion, ...] = ()
    cost_benefit: SurfaceQualityCostBenefit | None = None
    consolidated_cost_benefit: SurfaceQualityCostBenefit | None = None
    warnings: tuple[AnalysisWarning, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": {"path": self.source_path, "format": "stl"},
            "configuration": self.configuration.to_dict(),
            "assumptions": self.assumptions.to_dict(),
            "facts": self.facts.to_dict(),
            "regions": [region.to_dict() for region in self.regions],
            "critical_regions": [region.to_dict() for region in self.critical_regions],
            "consolidated_regions": [region.to_dict() for region in self.consolidated_regions],
            "cost_benefit": self.cost_benefit.to_dict() if self.cost_benefit else None,
            "consolidated_cost_benefit": self.consolidated_cost_benefit.to_dict() if self.consolidated_cost_benefit else None,
            "warnings": [warning.to_dict() for warning in self.warnings],
        }
