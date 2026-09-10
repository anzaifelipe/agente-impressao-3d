import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from agente_impressao_3d.application.analyze_orientation import (
    AnalyzeOrientation,
    _recommendation_key,
)
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.orientation import (
    PRINCIPAL_ORIENTATIONS,
    OrientationAnalysisConfiguration,
    OrientationCandidateResult,
    OrientationFacts,
    TriangleGeometryBatch,
)
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.domain.scale_and_unit import ScaleAndUnitConfiguration


class FakeTriangleSource:
    def __init__(self, *batches: TriangleGeometryBatch) -> None:
        self.batches = batches
        self.iterations = 0

    def iter_triangle_batches(self, batch_size: int) -> Iterator[TriangleGeometryBatch]:
        self.iterations += 1
        yield from self.batches


class FakeTriangleReader:
    def __init__(self, source: FakeTriangleSource) -> None:
        self.source = source
        self.open_calls = 0

    def open(self, source_path: Path) -> FakeTriangleSource:
        self.open_calls += 1
        return self.source


def batch(triangles: list[list[list[float]]]) -> TriangleGeometryBatch:
    return TriangleGeometryBatch(np.array(triangles, dtype=np.float64))


def profile(volume: Vector3 = Vector3(100.0, 100.0, 100.0)) -> PrinterProfile:
    return PrinterProfile("Example", "Printer", volume)


def analyze(
    *batches: TriangleGeometryBatch,
    printer: PrinterProfile | None = None,
    configuration: OrientationAnalysisConfiguration | None = None,
) -> tuple[object, FakeTriangleReader, FakeTriangleSource]:
    source = FakeTriangleSource(*batches)
    reader = FakeTriangleReader(source)
    result = AnalyzeOrientation(reader).execute(
        Path("example.stl"), printer or profile(), configuration
    )
    return result, reader, source


def box_triangles(x: float, y: float, z: float) -> list[list[list[float]]]:
    vertices = np.array(
        [
            [0, 0, 0], [x, 0, 0], [x, y, 0], [0, y, 0],
            [0, 0, z], [x, 0, z], [x, y, z], [0, y, z],
        ],
        dtype=np.float64,
    )
    faces = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return [vertices[list(face)].tolist() for face in faces]


def candidate(result: object, name: str) -> object:
    return next(item for item in result.candidates if item.orientation.name == name)


def test_exposes_six_principal_orientations_with_expected_directions() -> None:
    assert [orientation.name for orientation in PRINCIPAL_ORIENTATIONS] == [
        "positive_x", "negative_x", "positive_y", "negative_y", "positive_z", "negative_z"
    ]
    assert PRINCIPAL_ORIENTATIONS[0].build_direction == Vector3(1.0, 0.0, 0.0)
    assert PRINCIPAL_ORIENTATIONS[-1].build_direction == Vector3(0.0, 0.0, -1.0)


def test_permutates_dimensions_and_print_height_without_rotating_triangles() -> None:
    result, _, _ = analyze(batch(box_triangles(100, 80, 40)))

    assert candidate(result, "positive_x").facts.physical_dimensions == Vector3(40, 80, 100)
    assert candidate(result, "negative_x").facts.print_height == 100
    assert candidate(result, "positive_y").facts.physical_dimensions == Vector3(100, 40, 80)
    assert candidate(result, "negative_y").facts.print_height == 80
    assert candidate(result, "positive_z").facts.physical_dimensions == Vector3(100, 80, 40)


def test_build_volume_fit_overflow_and_exact_equality() -> None:
    result, _, _ = analyze(
        batch(box_triangles(100, 80, 40)), printer=profile(Vector3(50, 80, 100))
    )
    positive_z = candidate(result, "positive_z")
    positive_x = candidate(result, "positive_x")

    assert positive_z.facts.fits is False
    assert positive_z.facts.overflow == Vector3(50, 0, 0)
    assert positive_x.facts.fits is True
    assert positive_x.facts.remaining_space == Vector3(10, 0, 0)

    exact, _, _ = analyze(batch(box_triangles(100, 80, 40)), printer=profile(Vector3(100, 80, 40)))
    assert candidate(exact, "positive_z").facts.fits is True


@pytest.mark.parametrize(
    ("triangle", "overhang_orientation"),
    [
        ([[0, 0, 0], [0, 1, 0], [0, 0, 1]], "negative_x"),
        ([[0, 0, 0], [0, 0, 1], [0, 1, 0]], "positive_x"),
        ([[0, 0, 0], [0, 0, 1], [1, 0, 0]], "negative_y"),
        ([[0, 0, 0], [1, 0, 0], [0, 0, 1]], "positive_y"),
        ([[0, 0, 0], [1, 0, 0], [0, 1, 0]], "negative_z"),
        ([[0, 0, 0], [0, 1, 0], [1, 0, 0]], "positive_z"),
    ],
)
def test_overhang_uses_candidate_build_direction(
    triangle: list[list[float]], overhang_orientation: str
) -> None:
    result, _, _ = analyze(batch([triangle]))
    assert candidate(result, overhang_orientation).facts.overhang_face_count == 1


def test_includes_the_threshold_boundary() -> None:
    triangle = [[0, 0, 0], [0, 1, 0], [1, 0, -1]]
    result, _, _ = analyze(
        batch([triangle]), configuration=OrientationAnalysisConfiguration(threshold_degrees=45)
    )
    assert candidate(result, "positive_z").facts.overhang_face_count == 1


