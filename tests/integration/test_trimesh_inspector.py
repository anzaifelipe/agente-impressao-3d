from pathlib import Path

import pytest

from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.infrastructure.trimesh_inspector import TrimeshMeshInspector


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_closed_cube_analysis() -> None:
    result = AnalyzeStl(TrimeshMeshInspector()).execute(FIXTURES / "cube_ascii.stl")

    assert result.facts.triangle_count == 12
    assert result.facts.bounding_box.dimensions.x == pytest.approx(10)
    assert result.facts.bounding_box.dimensions.y == pytest.approx(10)
    assert result.facts.bounding_box.dimensions.z == pytest.approx(10)
    assert result.facts.watertight is True
    assert result.facts.volume.reliable is True
    assert result.facts.volume.cubic_units == pytest.approx(1000.0)
    assert result.warnings == ()


def test_open_mesh_has_no_reliable_volume_and_a_structured_warning() -> None:
    result = AnalyzeStl(TrimeshMeshInspector()).execute(FIXTURES / "open_triangle_ascii.stl")

    assert result.facts.triangle_count == 1
    assert result.facts.bounding_box.dimensions.x == pytest.approx(10)
    assert result.facts.bounding_box.dimensions.y == pytest.approx(10)
    assert result.facts.bounding_box.dimensions.z == pytest.approx(0)
    assert result.facts.watertight is False
    assert result.facts.volume.cubic_units is None
    assert result.facts.volume.reliable is False
    assert [warning.code for warning in result.warnings] == ["MESH_NOT_WATERTIGHT"]
