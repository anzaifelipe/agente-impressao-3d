import json

import pytest

from agente_impressao_3d.application.analyze_build_volume import AnalyzeBuildVolume
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
    ScaleAndUnitFacts,
)


def scaled_analysis(dimensions: Vector3, unit: str = "mm") -> ScaleAndUnitAnalysisResult:
    return ScaleAndUnitAnalysisResult(
        source_path="example.stl",
        facts=ScaleAndUnitFacts(
            observed_dimensions=dimensions,
            physical_dimensions=dimensions,
        ),
        configuration=ScaleAndUnitConfiguration(physical_unit=unit),
    )


def printer_profile(build_volume: Vector3 = Vector3(180.0, 180.0, 180.0)) -> PrinterProfile:
    return PrinterProfile(
        manufacturer="Bambu Lab",
        model="A1 Mini",
        build_volume=build_volume,
    )


def test_model_that_fits_reports_remaining_space_by_axis() -> None:
    result = AnalyzeBuildVolume().execute(
        scaled_analysis(Vector3(88.5, 100.0, 31.4)), printer_profile()
    )

    assert result.facts.fits is True
    assert (result.facts.fits_x, result.facts.fits_y, result.facts.fits_z) == (True, True, True)
    assert result.facts.remaining_space == Vector3(91.5, 80.0, 148.6)
    assert result.facts.overflow == Vector3(0.0, 0.0, 0.0)
    assert result.warnings == ()


@pytest.mark.parametrize(
    ("dimensions", "axis"),
    [
        (Vector3(200.0, 100.0, 50.0), "x"),
        (Vector3(100.0, 200.0, 50.0), "y"),
        (Vector3(100.0, 50.0, 200.0), "z"),
    ],
)
def test_model_exceeding_one_axis_reports_axis_specific_overflow(
    dimensions: Vector3, axis: str
) -> None:
    result = AnalyzeBuildVolume().execute(scaled_analysis(dimensions), printer_profile())

    assert result.facts.fits is False
    assert getattr(result.facts, f"fits_{axis}") is False
    assert getattr(result.facts.overflow, axis) == 20.0
    assert [warning.code for warning in result.warnings] == ["MODEL_EXCEEDS_BUILD_VOLUME"]


def test_model_exceeding_multiple_axes_reports_each_overflow() -> None:
    result = AnalyzeBuildVolume().execute(
        scaled_analysis(Vector3(200.0, 190.0, 50.0)), printer_profile()
    )

    assert (result.facts.fits_x, result.facts.fits_y, result.facts.fits_z) == (False, False, True)
    assert result.facts.overflow == Vector3(20.0, 10.0, 0.0)
    assert result.facts.remaining_space == Vector3(0.0, 0.0, 130.0)


def test_dimensions_equal_to_build_volume_fit_exactly() -> None:
    result = AnalyzeBuildVolume().execute(
        scaled_analysis(Vector3(180.0, 180.0, 180.0)), printer_profile()
    )

    assert result.facts.fits is True
    assert result.facts.remaining_space == Vector3(0.0, 0.0, 0.0)
    assert result.facts.overflow == Vector3(0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "build_volume",
    [
        Vector3(0.0, 180.0, 180.0),
        Vector3(180.0, -1.0, 180.0),
        Vector3(180.0, 180.0, float("nan")),
        Vector3(float("inf"), 180.0, 180.0),
    ],
)
def test_rejects_invalid_printer_build_volume(build_volume: Vector3) -> None:
    with pytest.raises(ValueError, match="build_volume"):
        printer_profile(build_volume)


def test_rejects_incompatible_units() -> None:
    with pytest.raises(ValueError, match="build_volume_unit"):
        AnalyzeBuildVolume().execute(
            scaled_analysis(Vector3(100.0, 100.0, 100.0), unit="in"), printer_profile()
        )


def test_serialized_result_is_json_friendly_and_declares_orientation() -> None:
    result = AnalyzeBuildVolume().execute(
        scaled_analysis(Vector3(200.0, 100.0, 50.0)), printer_profile()
    )

    serialized = result.to_dict()
    assert serialized["printer_profile"]["build_volume"] == {
        "x": 180.0,
        "y": 180.0,
        "z": 180.0,
    }
    assert serialized["facts"]["fits_x"] is False
    assert serialized["facts"]["overflow"]["x"] == 20.0
    assert serialized["assumptions"]["model_orientation"] == "as_provided"
    assert serialized["warnings"][0]["code"] == "MODEL_EXCEEDS_BUILD_VOLUME"
    json.dumps(serialized)
