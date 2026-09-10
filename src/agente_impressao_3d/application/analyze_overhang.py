"""Use case for batched, deterministic STL overhang analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agente_impressao_3d.domain.models import AnalysisWarning
from agente_impressao_3d.domain.overhang import (
    OverhangAnalysisAssumptions,
    OverhangAnalysisConfiguration,
    OverhangAnalysisResult,
    OverhangFacts,
)
from agente_impressao_3d.domain.ports import FaceMetricsReader


@dataclass(frozen=True, slots=True)
class AnalyzeOverhang:
    """Aggregates vectorized metrics while retaining no per-face Python objects."""

    face_metrics_reader: FaceMetricsReader

    def execute(
        self,
        source_path: Path,
        configuration: OverhangAnalysisConfiguration | None = None,
        assumptions: OverhangAnalysisAssumptions | None = None,
    ) -> OverhangAnalysisResult:
        config = configuration or OverhangAnalysisConfiguration()
        total_face_count = 0
        overhang_face_count = 0
        degenerate_face_count = 0
        total_area = 0.0
        overhang_area = 0.0

        for batch in self.face_metrics_reader.iter_face_metrics(source_path, config.batch_size):
            normal_z = batch.normal_z
            area = batch.area
            total_face_count += batch.face_count

            valid = np.isfinite(normal_z) & np.isfinite(area) & (area > 0.0)
            degenerate_face_count += batch.face_count - int(np.count_nonzero(valid))
            overhang = valid & (normal_z < 0.0) & (normal_z <= config.normal_z_limit)

            total_area += float(np.sum(area, where=valid, initial=0.0))
            overhang_area += float(np.sum(area, where=overhang, initial=0.0))
            overhang_face_count += int(np.count_nonzero(overhang))

        warnings: list[AnalysisWarning] = [
            AnalysisWarning(
                code="NORMAL_ORIENTATION_UNVERIFIED",
                message=(
                    "Face-normal orientation is derived from triangle winding and was "
                    "not verified or corrected. Overhang classification assumes outward normals."
                ),
            )
        ]
        if total_face_count == 0:
            warnings.append(
                AnalysisWarning(
                    code="EMPTY_MESH",
                    message="No faces were found in the STL file.",
                )
            )
        if degenerate_face_count:
            warnings.append(
                AnalysisWarning(
                    code="DEGENERATE_FACES_IGNORED",
                    message=(
                        f"{degenerate_face_count} face(s) with zero/invalid area or normal "
                        "were excluded from area and overhang calculations."
                    ),
                )
            )

        percentage = (overhang_area / total_area * 100.0) if total_area > 0.0 else None
        if total_area == 0.0:
            warnings.append(
                AnalysisWarning(
                    code="ZERO_TOTAL_SURFACE_AREA",
                    message="Total valid surface area is zero; overhang percentage is unavailable.",
                )
            )

        return OverhangAnalysisResult(
            source_path=str(source_path),
            facts=OverhangFacts(
                total_face_count=total_face_count,
                overhang_face_count=overhang_face_count,
                total_surface_area_square_units=total_area,
                overhang_surface_area_square_units=overhang_area,
                overhang_area_percentage=percentage,
            ),
            configuration=config,
            assumptions=assumptions or OverhangAnalysisAssumptions(),
            warnings=tuple(warnings),
        )