def test_estimates_contact_only_when_all_vertices_are_at_the_build_plate() -> None:
    floor = [[0, 0, 0], [0, 1, 0], [1, 0, 0]]
    raised_vertex = [[0, 0, 0], [0, 1, 0], [1, 0, 0.1]]
    result, _, _ = analyze(batch([floor, raised_vertex]))

    assert candidate(result, "positive_z").facts.estimated_build_plate_contact_area_square_units == pytest.approx(0.5)


def test_contact_tolerance_includes_nearby_face_only_when_configured() -> None:
    floor = [[0, 0, 0], [0, 1, 0], [1, 0, 0]]
    near_floor = [[0, 0, 0.005], [0, 1, 0.005], [1, 0, 0.005]]
    without_tolerance, _, _ = analyze(
        batch([floor, near_floor]),
        configuration=OrientationAnalysisConfiguration(bed_contact_tolerance_physical=0.001),
    )
    with_tolerance, _, _ = analyze(
        batch([floor, near_floor]),
        configuration=OrientationAnalysisConfiguration(bed_contact_tolerance_physical=0.01),
    )

    assert candidate(without_tolerance, "positive_z").facts.estimated_build_plate_contact_area_square_units == pytest.approx(0.5)
    assert candidate(with_tolerance, "positive_z").facts.estimated_build_plate_contact_area_square_units == pytest.approx(1.0)


def test_uses_one_open_and_multiple_batches_while_ignoring_degenerate_faces() -> None:
    valid = batch([[[0, 0, 0], [0, 1, 0], [1, 0, 0]]])
    degenerate = batch([[[0, 0, 0], [0, 0, 0], [0, 0, 0]]])
    result, reader, source = analyze(valid, degenerate)

    assert reader.open_calls == 1
    assert source.iterations == 2
    assert result.facts.total_face_count == 2
    assert result.facts.degenerate_face_count == 1
    assert {warning.code for warning in result.warnings} == {
        "NORMAL_ORIENTATION_UNVERIFIED", "DEGENERATE_FACES_IGNORED"
    }


def test_rejects_incompatible_units_before_opening_reader() -> None:
    source = FakeTriangleSource(batch(box_triangles(1, 1, 1)))
    reader = FakeTriangleReader(source)
    config = OrientationAnalysisConfiguration(
        scale_and_unit=ScaleAndUnitConfiguration(physical_unit="in")
    )
    with pytest.raises(ValueError, match="build_volume_unit"):
        AnalyzeOrientation(reader).execute(Path("example.stl"), profile(), config)
    assert reader.open_calls == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold_degrees": -0.1}, {"threshold_degrees": float("nan")},
        {"batch_size": 0}, {"bed_contact_tolerance_physical": -0.1},
        {"bed_contact_tolerance_physical": float("inf")},
    ],
)
def test_rejects_invalid_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        OrientationAnalysisConfiguration(**kwargs)


def test_orders_candidates_by_fit_overhang_height_contact_and_name() -> None:
    result, _, _ = analyze(batch(box_triangles(100, 80, 40)), printer=profile(Vector3(50, 100, 100)))
    assert result.ordered_orientation_names[0] == "negative_x"
    assert result.recommended_orientation_name == "negative_x"
    assert result.ordered_orientation_names.index("positive_x") < result.ordered_orientation_names.index("positive_z")


def test_recommendation_key_applies_all_declared_tie_breakers() -> None:
    def ranked(
        orientation_index: int, fits: bool, overhang: float, height: float, contact: float
    ) -> OrientationCandidateResult:
        return OrientationCandidateResult(
            orientation=PRINCIPAL_ORIENTATIONS[orientation_index],
            facts=OrientationFacts(
                observed_dimensions=Vector3(1, 1, 1), physical_dimensions=Vector3(1, 1, height),
                print_height=height, fits=fits, fits_x=fits, fits_y=fits, fits_z=fits,
                remaining_space=Vector3(0, 0, 0), overflow=Vector3(0, 0, 0),
                total_face_count=1, overhang_face_count=0, total_surface_area_square_units=1,
                overhang_surface_area_square_units=overhang, overhang_area_percentage=0,
                estimated_build_plate_contact_area_square_units=contact,
            ),
        )

    candidates = [
        ranked(0, False, 0, 0, 0),  # fit has priority over every later metric
        ranked(1, True, 2, 1, 9),   # worse overhang
        ranked(2, True, 1, 2, 9),   # worse height
        ranked(3, True, 1, 1, 1),   # worse contact
        ranked(4, True, 1, 1, 2),   # name resolves final equal-contact tie
        ranked(5, True, 1, 1, 2),
    ]

    assert [item.orientation.name for item in sorted(candidates, key=_recommendation_key)] == [
        "negative_z", "positive_z", "negative_y", "positive_y", "negative_x", "positive_x"
    ]


def test_serializes_json_friendly_result() -> None:
    result, _, _ = analyze(batch(box_triangles(10, 8, 4)))
    serialized = result.to_dict()
    assert serialized["recommended_orientation_name"] in serialized["ordered_orientation_names"]
    assert serialized["assumptions"]["automatic_arbitrary_rotation"] == "not performed"
    json.dumps(serialized)
