from pathlib import Path

from agente_impressao_3d.infrastructure.trimesh_triangle_geometry_reader import (
    TrimeshTriangleGeometryReader,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_reads_cube_as_bounded_triangle_batches() -> None:
    source = TrimeshTriangleGeometryReader().open(FIXTURES / "cube_ascii.stl")
    batches = list(source.iter_triangle_batches(batch_size=5))

    assert [batch.face_count for batch in batches] == [5, 5, 2]
    assert all(batch.vertices.shape[1:] == (3, 3) for batch in batches)
