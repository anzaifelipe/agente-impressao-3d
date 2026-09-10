from pathlib import Path

import pytest

from agente_impressao_3d.application.analyze_overhang import AnalyzeOverhang
from agente_impressao_3d.domain.overhang import OverhangAnalysisConfiguration
from agente_impressao_3d.infrastructure.trimesh_face_metrics_reader import (
    TrimeshFaceMetricsReader,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_cube_overhang_analysis_at_45_degrees() -> None:
    result = AnalyzeOverhang(TrimeshFaceMetricsReader()).execute(
        FIXTURES / "cube_ascii.stl",
        OverhangAnalysisConfiguration(threshold_degrees=45, batch_size=3),
    )

    assert result.facts.total_face_count == 12
    assert result.facts.overhang_face_count == 2
    assert result.facts.total_surface_area_square_units == pytest.approx(600.0)
    assert result.facts.overhang_surface_area_square_units == pytest.approx(100.0)
    assert result.facts.overhang_area_percentage == pytest.approx(100 / 600 * 100)
    assert [warning.code for warning in result.warnings] == ["NORMAL_ORIENTATION_UNVERIFIED"]


def test_face_at_the_45_degree_boundary_is_an_overhang() -> None:
    result = AnalyzeOverhang(TrimeshFaceMetricsReader()).execute(
        FIXTURES / "downward_45_ascii.stl",
        OverhangAnalysisConfiguration(threshold_degrees=45),
    )

    assert result.facts.total_face_count == 1
    assert result.facts.overhang_face_count == 1
    assert result.facts.total_surface_area_square_units == pytest.approx(2**0.5 / 2)
    assert result.facts.overhang_surface_area_square_units == pytest.approx(2**0.5 / 2)
