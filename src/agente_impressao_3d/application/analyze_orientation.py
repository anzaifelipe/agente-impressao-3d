"""Deterministic six-axis orientation analysis using reusable NumPy batches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agente_impressao_3d.domain.models import AnalysisWarning, Vector3
from agente_impressao_3d.domain.orientation import (
    PRINCIPAL_ORIENTATIONS,
    OrientationAnalysisAssumptions,
    OrientationAnalysisConfiguration,
    OrientationAnalysisFacts,
    OrientationAnalysisResult,
    OrientationCandidateResult,
    OrientationFacts,
)
from agente_impressao_3d.domain.ports import TriangleGeometryReader
from agente_impressao_3d.domain.printer_profile import PrinterProfile


_DIRECTIONS = np.array(
    [
        (
            orientation.build_direction.x,
            orientation.build_direction.y,
            orientation.build_direction.z,
        )
        for orientation in PRINCIPAL_ORIENTATIONS
    ],
    dtype=np.float64,
)


@dataclass(frozen=True, slots=True)
class AnalyzeOrientation:
    """Analyzes six fixed build directions without rotating or copying the mesh."""

    triangle_geometry_reader: TriangleGeometryReader

    def execute(
        self,
        source_path: Path,
        printer_profile: PrinterProfile,
        configuration: OrientationAnalysisConfiguration | None = None,
    ) -> OrientationAnalysisResult:
        config = configuration or OrientationAnalysisConfiguration()
        if printer_profile.build_volume_unit != config.scale_and_unit.physical_unit:
            raise ValueError(
                "printer_profile.build_volume_unit must match "
                "configuration.scale_and_unit.physical_unit."
            )

        source = self.triangle_geometry_reader.open(source_path)
        total_face_count = 0
        degenerate_face_count = 0
        total_area_model = 0.0
        overhang_face_counts = np.zeros(len(PRINCIPAL_ORIENTATIONS), dtype=np.int64)
        overhang_areas_model = np.zeros(len(PRINCIPAL_ORIENTATIONS), dtype=np.float64)
        raw_minimum = np.full(3, np.inf, dtype=np.float64)
        raw_maximum = np.full(3, -np.inf, dtype=np.float64)

        for batch in source.iter_triangle_batches(config.batch_size):
            triangles = batch.vertices
            if batch.face_count == 0:
                continue
            total_face_count += batch.face_count
            raw_minimum = np.minimum(raw_minimum, np.min(triangles, axis=(0, 1)))
            raw_maximum = np.maximum(raw_maximum, np.max(triangles, axis=(0, 1)))

            cross_product, area, valid = _face_geometry(triangles)
            degenerate_face_count += batch.face_count - int(np.count_nonzero(valid))
            total_area_model += float(np.sum(area, where=valid, initial=0.0))

            normal_dots = _normal_dots(cross_product, area, valid)
            overhang = valid[:, None] & (normal_dots < 0.0) & (
                normal_dots <= config.normal_dot_limit
            )
            overhang_face_counts += np.count_nonzero(overhang, axis=0)
            overhang_areas_model += np.sum(area[:, None] * overhang, axis=0)

        raw_dimensions = (
            raw_maximum - raw_minimum if total_face_count else np.zeros(3, dtype=np.float64)
        )
        contact_areas_model = self._calculate_contact_areas(
            source,
            config,
            raw_minimum,
            raw_maximum,
            total_face_count,
        )

        warnings = _global_warnings(
            total_face_count, degenerate_face_count, total_area_model
        )
        candidates = tuple(
            _candidate_result(
                orientation_index=index,
                raw_dimensions=raw_dimensions,
                total_face_count=total_face_count,
                total_area_model=total_area_model,
                overhang_face_count=int(overhang_face_counts[index]),
                overhang_area_model=float(overhang_areas_model[index]),
                contact_area_model=float(contact_areas_model[index]),
                printer_profile=printer_profile,
                configuration=config,
            )
            for index in range(len(PRINCIPAL_ORIENTATIONS))
        )
        ordered_candidates = tuple(sorted(candidates, key=_recommendation_key))

        return OrientationAnalysisResult(
            source_path=str(source_path),
            printer_profile=printer_profile,
            configuration=config,
            assumptions=OrientationAnalysisAssumptions(),
            facts=OrientationAnalysisFacts(
                total_face_count=total_face_count,
                degenerate_face_count=degenerate_face_count,
            ),
            candidates=candidates,
            ordered_orientation_names=tuple(
                candidate.orientation.name for candidate in ordered_candidates
            ),
            recommended_orientation_name=ordered_candidates[0].orientation.name,
            warnings=tuple(warnings),
        )

    def _calculate_contact_areas(
        self,
        source: object,
        config: OrientationAnalysisConfiguration,
        raw_minimum: np.ndarray,
        raw_maximum: np.ndarray,
        total_face_count: int,
    ) -> np.ndarray:
        contact_areas = np.zeros(len(PRINCIPAL_ORIENTATIONS), dtype=np.float64)
        if total_face_count == 0:
            return contact_areas

        tolerance_model = (
            config.bed_contact_tolerance_physical / config.scale_and_unit.scale_factor
        )
        for batch in source.iter_triangle_batches(config.batch_size):
            triangles = batch.vertices
            cross_product, area, valid = _face_geometry(triangles)
            normal_dots = _normal_dots(cross_product, area, valid)
            for index, orientation in enumerate(PRINCIPAL_ORIENTATIONS):
                direction = orientation.build_direction
                axis = _axis_for_direction(direction)
                sign = _sign_for_direction(direction)
                minimum_build_coordinate = (
                    raw_minimum[axis] if sign > 0.0 else -raw_maximum[axis]
                )
                projected_vertices = triangles[:, :, axis] * sign
                at_build_plate = np.all(
                    np.abs(projected_vertices - minimum_build_coordinate)
                    <= tolerance_model,
                    axis=1,
                )
                contact = valid & (normal_dots[:, index] < 0.0) & at_build_plate
                contact_areas[index] += float(
                    np.sum(area, where=contact, initial=0.0)
                )
        return contact_areas


def _face_geometry(
    triangles: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first_edge = triangles[:, 1] - triangles[:, 0]
    second_edge = triangles[:, 2] - triangles[:, 0]
    cross_product = np.cross(first_edge, second_edge)
    doubled_area = np.sqrt(np.einsum("ij,ij->i", cross_product, cross_product))
    area = doubled_area * 0.5
    valid = np.isfinite(doubled_area) & (doubled_area > 0.0) & np.isfinite(area)
    return cross_product, area, valid


def _normal_dots(
    cross_product: np.ndarray, area: np.ndarray, valid: np.ndarray
) -> np.ndarray:
    doubled_area = area * 2.0
    normal_dots = np.full(
        (cross_product.shape[0], len(PRINCIPAL_ORIENTATIONS)), np.nan, dtype=np.float64
    )
    np.divide(
        cross_product @ _DIRECTIONS.T,
        doubled_area[:, None],
        out=normal_dots,
        where=valid[:, None],
    )
    return normal_dots


def _axis_for_direction(direction: Vector3) -> int:
    return next(
        index for index, value in enumerate((direction.x, direction.y, direction.z)) if value
    )


def _sign_for_direction(direction: Vector3) -> float:
    return next(value for value in (direction.x, direction.y, direction.z) if value)


def _candidate_result(
    *,
    orientation_index: int,
    raw_dimensions: np.ndarray,
    total_face_count: int,
    total_area_model: float,
    overhang_face_count: int,
    overhang_area_model: float,
    contact_area_model: float,
    printer_profile: PrinterProfile,
    configuration: OrientationAnalysisConfiguration,
) -> OrientationCandidateResult:
    orientation = PRINCIPAL_ORIENTATIONS[orientation_index]
    observed = raw_dimensions[list(orientation.dimension_axis_order)]
    scale_factor = configuration.scale_and_unit.scale_factor
    physical = observed * scale_factor
    dimensions = Vector3(*map(float, physical))
    build_volume = printer_profile.build_volume
    fits_x = dimensions.x <= build_volume.x
    fits_y = dimensions.y <= build_volume.y
    fits_z = dimensions.z <= build_volume.z
    fits = fits_x and fits_y and fits_z
    remaining_space = Vector3(
        max(build_volume.x - dimensions.x, 0.0),
        max(build_volume.y - dimensions.y, 0.0),
        max(build_volume.z - dimensions.z, 0.0),
    )
    overflow = Vector3(
        max(dimensions.x - build_volume.x, 0.0),
        max(dimensions.y - build_volume.y, 0.0),
        max(dimensions.z - build_volume.z, 0.0),
    )
    area_scale = scale_factor**2
    total_area = total_area_model * area_scale
    overhang_area = overhang_area_model * area_scale
    warnings: list[AnalysisWarning] = []
    if not fits:
        axes = ", ".join(
            axis
            for axis, axis_fits in (("X", fits_x), ("Y", fits_y), ("Z", fits_z))
            if not axis_fits
        )
        warnings.append(
            AnalysisWarning(
                code="MODEL_EXCEEDS_BUILD_VOLUME",
                message=f"Model exceeds the printer build volume on axis or axes: {axes}.",
            )
        )
    return OrientationCandidateResult(
        orientation=orientation,
        facts=OrientationFacts(
            observed_dimensions=Vector3(*map(float, observed)),
            physical_dimensions=dimensions,
            print_height=dimensions.z,
            fits=fits,
            fits_x=fits_x,
            fits_y=fits_y,
            fits_z=fits_z,
            remaining_space=remaining_space,
            overflow=overflow,
            total_face_count=total_face_count,
            overhang_face_count=overhang_face_count,
            total_surface_area_square_units=total_area,
            overhang_surface_area_square_units=overhang_area,
            overhang_area_percentage=(overhang_area / total_area * 100.0)
            if total_area > 0.0
            else None,
            estimated_build_plate_contact_area_square_units=contact_area_model * area_scale,
        ),
        warnings=tuple(warnings),
    )


def _global_warnings(
    total_face_count: int, degenerate_face_count: int, total_area: float
) -> list[AnalysisWarning]:
    warnings = [
        AnalysisWarning(
            code="NORMAL_ORIENTATION_UNVERIFIED",
            message=(
                "Face-normal orientation is derived from triangle winding and was not "
                "verified or corrected. Orientation metrics assume outward normals."
            ),
        )
    ]
    if total_face_count == 0:
        warnings.append(AnalysisWarning(code="EMPTY_MESH", message="No faces were found in the STL file."))
    if degenerate_face_count:
        warnings.append(
            AnalysisWarning(
                code="DEGENERATE_FACES_IGNORED",
                message=(
                    f"{degenerate_face_count} face(s) with zero/invalid area or normal "
                    "were excluded from area, overhang, and build-plate contact calculations."
                ),
            )
        )
    if total_area == 0.0:
        warnings.append(
            AnalysisWarning(
                code="ZERO_TOTAL_SURFACE_AREA",
                message="Total valid surface area is zero; overhang percentage is unavailable.",
            )
        )
    return warnings


def _recommendation_key(candidate: OrientationCandidateResult) -> tuple[bool, float, float, float, str]:
    facts = candidate.facts
    return (
        not facts.fits,
        facts.overhang_surface_area_square_units,
        facts.print_height,
        -facts.estimated_build_plate_contact_area_square_units,
        candidate.orientation.name,
    )
