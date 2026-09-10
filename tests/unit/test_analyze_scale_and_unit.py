import json

import pytest

from agente_impressao_3d.application.analyze_scale_and_unit import AnalyzeScaleAndUnit
from agente_impressao_3d.domain.models import (
    AnalysisAssumptions,
    BoundingBox,
    GeometryFacts,
    StlAnalysisResult,
    Vector3,
    Volume,
)
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration


def stl_analysis_result() -> StlAnalysisResult:
    return StlAnalysisResult(
        source_path="example.stl",
        facts=GeometryFacts(
            triangle_count=12,
            bounding_box=BoundingBox(
                minimum=Vector3(0.0, 0.0, 0.0),
                maximum=Vector3(0.885, 1.0, 0.314),
            ),
            watertight=True,
            volume=Volume(cubic_units=1.0, reliable=True),
        ),
        assumptions=AnalysisAssumptions(),
    )


def test_default_scale_factor_preserves_dimensions() -> None:
    stl_analysis = stl_analysis_result()

    result = AnalyzeScaleAndUnit().execute(stl_analysis)

    expected_dimensions = stl_analysis.facts.bounding_box.dimensions
    assert result.configuration.scale_factor == 1.0
    assert result.facts.observed_dimensions == expected_dimensions
    assert result.facts.physical_dimensions == expected_dimensions


def test_scale_factor_100_calculates_physical_dimensions() -> None:
    result = AnalyzeScaleAndUnit().execute(
        stl_analysis_result(),
        ScaleAndUnitConfiguration(scale_factor=100, physical_unit="mm"),
    )

    assert result.facts.observed_dimensions == Vector3(0.885, 1.0, 0.314)
    assert result.facts.physical_dimensions.x == pytest.approx(88.5)
    assert result.facts.physical_dimensions.y == pytest.approx(100.0)
    assert result.facts.physical_dimensions.z == pytest.approx(31.4)
    assert result.configuration.physical_unit == "mm"


@pytest.mark.parametrize("scale_factor", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_rejects_non_positive_or_non_finite_scale_factors(scale_factor: float) -> None:
    with pytest.raises(ValueError, match="scale_factor"):
        ScaleAndUnitConfiguration(scale_factor=scale_factor)


def test_serialized_result_keeps_observed_and_physical_dimensions_distinct() -> None:
    result = AnalyzeScaleAndUnit().execute(
        stl_analysis_result(),
        ScaleAndUnitConfiguration(scale_factor=100, physical_unit="mm"),
    )

    serialized = result.to_dict()
    assert serialized["facts"]["observed_dimensions"] == {
        "x": 0.885,
        "y": 1.0,
        "z": 0.314,
    }
    assert serialized["facts"]["physical_dimensions"] == {
        "x": 88.5,
        "y": 100.0,
        "z": 31.4,
    }
    assert serialized["configuration"] == {
        "scale_factor": 100,
        "physical_unit": "mm",
    }
    json.dumps(serialized)
