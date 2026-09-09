from pathlib import Path

from agente_impressao_3d.application.analyze_stl import AnalyzeStl
from agente_impressao_3d.domain.models import (
    BoundingBox,
    GeometryFacts,
    MeshInspection,
    Vector3,
    Volume,
)


class FakeMeshInspector:
    def inspect(self, source_path: Path) -> MeshInspection:
        return MeshInspection(
            facts=GeometryFacts(
                triangle_count=12,
                bounding_box=BoundingBox(Vector3(0, 0, 0), Vector3(1, 2, 3)),
                watertight=True,
                volume=Volume(cubic_units=6, reliable=True),
            )
        )


def test_use_case_adds_explicit_unit_assumption() -> None:
    result = AnalyzeStl(FakeMeshInspector()).execute(Path("example.stl"))

    assert result.assumptions.coordinate_unit == "mm"
    assert result.to_dict()["facts"]["bounding_box"]["dimensions"] == {
        "x": 1,
        "y": 2,
        "z": 3,
    }
