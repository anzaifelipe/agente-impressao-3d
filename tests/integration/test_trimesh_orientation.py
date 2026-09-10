from pathlib import Path

import pytest

from agente_impressao_3d.application.analyze_orientation import AnalyzeOrientation
from agente_impressao_3d.domain.models import Vector3
from agente_impressao_3d.domain.printer_profile import PrinterProfile
from agente_impressao_3d.infrastructure.trimesh_triangle_geometry_reader import (
    TrimeshTriangleGeometryReader,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def candidate(result: object, name: str) -> object:
    return next(item for item in result.candidates if item.orientation.name == name)


def test_cube_is_symmetric_across_principal_orientations() -> None:
    result = AnalyzeOrientation(TrimeshTriangleGeometryReader()).execute(
        FIXTURES / "cube_ascii.stl",
        PrinterProfile("Example", "Cube Printer", Vector3(10, 10, 10)),
    )

    assert {item.facts.print_height for item in result.candidates} == {10.0}
    assert {item.facts.overhang_surface_area_square_units for item in result.candidates} == {100.0}
    assert {item.facts.estimated_build_plate_contact_area_square_units for item in result.candidates} == {100.0}
    assert {item.facts.fits for item in result.candidates} == {True}


def test_asymmetric_fixture_permutates_dimensions_and_changes_build_volume_fit() -> None:
    result = AnalyzeOrientation(TrimeshTriangleGeometryReader()).execute(
        FIXTURES / "asymmetric_orientation_ascii.stl",
        PrinterProfile("Example", "Rectangular", Vector3(50, 100, 100)),
    )

    positive_x = candidate(result, "positive_x")
    positive_z = candidate(result, "positive_z")
    assert positive_x.facts.physical_dimensions == Vector3(40, 80, 100)
    assert positive_x.facts.print_height == pytest.approx(100)
    assert positive_x.facts.fits is True
    assert positive_z.facts.physical_dimensions == Vector3(100, 80, 40)
    assert positive_z.facts.print_height == pytest.approx(40)
    assert positive_z.facts.fits is False
