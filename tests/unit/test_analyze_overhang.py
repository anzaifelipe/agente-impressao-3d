from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.domain.overhang import (
    FaceMetricsBatch,
    OverhangAnalysisConfiguration,
)


class FakeFaceMetricsReader:
    def __init__(self, *batches: FaceMetricsBatch) -> None:
        self.batches = batches

    def iter_face_metrics(
        self, source_path: Path, batch_size: int
    ) -> Iterator[FaceMetricsBatch]:
        yield from self.batches


def batch(normal_z: list[float], area: list[float]) -> FaceMetricsBatch:
    return FaceMetricsBatch(np.array(normal_z), np.array(area))


def test_classifies_downward_faces_and_includes_the_45_degree_boundary() -> None:
    result = AnalyzeOverhang(
        FakeFaceMetricsReader(batch([-1.0, -np.sqrt(0.5), 0.0, 1.0], [2, 3, 5, 7]))
    ).execute(Path("example.stl"), OverhangAnalysisConfiguration(threshold_degrees=45))

    assert result.facts.total_face_count == 4
    assert result.facts.overhang_face_count == 2
    assert result.facts.total_surface_area_square_units == pytest.approx(17)
    assert result.facts.overhang_surface_area_square_units == pytest.approx(5)
    assert result.facts.overhang_area_percentage == pytest.approx(5 / 17 * 100)


def test_uses_multiple_batches_and_ignores_degenerate_faces() -> None:
    result = AnalyzeOverhang(
        FakeFaceMetricsReader(
            batch([-1.0, np.nan], [2.0, 0.0]),
            batch([0.0, -1.0], [4.0, np.nan]),
        )
    ).execute(Path("example.stl"))

    assert result.facts.total_face_count == 4
    assert result.facts.overhang_face_count == 1
    assert result.facts.total_surface_area_square_units == pytest.approx(6.0)
    assert result.facts.overhang_surface_area_square_units == pytest.approx(2.0)
    assert {warning.code for warning in result.warnings} == {
        "NORMAL_ORIENTATION_UNVERIFIED",
        "DEGENERATE_FACES_IGNORED",
    }


def test_serialized_result_exposes_the_approved_angle_convention() -> None:
    result = AnalyzeOverhang(FakeFaceMetricsReader()).execute(Path("empty.stl"))
    serialized = result.to_dict()

    convention = serialized["configuration"]["angle_convention"]
    assert convention["boundary_inclusive"] is True
    assert "theta >= 90 degrees + threshold_degrees" in convention["overhang_condition"]
    assert serialized["assumptions"]["outward_normal_orientation"] == "assumed, not verified or corrected"
    assert {warning["code"] for warning in serialized["warnings"]} == {
        "NORMAL_ORIENTATION_UNVERIFIED",
        "EMPTY_MESH",
        "ZERO_TOTAL_SURFACE_AREA",
    }


@pytest.mark.parametrize("threshold", [-0.1, 90.1])
def test_rejects_thresholds_outside_the_supported_range(threshold: float) -> None:
    with pytest.raises(ValueError, match="threshold_degrees"):
        OverhangAnalysisConfiguration(threshold_degrees=threshold)
