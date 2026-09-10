import json
from dataclasses import replace

import pytest

from agente_impressao_3d.application.analyze_print_plan import AnalyzePrintPlan
from agente_impressao_3d.domain.build_volume import (
    BuildVolumeAnalysisAssumptions,
    BuildVolumeAnalysisResult,
    BuildVolumeFacts,
)
from agente_impressao_3d.domain.models import (
    AnalysisAssumptions,
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
    PrintRecommendationResult,
    PrintRecommendationStatus,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import (
    ScaleAndUnitAnalysisResult,
    ScaleAndUnitConfiguration,
    ScaleAndUnitFacts,
)


def analyses() -> tuple[
    StlAnalysisResult,
    ScaleAndUnitAnalysisResult,
    BuildVolumeAnalysisResult,
    OrientationAnalysisResult,
    PrintRecommendationResult,
]:
    source_path = "example.stl"
    printer = PrinterProfile("Example", "Printer", Vector3(100, 100, 100))
    stl = StlAnalysisResult(
        source_path=source_path,
        facts=GeometryFacts(
            triangle_count=1,
            bounding_box=BoundingBox(Vector3(0, 0, 0), Vector3(1, 1, 1)),
            watertight=False,
            volume=Volume(cubic_units=None, reliable=False),
        ),
        assumptions=AnalysisAssumptions(),
    )
    scale = ScaleAndUnitAnalysisResult(
        source_path=source_path,
        facts=ScaleAndUnitFacts(Vector3(1, 1, 1), Vector3(1, 1, 1)),
        configuration=ScaleAndUnitConfiguration(),
    )
    build = BuildVolumeAnalysisResult(
        source_path=source_path,
        printer_profile=printer,
        facts=BuildVolumeFacts(
            physical_dimensions=Vector3(1, 1, 1), fits=True,
            fits_x=True, fits_y=True, fits_z=True,
            remaining_space=Vector3(99, 99, 99), overflow=Vector3(0, 0, 0),
        ),
        assumptions=BuildVolumeAnalysisAssumptions(),
    )
    candidate = OrientationCandidateResult(
        orientation=PRINCIPAL_ORIENTATIONS[4],
        facts=OrientationFacts(
            observed_dimensions=Vector3(1, 1, 1), physical_dimensions=Vector3(1, 1, 1),
            print_height=1, fits=True, fits_x=True, fits_y=True, fits_z=True,
            remaining_space=Vector3(99, 99, 99), overflow=Vector3(0, 0, 0),
            total_face_count=1, overhang_face_count=0, total_surface_area_square_units=1,
            overhang_surface_area_square_units=0, overhang_area_percentage=0,
            estimated_build_plate_contact_area_square_units=0.5,
        ),
    )
    orientation = OrientationAnalysisResult(
        source_path=source_path,
        printer_profile=printer,
        configuration=OrientationAnalysisConfiguration(),
        assumptions=OrientationAnalysisAssumptions(),
        facts=OrientationAnalysisFacts(total_face_count=1, degenerate_face_count=0),
        candidates=(candidate,),
        ordered_orientation_names=("positive_z",),
        recommended_orientation_name="positive_z",
    )
    recommendation = PrintRecommendationResult(
        source_path=source_path,
        status=PrintRecommendationStatus.RECOMMENDED,
        configuration=PrintRecommendationConfiguration(),
        recommended_candidate=candidate,
        reasons=(),
        warnings=(),
    )
    return stl, scale, build, orientation, recommendation


def test_composes_the_same_result_instances() -> None:
    inputs = analyses()

    result = AnalyzePrintPlan().execute(*inputs)

    assert result.stl_analysis is inputs[0]
    assert result.scale_and_unit_analysis is inputs[1]
    assert result.build_volume_analysis is inputs[2]
    assert result.orientation_analysis is inputs[3]
    assert result.print_recommendation_analysis is inputs[4]


def test_accepts_consistent_sources_and_serializes_composed_analyses() -> None:
    result = AnalyzePrintPlan().execute(*analyses())

    serialized = result.to_dict()
    assert serialized["schema_version"] == "1.0"
    assert serialized["source"] == {"path": "example.stl", "format": "stl"}
    assert set(serialized["analyses"]) == {
        "stl", "scale_and_unit", "build_volume", "orientation", "print_recommendation"
    }
    json.dumps(serialized)


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_rejects_inconsistent_sources(index: int) -> None:
    inputs = list(analyses())
    inputs[index] = replace(inputs[index], source_path="other.stl")

    with pytest.raises(ValueError, match="same source_path"):
        AnalyzePrintPlan().execute(*inputs)
