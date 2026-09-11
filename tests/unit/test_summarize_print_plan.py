import json
from dataclasses import replace

import pytest

from agente_impressao_3d.application.analyze_print_plan import AnalyzePrintPlan
from agente_impressao_3d.application.summarize_print_plan import SummarizePrintPlan
from agente_impressao_3d.domain.build_volume import (
    BuildVolumeAnalysisAssumptions,
    BuildVolumeAnalysisResult,
    BuildVolumeFacts,
)
from agente_impressao_3d.domain.models import (
    AnalysisAssumptions,
    AnalysisWarning,
    BoundingBox,
    GeometryFacts,
    StlAnalysisResult,
    Vector3,
    Volume,
)
from agente_impressao_3d.domain.overhang import (
    OverhangAnalysisAssumptions,
    OverhangAnalysisConfiguration,
    OverhangAnalysisResult,
    OverhangFacts,
)
from agente_impressao_3d.domain.orientation import (
    PRINCIPAL_ORIENTATIONS,
    OrientationAnalysisAssumptions,
    OrientationAnalysisConfiguration,
    OrientationAnalysisFacts,
    OrientationAnalysisResult,
    OrientationCandidateResult,
    OrientationFacts,
)
from agente_impressao_3d.domain.print_recommendation import (
    PrintRecommendationConfiguration,
    PrintRecommendationResult,
    PrintRecommendationStatus,
    RecommendationWarning,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
    ScaleAndUnitFacts,
)


def print_plan(
    *,
    status: PrintRecommendationStatus = PrintRecommendationStatus.RECOMMENDED,
    selected: bool = True,
    fits: bool = True,
    overhang_percentage: float | None = 21.83,
    warnings: bool = False,
):
    source = "model.stl"
    profile = PrinterProfile("Example", "Printer", Vector3(200, 200, 200))
    stl = StlAnalysisResult(
        source,
        GeometryFacts(1, BoundingBox(Vector3(0, 0, 0), Vector3(1, 1, 1)), False, Volume(None, False)),
        AnalysisAssumptions(),
        (AnalysisWarning("STL_WARNING", "STL message"),) if warnings else (),
    )
    scale = ScaleAndUnitAnalysisResult(
        source,
        ScaleAndUnitFacts(Vector3(8.85, 10, 3.14), Vector3(88.5, 100, 31.4)),
        ScaleAndUnitConfiguration(physical_unit="mm"),
    )
    build = BuildVolumeAnalysisResult(
        source, profile,
        BuildVolumeFacts(Vector3(88.5, 100, 31.4), fits, fits, fits, fits, Vector3(1, 1, 1), Vector3(0, 0, 0)),
        BuildVolumeAnalysisAssumptions(),
        (AnalysisWarning("BUILD_WARNING", "Build message"),) if warnings else (),
    )
    candidate = OrientationCandidateResult(
        PRINCIPAL_ORIENTATIONS[5],
        OrientationFacts(Vector3(8.85, 10, 3.14), Vector3(88.5, 100, 31.4), 31.4, fits, fits, fits, fits,
                         Vector3(1, 1, 1), Vector3(0, 0, 0), 1, 0, 1, 0, overhang_percentage, 1),
    )
    orientation = OrientationAnalysisResult(
        source, profile, OrientationAnalysisConfiguration(), OrientationAnalysisAssumptions(),
        OrientationAnalysisFacts(1, 0), (candidate,), ("negative_z",), "negative_z",
        (AnalysisWarning("ORIENTATION_WARNING", "Orientation message"),) if warnings else (),
    )
    overhang = OverhangAnalysisResult(
        source, OverhangFacts(1, 0, 1, 0, overhang_percentage), OverhangAnalysisConfiguration(), OverhangAnalysisAssumptions(),
        (AnalysisWarning("NORMAL_ORIENTATION_UNVERIFIED", "Normals were not verified."),) if warnings else (),
    )
    recommendation_warnings = (
        (RecommendationWarning("print_recommendation", AnalysisWarning("RECOMMENDATION_WARNING", "Recommendation message")),)
        if warnings else ()
    )
    recommendation = PrintRecommendationResult(
        source, status, PrintRecommendationConfiguration(), candidate if selected else None, (), recommendation_warnings
    )
    return AnalyzePrintPlan().execute(stl, scale, build, overhang, orientation, recommendation)


def test_summarizes_complete_plan_and_serializes_json() -> None:
    result = SummarizePrintPlan().execute(print_plan(warnings=True))

    assert result.source_path == "model.stl"
    assert result.facts.physical_dimensions == Vector3(88.5, 100, 31.4)
    assert result.facts.physical_unit == "mm"
    assert result.facts.fits_build_volume is True
    assert result.facts.recommended_orientation == "negative_z"
    assert result.facts.print_height == 31.4
    assert result.facts.overhang_area_percentage == 21.83
    assert result.facts.recommendation_status == "recommended"
    assert [(warning.origin, warning.code) for warning in result.warnings] == [
        ("stl_analysis", "STL_WARNING"),
        ("build_volume_analysis", "BUILD_WARNING"),
        ("orientation_analysis", "ORIENTATION_WARNING"),
        ("overhang_analysis", "NORMAL_ORIENTATION_UNVERIFIED"),
        ("print_recommendation", "RECOMMENDATION_WARNING"),
    ]
    assert result.facts.warning_count == len(result.warnings) == 5
    serialized = result.to_dict()
    assert set(serialized) == {"schema_version", "source", "facts", "warnings"}
    assert serialized["source"] == {"path": "model.stl", "format": "stl"}
    json.dumps(serialized)


@pytest.mark.parametrize(
    ("status", "selected", "fits", "expected_orientation"),
    [
        (PrintRecommendationStatus.RECOMMENDED, True, True, "negative_z"),
        (PrintRecommendationStatus.PRINTABLE_WITH_WARNINGS, True, True, "negative_z"),
        (PrintRecommendationStatus.NOT_RECOMMENDED, False, True, None),
        (PrintRecommendationStatus.NOT_FIT, False, False, None),
    ],
)
def test_reflects_existing_recommendation_without_new_policy(status, selected, fits, expected_orientation) -> None:
    result = SummarizePrintPlan().execute(print_plan(status=status, selected=selected, fits=fits))

    assert result.facts.recommendation_status == status.value
    assert result.facts.recommended_orientation == expected_orientation
    assert result.facts.print_height == (31.4 if selected else None)
    assert result.facts.fits_build_volume is fits


def test_preserves_unavailable_overhang_as_none() -> None:
    result = SummarizePrintPlan().execute(print_plan(overhang_percentage=None))

    assert result.facts.overhang_area_percentage is None
