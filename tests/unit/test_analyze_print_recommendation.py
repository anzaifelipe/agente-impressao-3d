import json

import pytest

from agente_impressao_3d.application.analyze_print_recommendation import (
    AnalyzePrintRecommendation,
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
    PrintRecommendationStatus,
    RecommendationReasonCode,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile


def stl_result(warnings: tuple[AnalysisWarning, ...] = ()) -> StlAnalysisResult:
    return StlAnalysisResult(
        source_path="example.stl",
        facts=GeometryFacts(
            triangle_count=12,
            bounding_box=BoundingBox(Vector3(0, 0, 0), Vector3(10, 10, 10)),
            watertight=True,
            volume=Volume(cubic_units=1000, reliable=True),
        ),
        assumptions=AnalysisAssumptions(),
        warnings=warnings,
    )


def orientation_candidate(
    index: int, *, fits: bool = True, overhang_percentage: float = 10.0
) -> OrientationCandidateResult:
    return OrientationCandidateResult(
        orientation=PRINCIPAL_ORIENTATIONS[index],
        facts=OrientationFacts(
            observed_dimensions=Vector3(10, 10, 10),
            physical_dimensions=Vector3(10, 10, 10),
            print_height=10.0,
            fits=fits,
            fits_x=fits,
            fits_y=fits,
            fits_z=fits,
            remaining_space=Vector3(0, 0, 0),
            overflow=Vector3(0, 0, 0),
            total_face_count=12,
            overhang_face_count=1,
            total_surface_area_square_units=100.0,
            overhang_surface_area_square_units=overhang_percentage,
            overhang_area_percentage=overhang_percentage,
            estimated_build_plate_contact_area_square_units=25.0,
        ),
    )


def orientation_result(
    candidates: tuple[OrientationCandidateResult, ...],
    ordered_names: tuple[str, ...],
    *,
    face_count: int = 12,
    warnings: tuple[AnalysisWarning, ...] = (),
) -> OrientationAnalysisResult:
    return OrientationAnalysisResult(
        source_path="example.stl",
        printer_profile=PrinterProfile("Example", "Printer", Vector3(100, 100, 100)),
        configuration=OrientationAnalysisConfiguration(),
        assumptions=OrientationAnalysisAssumptions(),
        facts=OrientationAnalysisFacts(face_count, 0),
        candidates=candidates,
        ordered_orientation_names=ordered_names,
        recommended_orientation_name=ordered_names[0] if ordered_names else "",
        warnings=warnings,
    )


def test_recommends_first_compatible_candidate_in_existing_ranking() -> None:
    positive_x = orientation_candidate(0)
    negative_z = orientation_candidate(5)
    result = AnalyzePrintRecommendation().execute(
        stl_result(),
        orientation_result((positive_x, negative_z), ("negative_z", "positive_x")),
    )

    assert result.status is PrintRecommendationStatus.RECOMMENDED
    assert result.recommended_candidate is negative_z
    assert [reason.code for reason in result.reasons] == [
        RecommendationReasonCode.MODEL_FITS_BUILD_VOLUME,
        RecommendationReasonCode.BEST_ORIENTATION_SELECTED,
    ]


def test_skips_non_fitting_ranked_candidate_without_reordering() -> None:
    first = orientation_candidate(0, fits=False)
    second = orientation_candidate(1, fits=True)
    result = AnalyzePrintRecommendation().execute(
        stl_result(),
        orientation_result((second, first), ("positive_x", "negative_x")),
    )

    assert result.status is PrintRecommendationStatus.RECOMMENDED
    assert result.recommended_candidate is second


def test_returns_not_fit_when_all_ranked_candidates_do_not_fit() -> None:
    first = orientation_candidate(0, fits=False)
    second = orientation_candidate(1, fits=False)
    result = AnalyzePrintRecommendation().execute(
        stl_result(),
        orientation_result((first, second), ("positive_x", "negative_x")),
    )

    assert result.status is PrintRecommendationStatus.NOT_FIT
    assert result.recommended_candidate is None
    assert result.reasons[0].code is RecommendationReasonCode.MODEL_DOES_NOT_FIT_BUILD_VOLUME


def test_empty_mesh_is_not_recommended() -> None:
    result = AnalyzePrintRecommendation().execute(
        stl_result(),
        orientation_result(
            (), (), face_count=0,
            warnings=(AnalysisWarning("EMPTY_MESH", "No faces were found."),),
        ),
    )

    assert result.status is PrintRecommendationStatus.NOT_RECOMMENDED
    assert result.recommended_candidate is None
    assert result.reasons[0].code is RecommendationReasonCode.EMPTY_MESH


def test_empty_ranking_is_not_recommended() -> None:
    result = AnalyzePrintRecommendation().execute(stl_result(), orientation_result((), ()))

    assert result.status is PrintRecommendationStatus.NOT_RECOMMENDED
    assert result.reasons[0].code is RecommendationReasonCode.NO_VALID_ORIENTATION


@pytest.mark.parametrize(
    ("percentage", "expected_status"),
    [
        (50.1, PrintRecommendationStatus.PRINTABLE_WITH_WARNINGS),
        (50.0, PrintRecommendationStatus.RECOMMENDED),
        (49.9, PrintRecommendationStatus.RECOMMENDED),
    ],
)
def test_applies_configured_overhang_policy(
    percentage: float, expected_status: PrintRecommendationStatus
) -> None:
    chosen = orientation_candidate(0, overhang_percentage=percentage)
    result = AnalyzePrintRecommendation().execute(
        stl_result(),
        orientation_result((chosen,), ("positive_x",)),
        PrintRecommendationConfiguration(50.0),
    )

    assert result.status is expected_status
    if expected_status is PrintRecommendationStatus.PRINTABLE_WITH_WARNINGS:
        assert result.reasons[-1].code is (
            RecommendationReasonCode.OVERHANG_EXCEEDS_RECOMMENDED_THRESHOLD
        )


@pytest.mark.parametrize("value", [-0.1, 100.1, float("nan"), float("inf")])
def test_rejects_invalid_overhang_recommendation_limits(value: float) -> None:
    with pytest.raises(ValueError, match="maximum_recommended_overhang"):
        PrintRecommendationConfiguration(value)


def test_preserves_warning_codes_and_origins_without_reducing_normal_warning_status() -> None:
    normal_warning = AnalysisWarning("NORMAL_ORIENTATION_UNVERIFIED", "Normals are winding-derived.")
    mesh_warning = AnalysisWarning("MESH_NOT_WATERTIGHT", "Mesh is open.")
    chosen = orientation_candidate(0)
    result = AnalyzePrintRecommendation().execute(
        stl_result((mesh_warning,)),
        orientation_result((chosen,), ("positive_x",), warnings=(normal_warning,)),
    )

    assert result.status is PrintRecommendationStatus.RECOMMENDED
    assert [(item.origin, item.warning.code) for item in result.warnings] == [
        ("stl_analysis", "MESH_NOT_WATERTIGHT"),
        ("orientation_analysis", "NORMAL_ORIENTATION_UNVERIFIED"),
    ]


def test_serializes_recommendation_to_json() -> None:
    chosen = orientation_candidate(0)
    result = AnalyzePrintRecommendation().execute(
        stl_result(), orientation_result((chosen,), ("positive_x",))
    )

    serialized = result.to_dict()
    assert serialized["recommended_orientation"] == "positive_x"
    assert serialized["warnings"] == []
    json.dumps(serialized)
